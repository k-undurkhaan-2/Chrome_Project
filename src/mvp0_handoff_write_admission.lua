-- H3-A1: pure review of supplied H2 bytes, never a write/restore capability.
-- No clock, files, process discovery, module loading or target-memory access.
local Admission = {SCHEMA_VERSION = 1}
local MAX_REPORT_BYTES = 16384
local REVIEWABLE = "SOURCE_REVIEWABLE_NOT_AUTHORIZED"

-- Exact Verify.render v1 sequence. output_filename is NOT a rendered H2 field.
local H2_FIELDS = {
  "verification_schema_version", "verification_kind", "verification_batch_id", "verification_case_id",
  "source_batch_id", "source_case_id", "source_session_id", "source_log_filename", "source_log_size_bytes",
  "source_summary_filename", "source_diagnostic_filename", "source_companion_filename",
  "source_consistency_status", "source_cryptographic_authentication", "candidate_address",
  "expected_search_float", "expected_search_pattern", "operator_attestation_status", "process_identity_basis",
  "process_identity_os_measured", "source_process_identity_status", "confirmed_at_utc", "observed_at_utc",
  "observed_float", "observed_integer_pattern", "observed_float_pattern", "candidate_value_consistent",
  "verification_status", "failure_class", "memory_read_attempts", "memory_write_attempts",
  "semantic_correctness_established", "ownership_established", "authorization_status", "handoff_write_ready",
  "write_ready", "write_attempted", "baseline_eligible", "independent_review_required", "next_action", "warning",
}
local H2_LIMITATIONS = {
  authorization_status="NOT_AUTHORIZED", handoff_write_ready="false", write_ready="false",
  write_attempted="false", memory_write_attempts="0", memory_read_attempts="2",
  source_cryptographic_authentication="false", process_identity_os_measured="false",
  semantic_correctness_established="false", ownership_established="false",
  independent_review_required="true", baseline_eligible="false",
  next_action="independent_owner_decision_in_future_phase",
  warning="NOT A WRITE GRANT; not a signed permission or WRITE/RESTORE receipt",
}
local SOURCE_FIELDS = {
  "verification_batch_id", "verification_case_id", "source_batch_id", "source_case_id", "source_session_id",
  "source_log_filename", "source_log_size_bytes", "source_summary_filename", "source_diagnostic_filename",
  "source_companion_filename", "candidate_address", "expected_search_float", "expected_search_pattern",
  "observed_float", "observed_integer_pattern", "observed_float_pattern", "confirmed_at_utc", "observed_at_utc",
}
local CONTEXT_FIELDS = {
  "review_record_id", "h2_report_sha256", "h1_companion_sha256", "h1_log_sha256",
  "h1_summary_sha256", "h1_diagnostic_sha256",
}
local RESULT_FIELDS = {
  "admission_schema_version", "admission_kind", "review_status", "failure_class",
  "verification_batch_id", "verification_case_id", "source_batch_id", "source_case_id", "source_session_id",
  "source_log_filename", "source_log_size_bytes", "source_summary_filename", "source_diagnostic_filename",
  "source_companion_filename", "candidate_address", "expected_search_float", "expected_search_pattern",
  "observed_float", "observed_integer_pattern", "observed_float_pattern", "confirmed_at_utc", "observed_at_utc",
  "source_memory_read_attempts", "source_consistency_status", "operator_attestation_status",
  "source_process_identity_status", "source_temporal_scope", "current_target_freshness",
  "review_record_id", "declared_h2_report_sha256", "declared_h1_companion_sha256", "declared_h1_log_sha256",
  "declared_h1_summary_sha256", "declared_h1_diagnostic_sha256", "review_context_binding_verified",
  "authorization_status", "write_ready", "handoff_write_ready", "write_attempted",
  "memory_read_attempts", "memory_write_attempts", "process_identity_os_measured",
  "source_cryptographic_authentication", "semantic_correctness_established", "ownership_established",
  "independent_review_required", "baseline_eligible", "next_action", "warning",
}

local function finite(n)
  return type(n) == "number" and n == n and math.abs(n) ~= math.huge
end

local function number_text(n)
  return type(n) == "number" and math.type(n) == "float" and string.format("%.17g", n) or tostring(n)
end

local function token(s)
  return type(s) == "string" and #s > 0 and #s <= 80
    and s:match("^[A-Za-z0-9][A-Za-z0-9_-]*$") ~= nil
    and not s:find("__", 1, true) and s:sub(-1) ~= "_" and s ~= "nil"
