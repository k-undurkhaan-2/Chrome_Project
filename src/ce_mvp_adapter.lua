-- CE 7.6 x64 / Windows adapter. Loaded code is inert; new() resolves local APIs.
-- Win32 calls execute in CE, never in the target. Never close CE's borrowed handle.
local M = {}
local function fail(code) error(code, 0) end
local function whole(v) return type(v)=='number' and v%1==0 end
local function finite(v) return type(v)=='number' and v==v and math.abs(v)~=math.huge end
local MAX_ADDRESS = 0x7FFFFFFFFFFF
local function u32(v)
  if not whole(v) or v < -0x80000000 or v > 0xFFFFFFFF then return nil end
  return v < 0 and v+0x100000000 or v
end
local FIELDS = {f08=-0x20, f18=-0x10, f20=-8, f58=0x30, f68=0x40, f70=0x48, f78=0x50}
function M.new(cfg, ce, load_module, observation_source, execution)
  if execution then
    if execution.mode~='QUALIFICATION' or execution.version~='qsg.v1'
        or type(execution.assert_ready)~='function' or type(execution.build_writer)~='function'
        or observation_source~='synthetic' then fail('QSG_NATIVE_BACKEND_NOT_QUALIFIED') end
    execution.assert_ready() -- before acquiring even the raw writer capability
  end
  local f = {}
  for name in ([[openProcess getOpenedProcessID getOpenedProcessHandle getAddressSafe
      executeCodeLocalEx createMemoryStream readIntegerLocal readQwordLocal
      createMemScan createFoundList createTimer readInteger readFloat writeFloat
      cheatEngineIs64Bit getCheatEngineFileVersion getTickCount print]]):gmatch('%S+') do
    if type(ce[name]) ~= 'function' then fail('CE_API_MISSING:' .. name) end
    f[name] = ce[name]
  end
  for name in ('soExactValue vtDword rtRounded fsmAligned'):gmatch('%S+') do
    if not whole(ce[name]) or ce[name]<0 then fail('CE_ENUM_MISSING:' .. name) end
    f[name]=ce[name]
  end
  local _, version = f.getCheatEngineFileVersion()
  if type(version)~='table' or version.major~=7 or version.minor~=6 then fail('REQUIRES_CE_7_6') end
  if not f.cheatEngineIs64Bit() then fail('REQUIRES_CE_X64_WINDOWS') end
  local native = {}
  for name in ('OpenProcess CloseHandle GetProcessId GetProcessTimes WaitForSingleObject VirtualQueryEx'):gmatch('%S+') do
    native[name] = f.getAddressSafe('kernel32.' .. name, true)
    if not whole(native[name]) or native[name] <= 0 then fail('WIN32_API_MISSING:' .. name) end
  end
  if cfg.scan.mode=='process' then
    native.GetSystemInfo=f.getAddressSafe('kernel32.GetSystemInfo', true)
    if not whole(native.GetSystemInfo) or native.GetSystemInfo<=0 then fail('WIN32_API_MISSING:GetSystemInfo') end
    if type(ce.writeIntegerLocal)~='function' then fail('CE_API_MISSING:writeIntegerLocal') end
    f.writeIntegerLocal=ce.writeIntegerLocal
  end
  local function call(name, ...)
    local args = {}
    for i=1,select('#', ...) do args[i]={type=0, value=select(i, ...)} end
    return f.executeCodeLocalEx(native[name], table.unpack(args))
  end
  local a = {observation_source=observation_source or 'CE'}
  local observe=function() end
  function a.set_observer(fn) observe=fn end
  local observer, borrowed, stream, identity, guard, active_scan, timer
  local poison, closed, log_count, cleanup_uncertain = nil, false, 0, false
  local writer_port, bound_candidate
  local cycle_id=0
  local function empty_scope()
    return {cycle_id=cycle_id,scope_resolved=false,scan_mode=cfg.scan.mode,alignment_bytes=4,
      scan_policy=(cfg.scan.mode=='process' and 'MEM_PRIVATE; ' or '') .. '+W-X-C; aligned exact Float32 bits',
      candidate_policy='MEM_COMMIT/MEM_PRIVATE/PAGE_READWRITE; whole -0x20..+0x53 context',
      scope_complete=false,scan_complete=false,collection_complete=false,global_uniqueness_proven=false,
      decision_scope=execution and 'QSG_FULL_POPULATION' or 'LEGACY_SINGLE_SCOPE',write_admission_basis='NONE',
      raw_admission_complete=false,ranking_complete=false,coverage='pending',collection_phase='idle',
      raw_inspected_count=0,raw_admitted_count=0,collected_count=0,evaluated_count=0,
      unique_count=0,filtered_count=0,prescored_count=0,selected_count=0,ranked_count=0,qualified_count=0,
      raw_admission_budget=cfg.scan.scan_budget,ranking_budget=cfg.scan.max_candidates}
  end
  local scope=empty_scope()
  local start_address, stop_address
  function a.scan_scope()
    local out={}; for k,v in pairs(scope) do out[k]=v end; return out
  end
  function a.set_guard(fn) guard = fn end
  function a.now() return f.getTickCount() end
  local function checked()
    if execution then execution.check_local() end
    if poison then fail(poison) end
    local ok, err = pcall(guard)
    if not ok then poison=tostring(err); fail(poison) end
  end
  local function live_token(handle, pid, role)
    local waiting = call('WaitForSingleObject', handle, 0)
    if waiting == 0 then fail('PID_EXITED') end
    if waiting ~= 258 then fail('IDENTITY_UNCERTAIN') end
    if call('GetProcessId', handle) ~= pid then fail('PID_IDENTITY_MISMATCH') end
    local p = stream.Memory
    if call('GetProcessTimes', handle, p, p+8, p+16, p+24) ~= 1 then fail('IDENTITY_UNCERTAIN') end
    local lo, hi = u32(f.readIntegerLocal(p)), u32(f.readIntegerLocal(p+4))
    if not lo or not hi or (lo==0 and hi==0) then fail('IDENTITY_UNCERTAIN') end
    if call('WaitForSingleObject', handle, 0) ~= 258 then fail('PID_EXITED_OR_UNCERTAIN') end
    local token=string.format('%d:%08X%08X', pid, hi, lo)
    observe('identity_sample', {role=role,token=token})
    return token
  end
  function a.check_identity(token)
    observe('identity_begin', nil, 'identity_checks')
    if closed or not observer or not borrowed or not stream then fail('IDENTITY_UNCERTAIN') end
    if f.getOpenedProcessID() ~= cfg.target_pid or f.getOpenedProcessHandle() ~= borrowed then
      fail('CE_TARGET_CHANGED')
    end
    if live_token(observer, cfg.target_pid, 'query') ~= token
        or live_token(borrowed, cfg.target_pid, 'ce_reported') ~= token then fail('PID_IDENTITY_MISMATCH') end
    if f.getOpenedProcessID() ~= cfg.target_pid or f.getOpenedProcessHandle() ~= borrowed then
      fail('CE_TARGET_CHANGED')
    end
    observe('identity_ok')
  end
  function a.attach(pid)
    if closed or observer or pid ~= cfg.target_pid then fail('ATTACH_STATE_INVALID') end
    stream = f.createMemoryStream(); stream.Size=64
    observer = call('OpenProcess', 0x101400, 0, pid) -- QUERY_INFORMATION | QUERY_LIMITED | SYNCHRONIZE
    if not whole(observer) or observer <= 0 then observer=nil; fail('PROCESS_OPEN_FAILED') end
    identity = live_token(observer, pid, 'query')
    f.openProcess(pid) -- numeric PID only; return value differs across CE builds
    borrowed = f.getOpenedProcessHandle()
    if not whole(borrowed) or borrowed <= 0 then fail('CE_ATTACH_FAILED') end
    a.check_identity(identity)
    return identity
  end
  local function resolve_scope()
    -- begin_scan already guards the bound PID/creation token for both modes.
    if cfg.scan.mode=='bounded' then
      start_address,stop_address=cfg.scan.start_address,cfg.scan.stop_address
      scope.bounds_source='explicit configuration (legacy compatible)'
    else
      local p=stream.Memory
      -- SYSTEM_INFO on Windows AMD64: 48 bytes, DWORD union/page at 0/4,
      -- pointer-sized min/max at 8/16, allocation granularity DWORD at 40.
      -- GetSystemInfo returns void; poison output markers to detect no output.
      if f.writeIntegerLocal(p, -1)~=true or f.writeIntegerLocal(p+4, 0)~=true then
        fail('SYSTEM_INFO_BUFFER_FAILED')
      end
      call('GetSystemInfo', p)
      local arch,page=f.readIntegerLocal(p),f.readIntegerLocal(p+4)
      local lo,hi=f.readQwordLocal(p+8),f.readQwordLocal(p+16)
      local gran=f.readIntegerLocal(p+40)
      checked()
      if arch~=9 or page~=4096 or gran~=65536 or not whole(lo) or not whole(hi)
          or lo<0x10000 or lo>MAX_ADDRESS or hi<lo or hi>MAX_ADDRESS or hi-lo<128
          or lo%gran~=0 or (hi+1)%page~=0 then fail('PROCESS_SCOPE_UNAVAILABLE') end
      start_address,stop_address=lo,hi
      scope.bounds_source='GetSystemInfo/AMD64 SYSTEM_INFO (48 bytes)'
    end
    scope.scan_start_address,scope.scan_stop_address=start_address,stop_address
    scope.scope_resolved=true
    if cfg.scan.mode=='process' then observe('scan_scope_resolved', a.scan_scope()) end
  end
  function a.read_bits(addr)
    checked()
    observe(nil, nil, 'adapter_read_calls')
    return u32(f.readInteger(addr))
  end
  function a.write_float(addr, value)
    checked()
    if cfg.write_enabled ~= true or value ~= cfg.write_value then fail('WRITE_NOT_CONFIGURED') end
    observe('write_intent', {address=addr,write_intent_bits=cfg.write_bits}, 'adapter_write_attempts')
    local result=writer_port.write_float32(addr, value)
    observe('write_api_result', {address=addr,api_success=result==true},
      result==true and 'adapter_write_successes' or nil)
    return result
  end
  function a.readback(addr)
    observe(nil, nil, 'adapter_readback_calls')
    local bits = a.read_bits(addr)
    checked()
    observe(nil, nil, 'adapter_read_calls')
    local value=f.readFloat(addr)
    if execution then execution.readback(addr,bits,value) end
    return bits, value
  end
  local function mapping(addr)
    checked()
    if not whole(addr) or addr<0x10020 or addr>MAX_ADDRESS-0x53 then return nil end
    observe(nil, nil, 'mapping_queries')
    local p = stream.Memory
    if call('VirtualQueryEx', observer, addr, p, 48) ~= 48 then return nil end
    local base, alloc, size = f.readQwordLocal(p), f.readQwordLocal(p+8), f.readQwordLocal(p+24)
    local state, protect, kind = f.readIntegerLocal(p+32), f.readIntegerLocal(p+36), f.readIntegerLocal(p+40)
    if not whole(base) or not whole(alloc) or not whole(size) or size <= 0
        or base<0 or base>MAX_ADDRESS or alloc<0 or alloc>MAX_ADDRESS
        or size>MAX_ADDRESS-base+1
        or addr-0x20 < base or addr+0x54 > base+size
        or state~=0x1000 or protect~=0x04 or kind~=0x20000 then return nil end
    if cfg.scan.mode=='process' and (alloc>base or alloc<0x10000
        or base%4096~=0 or size%4096~=0) then return nil end
    return string.format('%X:%X:%X', base, alloc, size)
  end
  function a.valid(candidate)
    if mapping(candidate.address) ~= candidate.mapping then return false, 'MAPPING_CHANGED' end
    for key, offset in pairs(FIELDS) do
      local value = a.read_bits(candidate.address+offset)
      if value == nil then return false, 'ADDRESS_UNREADABLE' end
      if value ~= candidate.fields[key] then return false, 'STRUCTURE_CHANGED' end
    end
    local bits = a.read_bits(candidate.address)
    if bits == nil then return false, 'ADDRESS_UNREADABLE' end
    local value = string.unpack('<f', string.pack('<I4', bits))
    if value~=value or math.abs(value)==math.huge then return false, 'NONFINITE_VALUE' end
    observe('valid_value_observed', {address=candidate.address,value_bits=bits})
    return true -- finite value drift is intentionally irrelevant to validity
  end
  local function within(addr)
    return whole(addr) and addr>=0x10020 and addr<=MAX_ADDRESS-0x53
      and addr%4==0 and start_address~=nil and addr-0x20>=start_address
      and addr+0x53<=stop_address
  end
  local env = {assert=assert, error=error, type=type, pcall=pcall, pairs=pairs, ipairs=ipairs,
    tonumber=tonumber, tostring=tostring, math=math, string=string, table=table,
    debug=debug, os={clock=os.clock}, print=function() end}
  env._G = env
  env.getAddress = function(v)
    local n = type(v)=='number' and v or (type(v)=='string' and tonumber(v,16))
    if not within(n) then fail('FOUND_ADDRESS_OUT_OF_RANGE') end
    return n
  end
  local function abort(code)
    poison=code -- legacy pcall readers must not swallow a safety failure
    fail(code)
  end
  local function collection_time()
    checked()
    local task,now=active_scan,a.now()
    if not task then abort('SCAN_STATE_INVALID') end
    if not whole(now) or now<0 or now>math.maxinteger or now<task.last_tick then abort('CLOCK_UNCERTAIN') end
    task.last_tick=now
    if now-task.started_tick>=cfg.scan_timeout_ms then abort('SCAN_TIMEOUT') end
    return now
  end
  local function checkpoint()
    local now=collection_time()
    local task=active_scan
    task.operations=task.operations+1
    if task.operations>=cfg.scan.collection_batch_size or now-task.slice_started>=cfg.scan.collection_slice_ms then
      coroutine.yield()
      task.operations=0; task.slice_started=collection_time()
    end
  end
  env.readInteger = function(addr)
    checkpoint()
    local ok,bits = pcall(a.read_bits,addr)
    if not ok or bits==nil then active_scan.read_failure=true end
    if not ok then error(bits,0) end
    return bits
  end
  env.readFloat = function(addr)
    checkpoint(); checked(); observe(nil, nil, 'adapter_read_calls')
    local ok,value = pcall(f.readFloat,addr)
    if not ok then active_scan.read_failure=true; error(value,0) end
    if type(value)~='number' or value~=value or math.abs(value)==math.huge then active_scan.read_failure=true end
    return value
  end
  env.getCurrentMemscan = function() return active_scan.object end
  env.createFoundList = function(ms)
    checked()
    local task=active_scan
    if not task or not task.done or ms~=task.object or task.foundlist then fail('FOUNDLIST_BEFORE_DONE') end
    local fl = f.createFoundList(ms); task.foundlist=fl
    local total,indices,addresses=nil,{},{}
    local function verify_population()
      checkpoint()
      if fl.Count~=total then abort('FOUNDLIST_COUNT_CHANGED') end
      local progress=ms.getProgress()
      observe('scan_progress', {progress_results=type(progress)=='table' and progress.ResultsFound or nil,
        total_addresses=type(progress)=='table' and progress.TotalAddressesToScan or nil,
        scanned_addresses=type(progress)=='table' and progress.CurrentlyScanned or nil})
      if type(progress)~='table' or not whole(progress.TotalAddressesToScan)
          or progress.TotalAddressesToScan<0 or progress.TotalAddressesToScan>math.maxinteger
          or progress.CurrentlyScanned~=progress.TotalAddressesToScan
          or progress.ResultsFound~=total then abort('SCAN_COMPLETION_UNCERTAIN') end
      scope.scan_complete=true
    end
    task.verify_population=verify_population
    local proxy = {Address=setmetatable({}, {__index=function(_, index)
      checkpoint()
      if fl.Count~=total then abort('FOUNDLIST_COUNT_CHANGED') end
      if not whole(index) or index<0 or index>=total then abort('INVALID_FOUNDLIST_INDEX') end
      local addr=env.getAddress(fl.Address[index])
      if indices[index] and indices[index]~=addr then abort('FOUNDLIST_ADDRESS_CHANGED') end
      if addresses[addr] and addresses[addr]~=index+1 then abort('DUPLICATE_FOUND_ADDRESS') end
      if not indices[index] then scope.raw_inspected_count=scope.raw_inspected_count+1 end
      indices[index],addresses[addr]=addr,index+1
      return addr
    end})}
    function proxy.initialize()
      fl.initialize()
      total=fl.Count; scope.raw_match_count=total
      observe('scan_population', {cycle_id=task.cycle_id,raw_match_count=total,count_source='CE FoundList.Count',
        collection_complete=false,raw_admission_budget=cfg.scan.scan_budget,
        ranking_budget=cfg.scan.max_candidates,native_count_limited=false})
      if not whole(total) or total<0 or total>math.maxinteger then abort('INVALID_FOUNDLIST_COUNT') end
      verify_population()
      proxy.Count=total -- same native pool and zero-based indices; never truncate
      scope.collection_phase='legacy_collection'
      observe('scan_population_complete', {cycle_id=task.cycle_id,raw_match_count=total,scan_complete=true,
        collection_complete=false,completeness_reason='scan verified; legacy collection pending'})
    end
    function proxy.destroy()
      verify_population()
      -- Legacy destroys its view; native ownership stays with adapter disposal.
      for index,addr in pairs(indices) do
        checkpoint()
        if env.getAddress(fl.Address[index])~=addr then abort('FOUNDLIST_ADDRESS_CHANGED') end
      end
      verify_population()
    end
    return proxy
  end
  -- Private environments keep legacy runner globals and callbacks intact.
  local report = load_module('mvp0_candidate_report.lua', env)
  local collector = load_module('mvp0_foundlist_collector.lua', env)
  local score = report.score_candidate
  report.score_candidate = function(...)
    checkpoint()
    return score(...)
  end
  local function choose(bundle)
    local r=type(bundle)=='table' and bundle.result
    if type(r)~='table' or type(r.ranked)~='table' then fail('INVALID_RANK_RESULT') end
    if bundle.raw_count~=scope.raw_match_count then abort('FOUNDLIST_COUNT_CHANGED') end
    local function count(value, limit)
      return whole(value) and value>=0 and value<=limit
    end
    -- Legacy omits this optional count when no filtered candidates exist.
    local prescored=bundle.prescored_count
    if prescored==nil and bundle.filtered_count==0 then prescored=0 end
    if not count(bundle.scanned_count, math.min(bundle.raw_count,cfg.scan.scan_budget))
        or not count(bundle.unique_count,bundle.scanned_count)
        or not count(bundle.filtered_count,bundle.unique_count)
        or not count(prescored,bundle.filtered_count)
        or not count(bundle.selected_count,math.min(bundle.filtered_count,cfg.scan.max_candidates))
        or #r.ranked~=bundle.selected_count
        or type(bundle.candidate_value_addrs)~='table'
        or #bundle.candidate_value_addrs~=bundle.selected_count then fail('INVALID_SCOPE_COUNTS') end
    local decision=r.recommendation
    if type(decision)~='table' or r.final_decision~=decision
        or type(decision.manual_review_required)~='boolean'
        or (decision.recommendation~='ACCEPT' and decision.recommendation~='REVIEW'
          and decision.recommendation~='REJECT')
        or r.best~=r.ranked[1] or r.second~=r.ranked[2]
        or decision.recommended_candidate~=r.best then fail('INVALID_RANK_RESULT') end
    for _,row in ipairs(r.ranked) do
      if type(row)~='table' or type(row.candidate)~='table'
          or type(row.hard_pass)~='boolean' or not finite(row.final_score) then fail('INVALID_RANK_RESULT') end
    end
    scope.raw_admitted_count=bundle.scanned_count
    scope.collected_count=bundle.scanned_count -- alias, not native Count
    scope.unique_count=bundle.unique_count
    scope.filtered_count=bundle.filtered_count
    scope.prescored_count=prescored
    scope.selected_count=bundle.selected_count
    scope.ranked_count=#r.ranked; scope.evaluated_count=#r.ranked
    scope.raw_admission_strategy=bundle.raw_admission_strategy
    scope.selection_strategy=bundle.selection_strategy
    scope.raw_admission_complete=bundle.scanned_count==bundle.raw_count
    scope.ranking_complete=bundle.selected_count==bundle.filtered_count and #r.ranked==bundle.selected_count
    scope.collection_complete=scope.raw_admission_complete and scope.ranking_complete
    scope.coverage=scope.collection_complete and 'full_population' or 'sampled_or_reduced'
    scope.collection_phase='legacy_complete'
    scope.scope_complete=scope.collection_complete and not active_scan.read_failure
    observe('candidate_population', {cycle_id=cycle_id,raw_count=bundle.raw_count,scanned_count=bundle.scanned_count,
      raw_inspected_count=scope.raw_inspected_count,unique_count=bundle.unique_count,
      filtered_count=bundle.filtered_count,prescored_count=scope.prescored_count,
      selected_count=bundle.selected_count,ranked_count=#r.ranked,coverage=scope.coverage,
      collection_complete=scope.collection_complete,read_failure=active_scan.read_failure==true})
    if active_scan.read_failure then fail('SCREENING_READ_FAILED') end
    if #r.ranked==0 then
      if execution and not scope.collection_complete then fail('INCOMPLETE_CANDIDATE_POPULATION') end
      if decision.recommendation~='REJECT' then fail('INVALID_RANK_RESULT') end
      scope.qualified_count=0
      observe('ranking_summary', {cycle_id=cycle_id,ranked_count=0,qualified_count=0,recommendation='NONE'})
      return nil
    end
    local qualified=0
    for _, row in ipairs(r.ranked) do
      -- Bounded diagnostic count only in NORMAL; never override Legacy ACCEPT.
      -- QUALIFICATION retains its separate full-population/one-qualifier gate.
      local single=report.rank_candidates({report.score_candidate(row.candidate,cfg.scan.target_bits)})
      local decision=report.recommend_action(single)
      if single.best.hard_pass and decision.recommendation=='ACCEPT' then qualified=qualified+1 end
    end
    scope.qualified_count=qualified
    scope.ranking_best_address=r.best.candidate.value_addr
    scope.ranking_second_address=r.second and r.second.candidate.value_addr
    scope.ranking_best_score=r.best.final_score; scope.ranking_best_family_size=r.best.template_family_size
    scope.ranking_score_gap=r.score_gap; scope.ranking_confidence=r.confidence
    scope.ranking_recommendation=r.recommendation.recommendation
    observe('ranking_summary', {cycle_id=cycle_id,ranked_count=#r.ranked,qualified_count=qualified,
      coverage=scope.coverage,global_uniqueness_proven=false,
      recommendation=r.recommendation.recommendation,manual_review=r.recommendation.manual_review_required,
      best_score=r.best.final_score,hard_pass=r.best.hard_pass,confidence=r.confidence,
      address=r.best.candidate.value_addr})
    if execution then
      if not scope.collection_complete then fail('INCOMPLETE_CANDIDATE_POPULATION') end
      if qualified>1 then fail('AMBIGUOUS_CANDIDATES') end
      if qualified~=1 then fail('CANDIDATE_NOT_QUALIFIED') end
    end
    if r.best.hard_pass~=true or decision.recommendation~='ACCEPT'
        or decision.manual_review_required~=false then fail('CANDIDATE_NOT_QUALIFIED') end
    local row = r.best.candidate
    if not within(row.value_addr) then fail('FOUND_ADDRESS_OUT_OF_RANGE') end
    local selected=false
    for _,addr in ipairs(bundle.candidate_value_addrs) do
      if addr==row.value_addr then selected=true; break end
    end
    if not selected then fail('CANDIDATE_NOT_SELECTED') end
    if u32(row.f28)~=cfg.scan.target_bits or row.f28_float~=cfg.scan.target_value_float then
      fail('CANDIDATE_NOT_QUALIFIED')
    end
    local candidate = {address=row.value_addr, fields={}, mapping=mapping(row.value_addr)}
    if not candidate.mapping then fail('CANDIDATE_MAPPING_INVALID') end
    for key in pairs(FIELDS) do
      if u32(row[key])==nil then fail('CANDIDATE_UNREADABLE') end
      candidate.fields[key]=row[key]
    end
    scope.global_uniqueness_proven=scope.collection_complete and qualified==1
    scope.write_admission_basis=execution and 'QSG_FULL_POPULATION_UNIQUE_ACCEPT' or 'LEGACY_SCOPE_ACCEPT'
    observe('candidate_admitted', {cycle_id=cycle_id,address=candidate.address,coverage=scope.coverage,
      decision_scope=scope.decision_scope,write_admission_basis=scope.write_admission_basis,
      global_uniqueness_proven=scope.global_uniqueness_proven})
    return candidate
  end
  function a.begin_scan()
    checked()
    if active_scan then fail('SCAN_OVERLAP') end
    cycle_id=cycle_id+1
    scope=empty_scope() -- No previous ranking/coverage can prove this fresh cycle.
    start_address,stop_address=nil,nil
    scope.collection_phase='resolving_scope'
    resolve_scope()
    local task = {done=false, disposed=false,cycle_id=cycle_id}; active_scan=task
    local now=a.now()
    if not whole(now) or now<0 or now>math.maxinteger then fail('CLOCK_UNCERTAIN') end
    task.started_tick,task.last_tick,task.slice_started=now,now,now; task.operations=0
    scope.collection_phase='scanning'
    local ms=f.createMemScan(); task.object=ms
    if cfg.scan.mode=='process' then
      if type(ms.setSpecialScanOptionsOverride)~='function' then fail('PROCESS_SCAN_POLICY_UNAVAILABLE') end
      ms.setSpecialScanOptionsOverride({MEM_PRIVATE=true,MEM_IMAGE=false,MEM_MAPPED=false})
      scope.scan_policy='MEM_PRIVATE; +W-X-C; aligned exact Float32 bits'
    end
    ms.OnlyOneResult=false; ms.IsUnique=false
    ms.OnScanDone=function(sender)
      -- Only enqueue completion. Never read results/destroy an object in its event.
      if not task.disposed and sender==ms then task.done=true end
    end
    checked()
    -- Dword discovery of the exact Float32 bits avoids CE's decimal scan rounding.
    -- Candidate interpretation, qualification and the only write API remain Float32.
    observe('scan_invocation', {cycle_id=task.cycle_id,search_bits=cfg.scan.target_bits,
      search_mode='float32_bits_via_dword_hex',raw_admission_budget=cfg.scan.scan_budget,
      ranking_budget=cfg.scan.max_candidates}, 'adapter_scan_invocations')
    ms.firstScan(f.soExactValue, f.vtDword, f.rtRounded,
      string.format('%08X',cfg.scan.target_bits), '', start_address,
      stop_address, '+W-X-C', f.fsmAligned, '4', true, false, false, false)
    return task
  end
  function a.poll_scan(task)
    checked()
    if task~=active_scan or task.disposed then fail('SCAN_STATE_INVALID') end
    if not task.done then return false end
    if not task.worker then
      observe('scan_done_observed', {cycle_id=task.cycle_id}, 'scan_completions')
      task.worker=coroutine.create(function()
        local bundle=collector.run({max_candidates=cfg.scan.max_candidates,
          scan_budget=cfg.scan.scan_budget, target_value_pattern=cfg.scan.target_bits,
          target_value_float=cfg.scan.target_value_float, filter_target_match=true,
          use_prescore_selection=true, probe_full_foundlist=false,
          stable_filter_intersection_enabled=false, session_id='ce-native-single'})
        checked(); task.verify_population(); return choose(bundle)
      end)
    end
    local ok, result = coroutine.resume(task.worker)
    if poison then fail(poison) end
    if not ok then fail('SCREENING_CALLBACK:' .. tostring(result)) end
    if coroutine.status(task.worker)=='dead' then
      if execution and result then
        bound_candidate={address=result.address,mapping=result.mapping,fields={}}
        for k,v in pairs(result.fields) do bound_candidate.fields[k]=v end
        execution.bind_candidate(bound_candidate)
      end
      return true, result
    end
    return false
  end
  function a.dispose_scan(task)
    if task.disposed then return end
    observe('scan_dispose_begin', {cycle_id=task.cycle_id,cancel_requested=not task.done},
      not task.done and 'scan_cancel_requests' or nil)
    task.disposed=true; task.worker=nil
    if task==active_scan then active_scan=nil end
    local errors={}
    if task.foundlist then
      local fl=task.foundlist; task.foundlist=nil
      if not pcall(function() fl.destroy() end) then errors[#errors+1]='FOUNDLIST_CLEANUP_FAILED' end
    end
    if task.object then
      local ms=task.object; task.object=nil
      -- CE's destructor terminates the native scanner and releases its result files.
      if not pcall(function() ms.OnScanDone=nil; ms.destroy() end) then errors[#errors+1]='memscan' end
    end
    if #errors>0 then
      cleanup_uncertain=true; scope.scope_complete=false; scope.global_uniqueness_proven=false
      fail('SCAN_CLEANUP_FAILED:' .. table.concat(errors,','))
    end
    observe('scan_disposed', {cycle_id=task.cycle_id,dispose_call_returned=true}, 'scan_disposals')
  end
  function a.create_timer(interval, callback)
    if timer then fail('TIMER_OVERLAP') end
    if execution then callback=execution.wrap_tick(callback) end
    timer=f.createTimer(nil,false)
    timer.Interval=interval; timer.OnTimer=callback; timer.Enabled=true
    return timer
  end
  function a.cancel_timer(t)
    if t==timer then timer=nil end
    t.Enabled=false; t.OnTimer=nil; t.destroy()
    observe('timer_disposed', {dispose_call_returned=true})
  end
  function a.close()
    if execution then execution.revoke('ADAPTER_CLOSED') end
    closed=true
    local errors={}
    if timer and not pcall(a.cancel_timer, timer) then errors[#errors+1]='timer' end
    if active_scan and not pcall(a.dispose_scan, active_scan) then errors[#errors+1]='scan' end
    if observer then
      local old=observer; observer=nil
      local ok,result=pcall(call,'CloseHandle',old)
      if not ok or result~=1 then errors[#errors+1]='observer' end
      observe('query_handle_close', {api_success=ok and result==1})
    end
    if stream then
      local old=stream; stream=nil
      local ok=pcall(function() old.destroy() end)
      if not ok then errors[#errors+1]='stream' end
      observe('local_stream_dispose', {dispose_call_returned=ok})
    end
    if cleanup_uncertain then errors[#errors+1]='prior_cleanup' end
    if #errors>0 then fail('RESOURCE_CLEANUP_FAILED:' .. table.concat(errors,',')) end
  end
  function a.log(line)
    -- One session emits at most log_limit lines, including optional file output.
    local terminal=line:find('stop_reason=',1,true)~=nil
    -- Reserve the last line for the terminal reason even after noisy retries.
    if log_count>=cfg.log_limit or (not terminal and log_count>=cfg.log_limit-1) then return end
    log_count=log_count+1; f.print(line)
    if cfg.log_path then
      local out=assert(io.open(cfg.log_path,'a'))
      local ok,err=out:write(line .. '\n'); local closed_ok=out:close()
      if not ok or not closed_ok then error(err or 'LOG_CLOSE_FAILED',0) end
    end
  end
  if execution then
    local function final_check(addr)
      checked()
      if closed or not bound_candidate or bound_candidate.address~=addr then fail('QSG_CANDIDATE') end
      a.check_identity(identity)
      if a.valid(bound_candidate)~=true or a.read_bits(addr)~=cfg.scan.target_bits then fail('QSG_SCOPE_CHANGED') end
      checked()
      return identity
    end
    writer_port=execution.build_writer(f.writeFloat,final_check)
    if type(writer_port)~='table' or type(writer_port.write_float32)~='function' then fail('QSG_PLUGIN_MISSING') end
  else
    -- NORMAL preserves first result, exception identity and operation ordering.
    writer_port={write_float32=function(addr,value) return f.writeFloat(addr, value) end}
  end
  return a
end
return M
