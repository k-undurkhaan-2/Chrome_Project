-- Loading is inert. Standard Alpha requires explicit supplied test input.
-- Only an explicitly selected engineering/qualification Start reads local config.
if rawget(_G, 'H3A7_CE_MVP') then return H3A7_CE_MVP end
local source=debug.getinfo(1,'S').source
assert(source:sub(1,1)=='@', 'Load ce_mvp.lua from its saved file')
local dir=assert(source:sub(2):match('^(.*[\\/])'))
local api, instance, startup_error = {}, nil, nil
local execution_mode, factory, run, starting = 'ALPHA_STANDARD', nil, nil, false
local selection_locked, input_source, selection_error = false, nil, nil
local controlled_fixture
local function alpha()
  return execution_mode=='ALPHA_STANDARD' or execution_mode=='ALPHA_CONTROLLED'
end
local function module(name, env)
  return assert(loadfile(dir .. name, 't', env or _G))()
end
-- Explicit construction dependency, never discovered from the data-only config.
-- Selecting qualification latches even when its factory is invalid.
function api.configure_execution(request)
  if starting or (instance and (instance.status().running or instance.status().cleanup_pending)) then
    return false,'QSG_MODE_LOCKED'
  end
  if type(request)~='table' or getmetatable(request) then return false,'QSG_MODE_INVALID' end
  if selection_locked then
    -- Rechecking the same CT after an explicit Stop preserves its fixed selection.
    if alpha() and not selection_error and request.mode==execution_mode
        and request.factory==nil and request.input_source==input_source then
      for key in pairs(request) do
        if key~='mode' and key~='input_source' then return false,'QSG_MODE_LOCKED' end
      end
      return true
    end
    return false,'QSG_MODE_LOCKED'
  end
  if request.mode=='ALPHA_STANDARD' or request.mode=='ALPHA_CONTROLLED'
      or request.mode=='ENGINEERING_BOUNDED' then
    execution_mode=request.mode; selection_locked=true
    for key in pairs(request) do
      if key~='mode' and key~='input_source' then selection_error='EXECUTION_SELECTION_INVALID' end
    end
    if execution_mode=='ALPHA_STANDARD' then
      if request.input_source~='OWNED_SYNTHETIC' then selection_error='ALPHA_INPUT_REQUIRED' end
      input_source=request.input_source
    elseif request.input_source~=nil then selection_error='EXECUTION_SELECTION_INVALID' end
    if selection_error then return false,selection_error end
    return true
  end
  if request.mode~='QUALIFICATION' then return false,'QSG_MODE_INVALID' end
  execution_mode='QUALIFICATION'; selection_locked=true
  if type(request.factory)~='table' or request.factory.version~='qsg.v1'
      or type(request.factory.prepare_start)~='function' then return false,'QSG_PLUGIN_MISSING' end
  factory=request.factory
  return true
end
function api.start()
  if instance then
    local s=instance.status()
    local function reject(reason)
      instance.note_start_rejection(reason); return false,reason
    end
    if s.running then return reject('ALREADY_RUNNING') end
    if s.cleanup_pending then return reject('CLEANUP_IN_PROGRESS') end
    if not s.cleanup_ok then return reject('CLEANUP_UNCERTAIN_RELOAD_CE') end
  end
  if starting then return false,'QSG_START_IN_PROGRESS' end
  starting=true; selection_locked=true
  local pending_adapter
  local ok, result, detail=pcall(function()
    assert(_VERSION=='Lua 5.3', 'CE_ENTRYPOINT_REQUIRES_LUA_5_3')
    assert(not selection_error, selection_error)
    -- No ambient CE/file/process APIs in the operator's data-only config chunk.
    local config, adapter
    if alpha() then
      -- Fixed owned fixture: no caller-provided CE APIs, factory or private config.
      instance=nil; controlled_fixture=nil
      assert(execution_mode=='ALPHA_CONTROLLED' or input_source=='OWNED_SYNTHETIC',
        'ALPHA_INPUT_REQUIRED: explicitly select owned supplied input before Start; reload CE to change selection')
      controlled_fixture,adapter=module('ce_mvp_adapter.lua').new_controlled(module)
      config=controlled_fixture.cfg
    else
      config=assert(loadfile(dir .. 'ce_mvp_config.local.lua', 't', {}))()
    end
    local core=module('ce_mvp_core.lua')
    local validated=core.validate(config) -- before adapter construction/attachment
    if execution_mode=='QUALIFICATION' then
      assert(factory,'QSG_PLUGIN_MISSING')
      run=factory.prepare_start(validated)
      adapter=module('ce_mvp_adapter.lua').new(validated,_G,module,run.observation_source,run)
    elseif execution_mode=='ENGINEERING_BOUNDED' then
      adapter=module('ce_mvp_adapter.lua').new(validated,_G,module)
    end
    pending_adapter=adapter
    instance=core.new(config,adapter,api.start,
      alpha() and 'ALPHA_STOP_ONLY' or nil)
    if controlled_fixture then controlled_fixture.loop=instance end
    if run then run.bind_core(instance) end
    return instance.start()
  end)
  starting=false
  if execution_mode~='ENGINEERING_BOUNDED' and (not ok or result~=true) then
    if run then pcall(run.revoke,'QSG_START_FAILED') end
    if instance then pcall(instance.stop) end
    if pending_adapter then pcall(pending_adapter.close) end
    if run then pcall(run.finish) end
  end
  if not ok then startup_error=tostring(result):sub(1,240); print('[H3-A7] ' .. startup_error); return false,startup_error end
  startup_error=nil
  return result,detail
