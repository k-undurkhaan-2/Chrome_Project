-- Inert CE-hosted entry for explicitly supplied owned synthetic test tables.
-- No target APIs. The host tick clock measures evaluation only.
local source = debug.getinfo(1, 'S').source
assert(source:sub(1, 1) == '@', 'Load ce_mvp_readonly.lua from its saved file')
local dir = assert(source:sub(2):match('^(.*[\\/])'))
local api = {}
local modules = {
  ['mvp0_foundlist_collector.lua']=true,
  ['mvp0_offline_scoring.lua']=true,
  ['mvp0_candidate_report.lua']=true,
  ['mvp0_frozen_choice.lua']=true,
}

local fields = {'f08', 'f18', 'f20', 'f58', 'f68', 'f70', 'f78'}
local components = {
  'base_score', 'pointer_reward', 'strong_structure_bonus',
  'sparse_anchor_tail_penalty', 'anchored_fragmented_split_penalty',
  'one_sided_anchorless_split_penalty', 'anchorless_partial_split_penalty',
  'isolated_split_penalty', 'code_blob_penalty', 'scalar_block_penalty',
  'text_block_penalty', 'clone_penalty', 'mirrored_penalty',
}

local function load_module(name, env)
  assert(modules[name], 'G1_READONLY_UNKNOWN_MODULE')
  return assert(loadfile(dir .. name, 't', env))()
end

local function runtime()
  assert(_VERSION == 'Lua 5.3', 'CE_ENTRYPOINT_REQUIRES_LUA_5_3')
end

