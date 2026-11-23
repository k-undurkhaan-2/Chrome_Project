-- QSG v1: explicit, synthetic-only constructor dependency. No globals/IPC APIs.
-- Native transport and live arming deliberately have no implementation in R2.
local M={version='qsg.v1'}
local function fail(code) error(code,0) end
local function copy(t)
  if type(t)~='table' then return t end
  local out={}; for k,v in pairs(t) do out[k]=copy(v) end; return out
end
local function bits(v)
  if type(v)~='number' or v~=v or math.abs(v)==math.huge then fail('QSG_BITS') end
  return string.format('0x%08X',string.unpack('<I4',string.pack('<f',v)))
end
local function equal(a,b)
  if type(a)~=type(b) then return false end
  if type(a)~='table' then return a==b end
  for k,v in pairs(a) do if not equal(v,b[k]) then return false end end
  for k in pairs(b) do if a[k]==nil then return false end end
  return true
end
function M.new(h)
  if type(h)~='table' or h.enabled~=true or h.origin~='SYNTHETIC' then fail('QSG_NOT_ARMED') end
  if type(h.transport)~='table' or h.transport.version~='qsg.mock.v1'
      or h.transport.bounded~=true or h.transport.authenticated~=true
      or h.transport.timeout_unit~='ms' or type(h.transport.request)~='function' then fail('QSG_TRANSPORT_UNQUALIFIED') end
  for _,k in ipairs({'now_ms','hash','next_operation','start_request','current_scope','checkpoint','post_checkpoint','retirement'}) do
    if type(h[k])~='function' then fail('QSG_COMPONENT_MISSING') end
  end
  if type(h.recorder)~='table' or type(h.recorder.append)~='function' or type(h.recorder.capture)~='function' then fail('QSG_RECORDER_UNAVAILABLE') end
  local f={version=M.version}
  local current, failed
  local function rpc(kind,data)
    return h.transport.request(kind,copy(data),h.now_ms()+250)
  end
  function f.prepare_start(cfg)
    if failed then fail('QSG_FAILED_CLOSED') end
    if current and not current.finished then fail('QSG_RUN_ACTIVE') end
    if cfg.diagnostics.enabled~=true or cfg.scan.stop_address-cfg.scan.start_address~=65535
        or cfg.scan.scan_budget~=128 or cfg.scan.max_candidates~=128 or cfg.write_bits~=0x42FA0000
        or cfg.scan.target_bits~=0x42C80000 or cfg.monitor_interval_ms~=1000 or cfg.invalid_confirmations~=2
        or cfg.rescan_backoff_ms~=1000 or cfg.max_backoff_ms~=30000 or cfg.min_rescan_spacing_ms~=2000
        or cfg.max_rescan_attempts~=5 or cfg.scan_timeout_ms~=120000 or cfg.diagnostics.event_limit~=512 then fail('QSG_CONFIG_SCOPE') end
    -- The host reopens its fixed enrollment; Start never provisions a budget.
    local binding=rpc('begin',h.start_request())
    local scope=copy(binding.scope)
    local start_witness=h.current_scope()
    if cfg.target_pid~=scope.identity.pid or cfg.scan.start_address~=tonumber(scope.base)
        or scope.size~='65536' or not equal(start_witness.scope,scope)
        or type(start_witness.alive_instances)~='number' or start_witness.alive_instances<1
        or start_witness.alive_instances>(binding.phase=='L11' and 2 or 1) then
      pcall(rpc,'end',{lease=binding.lease,clean=false}); failed=true; fail('QSG_SCOPE_CHANGED')
    end
    local r={version=M.version,mode='QUALIFICATION',observation_source='synthetic',finished=false}
    current=r
    local active, writing, ticking, captured = true,false,false,false
    local core, candidate, pending, readback, fault
    local phase, phase_sequence=binding.phase,binding.phase_sequence
    local last_sequence, aliases, observed_bits = 0,{},{}
    local last_clock=h.now_ms()
    local function append(kind,data)
      return h.recorder.append(kind,{lease=copy(binding.lease),phase=phase,data=copy(data)})
    end
    local function safety_error(code)
      active=false; fault=code; failed=true
      pcall(append,'FAILED_CLOSED',{code=code})
      fail(code)
    end
    function r.check_local()
      if not active or fault then fail('QSG_GENERATION_REVOKED') end
      local now=h.now_ms()
      if type(now)~='number' or now%1~=0 or now<last_clock then safety_error('QSG_CLOCK') end
      last_clock=now
      if not active or fault then fail('QSG_GENERATION_REVOKED') end
      return now
    end
    function r.assert_ready()
      r.check_local()
      if not equal(h.current_scope().scope,scope) then safety_error('QSG_SCOPE_CHANGED') end
      rpc('ready',{lease=binding.lease})
      append('READY',{policy_digest=binding.policy_digest})
    end
    function r.bind_core(instance)
      if core then safety_error('QSG_CORE_REBOUND') end
      core=instance
    end
    local function snapshot()
      if not core then safety_error('QSG_CORE_REQUIRED') end
      local s=core.evidence()
      if s.enabled~=true or s.dropped_events~=0 or s.telemetry_error or s.last_sequence<last_sequence
          or #s.events~=s.last_sequence then safety_error('QSG_EVIDENCE_GAP') end
      for i,e in ipairs(s.events) do if e.sequence~=i then safety_error('QSG_EVIDENCE_GAP') end end
      return s
    end
    local function sync()
      local s=snapshot()
      -- Normalizer checks every old event for mutation/rollback, including counters.
      h.recorder.capture(s,binding.lease.run_id,phase,aliases)
      for _,e in ipairs(s.events) do
        if e.sequence>last_sequence then
          if e.event_type=='valid_value_observed' then observed_bits[e.address_label]=string.format('0x%08X',e.value_bits) end
          if e.event_type=='address_retired' then
            local address=aliases[e.address_label]
            if not address then safety_error('QSG_BINDING') end
            rpc('retire',{lease=binding.lease,address=tostring(address),target_event=h.retirement(address),core_sequence=e.sequence})
          end
          if e.event_type=='monitor_result' and (phase=='L05' or phase=='L06') then
            if e.valid~=true then safety_error('QSG_INVALID_MONITOR') end
            local counts={}
            for _,k in ipairs({'monitor_checks','valid_monitor_checks','scan_count','write_count','verified_writes'}) do counts[k]=e.counters[k] end
            rpc('monitor',{lease=binding.lease,phase=phase,sequence=e.sequence,bits=observed_bits[e.address_label],counters=counts})
          end
          if e.event_type=='readback_verified' then
            if not pending or pending.result~='TRUE' or not readback or readback.address~=pending.address
                or readback.bits~=0x42FA0000 or bits(readback.value)~='0x42FA0000'
                or e.readback_bits~=readback.bits or e.float_bits~=readback.bits
                or aliases[e.address_label]~=pending.address then safety_error('QSG_READBACK_BINDING') end
            local post=h.post_checkpoint(pending.address,pending.attempt,binding.lease,phase)
            if post.bits~='0x42FA0000' then safety_error('QSG_TARGET_READBACK') end
            local seal=append('VERIFIED',{attempt=pending.attempt,address=tostring(pending.address),
              bits='0x42FA0000',core_sequence=e.sequence,target=post.record,readback=readback})
            rpc('outcome',{attempt=pending.attempt,result=pending.result,event_digest=pending.return_digest})
            rpc('verified',{attempt=pending.attempt,evidence_digest=seal})
            pending=nil; readback=nil
          end
        end
      end
      last_sequence=s.last_sequence
      return s
    end
    function r.bind_candidate(c)
      r.check_local()
      local s=sync(); local rank,pop
      for _,e in ipairs(s.events) do
        if e.event_type=='candidate_population' then pop=e end
        if e.event_type=='ranking_summary' then rank=e end
      end
      if not rank or not pop or rank.qualified_count~=1 or rank.hard_pass~=true
          or rank.recommendation~='ACCEPT' or pop.collection_complete~=true or pop.read_failure then safety_error('QSG_CANDIDATE') end
      if aliases[rank.address_label] and aliases[rank.address_label]~=c.address then safety_error('QSG_ALIAS_CONFLICT') end
      aliases[rank.address_label]=c.address
      candidate=copy(c)
      candidate.rank_sequence=rank.sequence; candidate.population_sequence=pop.sequence
      candidate.alias=rank.address_label; candidate.qualified_count=rank.qualified_count
      candidate.hard_pass=rank.hard_pass; candidate.recommendation=rank.recommendation
      for _,k in ipairs({'raw_count','scanned_count','filtered_count','selected_count'}) do candidate[k]=pop[k] end
      append('CANDIDATE',candidate)
    end
    function r.readback(address,word,value)
      readback={address=address,bits=word,value=value} -- no IPC between raw and core verification
    end
    local function scope_check(address)
      local witness=h.current_scope()
      if not equal(witness.scope,scope) or witness.alive~=true or witness.ce_token~=string.format('%d:%s',scope.identity.pid,scope.identity.creation) then safety_error('QSG_SCOPE_CHANGED') end
      if witness.alive_instances~=1 then safety_error('QSG_TARGET_CONCURRENCY') end
      local offset=address-tonumber(scope.base)
      if address%4~=0 or offset<32 or offset>65536-84 or witness.retired[tostring(address)]
          or not witness.pages[tostring(math.floor(offset/4096))] then safety_error('QSG_RANGE_OR_RETIRED') end
      return witness.ce_token
    end
    function r.build_writer(raw,final_check)
      r.assert_ready()
      if captured or type(raw)~='function' or type(final_check)~='function' then safety_error('QSG_WRITER_REBOUND') end
      captured=true
      local used={}
      return {write_float32=function(address,value)
        if writing then safety_error('QSG_REENTRANT') end
        writing=true
        local ok,result=pcall(function()
          r.check_local()
          local s=sync(); local status=core.status()
          if not s.running or status.state~='WRITING' or not candidate or candidate.address~=address
              or status.candidate_address~=address or pending then safety_error('QSG_CANDIDATE') end
          local intent
          for _,e in ipairs(s.events) do if e.event_type=='write_intent' then intent=e end end
          if not intent or intent.address_label~=candidate.alias or intent.write_intent_bits~=0x42FA0000
              or bits(value)~='0x42FA0000' then safety_error('QSG_BITS') end
          candidate.intent_sequence=intent.sequence
          local token=scope_check(address)
          if final_check(address)~=token then safety_error('QSG_IDENTITY') end
          local operation=tostring(h.next_operation())
          local nonce=binding.lease.writer_id .. ':' .. operation
          local request={schema='qsg.write.v1',session_id=h.session_id,authorization_id=h.authorization_id,
            lease=copy(binding.lease),phase=phase,phase_sequence=phase_sequence,operation_id=operation,
            nonce=nonce,deadline_ms=tostring(h.now_ms()+1000),
            scope=copy(scope),address=tostring(address),offset=tostring(address-tonumber(scope.base)),
            bits=bits(value),candidate=copy(candidate),checkpoint=h.checkpoint(address,binding.lease,phase,nonce),ce_token=token}
          local request_digest=h.hash(request)
          append('PERMIT_REQUEST',{request_digest=request_digest,operation_id=operation})
          local reserved=rpc('reserve',request)
          if reserved.receipt_kind~='RESERVATION' or reserved.request_digest~=request_digest then safety_error('QSG_ACK_MISMATCH') end
          pending={attempt=reserved.attempt,address=address}
          append('RESERVATION',reserved)
          local receipt=rpc('claim',{attempt=reserved.attempt,request_digest=request_digest,lease=binding.lease})
          if receipt.receipt_kind~='DISPATCH' or receipt.attempt~=reserved.attempt or receipt.request_digest~=request_digest
              or not equal(receipt.lease,binding.lease) or type(receipt.receipt)~='string' or used[receipt.receipt] then safety_error('QSG_ACK_MISMATCH') end
          scope_check(address)
          append('RAW_DISPATCH',{attempt=receipt.attempt,receipt=receipt.receipt,address=tostring(address),bits=bits(value)})
          r.check_local()
          if h.now_ms()>=tonumber(receipt.expires_ms) then safety_error('QSG_RECEIPT_EXPIRED') end
          -- All IPC/recorder/witness callbacks precede these final adapter checks.
          -- Only a passive local clock sample remains; no yield, IPC or retry.
          if final_check(address)~=token or not active or fault then fail('QSG_GENERATION_REVOKED') end
          if r.check_local()>=tonumber(receipt.expires_ms) then safety_error('QSG_RECEIPT_EXPIRED') end
          used[receipt.receipt]=true
          local call_ok,returned=pcall(raw,address,value)
          pending.result=not call_ok and 'EXCEPTION' or returned==true and 'TRUE'
            or returned==false and 'FALSE' or 'NONBOOLEAN'
          pending.return_digest=append('RAW_RETURN',{attempt=pending.attempt,result=pending.result})
          if not call_ok then safety_error('QSG_RAW_EXCEPTION') end
          return returned
        end)
        writing=false
        if not ok then
          active=false; failed=true; fault='QSG_WRITE_FAILED'
          pcall(append,'FAILED_CLOSED',{code='QSG_WRITE_FAILED'})
          error(type(result)=='string' and result:match('^QSG_[A-Z_]+$') and result or 'QSG_WRITE_FAILED',0)
        end
        return result
      end}
    end
    function r.revoke(reason)
      active=false -- no transport or recorder can delay cancellation
    end
    function r.finish()
      if r.finished then return end
      active=false
      local ok,s=pcall(sync)
      local clean=ok and s.cleanup_ok and not s.running and not fault and pending==nil
      if pending and pending.result and pending.return_digest then
        pcall(rpc,'outcome',{attempt=pending.attempt,result=pending.result,event_digest=pending.return_digest})
      end
      local ended=pcall(rpc,'end',{lease=binding.lease,clean=clean==true})
      r.finished=true
      if not clean or not ended then failed=true end
    end
    function r.wrap_tick(callback)
      return function()
        if not active then return end
        if ticking then
          active=false; failed=true; fault='QSG_REENTRANT_TIMER'
          if core then core.stop() end
          return
        end
        ticking=true
        local ok=pcall(function()
          r.check_local(); rpc('ready',{lease=binding.lease}); sync()
          -- Observe L02/L03 without silently relabeling the initial write.
          if core.status().state=='WRITING' and (phase=='L02' or phase=='L03') then return end
          callback(); sync()
        end)
        ticking=false
        if not ok then active=false; failed=true; fault=fault or 'QSG_SUPERVISOR'; core.stop() end
        if not core.status().running then r.finish() end
      end
    end
    function r.enter_phase(next_phase)
      r.check_local(); sync()
      local result=rpc('phase',{lease=binding.lease,phase=next_phase,expected=phase_sequence})
      phase=result.phase; phase_sequence=result.phase_sequence
    end
    return r
  end
  function f.enter_phase(phase)
    if not current then fail('QSG_NOT_ARMED') end
    return current.enter_phase(phase)
  end
  return f
end
return M