end
function api.stop()
  if run then pcall(run.revoke,'OPERATOR_STOP') end -- local cancellation precedes cleanup/IPC
  local result=true
  if instance then result=instance.stop() end
  if run then pcall(run.finish) end
  return result
end
-- Read-only snapshots: no clock/identity/memory calls, and no output side effects.
function api.evidence()
  return instance and instance.evidence() or {enabled=false,reason='NO_RUN'}
end
-- Explicit fixture access reuses its existing step/fault controls. It never
-- exposes or forwards host CE target APIs, and is absent in native modes.
function api.controlled_fixture()
  return alpha() and controlled_fixture or nil
end
function api.evaluation()
  return instance and instance.evaluation() or nil
end
function api.print_evidence()
  local snapshot=api.evidence()
  local function line(row)
    local values={}
    local function flatten(t, prefix)
      for k,v in pairs(t) do
        if k~='events' then
          local key=prefix .. k
          if type(v)=='table' then flatten(v,key .. '.')
          else values[#values+1]=key .. '=' .. (type(v)=='string' and string.format('%q',v) or tostring(v)) end
        end
      end
    end
    flatten(row,''); table.sort(values)
    print('[H3-A7-EVIDENCE] ' .. table.concat(values,' '))
  end
  for _,event in ipairs(snapshot.events or {}) do line(event) end
  snapshot.event_type='snapshot'; line(snapshot)
  return snapshot
end
function api.status()
  local s=instance and instance.status() or {state='STOPPED',running=false,
    qualification='IMPLEMENTED_PENDING_CE_QUALIFICATION'}
  s.startup_error=startup_error
  s.execution_mode=execution_mode
  s.product_profile=alpha() and 'ALPHA_FULL'
    or (execution_mode=='QUALIFICATION' and 'STRICT_QUALIFICATION' or 'ENGINEERING_BOUNDED')
  -- scan_mode is the legacy address-scope setting, not a scoring-mode claim.
  s.scan_mode_domain='configured_address_scope'
  s.scoring_mode=alpha() and 'full' or 'bounded'
  s.acquisition_mode=alpha() and 'supplied_records' or 'native_scan'
  if alpha() then
    if not instance and startup_error then s.state='ERROR' end
    s.input_source=execution_mode=='ALPHA_CONTROLLED' and 'OWNED_SYNTHETIC' or input_source
    s.data_provenance=controlled_fixture and 'synthetic' or 'UNAVAILABLE'
    s.lifecycle_policy='ALPHA_STOP_ONLY'; s.automatic_recovery=false
    s.attachment_handle_status='ATTACHMENT_HANDLE_UNVERIFIED'
    s.authorization_status='NOT_PRODUCTION_AUTHORIZED'
    s.action_permitted=false; s.native_operation_status='NOT_RUN'
    s.native_readback_status='NOT_RUN'; s.semantic_validity='UNVERIFIED_SYNTHETIC_ONLY'
    s.native_qualification='QSG_NATIVE_BACKEND_NOT_QUALIFIED'
    s.external_acquisition_status='NOT_RUN'
    s.coverage_scope='supplied_distinct_eligible_only'
    s.evaluation_completed=s.evaluation_completed==true
    s.population_complete=s.population_complete==true
    s.identity_reconciled=s.identity_reconciled==true
    s.evaluation_status=s.evaluation_status or 'NOT_RUN'
    if not s.evaluation_completed and not s.running then
      if s.stop_reason=='OPERATOR_STOP' then s.evaluation_status='CANCELLED'
      elseif startup_error or s.state=='ERROR' then s.evaluation_status='ERROR' end
    end
  end
  for _,k in ipairs({'state','running','pid','identity_token','candidate_address','last_address',
      'last_written','last_written_bits','last_readback','last_readback_bits','scan_count',
      'write_count','monitor_checks','invalid_count','rescan_attempts','retry_at',
      'last_check_ms','last_invalidation','last_error','stop_reason','startup_error',
      'cleanup_pending','cleanup_ok','cleanup_error','log_error','qualification',
      'cycle_id','scan_mode','scope_resolved','scan_start_address','scan_stop_address','bounds_source',
      'scan_policy','candidate_policy','alignment_bytes','scope_complete',
      'raw_match_count','collected_count','evaluated_count','qualified_count',
      'raw_admitted_count','raw_inspected_count','unique_count','filtered_count','prescored_count',
      'selected_count','ranked_count','raw_admission_budget','ranking_budget','coverage',
      'raw_admission_complete','ranking_complete','global_uniqueness_proven',
      'decision_scope','write_admission_basis',
      'result_ready','scan_complete','collection_complete','collection_phase',
      'attachment_handle_status','authorization_status','execution_mode','lifecycle_policy',
      'automatic_recovery','action_permitted','native_operation_status','native_readback_status',
      'semantic_validity','native_qualification','product_profile','input_source','data_provenance',
      'scan_mode_domain','acquisition_mode','external_acquisition_status','scoring_mode','coverage_scope',
      'evaluation_status','evaluation_completed','population_mode','population_complete','identity_reconciled',
      'evaluation_supplied','evaluation_distinct','evaluation_duplicates','evaluation_eligible',
      'evaluation_excluded','evaluation_selected','evaluation_fully_scored','evaluation_ranked',
      'ranking_best_address','ranking_best_score','ranking_second_address','ranking_second_score',
      'ranking_score_gap','ranking_confidence','ranking_recommendation','ranking_manual_review_required'}) do
    local value=s[k]
    if type(value)=='number' and (k:find('address',1,true) or k:find('_bits',1,true)) then
      value=string.format('0x%X',value)
    end
    print('[H3-A7] ' .. k .. '=' .. tostring(value))
  end
  return s
end
_G.H3A7_CE_MVP=api
return api
