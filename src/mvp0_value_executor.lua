local Executor = {}

Executor.VERSION = "guarded_write_v4_restore_only"

local REQUIRED_CONFIRM = "I_ACCEPT_WRITE_TO_LIVE_MEMORY"
-- Local operator-owned evidence is the trust boundary. Never accept a receipt,
-- path, or evidence root supplied by the restoration configuration.
local EVIDENCE_ROOT = [[D:\armedforces.io-v2\log\auto_output]]
local MAX_EVIDENCE_BYTES = 1024 * 1024
local MAX_RESTORE_ARM_SECONDS = 600

local DEFAULTS = {
  execution_mode = "disabled",
  write_enabled = false,
  write_method = "float",
  execution_addr_source = "stable_intersection_best_candidate",
  require_known_true_match = true,
  require_full_profile = true,
  require_old_value_match = true,
  readback_tolerance = 0.0001,
}

local function finite(value)
  return type(value) == "number" and value == value and math.abs(value) ~= math.huge
end

local function valid_address(value)
  return finite(value) and value > 0 and value <= 0x1FFFFFFFFFFFFF and value % 1 == 0
end

local function u32(value)
  if not finite(value) or value % 1 ~= 0 or value < -0x80000000 or value > 0xFFFFFFFF then
    return nil
  end
  if value < 0 then
    return value + 0x100000000
  end
  return value
end

local function float32(value)
  local numeric = tonumber(value)
  if not finite(numeric) then
    return nil, nil
  end
  local ok, packed = pcall(string.pack, "<f", numeric)
  if not ok then
    return nil, nil
  end
  local rounded = string.unpack("<f", packed)
  if not finite(rounded) then
    return nil, nil
  end
  return rounded, string.unpack("<I4", packed)
end

local function read_u32(addr)
  if type(readInteger) ~= "function" then
    return false, nil
  end
  local ok, value = pcall(readInteger, addr)
  if not ok or value == nil then
    return false, nil
  end
  local pattern = u32(value)
  return pattern ~= nil, pattern
end

local function read_f32(addr)
  if type(readFloat) ~= "function" then
    return false, nil
  end
  local ok, value = pcall(readFloat, addr)
  if not ok or not finite(value) then
    return false, nil
  end
  return true, value
end

local function bool_default(value, default_value)
  if value == nil then
    return default_value
  end
  return value == true
end

local function text_default(value, default_value)
  if value == nil or tostring(value) == "" then
    return default_value
  end
  return tostring(value)
end

local function optional_text(value)
  if type(value) ~= "string" then
    return nil
  end
  local text = value:match("^%s*(.-)%s*$")
  if text == "" then
    return nil
  end
  return text
end

local function parse_utc_timestamp(value)
  local text = optional_text(value)
  if text == nil then
    return nil
  end

  local year, month, day, hour, min, sec = text:match("^(%d%d%d%d)%-(%d%d)%-(%d%d)T(%d%d):(%d%d):(%d%d)Z$")
  if year == nil then
    return nil
  end

  year, month, day = tonumber(year), tonumber(month), tonumber(day)
  hour, min, sec = tonumber(hour), tonumber(min), tonumber(sec)
  local leap = year % 4 == 0 and (year % 100 ~= 0 or year % 400 == 0)
  local months = {31, leap and 29 or 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31}
  if year < 1970 or month < 1 or month > 12 or day < 1 or day > months[month]
      or hour > 23 or min > 59 or sec > 59 then
    return nil
  end
  -- UTC arithmetic avoids local timezone/DST conversion and date normalization.
  local y = year - 1
  local days = 365 * y + math.floor(y / 4) - math.floor(y / 100) + math.floor(y / 400) - 719162
  for m = 1, month - 1 do days = days + months[m] end
  return ((days + day - 1) * 24 + hour) * 3600 + min * 60 + sec
end

local function utc_now_epoch()
  if type(os) ~= "table" or type(os.date) ~= "function" then
    return nil
  end
  local ok, now = pcall(os.date, "!%Y-%m-%dT%H:%M:%SZ")
  return ok and parse_utc_timestamp(now) or nil
end

