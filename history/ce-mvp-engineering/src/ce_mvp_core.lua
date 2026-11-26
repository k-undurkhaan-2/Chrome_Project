-- H3-A7: deterministic closed loop. No CE globals, I/O, timers or process access.
local M = {}
local function fail(code) error(code, 0) end
local function finite(v)
  return type(v) == 'number' and v == v and math.abs(v) ~= math.huge
end
local function integer(v, lo, hi)
  return finite(v) and v % 1 == 0 and v >= lo and v <= hi
end
function M.float32(v)
  if not finite(v) then fail('INVALID_FLOAT32') end
  local bytes = string.pack('<f', v)
  local rounded = string.unpack('<f', bytes)
  if not finite(rounded) then fail('FLOAT32_OVERFLOW') end
  return rounded, (string.unpack('<I4', bytes))
end
local function fields(t, allowed, name)
  if type(t) ~= 'table' or getmetatable(t) then fail('INVALID_' .. name) end
  for key in pairs(t) do
    if not allowed[key] then fail('UNKNOWN_' .. name .. '_FIELD') end
  end
end
local function keys(text)
  local out = {}; for key in text:gmatch('%S+') do out[key] = true end; return out
end
local ROOT = keys([[target_pid screening_profile value_type write_value write_enabled
  monitor_interval_ms invalid_confirmations rescan_backoff_ms max_backoff_ms
  min_rescan_spacing_ms max_rescan_attempts scan_timeout_ms scan engineering_extensions
  log_limit log_path diagnostics]])
local SCAN = keys([[mode start_address stop_address target_value_float target_value_pattern
  scan_budget max_candidates filter_target_match use_prescore_selection
  collection_batch_size collection_slice_ms
  process_candidate_limit process_chunk_candidates process_slice_ms]])
local EXT = keys('h3_a3_store h3_a4_approval strict_attachment')
local DIAG = keys('enabled session_token event_limit cleanup_start_probe')
local function address(v)
  if type(v) == 'string' and v:match('^0x%x+$') then v = tonumber(v) end
  if not integer(v, 0x10000, 0x7FFFFFFFFFFF) then fail('INVALID_SCAN_ADDRESS') end
  return math.tointeger(v)
