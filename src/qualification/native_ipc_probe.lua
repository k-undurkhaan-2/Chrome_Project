-- Standalone qsg.native-probe.v1. Loading defines functions only.
-- No ambient CE APIs, module imports, connection creation, timers or workers.
-- start_native is blocked; new_offline accepts explicitly supplied test fakes.
local M = {version='qsg.native-probe.v1'}
local function need(ok, code) if not ok then error(code,0) end end
local function whole(v) return type(v)=='number' and v%1==0 end
local function ident(v)
  return type(v)=='string' and #v>=1 and #v<=80 and v:match('^[%w][%w_.:-]*$')~=nil
end
local function sha(v) return type(v)=='string' and #v==64 and v:match('^[0-9a-f]+$')~=nil end
local keys={'channel_id','epoch','kind','method','origin','payload','request_id',
  'request_sha256','result','schema','sequence','session_id'}
local allowed={}; for _,k in ipairs(keys) do allowed[k]=true end
local methods={HELLO=true,ECHO=true,PING=true,CANCEL=true,CLOSE=true}

local function valid_utf8(s)
  local ok=pcall(function()
    need(utf8.len(s)~=nil,'INVALID_UTF8')
    for _,v in utf8.codes(s) do need(v<=0x10ffff and not (v>=0xd800 and v<=0xdfff),'INVALID_UTF8') end
  end)
  need(ok,'INVALID_UTF8')
end
local function quote(s)
  valid_utf8(s)
  local short={['\b']='\\b',['\f']='\\f',['\n']='\\n',['\r']='\\r',['\t']='\\t',['"']='\\"',['\\']='\\\\'}
  return '"' .. s:gsub('[%z\1-\31\\"]',function(c)
    return short[c] or string.format('\\u%04x',string.byte(c))
  end) .. '"'