local function get_config(opts)
  local cfg = opts and opts.config or {}
  local restore_write_value_float = cfg.restore_write_value_float
  local restore_write_value_pattern = cfg.restore_write_value_pattern
  local execution_addr_source = text_default(cfg.execution_addr_source, DEFAULTS.execution_addr_source)
  local write_value_float = cfg.write_value_float
  local write_value_pattern = cfg.write_value_pattern
  if execution_addr_source == "restore_source_batch_execution_addr" then
    write_value_float = restore_write_value_float
    write_value_pattern = restore_write_value_pattern
  end
  return {
    case_id = optional_text(cfg.case_id),
    session_id = optional_text(cfg.session_id),
    validation_profile = cfg.validation_profile,
    target_value_pattern = cfg.target_value_pattern,
    target_value_float = cfg.target_value_float,
    execution_mode = text_default(cfg.execution_mode, DEFAULTS.execution_mode),
    write_enabled = bool_default(cfg.write_enabled, DEFAULTS.write_enabled),
    execution_confirm = cfg.execution_confirm,
    execution_write_request_id = optional_text(cfg.execution_write_request_id),
    execution_armed_at_utc = optional_text(cfg.execution_armed_at_utc),
    execution_arm_expires_at_utc = optional_text(cfg.execution_arm_expires_at_utc),
    write_value_float = write_value_float,
    write_value_pattern = write_value_pattern,
    write_method = text_default(cfg.write_method, DEFAULTS.write_method),
    execution_addr_source = execution_addr_source,
    restore_source_batch_id = optional_text(cfg.restore_source_batch_id),
    restore_source_case_id = cfg.restore_source_case_id,
    restore_source_session_id = cfg.restore_source_session_id,
    restore_process_attestation = cfg.restore_process_attestation,
    restore_execution_addr = cfg.restore_execution_addr,
    restore_expected_current_float = cfg.restore_expected_current_float,
    restore_expected_current_pattern = cfg.restore_expected_current_pattern,
    restore_write_value_float = restore_write_value_float,
    restore_write_value_pattern = restore_write_value_pattern,
    require_known_true_match = bool_default(cfg.require_known_true_match, DEFAULTS.require_known_true_match),
    require_full_profile = bool_default(cfg.require_full_profile, DEFAULTS.require_full_profile),
    require_old_value_match = bool_default(cfg.require_old_value_match, DEFAULTS.require_old_value_match),
    readback_tolerance = cfg.readback_tolerance == nil and DEFAULTS.readback_tolerance
      or tonumber(cfg.readback_tolerance),
  }
end

local function base_result(opts, cfg)
  opts = opts or {}
  cfg = cfg or get_config(opts)
  local summary = type(opts.summary) == "table" and opts.summary or {}
  local target_value_pattern = opts.target_value_pattern
    or summary.target_value_pattern
    or cfg.target_value_pattern
  local target_value_float = opts.target_value_float
    or summary.target_value_float
    or cfg.target_value_float

  return {
    execution_enabled = cfg.execution_mode ~= "disabled",
    execution_mode = cfg.execution_mode,
    write_enabled = cfg.write_enabled,
    execution_confirm_ok = cfg.execution_confirm == REQUIRED_CONFIRM,
    execution_write_request_id = cfg.execution_write_request_id,
    execution_armed_at_utc = cfg.execution_armed_at_utc,
    execution_arm_expires_at_utc = cfg.execution_arm_expires_at_utc,
    execution_arm_valid = false,
    execution_arm_seconds_remaining = nil,
    execution_addr = nil,
    execution_addr_source = cfg.execution_addr_source,
    restore_source_batch_id = cfg.restore_source_batch_id,
    restore_source_case_id = cfg.restore_source_case_id,
    restore_source_session_id = cfg.restore_source_session_id,
    restore_source_evidence_ok = false,
    restore_identity_basis = "not_reconfirmed",
    restore_process_measured = false,
    restore_request_reserved = false,
    restore_execution_addr = cfg.restore_execution_addr,
    restore_expected_current_float = cfg.restore_expected_current_float,
    restore_expected_current_pattern = cfg.restore_expected_current_pattern,
    restore_write_value_float = cfg.restore_write_value_float,
    restore_write_value_pattern = cfg.restore_write_value_pattern,
    restore_old_value_match = nil,
    restore_current_value_match = nil,
    restore_current_float = nil,
    restore_current_pattern = nil,
    execution_preconditions_ok = false,
    execution_identity_ok = false,
    write_ready = false,
    write_readiness_failure_class = nil,
    execution_success = false,
    execution_failure_class = nil,
    known_true_match_ok = nil,
    rank_guard_ok = false,
    old_value_read_ok = false,
    old_value_pattern = nil,
    old_value_float = nil,
    target_value_pattern = target_value_pattern,
    target_value_float = target_value_float,
    requested_write_value_float = cfg.write_value_float,
    requested_write_value_pattern = cfg.write_value_pattern,
    write_attempted = false,
    write_api_ok = false,
    write_ok = false,
    restore_attempted = false,
    restore_write_ok = false,
    restore_readback_ok = false,
    readback_ok = false,
    readback_pattern = nil,
    readback_float = nil,
    readback_delta = nil,
    rollback_available = false,
    rollback_value_pattern = nil,
    rollback_value_float = nil,
    executor_version = Executor.VERSION,
    write_method = cfg.write_method,
  }
end

local function fail(result, failure_class)
  result.execution_preconditions_ok = false
  result.write_ready = false
  result.execution_failure_class = failure_class
  return result
end