end

local function parse_report(text)
  if type(text) ~= "string" then return nil, "report_type_invalid" end
  if #text == 0 or #text > MAX_REPORT_BYTES then return nil, "report_size_invalid" end
  if text:sub(-2) ~= "\r\n" or text:gsub("\r\n", ""):find("[^ -~]") then
    return nil, "report_framing_invalid"
  end
  local fields, index = {}, 0
  -- Non-greedy captures preserve empty records, unlike [^\r\n]+.
  for line in text:gmatch("(.-)\r\n") do
    index = index + 1
    local key, value = line:match("^([a-z_]+)=(.+)$")
    if not key or key ~= H2_FIELDS[index] or fields[key] ~= nil then
      return nil, "report_fields_invalid"
    end
    fields[key] = value
  end
  if index ~= #H2_FIELDS then return nil, "report_fields_invalid" end
  return fields
end

local function hex(s, is_address)
  if not s:match("^0x[0-9A-F]+$") or #s > (is_address and 16 or 10) then return nil end
  local n = tonumber(s)
  if not n or math.type(n) ~= "integer" or n < (is_address and 1 or 0)
      or n > (is_address and 0x1FFFFFFFFFFFFF or 0xFFFFFFFF)
      or s ~= string.format(is_address and "0x%X" or "0x%08X", n) then return nil end
  return n
end

local function float_value(s, bits)
  if not s:match("^[+-]?[%d%.]+[eE]?[+-]?%d*$") then return false end
  -- tonumber('-0') is an integer zero; retain the producer's negative zero.
  local n = s == "-0" and -0.0 or tonumber(s)
  if not finite(n) or number_text(n) ~= s then return false end
  local expected = string.unpack("<f", string.pack("<I4", bits))
  if not finite(expected) or n ~= expected then return false end
  local ok, packed = pcall(string.pack, "<f", n)
  return ok and string.unpack("<I4", packed) == bits
end

-- Gregorian arithmetic only; this validates two historical claims, not now.
local function utc(s)
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

local function validate_source(f)
  if f.verification_schema_version ~= "1" or f.verification_kind ~= "readonly_candidate_verification" then
    return "h2_schema_invalid"
  end
  if f.verification_status ~= "VALUE_CONSISTENT_NOT_AUTHORIZED" or f.failure_class ~= "nil"
      or f.candidate_value_consistent ~= "true" or f.source_consistency_status ~= "consistent_local_evidence_only" then
    return "h2_not_successful"
  end
  for key, value in pairs(H2_LIMITATIONS) do
    if f[key] ~= value then return "h2_limitations_invalid" end
  end
  if f.operator_attestation_status ~= "operator_reconfirmed" or f.process_identity_basis ~= "operator_reconfirmed"
      or f.source_process_identity_status ~= "operator_recorded_at_h1_not_measured" then
    return "h2_attestation_invalid"
  end
  for _, key in ipairs({"source_batch_id", "source_case_id", "source_session_id",
      "verification_batch_id", "verification_case_id"}) do
    if not token(f[key]) then return "source_identity_invalid" end
  end
  if f.source_case_id:lower() == f.verification_case_id:lower()
      or f.source_batch_id:lower() == f.verification_batch_id:lower() then return "source_identity_reused" end
  local stem = f.source_batch_id .. "__" .. f.source_session_id .. "__" .. f.source_case_id
  if f.source_log_filename ~= stem .. "__no_probe_A.log"
      or f.source_companion_filename ~= stem .. "__single_handoff.txt"
      or f.source_summary_filename ~= f.source_batch_id .. "__summary.txt"
      or f.source_diagnostic_filename ~= f.source_batch_id .. "__diagnostic_diff.txt" then
    return "source_filename_mismatch"
  end
  local size = f.source_log_size_bytes
  if #size > 7 or not size:match("^[1-9][0-9]*$") or tonumber(size) > 2 * 1024 * 1024 then
    return "source_log_size_invalid"
  end
  if not hex(f.candidate_address, true) then return "candidate_address_invalid" end
  local bits = hex(f.expected_search_pattern, false)
  local integer_bits = hex(f.observed_integer_pattern, false)
  local float_bits = hex(f.observed_float_pattern, false)
  if not bits or not integer_bits or not float_bits then return "candidate_pattern_invalid" end
  if bits ~= integer_bits or bits ~= float_bits then return "candidate_pattern_mismatch" end
  if not float_value(f.expected_search_float, bits) or not float_value(f.observed_float, bits) then
    return "candidate_value_invalid"
  end
  local confirmed, observed = utc(f.confirmed_at_utc), utc(f.observed_at_utc)
  if not confirmed or not observed then return "source_time_invalid" end
  if observed < confirmed or observed - confirmed > 120 then return "source_interval_invalid" end
