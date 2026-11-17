-- H3-A2: synthetic-only transaction engine. No production adapter or runner.
-- The independently loaded restore sibling has its own source validator.
local Protocol = {}
local KIND = "write"
local DOMAIN = "h3-synthetic-tests-v1"
local AUTHORITY = "synthetic-authority"
local ACTION = "single_float32_" .. KIND .. "_once"
local MAX_BYTES = 16384
local SOURCE_FIELDS = {
  "source_batch_id", "source_case_id", "source_session_id",
  "h1_log_id", "h1_log_sha256", "h1_summary_id", "h1_summary_sha256",
  "h1_diagnostic_id", "h1_diagnostic_sha256", "h1_companion_id", "h1_companion_sha256",
  "h2_id", "h2_sha256", "a1_id", "a1_sha256",
}
local APPROVAL_FIELDS = {
  "schema", "source_kind", "environment", "request_id", "authority", "trust_domain", "action",
  "case_id", "session_id", "candidate_address", "current_float", "current_pattern", "target_float", "target_pattern",
  "pid", "process_created_utc", "executable", "architecture", "attachment_id", "scene_id",
  "issued_utc", "expires_utc", "max_elapsed_ms",
}
for _, key in ipairs(SOURCE_FIELDS) do APPROVAL_FIELDS[#APPROVAL_FIELDS+1] = key end
local RECORD_FIELDS = {
  "schema", "source_kind", "environment", "request_id", "action", "approval_sha256",
  "sources_sha256", "process_sha256", "scope_sha256", "candidate_address",
  "current_float", "current_pattern", "target_float", "target_pattern", "issued_utc", "expires_utc", "max_elapsed_ms",
  "reservation_sha256", "preparation_sha256", "state", "attempted", "api_result",
  "api_ok", "readback_ok", "execution_success", "failure_class", "last_checked_utc",
  "last_checked_monotonic_ms",
}
local PUBLIC_FIELDS = {
  "schema", "environment", "authorization_status", "operation", "status", "failure_class",
  "operation_failure_class", "persistence_failure_class",
  "reservation_status", "preparation_published", "write_attempted", "restore_attempted",
  "write_api_ok", "restore_api_ok", "write_readback_ok", "restore_readback_ok",
  "memory_confirmed", "execution_success", "receipt_published", "receipt_finalized", "api_result",
  "memory_read_attempts", "memory_write_attempts", "request_sha256", "receipt_sha256",
}
local IDENTITY_FIELDS = {"pid", "process_created_utc", "executable", "architecture", "attachment_id"}
local SOURCE_NAMES = {"h1_log", "h1_summary", "h1_diagnostic", "h1_companion", "h2", "a1"}

local function finite(n)
  return type(n) == "number" and n == n and math.abs(n) ~= math.huge
end
local function token(s)
  return type(s) == "string" and #s >= 1 and #s <= 64
    and s:match("^[a-z][a-z0-9-]*$") ~= nil and s:sub(-1) ~= "-"
end
local function source_id(s)
  return type(s) == "string" and #s >= 1 and #s <= 80
    and s:match("^[A-Za-z0-9][A-Za-z0-9_-]*$") ~= nil
    and not s:find("__", 1, true) and s:sub(-1) ~= "_" and s ~= "nil"
end
local function digest(s)
  return type(s) == "string" and #s == 64 and s:match("^[0-9a-f]+$") ~= nil
end
local function decimal(s, minimum, maximum)
  if type(s) ~= "string" or #s > 16 or not s:match("^%d+$") then return nil end
  local n = tonumber(s)
  if not n or math.type(n) ~= "integer" or n < minimum or n > maximum or tostring(n) ~= s then return nil end
  return n
end
local function hex(s, address)
  if type(s) ~= "string" or #s > (address and 16 or 10) or not s:match("^0x[0-9A-F]+$") then return nil end
  local n = tonumber(s)
  if not n or math.type(n) ~= "integer" or n < (address and 1 or 0)
      or n > (address and 0x1FFFFFFFFFFFFF or 0xFFFFFFFF)
      or string.format(address and "0x%X" or "0x%08X", n) ~= s then return nil end
  return n
end
local function float_from_bits(bits)
  if bits == nil then return nil end
  local n = string.unpack("<f", string.pack("<I4", bits))
  return finite(n) and n or nil
end
local function exact_float(text, bits)
  if type(text) ~= "string" or #text > 32 or bits == nil then return false end
  local n = text == "-0" and -0.0 or tonumber(text)
  if not finite(n) or string.format("%.17g", n) ~= text then return false end
  local ok, packed = pcall(string.pack,"<f",n)
  return ok and float_from_bits(bits) == n and string.unpack("<I4",packed) == bits
end
local function utc(s)
  if type(s) ~= "string" then return nil end
  local y,m,d,h,n,sec = s:match("^(%d%d%d%d)%-(%d%d)%-(%d%d)T(%d%d):(%d%d):(%d%d)Z$")
  y,m,d,h,n,sec = tonumber(y),tonumber(m),tonumber(d),tonumber(h),tonumber(n),tonumber(sec)
  if not y or y < 1970 or m < 1 or m > 12 or h > 23 or n > 59 or sec > 59 then return nil end
  local leap = y % 4 == 0 and (y % 100 ~= 0 or y % 400 == 0)
  local days = {31,leap and 29 or 28,31,30,31,30,31,31,30,31,30,31}
  if d < 1 or d > days[m] then return nil end
  local before = 365*(y-1970) + math.floor((y-1)/4)-492 - math.floor((y-1)/100)+19 + math.floor((y-1)/400)-4
  for i=1,m-1 do before = before + days[i] end
  return ((before+d-1)*24+h)*3600+n*60+sec
end
local function encode(fields, values)
  local lines = {}
  for _, key in ipairs(fields) do lines[#lines+1] = key .. "=" .. tostring(values[key]) .. "\r\n" end
  return table.concat(lines)
end
local function parse(bytes, fields)
  if type(bytes) ~= "string" or #bytes == 0 or #bytes > MAX_BYTES or bytes:sub(-2) ~= "\r\n"
      or bytes:gsub("\r\n", ""):find("[^ -~]") then return nil end
  local result, count = {}, 0
  for line in bytes:gmatch("(.-)\r\n") do
    count = count+1
    local key, value = line:match("^([a-z0-9_]+)=(.+)$")
    if key ~= fields[count] or not value or #value > 512 or result[key] ~= nil then return nil end
    result[key] = value
  end
  return count == #fields and result or nil
end
local function valid_approval(a)
  if not a or a.schema ~= "h3_" .. KIND .. "_approval_v1" or a.source_kind ~= "h3_single"
      or a.environment ~= "synthetic_only" or a.action ~= ACTION
      or a.authority ~= AUTHORITY or a.trust_domain ~= DOMAIN then return false end
  for _, key in ipairs({"request_id", "case_id", "session_id", "attachment_id", "scene_id"}) do
    if not token(a[key]) then return false end
  end
  if not hex(a.candidate_address, true) or float_from_bits(hex(a.current_pattern)) == nil
      or float_from_bits(hex(a.target_pattern)) == nil or a.current_pattern == a.target_pattern
      or not exact_float(a.current_float,hex(a.current_pattern))
      or not exact_float(a.target_float,hex(a.target_pattern)) then return false end
  if not decimal(a.pid, 1, 4294967295) or not utc(a.process_created_utc)
      or (a.architecture ~= "x64" and a.architecture ~= "x86") then return false end
  local path = a.executable
  if #path > 260 or not path:match("^[A-Z]:\\[^:]+$") or path:find("/", 1, true)
      or path:find("..", 1, true) or path:find("\\\\", 1, true) or path:sub(-1) == "\\"
      or path:find('[<>|?*"]') then return false end
  local issued, expires = utc(a.issued_utc), utc(a.expires_utc)
  if not issued or not expires or expires <= issued or expires-issued > 120
      or utc(a.process_created_utc) > issued or not decimal(a.max_elapsed_ms, 1, 120000) then return false end
  for _, key in ipairs(SOURCE_FIELDS) do
    if key:sub(-7) == "_sha256" then
      if not digest(a[key]) then return false end
    elseif not source_id(a[key]) then return false end
  end
  local ids = {}
  for _, name in ipairs(SOURCE_NAMES) do
    if ids[a[name .. "_id"]] then return false end
    ids[a[name .. "_id"]] = true
  end
  return true
end

-- These functions use only copied scalar values and captured dependency handles.
-- Trusted adapters receive bytes, never mutable internal transaction tables.
local function validate_sources(a, bytes, d, need, hash)
  local artifacts = {}
  for _, name in ipairs(SOURCE_NAMES) do
    local ok, body = pcall(d.read_evidence, a[name .. "_id"])
    need(ok and type(body) == "string" and #body > 0 and #body <= 2*1024*1024, "source_unavailable")
    need(hash(body) == a[name .. "_sha256"], "source_hash_mismatch")
    artifacts[#artifacts+1] = body
  end
  local binding = encode(SOURCE_FIELDS, a) .. "candidate_address=" .. a.candidate_address
    .. "\r\ncurrent_pattern=" .. a.current_pattern .. "\r\n"
  local ok, verified = pcall(d.revalidate_sources, bytes, table.unpack(artifacts))
  need(ok and verified == binding, "source_revalidation_failed")
  return hash(binding)
end

local snapshots = setmetatable({}, {__mode="k"})
local function public_result(failure)
  return {
    schema="h3_synthetic_result_v1", environment="synthetic_only",
    authorization_status="NOT_PRODUCTION_AUTHORIZED", operation=KIND, status="REJECTED",
    failure_class=failure or "nil", operation_failure_class=failure or "nil", persistence_failure_class="nil",
    reservation_status="not_attempted", preparation_published=false,
    write_attempted=false, restore_attempted=false, write_api_ok=false, restore_api_ok=false,
    write_readback_ok=false, restore_readback_ok=false, memory_confirmed=false, execution_success=false,
    receipt_published=false, receipt_finalized=false, api_result="not_called", memory_read_attempts=0, memory_write_attempts=0,
    request_sha256="nil", receipt_sha256="nil",
  }
end
local function seal(result)
  local snapshot = {}
  for key,value in next,result do snapshot[key]=value end
  snapshots[result] = snapshot
  return result
end
function Protocol.render(result, ...)
  local snapshot = type(result) == "table" and getmetatable(result) == nil and snapshots[result]
  local valid = type(snapshot) == "table" and select("#", ...) == 0
  if valid then
    for key,value in next,result do if snapshot[key] ~= value then valid=false end end
    for key,value in next,snapshot do if rawget(result,key) ~= value then valid=false end end
  end
  return encode(PUBLIC_FIELDS, valid and snapshot or public_result("invalid_result"))
end

local DEPENDENCIES = {
  "verify_approval", "sha256", "read_evidence", "revalidate_sources", "identity", "scene", "clock",
  "reserve", "publish", "read_record", "finalize_receipt", "read_finalized", "read_integer", "read_float", "write_float",
}
function Protocol.new_synthetic(dependencies, ...)
  if select("#", ...) ~= 0 or type(dependencies) ~= "table" or getmetatable(dependencies) ~= nil then
    return nil, "invalid_dependencies"
  end
  local d, allowed = {}, {environment=true}
  if rawget(dependencies,"environment") ~= "synthetic_only" then return nil,"synthetic_only" end
  for _,key in ipairs(DEPENDENCIES) do
    local value=rawget(dependencies,key)
    if type(value) ~= "function" then return nil,"invalid_dependencies" end
    d[key],allowed[key]=value,true
  end
  for key in next,dependencies do if not allowed[key] then return nil,"invalid_dependencies" end end
  local used, busy = {}, false
  local engine = {}
  function engine.run(approval_bytes, authentication, ...)
    if busy then return seal(public_result("engine_busy")) end
    if select("#", ...) ~= 0 then return seal(public_result("unexpected_arguments")) end
    busy=true
    local r=public_result()
    local t={failure=nil, reserved=false, api_result="not_called", last_utc="nil", last_mono="nil"}
    local function need(condition, failure)
      if not condition then t.failure=failure; error(nil,0) end
    end
    local function hash(bytes)
      local ok,value=pcall(d.sha256,bytes)
      need(ok and digest(value),"hash_unavailable")
      return value
    end
    local function identity(a)
      local ok,value=pcall(d.identity)
      need(ok and value == encode(IDENTITY_FIELDS,a)
        .. "attachment_verified=true\r\nmeasurement_basis=synthetic_os_measurement\r\n", "identity_mismatch")
      local scene_ok,scene=pcall(d.scene)
      need(scene_ok and scene == a.scene_id,"scene_mismatch")
    end
    local function clock(a)
      local ok,now,mono=pcall(d.clock)
      local seconds=utc(now)
      need(ok and seconds ~= nil and finite(mono) and math.type(mono) == "integer"
        and mono >= 0 and mono <= 0x1FFFFFFFFFFFFF,"clock_unavailable")
      need(seconds >= utc(a.issued_utc) and seconds < utc(a.expires_utc),"approval_not_current")
      if t.start_seconds then
        need(seconds >= t.previous_seconds and mono >= t.previous_mono,"clock_rollback")
        need(mono-t.start_mono <= tonumber(a.max_elapsed_ms),"monotonic_deadline")
        need(math.abs((seconds-t.start_seconds)*1000-(mono-t.start_mono)) <= 1000,"clock_discontinuity")
      else t.start_seconds,t.start_mono=seconds,mono end
      t.previous_seconds,t.previous_mono=seconds,mono
      t.last_utc,t.last_mono=now,tostring(mono)
    end
    local function context(a) identity(a); clock(a) end
    local function observe(a, expected)
      r.memory_read_attempts=r.memory_read_attempts+1
      local integer_ok,integer=pcall(d.read_integer,tonumber(a.candidate_address))
      r.memory_read_attempts=r.memory_read_attempts+1
      local float_ok,value=pcall(d.read_float,tonumber(a.candidate_address))
      if not integer_ok or not float_ok or not finite(integer) or integer % 1 ~= 0
          or integer < -0x80000000 or integer > 0xFFFFFFFF or not finite(value) then return false end
      local bits=integer < 0 and integer+0x100000000 or integer
      local packed_ok,packed=pcall(string.pack,"<f",value)
      if not packed_ok then return false end
      local exact=string.unpack("<f",packed)
      return finite(exact) and exact == value and string.unpack("<I4",packed) == bits and bits == hex(expected)
    end
    local function record(schema,state,failure)
      local a=t.approval
      local values={schema=schema,source_kind="h3_single",environment="synthetic_only",request_id=a.request_id,
        action=ACTION,approval_sha256=t.approval_hash,sources_sha256=t.sources_hash,process_sha256=t.process_hash,
        scope_sha256=t.scope_hash,candidate_address=a.candidate_address,current_float=a.current_float,current_pattern=a.current_pattern,
        target_float=a.target_float,target_pattern=a.target_pattern,issued_utc=a.issued_utc,expires_utc=a.expires_utc,max_elapsed_ms=a.max_elapsed_ms,
        reservation_sha256=t.reservation_hash or "nil",preparation_sha256=t.preparation_hash or "nil",state=state,
        attempted=r[KIND .. "_attempted"],api_result=t.api_result,api_ok=r[KIND .. "_api_ok"],
        readback_ok=r[KIND .. "_readback_ok"],execution_success=r.memory_confirmed,
        failure_class=failure or "nil",last_checked_utc=t.last_utc,last_checked_monotonic_ms=t.last_mono}
      return encode(RECORD_FIELDS,values)
    end
    local function publish(kind,bytes,primitive)
      local ok,done=pcall(primitive,t.approval.request_id,kind,bytes)
      need(ok and done == true,kind .. "_persistence_failed")
      local read_ok,actual=pcall(d.read_record,t.approval.request_id,kind)
      need(read_ok and actual == bytes,kind .. "_readback_failed")
      return hash(bytes)
    end
    local ok=pcall(function()
      local a=parse(approval_bytes,APPROVAL_FIELDS)
      need(valid_approval(a),"approval_invalid")
      need(type(authentication) == "string" and #authentication > 0 and #authentication <= 256,"authentication_invalid")
      t.approval=a
      clock(a)
      local verified,exact,domain,authority=pcall(d.verify_approval,approval_bytes,authentication,ACTION)
      need(verified and exact == approval_bytes and domain == DOMAIN and authority == AUTHORITY,"approval_untrusted")
      t.approval_hash=hash(approval_bytes)
      r.request_sha256=hash(a.request_id)
      t.sources_hash=validate_sources(a,approval_bytes,d,need,hash)
      t.process_hash=hash(encode(IDENTITY_FIELDS,a))
      t.scope_hash=hash("case_id=" .. a.case_id .. "\r\nsession_id=" .. a.session_id .. "\r\nscene_id=" .. a.scene_id .. "\r\n")
      context(a)
      need(not used[a.request_id],"request_reused")
      used[a.request_id]=true -- Never clear, including failed or uncertain reservation.
      r.reservation_status="uncertain"
      t.reservation_hash=publish("reservation",record("h3_operation_reservation_v1","RESERVED"),d.reserve)
      t.reserved=true
      r.reservation_status="consumed"
      need(observe(a,a.current_pattern),"initial_value_mismatch")
      t.preparation_hash=publish("preparation",record("h3_single_" .. KIND .. "_preparation_v1","PREPARED"),d.publish)
      r.preparation_published=true
      context(a)
      need(observe(a,a.current_pattern),"prewrite_value_mismatch")
      context(a) -- Reads and all durable work are included in the final age/identity check.
      r[KIND .. "_attempted"],r.memory_write_attempts=true,1
      local api_ok,api_value=pcall(d.write_float,tonumber(a.candidate_address),float_from_bits(hex(a.target_pattern)))
      t.api_result=not api_ok and "exception" or (api_value == true and "true"
        or (api_value == false and "false" or (api_value == nil and "nil" or "nonboolean")))
      r.api_result=t.api_result
      r[KIND .. "_api_ok"]=api_ok and api_value == true
      context(a) -- Do not read a recycled/detached process after an uncertain write.
      r[KIND .. "_readback_ok"]=observe(a,a.target_pattern)
      clock(a) -- Slow readback is not allowed to silently exceed the approved window.
      need(r[KIND .. "_api_ok"],"mutation_api_" .. t.api_result)
      need(r[KIND .. "_readback_ok"],"readback_mismatch")
      r.memory_confirmed=true
    end)
    if not ok and not t.failure then t.failure="protocol_exception" end
    r.failure_class=t.failure or "nil"
    r.operation_failure_class=r.failure_class
    if t.reserved then
      local original_failure=t.failure
      local completed=pcall(function()
        local bytes=record("h3_single_" .. KIND .. "_receipt_v1",r.memory_confirmed and "CONFIRMED" or "UNCONFIRMED",original_failure)
        r.receipt_sha256=publish("receipt",bytes,d.publish)
      end)
      r.receipt_published=completed
      if not completed then
        r.persistence_failure_class=t.failure or "receipt_exception"
        r.failure_class=r.persistence_failure_class
      end
    end
    if r.memory_confirmed and r.receipt_published then
      local finalized=pcall(function()
        local final_ok,done=pcall(d.finalize_receipt,t.approval.request_id,r.receipt_sha256)
        need(final_ok and done == true,"receipt_finalization_failed")
        local read_ok,body=pcall(d.read_finalized,t.approval.request_id)
        need(read_ok and type(body) == "string" and hash(body) == r.receipt_sha256,"finalization_readback_failed")
      end)
      r.receipt_finalized=finalized
      if not finalized then
        r.persistence_failure_class=t.failure or "finalization_exception"
        r.failure_class=r.persistence_failure_class
      end
    end
    r.execution_success=r.memory_confirmed and r.receipt_published and r.receipt_finalized
    r.status=r.execution_success and "SYNTHETIC_CONFIRMED"
      or ((r[KIND .. "_attempted"] or r.reservation_status == "uncertain") and "UNCERTAIN" or "REJECTED")
    busy=false
    return seal(r)
  end
  return engine
end
return Protocol
