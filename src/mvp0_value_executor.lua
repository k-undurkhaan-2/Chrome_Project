local Executor = {}

Executor.VERSION = "guarded_write_v2"

local REQUIRED_CONFIRM = "I_ACCEPT_WRITE_TO_LIVE_MEMORY"

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

local function u32(value)
  if type(value) ~= "number" then
    return nil
  end
  if value < 0 then
    return value + 0x100000000
  end
  return value
end

local function read_u32(addr)
  if type(readInteger) ~= "function" then
    return false, nil
  end
  local ok, value = pcall(readInteger, addr)
  if not ok or value == nil then
    return false, nil
  end
  return true, u32(value)
end

local function read_f32(addr)
  if type(readFloat) ~= "function" then
    return false, nil
  end
  local ok, value = pcall(readFloat, addr)
  if not ok or type(value) ~= "number" then
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
  if value == nil then
    return nil
  end
  local text = tostring(value)
  if text == "" then
    return nil
  end
  return text
end

local function number_default(value, default_value)
  local numeric = tonumber(value)
  if numeric == nil then
    return default_value
  end
  return numeric
end

local function parse_utc_timestamp(value)
  local text = optional_text(value)
  if text == nil or type(os) ~= "table" or type(os.time) ~= "function" then
    return nil
  end

  local year, month, day, hour, min, sec = text:match("^(%d%d%d%d)%-(%d%d)%-(%d%d)T(%d%d):(%d%d):(%d%d)Z$")
  if year == nil then
    return nil
  end

  return os.time({
    year = tonumber(year),
    month = tonumber(month),
    day = tonumber(day),
    hour = tonumber(hour),
    min = tonumber(min),
    sec = tonumber(sec),
    isdst = false,
  })
end

local function utc_now_epoch()
  if type(os) ~= "table" or type(os.date) ~= "function" or type(os.time) ~= "function" then
    return nil
  end
  return os.time(os.date("!*t"))
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
    restore_execution_addr = cfg.restore_execution_addr,
    restore_expected_current_float = cfg.restore_expected_current_float,
    restore_expected_current_pattern = cfg.restore_expected_current_pattern,
    restore_write_value_float = restore_write_value_float,
    restore_write_value_pattern = restore_write_value_pattern,
    require_known_true_match = bool_default(cfg.require_known_true_match, DEFAULTS.require_known_true_match),
    require_full_profile = bool_default(cfg.require_full_profile, DEFAULTS.require_full_profile),
    require_old_value_match = bool_default(cfg.require_old_value_match, DEFAULTS.require_old_value_match),
    readback_tolerance = number_default(cfg.readback_tolerance, DEFAULTS.readback_tolerance),
  }
end

local function base_result(opts, cfg)
  opts = opts or {}
  cfg = cfg or get_config(opts)
  local summary = opts.summary or {}
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
    write_ok = false,
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

local function resolve_restore_execution_addr(cfg)
  if type(cfg.restore_execution_addr) == "number" then
    return cfg.restore_execution_addr
  end
  return nil
end

local function write_float(addr, value)
  if type(writeFloat) ~= "function" then
    return false, "write_api_unavailable"
  end
  local ok, write_result = pcall(writeFloat, addr, value)
  if not ok or write_result == false then
    return false, "write_failed"
  end
  return true, nil
end

local function read_old_value(result, addr)
  local read_ok, old_pattern = read_u32(addr)
  result.old_value_read_ok = read_ok
  result.old_value_pattern = old_pattern
  local float_ok, old_float = read_f32(addr)
  if float_ok then
    result.old_value_float = old_float
  end
  return read_ok, old_pattern
end

local function old_value_matches_target(result, cfg, old_pattern)
  local target_pattern = u32(result.target_value_pattern)
  if cfg.require_old_value_match and target_pattern ~= nil and old_pattern ~= target_pattern then
    return false
  end
  return true
end

local function validate_restore_config(cfg)
  if type(cfg.restore_execution_addr) ~= "number" then
    return false, "missing_restore_execution_addr"
  end
  if u32(cfg.restore_expected_current_pattern) == nil
      or tonumber(cfg.restore_expected_current_float) == nil then
    return false, "missing_restore_expected_current"
  end
  if u32(cfg.restore_write_value_pattern) == nil
      or tonumber(cfg.restore_write_value_float) == nil then
    return false, "missing_restore_write_value"
  end
  return true, nil
end

local function restore_current_value_matches(result, cfg)
  result.restore_current_pattern = result.old_value_pattern
  result.restore_current_float = result.old_value_float

  local expected_pattern = u32(cfg.restore_expected_current_pattern)
  local expected_float = tonumber(cfg.restore_expected_current_float)
  local pattern_ok = expected_pattern ~= nil and result.old_value_pattern == expected_pattern
  local float_ok = expected_float ~= nil
      and type(result.old_value_float) == "number"
      and math.abs(result.old_value_float - expected_float) <= cfg.readback_tolerance

  result.restore_current_value_match = pattern_ok and float_ok
  result.restore_old_value_match = result.restore_current_value_match
  return result.restore_current_value_match
