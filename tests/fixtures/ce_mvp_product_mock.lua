-- Deterministic CE API doubles for the standalone product. Never shipped in CT.
return function()
  local w={time=0,pid=101,opened=0,memory={},addresses={},timers={},scans={},writes={},
    reads=0,opens=0,fail={},cfg={target_pid=101,write_enabled=true,write_value=125,
      monitor_interval_ms=1000,scan_timeout_ms=120000,
      scan={target_value_float=100,target_value_pattern=0x42C80000,scan_budget=2,max_candidates=1}}}
  local env=setmetatable({}, {__index=_G}); env._G=env; w.env=env
  env.print=function() end
  env.soExactValue=0; env.vtDword=2; env.rtRounded=0; env.fsmAligned=1
  env.getMainForm=function() return {SaveDialog1={FileName=w.filename or ''}} end
  env.loadfile=function(path)
    w.config_path=path
    if w.fail.config then return nil,'CONFIG_MISSING' end
    return function() return w.cfg end
  end
  env.openProcess=function(pid)
    assert(type(pid)=='number'); w.opens=w.opens+1; w.opened=w.fail.attach and 999 or pid
  end
  env.getOpenedProcessID=function() return w.opened end
  env.getTickCount=function() return w.time end
  local function hook(event)
    if w.hook then w.hook(event) end
  end
  env.readInteger=function(addr)
    w.reads=w.reads+1; hook('integer')
    return w.memory[addr]
  end
  env.readFloat=function(addr)
    w.reads=w.reads+1; hook('float')
    if w.fail.unreadable then return nil end
    if w.fail.float~=nil then return w.fail.float end
    local bits=w.memory[addr]
    if bits then return (string.unpack('<f',string.pack('<I4',bits))) end
  end
  env.writeFloat=function(addr,value)
    hook('write')
    w.writes[#w.writes+1]={address=addr,value=value,time=w.time}
    if w.fail.write then return false end
    if not w.fail.readback then w.memory[addr]=string.unpack('<I4',string.pack('<f',value)) end
    return true
  end
  function w.object(addr,strong)
    addr=addr or 0x100128+#w.addresses*0x200
    for offset=-0x80,0xCC,4 do w.memory[addr+offset]=0 end
    local fields={0x10011200,0x10013800,0x10042100,0x10060000,0x10025600,0x10028400,0x10086300}
    if strong~=false then
      for i,offset in ipairs({-0x20,-0x10,-8,0x30,0x40,0x48,0x50}) do w.memory[addr+offset]=fields[i] end
    end
    w.memory[addr]=0x42C80000; w.addresses[#w.addresses+1]=addr
    return addr
  end
  env.createMemScan=function()
    local s={results={}}; w.scans[#w.scans+1]=s
    s.setSpecialScanOptionsOverride=function(opts) s.options=opts end
    s.firstScan=function(...)
      s.args={...}
      assert(s.args[1]==env.soExactValue and s.args[2]==env.vtDword)
      local bits=tonumber(s.args[4],16)
      for _,addr in ipairs(w.addresses) do
        if w.memory[addr]==bits and addr>=s.args[6] and addr<=s.args[7] then
          s.results[#s.results+1]=string.format('%X',addr)
        end
      end
      table.sort(s.results)
    end
    s.destroy=function()
      assert(not w.fail.scan_destroy,'SCAN_DESTROY_FAILED')
      s.destroyed=true
    end
    return s
  end
  env.createFoundList=function(s)
    local f={Count=#s.results,Address={}}
    for i,addr in ipairs(s.results) do f.Address[i-1]=addr end
    f.initialize=function() f.initialized=true end
    f.destroy=function() f.destroyed=true end
    w.found=f; return f
  end
  env.createTimer=function(_,enabled)
    local t={Enabled=enabled}; w.timers[#w.timers+1]=t
    t.destroy=function() t.destroyed=true end
    return t
  end
  w.records={}
  for id=1,3 do
    local data={Active=false,Address='0'}
    w.records[id]=setmetatable({}, {__index=data,__newindex=function(record,key,value)
      if key=='Active' and data.Active~=value then
        if value and data.OnActivate and not data.OnActivate(record,true,data.Active) then return end
        data.Active=value
        local code=w.scripts and w.scripts[id] and w.scripts[id][value and 1 or 2]
        if code then
          local ok,err=pcall(assert(load(code,'@CT:'..id,'t',env)))
          if not ok then data.Active=false; error(err,0) end
        end
      else data[key]=value end
    end})
  end
  env.getAddressList=function() return {getMemoryRecordByID=function(id) return w.records[id] end} end
  function w.start() w.records[1].Active=true end
  function w.stop() w.records[1].Active=false end
  function w.status() return env.CE_MVP_PRODUCT.status() end
  function w.step(count)
    for _=1,count or 1 do
      w.time=w.time+50
      for _,s in ipairs(w.scans) do
        if not s.destroyed and not s.done and not w.fail.scan_pending then
          s.done=true; s.OnScanDone(s)
        end
      end
      for _,t in ipairs(w.timers) do
        if not t.destroyed and t.Enabled then t.OnTimer(t) end
      end
    end
  end
  function w.until_state(expected)
    for _=1,10000 do
      local s=w.status()
      if s.state==expected then return s end
      assert(s.state~='ERROR',s.stop_reason)
      w.step()
    end
    error('TEST_TIMEOUT: '..w.status().state)
  end
  return w
end
