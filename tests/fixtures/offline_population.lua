-- Existing table population fixture, independent of the retired CE orchestration.
-- No process, scan, timer, write or native API is provided.
local M = {}
function M.new(sources)
  local w={reads=0, writes={}, scans={}, timers={}, native_calls={}, objects={},
    open_calls=0, forbidden=0, cfg={scan={scan_budget=128,max_candidates=128}}}
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
  function w.load(name,env)
    if type(sources)=='function' then return sources(name,env) end
    return assert(load(assert(sources[name]),'@'..name,'t',env or _G))()
  end
  return w
end
return M
