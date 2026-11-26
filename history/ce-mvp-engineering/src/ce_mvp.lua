-- Loading is inert. Standard ID1 runs the original config with CE native APIs.
-- Engineering, synthetic examples and qualification retain explicit selection.
if rawget(_G, 'H3A7_CE_MVP') then return H3A7_CE_MVP end
local source=debug.getinfo(1,'S').source
assert(source:sub(1,1)=='@', 'Load ce_mvp.lua from its saved file')
local dir=assert(source:sub(2):match('^(.*[\\/])'))
local api, instance, startup_error = {}, nil, nil
local execution_mode, factory, run, starting = 'ALPHA_STANDARD', nil, nil, false
local selection_locked, input_source, selection_error = false, nil, nil
local config_source, config_admission, config_error = 'NONE', 'NOT_CHECKED', nil
local config_state={config_file_status='NOT_READ',config_contract='NOT_CHECKED',
  config_validation='NOT_CHECKED',profile_compatibility='NOT_CHECKED',
  config_application='NOT_APPLIED',runtime_capability='NOT_CHECKED',
  execution_readiness='NOT_CHECKED'}
local config_effects={}
local controlled_fixture
local function alpha()
  return execution_mode=='ALPHA_STANDARD' or execution_mode=='ALPHA_CONTROLLED'
end
local function module(name, env)
  return assert(loadfile(dir .. name, 't', env or _G))()
end
local function reject_config(reason)
  config_admission='REJECTED'; config_error=reason
  config_state.config_validation=(reason=='ALPHA_CONFIG_MISSING' or reason=='ALPHA_CONFIG_UNREADABLE')
    and 'NOT_RUN' or 'INVALID'
  -- Like a rejected explicit selection, correction requires a fresh CE session.
  selection_error=reason=='ALPHA_CONFIG_MISSING'
    and 'ALPHA_INPUT_REQUIRED: ALPHA_CONFIG_MISSING' or reason
  error(selection_error,0)
end
local function block_config(reason, readiness)
  config_state.config_block=reason
  config_state.execution_readiness=readiness
  selection_error=reason; error(reason,0)
end
local function safe_runtime_error(value)
  return type(value)=='string' and (value:match('^[A-Z][A-Z0-9_:,]*$')
    or value:match('^CE_API_MISSING:[%w_]+$') or value:match('^WIN32_API_MISSING:[%w_]+$'))
    and value or 'ALPHA_RUNTIME_FAILURE'
end
local function original_config(c)
  config_state.config_contract='ORIGINAL'
  local selected=c.input_source
  c.input_source=nil -- existing optional Alpha selection, not an original field
  local ok,validated=pcall(module('ce_mvp_core.lua').validate_contract,c)
  if not ok then
    -- The shared validator emits fixed codes. Never publish a Lua/OS exception.
    local code=type(validated)=='string' and validated:match('^[A-Z][A-Z0-9_]+$')
    reject_config(code or 'ALPHA_CONFIG_VALIDATION_FAILED')
  end
  if selected~=nil and type(selected)~='string' then reject_config('ALPHA_CONFIG_FIELD_TYPE') end
  config_state.config_validation='VALID'; config_admission='ACCEPTED'
  config_state.profile_compatibility='COMPATIBLE_WITH_ENGINEERING_ONLY_FIELDS'
  config_state.runtime_capability=selected==nil and 'CE_NATIVE_FULL_POOL'
    or (selected=='OWNED_SYNTHETIC' and 'OWNED_SYNTHETIC_ONLY' or 'UNSUPPORTED_INPUT')
  for _,key in ipairs({'target_pid','screening_profile','value_type','write_value','write_enabled',
      'monitor_interval_ms','scan_timeout_ms','log_limit','log_path','diagnostics',
      'scan.mode','scan.target_value_float','scan.target_value_pattern',
      'scan.filter_target_match','scan.use_prescore_selection',
      'scan.collection_batch_size','scan.collection_slice_ms'}) do
    config_effects[key]='NOT_APPLIED'
  end
  for _,key in ipairs({'invalid_confirmations','min_rescan_spacing_ms','rescan_backoff_ms',
      'max_backoff_ms','max_rescan_attempts'}) do config_effects[key]='ENGINEERING_ONLY_STOP_FIRST' end
  for _,key in ipairs({'scan.scan_budget','scan.max_candidates'}) do
    config_effects[key]='ENGINEERING_ONLY_FULL_POPULATION'
  end
  config_effects.engineering_extensions='DISABLED'
  if validated.scan.mode=='bounded' or validated.diagnostics.cleanup_start_probe then
    config_state.profile_compatibility='CONFLICT'
    local reason=validated.scan.mode=='bounded' and 'ALPHA_PROFILE_BOUNDED_SCOPE'
      or 'ALPHA_PROFILE_QUALIFICATION_PROBE'
    block_config(reason,'BLOCKED_PROFILE')
  end
  if validated.target_pid==0 then block_config('ALPHA_CONFIG_TARGET_REQUIRED','BLOCKED_SAFE_DEFAULT') end
  if not validated.write_enabled then block_config('WRITE_DISABLED','BLOCKED_CONFIGURED_INTENT') end
  if selected==nil then
    input_source='CONFIGURED_TARGET'
    return c -- actual parameters go to the existing adapter, never fixture defaults
  end
  if selected~='OWNED_SYNTHETIC' then block_config('ALPHA_CONFIG_INPUT_UNSUPPORTED','BLOCKED_CAPABILITY') end
  -- The only existing configured consumer is the fixed owned table environment.
  -- Do not rebind that environment to a purported external identity.
  if validated.target_pid~=101 then
    block_config('ALPHA_SYNTHETIC_IDENTITY_MISMATCH','BLOCKED_CAPABILITY')
  end
  input_source=selected
  return c