end

local function valid_context(context)
  if context == nil then return true end
  if type(context) ~= "table" or getmetatable(context) ~= nil then return false end
  local allowed = {}
  for _, key in ipairs(CONTEXT_FIELDS) do allowed[key] = true end
  -- next/rawget avoid invoking any caller-provided __pairs/__index callback.
  for key in next, context do if not allowed[key] then return false end end
  if not token(rawget(context, "review_record_id")) then return false end
  for i=2,#CONTEXT_FIELDS do
    local s = rawget(context, CONTEXT_FIELDS[i])
    if type(s) ~= "string" or #s ~= 64 or not s:match("^[0-9a-f]+$") then return false end
  end
  return true
end

local function base_result(failure)
  return {
    admission_schema_version=1, admission_kind="handoff_source_review",
    review_status="REJECTED", failure_class=failure,
    source_temporal_scope="historical_observation_only", current_target_freshness="not_evaluated",
    review_context_binding_verified=false, authorization_status="NOT_AUTHORIZED",
    write_ready=false, handoff_write_ready=false, write_attempted=false,
    memory_read_attempts=0, memory_write_attempts=0, process_identity_os_measured=false,
    source_cryptographic_authentication=false, semantic_correctness_established=false,
    ownership_established=false, independent_review_required=true, baseline_eligible=false,
    next_action="separate_owner_review_required",
    warning="NOT A WRITE GRANT; historical local evidence only; not a write or restore receipt",
  }
end

local function evaluate(text, context)
  local fields, failure = parse_report(text)
  if not fields then return base_result(failure) end
  failure = validate_source(fields)
  if failure then return base_result(failure) end
  if not valid_context(context) then return base_result("review_context_invalid") end
  local result = base_result(nil)
  result.review_status = REVIEWABLE
  -- Copy immutable strings exactly as rendered by H2, including numeric text.
  -- This is validated provenance, not independent authentication of its origin.
  for _, key in ipairs(SOURCE_FIELDS) do result[key] = fields[key] end
  result.source_memory_read_attempts = 2
  result.source_consistency_status = fields.source_consistency_status
  result.operator_attestation_status = fields.operator_attestation_status
  result.source_process_identity_status = fields.source_process_identity_status
  if context then
    result.review_record_id = context.review_record_id
    for i=2,#CONTEXT_FIELDS do
      local key = CONTEXT_FIELDS[i]
      result["declared_" .. key] = context[key]
    end
  end
  return result
end

-- A returned table is a review view, not a transferable capability. Keep a
-- private scalar snapshot so render cannot promote or inject a mutated view.
-- Weak keys avoid retaining abandoned results or storing unbounded report text.
local snapshots = setmetatable({}, {__mode="k"})
local function seal(result)
  local copy = {}
  for key, value in next, result do copy[key] = value end
  snapshots[result] = copy
  return result
end

function Admission.evaluate(report_text, review_context, ...)
  if select("#", ...) ~= 0 then return seal(base_result("unexpected_arguments")) end
  local ok, result = pcall(evaluate, report_text, review_context)
  return seal(ok and result or base_result("admission_exception"))
end

local function unchanged(result)
  if type(result) ~= "table" or getmetatable(result) ~= nil then return nil end
  local snapshot = snapshots[result]
  if not snapshot then return nil end
  for key, value in next, result do if rawget(snapshot, key) ~= value then return nil end end
  for key, value in next, snapshot do if rawget(result, key) ~= value then return nil end end
  return snapshot
end

function Admission.render(result, ...)
  local snapshot = select("#", ...) == 0 and unchanged(result) or nil
  snapshot = snapshot or base_result("invalid_result")
  local lines = {}
  for _, key in ipairs(RESULT_FIELDS) do lines[#lines + 1] = key .. "=" .. tostring(snapshot[key]) end
  return table.concat(lines, "\r\n") .. "\r\n"
end

return Admission
