-- Native CE product: config -> exact scan -> unchanged Single ranking -> maintain value.
-- Loading is inert. There are no engineering modes, fixtures or approval gates.
local api = {}
local state = {state='STOPPED', running=false, write_count=0, rewrite_count=0}
local config, modules, timer, scanner, found, worker, scan_done, next_check, started
local start_record, value_record, in_tick, pending_error, inspected, operations, slice_started

local function finite(v)
  return type(v)=='number' and v==v and math.abs(v)~=math.huge
end
local function integer(v, low, high)
  return finite(v) and v%1==0 and v>=low and v<=high
end
local function float32(v)
  assert(finite(v), 'Expected a finite Float32 value')
  local packed=string.pack('<f',v)
  local value=string.unpack('<f',packed)
  assert(finite(value), 'Float32 value is out of range')
  return value,string.unpack('<I4',packed)
end
local function read_config(path)
  local c=assert(loadfile(path,'t',{}))()
  assert(type(c)=='table', 'Config must return a table')
  assert(integer(c.target_pid,1,0xFFFFFFFF), 'target_pid must be a positive PID')
  assert(c.write_enabled==true, 'write_enabled must be true')
  assert(c.value_type==nil or c.value_type=='float32', 'value_type must be float32')
  assert(c.screening_profile==nil or c.screening_profile=='single', 'screening_profile must be single')
  assert(integer(c.monitor_interval_ms,1,0x7FFFFFFF), 'monitor_interval_ms must be positive')
  assert(type(c.scan)=='table', 'scan settings are required')
  local search,bits=float32(c.scan.target_value_float)
  assert(c.scan.target_value_pattern==nil or c.scan.target_value_pattern==bits,
    'target_value_pattern does not match target_value_float')
  local value,write_bits=float32(c.write_value)
  local lo,hi=c.scan.start_address,c.scan.stop_address
  if type(lo)=='string' then lo=assert(tonumber(lo), 'Invalid start_address') end
  if type(hi)=='string' then hi=assert(tonumber(hi), 'Invalid stop_address') end
  assert((lo==nil)==(hi==nil), 'Both scan bounds are required together')
  lo,hi=lo or 0x10000,hi or 0x7FFFFFFFFFFF
  assert(integer(lo,0,0x7FFFFFFFFFFF) and integer(hi,lo,0x7FFFFFFFFFFF), 'Invalid scan bounds')
  local batch=c.scan.collection_batch_size or 256
  local slice=c.scan.collection_slice_ms or 10
  local timeout=c.scan_timeout_ms or 120000
  assert(integer(batch,1,0x7FFFFFFF) and integer(slice,1,1000), 'Invalid collection timing')
  assert(integer(timeout,1,0x7FFFFFFF), 'scan_timeout_ms must be positive')
  -- Other legacy keys in the existing config are deliberately not interpreted.
  -- Count budgets cannot truncate the requested full initial address pool.
  return {pid=math.tointeger(c.target_pid), search=search, search_bits=bits,
    value=value, write_bits=write_bits, interval=c.monitor_interval_ms,
    lo=lo,hi=hi,batch=batch,slice=slice,timeout=timeout}
end
local function message(text)
  pcall(print,'[CE MVP] '..text)
