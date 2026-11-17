-- H2: local evidence consistency and one read-only candidate observation.
-- Dependencies are injected. No filesystem, process discovery, collector,
-- executor, Write Arm, restore or memory-write API is accessed here.
local Verify = {SCHEMA_VERSION = 1}
local ROOT = [[D:\armedforces.io-v2\log\auto_output]]
local LIMIT = 2 * 1024 * 1024
local COMPANION_LIMIT = 16384

local function finite(n)
  return type(n) == "number" and n == n and math.abs(n) ~= math.huge
end

local function integer(n, low, high)
  return finite(n) and n % 1 == 0 and n >= low and n <= high
end

local function token(s)
  return type(s) == "string" and #s > 0 and #s <= 80
    and s:match("^[A-Za-z0-9][A-Za-z0-9_-]*$") ~= nil
    and not s:find("__", 1, true) and s:sub(-1) ~= "_" and s ~= "nil"
end

local function keys_only(t, names)
  if type(t) ~= "table" or getmetatable(t) ~= nil then return false end
  local allowed = {}
  for name in names:gmatch("%S+") do allowed[name] = true end
  for name in pairs(t) do if not allowed[name] then return false end end
  return true
end

local function numeric(s)
  if type(s) ~= "string" or not s:match("^[+-]?[%d%.]+[eE]?[+-]?%d*$") then return nil end
  local n = s == "-0" and -0.0 or tonumber(s)
  return finite(n) and n or nil
end

local function float_bits(n)
  if not finite(n) then return nil end
  local ok, bytes = pcall(string.pack, "<f", n)
  if not ok or not finite(string.unpack("<f", bytes)) then return nil end
  return string.unpack("<I4", bytes)
end

local function hex(s, address)
  if type(s) ~= "string" or not s:match("^0x[0-9A-F]+$") then return nil end
  local n = tonumber(s)
  if not integer(n, address and 1 or 0, address and 0x1FFFFFFFFFFFFF or 0xFFFFFFFF) then return nil end
  if s ~= string.format(address and "0x%X" or "0x%08X", n) then return nil end
  return n
end

local function number_text(n)
  return type(n) == "number" and math.type(n) == "float" and string.format("%.17g", n) or tostring(n)
end

local FIXED = {
  handoff_schema_version = "1", handoff_kind = "single_candidate_proposal",
  authorization_status = "NOT_AUTHORIZED", handoff_write_ready = "false",
  write_attempted = "false", baseline_eligible = "false", source_mode = "no_probe_A",
  source_validation_profile = "single", run_valid = "true", failure_class = "nil",
  error = "nil", probe_full_foundlist = "false", candidate_rank = "1",
  operator_process_identity_verified = "false", independent_review_required = "true",
  session_identity_note = "internal session label does not identify a Windows process instance",
  next_action = "independent_candidate_and_process_verification",
  warning = "NOT A WRITE GRANT; no live write can be triggered from this artifact; rank and confidence do not prove correctness",
  authentication_note = "not cryptographically authenticated",
}
local FIELDS = {
  "handoff_schema_version", "handoff_kind", "authorization_status", "handoff_write_ready",
  "write_attempted", "baseline_eligible", "source_batch_id", "source_case_id", "source_session_id",
  "source_mode", "source_validation_profile", "source_log_filename", "source_log_size_bytes",
  "run_valid", "failure_class", "error", "probe_full_foundlist", "candidate_rank", "candidate_address",
  "candidate_count", "best_score", "second_score", "score_gap", "confidence", "recommendation",
  "search_target_float", "search_target_pattern", "operator_process_identity_verified",
  "session_identity_note", "independent_review_required", "next_action", "warning", "authentication_note",
}

local function crlf(text)
  return type(text) == "string" and #text > 0 and not text:find("%z")
    and not text:gsub("\r\n", ""):find("[\r\n]")
end