end
local function validate(input, contract_only)
  fields(input, ROOT, 'CONFIG')
  local c = {}
  for k, v in pairs(input) do c[k] = v end
  if not integer(c.target_pid, contract_only and 0 or 1, 0xFFFFFFFF) then fail('INVALID_TARGET_PID') end
  c.target_pid = math.tointeger(c.target_pid)
  if c.screening_profile ~= 'single' then fail('UNSUPPORTED_PROFILE') end
  if c.value_type ~= 'float32' then fail('UNSUPPORTED_VALUE_TYPE') end
  if contract_only then
    if type(c.write_enabled)~='boolean' then fail('INVALID_WRITE_ENABLED') end
  elseif c.write_enabled ~= true then fail('WRITE_DISABLED') end
  c.write_value, c.write_bits = M.float32(c.write_value)
  for k, bounds in pairs({monitor_interval_ms={100,60000}, invalid_confirmations={1,20},
      rescan_backoff_ms={100,600000}, max_backoff_ms={100,600000},
      min_rescan_spacing_ms={100,600000}, max_rescan_attempts={0,50},
      scan_timeout_ms={1000,600000}, log_limit={16,2000}}) do
    if not integer(c[k], bounds[1], bounds[2]) then fail('INVALID_' .. k:upper()) end
  end
  if c.max_backoff_ms < c.rescan_backoff_ms then fail('INCONSISTENT_BACKOFF') end
  if c.log_path ~= nil and (type(c.log_path) ~= 'string' or #c.log_path > 512
      or not c.log_path:match('^[A-Za-z]:[\\/].+%.log$') or c.log_path:find('[%c]')) then
    fail('INVALID_LOG_PATH')
  end
  fields(c.engineering_extensions, EXT, 'EXTENSION')
  c.engineering_extensions = {}
  for k, v in pairs(input.engineering_extensions) do
    if v ~= false then fail('UNSUPPORTED_ENGINEERING_EXTENSION') end
    c.engineering_extensions[k] = false
  end
  fields(input.scan, SCAN, 'SCAN')
  c.scan = {}; for k, v in pairs(input.scan) do c.scan[k] = v end
  local s = c.scan
  local has_start, has_stop = s.start_address~=nil, s.stop_address~=nil
  if has_start~=has_stop then fail('INCOMPLETE_SCAN_RANGE') end
  -- Legacy paired bounds always retain their bounded meaning.
  if s.mode==nil then s.mode=has_start and 'bounded' or 'process' end
  if s.mode~='bounded' and s.mode~='process' then fail('INVALID_SCAN_MODE') end
  if s.mode=='process' then
    if has_start then fail('CONFLICTING_SCAN_RANGE') end
  else
    if not has_start then fail('INCOMPLETE_SCAN_RANGE') end
    s.start_address, s.stop_address = address(s.start_address), address(s.stop_address)
    if s.stop_address - s.start_address < 128 then fail('INVALID_SCAN_RANGE') end
  end
  s.target_value_float, s.target_bits = M.float32(s.target_value_float)
  if not integer(s.target_value_pattern, 0, 0xFFFFFFFF)
      or s.target_value_pattern ~= s.target_bits then fail('SCAN_PATTERN_MISMATCH') end
  -- Legacy intake and ranked selection are independent of native FoundList.Count.
  -- Keep the collector's defaults; the adapter distinguishes scoped ACCEPT from QSG proof.
  if s.scan_budget==nil then s.scan_budget=2000 end
  if s.max_candidates==nil then s.max_candidates=20 end
  if not integer(s.scan_budget, 1, 65536) or not integer(s.max_candidates, 1, 128)
      or s.max_candidates>s.scan_budget
      or s.filter_target_match ~= true or s.use_prescore_selection ~= true then
    fail('INVALID_SCAN_SETTINGS')
  end
  if s.process_candidate_limit~=nil or s.process_chunk_candidates~=nil or s.process_slice_ms~=nil then
    fail('OBSOLETE_PROCESS_BUDGET_USE_LEGACY_INTAKE_SETTINGS')
  end
  for k,rule in pairs({collection_batch_size={256,16,2048},collection_slice_ms={10,1,25}}) do
    if s[k]==nil then s[k]=rule[1] end
    if not integer(s[k],rule[2],rule[3]) then fail('INVALID_COLLECTION_BUDGET') end
  end
  c.diagnostics = {enabled=false}
  if input.diagnostics ~= nil then
    fields(input.diagnostics, DIAG, 'DIAGNOSTICS')
    local d = input.diagnostics
    if type(d.enabled) ~= 'boolean' or (d.cleanup_start_probe ~= nil
        and type(d.cleanup_start_probe) ~= 'boolean') then fail('INVALID_DIAGNOSTICS') end
    if d.enabled and (type(d.session_token) ~= 'string' or #d.session_token<1
        or #d.session_token>64 or not d.session_token:match('^[%w_-]+$')
        or not integer(d.event_limit, 32, 2048)) then fail('INVALID_DIAGNOSTICS') end
    if d.cleanup_start_probe and not d.enabled then fail('INVALID_DIAGNOSTICS') end
    for k,v in pairs(d) do c.diagnostics[k]=v end
  end
  return c
end

-- Recognition of a safe template is separate from admission to an executing core.
-- The original execution validator and its error ordering remain unchanged.
function M.validate_contract(input) return validate(input, true) end
function M.validate(input) return validate(input, false) end