end
local function standard_config()
  config_source='LOCAL_CONFIG'; config_admission='NOT_CHECKED'; config_error=nil
  config_state={config_file_status='NOT_READ',config_contract='NOT_CHECKED',
    config_validation='NOT_CHECKED',profile_compatibility='NOT_CHECKED',
    config_application='NOT_APPLIED',runtime_capability='NOT_CHECKED',
    execution_readiness='NOT_CHECKED'}
  config_effects={}
  input_source=nil
  -- Read one snapshot from the bound installation. Never expose OS/file errors.
  local opened,file,_,code=pcall(function() return io.open(dir .. 'ce_mvp_config.local.lua','rb') end)
  if not opened or not file then
    config_state.config_file_status=opened and code==2 and 'MISSING' or 'UNREADABLE'
    reject_config(opened and code==2 and 'ALPHA_CONFIG_MISSING' or 'ALPHA_CONFIG_UNREADABLE')
  end
  local read_ok,text=pcall(file.read,file,'*a')
  local close_ok,closed=pcall(file.close,file)
  if not read_ok or type(text)~='string' or not close_ok or not closed then
    config_state.config_file_status='UNREADABLE'
    reject_config('ALPHA_CONFIG_UNREADABLE')
  end
  config_state.config_file_status='READ'
  -- Trusted local Lua convention, NOT an arbitrary-code sandbox or time bound.
  -- The empty environment removes ambient APIs; only the returned data is admitted.
  local chunk=load(text,'@ce_mvp_config.local.lua','t',{})
  if not chunk then reject_config('ALPHA_CONFIG_SYNTAX') end
  local ok,c=pcall(chunk)
  if not ok then reject_config('ALPHA_CONFIG_EVALUATION_FAILED') end
  if type(c)~='table' or getmetatable(c) then reject_config('ALPHA_CONFIG_SHAPE') end
  if c.target_pid~=nil or c.scan~=nil or (c.schema==nil and c.mode==nil and next(c)) then
    return original_config(c)
  end
  config_state.config_contract='SYNTHETIC_SELECTOR_V1'
  for key in pairs(c) do
    if key~='schema' and key~='mode' and key~='input_source' then
      reject_config('ALPHA_CONFIG_UNKNOWN_FIELD')
    end
  end
  for _,key in ipairs({'schema','mode','input_source'}) do
    if c[key]==nil then reject_config('ALPHA_CONFIG_REQUIRED_FIELD') end
    if type(c[key])~='string' then reject_config('ALPHA_CONFIG_FIELD_TYPE') end
  end
  if c.schema~='g1.alpha.config.v1' then reject_config('ALPHA_CONFIG_SCHEMA') end
  if c.mode~='ALPHA_STANDARD' then reject_config('ALPHA_CONFIG_MODE') end
  if c.input_source~='OWNED_SYNTHETIC' then reject_config('ALPHA_CONFIG_INPUT') end
  -- All fields are validated before publishing selection or creating the fixture.
  execution_mode=c.mode; input_source=c.input_source; config_admission='ACCEPTED'
  config_state.config_validation='VALID'
  config_state.profile_compatibility='SYNTHETIC_SELECTION_ONLY'
  config_state.runtime_capability='OWNED_SYNTHETIC_ONLY'
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
    config_source='EXPLICIT_API'
    config_admission=alpha() and 'ACCEPTED' or 'NOT_APPLICABLE'
    for key in pairs(request) do
      if key~='mode' and key~='input_source' then selection_error='EXECUTION_SELECTION_INVALID' end
    end
    if execution_mode=='ALPHA_STANDARD' then
      if request.input_source~='OWNED_SYNTHETIC' then selection_error='ALPHA_INPUT_REQUIRED' end
      input_source=request.input_source
    elseif request.input_source~=nil then selection_error='EXECUTION_SELECTION_INVALID' end
    if selection_error then
      config_admission='REJECTED'; config_error=selection_error
      return false,selection_error
    end
    return true
  end
  if request.mode~='QUALIFICATION' then return false,'QSG_MODE_INVALID' end
  execution_mode='QUALIFICATION'; selection_locked=true
  config_source='EXPLICIT_API'; config_admission='NOT_APPLICABLE'
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
    if selection_error then error(selection_error,0) end
    local config, adapter
    if alpha() then
      config_state.runtime_capability='OWNED_SYNTHETIC_ONLY'
      -- Clear completed data at this admitted fresh-Start boundary, before config
      -- validation. Running/cleanup rejection above must retain its protections.
      instance=nil; controlled_fixture=nil
      if execution_mode=='ALPHA_STANDARD' and config_source~='EXPLICIT_API' then
        config=standard_config()
      end
      assert(execution_mode=='ALPHA_CONTROLLED' or input_source=='OWNED_SYNTHETIC'
          or input_source=='CONFIGURED_TARGET',
        'ALPHA_INPUT_REQUIRED: explicitly select owned supplied input before Start; reload CE to change selection')
      if input_source~='CONFIGURED_TARGET' then
        controlled_fixture,adapter=module('ce_mvp_adapter.lua').new_controlled(module,config)
        config=controlled_fixture.cfg
      end
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
    elseif input_source=='CONFIGURED_TARGET' then
      local admitted,value=pcall(module('ce_mvp_adapter.lua').new_native,validated,_G,module)
      if not admitted then block_config(safe_runtime_error(value),'BLOCKED_RUNTIME') end
      adapter=value
    end
    pending_adapter=adapter
    instance=core.new(config,adapter,api.start,
      input_source=='CONFIGURED_TARGET' and 'NATIVE_MAINTAIN' or (alpha() and 'ALPHA_STOP_ONLY' or nil))
    if alpha() then
      local applied=input_source=='CONFIGURED_TARGET' and 'APPLIED_STANDARD_ADAPTER' or 'APPLIED_OWNED_SYNTHETIC'
      config_state.config_application=config_state.config_contract=='ORIGINAL'
        and applied or 'FIXTURE_DEFAULTS_ONLY'
      config_state.execution_readiness=input_source=='CONFIGURED_TARGET' and 'ADMITTED' or 'OWNED_TEST_ONLY'
      for key,value in pairs(config_effects) do
        if value=='NOT_APPLIED' then config_effects[key]=applied end
      end
      if config_state.config_contract=='ORIGINAL' then
        config_effects.target_pid=input_source=='CONFIGURED_TARGET' and applied or 'MATCHED_FIXED_SYNTHETIC_IDENTITY'
        config_effects.screening_profile='SINGLE_SCORER_FULL_POPULATION'
        config_effects.write_enabled='CONFIGURED_INTENT_ONLY'
        config_effects['scan.mode']=input_source=='CONFIGURED_TARGET' and applied or 'APPLIED_SYNTHETIC_SCOPE_GUARD'
        config_effects['scan.collection_batch_size']='APPLIED_ADAPTER_CHECKPOINTS_ONLY'
        config_effects['scan.collection_slice_ms']='APPLIED_ADAPTER_CHECKPOINTS_ONLY'
        if not config.log_path then config_effects.log_path='NOT_CONFIGURED' end
        if not config.diagnostics or not config.diagnostics.enabled then config_effects.diagnostics='DISABLED' end
      end
    end
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
  if not ok then
    startup_error=config_state.config_contract=='ORIGINAL' and safe_runtime_error(result)
      or tostring(result):sub(1,240)
    print('[H3-A7] ' .. startup_error); return false,startup_error
  end
  startup_error=nil
  if result~=true and config_state.config_contract=='ORIGINAL' then detail=safe_runtime_error(detail) end
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
  s.config_source=config_source; s.config_admission=config_admission
  s.config_error=config_error
  for k,v in pairs(config_state) do s[k]=v end
  s.config_effects={}; for k,v in pairs(config_effects) do s.config_effects[k]=v end
  s.product_profile=input_source=='CONFIGURED_TARGET' and 'CE_NATIVE_FULL'
    or alpha() and 'ALPHA_FULL'
    or (execution_mode=='QUALIFICATION' and 'STRICT_QUALIFICATION' or 'ENGINEERING_BOUNDED')
  -- scan_mode is the legacy address-scope setting, not a scoring-mode claim.
  s.scan_mode_domain='configured_address_scope'
  s.scoring_mode=alpha() and 'full' or 'bounded'
  s.acquisition_mode=alpha() and (input_source=='CONFIGURED_TARGET' and 'configured_target_scan' or 'supplied_records') or 'native_scan'
  if alpha() then
    if not instance and startup_error then s.state='ERROR' end
    s.input_source=execution_mode=='ALPHA_CONTROLLED' and 'OWNED_SYNTHETIC' or input_source
    local native=input_source=='CONFIGURED_TARGET'
    s.data_provenance=native and (instance and 'CE_NATIVE' or 'UNAVAILABLE')
      or (controlled_fixture and 'synthetic' or 'UNAVAILABLE')
    s.lifecycle_policy=native and 'NATIVE_MAINTAIN' or 'ALPHA_STOP_ONLY'; s.automatic_recovery=false
    s.attachment_handle_status='ATTACHMENT_HANDLE_UNVERIFIED'
    s.authorization_status='NOT_PRODUCTION_AUTHORIZED'
    s.action_permitted=native and s.running==true and s.evaluation_completed==true
    s.native_operation_status=native and s.operation_status or 'NOT_RUN'
    s.native_readback_status=native and s.readback_status or 'NOT_RUN'
    s.semantic_validity=input_source=='CONFIGURED_TARGET' and 'NOT_ESTABLISHED' or 'UNVERIFIED_SYNTHETIC_ONLY'
    s.native_qualification=native and 'NATIVE_IMPLEMENTED_PENDING_INDEPENDENT_QUALIFICATION'
      or 'QSG_NATIVE_BACKEND_NOT_QUALIFIED'
    s.external_acquisition_status=native and (s.acquisition_complete and 'SNAPSHOT_COMPLETE'
      or (s.running and 'PENDING' or 'NOT_COMPLETED')) or 'NOT_RUN'
    if not native then s.acquisition_complete=false end
    s.acquisition_evidence=s.acquisition_evidence or 'NOT_ESTABLISHED'
    s.operation_status=s.operation_status or 'NOT_RUN'
    s.readback_status=s.readback_status or 'NOT_RUN'
    s.monitor_status=s.monitor_status or 'NOT_RUN'
    s.coverage_scope=native and 'ce_foundlist_distinct_eligible' or 'supplied_distinct_eligible_only'
    s.evaluation_completed=s.evaluation_completed==true
    s.population_complete=s.population_complete==true
    s.identity_reconciled=s.identity_reconciled==true
    s.evaluation_status=s.evaluation_status or 'NOT_RUN'
    if not s.evaluation_completed and not s.running then
      if s.stop_reason=='OPERATOR_STOP' then s.evaluation_status='CANCELLED'
      elseif startup_error or s.state=='ERROR' then s.evaluation_status='ERROR' end
    end
  end
  if config_state.config_contract=='ORIGINAL' and input_source~='CONFIGURED_TARGET' then
    -- ID2 publishes applicability, never operator values or private log errors.
    for _,key in ipairs({'pid','identity_token','candidate_address','last_address',
        'last_written','last_written_bits','last_readback','last_readback_bits',
        'scan_start_address','scan_stop_address','ranking_best_address','ranking_second_address',
        'raw_admission_budget','ranking_budget','events'}) do
      s[key]=nil
    end
    for _,key in ipairs({'last_error','stop_reason','startup_error','log_error'}) do
      if s[key] then s[key]=safe_runtime_error(s[key]) end
    end
  end
  for _,k in ipairs({'state','running','pid','identity_token','candidate_address','last_address',
      'last_written','last_written_bits','last_readback','last_readback_bits','scan_count',
      'write_count','rewrite_count','maintain_value','last_observed_value','last_observed_bits',
      'monitor_checks','invalid_count','rescan_attempts','retry_at',
      'operation_status','readback_status','monitor_status',
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
      'config_source','config_admission','config_error',
      'config_file_status','config_contract','config_validation','profile_compatibility',
      'config_application','runtime_capability','execution_readiness','config_block',
      'scan_mode_domain','acquisition_mode','external_acquisition_status','scoring_mode','coverage_scope',
      'acquisition_complete','acquisition_evidence',
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
  local effect_keys={}; for key in pairs(config_effects) do effect_keys[#effect_keys+1]=key end
  table.sort(effect_keys)
  for _,key in ipairs(effect_keys) do print('[H3-A7] config_effect.' .. key .. '=' .. config_effects[key]) end
  return s
end
_G.H3A7_CE_MVP=api
return api