end
local function canonical(v)
  local out={}
  for _,k in ipairs(keys) do
    local x=v[k]
    need(type(x)=='string' or whole(x),'JSON_TYPE')
    out[#out+1]=quote(k) .. ':' .. (type(x)=='string' and quote(x) or string.format('%d',x))
  end
  return '{' .. table.concat(out,',') .. '}'
end
local function validate(v)
  need(type(v)=='table','MESSAGE_FIELDS')
  local count=0
  for k in pairs(v) do need(allowed[k],'MESSAGE_FIELDS'); count=count+1 end
  need(count==#keys,'MESSAGE_FIELDS')
  need(v.schema==M.version and v.origin=='SYNTHETIC','ORIGIN_OR_VERSION')
  need(methods[v.method]==true,'METHOD')
  need(v.kind=='REQUEST' or v.kind=='RESPONSE','MESSAGE_KIND')
  need(ident(v.session_id) and ident(v.channel_id) and ident(v.request_id),'IDENTIFIER')
  need(whole(v.epoch) and v.epoch>=1 and v.epoch<=2147483647 and whole(v.sequence)
    and v.sequence>=1 and v.sequence<=2147483647,'INTEGER')
  need(type(v.payload)=='string','PAYLOAD')
  if v.method~='ECHO' then need(v.payload=='','CONTROL_PAYLOAD') end
  if v.kind=='REQUEST' then need(v.request_sha256=='' and v.result=='','REQUEST_FIELDS')
  else
    need(sha(v.request_sha256),'SHA256')
    need(v.result==(v.method=='CANCEL' and 'CANCELLED' or v.method=='CLOSE' and 'CLOSED' or 'OK'),'RESPONSE_RESULT')
  end
end
local function decode(body)
  valid_utf8(body)
  local pos=1
  local function char() return body:sub(pos,pos) end
  local function take(c) need(char()==c,'INVALID_JSON'); pos=pos+1 end
  local function str()
    take('"'); local out={}
    while pos<=#body do
      local c=char(); pos=pos+1
      if c=='"' then return table.concat(out) end
      if c=='\\' then
        local e=char(); pos=pos+1
        local escapes={['"']='"',['\\']='\\',['/']='/',b='\b',f='\f',n='\n',r='\r',t='\t'}
        if e=='u' then
          local h=body:sub(pos,pos+3)
          need(#h==4 and h:match('^[0-9a-fA-F]+$'),'INVALID_JSON')
          local n=tonumber(h,16)
          need(n<0xd800 or n>0xdfff,'INVALID_JSON')
          out[#out+1]=utf8.char(n); pos=pos+4
        else need(escapes[e]~=nil,'INVALID_JSON'); out[#out+1]=escapes[e] end
      else need(string.byte(c)>=32,'INVALID_JSON'); out[#out+1]=c end
    end
    error('INVALID_JSON',0)
  end
  take('{'); local result={}
  if char()~='}' then
    while true do
      local k=str(); need(result[k]==nil,'DUPLICATE_KEY'); take(':')
      if char()=='"' then result[k]=str()
      else
        local n=body:sub(pos):match('^-?%d+')
        need(n and #n<=10,'JSON_NUMBER'); pos=pos+#n; result[k]=tonumber(n)
      end
      if char()=='}' then break end
      take(',')
    end
  end
  take('}'); need(pos==#body+1,'INVALID_JSON')
  validate(result); need(canonical(result)==body,'NONCANONICAL_JSON')
  return result
end

-- Pure Lua 5.3 integer SHA-256. No crypto/native/FFI library is loaded.
local K={0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,
0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,
0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,
0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,
0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,
0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,
0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,
0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2}
local function ror(x,n) return ((x>>n)|(x<<(32-n)))&0xffffffff end
local function hash(raw)
  local h={0x6a09e667,0xbb67ae85,0x3c6ef372,0xa54ff53a,0x510e527f,0x9b05688c,0x1f83d9ab,0x5be0cd19}
  local data=raw .. '\128' .. string.rep('\0',(55-#raw)%64) .. string.pack('>I8',#raw*8)
  for offset=1,#data,64 do
    local w={}
    for j=0,15 do w[j]=string.unpack('>I4',data,offset+j*4) end
    for j=16,63 do
      local x,y=w[j-15],w[j-2]
      w[j]=(w[j-16]+(ror(x,7)~ror(x,18)~(x>>3))+w[j-7]+(ror(y,17)~ror(y,19)~(y>>10)))&0xffffffff
    end
    local a,b,c,d,e,f,g,hh=table.unpack(h)
    for j=0,63 do
      local t1=(hh+(ror(e,6)~ror(e,11)~ror(e,25))+((e&f)~((~e)&g))+K[j+1]+w[j])&0xffffffff
      local t2=((ror(a,2)~ror(a,13)~ror(a,22))+((a&b)~(a&c)~(b&c)))&0xffffffff
      hh,g,f,e,d,c,b,a=g,f,e,(d+t1)&0xffffffff,c,b,a,(t1+t2)&0xffffffff
    end
    local v={a,b,c,d,e,f,g,hh}
    for j=1,8 do h[j]=(h[j]+v[j])&0xffffffff end
  end
  local out={}; for _,n in ipairs(h) do out[#out+1]=string.format('%08x',n) end
  return table.concat(out)
end
M.sha256=hash
function M.decode_frame(raw)
  need(type(raw)=='string' and #raw>=4,'TRUNCATED_FRAME')
  local n=string.unpack('<I4',raw)
  need(n>=1 and n<=65536,'FRAME_LENGTH')
  need(#raw==n+4,#raw<n+4 and 'TRUNCATED_FRAME' or 'TRAILING_BYTES')
  return decode(raw:sub(5))
end
function M.start_native() error('R3_B_NOT_AUTHORIZED',0) end

function M.new_offline(cap,binding)
  need(type(cap)=='table' and cap.mode=='offline' and cap.origin=='SYNTHETIC','OFFLINE_PROBE_DISABLED')
  local cap_keys={mode=true,origin=true,read_some=true,write_some=true,close=true,now_ms=true,cancelled=true,emit=true}
  for k in pairs(cap) do need(cap_keys[k],'CAPABILITY_NOT_ALLOWED') end
  for _,k in ipairs({'read_some','write_some','close','now_ms','cancelled','emit'}) do need(type(cap[k])=='function','CAPABILITY_MISSING') end
  need(type(binding)=='table' and ident(binding.session_id) and ident(binding.channel_id)
    and whole(binding.epoch) and binding.epoch>0 and binding.epoch<=2147483647,'BINDING')
  for k in pairs(binding) do need(k=='session_id' or k=='channel_id' or k=='epoch','BINDING') end
  local sid,cid,epoch=binding.session_id,binding.channel_id,binding.epoch
  local read,write,close,clock,cancelled,emit=cap.read_some,cap.write_some,cap.close,cap.now_ms,cap.cancelled,cap.emit
  local state,sequence,seen,last='NEW',0,{},-1
  local header,body,length,deadline='', '',nil,nil
  local pending,position,current=nil,1,nil
  local closed,cleanup,busy=false,'NOT_OBSERVED',false
  local api={}
  local function now()
    local n=clock(); need(whole(n) and n>=0 and n>=last,'CLOCK_REVERSED'); last=n; return n
  end
  function api.close()
    if closed then return cleanup end
    closed=true; pending=nil; current=nil; state='CLOSED'; cleanup='INDETERMINATE'
    local ok,result=pcall(close)
    if ok and result==true then cleanup='CLOSED' end
    emit('CLOSE',nil,nil,cleanup)
    return cleanup
  end
  local function check()
    need(not closed,'SESSION_CLOSED')
    need(cancelled()~=true,'CANCELLED')
    local n=now(); if deadline then need(n<deadline,'REQUEST_TIMEOUT') end
    return n
  end
  function api.step()
    if busy then api.close(); error('REENTRANT_REQUEST',0) end
    busy=true
    local ok,result=pcall(function()
      local n=check()
      if not deadline then deadline=n+250 end
      if pending then
        local part=pending:sub(position,position+4095)
        local sent=write(part)
        need(whole(sent) and sent>0 and sent<=#part,'SHORT_OR_INVALID_SEND')
        emit('TX_CHUNK',current,part:sub(1,sent),''); check()
        position=position+sent
        if position<=#pending then return 'PROGRESS' end
        emit('TX',current,pending,'')
        local method=current.method
        pending=nil; current=nil; header=''; body=''; length=nil; deadline=nil; position=1
        state='READY'
        if method=='CLOSE' or method=='CANCEL' then api.close() end
        return 'REPLIED'
      end
      local chunk=read(4096)
      need(type(chunk)=='string' and #chunk<=4096,'READ_BYTES')
      if #chunk>0 then emit('RX_CHUNK',nil,chunk,'') end
      check()
      if #chunk==0 then return 'WAIT' end
      local take=math.min(4-#header,#chunk)
      header=header .. chunk:sub(1,take)
      if #header==4 and not length then
        length=string.unpack('<I4',header)
        need(length>=1 and length<=65536,'FRAME_LENGTH')
      end
      local rest=chunk:sub(take+1)
      if length then need(#body+#rest<=length,'TRAILING_BYTES'); body=body .. rest end
      if not length or #body<length then return 'PROGRESS' end
      local request=decode(body)
      need(request.kind=='REQUEST' and request.session_id==sid and request.channel_id==cid and request.epoch==epoch,'REQUEST_BINDING')
      need(request.sequence==sequence+1 and not seen[request.request_id],'REQUEST_REPLAY')
      need((state=='NEW' and request.method=='HELLO') or (state=='READY' and request.method~='HELLO'),'METHOD_ORDER')
      sequence=request.sequence; seen[request.request_id]=true
      emit('RX',request,header .. body,'')
      local response={}; for k,v in pairs(request) do response[k]=v end
      response.kind='RESPONSE'; response.request_sha256=hash(body)
      response.result=request.method=='CANCEL' and 'CANCELLED' or request.method=='CLOSE' and 'CLOSED' or 'OK'
      local reply=canonical(response); need(#reply<=65536,'FRAME_LENGTH')
      pending=string.pack('<I4',#reply) .. reply; current=response; state='SENDING'
      return 'PROGRESS'
    end)
    busy=false
    if not ok then
      pcall(emit,'REJECT',nil,nil,'COMPONENT_FAILURE')
      api.close()
      error(result,0)
    end
    return result
  end
  function api.status() return state,cleanup end
  return api
end
-- B0 maps the installed LuaPipe API shape through injected test equipment.
-- No real CE object can be obtained here: start_native remains hard-blocked.
function M.new_ce_pipe_model(provider,binding,options)
  need(type(provider)=='table' and provider.origin=='SYNTHETIC','SYNTHETIC_PROVIDER_REQUIRED')
  local permitted={origin=true,connectToPipe=true,observe_closed=true,now_ms=true,cancelled=true,emit=true}
  for k in pairs(provider) do need(permitted[k],'CAPABILITY_NOT_ALLOWED') end
  for _,k in ipairs({'connectToPipe','observe_closed','now_ms','cancelled','emit'}) do
    need(type(provider[k])=='function','CAPABILITY_MISSING')
  end
  need(type(options)=='table','PIPE_OPTIONS')
  for k in pairs(options) do
    need(k=='endpoint' or k=='constructor_parameter' or k=='timeout_property' or k=='units','PIPE_OPTIONS')
  end
  need(type(options.endpoint)=='string' and options.endpoint:match('^qsg%-r3%-%x+$')
    and #options.endpoint==39,'LOCAL_ENDPOINT')
  need(options.units=='UNKNOWN_MODEL','TIMEOUT_UNITS_UNVERIFIED')
  need(options.constructor_parameter==25 or options.constructor_parameter==100
    or options.constructor_parameter==250,'PIPE_TIMEOUT_PARAMETER')
  need(whole(options.timeout_property) and options.timeout_property>0 and options.timeout_property<=250,'PIPE_TIMEOUT_PROPERTY')
  local connect,observe,clock,cancelled,emit=provider.connectToPipe,provider.observe_closed,
    provider.now_ms,provider.cancelled,provider.emit
  local endpoint,parameter,property=options.endpoint,options.constructor_parameter,options.timeout_property
  local pipe,worker=nil,nil
  local used,closed,deadline,last=false,false,nil,-1
  local cleanup='NOT_OBSERVED'
  local api={}
  local function check()
    need(not closed and cancelled()~=true,'CANCELLED')
    local n=clock(); need(whole(n) and n>=0 and n>=last,'CLOCK_REVERSED'); last=n
    if deadline then need(n<deadline,'REQUEST_TIMEOUT') end
    return n
  end
  local function close_pipe()
    if closed then return cleanup=='CLOSED' end
    closed=true; cleanup='UNCERTAIN'
    if not pipe then cleanup='CLOSED'; return true end
    local ok=pcall(function() pipe.destroy() end)
    if ok and observe(pipe)==true then cleanup='CLOSED' end
    return cleanup=='CLOSED'
  end
  local cap={mode='offline',origin='SYNTHETIC',now_ms=clock,cancelled=cancelled,emit=emit,close=close_pipe}
  cap.read_some=function(maximum)
    check(); need(pipe and pipe.Connected==true,'DISCONNECTED')
    local bytes=pipe.readBytes(maximum)
    check(); need(type(bytes)=='table','READ_NIL')
    local out,count={},0
    for k,v in pairs(bytes) do
      need(whole(k) and k>=1 and k<=maximum and whole(v) and v>=0 and v<=255,'READ_BYTES')
      count=count+1
    end
    need(count<=maximum,'READ_BYTES')
    for n=1,count do need(bytes[n]~=nil,'READ_BYTES'); out[n]=string.char(bytes[n]) end
    return table.concat(out) -- empty model read means WAIT, nil means failed read
  end
  cap.write_some=function(raw)
    check(); need(pipe and pipe.Connected==true,'DISCONNECTED')
    local bytes={}; for n=1,#raw do bytes[n]=string.byte(raw,n) end
    local count=pipe.writeBytes(bytes,#bytes)
    check(); need(whole(count) and count>0 and count<=#raw,'SHORT_OR_INVALID_SEND')
    return count
  end
  -- Validate binding and construct an inert byte worker before connection.
  worker=M.new_offline(cap,binding)
  function api.connect()
    need(not used,'CONNECTION_REUSE'); used=true
    local ok,result=pcall(function()
      deadline=check()+250
      pipe=connect(endpoint,parameter)
      check(); need(type(pipe)=='table' and pipe.Connected==true,'CONNECT_FAILED')
      need(type(pipe.readBytes)=='function' and type(pipe.writeBytes)=='function'
        and type(pipe.destroy)=='function','PIPE_CAPABILITY')
      pipe.Timeout=property
      -- Never install an extension callback or pump UI messages.
      pipe.OnAboutToTimeout=function() return true end
      check(); deadline=nil
      return 'SYNTHETIC_CONNECTED'
    end)
    if not ok then close_pipe(); error(result,0) end
    return result
  end
  function api.step()
    need(used and pipe~=nil and not closed,'PIPE_NOT_CONNECTED')
    return worker.step()
  end
  function api.close() worker.close(); return cleanup end
  function api.status() return cleanup,closed end
  return api
end
-- P0 data-only binding. This is not an OS or signature-verification interface.
-- Both expected and admitted data come from trusted offline test equipment.
-- No capability is invoked here; step() remains an explicit caller operation.
local activation_seen,activation_count={},0
function M.bind_activation_model(cap,binding,admitted,expected)
  local fields={schema=true,origin=true,state=true,native_activation=true,os_evidence=true,
    candidate_sha256=true,authorization_sha256=true,session_id=true,channel_id=true,epoch=true,nonce=true}
  local count=0
  need(type(admitted)=='table' and type(expected)=='table','P0_BINDING')
  for k,v in pairs(admitted) do
    need(fields[k] and expected[k]==v,'P0_BINDING'); count=count+1
  end
  need(count==11,'P0_BINDING')
  count=0; for k in pairs(expected) do need(fields[k],'P0_BINDING'); count=count+1 end
  need(count==11,'P0_BINDING')
  need(admitted.schema=='qsg.native-probe.activation.v1' and admitted.origin=='SYNTHETIC'
    and admitted.state=='RUN_PERMITTED' and admitted.os_evidence=='NOT_PROVEN'
    and admitted.native_activation=='BLOCKED_NATIVE_ACTIVATION_UNPROVEN','P0_SYNTHETIC_ONLY')
  need(sha(admitted.candidate_sha256) and sha(admitted.authorization_sha256)
    and sha(admitted.nonce),'P0_BINDING')
  need(type(binding)=='table' and binding.session_id==admitted.session_id
    and binding.channel_id==admitted.channel_id and binding.epoch==admitted.epoch,'P0_BINDING')
  need(ident(admitted.session_id) and ident(admitted.channel_id) and whole(admitted.epoch)
    and admitted.epoch>0 and admitted.epoch<=2147483647,'P0_BINDING')
  local key=admitted.authorization_sha256 .. ':' .. admitted.session_id .. ':'
    .. admitted.channel_id .. ':' .. string.format('%d',admitted.epoch) .. ':' .. admitted.nonce
  need(not activation_seen[key] and activation_count<20,'P0_ACTIVATION_REPLAY')
  activation_seen[key]=true; activation_count=activation_count+1
  return M.new_offline(cap,binding)
end
return M