local function rank_frozen(baseline, model)
  local result = {model='conditional_choice_linear_ridge_0.1', status='EMPTY', ranked={}, leaders={}}
  if #baseline.ranked == 0 then return result end
  local scores, rows = {}, {}
  for i, scored in ipairs(baseline.ranked) do
    local words, values = {}, {}
    for j, key in ipairs(fields) do
      local word = scored.candidate[key]
      -- The existing table contract permits integral numeric words. Normalize
      -- their Lua subtype without changing any value or imputing missingness.
      if word ~= nil then words[j] = assert(math.tointeger(word), 'INVALID_BASELINE_WORD') end
    end
    for j, key in ipairs(components) do values[j] = scored[key] end
    scores[i], rows[i] = scored.final_score, model.features(words, values)
  end
  local predicted = model.predict(scores, rows)
  for i, scored in ipairs(baseline.ranked) do
    result.ranked[i] = {candidate=scored.candidate, baseline_rank=i,
      baseline_final_score=scored.final_score, final_score=predicted[i]}
  end
  table.sort(result.ranked, function(a, b)
    if a.final_score ~= b.final_score then return a.final_score > b.final_score end
    return a.baseline_rank < b.baseline_rank -- presentation only, never uniqueness
  end)
  local sorted_scores = {}
  for i, row in ipairs(result.ranked) do
    row.rank_position, sorted_scores[i] = i, row.final_score
  end
  for _, i in ipairs(model.leaders(sorted_scores)) do
    result.leaders[#result.leaders + 1] = result.ranked[i]
  end
  result.status = #result.leaders == 1 and 'UNIQUE' or 'AMBIGUOUS'
  result.best = #result.leaders == 1 and result.leaders[1] or nil
  result.score_gap = #sorted_scores > 1 and sorted_scores[1] - sorted_scores[2] or nil
  return result
end

function api.evaluate(records, options)
  runtime()
  local clock = getTickCount
  assert(type(clock) == 'function', 'G1_READONLY_HOST_CLOCK_REQUIRED')
  local started = clock()
  local function elapsed(since) return (clock() - since) % 4294967296 end
  assert(type(options) == 'table' and getmetatable(options) == nil
    and options.population_mode == 'full', 'G1_READONLY_EXPLICIT_FULL_REQUIRED')
  -- The outer collector also has no ambient CE/file/process/action capabilities.
  local env = {
    assert=assert, error=error, ipairs=ipairs, pairs=pairs, next=next, pcall=pcall,
    select=select, tonumber=tonumber, tostring=tostring, type=type, getmetatable=getmetatable,
    math=math, string=string, table=table, debug={getinfo=debug.getinfo}, os={clock=os.clock},
  }
  env._G = env
  local collector = load_module('mvp0_foundlist_collector.lua', env)
  local model = load_module('mvp0_frozen_choice.lua', env)
  local compute_started = clock()
  -- Always the explicit table overload. AC6 validates completion and AC5 checks
  -- exact membership, full features, common cohort, ordering and ordinary result.
  local completed = collector.run(options, {records=records, load_module=load_module})
  -- Preserve the validated baseline in full. Only this test entry's final
  -- result/proposal uses the frozen model; ordinary AC5/AC6 callers are unchanged.
  completed.baseline_result = completed.result
  completed.result = rank_frozen(completed.baseline_result, model)
  local compute_ms = elapsed(compute_started)
  local outcome = {
    scope='OWNED_SYNTHETIC_TABLES_READ_ONLY', state='COMPLETED_READ_ONLY',
    action_permitted=false, action_status='UNSUPPORTED_NO_COOPERATIVE_OPERATION_INTERFACE',
    lifecycle_status='UNSUPPORTED_NO_APPLICATION_LIFECYCLE_INTERFACE',
    semantic_validity='UNVERIFIED_SYNTHETIC_SNAPSHOT_ONLY', automatic_recovery=false,
    proposed_rank1=completed.result.best and completed.result.best.candidate.value_addr or nil,
    evaluation=completed,
    timing={clock='getTickCount', algorithm_compute_ms=compute_ms},
  }
  outcome.timing.total_evaluation_ms = elapsed(started)
  return outcome
end

local function render(outcome)
  local evaluation, lines = outcome.evaluation, {}
  local function field(key, value)
    lines[#lines + 1] = '[G1-READONLY] ' .. key .. '=' .. tostring(value)
  end
  local function identities(key, values)
    local words = {}
    for _, value in ipairs(values) do words[#words + 1] = string.format('0x%X', value) end
    field(key, table.concat(words, ','))
  end
  for _, key in ipairs({'scope', 'state', 'action_permitted', 'action_status',
    'lifecycle_status', 'semantic_validity', 'automatic_recovery', 'proposed_rank1'}) do
    field(key, outcome[key])
  end
  for _, key in ipairs({'status', 'completed', 'population_mode', 'population_complete'}) do
    field(key, evaluation[key])
  end
  for _, key in ipairs({'supplied', 'distinct', 'duplicates', 'eligible', 'excluded',
    'selected', 'fully_scored', 'ranked'}) do field('counts.' .. key, evaluation.counts[key]) end
  for _, key in ipairs({'supplied', 'distinct', 'eligible'}) do
    identities('identities.' .. key, evaluation.identities[key])
  end
  identities('identities.selected', evaluation.collection.candidate_value_addrs)
  local ranked = {}
  for _, row in ipairs(evaluation.result.ranked) do ranked[#ranked + 1] = row.candidate.value_addr end
  identities('identities.ranked', ranked)
  field('model', evaluation.result.model)
  field('prediction_status', evaluation.result.status)
  field('score_gap', evaluation.result.score_gap)
  local leaders = {}
  for _, row in ipairs(evaluation.result.leaders) do leaders[#leaders + 1] = row.candidate.value_addr end
  identities('identities.leaders', leaders)
  for _, row in ipairs(evaluation.result.ranked) do
    field('rank.' .. row.rank_position, string.format('0x%X; choice_score=%.17g; baseline_score=%.17g',
      row.candidate.value_addr, row.final_score, row.baseline_final_score))
  end
  for _, key in ipairs({'clock', 'algorithm_compute_ms', 'total_evaluation_ms'}) do
    field('timing.' .. key, outcome.timing[key])
  end
  lines[#lines + 1] = '[G1-READONLY] invocation=COMPLETE; prediction grants no action authority'
  return table.concat(lines, '\n')
end

function api.run_example()
  -- No cached result or scheduler. BEGIN makes any previous console output a
  -- different invocation; no success output is rendered until AC6 has returned.
  print('[G1-READONLY] invocation=BEGIN; previous output is not this invocation result')
  runtime()
  local input = assert(loadfile(dir .. 'examples/g1_alpha_population.example.lua', 't', {}))()
  assert(type(input) == 'table' and getmetatable(input) == nil, 'G1_READONLY_INVALID_EXAMPLE')
  for key in pairs(input) do
    assert(key == 'records' or key == 'options', 'G1_READONLY_INVALID_EXAMPLE')
  end
  -- Propagate errors (including allocator failure) unchanged. No catch/fallback,
  -- replacement recommendation, success marker or persisted result on failure.
  local outcome = api.evaluate(input.records, input.options)
  print(render(outcome))
  return outcome
end

return api
