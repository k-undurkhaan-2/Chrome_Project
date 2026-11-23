-- Loading is inert. Only start() reads the local config and initiates a run.
if rawget(_G, 'H3A7_CE_MVP') then return H3A7_CE_MVP end
local source=debug.getinfo(1,'S').source
assert(source:sub(1,1)=='@', 'Load ce_mvp.lua from its saved file')
local dir=assert(source:sub(2):match('^(.*[\\/])'))
local api, instance, startup_error = {}, nil, nil
local execution_mode, factory, run, starting = 'NORMAL', nil, nil, false
local function module(name, env)
  return assert(loadfile(dir .. name, 't', env or _G))()
end
-- Explicit construction dependency, never discovered from the data-only config.
-- Selecting qualification latches even when its factory is invalid.
function api.configure_execution(request)
  if starting or (instance and (instance.status().running or instance.status().cleanup_pending)) then
    return false,'QSG_MODE_LOCKED'
  end
  if execution_mode=='QUALIFICATION' then return false,'QSG_MODE_LOCKED' end
  if type(request)~='table' or request.mode~='QUALIFICATION' then return false,'QSG_MODE_INVALID' end
  execution_mode='QUALIFICATION'
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
  starting=true
  local pending_adapter
  local ok, result, detail=pcall(function()
    assert(_VERSION=='Lua 5.3', 'CE_ENTRYPOINT_REQUIRES_LUA_5_3')
    -- No ambient CE/file/process APIs in the operator's data-only config chunk.
    local config=assert(loadfile(dir .. 'ce_mvp_config.local.lua', 't', {}))()
    local core=module('ce_mvp_core.lua')
    local validated=core.validate(config) -- before adapter construction/attachment
    local adapter
    if execution_mode=='QUALIFICATION' then
      assert(factory,'QSG_PLUGIN_MISSING')
      run=factory.prepare_start(validated)
      adapter=module('ce_mvp_adapter.lua').new(validated,_G,module,run.observation_source,run)
    else
      adapter=module('ce_mvp_adapter.lua').new(validated,_G,module)
    end
    pending_adapter=adapter
    instance=core.new(config,adapter,api.start)
    if run then run.bind_core(instance) end
    return instance.start()
  end)
  starting=false
  if execution_mode=='QUALIFICATION' and (not ok or result~=true) then
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
  for _,k in ipairs({'state','running','pid','identity_token','candidate_address','last_address',
      'last_written','last_written_bits','last_readback','last_readback_bits','scan_count',
      'write_count','monitor_checks','invalid_count','rescan_attempts','retry_at',
      'last_check_ms','last_invalidation','last_error','stop_reason','startup_error',
      'cleanup_pending','cleanup_ok','cleanup_error','log_error','qualification',
      'scan_mode','scope_resolved','scan_start_address','scan_stop_address','bounds_source',
      'scan_policy','candidate_policy','alignment_bytes','scope_complete',
      'raw_match_count','collected_count','evaluated_count','qualified_count',
      'scan_complete','collection_complete','collection_phase','process_candidate_limit',
      'attachment_handle_status','authorization_status'}) do
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