end

local function validate_write_arm(result, cfg)
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

  local seconds_remaining = os.difftime(expires_epoch, now_epoch)
  result.execution_arm_seconds_remaining = seconds_remaining
  if seconds_remaining < 0 then
    result.execution_arm_valid = false
    return false, "execution_arm_expired"
  end

  result.execution_arm_valid = true
  return true, nil
end

function Executor.default_result(opts)
  return base_result(opts, get_config(opts))
end

function Executor.evaluate(opts)
  opts = opts or {}
  local cfg = get_config(opts)
  local summary = opts.summary or {}
  local result = base_result(opts, cfg)

  if cfg.execution_mode == "disabled" then
    result.execution_enabled = false
    return result
  end

  if cfg.execution_mode ~= "dry_run" and cfg.execution_mode ~= "write" then
    return fail(result, "invalid_execution_mode")
  end

  if cfg.require_full_profile and summary.validation_profile ~= "full" then
    return fail(result, "profile_not_full")
  end

  if summary.run_valid ~= true then
    return fail(result, "run_not_valid")
  end

  if summary.collector_empty == true then
    return fail(result, "collector_empty")
  end

  local restore_source = is_restore_source(cfg)
  local addr = nil
  if restore_source then
    addr = resolve_restore_execution_addr(cfg)
  else
    addr = resolve_execution_addr(summary, cfg.execution_addr_source)
  end
  result.execution_addr = addr
  if type(addr) ~= "number" then
    if restore_source then
      return fail(result, "missing_restore_execution_addr")
    end
    return fail(result, "missing_execution_addr")
  end

  if restore_source then
    local restore_config_ok, restore_config_failure = validate_restore_config(cfg)
    if restore_config_ok ~= true then
      return fail(result, restore_config_failure)
    end
  else
    local stable_rank = tonumber(summary.stable_intersection_known_true_rank_position)
    if stable_rank ~= 1 then
      return fail(result, "stable_rank_not_1")
    end
  end

  local rank_guard = opts.rank_guard
  if rank_guard ~= nil then
    result.rank_guard_ok = rank_guard.ok == true
  end
  if cfg.execution_mode == "write" and not restore_source and result.rank_guard_ok ~= true then
    return fail(result, "rank_guard_failed")
  end

  local known_true_addr = opts.known_true_addr or summary.known_true_addr
  if type(known_true_addr) == "number" then
    result.known_true_match_ok = addr == known_true_addr
    if cfg.require_known_true_match and not restore_source and not result.known_true_match_ok then
      return fail(result, "known_true_mismatch")
    end
  end

  if cfg.execution_mode == "write" then
    if cfg.write_enabled ~= true then
      return fail(result, "write_disabled")
    end
    if result.execution_confirm_ok ~= true then
      return fail(result, "missing_execution_confirm")
    end
    local arm_ok, arm_failure_class = validate_write_arm(result, cfg)
    if arm_ok ~= true then
      return fail(result, arm_failure_class)
    end
    if cfg.write_method ~= "float" then
      return fail(result, "unsupported_write_method")
    end
    if restore_source then
      if tonumber(cfg.restore_write_value_float) == nil then
        return fail(result, "missing_restore_write_value")
      end
    elseif tonumber(cfg.write_value_float) == nil then
      return fail(result, "invalid_write_value_float")
    end
  end

  local read_ok, old_pattern = read_old_value(result, addr)
  if not read_ok then
    return fail(result, "old_value_read_failed")
  end

  if restore_source then
    if not restore_current_value_matches(result, cfg) then
      return fail(result, "restore_old_value_mismatch")
    end
  else
    if not old_value_matches_target(result, cfg, old_pattern) then
      return fail(result, "old_value_mismatch")
    end
  end

  result.execution_preconditions_ok = true

  if cfg.execution_mode == "dry_run" then
    return result
  end

  local write_value_float = tonumber(cfg.write_value_float)
  result.write_attempted = true
  result.rollback_available = true
  result.rollback_value_pattern = result.old_value_pattern
  result.rollback_value_float = result.old_value_float
  local write_ok, write_failure_class = write_float(addr, write_value_float)
  result.write_ok = write_ok
  if not result.write_ok then
    result.execution_failure_class = write_failure_class or "write_failed"
    return result
  end

  local readback_pattern_ok, readback_pattern = read_u32(addr)
  if readback_pattern_ok then
    result.readback_pattern = readback_pattern
  end
  local readback_float_ok, readback_float = read_f32(addr)
  if readback_float_ok then
    result.readback_float = readback_float
    result.readback_delta = readback_float - write_value_float
    result.readback_ok = math.abs(result.readback_delta) <= cfg.readback_tolerance
  end

  if result.readback_ok ~= true then
    result.execution_failure_class = "readback_mismatch"
  end
  return result
end

_G.MVP0ValueExecutor = Executor
return Executor
