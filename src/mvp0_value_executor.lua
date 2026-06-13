local Executor = {}

Executor.VERSION = "dry_run_v1"

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

local function number_default(value, default_value)
  local numeric = tonumber(value)
  if numeric == nil then
    return default_value
  end
  return numeric
end

local function get_config(opts)
  local cfg = opts and opts.config or {}
  return {
    execution_mode = text_default(cfg.execution_mode, DEFAULTS.execution_mode),
    write_enabled = bool_default(cfg.write_enabled, DEFAULTS.write_enabled),
    write_value_float = cfg.write_value_float,
    write_value_pattern = cfg.write_value_pattern,
    write_method = text_default(cfg.write_method, DEFAULTS.write_method),
    execution_addr_source = text_default(cfg.execution_addr_source, DEFAULTS.execution_addr_source),
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
    execution_addr = nil,
    execution_addr_source = cfg.execution_addr_source,
    execution_preconditions_ok = false,
    execution_failure_class = nil,
    known_true_match_ok = nil,
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
    rollback_available = false,
    executor_version = Executor.VERSION,
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

  if cfg.execution_mode == "write" and cfg.write_enabled == true then
    return fail(result, "write_not_supported_in_v1")
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

  local addr = resolve_execution_addr(summary, cfg.execution_addr_source)
  result.execution_addr = addr
  if type(addr) ~= "number" then
    return fail(result, "missing_execution_addr")
  end

  local stable_rank = tonumber(summary.stable_intersection_known_true_rank_position)
  if stable_rank ~= 1 then
    return fail(result, "stable_rank_not_1")
  end

  local known_true_addr = opts.known_true_addr or summary.known_true_addr
  if type(known_true_addr) == "number" then
    result.known_true_match_ok = addr == known_true_addr
    if cfg.require_known_true_match and not result.known_true_match_ok then
      return fail(result, "known_true_mismatch")
    end
  end

  local read_ok, old_pattern = read_u32(addr)
  result.old_value_read_ok = read_ok
  result.old_value_pattern = old_pattern
  local float_ok, old_float = read_f32(addr)
  if float_ok then
    result.old_value_float = old_float
  end

  if not read_ok then
    return fail(result, "old_value_read_failed")
  end

  local target_pattern = u32(result.target_value_pattern)
  if cfg.require_old_value_match and target_pattern ~= nil and old_pattern ~= target_pattern then
    return fail(result, "old_value_mismatch")
  end

  if cfg.execution_mode == "write" then
    return fail(result, "write_disabled")
  end

  result.execution_preconditions_ok = true
  return result
end

_G.MVP0ValueExecutor = Executor
return Executor