local function resolve_execution_addr(summary, source)
  if source == "stable_intersection_best_candidate" then
    return summary.stable_intersection_best_candidate
  end
  if source == "best_candidate" or source == "final_best_candidate" then
    return summary.best_candidate_addr
  end
  return nil
end

local function is_restore_source(cfg)
  return cfg.execution_addr_source == "restore_source_batch_execution_addr"
end

local function write_float(addr, value)
  if type(writeFloat) ~= "function" then
    return false, "write_api_unavailable"
  end
  local ok, write_result = pcall(writeFloat, addr, value)
  if not ok or write_result ~= true then
    return false, "write_failed"
  end
  return true, nil
end

local function read_old_value(result, addr)
  local read_ok, old_pattern = read_u32(addr)
  result.old_value_pattern = old_pattern
  local float_ok, old_float = read_f32(addr)
  if float_ok then
    result.old_value_float = old_float
  end
  result.old_value_read_ok = read_ok and float_ok
  return result.old_value_read_ok, old_pattern
end

local function old_value_matches_target(result, cfg, old_pattern)
  local target_pattern = u32(result.target_value_pattern)
  if cfg.require_old_value_match and (target_pattern == nil or old_pattern ~= target_pattern) then
    return false
  end
  return true
end

local function validate_restore_config(cfg)
  if cfg.restore_source_batch_id == nil then
    return false, "missing_restore_source_batch_id"
  end
  if u32(cfg.restore_expected_current_pattern) == nil
      or tonumber(cfg.restore_expected_current_float) == nil then
    return false, "missing_restore_expected_current"
  end
  if u32(cfg.restore_write_value_pattern) == nil
      or tonumber(cfg.restore_write_value_float) == nil then
    return false, "missing_restore_write_value"
  end
  local _, current_pattern = float32(cfg.restore_expected_current_float)
  local _, original_pattern = float32(cfg.restore_write_value_float)
  if current_pattern ~= u32(cfg.restore_expected_current_pattern)
      or original_pattern ~= u32(cfg.restore_write_value_pattern) then
    return false, "restore_value_pattern_mismatch"
  end
  return true, nil
end

local function restore_current_value_matches(result, cfg)
  result.restore_current_pattern = result.old_value_pattern
  result.restore_current_float = result.old_value_float

  local expected_pattern = u32(cfg.restore_expected_current_pattern)
  local expected_float = float32(cfg.restore_expected_current_float)
  local pattern_ok = expected_pattern ~= nil and result.old_value_pattern == expected_pattern
  local float_ok = expected_float ~= nil
      and type(result.old_value_float) == "number"
      and result.old_value_float == expected_float

  result.restore_current_value_match = pattern_ok and float_ok
  result.restore_old_value_match = result.restore_current_value_match
  return result.restore_current_value_match
end

local function safe_token(value)
  -- Match the runner's canonical filename tokens without lossy sanitization.
  return type(value) == "string" and #value > 0 and #value <= 128
    and value ~= "nil" and value ~= "unknown"
    and value:match("^[A-Za-z0-9][A-Za-z0-9_-]*$") ~= nil
    and not value:find("__", 1, true) and value:sub(-1) ~= "_"
end

local function read_evidence(path)
  if type(io) ~= "table" or type(io.open) ~= "function" then
    return nil, "restore_evidence_io_unavailable"
  end
  local opened, handle = pcall(io.open, path, "rb")
  if not opened or not handle then return nil, "restore_source_evidence_missing" end
  local ok, text = pcall(handle.read, handle, MAX_EVIDENCE_BYTES + 1)
  local closed, close_result = pcall(handle.close, handle)
  if not ok or not closed or not close_result or type(text) ~= "string"
      or #text == 0 or #text > MAX_EVIDENCE_BYTES or text:find("%z") then
    return nil, "restore_source_evidence_malformed"
  end
  return text
end

local SOURCE_FIELDS = {
  "case_id", "session_id", "mode", "validation_profile", "run_valid", "failure_class", "error", "collector_empty",
  "known_true_addr", "stable_intersection_best_candidate", "stable_intersection_known_true_rank_position",
  "execution_mode", "execution_addr", "execution_addr_source", "execution_write_request_id",
  "execution_armed_at_utc", "execution_arm_expires_at_utc", "execution_arm_valid", "execution_arm_seconds_remaining",
  "execution_enabled", "write_enabled", "execution_confirm_ok", "execution_identity_ok",
  "execution_preconditions_ok", "rank_guard_ok", "known_true_match_ok", "old_value_read_ok",
  "write_ready", "write_attempted", "write_api_ok", "write_ok", "readback_ok", "execution_success",
  "execution_failure_class", "restore_attempted", "restore_source_batch_id", "rollback_available",
  "write_method", "executor_version", "old_value_float", "old_value_pattern",
  "rollback_value_float", "rollback_value_pattern", "requested_write_value_float",
  "requested_write_value_pattern", "readback_float", "readback_pattern",
}