function M.new(config, adapter, public_start_probe, lifecycle_policy)
  lifecycle_policy = lifecycle_policy or 'ENGINEERING_RECOVERY'
  if lifecycle_policy ~= 'ENGINEERING_RECOVERY' and lifecycle_policy ~= 'ALPHA_STOP_ONLY'
      and lifecycle_policy ~= 'NATIVE_MAINTAIN' then
    fail('INVALID_LIFECYCLE_POLICY')
  end
  local maintain = lifecycle_policy == 'NATIVE_MAINTAIN'
  local stop_only = lifecycle_policy ~= 'ENGINEERING_RECOVERY'
  local c = M.validate(config)
  local a = adapter
  local s = {state='STOPPED', running=false, pid=c.target_pid, scan_count=0,
    write_count=0, monitor_checks=0, invalid_count=0, rescan_attempts=0,
    operation_status='NOT_RUN', readback_status='NOT_RUN', monitor_status='NOT_RUN',
    qualification='IMPLEMENTED_PENDING_CE_QUALIFICATION',
    attachment_handle_status='ATTACHMENT_HANDLE_UNVERIFIED',
    authorization_status='NOT_PRODUCTION_AUTHORIZED',
    lifecycle_policy=lifecycle_policy, automatic_recovery=not stop_only,
    maintain_value=maintain, rewrite_count=0}
  local busy, timer, scan, selected, epoch = false, nil, nil, nil, 0
  local rewrite_pending=false
  local retired, events, last_time, next_check, scan_started, retry_at = {}, {}, nil, nil, nil, nil
  local cleanup_failed = false
  local api = {}
  -- Opt-in observation of existing operations only. No clocks, native calls,
  -- output sinks or user callbacks in the recorder; errors invalidate evidence,
  -- not the existing control flow. Returned tables cannot mutate a running run.
  local diagnostic_events, counters, labels, identity_evidence = {}, {}, {}, {}
  for name in ([[adapter_read_calls adapter_readback_calls adapter_write_attempts
      adapter_write_successes verified_writes adapter_scan_invocations scan_completions
      scan_cancel_requests scan_disposals identity_checks mapping_queries
      valid_monitor_checks invalid_monitor_checks retirements cleanup_attempts rejected_starts]]):gmatch('%S+') do
    counters[name]=0
  end
  local sequence, dropped, label_count, first_time, telemetry_error = 0, 0, 0, nil, nil
  local function copy(t)
    local out={}; for k,v in pairs(t) do out[k]=type(v)=='table' and copy(v) or v end
    return out
  end
  local function count_snapshot()
    local out=copy(counters)
    for _,k in ipairs({'scan_count','write_count','monitor_checks','invalid_count','rescan_attempts'}) do
      out[k]=s[k]
    end
    return out
  end
  local function record(kind, data, counter)
    if not c.diagnostics.enabled then return end
    if counter then counters[counter]=(counters[counter] or 0)+1 end
    if kind=='identity_begin' then identity_evidence={check_complete=false}; return end
    if kind=='identity_sample' then
      identity_evidence[data.role .. '_token']=data.token
      identity_evidence.evidence_source='GetProcessId/GetProcessTimes/WaitForSingleObject'
      return
    end
    if kind=='identity_ok' then identity_evidence.check_complete=true; return end
    if not kind then return end
    sequence=sequence+1
    local e={schema=1, session_token=c.diagnostics.session_token,
      source=a.observation_source or 'synthetic', sequence=sequence, event_type=kind,
      state_before=s.state, state_after=s.state, configured_pid=c.target_pid,
      relative_ms=first_time and last_time-first_time or nil,
      time_source='last control tick; no event-time or UTC precision claim',
      counters=count_snapshot(), identity=copy(identity_evidence)}
    for k,v in pairs(data or {}) do
      if k=='address' then
        if not labels[v] then labels[v]='A' .. label_count; label_count=label_count+1 end
        e.address_label=labels[v]
      else e[k]=v end
    end
    diagnostic_events[#diagnostic_events+1]=e
    if #diagnostic_events>c.diagnostics.event_limit then
      table.remove(diagnostic_events,1); dropped=dropped+1
    end
  end
  local function observe(...)
    if not c.diagnostics.enabled then return end
    if not pcall(record, ...) then telemetry_error='OBSERVATION_FAILED' end
  end
  if a.set_observer then a.set_observer(observe) end
  function api.evidence()
    if not c.diagnostics.enabled then return {enabled=false} end
    return {enabled=true, schema=1, session_token=c.diagnostics.session_token,
      scan_scope=a.scan_scope and a.scan_scope() or nil,
      source=a.observation_source or 'synthetic', configured_pid=c.target_pid,
      state=s.state, running=s.running, cleanup_pending=s.cleanup_pending or false,
      cleanup_ok=not cleanup_failed and not s.cleanup_pending, stop_reason=s.stop_reason,
      relative_ms=first_time and last_time-first_time or nil, counters=count_snapshot(),
      identity=copy(identity_evidence), events=copy(diagnostic_events),
      dropped_events=dropped, last_sequence=sequence, telemetry_error=telemetry_error,
      attachment_handle_status=s.attachment_handle_status, authorization_status=s.authorization_status}
  end
  local function emit(message)
    local line = '[H3-A7] ' .. message
    events[#events+1] = line
    if #events > c.log_limit then table.remove(events, 1) end
    -- Output failure must not undo a safe stop or permit another write.
    local ok = pcall(a.log, line)
    if not ok then
      s.log_error = 'LOG_OUTPUT_FAILED'
      if s.running then fail('LOG_OUTPUT_FAILED') end
    end
  end
  local function transition(state)
    local before=s.state
    s.state = state
    observe('state_transition', {state_before=before,state_after=state})
    emit('state=' .. state .. ' pid=' .. s.pid .. ' scans=' .. s.scan_count .. ' writes=' .. s.write_count)
  end
  local function dispose_scan()
    if scan then
      local old = scan; scan = nil
      a.dispose_scan(old)
    end
  end
  local function finish(reason, is_error)
    s.running = false; epoch = epoch + 1
    s.cleanup_pending = true
    s.stop_reason = reason
    if is_error then s.last_error = reason end
    observe('cleanup_begin', {reason=reason}, 'cleanup_attempts')
    -- L10 only: one deliberately rejected Start at the real cleanup boundary.
    -- The loader supplies its own Start, never operator-supplied executable code.
    if c.diagnostics.enabled and c.diagnostics.cleanup_start_probe then
      c.diagnostics.cleanup_start_probe=false
      local ok, accepted, rejection=pcall(public_start_probe or api.start)
      observe('cleanup_start_probe', {call_ok=ok,accepted=accepted==true,
        reason=ok and rejection or 'PROBE_CALL_FAILED'})
    end
    local cleanup = {}
    if timer then
      local old = timer; timer = nil
      if not pcall(a.cancel_timer, old) then cleanup[#cleanup+1] = 'timer' end
    end
    if not pcall(dispose_scan) then cleanup[#cleanup+1] = 'scan' end
    if not pcall(a.close) then cleanup[#cleanup+1] = 'identity' end
    if #cleanup > 0 then
      cleanup_failed = true; s.cleanup_error = table.concat(cleanup, ',')
      is_error = true
    end
    selected = nil; s.candidate_address = nil
    s.cleanup_pending = false
    observe('cleanup_complete', {cleanup_ok=not cleanup_failed,reason=reason,
      cleanup_error=s.cleanup_error})
    transition(is_error and 'ERROR' or 'STOPPED')
    emit('stop_reason=' .. reason .. (s.cleanup_error and ' cleanup_error=' .. s.cleanup_error or ''))
  end
  local function clock()
    local t = a.now()
    if not integer(t, 0, math.maxinteger) or (last_time and t < last_time) then fail('CLOCK_UNCERTAIN') end
    last_time = t; first_time=first_time or t; return t
  end
  local function guard()
    if not s.running then fail('CANCELLED') end
    a.check_identity(s.identity_token)
    if not s.running then fail('CANCELLED') end
  end
  -- Also used at each memory primitive in the CE adapter, including collector reads.
  a.set_guard(guard)
  local function backoff(reason, now)
    guard(); dispose_scan()
    if stop_only then fail((maintain and 'NATIVE_STOP:' or 'ALPHA_STOP:') .. reason) end
    if s.rescan_attempts >= c.max_rescan_attempts then fail('RESCAN_LIMIT_EXHAUSTED') end
    s.rescan_attempts = s.rescan_attempts + 1
    local delay = math.min(c.max_backoff_ms, c.rescan_backoff_ms * 2^(s.rescan_attempts-1))
    retry_at = math.max(now + delay, (scan_started or now) + c.min_rescan_spacing_ms)
    s.retry_at = retry_at; s.last_invalidation = reason
    observe('backoff', {reason=reason,delay_ms=retry_at-now})
    transition('RESCAN_BACKOFF')
  end
  local function do_tick()
    local now = clock(); s.last_check_ms = now
    if s.state == 'ATTACHING' then
      s.identity_token = a.attach(c.target_pid)
      if type(s.identity_token) ~= 'string' or s.identity_token == '' then fail('IDENTITY_UNCERTAIN') end
      guard(); emit('identity=' .. s.identity_token)
      observe('identity_bound', {identity_token=s.identity_token})
      transition('SCREENING')
      return
    end
    guard()
    if s.state == 'RESCAN_BACKOFF' then
      if now >= retry_at then transition('SCREENING') end
    elseif s.state == 'SCREENING' then
      if not scan then
        s.scan_count = s.scan_count + 1; scan_started = now
        scan = a.begin_scan()
        if not scan then fail('SCAN_START_FAILED') end
      elseif now - scan_started >= c.scan_timeout_ms then
        fail('SCAN_TIMEOUT')
      else
        local ready, result = a.poll_scan(scan)
        guard()
        if ready then
          selected = result; dispose_scan()
          if not selected then backoff('NO_CANDIDATE', now)
          else
            s.candidate_address = selected.address
            s.last_address = selected.address
            transition('CANDIDATE_CHECK')
          end
        end
      end
    elseif s.state == 'CANDIDATE_CHECK' then
      if not selected or retired[selected.address] then fail('RETIRED_CANDIDATE') end
      if a.valid(selected) ~= true or a.read_bits(selected.address) ~= c.scan.target_bits then
        fail('CANDIDATE_CHANGED')
      end
      guard(); transition('WRITING')
    elseif s.state == 'WRITING' then
      -- Recheck after the UI tick boundary. Readback is immediate in this tick.
      local valid, reason=a.valid(selected)
      if valid~=true then fail(maintain and (reason or 'ADDRESS_INVALID') or 'PREWRITE_CANDIDATE_CHANGED') end
      local before=a.read_bits(selected.address)
      if rewrite_pending then
        if not integer(before,0,0xFFFFFFFF) then fail('ADDRESS_UNREADABLE') end
        local current=string.unpack('<f',string.pack('<I4',before))
        if not finite(current) then fail('NONFINITE_VALUE') end
        -- A value that recovered between monitor and write must not be lowered.
        if current>=c.write_value then
          rewrite_pending=false; next_check=now+c.monitor_interval_ms
          s.monitor_status='VALID'; transition('MONITORING'); return
        end
      elseif before ~= c.scan.target_bits then
        fail('PREWRITE_CANDIDATE_CHANGED')
      end
      guard()
      s.write_count = s.write_count + 1
      if rewrite_pending then s.rewrite_count=s.rewrite_count+1 end
      s.last_address = selected.address; s.last_written = c.write_value; s.last_written_bits = c.write_bits
      -- Cache each boundary separately. A thrown operation or readback leaves
      -- an unconfirmed attempt, never a successful verification claim.
      s.operation_status='ATTEMPTED_UNCONFIRMED'
      if a.write_float(selected.address, c.write_value) ~= true then
        s.operation_status='FAILED'; fail('WRITE_FAILED')
      end
      s.operation_status='API_SUCCEEDED'
      guard(); transition('READBACK')
      s.readback_status='ATTEMPTED_UNCONFIRMED'
      local bits, value = a.readback(selected.address)
      s.last_readback_bits, s.last_readback = bits, value
      observe('readback_result', {address=selected.address,write_intent_bits=c.write_bits,
        readback_bits=bits,readback_float=value})
      if bits == nil or not finite(value) then
        s.readback_status='FAILED'; fail('READBACK_MISMATCH')
      end
      if bits ~= c.write_bits then s.readback_status='MISMATCH'; fail('READBACK_MISMATCH') end
      local _, value_bits = M.float32(value)
      if value_bits ~= c.write_bits then s.readback_status='MISMATCH'; fail('READBACK_MISMATCH') end
      s.readback_status='VERIFIED'
      rewrite_pending=false
      if maintain then
        s.monitor_status='VALID'; s.last_observed_value=value; s.last_observed_bits=bits
      end
      observe('readback_verified', {address=selected.address,write_intent_bits=c.write_bits,
        readback_bits=bits,float_bits=value_bits}, 'verified_writes')
      guard(); s.invalid_count = 0; next_check = now + c.monitor_interval_ms
      emit(string.format('address=0x%X written=%.9g readback=%.9g bits=0x%08X',
        selected.address, c.write_value, value, bits))
      transition('MONITORING')
    elseif s.state == 'MONITORING' and now >= next_check then
      next_check = now + c.monitor_interval_ms
      s.monitor_checks = s.monitor_checks + 1
      s.monitor_status='CHECK_UNCONFIRMED'
      local valid, reason = a.valid(selected)
      guard()
      s.monitor_status=valid==true and 'VALID' or 'INVALID'
      observe('monitor_result', {address=selected.address,valid=valid==true,reason=reason},
        valid and 'valid_monitor_checks' or 'invalid_monitor_checks')
      if valid then
        s.invalid_count = 0
        if maintain then
          local bits,value=a.readback(selected.address)
          guard()
          if not integer(bits,0,0xFFFFFFFF) or not finite(value) then fail('ADDRESS_UNREADABLE') end
          local _,value_bits=M.float32(value)
          if value_bits~=bits then fail('MONITOR_READ_INCONSISTENT') end
          s.last_observed_value=value; s.last_observed_bits=bits
          if value<c.write_value then
            rewrite_pending=true; s.monitor_status='VALUE_BELOW_TARGET'
            transition('WRITING')
          end
        end
      else
        s.invalid_count = s.invalid_count + 1
        s.last_invalidation = reason or 'ADDRESS_INVALID'
        if stop_only or s.invalid_count >= c.invalid_confirmations then
          retired[selected.address] = true; s.last_address = selected.address
          observe('address_retired', {address=selected.address,reason=s.last_invalidation}, 'retirements')
          selected = nil; s.candidate_address = nil
          backoff(s.last_invalidation, now)
        end
      end
    end
  end
  function api.tick()
    if not s.running then return end
    if busy then finish('REENTRANT_TIMER', true); return end
    busy = true
    local ok, err = pcall(do_tick)
    busy = false
    if not ok and s.running then finish(tostring(err):sub(1, 240), true) end
  end
  function api.start()
    local function reject(reason)
      api.note_start_rejection(reason); return false,reason
    end
    if s.cleanup_pending then return reject('CLEANUP_IN_PROGRESS') end
    if s.running or busy then return reject('ALREADY_RUNNING') end
    if cleanup_failed then return reject('CLEANUP_UNCERTAIN_RELOAD_CE') end
    -- A core is one run; the public loader constructs a fresh core on restart.
    if epoch ~= 0 then return reject('RUN_ALREADY_FINISHED') end
    s.running = true
    local ok, result = pcall(function()
      transition('ATTACHING')
      if not s.running then return nil end
      return a.create_timer(50, api.tick)
    end)
    if not ok or not result then
      if s.running then finish(not ok and tostring(result):sub(1,240) or 'TIMER_START_FAILED', true) end
      return false, s.stop_reason
    end
    if not s.running then return false, s.stop_reason end
    timer = result
    return true
  end
  function api.note_start_rejection(reason)
    observe('start_rejected', {reason=reason}, 'rejected_starts')
  end
  function api.stop()
    if s.running then finish('OPERATOR_STOP', false) end
    return true
  end
  function api.status()
    local out = {}; for k, v in pairs(s) do out[k] = v end
    out.data_provenance=a.observation_source or 'UNKNOWN'
    out.scan_mode=c.scan.mode
    for k,v in pairs(a.scan_scope and a.scan_scope() or {}) do out[k]=v end
    out.events = {}; for i, v in ipairs(events) do out.events[i] = v end
    out.cleanup_ok = not cleanup_failed and not s.cleanup_pending
    return out
  end
  function api.evaluation()
    return a.evaluation and a.evaluation() or nil
  end
  return api
end
return M
