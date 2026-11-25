-- Pure table-data entry point. Not loaded by any CE or product entry point.
-- load_module(name, env) loads the two existing scoring modules into env.
local M = {}

local function require_value(ok, code)
  if not ok then error(code, 0) end
end

local function integer(value, low, high)
  return type(value) == 'number' and value == value and value % 1 == 0
    and value >= low and value <= high
end

local function plain_table(value)
  return type(value) == 'table' and getmetatable(value) == nil
end

local function array_size(value)
  require_value(plain_table(value), 'OFFLINE_INVALID_RECORDS: plain array required')
  local count = 0
  for key in pairs(value) do
    count = count + 1
    require_value(integer(key, 1, #value), 'OFFLINE_INVALID_RECORDS: dense array required')
  end
  require_value(count == #value, 'OFFLINE_INVALID_RECORDS: dense array required')
  return count
end

local OPTION_KEYS = {
  population_mode=true, scan_budget=true, max_candidates=true,
  target_value_pattern=true, target_value_float=true, session_id=true,
  filter_target_match=true, use_prescore_selection=true,
}

local function options(input)
  if input == nil then input = {} end
  require_value(plain_table(input), 'OFFLINE_INVALID_OPTIONS: plain table required')
  local opts = {}
  for key, value in pairs(input) do
    require_value(OPTION_KEYS[key], 'OFFLINE_INVALID_OPTIONS: ' .. tostring(key))
    opts[key] = value
  end
  if opts.population_mode == nil then opts.population_mode = 'bounded' end
  require_value(opts.population_mode == 'bounded' or opts.population_mode == 'full',
    'OFFLINE_INVALID_OPTIONS: population_mode must be bounded or full')
  require_value(integer(opts.target_value_pattern, 0, 0xFFFFFFFF),
    'OFFLINE_INVALID_OPTIONS: target_value_pattern must be uint32')
  require_value(opts.target_value_float == nil or (type(opts.target_value_float) == 'number'
    and opts.target_value_float == opts.target_value_float and math.abs(opts.target_value_float) < math.huge),
    'OFFLINE_INVALID_OPTIONS: target_value_float must be finite')
  require_value(opts.session_id == nil or type(opts.session_id) == 'string',
    'OFFLINE_INVALID_OPTIONS: session_id must be a string')
  for _, key in ipairs({'filter_target_match', 'use_prescore_selection'}) do
    require_value(opts[key] == nil or opts[key] == true, 'OFFLINE_INVALID_OPTIONS: ' .. key)
    opts[key] = true
  end
  if opts.population_mode == 'full' then
    require_value(opts.scan_budget == nil and opts.max_candidates == nil,
      'OFFLINE_INVALID_OPTIONS: full mode forbids count budgets')
  else
    -- Same defaults and validation as the existing bounded scan settings.
    if opts.scan_budget == nil then opts.scan_budget = 2000 end
    if opts.max_candidates == nil then opts.max_candidates = 20 end
    require_value(integer(opts.scan_budget, 1, 65536) and integer(opts.max_candidates, 1, 128)
      and opts.max_candidates <= opts.scan_budget, 'OFFLINE_INVALID_OPTIONS: INVALID_SCAN_SETTINGS')
  end
  opts.probe_full_foundlist = false
  opts.stable_filter_intersection_enabled = false
  return opts
end

local function same_words(a, b)
  for key, value in pairs(a) do if b[key] ~= value then return false end end
  for key, value in pairs(b) do if a[key] ~= value then return false end end
  return true
end

local function population(records, pattern)
  local supplied_count = array_size(records)
  local supplied, distinct, eligible, found, by_id, words = {}, {}, {}, {}, {}, {}
  for _, record in ipairs(records) do
    require_value(plain_table(record) and integer(record.addr, 1, 2^53 - 1)
      and type(record.mapped) == 'boolean' and integer(record.protect, 0, 0xFFFFFFFF)
      and plain_table(record.memory), 'OFFLINE_INVALID_RECORDS: malformed record')
    for key, value in pairs(record.memory) do
      require_value(integer(key, 1, 2^53 - 1) and integer(value, 0, 0xFFFFFFFF),
        'OFFLINE_INVALID_RECORDS: memory must contain numeric uint32 words')
      -- Match the existing table fixture: unmapped records cannot supply reads.
      if record.mapped then
        require_value(words[key] == nil or words[key] == value,
          'OFFLINE_INVALID_RECORDS: conflicting word')
        words[key] = value
      end
    end
    local previous = by_id[record.addr]
    if previous then
      require_value(previous.mapped == record.mapped and previous.protect == record.protect
        and same_words(previous.memory, record.memory), 'OFFLINE_INVALID_RECORDS: conflicting duplicate')
    else
      by_id[record.addr] = record
      distinct[#distinct + 1] = record.addr
    end
    supplied[#supplied + 1] = record.addr
    -- Exactly the existing frozen offline FoundList eligibility predicate.
    if record.mapped and record.protect == 4 and record.memory[record.addr] == pattern then
      found[#found + 1] = record.addr
      if not previous then eligible[#eligible + 1] = record.addr end
    end
  end
  return supplied_count, {supplied=supplied, distinct=distinct, eligible=eligible}, found, words
end

local function environment(found, words)
  -- Deliberately no ambient-global fallback, process API, I/O or module loader.
  local env = {
    assert=assert, error=error, ipairs=ipairs, pairs=pairs, next=next, pcall=pcall,
    select=select, tonumber=tonumber, tostring=tostring, type=type,
    math=math, string=string, table=table, debug={getinfo=debug.getinfo},
    os={clock=os.clock}, print=function() end,
  }
  env._G = env
  env.readInteger = function(addr) return words[addr] end
  env.readFloat = function(addr)
    if words[addr] == nil then return nil end
    return string.unpack('<f', string.pack('<I4', words[addr]))
  end
  env.getAddress = function(addr) return type(addr) == 'number' and addr or tonumber(addr, 16) end
  env.getCurrentMemscan = function() return {} end
  env.createFoundList = function()
    local list = {Count=#found, Address={}}
    for index, addr in ipairs(found) do list.Address[index - 1] = addr end
    list.initialize = function() end
    list.destroy = function() end
    return list
  end
  return env
end

local function complete_result(result, bundle, eligible, report, env)
  local function check(ok) require_value(ok, 'OFFLINE_INCOMPLETE_RESULT') end
  check(type(result) == 'table' and type(result.ranked) == 'table')
  local expected, seen, families = {}, {}, {}
  for _, addr in ipairs(eligible) do expected[addr] = true end
  local selected, selected_count = {}, 0
  for _, addr in ipairs(bundle.candidate_value_addrs) do
    check(expected[addr] and not selected[addr])
    selected[addr] = true
    selected_count = selected_count + 1
  end
  check(#result.ranked == bundle.selected_count and selected_count == bundle.selected_count)
  local completed_count = 0
  for index, scored in ipairs(result.ranked) do
    completed_count = completed_count + 1
    local candidate = scored.candidate
    check(type(candidate) == 'table' and selected[candidate.value_addr] and not seen[candidate.value_addr])
    seen[candidate.value_addr] = true
    check(scored.rank_position == index and type(scored.local_features) == 'table'
      and type(scored.local_features.advanced_layout) == 'table'
      and type(scored.template_family_id) == 'string' and type(scored.clone_family_id) == 'string'
      and type(scored.score_breakdown) == 'string' and type(scored.tie_break_vector) == 'string'
      and type(scored.rank_reason) == 'string')
    for _, key in ipairs({'base_score', 'final_score', 'total_adjustment'}) do
      check(type(scored[key]) == 'number' and scored[key] == scored[key] and math.abs(scored[key]) < math.huge)
    end
    check(scored.score == scored.final_score and scored.final_score == scored.base_score + scored.total_adjustment)
    check(candidate.base_addr == candidate.value_addr - report.CONFIG.value_offset)
    for key, offset in pairs(report.CONFIG.offsets) do
      check(candidate[key] == env.readInteger(candidate.base_addr + offset))
    end
    local expected_float = env.readFloat(candidate.value_addr)
    check(candidate.f28_float == expected_float or
      (candidate.f28_float ~= candidate.f28_float and expected_float ~= expected_float))
    if index > 1 then check(not report.compare_final_candidates(scored, result.ranked[index - 1])) end
    families[scored.clone_family_id] = (families[scored.clone_family_id] or 0) + 1
  end
  check(completed_count == selected_count)
  for _, scored in ipairs(result.ranked) do
    check(scored.template_family_size == families[scored.clone_family_id])
  end
  check(result.best == result.ranked[1] and result.second == result.ranked[2]
    and type(result.recommendation) == 'table' and result.final_decision == result.recommendation
    and result.recommendation.recommended_candidate == result.best and type(result.report_text) == 'string')
end

function M.run(records, input_options, load_module)
  local opts = options(input_options)
  require_value(type(load_module) == 'function', 'OFFLINE_INVALID_LOADER')
  local supplied_count, identities, found, words = population(records, opts.target_value_pattern)
  local mode = opts.population_mode
  opts.population_mode = nil
  if mode == 'full' then
    -- Exact finite input size, never a magic sentinel or a caller's requested count.
    opts.scan_budget = math.max(1, #found)
    opts.max_candidates = math.max(1, #identities.eligible)
  end
  local env = environment(found, words)
  local report = load_module('mvp0_candidate_report.lua', env)
  local collector = load_module('mvp0_foundlist_collector.lua', env)
  local bundle = collector.build_input(opts)
  -- Same full feature/context/rank/recommendation/report call as the reference.
  -- Exceptions (including allocator failures) propagate; no partial result escapes.
  local result = report.run(bundle.input)
  complete_result(result, bundle, identities.eligible, report, env)
  if mode == 'full' then
    require_value(bundle.raw_count == #found and bundle.scanned_count == #found
      and bundle.unique_count == #identities.eligible and bundle.filtered_count == #identities.eligible
      and #result.ranked == #identities.eligible, 'OFFLINE_INCOMPLETE_RESULT: population coverage')
  end
  return {
    population_mode=mode, completed=true,
    status=(#result.ranked == 0) and 'EMPTY' or 'COMPLETE',
    population_complete=(#result.ranked == #identities.eligible),
    counts={supplied=supplied_count, distinct=#identities.distinct,
      duplicates=supplied_count - #identities.distinct, eligible=#identities.eligible,
      excluded=#identities.distinct - #identities.eligible,
      selected=bundle.selected_count, fully_scored=#result.ranked, ranked=#result.ranked},
    identities=identities, collection=bundle, filter=collector.LAST_FILTER_DEBUG, result=result,
  }
end

return M