end
local function dispose_scan()
  local errors={}
  if found then
    local old=found; found=nil
    if not pcall(function() old.destroy() end) then errors[#errors+1]='FoundList' end
  end
  if scanner then
    local old=scanner; scanner=nil
    if not pcall(function() old.OnScanDone=nil; old.destroy() end) then errors[#errors+1]='MemScan' end
  end
  worker=nil
  if #errors>0 then state.cleanup_error=table.concat(errors,', ') end
  return #errors==0,table.concat(errors,', ')
end
local function finish(reason, failed)
  if not state.running then return end
  state.running=false; state.stop_reason=reason; state.state=failed and 'ERROR' or 'STOPPED'
  if timer then
    local old=timer; timer=nil
    local ok=pcall(function() old.Enabled=false; old.OnTimer=nil; old.destroy() end)
    if not ok then state.cleanup_error='Timer' end
  end
  local ok,err=dispose_scan()
  if not ok then state.cleanup_error=err end
  state.cleanup_ok=state.cleanup_error==nil
  message(state.state..': '..reason)
  if start_record then pcall(function() start_record.Active=false end) end
end
local function guard()
  assert(state.running, 'STOPPED')
  assert(getOpenedProcessID()==config.pid, 'CE_TARGET_CHANGED')
end
local function checkpoint()
  if pending_error then error(pending_error,0) end
  local ok,err=pcall(guard)
  if not ok then pending_error=tostring(err); error(pending_error,0) end
  local now=getTickCount()
  if now-started>=config.timeout then pending_error='SCAN_TIMEOUT'; error(pending_error,0) end
  operations=operations+1
  if operations>=config.batch or now-slice_started>=config.slice then
    coroutine.yield()
    if pending_error then error(pending_error,0) end
    guard(); operations=0; slice_started=getTickCount()
  end
end
local function evaluate_pool()
  local env={assert=assert,error=error,type=type,pcall=pcall,pairs=pairs,ipairs=ipairs,
    next=next,select=select,tonumber=tonumber,tostring=tostring,math=math,string=string,
    table=table,debug=debug,os={clock=os.clock},print=function() end}
  env._G=env
  env.readInteger=function(address) checkpoint(); return readInteger(address) end
  env.readFloat=function(address) checkpoint(); return readFloat(address) end
  env.getAddress=function(address)
    return type(address)=='number' and address or tonumber(address,16)
  end
  env.getCurrentMemscan=function() return scanner end
  env.createFoundList=function(scan)
    assert(scan==scanner, 'SCAN_CHANGED')
    return {Count=state.raw_count,initialize=function() end,destroy=function() end,
      Address=setmetatable({}, {__index=function(_,index)
        checkpoint()
        assert(found.Count==state.raw_count, 'SCAN_RESULTS_CHANGED')
        if not inspected[index] then inspected[index]=true; state.inspected_count=state.inspected_count+1 end
        return found.Address[index]
      end})}
  end
  -- Load the original files verbatim; no scoring function is replaced or patched.
  assert(load(modules['mvp0_candidate_report.lua'],'@mvp0_candidate_report.lua','t',env))()
  local collector=assert(load(modules['mvp0_foundlist_collector.lua'],'@mvp0_foundlist_collector.lua','t',env))()
  local count=math.max(1,state.raw_count)
  local result=collector.run({scan_budget=count,max_candidates=count,
    target_value_pattern=config.search_bits,target_value_float=config.search,
    filter_target_match=true,use_prescore_selection=true,probe_full_foundlist=false,
    stable_filter_intersection_enabled=false})
  if pending_error then error(pending_error,0) end
  guard()
  assert(getTickCount()-started<config.timeout, 'SCAN_TIMEOUT')
  assert(found.Count==state.raw_count and result.raw_count==state.raw_count
    and result.scanned_count==state.raw_count and state.inspected_count==state.raw_count,
    'INCOMPLETE_ADDRESS_POOL')
  assert(result.selected_count==result.filtered_count
    and #result.result.ranked==result.selected_count, 'INCOMPLETE_RANKING')
  return result
end
local function current_value()
  guard()
  local value=readFloat(state.address)
  guard()
  if not finite(value) then error('VALUE_UNREADABLE (???)',0) end
  state.current_value=value
  return value
end
local function write_value(first)
  local before=current_value()
  if not first and before>=config.value then return end
  guard()
  state.write_count=state.write_count+1
  if not first then state.rewrite_count=state.rewrite_count+1 end
  assert(writeFloat(state.address,config.value)==true, 'WRITE_FAILED')
  local after=current_value()
  local _,bits=float32(after)
  assert(bits==config.write_bits, 'WRITE_READBACK_MISMATCH')
  state.last_written=config.value; state.readback_verified=true
  message(string.format('%s 0x%X = %.9g',first and 'Wrote' or 'Restored',state.address,after))
end
local function step()
  guard()
  local now=getTickCount()
  if state.state=='SCANNING' or state.state=='RANKING' then
    assert(now-started<config.timeout, 'SCAN_TIMEOUT')
  end
  if state.state=='SCANNING' and scan_done then
    found=createFoundList(scanner); found.initialize()
    state.raw_count=found.Count
    assert(integer(state.raw_count,0,math.maxinteger), 'INVALID_SCAN_COUNT')
    state.inspected_count=0; inspected={}; operations=0; slice_started=now
    state.state='RANKING'; worker=coroutine.create(evaluate_pool)
    message('Found '..state.raw_count..' addresses; ranking the full pool')
  end
  if state.state=='RANKING' then
    local ok,result=coroutine.resume(worker)
    if not state.running then return end
    if pending_error then error(pending_error,0) end
    if not ok then error(result,0) end
    if coroutine.status(worker)~='dead' then return end
    local ranked=result.result
    state.filtered_count=result.filtered_count; state.scored_count=#ranked.ranked
    local best=ranked.best
    local released,err=dispose_scan()
    assert(released,'SCAN_CLEANUP_FAILED: '..err)
    assert(best and best.hard_pass==true,'NO_HARD_PASS_CANDIDATE')
    state.address=best.candidate.value_addr; state.score=best.final_score
    state.recommendation=ranked.recommendation.recommendation
    if value_record then
      value_record.Active=false
      value_record.Address=string.format('%X',state.address)
    end
    -- The user requested rank 1 after the hard filter. Recommendation labels
    -- remain the unchanged algorithm's output, not a second execution gate.
    write_value(true)
    state.state='MONITORING'; next_check=getTickCount()+config.interval
    message('Monitoring every '..config.interval..' ms')
  elseif state.state=='MONITORING' and now>=next_check then
    state.monitor_checks=state.monitor_checks+1
    if current_value()<config.value then write_value(false) end
    next_check=getTickCount()+config.interval
  end
end
function api.start(config_path, embedded_modules, control_record, live_value_record)
  if state.running then return false,'ALREADY_RUNNING' end
  if state.cleanup_error then return false,'Close this CE session after cleanup failure' end
  state={state='STARTING',running=false,write_count=0,rewrite_count=0,monitor_checks=0,
    raw_count=0,inspected_count=0,filtered_count=0,scored_count=0,cleanup_ok=true}
  config=nil; modules=embedded_modules; scan_done=false; pending_error=nil
  start_record=control_record; value_record=live_value_record
  local ok,err=pcall(function()
    config=read_config(config_path)
    assert(type(modules)=='table' and type(modules['mvp0_candidate_report.lua'])=='string'
      and type(modules['mvp0_foundlist_collector.lua'])=='string','Embedded algorithms are missing')
    if value_record then
      value_record.Active=false; value_record.Address='0'
      value_record.OnActivate=function(_,before) return not before end
    end
    state.pid=config.pid; state.target_value=config.value; state.interval_ms=config.interval
    openProcess(config.pid)
    assert(getOpenedProcessID()==config.pid,'ATTACH_FAILED')
    state.running=true; started=getTickCount()
    scanner=createMemScan()
    if type(scanner.setSpecialScanOptionsOverride)=='function' then
      scanner.setSpecialScanOptionsOverride({MEM_PRIVATE=true,MEM_IMAGE=true,MEM_MAPPED=true})
    end
    scanner.OnlyOneResult=false; scanner.IsUnique=false
    local owned=scanner
    scanner.OnScanDone=function(sender)
      if state.running and scanner==owned and sender==owned then scan_done=true end
    end
    state.state='SCANNING'
    scanner.firstScan(soExactValue,vtDword,rtRounded,string.format('%08X',config.search_bits),'',
      config.lo,config.hi,'+W',fsmAligned,'4',true,false,false,false)
    timer=createTimer(nil,false); timer.Interval=50
    timer.OnTimer=function()
      if not state.running then return end
      if in_tick then finish('REENTRANT_TIMER',true); return end
      in_tick=true
      local success,failure=pcall(step)
      in_tick=false
      if not success and state.running then finish(tostring(failure),true) end
    end
    timer.Enabled=true
    message('Attached PID '..config.pid..'; scanning '..string.format('%.9g',config.search))
  end)
  if not ok then
    if state.running then finish(tostring(err),true)
    else state.state='ERROR'; state.stop_reason=tostring(err); message(state.stop_reason) end
    return false,tostring(err)
  end
  return true
end
function api.stop()
  if state.running then finish('OPERATOR_STOP',false) end
  return true
end
function api.status()
  local copy={}; for key,value in pairs(state) do copy[key]=value end
  return copy
end
function api.print_status()
  for _,key in ipairs({'state','pid','raw_count','inspected_count','filtered_count','scored_count',
      'address','score','recommendation','current_value','target_value','interval_ms',
      'write_count','rewrite_count','monitor_checks','readback_verified','stop_reason','cleanup_ok','cleanup_error'}) do
    local value=state[key]
    if key=='address' and value then value=string.format('0x%X',value) end
    message(key..'='..tostring(value))
  end
  return api.status()
end
return api
