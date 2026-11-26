-- Inert CE-hosted entry for explicitly supplied synthetic tables. No native API.
-- The ordinary AC6/AC5 completion envelope is returned without modification.
local source = debug.getinfo(1, 'S').source
assert(source:sub(1, 1) == '@', 'Load ce_mvp_readonly.lua from its saved file')
local dir = assert(source:sub(2):match('^(.*[\\/])'))
local api = {}
local modules = {
  ['mvp0_foundlist_collector.lua']=true,
  ['mvp0_offline_scoring.lua']=true,
  ['mvp0_candidate_report.lua']=true,
}

local function load_module(name, env)
  assert(modules[name], 'G1_READONLY_UNKNOWN_MODULE')
  return assert(loadfile(dir .. name, 't', env))()
end

local function runtime()
  assert(_VERSION == 'Lua 5.3', 'CE_ENTRYPOINT_REQUIRES_LUA_5_3')
end

function api.evaluate(records, options)
  runtime()
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
  -- Always the explicit table overload. AC6 validates completion and AC5 checks
  -- exact membership, full features, common cohort, ordering and ordinary result.
  local completed = collector.run(options, {records=records, load_module=load_module})
  return {
    scope='OWNED_SYNTHETIC_TABLES_READ_ONLY', state='COMPLETED_READ_ONLY',
    action_permitted=false, action_status='UNSUPPORTED_NO_COOPERATIVE_OPERATION_INTERFACE',
    lifecycle_status='UNSUPPORTED_NO_APPLICATION_LIFECYCLE_INTERFACE',
    semantic_validity='UNVERIFIED_SYNTHETIC_SNAPSHOT_ONLY', automatic_recovery=false,
    proposed_rank1=completed.status == 'COMPLETE' and completed.result.best.candidate.value_addr or nil,
    evaluation=completed,
  }
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
  field('recommendation', evaluation.result.recommendation.recommendation)
  field('manual_review_required', evaluation.result.recommendation.manual_review_required)
  lines[#lines + 1] = evaluation.result.report_text
  lines[#lines + 1] = '[G1-READONLY] invocation=COMPLETE; recommendation grants no action authority'
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