local function companion(text, source, log_name)
  if not crlf(text) or #text > COMPANION_LIMIT or text:sub(-2) ~= "\r\n" then
    return nil, "source_companion_malformed"
  end
  local values, expected, order = {}, {}, {}
  for _, key in ipairs(FIELDS) do expected[key] = true end
  for line in text:gmatch("([^\r\n]+)\r\n") do
    local key, value = line:match("^([a-z_]+)=(.+)$")
    if not key or not expected[key] or values[key] ~= nil then return nil, "source_companion_fields" end
    values[key] = value
  end
  for _, key in ipairs(FIELDS) do
    if values[key] == nil and key ~= "confidence" and key ~= "recommendation" then
      return nil, "source_companion_fields"
    end
    if values[key] ~= nil then order[#order + 1] = key .. "=" .. values[key] end
  end
  if table.concat(order, "\r\n") .. "\r\n" ~= text then return nil, "source_companion_fields" end
  for key, value in pairs(FIXED) do
    if values[key] ~= value then return nil, "source_non_authorizing_declaration" end
  end
  for _, key in ipairs({"batch_id", "case_id", "session_id"}) do
    if values["source_" .. key] ~= source[key] then return nil, "source_identity_mismatch" end
  end
  if values.source_log_filename ~= log_name then return nil, "source_identity_mismatch" end
  if values.confidence and not ({HIGH=true, MEDIUM=true, LOW=true})[values.confidence] then
    return nil, "source_enum_invalid"
  end
  if values.recommendation and not ({ACCEPT=true, REVIEW=true, REJECT=true})[values.recommendation] then
    return nil, "source_enum_invalid"
  end
  values.address = hex(values.candidate_address, true)
  if not values.address then return nil, "source_address_invalid" end
  for _, key in ipairs({"source_log_size_bytes", "candidate_count", "best_score", "second_score",
      "score_gap", "search_target_float"}) do
    local value = values[key]
    if value ~= "nil" then
      local n = numeric(value)
      if n == nil or number_text(n) ~= value then return nil, "source_numeric_invalid" end
      values[key .. "_number"] = n
    end
  end
  local size, count = values.source_log_size_bytes_number, values.candidate_count_number
  local best, second, gap = values.best_score_number, values.second_score_number, values.score_gap_number
  if not integer(size, 1, LIMIT) or not integer(count, 1, 100000) or best == nil
      or (count == 1 and second ~= nil) or (count > 1 and second == nil)
      or (second ~= nil and second > best)
      or (gap ~= nil and (gap ~= (second and best - second or best) or (second and gap < 0))) then
    return nil, "source_scores_invalid"
  end
  local bits = values.search_target_pattern ~= "nil" and hex(values.search_target_pattern, false) or nil
  local float = values.search_target_float_number
  if (values.search_target_pattern ~= "nil" and bits == nil)
      or (float ~= nil and float_bits(float) == nil)
      or (bits ~= nil and not finite(string.unpack("<f", string.pack("<I4", bits))))
      or (float ~= nil and bits ~= nil and float_bits(float) ~= bits) then
    return nil, "source_search_pattern_invalid"
  end
  values.expected_bits = bits or float_bits(float)
  if values.expected_bits == nil then return nil, "source_search_value_missing" end
  return values
end

-- Legacy documents repeat fields only in distinct sections. The summary and
-- diagnostic embed execution fields without a heading; split at their marker.
local function document(text, title)
  if not crlf(text) or #text > LIMIT then return nil end
  local sections, current = {}, nil
  for line in (text .. "\r\n"):gmatch("(.-)\r\n") do
    if line ~= "" then
      if line:match("^=== .+ ===$") or line:match("^%-%-%- .+ %-%-%-$") or line == "[no_probe_A]" then
        if sections[line] then return nil end
        current = line; sections[current] = {}
      else
        local key, value = line:match("^([a-zA-Z0-9_]+)%s+= (.+)$")
        if not current or not key then return nil end
        if key == "execution_enabled" and current ~= "=== value_execution ===" then
          current = current .. "/execution"
          if sections[current] then return nil end
          sections[current] = {}
        end
        if sections[current][key] ~= nil then return nil end
        sections[current][key] = value
      end
    end
  end
  if text:sub(1, #title + 2) ~= title .. "\r\n" then return nil end
  return sections
end

local function eq_fields(fields, expected)
  if type(fields) ~= "table" then return false end
  for key, value in pairs(expected) do if fields[key] ~= value then return false end end
  return true
end

-- H1's legacy reports use tostring (fewer digits than the companion). Compare
-- that exact rendering numerically, with no score tolerance or new threshold.
local function legacy_number(text, n)
  if n == nil then return text == "nil" end
  return numeric(text) == tonumber(tostring(n))
end

local function search_fields(fields, c)
  if not fields then return false end
  local pattern = c.search_target_pattern == "nil" and "nil" or string.format("0x%X", c.expected_bits)
  return fields.target_value_pattern == pattern
    and legacy_number(fields.target_value_float, c.search_target_float_number)
end

local SAFE_EXECUTION = {
  execution_enabled="false", execution_mode="disabled", write_enabled="false",
  execution_confirm_ok="false", execution_arm_valid="false", execution_addr="nil",
  execution_preconditions_ok="false", execution_identity_ok="false", write_ready="false",
  execution_success="false", write_attempted="false", write_api_ok="false", write_ok="false",
  restore_attempted="false", restore_write_ok="false", restore_readback_ok="false",
  readback_ok="false", rollback_available="false",
}
local SAFE_RUN = {run_valid="true", failure_class="nil", error="nil", collector_empty="false"}
local SINGLE = {validation_profile="single", baseline_eligible="false", profile_note="single_pass_detect_only",
  skipped_modes="with_probe, no_probe_B, stable_no_probe_intersection"}
local PUBLICATION = {
  single_handoff_status="VALIDATED_PENDING_OUTPUT", single_handoff_failure_class="nil",
  single_source_log_failure_class="nil",
  single_handoff_publication_note="publication follows both batch reports; check console and companion file",
}

local function trace_evidence(body, c, source)
  -- LF is legitimate only inside H1's embedded ranker report, never in the
  -- surrounding CRLF envelope or in the companion. Parse the summary and each
  -- ranked object, rejecting duplicate fields and incomplete rank lists.
  if body:find("\r") or body:find("%z") or body:sub(-1) ~= "\n" then return false end
  local summary, recommendation, candidates = {}, {}, {}
  local section, row = summary, nil
  for line in (body .. "\n"):gmatch("([^\n]*)\n") do
    local rank = line:match("^%-%-%- Candidate #(%d+) %-%-%-$")
    if rank then
      if tonumber(rank) ~= #candidates + 1 then return false end
      row = {}; candidates[#candidates + 1] = row; section = row
    elseif line == "=== Recommendation ===" then section = recommendation
    elseif line ~= "" and not line:match("^=+$") and line ~= "=== Session Summary ===" then
      local key, value
      if row then key, value = line:match("^(.-)%s*= (.*)$")
      else key, value = line:match("^(.-)%s*: (.*)$") end
      if not key or section[key] ~= nil then return false end
      section[key] = value
    end
  end
  if not eq_fields(summary, {Session=source.session_id, Mode="no_probe", Candidates=c.candidate_count,
      ["Best candidate"]=c.candidate_address, Confidence=c.confidence or "nil"})
      or not legacy_number(summary["Best score"], c.best_score_number)
      or not legacy_number(summary["Score gap"], c.score_gap_number)
      or #candidates ~= c.candidate_count_number then return false end
  if c.second_score_number ~= nil and not legacy_number(summary["Second score"], c.second_score_number) then return false end
  if summary["Target value pattern"] ~= c.search_target_pattern
      or (c.search_target_float_number ~= nil and not legacy_number(summary["Target value float"], c.search_target_float_number)) then return false end
  if c.recommendation ~= nil and not eq_fields(recommendation, {
      Recommendation=c.recommendation, Confidence=c.confidence or "nil",
      ["Recommended value addr"]=c.candidate_address}) then return false end
  if c.recommendation ~= nil and not legacy_number(recommendation["Recommended score"], c.best_score_number) then return false end
  local seen, previous = {}, nil
  for i, item in ipairs(candidates) do
    local addr, score = hex(item.value_addr, true), numeric(item.score)
    if not addr or seen[addr] or not score or (previous and score > previous) or item.negative == nil
        or item.rank_position ~= tostring(i) or not legacy_number(item.final_score, score) then return false end
    if i == 1 and (item.value_addr ~= c.candidate_address or not legacy_number(item.score, c.best_score_number)) then return false end
    if i == 2 and not legacy_number(item.score, c.second_score_number) then return false end
    seen[addr], previous = true, score
  end
  return true
end

local function reconcile(evidence, c, source, names)
  local log, trace = evidence.log, nil
  if log:sub(-2) ~= "\r\n" then return "source_report_malformed" end
  if log:find("=== report_text ===\r\n", 1, true) then
    local prefix, body, suffix = log:match("^(.-)=== report_text ===\r\n(.-)\r\n(=== single_detect_only ===\r\n.*)$")
    if not prefix or not trace_evidence(body, c, source) then return "source_trace_conflict" end
    log, trace = prefix .. suffix, true
    -- Empty truth logs are emitted as a literal nil, not a key/value field.
    log = log:gsub("=== truth_probe_logs ===\r\nnil\r\n", "=== truth_probe_logs ===\r\n")
  end
  local l = document(log, trace and "=== run_config ===" or "=== compact_report ===")
  local s = document(evidence.summary, "=== Batch Summary ===")
  local d = document(evidence.diagnostic, "=== Diagnostic Sandwich Diff ===")
  if not l or not s or not d then return "source_report_malformed" end
  local section = "--- " .. source.session_id .. " / no_probe_A ---"
  local group = "--- " .. source.session_id .. "::" .. source.case_id .. " ---"
  local sc, se, dg, de = s[section], s[section .. "/execution"], d[group], d["[no_probe_A]/execution"]
  local lc = l[trace and "=== run_config ===" or "=== compact_report ==="]
  local stats = trace and l["=== collector_stats ==="] or lc
  local le = l["=== value_execution ==="]
  -- Only one source case/mode: reject colliding multi-case sections even if a
  -- matching section happens to exist. Never use last-key/last-case wins.
  local allowed_s = {["=== Batch Summary ==="]=true, [section]=true, [section .. "/execution"]=true, [group]=true,
    ["=== Delayed Snapshot Intersection Summary ==="]=true, ["=== single_handoff_validation ==="]=true}
  local allowed_d = {["=== Diagnostic Sandwich Diff ==="]=true, [group]=true, ["[no_probe_A]"]=true,
    ["[no_probe_A]/execution"]=true, ["=== single_handoff_validation ==="]=true}
  local allowed_l = {["=== single_detect_only ==="]=true, ["=== value_execution ==="]=true,
    ["=== report_render_policy ==="]=true, ["=== selected_quota_debug ==="]=true}
  for _, key in ipairs(trace and {"run_config", "collector_stats", "truth_probe_flags", "extra_probe_debug",
      "truth_probe_logs", "known_true_debug"} or {"compact_report"}) do allowed_l["=== " .. key .. " ==="] = true end
  for key in pairs(s) do if not allowed_s[key] then return "source_identity_ambiguous" end end
  for key in pairs(d) do if not allowed_d[key] then return "source_identity_ambiguous" end end
  for key in pairs(l) do if not allowed_l[key] then return "source_identity_ambiguous" end end
  for _, pair in ipairs({{s,"=== Batch Summary ==="}, {d,"=== Diagnostic Sandwich Diff ==="}}) do
    if not eq_fields(pair[1][pair[2]], {batch_id=source.batch_id, output_dir=ROOT}) then return "source_identity_mismatch" end
    local publication = pair[1]["=== single_handoff_validation ==="]
    if not eq_fields(publication, PUBLICATION) or publication.single_source_log_filename ~= names.log then
      return "source_publication_incomplete"
    end
  end
  if not eq_fields(lc, {case_id=source.case_id, session_id=source.session_id, mode="no_probe_A"})
      or not eq_fields(sc, {case_id=source.case_id, probe_full_foundlist="false"})
      or not eq_fields(se, {log_path=ROOT .. "\\" .. names.log, confidence=c.confidence or "nil"})
      or not eq_fields(l["=== single_detect_only ==="], {mode="no_probe_A", probe_full_foundlist="false"}) then
    return "source_identity_mismatch"
  end
  for _, fields in ipairs({lc, sc, dg, l["=== single_detect_only ==="] or {}}) do
    if not eq_fields(fields, SINGLE) then return "source_not_single" end
  end
  for _, fields in ipairs({stats or {}, sc or {}, dg or {}, s[group] or {}}) do
    if not eq_fields(fields, SAFE_RUN) then return "source_run_invalid" end
  end
  for _, fields in ipairs({le or {}, se or {}, de or {}}) do
    if not eq_fields(fields, SAFE_EXECUTION) then return "source_execution_conflict" end
  end
  for key, value in pairs(le) do
    if se[key] ~= value or de[key] ~= value then return "source_execution_conflict" end
  end
  if not eq_fields(le, {executor_version="guarded_write_v3", execution_failure_class="nil"})
      or not ({float=true, integer=true, bytes=true})[le.write_method]
      or not ({stable_intersection_best_candidate=true, best_candidate=true, final_best_candidate=true,
        restore_source_batch_execution_addr=true})[le.execution_addr_source] then return "source_execution_conflict" end
  for _, fields in ipairs({sc, dg, s[group]}) do
    if not eq_fields(fields, {recommendation="nil", empty_modes="none"}) then return "source_run_invalid" end
  end
  if not trace and lc.recommendation ~= "nil" then return "source_run_invalid" end
  local policy = l["=== report_render_policy ==="]
  if not eq_fields(policy, {compact_report_enabled=trace and "false" or "true",
      skipped_verbose_report_sections=trace and "none" or "truth_probe_logs, report_text",
      verbose_report_section_count=trace and "2" or "0"}) then return "source_report_malformed" end
  for _, fields in ipairs({lc, sc, dg, le, se, de}) do
    if not search_fields(fields, c) then return "source_search_conflict" end
  end
  if #evidence.log ~= c.source_log_size_bytes_number
      or not legacy_number(sc.log_size_bytes, #evidence.log)
      or not legacy_number(de.log_size_bytes, #evidence.log) then return "source_size_mismatch" end
  local da = d["[no_probe_A]"]
  if not da or da.best_candidate ~= c.candidate_address or sc.best_candidate ~= c.candidate_address
      or (not trace and lc.best_candidate ~= c.candidate_address) then return "source_candidate_conflict" end
  for _, fields in ipairs(trace and {sc} or {sc, lc}) do
    for _, key in ipairs({"best_score", "second_score", "score_gap"}) do
      if not legacy_number(fields[key], c[key .. "_number"]) then return "source_score_conflict" end
    end
  end
  for _, fields in ipairs({sc, stats, da}) do
    if not legacy_number(fields.selected_count, c.candidate_count_number) then return "source_count_conflict" end
  end
  for _, key in ipairs({"raw_count", "unique_count", "filtered_count"}) do
    local n = numeric(stats[key])
    if not integer(n, c.candidate_count_number, 0x1FFFFFFFFFFFFF)
        or not legacy_number(da[key], n)
        or (key == "filtered_count" and not legacy_number(sc[key], n)) then return "source_count_conflict" end
  end
  if not ({basic=true, debug=true, trace=true})[lc.diagnostic_level]
      or lc.diagnostic_level ~= sc.diagnostic_level or lc.diagnostic_level ~= dg.diagnostic_level then
    return "source_enum_invalid"
  end
  return nil
end

-- Gregorian UTC arithmetic avoids host-local timezone/DST conversion. Time is
-- only an expiry check on an operator claim, not proof of process identity.
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

local function process(p, requested)
  if not keys_only(p, "process_name executable pid started_at_utc scene") then return false end
  if not integer(p.pid, 1, 0xFFFFFFFF) or not utc(p.started_at_utc) or not token(p.scene)
      or p.process_name ~= requested or type(p.executable) ~= "string" or #p.executable > 260
      or not p.executable:match("^[A-Za-z]:\\[^\r\n]+$") or p.executable:find('[%c<>"|?*]')
      or p.executable:sub(3):find(":", 1, true) or p.executable:find("/", 1, true) then return false end
  for part in p.executable:sub(4):gmatch("[^\\]+") do
    if part == "." or part == ".." or part:match("[%. ]$") then return false end
  end
  return not p.executable:find("\\\\", 1, true)
    and p.executable:match("([^\\]+)$") == requested
end

local function attestation(a, request, now)
  if not keys_only(a, "identity_basis permitted_disposable_environment h1_did_not_measure_identity source_identity_status continuity_confirmed continuity_basis confirmed_at_utc source_recorded_at_utc verification_case_id source_batch_id source_case_id source_session_id requested_process_name source current") then
    return "operator_attestation_missing_or_invalid"
  end
  if a.identity_basis ~= "operator_reconfirmed" or a.h1_did_not_measure_identity ~= true then return "operator_identity_claim_invalid" end
  if a.source_identity_status ~= "operator_recorded_at_h1" or a.source == nil then return "source_process_identity_unavailable" end
  if a.permitted_disposable_environment ~= true or a.continuity_confirmed ~= true
      or type(a.continuity_basis) ~= "string" or #a.continuity_basis < 12 or #a.continuity_basis > 512
      or a.continuity_basis:find("[%c]") or not a.continuity_basis:match("%S") then return "operator_continuity_unconfirmed" end
  if a.verification_case_id ~= request.case_id then return "operator_binding_mismatch" end
  for _, key in ipairs({"batch_id", "case_id", "session_id"}) do
    if a["source_" .. key] ~= request.source[key] then return "operator_binding_mismatch" end
  end
  if type(a.requested_process_name) ~= "string" or #a.requested_process_name > 100
      or not a.requested_process_name:match("^[A-Za-z0-9_. -]+%.exe$")
      or not process(a.source, a.requested_process_name) or not process(a.current, a.requested_process_name) then
    return "operator_process_context_invalid"
  end
  for _, key in ipairs({"pid", "started_at_utc", "executable", "scene", "process_name"}) do
    if a.source[key] ~= a.current[key] then return "operator_process_changed" end
  end
  local current, confirmed, recorded = utc(now), utc(a.confirmed_at_utc), utc(a.source_recorded_at_utc)
  if not current or not confirmed or not recorded or confirmed > current or current - confirmed > 120
      or recorded > confirmed or utc(a.source.started_at_utc) > recorded then return "operator_attestation_stale_or_invalid_time" end
  return nil
end

local function config_failure(cfg, raw)
  if cfg.handoff_verify_only ~= true or cfg.validation_profile ~= "single"
      or cfg.execution_mode ~= "disabled" or cfg.write_enabled ~= false
      or cfg.single_handoff_enabled == true or cfg.execution_addr_source == "restore_source_batch_execution_addr" then
    return "verification_requires_single_readonly"
  end
  for _, input in ipairs({cfg, raw or {}}) do
    for key, value in pairs(input) do
      if type(key) == "string" and value ~= nil and (key:match("^restore_")
          or key == "execution_confirm" or key == "execution_write_request_id"
          or key == "execution_armed_at_utc" or key == "execution_arm_expires_at_utc"
          or key == "write_value_float" or key == "write_value_pattern") then return "verification_mixed_operation" end
    end
  end
  if type(raw) == "table" and (raw.modes ~= nil or raw.execution_mode ~= "disabled"
      or raw.write_enabled ~= false or raw.validation_profile ~= "single") then return "verification_mixed_operation" end
  return nil
end

local function reject(r, failure)
  r.verification_status, r.failure_class = "REJECTED", failure
  return r
end

function Verify.run(cfg, raw, deps)
  local r = {
    verification_schema_version=1, verification_kind="readonly_candidate_verification",
    verification_status="REJECTED", candidate_value_consistent="not_evaluated",
    source_consistency_status="not_evaluated", operator_attestation_status="not_evaluated",
    process_identity_basis="not_measured", source_process_identity_status="not_evaluated",
    source_cryptographic_authentication=false, process_identity_os_measured=false,
    semantic_correctness_established=false, ownership_established=false,
    authorization_status="NOT_AUTHORIZED", handoff_write_ready=false, write_ready=false,
    write_attempted=false, baseline_eligible=false, memory_write_attempts=0, memory_read_attempts=0,
    independent_review_required=true, next_action="independent_owner_decision_in_future_phase",
    warning="NOT A WRITE GRANT; not a signed permission or WRITE/RESTORE receipt",
  }
  local request = type(cfg) == "table" and cfg.handoff_verify_request or nil
  if type(deps) ~= "table" or not token(deps.batch_id) or not keys_only(request, "case_id source attestation")
      or not token(request.case_id) or not keys_only(request.source, "batch_id case_id session_id") then
    return reject(r, "verification_request_invalid")
  end
  local source = request.source
  for _, key in ipairs({"batch_id", "case_id", "session_id"}) do
    if not token(source[key]) then return reject(r, "source_token_invalid") end
    r["source_" .. key] = source[key]
  end
  if request.case_id:lower() == source.case_id:lower() or deps.batch_id:lower() == source.batch_id:lower() then
    return reject(r, "verification_identity_reused")
  end
  r.verification_batch_id, r.verification_case_id = deps.batch_id, request.case_id
  r.output_filename = deps.batch_id .. "__" .. request.case_id .. "__handoff_verification.txt"
  local failure = config_failure(cfg, raw)
  if failure then return reject(r, failure) end
  local stem = source.batch_id .. "__" .. source.session_id .. "__" .. source.case_id
  local names = {log=stem .. "__no_probe_A.log", summary=source.batch_id .. "__summary.txt",
    diagnostic=source.batch_id .. "__diagnostic_diff.txt", companion=stem .. "__single_handoff.txt"}
  if type(deps.read_source) ~= "function" then return reject(r, "source_api_unavailable") end
  local evidence = {}
  for _, key in ipairs({"companion", "log", "summary", "diagnostic"}) do
    local limit = key == "companion" and COMPANION_LIMIT or LIMIT
    local ok, text, why = pcall(deps.read_source, names[key], limit)
    if not ok then return reject(r, "source_io_exception") end
    if type(text) ~= "string" then
      local allowed = {source_missing=true, source_unreadable=true, source_io_failed=true, source_io_exception=true, source_oversized=true}
      return reject(r, allowed[why] and why or "source_io_failed")
    end
    if #text > limit then return reject(r, "source_oversized") end
    if #text == 0 then return reject(r, "source_empty") end
    evidence[key] = text
  end
  local c
  c, failure = companion(evidence.companion, source, names.log)
  if not c then return reject(r, failure) end
  failure = reconcile(evidence, c, source, names)
  if failure then return reject(r, failure) end
  r.source_consistency_status = "consistent_local_evidence_only"
  r.source_log_filename, r.source_log_size_bytes = names.log, #evidence.log
  r.source_summary_filename, r.source_diagnostic_filename, r.source_companion_filename = names.summary, names.diagnostic, names.companion
  r.candidate_address, r.expected_search_pattern = c.candidate_address, string.format("0x%08X", c.expected_bits)
  r.expected_search_float = string.unpack("<f", string.pack("<I4", c.expected_bits))
  local ok, now = pcall(function() return deps.now_utc() end)
  failure = attestation(request.attestation, request, ok and now or nil)
  if failure then
    r.operator_attestation_status = "rejected"
    r.source_process_identity_status = failure == "source_process_identity_unavailable" and "unavailable" or "not_verified"
    return reject(r, failure)
  end
  r.operator_attestation_status, r.process_identity_basis = "operator_reconfirmed", "operator_reconfirmed"
  r.source_process_identity_status = "operator_recorded_at_h1_not_measured"
  r.confirmed_at_utc, r.observed_at_utc = request.attestation.confirmed_at_utc, now
  if type(deps.readInteger) ~= "function" or type(deps.readFloat) ~= "function" then return reject(r, "candidate_read_api_unavailable") end
  r.candidate_value_consistent = false
  r.memory_read_attempts = 1
  local integer_ok, bits = pcall(deps.readInteger, c.address)
  if not integer_ok or not integer(bits, -0x80000000, 0xFFFFFFFF) then return reject(r, "candidate_integer_read_failed") end
  if bits < 0 then bits = bits + 0x100000000 end
  r.observed_integer_pattern = string.format("0x%08X", bits)
  r.memory_read_attempts = 2
  local float_ok, value = pcall(deps.readFloat, c.address)
  local observed_bits = float_ok and float_bits(value) or nil
  if observed_bits == nil then return reject(r, "candidate_float_read_failed") end
  r.observed_float, r.observed_float_pattern = value, string.format("0x%08X", observed_bits)
  -- readFloat must itself be a Float32 value, not an arbitrary rounded double.
  if value ~= string.unpack("<f", string.pack("<I4", observed_bits)) or observed_bits ~= bits then
    return reject(r, "candidate_observation_inconsistent")
  end
  if bits ~= c.expected_bits then return reject(r, "candidate_value_mismatch") end
  r.candidate_value_consistent, r.verification_status = true, "VALUE_CONSISTENT_NOT_AUTHORIZED"
  return r
end

local RESULT_FIELDS = {
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

function Verify.render(result)
  local lines = {}
  for _, key in ipairs(RESULT_FIELDS) do lines[#lines + 1] = key .. "=" .. number_text(result[key]) end
  return table.concat(lines, "\r\n") .. "\r\n"
end

return Verify