local function receipt_fields(text)
  local allowed, fields = {}, {}
  for _, key in ipairs(SOURCE_FIELDS) do allowed[key] = true end
  for line in (text .. "\n"):gmatch("([^\n]*)\n") do
    local key, value = line:match("^([%w_]+)%s*=%s*(.-)%s*$")
    if key and allowed[key] then
      if fields[key] ~= nil then return nil end
      fields[key] = value
    end
  end
  return fields
end

local function summary_receipt(text, batch_id)
  if not text:match("^=== Batch Summary ===[\r\n]") then return nil end
  local batch_count, stable_count, block, session = 0, 0, nil, nil
  local in_stable = false
  for line in (text .. "\n"):gmatch("([^\n]*)\n") do
    line = line:gsub("\r$", "")
    local id = line:match("^batch_id = (.+)$")
    if id then
      batch_count = batch_count + 1
      if id ~= batch_id then return nil end
    end
    if line:match("^===") or line:match("^---") then
      in_stable = false
      local name = line:match("^%-%-%- (.+) / stable_no_probe_intersection %-%-%-$")
      if name then
        stable_count = stable_count + 1
        session, block, in_stable = name, {}, true
      end
    elseif in_stable then
      block[#block + 1] = line
    end
  end
  if batch_count ~= 1 or stable_count ~= 1 then return nil end
  local fields = receipt_fields(table.concat(block, "\n"))
  if not fields or (fields.session_id and fields.session_id ~= session)
      or (fields.mode and fields.mode ~= "stable_no_probe_intersection") then return nil end
  fields.session_id = session
  fields.mode = "stable_no_probe_intersection"
  return fields
end

local function receipt_pair(fields, prefix)
  local value = tonumber(fields[prefix .. "_float"])
  local bits = u32(tonumber(fields[prefix .. "_pattern"]))
  local rounded, packed = float32(value)
  if rounded == nil or bits == nil or packed ~= bits then return nil end
  return rounded, bits
end

local function validate_source_evidence(result, cfg)
  local batch = cfg.restore_source_batch_id
  if not batch or not batch:match("^%d%d%d%d%d%d%d%d%-%d%d%d%d%d%d$")
      or not safe_token(cfg.restore_source_case_id) or not safe_token(cfg.restore_source_session_id) then
    return nil, "invalid_restore_source_identity"
  end
  local summary_text, err = read_evidence(EVIDENCE_ROOT .. "\\" .. batch .. "__summary.txt")
  if not summary_text then return nil, err end
  local receipt = summary_receipt(summary_text, batch)
  if not receipt then return nil, "restore_source_evidence_malformed" end
  if receipt.case_id ~= cfg.restore_source_case_id or receipt.session_id ~= cfg.restore_source_session_id
      or cfg.session_id ~= receipt.session_id then
    return nil, "restore_source_identity_mismatch"
  end
  local path = string.format("%s\\%s__%s__%s__stable_no_probe_intersection.log",
    EVIDENCE_ROOT, batch, cfg.restore_source_session_id, cfg.restore_source_case_id)
  local log_text
  log_text, err = read_evidence(path)
  if not log_text then return nil, err end
  local log_receipt = receipt_fields(log_text)
  local _, execution_sections = log_text:gsub("=== value_execution ===", "")
  if not log_receipt or execution_sections ~= 1 then return nil, "restore_source_evidence_malformed" end
  for _, key in ipairs(SOURCE_FIELDS) do
    if receipt[key] == nil or receipt[key] ~= log_receipt[key] then
      return nil, "restore_source_evidence_mismatch"
    end
  end
  for _, key in ipairs({"run_valid", "execution_enabled", "write_enabled", "execution_confirm_ok",
      "execution_identity_ok", "execution_preconditions_ok", "rank_guard_ok", "known_true_match_ok",
      "old_value_read_ok", "execution_arm_valid", "write_ready", "write_attempted", "write_api_ok",
      "write_ok", "readback_ok", "execution_success", "rollback_available"}) do
    if receipt[key] ~= "true" then return nil, "restore_source_write_not_successful" end
  end
  if receipt.validation_profile ~= "full" or receipt.execution_mode ~= "write"
      or receipt.collector_empty ~= "false"
      or receipt.restore_attempted ~= "false" or receipt.restore_source_batch_id ~= "nil"
      or receipt.execution_failure_class ~= "nil" or receipt.failure_class ~= "nil" or receipt.error ~= "nil"
      or receipt.write_method ~= "float"
      or (receipt.executor_version ~= "guarded_write_v3" and receipt.executor_version ~= Executor.VERSION)
      or (receipt.execution_addr_source ~= "stable_intersection_best_candidate"
        and receipt.execution_addr_source ~= "best_candidate" and receipt.execution_addr_source ~= "final_best_candidate")
      or tonumber(receipt.stable_intersection_known_true_rank_position) ~= 1 then
    return nil, "restore_source_write_not_successful"
  end
  local addr = tonumber(receipt.execution_addr)
  if not valid_address(addr) or addr ~= cfg.restore_execution_addr
      or addr ~= tonumber(receipt.known_true_addr) or addr ~= tonumber(receipt.stable_intersection_best_candidate) then
    return nil, "restore_source_address_mismatch"
  end
  local original, original_bits = receipt_pair(receipt, "old_value")
  local rollback, rollback_bits = receipt_pair(receipt, "rollback_value")
  local written, written_bits = receipt_pair(receipt, "requested_write_value")
  local readback, readback_bits = receipt_pair(receipt, "readback")
  if original == nil or rollback == nil or written == nil or readback == nil
      or original_bits ~= rollback_bits or written_bits ~= readback_bits
      or original_bits ~= u32(cfg.restore_write_value_pattern)
      or written_bits ~= u32(cfg.restore_expected_current_pattern) then
    return nil, "restore_source_value_mismatch"
  end
  local source_armed = parse_utc_timestamp(receipt.execution_armed_at_utc)
  local source_expires = parse_utc_timestamp(receipt.execution_arm_expires_at_utc)
  local remaining = tonumber(receipt.execution_arm_seconds_remaining)
  if not safe_token(receipt.execution_write_request_id) or not source_armed or not source_expires
      or source_expires <= source_armed or not finite(remaining) or remaining <= 0
      or remaining > source_expires - source_armed then return nil, "restore_source_arm_invalid" end
  result.restore_source_evidence_ok = true
  result.restore_source_write_request_id = receipt.execution_write_request_id
  return receipt
end

local function identity_text(value)
  return type(value) == "string" and #value > 0 and #value <= 512
    and optional_text(value) == value and not value:find("%c") and value ~= "unknown" and value ~= "nil"
end

local function validate_restore_attestation(result, cfg, receipt)
  local att = cfg.restore_process_attestation
  local now = utc_now_epoch()
  if type(att) ~= "table" or att.identity_basis ~= "operator_reconfirmed"
      or att.same_process_confirmed ~= true or att.source_receipt_confirmed ~= true
      or att.request_id ~= cfg.execution_write_request_id or not safe_token(att.request_id)
      or att.source_write_request_id ~= receipt.execution_write_request_id
      or att.source_batch_id ~= cfg.restore_source_batch_id
      or att.case_id ~= cfg.case_id or att.session_id ~= cfg.session_id
      or type(att.source) ~= "table" or type(att.current) ~= "table" then
    return "restore_process_attestation_invalid"
  end
  local confirmed = parse_utc_timestamp(att.confirmed_at_utc)
  local started = parse_utc_timestamp(att.current.started_at_utc)
  if not now or not confirmed or not started or started > confirmed or confirmed > now
      or started > parse_utc_timestamp(receipt.execution_armed_at_utc)
      or now - confirmed > MAX_RESTORE_ARM_SECONDS
      or not finite(att.current.pid) or att.current.pid % 1 ~= 0 or att.current.pid <= 0
      or att.current.pid > 0xFFFFFFFF or not identity_text(att.current.executable)
      or not identity_text(att.current.scene) then return "restore_process_attestation_invalid" end
  for _, key in ipairs({"pid", "started_at_utc", "executable", "scene"}) do
    if att.source[key] ~= att.current[key] then return "restore_process_identity_changed" end
  end
  result.restore_identity_basis = "operator_reconfirmed"
  result.restore_process_pid = att.current.pid
  result.restore_process_started_at_utc = att.current.started_at_utc
  result.restore_process_executable = att.current.executable
  result.restore_process_scene = att.current.scene
  result.restore_process_confirmed_at_utc = att.confirmed_at_utc
  return nil
end

local function restore_request_path(cfg)
  return EVIDENCE_ROOT .. "\\restore_request__" .. cfg.execution_write_request_id .. ".log"
end

local function unused_restore_request(cfg)
  if not safe_token(cfg.execution_write_request_id) then return "missing_execution_arm" end
  -- Read exactly this request's reservation; never enumerate/reprocess history.
  if type(io) ~= "table" or type(io.open) ~= "function" then return "restore_evidence_io_unavailable" end
  local ok, handle, _, code = pcall(io.open, restore_request_path(cfg), "rb")
  if not ok then return "restore_request_check_failed" end
  if handle then
    pcall(handle.close, handle)
    return "restore_request_reused"
  end
  if code ~= 2 then return "restore_request_check_failed" end -- ENOENT only
  return nil
end

local function reserve_restore_request(result, cfg)
  local failure = unused_restore_request(cfg)
  if failure then return failure end
  -- Consume before attempting memory I/O, including uncertain/failed writes.
  -- Manual runs are serialized; a reservation is never removed or retried.
  local ok, handle = pcall(io.open, restore_request_path(cfg), "wb")
  if not ok or not handle then return "restore_request_reservation_failed" end
  local written, write_result = pcall(handle.write, handle,
    "restore_request_reserved = true\nexecution_write_request_id = " .. cfg.execution_write_request_id
      .. "\nrestore_source_batch_id = " .. cfg.restore_source_batch_id .. "\n")
  local closed, close_result = pcall(handle.close, handle)
  if not written or not write_result or not closed or not close_result then
    return "restore_request_reservation_failed"
  end
  result.restore_request_reserved = true
  return nil
end

local function validate_write_arm(result, cfg)
  result.execution_arm_valid = false
  result.execution_arm_seconds_remaining = nil
  if cfg.execution_write_request_id == nil
      or cfg.execution_armed_at_utc == nil
      or cfg.execution_arm_expires_at_utc == nil then
    return false, "missing_execution_arm"
  end

  local armed_epoch = parse_utc_timestamp(cfg.execution_armed_at_utc)
  local expires_epoch = parse_utc_timestamp(cfg.execution_arm_expires_at_utc)
  local now_epoch = utc_now_epoch()
  if armed_epoch == nil or expires_epoch == nil or now_epoch == nil then
    return false, "missing_execution_arm"
  end

  if expires_epoch <= armed_epoch or now_epoch < armed_epoch then
    result.execution_arm_valid = false
    return false, "invalid_execution_arm_window"
  end
  local seconds_remaining = expires_epoch - now_epoch
  result.execution_arm_seconds_remaining = seconds_remaining
  if seconds_remaining <= 0 then
    result.execution_arm_valid = false
    return false, "execution_arm_expired"
  end

  result.execution_arm_valid = true
  return true, nil
end

local function write_readiness(result, cfg)
  local arm_ok, arm_failure = validate_write_arm(result, cfg)
  if not cfg.write_enabled then return "write_disabled" end
  if not result.execution_confirm_ok then return "missing_execution_confirm" end
  if not arm_ok then return arm_failure end
  if type(writeFloat) ~= "function" then return "write_api_unavailable" end
  return nil
end

local function perform_write(result, cfg, addr, write_value_float, write_value_pattern, restore_source)
  result.write_attempted = true
  result.restore_attempted = restore_source
  result.rollback_available = true
  result.rollback_value_pattern = result.old_value_pattern
  result.rollback_value_float = result.old_value_float
  local write_ok, write_failure_class = write_float(addr, write_value_float)
  result.write_api_ok = write_ok
  result.restore_write_ok = restore_source and write_ok
  if not write_ok then
    result.execution_failure_class = write_failure_class or "write_failed"
    return result
  end

  local readback_pattern_ok, readback_pattern = read_u32(addr)
  if readback_pattern_ok then
    result.readback_pattern = readback_pattern
  end
  local readback_float_ok, readback_float = read_f32(addr)
  if readback_float_ok then
    local _, readback_float_pattern = float32(readback_float)
    result.readback_float = readback_float
    result.readback_delta = readback_float - write_value_float
    result.readback_ok = readback_pattern_ok and readback_pattern == write_value_pattern
      and readback_float_pattern == write_value_pattern
      and math.abs(result.readback_delta) <= cfg.readback_tolerance
      and (not restore_source or readback_float == write_value_float)
  end

  result.restore_readback_ok = restore_source and result.readback_ok
  result.write_ok = write_ok and result.readback_ok
  result.execution_success = result.write_ok
  if result.readback_ok ~= true then
    result.execution_failure_class = (not readback_pattern_ok or not readback_float_ok)
      and "readback_read_failed" or "readback_mismatch"
  end
  return result
end

function Executor.default_result(opts)
  return base_result(opts, get_config(opts))
end

local function evaluate_normal(opts, cfg, result)
  local summary = type(opts.summary) == "table" and opts.summary or {}

  if cfg.execution_mode == "disabled" then
    result.execution_enabled = false
    return result
  end

  if cfg.execution_mode ~= "dry_run" and cfg.execution_mode ~= "write" then
    return fail(result, "invalid_execution_mode")
  end

  -- Single has no write handoff; configuration overrides cannot relabel it.
  if cfg.validation_profile == "single" or summary.validation_profile == "single" then
    return fail(result, "single_detect_only")
  end
  if summary.validation_profile ~= "full" and summary.validation_profile ~= "quick" then
    return fail(result, "invalid_validation_profile")
  end
  if cfg.require_full_profile and summary.validation_profile ~= "full" then
    return fail(result, "profile_not_full")
  end
  if cfg.case_id == nil or cfg.session_id == nil
      or cfg.case_id ~= summary.case_id or cfg.session_id ~= summary.session_id
      or cfg.validation_profile ~= summary.validation_profile then
    return fail(result, "execution_identity_mismatch")
  end
  result.execution_identity_ok = true

  if summary.run_valid ~= true or summary.error ~= nil or summary.failure_class ~= nil then
    return fail(result, "run_not_valid")
  end

  if summary.collector_empty == true then
    return fail(result, "collector_empty")
  end

  local addr = resolve_execution_addr(summary, cfg.execution_addr_source)
  result.execution_addr = addr
  if not valid_address(addr) then
    -- Keep malformed numbers out of hex-formatted runner output.
    result.execution_addr = nil
    return fail(result, addr == nil and "missing_execution_addr" or "invalid_execution_addr")
  end

  local stable_rank = tonumber(summary.stable_intersection_known_true_rank_position)
  if stable_rank ~= 1 then
    return fail(result, "stable_rank_not_1")
  end

  local rank_guard = opts.rank_guard
  if type(rank_guard) == "table" then
    result.rank_guard_ok = rank_guard.ok == true
      and rank_guard.rank_A == 1 and rank_guard.rank_W == 1 and rank_guard.rank_B == 1
      and rank_guard.case_id == summary.case_id and rank_guard.session_id == summary.session_id
      and rank_guard.validation_profile == "full"
  end
  if result.rank_guard_ok ~= true then
    return fail(result, "rank_guard_failed")
  end

  local known_true_addr = opts.known_true_addr or summary.known_true_addr
    or (opts.config and opts.config.known_true_addr)
  for _, source in ipairs({opts, summary, opts.config or {}}) do
    if source.known_true_addr ~= nil and source.known_true_addr ~= known_true_addr then
      return fail(result, "known_true_identity_mismatch")
    end
  end
  result.known_true_match_ok = valid_address(known_true_addr) and addr == known_true_addr
  if cfg.require_known_true_match and not result.known_true_match_ok then
    return fail(result, valid_address(known_true_addr) and "known_true_mismatch" or "missing_known_true_addr")
  end

  if cfg.write_method ~= "float" then
    return fail(result, "unsupported_write_method")
  end
  if not finite(cfg.readback_tolerance) or cfg.readback_tolerance < 0 then
    return fail(result, "invalid_readback_tolerance")
  end
  local write_value_float, write_value_pattern = float32(cfg.write_value_float)
  if write_value_float == nil then
    return fail(result, "invalid_write_value_float")
  end
  if cfg.write_value_pattern ~= nil and u32(cfg.write_value_pattern) ~= write_value_pattern then
    return fail(result, "write_value_pattern_mismatch")
  end
  result.requested_write_value_float = write_value_float
  result.requested_write_value_pattern = write_value_pattern

  do
    local expected_pattern = u32(result.target_value_pattern)
    if cfg.require_old_value_match and expected_pattern == nil then
      return fail(result, "missing_target_value_pattern")
    end
    for _, source in ipairs({opts, summary, cfg}) do
      local _, pattern_from_float = float32(source.target_value_float)
      if (source.target_value_pattern ~= nil and u32(source.target_value_pattern) ~= expected_pattern)
          or (source.target_value_float ~= nil and pattern_from_float ~= expected_pattern) then
        return fail(result, "target_value_identity_mismatch")
      end
    end
  end

  result.write_readiness_failure_class = write_readiness(result, cfg)
  if cfg.execution_mode == "write" and result.write_readiness_failure_class ~= nil then
    return fail(result, result.write_readiness_failure_class)
  end
  local read_ok, old_pattern = read_old_value(result, addr)
  if not read_ok then
    return fail(result, "old_value_read_failed")
  end
  local _, old_float_pattern = float32(result.old_value_float)
  if old_float_pattern ~= old_pattern then
    return fail(result, "old_value_inconsistent")
  end

  if not old_value_matches_target(result, cfg, old_pattern) then
    return fail(result, "old_value_mismatch")
  end

  result.execution_preconditions_ok = true
  -- Reads may have consumed the remainder of the arm. Recheck immediately
  -- before the only write, and expose authorization separately in previews.
  result.write_readiness_failure_class = write_readiness(result, cfg)
  result.write_ready = result.write_readiness_failure_class == nil

  if cfg.execution_mode == "dry_run" then
    return result
  end
  if not result.write_ready then
    return fail(result, result.write_readiness_failure_class)
  end

  return perform_write(result, cfg, addr, write_value_float, write_value_pattern, false)
end

local function restore_readiness(result, cfg, receipt)
  local failure = write_readiness(result, cfg)
  if failure then return failure end
  local armed = parse_utc_timestamp(cfg.execution_armed_at_utc)
  local expires = parse_utc_timestamp(cfg.execution_arm_expires_at_utc)
  if cfg.execution_write_request_id == receipt.execution_write_request_id
      or armed <= parse_utc_timestamp(receipt.execution_armed_at_utc) then
    result.execution_arm_valid = false
    return "restore_authorization_reused"
  end
  if expires - armed > MAX_RESTORE_ARM_SECONDS then
    result.execution_arm_valid = false
    return "restore_arm_too_long"
  end
  if parse_utc_timestamp(cfg.restore_process_attestation.confirmed_at_utc) < armed then
    return "restore_attestation_predates_arm"
  end
  return unused_restore_request(cfg)
end

local function evaluate_restore(opts, cfg, result)
  result.mode = "restore_only"
  if cfg.execution_mode == "disabled" then return result end
  if cfg.execution_mode ~= "dry_run" and cfg.execution_mode ~= "write" then
    return fail(result, "invalid_execution_mode")
  end
  if cfg.validation_profile == "single"
      or (type(opts.summary) == "table" and rawget(opts.summary, "validation_profile") == "single") then
    return fail(result, "single_detect_only")
  end
  if cfg.validation_profile ~= "full" then return fail(result, "profile_not_full") end
  if not safe_token(cfg.case_id) or not safe_token(cfg.session_id) then
    return fail(result, "execution_identity_mismatch")
  end
  if not valid_address(cfg.restore_execution_addr) then
    return fail(result, cfg.restore_execution_addr == nil
      and "missing_restore_execution_addr" or "invalid_restore_execution_addr")
  end
  result.execution_addr = cfg.restore_execution_addr
  local valid, failure = validate_restore_config(cfg)
  if not valid then return fail(result, failure) end
  if cfg.write_method ~= "float" then return fail(result, "unsupported_write_method") end
  if not finite(cfg.readback_tolerance) or cfg.readback_tolerance < 0 then
    return fail(result, "invalid_readback_tolerance")
  end
  local receipt
  receipt, failure = validate_source_evidence(result, cfg)
  if not receipt then return fail(result, failure) end
  failure = validate_restore_attestation(result, cfg, receipt)
  if failure then return fail(result, failure) end
  result.execution_identity_ok = true -- case/session linkage, NOT measured process identity
  failure = unused_restore_request(cfg)
  if failure then return fail(result, failure) end
  if cfg.execution_write_request_id == receipt.execution_write_request_id then
    return fail(result, "restore_authorization_reused")
  end
  local value, bits = float32(cfg.restore_write_value_float)
  result.requested_write_value_float, result.requested_write_value_pattern = value, bits
  result.write_readiness_failure_class = restore_readiness(result, cfg, receipt)
  if cfg.execution_mode == "write" and result.write_readiness_failure_class then
    return fail(result, result.write_readiness_failure_class)
  end
  local read_ok, current_bits = read_old_value(result, result.execution_addr)
  if not read_ok then return fail(result, "old_value_read_failed") end
  local _, float_bits = float32(result.old_value_float)
  if float_bits ~= current_bits then return fail(result, "old_value_inconsistent") end
  if not restore_current_value_matches(result, cfg) then return fail(result, "restore_old_value_mismatch") end
  result.execution_preconditions_ok = true
  -- Reconfirm the independent attestation/arm after all preflight reads.
  failure = validate_restore_attestation(result, cfg, receipt)
  if failure then return fail(result, failure) end
  result.write_readiness_failure_class = restore_readiness(result, cfg, receipt)
  result.write_ready = result.write_readiness_failure_class == nil
  if cfg.execution_mode == "dry_run" then return result end
  if not result.write_ready then return fail(result, result.write_readiness_failure_class) end
  failure = reserve_restore_request(result, cfg)
  if failure then return fail(result, failure) end
  -- Reservation I/O can take time: reread this address and recheck authority.
  read_ok, current_bits = read_old_value(result, result.execution_addr)
  if not read_ok then return fail(result, "old_value_read_failed") end
  _, float_bits = float32(result.old_value_float)
  if float_bits ~= current_bits then return fail(result, "old_value_inconsistent") end
  if not restore_current_value_matches(result, cfg) then return fail(result, "restore_old_value_mismatch") end
  failure = validate_restore_attestation(result, cfg, receipt)
  if failure then return fail(result, failure) end
  failure = write_readiness(result, cfg)
  if failure then return fail(result, failure) end
  return perform_write(result, cfg, result.execution_addr, value, bits, true)
end

function Executor.evaluate(opts)
  opts = opts or {}
  local cfg = get_config(opts)
  local restoring = is_restore_source(cfg)
  -- A restore never reads ranking/target fields, even from a malformed summary.
  local result = base_result(restoring and {config = opts.config} or opts, cfg)
  local evaluate = restoring and evaluate_restore or evaluate_normal
  local ok, evaluated = pcall(evaluate, opts, cfg, result)
  if ok then return evaluated end
  -- Preserve attempt/API flags if an unexpected exception followed a write.
  result.execution_success, result.write_ok, result.readback_ok, result.restore_readback_ok = false, false, false, false
  result.executor_error = tostring(evaluated)
  return fail(result, "executor_exception")
end

_G.MVP0ValueExecutor = Executor
return Executor
