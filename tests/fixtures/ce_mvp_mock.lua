-- Table-backed CE/Win32 primitives. No native API, target memory or CE is used.
local M = {}
function M.new(sources)
  local w={time=0, pid=101, opened=0, ce_handle=202, creation=91, alive=true,
    reads=0, writes={}, scans={}, timers={}, native_calls={}, objects={}, localmem={},
    open_calls=0, observers=0, streams=0, foundlists=0, active_scans=0,
    active_timers=0, max_scans=0, max_timers=0, forbidden=0, lines={}, fail={}}
  local ce={soExactValue=0,vtDword=2,rtRounded=0,fsmAligned=1}
  local function forbidden() w.forbidden=w.forbidden+1; error('FORBIDDEN_ACCESS') end
  for _,name in ipairs({'executeCode','executeCodeEx','writeInteger','writeBytes',
      'getProcessIDFromProcessName','getCurrentMemscan','AOBScan','waitTillDone'}) do ce[name]=forbidden end
  local function hook(event)
    if w.hook then w.hook(event) end
    if w.fail[event]=='throw' then error('INJECTED_' .. event) end
  end
  function w.object(addr, kind)
    local fields=kind=='weak' and {0,0,0,0,0,0,0}
      or {0x10011200,0x10013800,0x10042100,0x10060000,0x10025600,0x10028400,0x10086300}
    local o={addr=addr, mapped=true, readable=true, protect=4, alloc=0x100000, memory={}}
    for i,offset in ipairs({-0x20,-0x10,-8,0x30,0x40,0x48,0x50}) do o.memory[addr+offset]=fields[i] end
    o.memory[addr]=0x42C80000; w.objects[#w.objects+1]=o
    if w.fast_index then for key in pairs(o.memory) do w.fast_index[key]=o end end
    return o
  end
  function w.locate(addr)
    if w.fast_index then
      local o=w.fast_index[addr]; if o and o.mapped then return o end; return nil
    end
    for _,o in ipairs(w.objects) do if o.mapped and o.memory[addr]~=nil then return o end end
  end
  function w.use_layout(pages, words)
    -- Materialize whole committed pages, including zero-filled padding. Scan the
    -- bytes independently rather than trusting the target plan's position list.
    w.objects={}; w.image=true
    for _,page in ipairs(pages) do
      local base=0x100000+page*0x1000
      local o={addr=base+0x128,base=base,size=0x1000,mapped=true,readable=true,
        protect=4,alloc=0x100000,memory={}}
      for offset=0,0xFFC,4 do o.memory[base+offset]=0 end
      w.objects[#w.objects+1]=o
    end
    for offset,bits in pairs(words) do
      local addr=0x100000+offset
      assert(w.locate(addr),'plan must write only committed fixture pages').memory[addr]=bits
    end
    w.cfg.scan.start_address=0x100000; w.cfg.scan.stop_address=0x10FFFF
  end
  local exports, reverse={},{}
  ce.getAddressSafe=function(name, local_only)
    assert(local_only==true)
    local key=name:match('^kernel32%.(.+)$'); assert(key)
    if w.fail.symbol==key then return nil end
    if not exports[key] then exports[key]=#reverse+1; reverse[#reverse+1]=key end
    return exports[key]
  end
  ce.getCheatEngineFileVersion=function() return 0,{major=7,minor=w.fail.ce_version or 6} end
  ce.cheatEngineIs64Bit=function() return not w.fail.x86 end
  ce.executeCodeLocalEx=function(symbol,...)
    local name=assert(reverse[symbol]); local args={}
    for i=1,select('#',...) do local p=select(i,...); assert(p.type==0); args[i]=p.value end
    w.native_calls[#w.native_calls+1]={name=name,args=args}; hook(name)
    if w.fail[name]=='nil' then return nil end
    if name=='GetTickCount64' then return w.time end
    if name=='GetSystemInfo' then
      local p=args[1]; assert(p==0x800000 and w.observers==1 and w.opened==w.pid)
      if w.fail.system_info_no_output then return end
      local bytes=string.pack('<I2I2I4I8I8I8I4I4I4I2I2',
        9,0,4096,0x10000,0x7FFFFFFEFFFF,1,1,8664,65536,6,0)
      assert(#bytes==48)
      for offset=0,44,4 do w.localmem[p+offset]=string.unpack('<I4',bytes,offset+1) end
      for _,offset in ipairs({8,16}) do w.localmem[p+offset]=string.unpack('<I8',bytes,offset+1) end
      for offset,value in pairs(w.system_info_override or {}) do w.localmem[p+offset]=value end
      return -- native return is void, never a success Boolean
    end
    if name=='OpenProcess' then
      assert(args[1]==0x101400 and args[2]==0 and args[3]==w.pid)
      w.open_calls=w.open_calls+1
      if w.fail.open then return 0 end
      assert(w.observers==0); w.observers=1; return 201
    end
    if name=='CloseHandle' then
      assert(args[1]==201 and w.observers==1,'must never close borrowed CE handle')
      w.observers=0; return w.fail.close and 0 or 1
    end
    assert(args[1]==201 or args[1]==202,'unowned process handle')
    if name=='WaitForSingleObject' then
      assert(args[2]==0)
      if w.fail.wait then return 0xFFFFFFFF end
      return w.alive and 258 or 0
    end
    if name=='GetProcessId' then return w.fail.native_pid or w.pid end
    if name=='GetProcessTimes' then
      if w.fail.times then return 0 end
      local ptr=args[2]; assert(args[3]==ptr+8 and args[4]==ptr+16 and args[5]==ptr+24)
      w.localmem[ptr]=w.creation+(args[1]==202 and (w.fail.ce_creation or 0) or 0)
      w.localmem[ptr+4]=1; return 1
    end
    if name=='VirtualQueryEx' then
      assert(args[1]==201 and args[4]==48)
      local o=w.locate(args[2]); if not o then return 0 end
      local p=args[3]
      w.localmem[p]=o.base or 0x100000; w.localmem[p+8]=o.alloc; w.localmem[p+24]=o.size or 0x20000
      w.localmem[p+32]=0x1000; w.localmem[p+36]=o.protect; w.localmem[p+40]=0x20000
      return 48
    end
    error('unexpected native API ' .. name)
  end
  ce.createMemoryStream=function()
    w.streams=w.streams+1; local dead=false
    return {Memory=0x800000, destroy=function() assert(not dead); dead=true; w.streams=w.streams-1 end}
  end
  ce.readIntegerLocal=function(addr) return w.localmem[addr] end
  ce.readQwordLocal=ce.readIntegerLocal
  ce.writeIntegerLocal=function(addr,value)
    assert(addr==0x800000 or addr==0x800004)
    if w.fail.local_write then return false end
    w.localmem[addr]=value; return true
  end
  ce.openProcess=function(pid)
    assert(pid==w.pid and type(pid)=='number'); hook('attach')
    w.opened=w.fail.attach and 999 or pid
  end
  ce.getOpenedProcessID=function() hook('opened_pid'); return w.opened end
  ce.getOpenedProcessHandle=function() return w.ce_handle end
  local function target_access()
    assert(w.alive and w.opened==w.pid and w.ce_handle==202,'unauthorized process memory access')
  end
  ce.readInteger=function(addr)
    target_access(); w.reads=w.reads+1; hook('read')
    local o=w.locate(addr)
    if not o or not o.readable or w.fail.unreadable==addr then return nil end
    return o.memory[addr]
  end
  ce.readFloat=function(addr)
    target_access(); w.reads=w.reads+1; hook('read_float')
    if w.fail.readback_float and #w.writes>0 then return w.fail.readback_float end
    local o=w.locate(addr)
    if o and o.readable then return (string.unpack('<f',string.pack('<I4',o.memory[addr]))) end
  end
  ce.writeFloat=function(addr,value)
    target_access(); hook('write')
    local o=assert(w.locate(addr)); w.writes[#w.writes+1]={addr=addr,value=value,time=w.time}
    if w.fail.write_nil then return nil end
    if w.fail.write_return~=nil then return w.fail.write_return end
    if w.fail.write_no_change then return true end
    o.memory[addr]=string.unpack('<I4',string.pack('<f',value)); return true
  end
  ce.createMemScan=function()
    hook('create_scan'); assert(w.active_scans==0,'overlapping scanners')
    w.active_scans=w.active_scans+1; w.max_scans=math.max(w.max_scans,w.active_scans)
    local ms={done=false,dead=false,addresses={}}
    if not w.fail.scan_policy then
      ms.setSpecialScanOptionsOverride=function(options) ms.policy=options end
    end
    w.scans[#w.scans+1]=ms
    ms.firstScan=function(...)
      target_access(); hook('first_scan')
      local args={...}; ms.args=args
      assert(#args==14 and args[1]==0 and args[2]==2 and args[4]=='42C80000')
      assert(args[8]=='+W-X-C' and args[9]==1 and args[10]=='4' and args[11]==true)
      assert(ms.OnlyOneResult==false and ms.IsUnique==false)
      for _,o in ipairs(w.objects) do
        if w.image then
          for addr=o.base,o.base+o.size-4,4 do
            if o.mapped and o.protect==4 and addr>=args[6] and addr<=args[7]
                and o.memory[addr]==0x42C80000 then ms.addresses[#ms.addresses+1]=addr end
          end
        elseif o.mapped and o.protect==4 and o.memory[o.addr]==0x42C80000 then
          ms.addresses[#ms.addresses+1]=o.addr
        end
      end
      ms.due=w.time+50
      ms.saved_callback=ms.OnScanDone
    end
    ms.getProgress=function()
      assert(ms.done)
      return {TotalAddressesToScan=100,CurrentlyScanned=w.fail.progress and 50 or 100,
        ResultsFound=w.fail.results_count or #ms.addresses}
    end
    ms.destroy=function()
      assert(not ms.dead); ms.dead=true; w.active_scans=w.active_scans-1
      hook('destroy_scan')
    end
    return ms
  end
  ce.createFoundList=function(ms)
    assert(ms.done and not ms.dead,'FoundList read before completion')
    w.foundlists=w.foundlists+1
    local fl={Count=#ms.addresses,Address={},dead=false}
    w.latest_foundlist=fl
    for i,addr in ipairs(ms.addresses) do fl.Address[i-1]=string.format('%X',addr) end
    fl.initialize=function() hook('initialize') end
    fl.destroy=function() assert(not fl.dead); fl.dead=true; w.foundlists=w.foundlists-1; hook('destroy_foundlist') end
    return fl
  end
  ce.createTimer=function(owner,enabled)
    assert(owner==nil and enabled==false and w.active_timers==0)
    local t={Enabled=false,dead=false}; w.timers[#w.timers+1]=t
    w.active_timers=w.active_timers+1; w.max_timers=math.max(w.max_timers,w.active_timers)
    t.destroy=function() assert(not t.dead); t.dead=true; w.active_timers=w.active_timers-1 end
    return t
  end
  ce.print=function(line) hook('log'); w.lines[#w.lines+1]=line end
  w.ce=ce
  function w.load(name,env) return assert(load(assert(sources[name]),'@'..name,'t',env or _G))() end
  w.core=w.load('ce_mvp_core.lua'); w.adapter_module=w.load('ce_mvp_adapter.lua')
  w.cfg=w.load('ce_mvp_config.example.lua')
  w.cfg.target_pid=w.pid; w.cfg.write_enabled=true
  w.cfg.scan.start_address=0x100000; w.cfg.scan.stop_address=0x11FFFF
  w.cfg.monitor_interval_ms=100; w.cfg.rescan_backoff_ms=100; w.cfg.max_backoff_ms=800
  w.cfg.min_rescan_spacing_ms=200; w.cfg.scan_timeout_ms=10000; w.cfg.max_rescan_attempts=3
  function w.start()
    local validated=w.core.validate(w.cfg)
    w.adapter=w.adapter_module.new(validated,ce,w.load,'synthetic')
    w.loop=w.core.new(w.cfg,w.adapter); return w.loop.start()
  end
  function w.step(count)
    for _=1,count or 1 do
      w.time=w.time+50
      for _,ms in ipairs(w.scans) do
        if not ms.done and not ms.dead and ms.due and w.time>=ms.due and not w.fail.no_complete then
          ms.done=true; if ms.OnScanDone then ms.OnScanDone(ms) end
        end
      end
      for _,t in ipairs(w.timers) do if t.Enabled and t.OnTimer then t.OnTimer(t) end end
    end
  end
  function w.until_state(state)
    for _=1,1000 do
      local s=w.loop.status()
      if s.state==state then return s end
      if not s.running then error('unexpected terminal state: '..s.state..':'..tostring(s.last_error)) end
      w.step()
    end
    error('state timeout: '..state)
  end
  function w.clean()
    assert(w.active_scans==0 and w.active_timers==0 and w.observers==0 and w.streams==0 and w.foundlists==0)
    assert(w.forbidden==0 and w.max_scans<=1 and w.max_timers<=1)
  end
  return w
end
return M
