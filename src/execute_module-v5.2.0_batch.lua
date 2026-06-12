-- execute_module-v5.2.0
-- Batch no-probe / with-probe runner with automatic log persistence.

local REPORT_MODULE_PATH = [[D:\Lua Developer\mvp0_candidate_report.lua]]
local COLLECTOR_MODULE_PATH = [[D:\Lua Developer\mvp0_foundlist_collector.lua]]
local OUTPUT_DIR = [[D:\armedforces.io-v2\log\auto_output]]
local LOCAL_CASE_CONFIG_PATH = [[D:\Lua Developer\src\run_case_config.local.lua]]

local MODE_PRESETS = {
  no_probe = {
    mode = "no_probe",
    probe_full_foundlist = false,
  },
  no_probe_A = {
    mode = "no_probe_A",
    probe_full_foundlist = false,
  },
  with_probe = {
    mode = "with_probe",
    probe_full_foundlist = true,
  },
  no_probe_B = {
    mode = "no_probe_B",
    probe_full_foundlist = false,
  },
}

local function file_exists(path)
  local handle = io.open(path, "r")
  if handle ~= nil then
    handle:close()
    return true
  end
  return false
end

local function parse_case_number(value, field_name)
  if value == nil then
    return nil
  end
  if type(value) == "number" then
    return value
  end
  if type(value) == "string" then
    local text = value:gsub("^%s+", ""):gsub("%s+$", "")
    if text == "" then
      return nil
    end
    local numeric = tonumber(text)
    if numeric ~= nil then
      return numeric
    end
    local hex = text:match("^0[xX]([%da-fA-F]+)$")
    if hex ~= nil then
      local parsed = 0
      for i = 1, #hex do
        parsed = parsed * 16 + tonumber(hex:sub(i, i), 16)
      end
      return parsed
    end
  end
  error("invalid case config number for " .. tostring(field_name) .. ": " .. tostring(value))
end

local function parse_case_float(value, field_name)
  if value == nil then
    return nil
  end
  if type(value) == "number" then
    return value
  end
  if type(value) == "string" then
    local numeric = tonumber(value)
    if numeric ~= nil then
      return numeric
    end
  end
  error("invalid case config float for " .. tostring(field_name) .. ": " .. tostring(value))
end

local function normalize_diagnostic_level(value)
  local level = tostring(value or "basic"):lower()
  if level == "basic" or level == "debug" or level == "trace" then
    return level
  end
  error("invalid diagnostic_level: " .. tostring(value))
end

local function apply_local_case_config(run_cases, path)
  for _, case_cfg in ipairs(run_cases or {}) do
    case_cfg.case_config_loaded = false
    case_cfg.case_config_path = path
    case_cfg.known_true_addr_source = "default"
    case_cfg.target_value_source = "default"
    case_cfg.diagnostic_level = normalize_diagnostic_level(case_cfg.diagnostic_level)
  end

  if not file_exists(path) then
    return run_cases
  end

  local loaded = dofile(path)
  if type(loaded) ~= "table" then
    error("case config must return a table: " .. tostring(path))
  end

  local case_cfg = run_cases[1]
  if case_cfg == nil then
    error("case config cannot be applied because RUN_CASES is empty")
  end

  case_cfg.case_config_loaded = true
  if loaded.case_id ~= nil then
    case_cfg.case_id = tostring(loaded.case_id)
  end
  if loaded.known_true_addr ~= nil then
    case_cfg.known_true_addr = parse_case_number(loaded.known_true_addr, "known_true_addr")
    case_cfg.known_true_addr_source = "local"
  end
  if loaded.target_value_addr ~= nil then
    case_cfg.target_value_addr = parse_case_number(loaded.target_value_addr, "target_value_addr")
    case_cfg.target_value_source = "local"
  end
  if loaded.target_value_pattern ~= nil then
    case_cfg.target_value_pattern = parse_case_number(loaded.target_value_pattern, "target_value_pattern")
    case_cfg.target_value_source = "local"
  end
  if loaded.target_value_float ~= nil then
    case_cfg.target_value_float = parse_case_float(loaded.target_value_float, "target_value_float")
    case_cfg.target_value_source = "local"
  end
  if loaded.diagnostic_level ~= nil then
    case_cfg.diagnostic_level = normalize_diagnostic_level(loaded.diagnostic_level)
  end

  return run_cases
end

local RUN_CASES = {
  {
    case_id = "case_01",
    session_id = "collector-retest-wide-2",
    known_true_addr = nil,
    target_value_pattern = 0x42C80000,
    target_value_float = 100.0,
    max_candidates = 100,
    scan_budget = 8000,
    filter_target_match = true,
    use_prescore_selection = true,
    stable_filter_intersection_enabled = false,
    diagnostic_level = "basic",
    modes = {
      {name = "no_probe_A", probe_full_foundlist = false},
      {name = "with_probe", probe_full_foundlist = true},
      {name = "no_probe_B", probe_full_foundlist = false},
    },
  },
}

RUN_CASES = apply_local_case_config(RUN_CASES, LOCAL_CASE_CONFIG_PATH)

local original_print = print
local active_log_lines = nil
local console_print_total_ms = 0

local function stringify(...)
  local parts = {}
  for i = 1, select("#", ...) do
    parts[#parts + 1] = tostring(select(i, ...))
  end
  return table.concat(parts, "\t")
end

print = function(...)
  if active_log_lines ~= nil then
    active_log_lines[#active_log_lines + 1] = stringify(...)
  end
  local print_start_ms = os.clock() * 1000
  original_print(...)
  console_print_total_ms = console_print_total_ms + math.floor(((os.clock() * 1000) - print_start_ms) + 0.5)
end

local function ensure_directory(path)
  os.execute(string.format('cmd /c if not exist "%s" mkdir "%s"', path, path))
end

local function sanitize_token(value)
  local text = tostring(value or "nil")
  text = text:gsub("[^%w%-_]+", "_")
  text = text:gsub("_+", "_")
  text = text:gsub("^_", "")
  text = text:gsub("_$", "")
  if text == "" then
    return "nil"
  end
  return text
end

local function now_ms()
  return os.clock() * 1000
end

local function elapsed_ms(start_ms)
  if start_ms == nil then
    return nil
  end
  return math.floor((now_ms() - start_ms) + 0.5)
end

local function timing_value(value)
  return tonumber(value) or 0
end

local function compute_known_timed_ms(summary)
  return timing_value(summary.mode_config_ms)
    + timing_value(summary.runner_setup_ms)
    + timing_value(summary.collector_call_ms)
    + timing_value(summary.report_render_ms)
    + timing_value(summary.file_write_ms)
    + timing_value(summary.stable_intersection_build_ms)
end

local function finalize_timing_summary(summary)
  if summary == nil then
    return nil
  end

  summary.mode_total_ms = summary.total_ms
  summary.known_timed_ms = compute_known_timed_ms(summary)
  if summary.mode_total_ms ~= nil then
    summary.uninstrumented_gap_ms = summary.mode_total_ms - summary.known_timed_ms
    if summary.mode_total_ms ~= 0 then
      summary.uninstrumented_gap_ratio = summary.uninstrumented_gap_ms / summary.mode_total_ms
    else
      summary.uninstrumented_gap_ratio = nil
    end
  else
    summary.uninstrumented_gap_ms = nil
    summary.uninstrumented_gap_ratio = nil
  end

  return summary
end

local function hex_u64(value)
  if value == nil then
    return "nil"
  end
  return string.format("0x%X", value)
end

local function copy_array(values)
  local copied = {}
  for i, value in ipairs(values or {}) do
    copied[i] = value
  end
  return copied
end

local function get_best_candidate_addr(result)
  local best = result and result.best or nil
  return best and best.candidate and best.candidate.value_addr or nil
end

local function known_true_needs_diagnostics(bundle, result, known_true_addr)
  if known_true_addr == nil then
    return false
  end
  if bundle == nil then
    return true
  end
  if bundle.raw_count == 0 or bundle.true_in_raw == false or bundle.true_in_unique == false then
    return true
  end
  if bundle.true_in_filtered == false or bundle.true_in_prescored == false or bundle.true_in_selected == false then
    return true
  end
  local rank = (bundle and bundle.known_true_rank_position) or (result and result.known_true_rank_position)
  if rank ~= nil and rank ~= 1 then
    return true
  end
  local best_addr = get_best_candidate_addr(result)
  return best_addr ~= nil and best_addr ~= known_true_addr
end

local function filter_truth_probe_logs(logs, diagnostic_level, include_detail)
  if diagnostic_level == "trace" or include_detail then
    return logs
  end
  if type(logs) ~= "table" then
    return logs
  end

  local filtered = {}
  for _, line in ipairs(logs) do
    local text = tostring(line)
    if not text:find("%[filter_known_true%]") and not text:find("%[filter_mismatch_sample%]") then
      filtered[#filtered + 1] = line
    end
  end
  return filtered
end

local function make_report_policy(compact_enabled, skipped_sections, verbose_section_count)
  return {
    compact_report_enabled = compact_enabled,
    skipped_verbose_report_sections = skipped_sections,
    verbose_report_section_count = verbose_section_count,
  }
end

local function should_emit_verbose_bundle_report(case_cfg, bundle, result)
  if case_cfg.diagnostic_level == "trace" then
    return true
  end
  if known_true_needs_diagnostics(bundle, result, case_cfg.known_true_addr) then
    return true
  end
  if case_cfg.diagnostic_level == "debug" and (bundle == nil or bundle.raw_count == 0) then
    return true
  end
  return false
end

local function should_emit_verbose_stable_report(case_cfg, summary)
  if case_cfg.diagnostic_level == "trace" then
    return true
  end
  if summary == nil then
    return true
  end
  if summary.stable_intersection_true_in_filtered == false then
    return true
  end
  if summary.stable_intersection_known_true_rank_position ~= nil and summary.stable_intersection_known_true_rank_position ~= 1 then
    return true
  end
  if summary.stable_intersection_best_candidate ~= nil and case_cfg.known_true_addr ~= nil
      and summary.stable_intersection_best_candidate ~= case_cfg.known_true_addr then
    return true
  end
  if case_cfg.diagnostic_level == "debug" and (summary.run_valid == false or summary.collector_empty == true) then
    return true
  end
  return false
end

local function build_address_set(addresses)
  local set = {}
  for _, addr in ipairs(addresses or {}) do
    set[addr] = true
  end
  return set
end

local function collect_unique_only(source_addresses, other_a_addresses, other_b_addresses, limit)
  local source_set = build_address_set(source_addresses)
  local other_a_set = build_address_set(other_a_addresses)
  local other_b_set = build_address_set(other_b_addresses)
  local sample = {}

  for _, addr in ipairs(source_addresses or {}) do
    if source_set[addr] and not other_a_set[addr] and not other_b_set[addr] then
      sample[#sample + 1] = addr
      if limit ~= nil and #sample >= limit then
        break
      end
    end
  end

  return sample
end

local function format_address_sample(addresses)
  if addresses == nil or #addresses == 0 then
    return "empty"
  end

  local parts = {}
  for _, addr in ipairs(addresses) do
    parts[#parts + 1] = hex_u64(addr)
  end
  return table.concat(parts, ", ")
end

local function compute_match_overlap_counts(a_addresses, w_addresses, b_addresses)
  local counts = {}
  for _, addresses in ipairs({a_addresses or {}, w_addresses or {}, b_addresses or {}}) do
    local seen_in_run = {}
    for _, addr in ipairs(addresses) do
      if not seen_in_run[addr] then
        counts[addr] = (counts[addr] or 0) + 1
        seen_in_run[addr] = true
      end
    end
  end

  local result = {
    matched_in_all_three_count = 0,
    matched_in_any_two_count = 0,
    matched_unique_to_each_count = 0,
  }

  for _, count in pairs(counts) do
    if count == 3 then
      result.matched_in_all_three_count = result.matched_in_all_three_count + 1
    elseif count == 2 then
      result.matched_in_any_two_count = result.matched_in_any_two_count + 1
    elseif count == 1 then
      result.matched_unique_to_each_count = result.matched_unique_to_each_count + 1
    end
  end

  return result
end

local function collect_top_buckets(addresses, bucket_size, top_n)
  local counts = {}
  local ordered = {}

  for _, addr in ipairs(addresses or {}) do
    local bucket = math.floor(addr / bucket_size) * bucket_size
    if counts[bucket] == nil then
      counts[bucket] = 0
      ordered[#ordered + 1] = bucket
    end
    counts[bucket] = counts[bucket] + 1
  end

  table.sort(ordered, function(a, b)
    if counts[a] ~= counts[b] then
      return counts[a] > counts[b]
    end
    return a < b
  end)

  local top = {}
  for i = 1, math.min(top_n or 5, #ordered) do
    local bucket = ordered[i]
    top[#top + 1] = {
      bucket = bucket,
      count = counts[bucket],
    }
  end

  return top
end

local function format_bucket_entries(entries)
  if entries == nil or #entries == 0 then
    return "empty"
  end

  local parts = {}
  for _, entry in ipairs(entries) do
    parts[#parts + 1] = string.format("%s(%d)", hex_u64(entry.bucket), entry.count)
  end
  return table.concat(parts, ", ")
end

local function collect_dominant_delta_candidates(left_addresses, right_addresses, pair_limit)
  local delta_counts = {}
  local delta_pairs = {}
  local left_limit = math.min(#(left_addresses or {}), pair_limit or 32)
  local right_limit = math.min(#(right_addresses or {}), pair_limit or 32)

  for i = 1, left_limit do
    local left = left_addresses[i]
    for j = 1, right_limit do
      local right = right_addresses[j]
      local delta = right - left
      delta_counts[delta] = (delta_counts[delta] or 0) + 1
      if delta_pairs[delta] == nil then
        delta_pairs[delta] = {}
      end
      local pairs = delta_pairs[delta]
      if #pairs < 5 then
        pairs[#pairs + 1] = { left = left, right = right }
      end
    end
  end

  local deltas = {}
  for delta, count in pairs(delta_counts) do
    if delta ~= 0 then
      deltas[#deltas + 1] = {
        delta = delta,
        count = count,
        pairs = delta_pairs[delta],
      }
    end
  end

  table.sort(deltas, function(a, b)
    if a.count ~= b.count then
      return a.count > b.count
    end
    return a.delta < b.delta
  end)

  local top = {}
  for i = 1, math.min(3, #deltas) do
    top[#top + 1] = deltas[i]
  end
  return top
end

local function format_delta_candidates(candidates)
  if candidates == nil or #candidates == 0 then
    return "none"
  end

  local lines = {}
  for _, candidate in ipairs(candidates) do
    local pair_parts = {}
    for _, pair in ipairs(candidate.pairs or {}) do
      pair_parts[#pair_parts + 1] = string.format("%s->%s", hex_u64(pair.left), hex_u64(pair.right))
    end
    lines[#lines + 1] = string.format(
      "delta=%s hits=%d samples=%s",
      hex_u64(candidate.delta),
      candidate.count,
      (#pair_parts > 0) and table.concat(pair_parts, ", ") or "none"
    )
  end
  return table.concat(lines, " | ")
end

local function build_interpretation_hints(only_with_probe, only_no_probe_b, page_top_with_probe, page_top_no_probe_b, delta_candidates)
  local hints = {}
  local with_probe_count = #(only_with_probe or {})
  local no_probe_b_count = #(only_no_probe_b or {})

  if with_probe_count > 0 and page_top_with_probe[1] ~= nil and page_top_with_probe[1].count >= math.max(4, math.floor(with_probe_count * 0.25)) then
    hints[#hints + 1] = "matched_only_in_with_probe clusters in a small set of pages"
  end
  if no_probe_b_count > 0 and page_top_no_probe_b[1] ~= nil and page_top_no_probe_b[1].count >= math.max(4, math.floor(no_probe_b_count * 0.25)) then
    hints[#hints + 1] = "matched_only_in_no_probe_B clusters in a small set of pages"
  end
  if delta_candidates ~= nil and delta_candidates[1] ~= nil and delta_candidates[1].count >= 4 then
    hints[#hints + 1] = "pattern is consistent with a repeated address delta between with_probe and no_probe_B samples"
  end
  if #hints == 0 then
    hints[1] = "pattern does not show a single dominant explanation from this lightweight pass"
  end
  return table.concat(hints, "; ")
end

local function build_pass_interpretation_hint(pass1_only, pass2_only, page_top_pass1, page_top_pass2)
  local hints = {}
  local pass1_count = #(pass1_only or {})
  local pass2_count = #(pass2_only or {})

  if pass1_count > 0 and page_top_pass1[1] ~= nil and page_top_pass1[1].count >= math.max(4, math.floor(pass1_count * 0.25)) then
    hints[#hints + 1] = "pass1-only matches cluster in a small set of pages"
  end
  if pass2_count > 0 and page_top_pass2[1] ~= nil and page_top_pass2[1].count >= math.max(4, math.floor(pass2_count * 0.25)) then
    hints[#hints + 1] = "pass2-only matches cluster in a small set of pages"
  end
  if #hints == 0 then
    hints[1] = "pass1/pass2-only samples do not show a single dominant explanation from this lightweight pass"
  end
  return table.concat(hints, "; ")
end

local function count_set_members(set)
  local count = 0
  for _, enabled in pairs(set or {}) do
    if enabled then
      count = count + 1
    end
  end
  return count
end

local function collect_intersection_addresses(left_addresses, right_addresses, limit)
  local right_set = build_address_set(right_addresses)
  local seen = {}
  local intersection = {}

  for _, addr in ipairs(left_addresses or {}) do
    if right_set[addr] and not seen[addr] then
      seen[addr] = true
      intersection[#intersection + 1] = addr
      if limit ~= nil and #intersection >= limit then
        break
      end
    end
  end

  return intersection
end

local function build_no_probe_intersection_hint(a_only, b_only, intersection, page_top_a_only, page_top_b_only, page_top_intersection)
  local hints = {}
  local a_only_count = #(a_only or {})
  local b_only_count = #(b_only or {})
  local intersection_count = #(intersection or {})

  if intersection_count > 0 and intersection_count >= math.max(a_only_count, b_only_count) then
    hints[#hints + 1] = "stable intersection preserves a larger core set than either drifting edge set"
  end
  if a_only_count > 0 and b_only_count > 0
    and page_top_a_only[1] ~= nil and page_top_b_only[1] ~= nil
    and page_top_a_only[1].count >= math.max(4, math.floor(a_only_count * 0.25))
    and page_top_b_only[1].count >= math.max(4, math.floor(b_only_count * 0.25)) then
    hints[#hints + 1] = "A_only and B_only are heavily clustered in disjoint page groups"
  elseif a_only_count > 0 and page_top_a_only[1] ~= nil and page_top_a_only[1].count >= math.max(4, math.floor(a_only_count * 0.25)) then
    hints[#hints + 1] = "A_only clusters in a small set of pages"
  elseif b_only_count > 0 and page_top_b_only[1] ~= nil and page_top_b_only[1].count >= math.max(4, math.floor(b_only_count * 0.25)) then
    hints[#hints + 1] = "B_only clusters in a small set of pages"
  end
  if intersection_count > 0 and page_top_intersection[1] ~= nil and page_top_intersection[1].count >= math.max(4, math.floor(intersection_count * 0.25)) then
    hints[#hints + 1] = "stable intersection retains a concentrated page core"
  end
  if #hints == 0 then
    hints[1] = "no_probe_A/no_probe_B stable intersection does not yet suggest a single dominant pattern"
  end
  return table.concat(hints, "; ")
end

local function build_no_probe_snapshot_intersection_analysis(no_probe_a, no_probe_b)
  if no_probe_a == nil or no_probe_b == nil then
    return nil
  end

  local a_addresses = copy_array(no_probe_a.matched_addresses or {})
  local b_addresses = copy_array(no_probe_b.matched_addresses or {})
  table.sort(a_addresses)
  table.sort(b_addresses)

  local full_intersection = collect_intersection_addresses(b_addresses, a_addresses, nil)
  local full_a_only = collect_unique_only(a_addresses, b_addresses, {}, nil)
  local full_b_only = collect_unique_only(b_addresses, a_addresses, {}, nil)
  local intersection_sample = collect_intersection_addresses(b_addresses, a_addresses, 20)
  local a_only_sample = collect_unique_only(a_addresses, b_addresses, {}, 20)
  local b_only_sample = collect_unique_only(b_addresses, a_addresses, {}, 20)
  local union_set = build_address_set(a_addresses)
  local intersection_set = build_address_set(full_intersection)
  local known_true_addr = no_probe_a.known_true_addr or no_probe_b.known_true_addr

  for _, addr in ipairs(b_addresses) do
    union_set[addr] = true
  end

  local page_top_a_only = collect_top_buckets(full_a_only, 0x1000, 5)
  local page_top_b_only = collect_top_buckets(full_b_only, 0x1000, 5)
  local page_top_intersection = collect_top_buckets(full_intersection, 0x1000, 5)
  local region_top_a_only = collect_top_buckets(full_a_only, 0x10000, 5)
  local region_top_b_only = collect_top_buckets(full_b_only, 0x10000, 5)
  local region_top_intersection = collect_top_buckets(full_intersection, 0x10000, 5)
  local segment_top_a_only = collect_top_buckets(full_a_only, 0x100000, 5)
  local segment_top_b_only = collect_top_buckets(full_b_only, 0x100000, 5)
  local segment_top_intersection = collect_top_buckets(full_intersection, 0x100000, 5)

  -- [stable-intersection-analysis]
  return {
    delayed_snapshot_intersection_enabled = true,
    delayed_snapshot_no_probe_stable_intersection_count = #full_intersection,
    delayed_snapshot_no_probe_union_count = count_set_members(union_set),
    delayed_snapshot_no_probe_A_only_count = #full_a_only,
    delayed_snapshot_no_probe_B_only_count = #full_b_only,
    full_intersection_addresses = full_intersection,
    delayed_snapshot_known_true_in_intersection = (known_true_addr ~= nil) and (intersection_set[known_true_addr] == true) or nil,
    matched_only_in_no_probe_A_vs_B = a_only_sample,
    matched_only_in_no_probe_B_vs_A = b_only_sample,
    matched_in_no_probe_intersection = intersection_sample,
    page_cluster_summary_no_probe_A_only = page_top_a_only,
    page_cluster_summary_no_probe_B_only = page_top_b_only,
    page_cluster_summary_no_probe_intersection = page_top_intersection,
    region_cluster_summary_no_probe_A_only = region_top_a_only,
    region_cluster_summary_no_probe_B_only = region_top_b_only,
    region_cluster_summary_no_probe_intersection = region_top_intersection,
    segment_cluster_summary_no_probe_A_only = segment_top_a_only,
    segment_cluster_summary_no_probe_B_only = segment_top_b_only,
    segment_cluster_summary_no_probe_intersection = segment_top_intersection,
    interpretation_hint = build_no_probe_intersection_hint(
      full_a_only,
      full_b_only,
      full_intersection,
      page_top_a_only,
      page_top_b_only,
      page_top_intersection
    ),
  }
end

local function build_runtime_empty_diagnostics(group)
  local mode_names = {"no_probe_A", "with_probe", "no_probe_B"}
  local empty_modes = {}
  local all_present = true
  local all_empty = true
  local mode_empty = {}

  for _, mode_name in ipairs(mode_names) do
    local summary = group and group[mode_name] or nil
    local is_empty = summary ~= nil and summary.raw_count == 0
    mode_empty[mode_name] = is_empty
    if summary == nil then
      all_present = false
    end
    if is_empty then
      empty_modes[#empty_modes + 1] = mode_name
    else
      all_empty = false
    end
  end

  local collector_empty = all_present and all_empty
  return {
    run_valid = not collector_empty,
    failure_class = collector_empty and "collector_runtime_empty" or nil,
    collector_empty = collector_empty,
    empty_modes = (#empty_modes > 0) and table.concat(empty_modes, ", ") or "none",
    recommendation = collector_empty and "INVALID_RUNTIME_SAMPLE" or nil,
    no_probe_A_collector_empty = mode_empty.no_probe_A,
    with_probe_collector_empty = mode_empty.with_probe,
    no_probe_B_collector_empty = mode_empty.no_probe_B,
  }
end

local function apply_runtime_empty_diagnostics(summary, diagnostics)
  if summary == nil or diagnostics == nil then
    return
  end

  summary.run_valid = diagnostics.run_valid
  summary.failure_class = diagnostics.failure_class
  summary.collector_empty = diagnostics.collector_empty
  summary.empty_modes = diagnostics.empty_modes
  summary.recommendation = diagnostics.recommendation
  summary.no_probe_A_collector_empty = diagnostics.no_probe_A_collector_empty
  summary.with_probe_collector_empty = diagnostics.with_probe_collector_empty
  summary.no_probe_B_collector_empty = diagnostics.no_probe_B_collector_empty
end

local function get_runtime_diagnostic(diagnostics, key)
  if diagnostics == nil then
    return nil
  end
  return diagnostics[key]
end

local function write_text_file(path, text)
  local fh, err = io.open(path, "wb")
  if not fh then
    error("failed to open output file: " .. tostring(path) .. " (" .. tostring(err) .. ")")
  end
  fh:write(text)
  fh:close()
end

local function print_func_source(name, fn)
  if type(fn) ~= "function" then
    print(string.format("[FUNC] %s = %s", name, tostring(fn)))
    return
  end

  local info = debug.getinfo(fn, "S")
  print(string.format(
    "[FUNC] %s -> source=%s line=%s",
    name,
    tostring(info and info.short_src),
    tostring(info and info.linedefined)
  ))
end

local function print_kv(label, value)
  print(string.format("%-30s = %s", label, tostring(value)))
end

local function print_hex_kv(label, value)
  if value == nil then
    print_kv(label, nil)
  else
    print(string.format("%-30s = 0x%X", label, value))
  end
end

local function print_log_table(title, t)
  print("=== " .. title .. " ===")

  if t == nil then
    print("nil")
    return
  end

  if type(t) ~= "table" then
    print(tostring(t))
    return
  end

  local has_array_items = false
  for i, v in ipairs(t) do
    has_array_items = true
    print(string.format("%02d: %s", i, tostring(v)))
  end

  if not has_array_items then
    local keys = {}
    for k, _ in pairs(t) do
      keys[#keys + 1] = k
    end

    table.sort(keys, function(a, b)
      return tostring(a) < tostring(b)
    end)

    for _, k in ipairs(keys) do
      print(tostring(k) .. " = " .. tostring(t[k]))
    end
  end
end

local function print_report_policy(policy)
  print("=== report_render_policy ===")
  print_kv("compact_report_enabled", policy and policy.compact_report_enabled)
  print_kv("skipped_verbose_report_sections", policy and policy.skipped_verbose_report_sections)
  print_kv("verbose_report_section_count", policy and policy.verbose_report_section_count)
end

local function pick_known_true_field(bundle, result, name)
  if bundle and bundle[name] ~= nil then
    return bundle[name]
  end
  if result and result[name] ~= nil then
    return result[name]
  end
  return nil
end

local function load_modules()
  MVP0 = nil
  MVP0FoundList = nil
  collectgarbage()

  dofile(REPORT_MODULE_PATH)
  dofile(COLLECTOR_MODULE_PATH)

  print_func_source("MVP0.score_base_candidate", MVP0 and MVP0.score_base_candidate)
  print_func_source("MVP0.apply_rank_adjustments", MVP0 and MVP0.apply_rank_adjustments)
  print_func_source("MVP0.render_report", MVP0 and MVP0.render_report)
  print_func_source("MVP0.compute_one_sided_anchorless_split_penalty", MVP0 and MVP0.compute_one_sided_anchorless_split_penalty)
end

local function get_filter_debug_snapshot()
  local debug_info = MVP0FoundList and MVP0FoundList.LAST_FILTER_DEBUG or nil
  if type(debug_info) ~= "table" then
    return nil
  end

  return {
    unique_count = debug_info.unique_count,
    matched_count = debug_info.matched_count,
    value_mismatch_count = debug_info.value_mismatch_count,
    read_failed_count = debug_info.read_failed_count,
    filter_ms = debug_info.filter_ms,
    prescore_ms = debug_info.prescore_ms,
    prescore_read_ms = debug_info.prescore_read_ms,
    prescore_score_ms = debug_info.prescore_score_ms,
    prescore_sort_ms = debug_info.prescore_sort_ms,
    prescore_select_ms = debug_info.prescore_select_ms,
    prescore_detail_ms = debug_info.prescore_detail_ms,
    retry_recovered_count = debug_info.retry_recovered_count,
    retry_still_mismatch_count = debug_info.retry_still_mismatch_count,
    retry_read_failed_count = debug_info.retry_read_failed_count,
    delayed_recheck_enabled = debug_info.delayed_recheck_enabled,
    delayed_recheck_candidate_count = debug_info.delayed_recheck_candidate_count,
    delayed_recovered_count = debug_info.delayed_recovered_count,
    delayed_still_mismatch_count = debug_info.delayed_still_mismatch_count,
    delayed_read_failed_count = debug_info.delayed_read_failed_count,
    stable_intersection_enabled = debug_info.stable_intersection_enabled,
    pass1_matched_count = debug_info.pass1_matched_count,
    pass2_matched_count = debug_info.pass2_matched_count,
    intersection_filtered_count = debug_info.intersection_filtered_count,
    pass1_only_count = debug_info.pass1_only_count,
    pass2_only_count = debug_info.pass2_only_count,
    pass1_read_failed_count = debug_info.pass1_read_failed_count,
    pass2_read_failed_count = debug_info.pass2_read_failed_count,
    pass1_matched_addresses = copy_array(debug_info.pass1_matched_addresses),
    pass2_matched_addresses = copy_array(debug_info.pass2_matched_addresses),
    pass1_only_addresses = copy_array(debug_info.pass1_only_addresses),
    pass2_only_addresses = copy_array(debug_info.pass2_only_addresses),
    matched_addresses = copy_array(debug_info.matched_addresses),
    stable_snapshot_A_ms = debug_info.stable_snapshot_A_ms,
    stable_snapshot_B_ms = debug_info.stable_snapshot_B_ms,
    stable_intersection_build_ms = debug_info.stable_intersection_build_ms,
  }
end

local function emit_compact_bundle_report(case_cfg, mode_cfg, bundle, policy)
  local result = (bundle and bundle.result) or {}
  local best = result and result.best or nil
  local collector_empty = bundle and bundle.raw_count == 0
  local run_valid = bundle and bundle.raw_count ~= nil and bundle.raw_count ~= 0
  local rank_position = pick_known_true_field(bundle, result, "known_true_rank_position")

  print("=== compact_report ===")
  print_kv("case_id", case_cfg.case_id)
  print_kv("case_config_loaded", case_cfg.case_config_loaded)
  print_kv("case_config_path", case_cfg.case_config_path)
  print_kv("known_true_addr_source", case_cfg.known_true_addr_source)
  print_kv("target_value_source", case_cfg.target_value_source)
  print_kv("diagnostic_level", case_cfg.diagnostic_level)
  print_kv("session_id", case_cfg.session_id)
  print_kv("mode", mode_cfg.mode)
  print_hex_kv("known_true_addr", case_cfg.known_true_addr)
  print_hex_kv("target_value_addr", case_cfg.target_value_addr)
  print_hex_kv("target_value_pattern", case_cfg.target_value_pattern)
  print_kv("target_value_float", case_cfg.target_value_float)
  print_kv("run_valid", run_valid)
  print_kv("failure_class", collector_empty and "collector_runtime_empty" or nil)
  print_kv("collector_empty", collector_empty)
  print_kv("true_in_raw", bundle and bundle.true_in_raw)
  print_kv("true_in_unique", bundle and bundle.true_in_unique)
  print_kv("true_in_filtered", bundle and bundle.true_in_filtered)
  print_kv("true_in_prescored", bundle and bundle.true_in_prescored)
  print_kv("true_in_selected", bundle and bundle.true_in_selected)
  print_kv("rank_position", rank_position)
  print_kv("known_true_rank_position", rank_position)
  print_hex_kv("best_candidate", best and best.candidate and best.candidate.value_addr or nil)
  print_kv("best_score", result and result.best and result.best.score or nil)
  print_kv("second_score", result and result.second and result.second.score or nil)
  print_kv("score_gap", result and result.score_gap or nil)
  print_kv("recommendation", result and result.final_decision and result.final_decision.action or nil)
  print_kv("raw_count", bundle and bundle.raw_count)
  print_kv("unique_count", bundle and bundle.unique_count)
  print_kv("filtered_count", bundle and bundle.filtered_count)
  print_kv("prescored_count", bundle and bundle.prescored_count)
  print_kv("selected_count", bundle and bundle.selected_count)
  print_report_policy(policy)
end

local function emit_bundle_report(case_cfg, mode_cfg, bundle, policy)
  local result = (bundle and bundle.result) or {}

  print("=== run_config ===")
  print_kv("case_id", case_cfg.case_id)
  print_kv("case_config_loaded", case_cfg.case_config_loaded)
  print_kv("case_config_path", case_cfg.case_config_path)
  print_kv("known_true_addr_source", case_cfg.known_true_addr_source)
  print_kv("target_value_source", case_cfg.target_value_source)
  print_kv("diagnostic_level", case_cfg.diagnostic_level)
  print_kv("session_id", case_cfg.session_id)
  print_kv("mode", mode_cfg.mode)
  print_hex_kv("known_true_addr", case_cfg.known_true_addr)
  print_hex_kv("target_value_addr", case_cfg.target_value_addr)
  print_hex_kv("target_value_pattern", case_cfg.target_value_pattern)
  print_kv("target_value_float", case_cfg.target_value_float)
  print_kv("probe_full_foundlist", mode_cfg.probe_full_foundlist)

  print("=== collector_stats ===")
  print_kv("raw_count", bundle and bundle.raw_count)
  print_kv("scanned_count", bundle and bundle.scanned_count)
  print_kv("unique_count", bundle and bundle.unique_count)
  print_kv("filtered_count", bundle and bundle.filtered_count)
  print_kv("prescored_count", bundle and bundle.prescored_count)
  print_kv("selected_count", bundle and bundle.selected_count)
  print_kv("selection_strategy", bundle and bundle.selection_strategy)

  print("=== truth_probe_flags ===")
  print_kv("true_in_full_foundlist_checked", bundle and bundle.true_in_full_foundlist_checked)
  print_kv("true_in_full_foundlist", bundle and bundle.true_in_full_foundlist)
  print_kv("true_in_full_foundlist_observed", bundle and bundle.true_in_full_foundlist_observed)
  print_kv("true_in_raw", bundle and bundle.true_in_raw)
  print_kv("true_in_unique", bundle and bundle.true_in_unique)
  print_kv("true_in_filtered", bundle and bundle.true_in_filtered)
  print_kv("true_in_prescored", bundle and bundle.true_in_prescored)
  print_kv("true_in_selected", bundle and bundle.true_in_selected)

  print("=== extra_probe_debug ===")
  print_hex_kv("known_true_addr", case_cfg.known_true_addr)
  print_kv("true_foundlist_index", bundle and bundle.true_foundlist_index)
  print_kv("probe_window_radius", bundle and bundle.probe_window_radius)
  print_kv("raw_probe_full_foundlist_enabled", bundle and bundle.raw_probe_full_foundlist_enabled)
  print_kv("raw_probe_used", bundle and bundle.raw_probe_used)
  print_kv("known_true_raw_admission_path", bundle and bundle.known_true_raw_admission_path)

  print_log_table(
    "truth_probe_logs",
    filter_truth_probe_logs(bundle and bundle.truth_probe_logs, case_cfg.diagnostic_level, known_true_needs_diagnostics(bundle, result, case_cfg.known_true_addr))
  )

  print("=== known_true_debug ===")
  print_kv("known_true_rank_position", pick_known_true_field(bundle, result, "known_true_rank_position"))
  print_kv("known_true_base_score", pick_known_true_field(bundle, result, "known_true_base_score"))
  print_kv("known_true_final_score", pick_known_true_field(bundle, result, "known_true_final_score"))
  print_kv("known_true_tie_break_vector", pick_known_true_field(bundle, result, "known_true_tie_break_vector"))
  print_report_policy(policy)

  print("=== report_text ===")
  if result and result.report_text then
    print(result.report_text)
  else
    print("bundle.result.report_text = nil")
  end
end

local function build_run_summary(case_cfg, mode_cfg, bundle, log_path, filter_debug, timing)
  local result = (bundle and bundle.result) or {}
  local best = result and result.best or nil

  return {
    case_id = case_cfg.case_id,
    case_config_loaded = case_cfg.case_config_loaded,
    case_config_path = case_cfg.case_config_path,
    known_true_addr_source = case_cfg.known_true_addr_source,
    target_value_source = case_cfg.target_value_source,
    diagnostic_level = case_cfg.diagnostic_level,
    session_id = case_cfg.session_id,
    mode = mode_cfg.mode,
    probe_full_foundlist = mode_cfg.probe_full_foundlist,
    known_true_addr = case_cfg.known_true_addr,
    target_value_addr = case_cfg.target_value_addr,
    target_value_pattern = case_cfg.target_value_pattern,
    target_value_float = case_cfg.target_value_float,
    raw_count = bundle and bundle.raw_count,
    unique_count = bundle and bundle.unique_count,
    known_true_rank_position = pick_known_true_field(bundle, result, "known_true_rank_position"),
    known_true_final_score = pick_known_true_field(bundle, result, "known_true_final_score"),
    true_in_selected = bundle and bundle.true_in_selected,
    known_true_raw_admission_path = bundle and bundle.known_true_raw_admission_path,
    selected_count = bundle and bundle.selected_count,
    filtered_count = bundle and bundle.filtered_count,
    matched_count = filter_debug and filter_debug.matched_count or nil,
    value_mismatch_count = filter_debug and filter_debug.value_mismatch_count or nil,
    read_failed_count = filter_debug and filter_debug.read_failed_count or nil,
    mode_config_ms = timing and timing.mode_config_ms or nil,
    runner_setup_ms = timing and timing.runner_setup_ms or nil,
    collector_ms = timing and timing.collector_ms or nil,
    collector_call_ms = timing and timing.collector_call_ms or timing and timing.collector_ms or nil,
    filter_ms = filter_debug and filter_debug.filter_ms or nil,
    prescore_ms = filter_debug and filter_debug.prescore_ms or nil,
    prescore_read_ms = filter_debug and filter_debug.prescore_read_ms or nil,
    prescore_score_ms = filter_debug and filter_debug.prescore_score_ms or nil,
    prescore_sort_ms = filter_debug and filter_debug.prescore_sort_ms or nil,
    prescore_select_ms = filter_debug and filter_debug.prescore_select_ms or nil,
    prescore_detail_ms = filter_debug and filter_debug.prescore_detail_ms or nil,
    stable_intersection_ms = timing and timing.stable_intersection_ms or nil,
    stable_snapshot_A_ms = timing and timing.stable_snapshot_A_ms or filter_debug and filter_debug.stable_snapshot_A_ms or nil,
    stable_snapshot_B_ms = timing and timing.stable_snapshot_B_ms or filter_debug and filter_debug.stable_snapshot_B_ms or nil,
    stable_intersection_build_ms = timing and timing.stable_intersection_build_ms or filter_debug and filter_debug.stable_intersection_build_ms or nil,
    report_render_ms = timing and timing.report_render_ms or nil,
    compact_report_enabled = timing and timing.compact_report_enabled or false,
    skipped_verbose_report_sections = timing and timing.skipped_verbose_report_sections or "none",
    verbose_report_section_count = timing and timing.verbose_report_section_count or 0,
    stable_report_render_ms = timing and timing.stable_report_render_ms or nil,
    diagnostic_render_ms = timing and timing.diagnostic_render_ms or nil,
    console_print_ms = timing and timing.console_print_ms or nil,
    file_write_ms = timing and timing.file_write_ms or timing and timing.write_log_ms or nil,
    write_log_ms = timing and timing.write_log_ms or nil,
    total_ms = timing and timing.total_ms or nil,
    log_size_bytes = timing and timing.log_size_bytes or nil,
    retry_recovered_count = filter_debug and filter_debug.retry_recovered_count or nil,
    retry_still_mismatch_count = filter_debug and filter_debug.retry_still_mismatch_count or nil,
    retry_read_failed_count = filter_debug and filter_debug.retry_read_failed_count or nil,
    delayed_recheck_enabled = filter_debug and filter_debug.delayed_recheck_enabled or nil,
    delayed_recheck_candidate_count = filter_debug and filter_debug.delayed_recheck_candidate_count or nil,
    delayed_recovered_count = filter_debug and filter_debug.delayed_recovered_count or nil,
    delayed_still_mismatch_count = filter_debug and filter_debug.delayed_still_mismatch_count or nil,
    delayed_read_failed_count = filter_debug and filter_debug.delayed_read_failed_count or nil,
    stable_intersection_enabled = filter_debug and filter_debug.stable_intersection_enabled or nil,
    pass1_matched_count = filter_debug and filter_debug.pass1_matched_count or nil,
    pass2_matched_count = filter_debug and filter_debug.pass2_matched_count or nil,
    intersection_filtered_count = filter_debug and filter_debug.intersection_filtered_count or nil,
    pass1_only_count = filter_debug and filter_debug.pass1_only_count or nil,
    pass2_only_count = filter_debug and filter_debug.pass2_only_count or nil,
    pass1_read_failed_count = filter_debug and filter_debug.pass1_read_failed_count or nil,
    pass2_read_failed_count = filter_debug and filter_debug.pass2_read_failed_count or nil,
    pass1_matched_addresses = filter_debug and copy_array(filter_debug.pass1_matched_addresses) or {},
    pass2_matched_addresses = filter_debug and copy_array(filter_debug.pass2_matched_addresses) or {},
    pass1_only_addresses = filter_debug and copy_array(filter_debug.pass1_only_addresses) or {},
    pass2_only_addresses = filter_debug and copy_array(filter_debug.pass2_only_addresses) or {},
    matched_addresses = filter_debug and copy_array(filter_debug.matched_addresses) or {},
    best_candidate_addr = best and best.candidate and best.candidate.value_addr or nil,
    best_score = result and result.best and result.best.score or nil,
    second_score = result and result.second and result.second.score or nil,
    score_gap = result and result.score_gap or nil,
    confidence = result and result.confidence or nil,
    log_path = log_path,
  }
end

local function print_run_summary(summary)
  print("=== compact_summary ===")
  print_kv("case_id", summary.case_id)
  print_kv("case_config_loaded", summary.case_config_loaded)
  print_kv("case_config_path", summary.case_config_path)
  print_kv("known_true_addr_source", summary.known_true_addr_source)
  print_kv("target_value_source", summary.target_value_source)
  print_kv("diagnostic_level", summary.diagnostic_level)
  print_kv("session_id", summary.session_id)
  print_kv("mode", summary.mode)
  print_kv("run_valid", summary.run_valid)
  print_kv("failure_class", summary.failure_class)
  print_kv("collector_empty", summary.collector_empty)
  print_kv("empty_modes", summary.empty_modes)
  print_kv("recommendation", summary.recommendation)
  print_hex_kv("target_value_addr", summary.target_value_addr)
  print_hex_kv("target_value_pattern", summary.target_value_pattern)
  print_kv("target_value_float", summary.target_value_float)
  print_hex_kv("best_candidate_addr", summary.best_candidate_addr)
  print_kv("best_score", summary.best_score)
  print_kv("second_score", summary.second_score)
  print_kv("score_gap", summary.score_gap)
  print_kv("known_true_rank_position", summary.known_true_rank_position)
  print_kv("known_true_final_score", summary.known_true_final_score)
  print_kv("true_in_selected", summary.true_in_selected)
  print_kv("known_true_raw_admission_path", summary.known_true_raw_admission_path)
  print_kv("selected_count", summary.selected_count)
  print_kv("filtered_count", summary.filtered_count)
  print_kv("matched_count", summary.matched_count)
  print_kv("value_mismatch_count", summary.value_mismatch_count)
  print_kv("read_failed_count", summary.read_failed_count)
  print_kv("mode_total_ms", summary.mode_total_ms)
  print_kv("known_timed_ms", summary.known_timed_ms)
  print_kv("uninstrumented_gap_ms", summary.uninstrumented_gap_ms)
  print_kv("uninstrumented_gap_ratio", summary.uninstrumented_gap_ratio)
  print_kv("runner_setup_ms", summary.runner_setup_ms)
  print_kv("mode_config_ms", summary.mode_config_ms)
  print_kv("collector_call_ms", summary.collector_call_ms)
  print_kv("collector_ms", summary.collector_ms)
  print_kv("filter_ms", summary.filter_ms)
  print_kv("prescore_ms", summary.prescore_ms)
  print_kv("prescore_read_ms", summary.prescore_read_ms)
  print_kv("prescore_score_ms", summary.prescore_score_ms)
  print_kv("prescore_sort_ms", summary.prescore_sort_ms)
  print_kv("prescore_select_ms", summary.prescore_select_ms)
  print_kv("prescore_detail_ms", summary.prescore_detail_ms)
  print_kv("stable_intersection_ms", summary.stable_intersection_ms)
  print_kv("stable_snapshot_A_ms", summary.stable_snapshot_A_ms)
  print_kv("stable_snapshot_B_ms", summary.stable_snapshot_B_ms)
  print_kv("stable_intersection_build_ms", summary.stable_intersection_build_ms)
  print_kv("report_render_ms", summary.report_render_ms)
  print_kv("compact_report_enabled", summary.compact_report_enabled)
  print_kv("skipped_verbose_report_sections", summary.skipped_verbose_report_sections)
  print_kv("verbose_report_section_count", summary.verbose_report_section_count)
  print_kv("stable_report_render_ms", summary.stable_report_render_ms)
  print_kv("diagnostic_render_ms", summary.diagnostic_render_ms)
  print_kv("console_print_ms", summary.console_print_ms)
  print_kv("file_write_ms", summary.file_write_ms)
  print_kv("write_log_ms", summary.write_log_ms)
  print_kv("total_ms", summary.total_ms)
  print_kv("log_size_bytes", summary.log_size_bytes)
  print_kv("retry_recovered_count", summary.retry_recovered_count)
  print_kv("retry_still_mismatch_count", summary.retry_still_mismatch_count)
  print_kv("retry_read_failed_count", summary.retry_read_failed_count)
  print_kv("delayed_recheck_enabled", summary.delayed_recheck_enabled)
  print_kv("delayed_recheck_candidate_count", summary.delayed_recheck_candidate_count)
  print_kv("delayed_recovered_count", summary.delayed_recovered_count)
  print_kv("delayed_still_mismatch_count", summary.delayed_still_mismatch_count)
  print_kv("delayed_read_failed_count", summary.delayed_read_failed_count)
  print_kv("stable_intersection_enabled", summary.stable_intersection_enabled)
  print_kv("pass1_matched_count", summary.pass1_matched_count)
  print_kv("pass2_matched_count", summary.pass2_matched_count)
  print_kv("intersection_filtered_count", summary.intersection_filtered_count)
  print_kv("pass1_only_count", summary.pass1_only_count)
  print_kv("pass2_only_count", summary.pass2_only_count)
  -- [stable-intersection-print]
  if summary.stable_intersection_base_snapshot ~= nil then
    print_kv("stable_no_probe_intersection_enabled", summary.stable_no_probe_intersection_enabled)
    print_kv("stable_intersection_snapshot_A_filtered_count", summary.stable_intersection_snapshot_A_filtered_count)
    print_kv("stable_intersection_snapshot_B_filtered_count", summary.stable_intersection_snapshot_B_filtered_count)
    print_kv("stable_intersection_enabled", summary.stable_intersection_enabled)
    print_kv("stable_intersection_base_snapshot", summary.stable_intersection_base_snapshot)
    print_kv("stable_intersection_filtered_count", summary.stable_intersection_filtered_count)
    print_kv("stable_intersection_snapshot_A_only_count", summary.stable_intersection_snapshot_A_only_count)
    print_kv("stable_intersection_snapshot_B_only_count", summary.stable_intersection_snapshot_B_only_count)
    print_kv("stable_intersection_canonical_source_count", summary.stable_intersection_canonical_source_count)
    print_kv("stable_intersection_downstream_input_count", summary.stable_intersection_downstream_input_count)
    print_kv("stable_intersection_true_in_filtered", summary.stable_intersection_true_in_filtered)
    print_kv("stable_intersection_prescored_count", summary.stable_intersection_prescored_count)
    print_kv("stable_intersection_selected_count", summary.stable_intersection_selected_count)
    print_kv("stable_intersection_known_true_rank_position", summary.stable_intersection_known_true_rank_position)
    print_hex_kv("stable_intersection_best_candidate", summary.stable_intersection_best_candidate)
    print_kv("stable_intersection_best_score", summary.stable_intersection_best_score)
    print_kv("stable_intersection_second_score", summary.stable_intersection_second_score)
    print_kv("stable_intersection_score_gap", summary.stable_intersection_score_gap)
  end
  print_kv("confidence", summary.confidence)
  print_kv("log_path", summary.log_path)
end

local function render_summary_file(batch_id, summaries)
  local lines = {}
  lines[#lines + 1] = "=== Batch Summary ==="
  lines[#lines + 1] = "batch_id = " .. tostring(batch_id)
  lines[#lines + 1] = "output_dir = " .. tostring(OUTPUT_DIR)
  lines[#lines + 1] = ""

  for _, summary in ipairs(summaries) do
    lines[#lines + 1] = string.format("--- %s / %s ---", tostring(summary.session_id), tostring(summary.mode))
    lines[#lines + 1] = "case_id = " .. tostring(summary.case_id)
    lines[#lines + 1] = "case_config_loaded = " .. tostring(summary.case_config_loaded)
    lines[#lines + 1] = "case_config_path = " .. tostring(summary.case_config_path)
    lines[#lines + 1] = "known_true_addr_source = " .. tostring(summary.known_true_addr_source)
    lines[#lines + 1] = "target_value_source = " .. tostring(summary.target_value_source)
    lines[#lines + 1] = "diagnostic_level = " .. tostring(summary.diagnostic_level)
    lines[#lines + 1] = "known_true_addr = " .. tostring(hex_u64(summary.known_true_addr))
    lines[#lines + 1] = "probe_full_foundlist = " .. tostring(summary.probe_full_foundlist)
    lines[#lines + 1] = "run_valid = " .. tostring(summary.run_valid)
    lines[#lines + 1] = "failure_class = " .. tostring(summary.failure_class)
    lines[#lines + 1] = "collector_empty = " .. tostring(summary.collector_empty)
    lines[#lines + 1] = "empty_modes = " .. tostring(summary.empty_modes)
    lines[#lines + 1] = "recommendation = " .. tostring(summary.recommendation)
    lines[#lines + 1] = "no_probe_A_collector_empty = " .. tostring(summary.no_probe_A_collector_empty)
    lines[#lines + 1] = "with_probe_collector_empty = " .. tostring(summary.with_probe_collector_empty)
    lines[#lines + 1] = "no_probe_B_collector_empty = " .. tostring(summary.no_probe_B_collector_empty)
    lines[#lines + 1] = "target_value_addr = " .. tostring(hex_u64(summary.target_value_addr))
    lines[#lines + 1] = "target_value_pattern = " .. tostring(hex_u64(summary.target_value_pattern))
    lines[#lines + 1] = "target_value_float = " .. tostring(summary.target_value_float)
    lines[#lines + 1] = "best_candidate = " .. tostring(hex_u64(summary.best_candidate_addr))
    lines[#lines + 1] = "best_score = " .. tostring(summary.best_score)
    lines[#lines + 1] = "second_score = " .. tostring(summary.second_score)
    lines[#lines + 1] = "score_gap = " .. tostring(summary.score_gap)
    lines[#lines + 1] = "known_true_rank_position = " .. tostring(summary.known_true_rank_position)
    lines[#lines + 1] = "known_true_final_score = " .. tostring(summary.known_true_final_score)
    lines[#lines + 1] = "true_in_selected = " .. tostring(summary.true_in_selected)
    lines[#lines + 1] = "known_true_raw_admission_path = " .. tostring(summary.known_true_raw_admission_path)
    lines[#lines + 1] = "selected_count = " .. tostring(summary.selected_count)
    lines[#lines + 1] = "filtered_count = " .. tostring(summary.filtered_count)
    lines[#lines + 1] = "matched_count = " .. tostring(summary.matched_count)
    lines[#lines + 1] = "value_mismatch_count = " .. tostring(summary.value_mismatch_count)
    lines[#lines + 1] = "read_failed_count = " .. tostring(summary.read_failed_count)
    lines[#lines + 1] = "mode_total_ms = " .. tostring(summary.mode_total_ms)
    lines[#lines + 1] = "known_timed_ms = " .. tostring(summary.known_timed_ms)
    lines[#lines + 1] = "uninstrumented_gap_ms = " .. tostring(summary.uninstrumented_gap_ms)
    lines[#lines + 1] = "uninstrumented_gap_ratio = " .. tostring(summary.uninstrumented_gap_ratio)
    lines[#lines + 1] = "runner_setup_ms = " .. tostring(summary.runner_setup_ms)
    lines[#lines + 1] = "mode_config_ms = " .. tostring(summary.mode_config_ms)
    lines[#lines + 1] = "collector_call_ms = " .. tostring(summary.collector_call_ms)
    lines[#lines + 1] = "collector_ms = " .. tostring(summary.collector_ms)
    lines[#lines + 1] = "filter_ms = " .. tostring(summary.filter_ms)
    lines[#lines + 1] = "prescore_ms = " .. tostring(summary.prescore_ms)
    lines[#lines + 1] = "prescore_read_ms = " .. tostring(summary.prescore_read_ms)
    lines[#lines + 1] = "prescore_score_ms = " .. tostring(summary.prescore_score_ms)
    lines[#lines + 1] = "prescore_sort_ms = " .. tostring(summary.prescore_sort_ms)
    lines[#lines + 1] = "prescore_select_ms = " .. tostring(summary.prescore_select_ms)
    lines[#lines + 1] = "prescore_detail_ms = " .. tostring(summary.prescore_detail_ms)
    lines[#lines + 1] = "stable_intersection_ms = " .. tostring(summary.stable_intersection_ms)
    lines[#lines + 1] = "stable_snapshot_A_ms = " .. tostring(summary.stable_snapshot_A_ms)
    lines[#lines + 1] = "stable_snapshot_B_ms = " .. tostring(summary.stable_snapshot_B_ms)
    lines[#lines + 1] = "stable_intersection_build_ms = " .. tostring(summary.stable_intersection_build_ms)
    lines[#lines + 1] = "report_render_ms = " .. tostring(summary.report_render_ms)
    lines[#lines + 1] = "compact_report_enabled = " .. tostring(summary.compact_report_enabled)
    lines[#lines + 1] = "skipped_verbose_report_sections = " .. tostring(summary.skipped_verbose_report_sections)
    lines[#lines + 1] = "verbose_report_section_count = " .. tostring(summary.verbose_report_section_count)
    lines[#lines + 1] = "stable_report_render_ms = " .. tostring(summary.stable_report_render_ms)
    lines[#lines + 1] = "diagnostic_render_ms = " .. tostring(summary.diagnostic_render_ms)
    lines[#lines + 1] = "console_print_ms = " .. tostring(summary.console_print_ms)
    lines[#lines + 1] = "file_write_ms = " .. tostring(summary.file_write_ms)
    lines[#lines + 1] = "write_log_ms = " .. tostring(summary.write_log_ms)
    lines[#lines + 1] = "total_ms = " .. tostring(summary.total_ms)
    lines[#lines + 1] = "log_size_bytes = " .. tostring(summary.log_size_bytes)
    lines[#lines + 1] = "retry_recovered_count = " .. tostring(summary.retry_recovered_count)
    lines[#lines + 1] = "retry_still_mismatch_count = " .. tostring(summary.retry_still_mismatch_count)
    lines[#lines + 1] = "retry_read_failed_count = " .. tostring(summary.retry_read_failed_count)
    lines[#lines + 1] = "delayed_recheck_enabled = " .. tostring(summary.delayed_recheck_enabled)
    lines[#lines + 1] = "delayed_recheck_candidate_count = " .. tostring(summary.delayed_recheck_candidate_count)
    lines[#lines + 1] = "delayed_recovered_count = " .. tostring(summary.delayed_recovered_count)
    lines[#lines + 1] = "delayed_still_mismatch_count = " .. tostring(summary.delayed_still_mismatch_count)
    lines[#lines + 1] = "delayed_read_failed_count = " .. tostring(summary.delayed_read_failed_count)
    lines[#lines + 1] = "stable_intersection_enabled = " .. tostring(summary.stable_intersection_enabled)
    lines[#lines + 1] = "pass1_matched_count = " .. tostring(summary.pass1_matched_count)
    lines[#lines + 1] = "pass2_matched_count = " .. tostring(summary.pass2_matched_count)
    lines[#lines + 1] = "intersection_filtered_count = " .. tostring(summary.intersection_filtered_count)
    lines[#lines + 1] = "pass1_only_count = " .. tostring(summary.pass1_only_count)
    lines[#lines + 1] = "pass2_only_count = " .. tostring(summary.pass2_only_count)
    -- [stable-intersection-summary-file]
    if summary.stable_intersection_base_snapshot ~= nil then
      lines[#lines + 1] = "stable_no_probe_intersection_enabled = " .. tostring(summary.stable_no_probe_intersection_enabled)
      lines[#lines + 1] = "stable_intersection_snapshot_A_filtered_count = " .. tostring(summary.stable_intersection_snapshot_A_filtered_count)
      lines[#lines + 1] = "stable_intersection_snapshot_B_filtered_count = " .. tostring(summary.stable_intersection_snapshot_B_filtered_count)
      lines[#lines + 1] = "stable_intersection_enabled = " .. tostring(summary.stable_intersection_enabled)
      lines[#lines + 1] = "stable_intersection_base_snapshot = " .. tostring(summary.stable_intersection_base_snapshot)
      lines[#lines + 1] = "stable_intersection_filtered_count = " .. tostring(summary.stable_intersection_filtered_count)
      lines[#lines + 1] = "stable_intersection_snapshot_A_only_count = " .. tostring(summary.stable_intersection_snapshot_A_only_count)
      lines[#lines + 1] = "stable_intersection_snapshot_B_only_count = " .. tostring(summary.stable_intersection_snapshot_B_only_count)
      lines[#lines + 1] = "stable_intersection_canonical_source_count = " .. tostring(summary.stable_intersection_canonical_source_count)
      lines[#lines + 1] = "stable_intersection_downstream_input_count = " .. tostring(summary.stable_intersection_downstream_input_count)
      lines[#lines + 1] = "stable_intersection_true_in_filtered = " .. tostring(summary.stable_intersection_true_in_filtered)
      lines[#lines + 1] = "stable_intersection_prescored_count = " .. tostring(summary.stable_intersection_prescored_count)
      lines[#lines + 1] = "stable_intersection_selected_count = " .. tostring(summary.stable_intersection_selected_count)
      lines[#lines + 1] = "stable_intersection_known_true_rank_position = " .. tostring(summary.stable_intersection_known_true_rank_position)
      lines[#lines + 1] = "stable_intersection_best_candidate = " .. tostring(hex_u64(summary.stable_intersection_best_candidate))
      lines[#lines + 1] = "stable_intersection_best_score = " .. tostring(summary.stable_intersection_best_score)
      lines[#lines + 1] = "stable_intersection_second_score = " .. tostring(summary.stable_intersection_second_score)
      lines[#lines + 1] = "stable_intersection_score_gap = " .. tostring(summary.stable_intersection_score_gap)
    end
    lines[#lines + 1] = "confidence = " .. tostring(summary.confidence)
    lines[#lines + 1] = "log_path = " .. tostring(summary.log_path)
    lines[#lines + 1] = ""
  end

  local groups = {}
  for _, summary in ipairs(summaries) do
    local key = tostring(summary.session_id) .. "::" .. tostring(summary.case_id)
    groups[key] = groups[key] or {}
    groups[key][summary.mode] = summary
  end

  lines[#lines + 1] = "=== Delayed Snapshot Intersection Summary ==="
  lines[#lines + 1] = ""
  for key, group in pairs(groups) do
    local analysis = build_no_probe_snapshot_intersection_analysis(group.no_probe_A, group.no_probe_B)
    if analysis ~= nil then
      local runtime_empty_diagnostics = build_runtime_empty_diagnostics(group)
      lines[#lines + 1] = "--- " .. tostring(key) .. " ---"
      lines[#lines + 1] = "run_valid = " .. tostring(runtime_empty_diagnostics.run_valid)
      lines[#lines + 1] = "failure_class = " .. tostring(runtime_empty_diagnostics.failure_class)
      lines[#lines + 1] = "collector_empty = " .. tostring(runtime_empty_diagnostics.collector_empty)
      lines[#lines + 1] = "empty_modes = " .. tostring(runtime_empty_diagnostics.empty_modes)
      lines[#lines + 1] = "recommendation = " .. tostring(runtime_empty_diagnostics.recommendation)
      lines[#lines + 1] = "delayed_snapshot_intersection_enabled = " .. tostring(analysis.delayed_snapshot_intersection_enabled)
      lines[#lines + 1] = "delayed_snapshot_no_probe_stable_intersection_count = " .. tostring(analysis.delayed_snapshot_no_probe_stable_intersection_count)
      lines[#lines + 1] = "delayed_snapshot_no_probe_union_count = " .. tostring(analysis.delayed_snapshot_no_probe_union_count)
      lines[#lines + 1] = "delayed_snapshot_no_probe_A_only_count = " .. tostring(analysis.delayed_snapshot_no_probe_A_only_count)
      lines[#lines + 1] = "delayed_snapshot_no_probe_B_only_count = " .. tostring(analysis.delayed_snapshot_no_probe_B_only_count)
      lines[#lines + 1] = "delayed_snapshot_known_true_in_intersection = " .. tostring(analysis.delayed_snapshot_known_true_in_intersection)
      lines[#lines + 1] = "matched_only_in_no_probe_A_vs_B = " .. format_address_sample(analysis.matched_only_in_no_probe_A_vs_B)
      lines[#lines + 1] = "matched_only_in_no_probe_B_vs_A = " .. format_address_sample(analysis.matched_only_in_no_probe_B_vs_A)
      lines[#lines + 1] = "matched_in_no_probe_intersection = " .. format_address_sample(analysis.matched_in_no_probe_intersection)
      lines[#lines + 1] = ""
    end
  end

  return table.concat(lines, "\r\n")
end

local function emit_compact_stable_intersection_report(case_cfg, summary, policy)
  print("=== stable_intersection_compact_report ===")
  print_kv("case_id", case_cfg.case_id)
  print_kv("case_config_loaded", case_cfg.case_config_loaded)
  print_kv("case_config_path", case_cfg.case_config_path)
  print_kv("known_true_addr_source", case_cfg.known_true_addr_source)
  print_kv("target_value_source", case_cfg.target_value_source)
  print_kv("diagnostic_level", case_cfg.diagnostic_level)
  print_kv("session_id", case_cfg.session_id)
  print_kv("mode", "stable_no_probe_intersection")
  print_kv("run_valid", summary.run_valid)
  print_kv("failure_class", summary.failure_class)
  print_kv("collector_empty", summary.collector_empty)
  print_kv("recommendation", summary.recommendation)
  print_hex_kv("known_true_addr", case_cfg.known_true_addr)
  print_hex_kv("target_value_addr", summary.target_value_addr)
  print_hex_kv("target_value_pattern", summary.target_value_pattern)
  print_kv("target_value_float", summary.target_value_float)
  print_kv("stable_no_probe_intersection_enabled", summary.stable_no_probe_intersection_enabled)
  print_kv("stable_intersection_snapshot_A_filtered_count", summary.stable_intersection_snapshot_A_filtered_count)
  print_kv("stable_intersection_snapshot_B_filtered_count", summary.stable_intersection_snapshot_B_filtered_count)
  print_kv("stable_intersection_filtered_count", summary.stable_intersection_filtered_count)
  print_kv("stable_intersection_true_in_filtered", summary.stable_intersection_true_in_filtered)
  print_kv("stable_intersection_prescored_count", summary.stable_intersection_prescored_count)
  print_kv("stable_intersection_selected_count", summary.stable_intersection_selected_count)
  print_kv("stable_intersection_known_true_rank_position", summary.stable_intersection_known_true_rank_position)
  print_hex_kv("stable_intersection_best_candidate", summary.stable_intersection_best_candidate)
  print_kv("stable_intersection_best_score", summary.stable_intersection_best_score)
  print_kv("stable_intersection_second_score", summary.stable_intersection_second_score)
  print_kv("stable_intersection_score_gap", summary.stable_intersection_score_gap)
  print_report_policy(policy)
end

local function emit_stable_intersection_report(case_cfg, bundle, summary, policy)
  print("=== stable_intersection_experiment ===")
  print_kv("case_id", case_cfg.case_id)
  print_kv("case_config_loaded", case_cfg.case_config_loaded)
  print_kv("case_config_path", case_cfg.case_config_path)
  print_kv("known_true_addr_source", case_cfg.known_true_addr_source)
  print_kv("target_value_source", case_cfg.target_value_source)
  print_kv("diagnostic_level", case_cfg.diagnostic_level)
  print_kv("session_id", case_cfg.session_id)
  print_kv("mode", "stable_no_probe_intersection")
  -- [stable-intersection-report]
  print_kv("run_valid", summary.run_valid)
  print_kv("failure_class", summary.failure_class)
  print_kv("collector_empty", summary.collector_empty)
  print_kv("empty_modes", summary.empty_modes)
  print_kv("recommendation", summary.recommendation)
  print_kv("no_probe_A_collector_empty", summary.no_probe_A_collector_empty)
  print_kv("with_probe_collector_empty", summary.with_probe_collector_empty)
  print_kv("no_probe_B_collector_empty", summary.no_probe_B_collector_empty)
  print_hex_kv("target_value_addr", summary.target_value_addr)
  print_hex_kv("target_value_pattern", summary.target_value_pattern)
  print_kv("target_value_float", summary.target_value_float)
  print_kv("mode_total_ms", summary.mode_total_ms)
  print_kv("known_timed_ms", summary.known_timed_ms)
  print_kv("uninstrumented_gap_ms", summary.uninstrumented_gap_ms)
  print_kv("uninstrumented_gap_ratio", summary.uninstrumented_gap_ratio)
  print_kv("runner_setup_ms", summary.runner_setup_ms)
  print_kv("mode_config_ms", summary.mode_config_ms)
  print_kv("collector_call_ms", summary.collector_call_ms)
  print_kv("collector_ms", summary.collector_ms)
  print_kv("filter_ms", summary.filter_ms)
  print_kv("prescore_ms", summary.prescore_ms)
  print_kv("prescore_read_ms", summary.prescore_read_ms)
  print_kv("prescore_score_ms", summary.prescore_score_ms)
  print_kv("prescore_sort_ms", summary.prescore_sort_ms)
  print_kv("prescore_select_ms", summary.prescore_select_ms)
  print_kv("prescore_detail_ms", summary.prescore_detail_ms)
  print_kv("stable_intersection_ms", summary.stable_intersection_ms)
  print_kv("stable_snapshot_A_ms", summary.stable_snapshot_A_ms)
  print_kv("stable_snapshot_B_ms", summary.stable_snapshot_B_ms)
  print_kv("stable_intersection_build_ms", summary.stable_intersection_build_ms)
  print_kv("report_render_ms", summary.report_render_ms)
  print_kv("stable_report_render_ms", summary.stable_report_render_ms)
  print_kv("diagnostic_render_ms", summary.diagnostic_render_ms)
  print_kv("console_print_ms", summary.console_print_ms)
  print_kv("file_write_ms", summary.file_write_ms)
  print_kv("write_log_ms", summary.write_log_ms)
  print_kv("total_ms", summary.total_ms)
  print_kv("log_size_bytes", summary.log_size_bytes)
  print_kv("stable_no_probe_intersection_enabled", summary.stable_no_probe_intersection_enabled)
  print_kv("stable_intersection_snapshot_A_filtered_count", summary.stable_intersection_snapshot_A_filtered_count)
  print_kv("stable_intersection_snapshot_B_filtered_count", summary.stable_intersection_snapshot_B_filtered_count)
  print_kv("stable_intersection_enabled", summary.stable_intersection_enabled)
  print_kv("stable_intersection_base_snapshot", summary.stable_intersection_base_snapshot)
  print_kv("stable_intersection_filtered_count", summary.stable_intersection_filtered_count)
  print_kv("stable_intersection_snapshot_A_only_count", summary.stable_intersection_snapshot_A_only_count)
  print_kv("stable_intersection_snapshot_B_only_count", summary.stable_intersection_snapshot_B_only_count)
  print_kv("stable_intersection_canonical_source_count", summary.stable_intersection_canonical_source_count)
  print_kv("stable_intersection_downstream_input_count", summary.stable_intersection_downstream_input_count)
  print_kv("stable_intersection_true_in_filtered", summary.stable_intersection_true_in_filtered)
  print_kv("stable_intersection_prescored_count", summary.stable_intersection_prescored_count)
  print_kv("stable_intersection_selected_count", summary.stable_intersection_selected_count)
  print_kv("stable_intersection_known_true_rank_position", summary.stable_intersection_known_true_rank_position)
  print_hex_kv("stable_intersection_best_candidate", summary.stable_intersection_best_candidate)
  print_kv("stable_intersection_best_score", summary.stable_intersection_best_score)
  print_kv("stable_intersection_second_score", summary.stable_intersection_second_score)
  print_kv("stable_intersection_score_gap", summary.stable_intersection_score_gap)
  print_kv("delayed_snapshot_no_probe_stable_intersection_count", summary.delayed_snapshot_no_probe_stable_intersection_count)
  print_kv("delayed_snapshot_no_probe_union_count", summary.delayed_snapshot_no_probe_union_count)
  print_kv("delayed_snapshot_no_probe_A_only_count", summary.delayed_snapshot_no_probe_A_only_count)
  print_kv("delayed_snapshot_no_probe_B_only_count", summary.delayed_snapshot_no_probe_B_only_count)
  print_kv("delayed_snapshot_known_true_in_intersection", summary.delayed_snapshot_known_true_in_intersection)
  print_report_policy(policy)

  print("=== report_text ===")
  if bundle and bundle.result and bundle.result.report_text then
    print(bundle.result.report_text)
  else
    print("bundle.result.report_text = nil")
  end
end

local function build_stable_intersection_summary(case_cfg, bundle, log_path, analysis, base_snapshot, runtime_diagnostics, timing)
  local result = (bundle and bundle.result) or {}
  local best = result and result.best or nil
  local downstream_input_count = bundle and bundle.stable_intersection_downstream_input_count or nil
  local canonical_source_count = bundle and bundle.stable_intersection_canonical_source_count or nil

  return {
    case_id = case_cfg.case_id,
    case_config_loaded = case_cfg.case_config_loaded,
    case_config_path = case_cfg.case_config_path,
    known_true_addr_source = case_cfg.known_true_addr_source,
    target_value_source = case_cfg.target_value_source,
    diagnostic_level = case_cfg.diagnostic_level,
    session_id = case_cfg.session_id,
    mode = "stable_no_probe_intersection",
    probe_full_foundlist = false,
    known_true_addr = case_cfg.known_true_addr,
    target_value_addr = case_cfg.target_value_addr,
    target_value_pattern = case_cfg.target_value_pattern,
    target_value_float = case_cfg.target_value_float,
    run_valid = get_runtime_diagnostic(runtime_diagnostics, "run_valid"),
    failure_class = get_runtime_diagnostic(runtime_diagnostics, "failure_class"),
    collector_empty = get_runtime_diagnostic(runtime_diagnostics, "collector_empty"),
    empty_modes = get_runtime_diagnostic(runtime_diagnostics, "empty_modes"),
    recommendation = get_runtime_diagnostic(runtime_diagnostics, "recommendation"),
    no_probe_A_collector_empty = get_runtime_diagnostic(runtime_diagnostics, "no_probe_A_collector_empty"),
    with_probe_collector_empty = get_runtime_diagnostic(runtime_diagnostics, "with_probe_collector_empty"),
    no_probe_B_collector_empty = get_runtime_diagnostic(runtime_diagnostics, "no_probe_B_collector_empty"),
    raw_count = bundle and bundle.raw_count or nil,
    unique_count = bundle and bundle.unique_count or nil,
    known_true_rank_position = bundle and bundle.known_true_rank_position or nil,
    known_true_final_score = bundle and bundle.known_true_final_score or nil,
    true_in_selected = bundle and bundle.true_in_selected or nil,
    known_true_raw_admission_path = base_snapshot and base_snapshot.known_true_raw_admission_path or nil,
    selected_count = bundle and bundle.selected_count or nil,
    filtered_count = bundle and bundle.filtered_count or nil,
    matched_count = bundle and bundle.filtered_count or nil,
    value_mismatch_count = nil,
    read_failed_count = nil,
    mode_config_ms = timing and timing.mode_config_ms or nil,
    runner_setup_ms = timing and timing.runner_setup_ms or nil,
    collector_ms = timing and timing.collector_ms or nil,
    collector_call_ms = timing and timing.collector_call_ms or timing and timing.collector_ms or nil,
    filter_ms = bundle and bundle.filter_ms or nil,
    prescore_ms = bundle and bundle.prescore_ms or nil,
    prescore_read_ms = bundle and bundle.prescore_read_ms or nil,
    prescore_score_ms = bundle and bundle.prescore_score_ms or nil,
    prescore_sort_ms = bundle and bundle.prescore_sort_ms or nil,
    prescore_select_ms = bundle and bundle.prescore_select_ms or nil,
    prescore_detail_ms = bundle and bundle.prescore_detail_ms or nil,
    stable_intersection_ms = timing and timing.stable_intersection_ms or nil,
    stable_snapshot_A_ms = bundle and bundle.stable_snapshot_A_ms or nil,
    stable_snapshot_B_ms = bundle and bundle.stable_snapshot_B_ms or nil,
    stable_intersection_build_ms = bundle and bundle.stable_intersection_build_ms or timing and timing.stable_intersection_build_ms or nil,
    report_render_ms = timing and timing.report_render_ms or nil,
    compact_report_enabled = timing and timing.compact_report_enabled or false,
    skipped_verbose_report_sections = timing and timing.skipped_verbose_report_sections or "none",
    verbose_report_section_count = timing and timing.verbose_report_section_count or 0,
    stable_report_render_ms = timing and timing.stable_report_render_ms or nil,
    diagnostic_render_ms = timing and timing.diagnostic_render_ms or nil,
    console_print_ms = timing and timing.console_print_ms or nil,
    file_write_ms = timing and timing.file_write_ms or timing and timing.write_log_ms or nil,
    write_log_ms = timing and timing.write_log_ms or nil,
    total_ms = timing and timing.total_ms or nil,
    log_size_bytes = timing and timing.log_size_bytes or nil,
    retry_recovered_count = nil,
    retry_still_mismatch_count = nil,
    retry_read_failed_count = nil,
    delayed_recheck_enabled = nil,
    delayed_recheck_candidate_count = nil,
    delayed_recovered_count = nil,
    delayed_still_mismatch_count = nil,
    delayed_read_failed_count = nil,
    -- [stable-intersection-summary-table]
    stable_no_probe_intersection_enabled = bundle and bundle.stable_no_probe_intersection_enabled or true,
    stable_intersection_enabled = true,
    stable_intersection_base_snapshot = "no_probe_B",
    stable_intersection_snapshot_A_filtered_count = bundle and bundle.stable_intersection_snapshot_A_filtered_count or nil,
    stable_intersection_snapshot_B_filtered_count = bundle and bundle.stable_intersection_snapshot_B_filtered_count or nil,
    stable_intersection_filtered_count = bundle and bundle.stable_intersection_filtered_count or nil,
    stable_intersection_snapshot_A_only_count = bundle and bundle.stable_intersection_snapshot_A_only_count or nil,
    stable_intersection_snapshot_B_only_count = bundle and bundle.stable_intersection_snapshot_B_only_count or nil,
    stable_intersection_canonical_source_count = canonical_source_count,
    stable_intersection_downstream_input_count = downstream_input_count,
    stable_intersection_true_in_filtered = bundle and bundle.stable_intersection_true_in_filtered or bundle and bundle.true_in_filtered or nil,
    stable_intersection_prescored_count = bundle and bundle.prescored_count or nil,
    stable_intersection_selected_count = bundle and bundle.selected_count or nil,
    stable_intersection_known_true_rank_position = bundle and bundle.known_true_rank_position or nil,
    stable_intersection_best_candidate = best and best.candidate and best.candidate.value_addr or nil,
    stable_intersection_best_score = result and result.best and result.best.score or nil,
    stable_intersection_second_score = result and result.second and result.second.score or nil,
    stable_intersection_score_gap = result and result.score_gap or nil,
    delayed_snapshot_no_probe_stable_intersection_count = analysis and analysis.delayed_snapshot_no_probe_stable_intersection_count or nil,
    delayed_snapshot_no_probe_union_count = analysis and analysis.delayed_snapshot_no_probe_union_count or nil,
    delayed_snapshot_no_probe_A_only_count = analysis and analysis.delayed_snapshot_no_probe_A_only_count or nil,
    delayed_snapshot_no_probe_B_only_count = analysis and analysis.delayed_snapshot_no_probe_B_only_count or nil,
    delayed_snapshot_known_true_in_intersection = analysis and analysis.delayed_snapshot_known_true_in_intersection or nil,
    best_candidate_addr = best and best.candidate and best.candidate.value_addr or nil,
    best_score = result and result.best and result.best.score or nil,
    second_score = result and result.second and result.second.score or nil,
    score_gap = result and result.score_gap or nil,
    confidence = result and result.confidence or nil,
    log_path = log_path,
  }
end

local function run_stable_intersection_mode(case_cfg, no_probe_a, no_probe_b, batch_id, runtime_diagnostics)
  local total_start_ms = now_ms()
  local stable_intersection_build_start_ms = now_ms()
  local analysis = build_no_probe_snapshot_intersection_analysis(no_probe_a, no_probe_b)
  local stable_intersection_build_ms = elapsed_ms(stable_intersection_build_start_ms)
  if analysis == nil then
    return nil
  end

  local runner_setup_start_ms = now_ms()
  active_log_lines = {}
  local safe_session = sanitize_token(case_cfg.session_id)
  local safe_case = sanitize_token(case_cfg.case_id)
  local log_path = string.format(
    "%s\\%s__%s__%s__stable_no_probe_intersection.log",
    OUTPUT_DIR,
    batch_id,
    safe_session,
    safe_case
  )
  local runner_setup_ms = elapsed_ms(runner_setup_start_ms)

  local stable_intersection_ms = nil
  local report_render_ms = nil
  local console_print_ms = nil
  local compact_report_enabled = nil
  local skipped_verbose_report_sections = nil
  local verbose_report_section_count = nil
  local ok, bundle_or_err = xpcall(function()
    local module_load_start_ms = now_ms()
    load_modules()
    runner_setup_ms = runner_setup_ms + elapsed_ms(module_load_start_ms)
    local stable_start_ms = now_ms()
    local bundle = MVP0FoundList.run({
      max_candidates = case_cfg.max_candidates,
      scan_budget = case_cfg.scan_budget,
      target_value_pattern = case_cfg.target_value_pattern,
      target_value_float = case_cfg.target_value_float,
      session_id = case_cfg.session_id,
      filter_target_match = case_cfg.filter_target_match,
      use_prescore_selection = case_cfg.use_prescore_selection,
      stable_no_probe_intersection_enabled = true,
      stable_filter_intersection_enabled = false,
      delayed_recheck_enabled = false,
      probe_full_foundlist = false,
      known_true_addr = case_cfg.known_true_addr,
    })
    stable_intersection_ms = elapsed_ms(stable_start_ms)

    local summary = build_stable_intersection_summary(case_cfg, bundle, log_path, analysis, no_probe_b, runtime_diagnostics, {
      mode_config_ms = 0,
      runner_setup_ms = runner_setup_ms,
      collector_ms = stable_intersection_ms,
      collector_call_ms = stable_intersection_ms,
      stable_intersection_ms = stable_intersection_ms,
      stable_intersection_build_ms = stable_intersection_build_ms,
    })
    local report_console_start_ms = console_print_total_ms
    local report_render_start_ms = now_ms()
    local emit_verbose_report = should_emit_verbose_stable_report(case_cfg, summary)
    local report_policy
    if emit_verbose_report then
      report_policy = make_report_policy(false, "none", 1)
      emit_stable_intersection_report(case_cfg, bundle, summary, report_policy)
    else
      report_policy = make_report_policy(true, "report_text", 0)
      emit_compact_stable_intersection_report(case_cfg, summary, report_policy)
    end
    compact_report_enabled = report_policy.compact_report_enabled
    skipped_verbose_report_sections = report_policy.skipped_verbose_report_sections
    verbose_report_section_count = report_policy.verbose_report_section_count
    report_render_ms = elapsed_ms(report_render_start_ms)
    console_print_ms = console_print_total_ms - report_console_start_ms
    summary.report_render_ms = report_render_ms
    summary.stable_report_render_ms = report_render_ms
    summary.console_print_ms = console_print_ms
    summary.compact_report_enabled = compact_report_enabled
    summary.skipped_verbose_report_sections = skipped_verbose_report_sections
    summary.verbose_report_section_count = verbose_report_section_count
    return {
      bundle = bundle,
      summary = summary,
    }
  end, debug.traceback)

  if not ok then
    print("=== run_error ===")
    print(bundle_or_err)
  end

  local log_text = table.concat(active_log_lines, "\r\n") .. "\r\n"
  local log_size_bytes = #log_text
  local write_start_ms = now_ms()
  write_text_file(log_path, log_text)
  local write_log_ms = elapsed_ms(write_start_ms)
  local file_write_ms = write_log_ms
  active_log_lines = nil
  local total_ms = elapsed_ms(total_start_ms)

  if not ok then
    return finalize_timing_summary({
      case_id = case_cfg.case_id,
      case_config_loaded = case_cfg.case_config_loaded,
      case_config_path = case_cfg.case_config_path,
      known_true_addr_source = case_cfg.known_true_addr_source,
      target_value_source = case_cfg.target_value_source,
      diagnostic_level = case_cfg.diagnostic_level,
      session_id = case_cfg.session_id,
      mode = "stable_no_probe_intersection",
      known_true_addr = case_cfg.known_true_addr,
      target_value_addr = case_cfg.target_value_addr,
      target_value_pattern = case_cfg.target_value_pattern,
      target_value_float = case_cfg.target_value_float,
      mode_config_ms = 0,
      runner_setup_ms = runner_setup_ms,
      collector_ms = stable_intersection_ms,
      collector_call_ms = stable_intersection_ms,
      filter_ms = nil,
      prescore_ms = nil,
      stable_intersection_ms = stable_intersection_ms,
      stable_intersection_build_ms = stable_intersection_build_ms,
      report_render_ms = report_render_ms,
      compact_report_enabled = compact_report_enabled,
      skipped_verbose_report_sections = skipped_verbose_report_sections,
      verbose_report_section_count = verbose_report_section_count,
      stable_report_render_ms = report_render_ms,
      diagnostic_render_ms = nil,
      console_print_ms = console_print_ms,
      file_write_ms = file_write_ms,
      write_log_ms = write_log_ms,
      total_ms = total_ms,
      log_size_bytes = log_size_bytes,
      run_valid = get_runtime_diagnostic(runtime_diagnostics, "run_valid"),
      failure_class = get_runtime_diagnostic(runtime_diagnostics, "failure_class"),
      collector_empty = get_runtime_diagnostic(runtime_diagnostics, "collector_empty"),
      empty_modes = get_runtime_diagnostic(runtime_diagnostics, "empty_modes"),
      recommendation = get_runtime_diagnostic(runtime_diagnostics, "recommendation"),
      no_probe_A_collector_empty = get_runtime_diagnostic(runtime_diagnostics, "no_probe_A_collector_empty"),
      with_probe_collector_empty = get_runtime_diagnostic(runtime_diagnostics, "with_probe_collector_empty"),
      no_probe_B_collector_empty = get_runtime_diagnostic(runtime_diagnostics, "no_probe_B_collector_empty"),
      log_path = log_path,
      error = bundle_or_err,
      stable_intersection_enabled = true,
      stable_no_probe_intersection_enabled = true,
      stable_intersection_snapshot_A_filtered_count = no_probe_a and no_probe_a.filtered_count or nil,
      stable_intersection_snapshot_B_filtered_count = no_probe_b and no_probe_b.filtered_count or nil,
      stable_intersection_base_snapshot = "no_probe_B",
      stable_intersection_filtered_count = analysis.delayed_snapshot_no_probe_stable_intersection_count,
      stable_intersection_snapshot_A_only_count = analysis.delayed_snapshot_no_probe_A_only_count,
      stable_intersection_snapshot_B_only_count = analysis.delayed_snapshot_no_probe_B_only_count,
      stable_intersection_canonical_source_count = no_probe_b and no_probe_b.filtered_count or nil,
      stable_intersection_downstream_input_count = analysis.delayed_snapshot_no_probe_stable_intersection_count,
      stable_intersection_true_in_filtered = nil,
      stable_intersection_prescored_count = nil,
      stable_intersection_selected_count = nil,
      stable_intersection_known_true_rank_position = nil,
      stable_intersection_best_candidate = nil,
      stable_intersection_best_score = nil,
      stable_intersection_second_score = nil,
      stable_intersection_score_gap = nil,
      delayed_snapshot_no_probe_stable_intersection_count = analysis.delayed_snapshot_no_probe_stable_intersection_count,
      delayed_snapshot_no_probe_union_count = analysis.delayed_snapshot_no_probe_union_count,
      delayed_snapshot_no_probe_A_only_count = analysis.delayed_snapshot_no_probe_A_only_count,
      delayed_snapshot_no_probe_B_only_count = analysis.delayed_snapshot_no_probe_B_only_count,
      delayed_snapshot_known_true_in_intersection = analysis.delayed_snapshot_known_true_in_intersection,
    })
  end

  bundle_or_err.summary.write_log_ms = write_log_ms
  bundle_or_err.summary.file_write_ms = file_write_ms
  bundle_or_err.summary.total_ms = total_ms
  bundle_or_err.summary.log_size_bytes = log_size_bytes
  finalize_timing_summary(bundle_or_err.summary)
  local diagnostic_render_start_ms = now_ms()
  print_run_summary(bundle_or_err.summary)
  bundle_or_err.summary.diagnostic_render_ms = elapsed_ms(diagnostic_render_start_ms)
  return bundle_or_err.summary
end

local function render_diagnostic_diff_file(batch_id, summaries)
  local groups = {}
  local lines = {}

  for _, summary in ipairs(summaries) do
    local key = tostring(summary.session_id) .. "::" .. tostring(summary.case_id)
    groups[key] = groups[key] or {}
    groups[key][summary.mode] = summary
  end

  lines[#lines + 1] = "=== Diagnostic Sandwich Diff ==="
  lines[#lines + 1] = "batch_id = " .. tostring(batch_id)
  lines[#lines + 1] = "output_dir = " .. tostring(OUTPUT_DIR)
  lines[#lines + 1] = ""

  for key, group in pairs(groups) do
    local no_probe_a = group.no_probe_A
    local with_probe = group.with_probe
    local no_probe_b = group.no_probe_B

    local stable_summary = group.stable_no_probe_intersection

    if no_probe_a ~= nil and with_probe ~= nil and no_probe_b ~= nil then
      local overlap = compute_match_overlap_counts(
        no_probe_a.matched_addresses,
        with_probe.matched_addresses,
        no_probe_b.matched_addresses
      )
      local full_only_a = collect_unique_only(no_probe_a.matched_addresses, with_probe.matched_addresses, no_probe_b.matched_addresses, nil)
      local full_only_w = collect_unique_only(with_probe.matched_addresses, no_probe_a.matched_addresses, no_probe_b.matched_addresses, nil)
      local full_only_b = collect_unique_only(no_probe_b.matched_addresses, no_probe_a.matched_addresses, with_probe.matched_addresses, nil)
      local only_a = collect_unique_only(no_probe_a.matched_addresses, with_probe.matched_addresses, no_probe_b.matched_addresses, 20)
      local only_w = collect_unique_only(with_probe.matched_addresses, no_probe_a.matched_addresses, no_probe_b.matched_addresses, 20)
      local only_b = collect_unique_only(no_probe_b.matched_addresses, no_probe_a.matched_addresses, with_probe.matched_addresses, 20)
      local page_top_no_probe_a = collect_top_buckets(full_only_a, 0x1000, 5)
      local page_top_with_probe = collect_top_buckets(full_only_w, 0x1000, 5)
      local page_top_no_probe_b = collect_top_buckets(full_only_b, 0x1000, 5)
      local region_top_no_probe_a = collect_top_buckets(full_only_a, 0x10000, 5)
      local region_top_with_probe = collect_top_buckets(full_only_w, 0x10000, 5)
      local region_top_no_probe_b = collect_top_buckets(full_only_b, 0x10000, 5)
      local segment_top_no_probe_a = collect_top_buckets(full_only_a, 0x100000, 5)
      local segment_top_with_probe = collect_top_buckets(full_only_w, 0x100000, 5)
      local segment_top_no_probe_b = collect_top_buckets(full_only_b, 0x100000, 5)
      local delta_candidates = collect_dominant_delta_candidates(full_only_w, full_only_b, 32)
      local interpretation_hint = build_interpretation_hints(full_only_w, full_only_b, page_top_with_probe, page_top_no_probe_b, delta_candidates)
      local no_probe_snapshot_analysis = build_no_probe_snapshot_intersection_analysis(no_probe_a, no_probe_b)
      local runtime_empty_diagnostics = build_runtime_empty_diagnostics(group)

      lines[#lines + 1] = "--- " .. tostring(key) .. " ---"
      lines[#lines + 1] = "run_valid = " .. tostring(runtime_empty_diagnostics.run_valid)
      lines[#lines + 1] = "failure_class = " .. tostring(runtime_empty_diagnostics.failure_class)
      lines[#lines + 1] = "collector_empty = " .. tostring(runtime_empty_diagnostics.collector_empty)
      lines[#lines + 1] = "empty_modes = " .. tostring(runtime_empty_diagnostics.empty_modes)
      lines[#lines + 1] = "recommendation = " .. tostring(runtime_empty_diagnostics.recommendation)
      lines[#lines + 1] = "case_config_loaded = " .. tostring(no_probe_a.case_config_loaded)
      lines[#lines + 1] = "case_config_path = " .. tostring(no_probe_a.case_config_path)
      lines[#lines + 1] = "known_true_addr_source = " .. tostring(no_probe_a.known_true_addr_source)
      lines[#lines + 1] = "target_value_source = " .. tostring(no_probe_a.target_value_source)
      lines[#lines + 1] = "diagnostic_level = " .. tostring(no_probe_a.diagnostic_level)
      lines[#lines + 1] = "no_probe_A_collector_empty = " .. tostring(runtime_empty_diagnostics.no_probe_A_collector_empty)
      lines[#lines + 1] = "with_probe_collector_empty = " .. tostring(runtime_empty_diagnostics.with_probe_collector_empty)
      lines[#lines + 1] = "no_probe_B_collector_empty = " .. tostring(runtime_empty_diagnostics.no_probe_B_collector_empty)
      lines[#lines + 1] = "target_value_addr = " .. tostring(hex_u64(no_probe_a.target_value_addr))
      lines[#lines + 1] = "target_value_pattern = " .. tostring(hex_u64(no_probe_a.target_value_pattern))
      lines[#lines + 1] = "target_value_float = " .. tostring(no_probe_a.target_value_float)

      for _, summary in ipairs({no_probe_a, with_probe, no_probe_b}) do
        lines[#lines + 1] = "[" .. tostring(summary.mode) .. "]"
        lines[#lines + 1] = "raw_count = " .. tostring(summary.raw_count)
        lines[#lines + 1] = "unique_count = " .. tostring(summary.unique_count)
        lines[#lines + 1] = "filtered_count = " .. tostring(summary.filtered_count)
        lines[#lines + 1] = "matched_count = " .. tostring(summary.matched_count)
        lines[#lines + 1] = "value_mismatch_count = " .. tostring(summary.value_mismatch_count)
        lines[#lines + 1] = "read_failed_count = " .. tostring(summary.read_failed_count)
        lines[#lines + 1] = "mode_total_ms = " .. tostring(summary.mode_total_ms)
        lines[#lines + 1] = "known_timed_ms = " .. tostring(summary.known_timed_ms)
        lines[#lines + 1] = "uninstrumented_gap_ms = " .. tostring(summary.uninstrumented_gap_ms)
        lines[#lines + 1] = "uninstrumented_gap_ratio = " .. tostring(summary.uninstrumented_gap_ratio)
        lines[#lines + 1] = "runner_setup_ms = " .. tostring(summary.runner_setup_ms)
        lines[#lines + 1] = "mode_config_ms = " .. tostring(summary.mode_config_ms)
        lines[#lines + 1] = "collector_call_ms = " .. tostring(summary.collector_call_ms)
        lines[#lines + 1] = "collector_ms = " .. tostring(summary.collector_ms)
        lines[#lines + 1] = "filter_ms = " .. tostring(summary.filter_ms)
        lines[#lines + 1] = "prescore_ms = " .. tostring(summary.prescore_ms)
        lines[#lines + 1] = "prescore_read_ms = " .. tostring(summary.prescore_read_ms)
        lines[#lines + 1] = "prescore_score_ms = " .. tostring(summary.prescore_score_ms)
        lines[#lines + 1] = "prescore_sort_ms = " .. tostring(summary.prescore_sort_ms)
        lines[#lines + 1] = "prescore_select_ms = " .. tostring(summary.prescore_select_ms)
        lines[#lines + 1] = "prescore_detail_ms = " .. tostring(summary.prescore_detail_ms)
        lines[#lines + 1] = "stable_intersection_ms = " .. tostring(summary.stable_intersection_ms)
        lines[#lines + 1] = "stable_snapshot_A_ms = " .. tostring(summary.stable_snapshot_A_ms)
        lines[#lines + 1] = "stable_snapshot_B_ms = " .. tostring(summary.stable_snapshot_B_ms)
        lines[#lines + 1] = "stable_intersection_build_ms = " .. tostring(summary.stable_intersection_build_ms)
        lines[#lines + 1] = "report_render_ms = " .. tostring(summary.report_render_ms)
        lines[#lines + 1] = "compact_report_enabled = " .. tostring(summary.compact_report_enabled)
        lines[#lines + 1] = "skipped_verbose_report_sections = " .. tostring(summary.skipped_verbose_report_sections)
        lines[#lines + 1] = "verbose_report_section_count = " .. tostring(summary.verbose_report_section_count)
        lines[#lines + 1] = "stable_report_render_ms = " .. tostring(summary.stable_report_render_ms)
        lines[#lines + 1] = "diagnostic_render_ms = " .. tostring(summary.diagnostic_render_ms)
        lines[#lines + 1] = "console_print_ms = " .. tostring(summary.console_print_ms)
        lines[#lines + 1] = "file_write_ms = " .. tostring(summary.file_write_ms)
        lines[#lines + 1] = "write_log_ms = " .. tostring(summary.write_log_ms)
        lines[#lines + 1] = "total_ms = " .. tostring(summary.total_ms)
        lines[#lines + 1] = "log_size_bytes = " .. tostring(summary.log_size_bytes)
        lines[#lines + 1] = "retry_recovered_count = " .. tostring(summary.retry_recovered_count)
        lines[#lines + 1] = "retry_still_mismatch_count = " .. tostring(summary.retry_still_mismatch_count)
        lines[#lines + 1] = "retry_read_failed_count = " .. tostring(summary.retry_read_failed_count)
        lines[#lines + 1] = "delayed_recheck_enabled = " .. tostring(summary.delayed_recheck_enabled)
        lines[#lines + 1] = "delayed_recheck_candidate_count = " .. tostring(summary.delayed_recheck_candidate_count)
        lines[#lines + 1] = "delayed_recovered_count = " .. tostring(summary.delayed_recovered_count)
        lines[#lines + 1] = "delayed_still_mismatch_count = " .. tostring(summary.delayed_still_mismatch_count)
        lines[#lines + 1] = "delayed_read_failed_count = " .. tostring(summary.delayed_read_failed_count)
        lines[#lines + 1] = "stable_intersection_enabled = " .. tostring(summary.stable_intersection_enabled)
        lines[#lines + 1] = "pass1_matched_count = " .. tostring(summary.pass1_matched_count)
        lines[#lines + 1] = "pass2_matched_count = " .. tostring(summary.pass2_matched_count)
        lines[#lines + 1] = "intersection_filtered_count = " .. tostring(summary.intersection_filtered_count)
        lines[#lines + 1] = "pass1_only_count = " .. tostring(summary.pass1_only_count)
        lines[#lines + 1] = "pass2_only_count = " .. tostring(summary.pass2_only_count)
        lines[#lines + 1] = "matched_only_in_pass1 = " .. format_address_sample((function()
          local sample = copy_array(summary.pass1_only_addresses)
          table.sort(sample)
          while #sample > 20 do table.remove(sample) end
          return sample
        end)())
        lines[#lines + 1] = "matched_only_in_pass2 = " .. format_address_sample((function()
          local sample = copy_array(summary.pass2_only_addresses)
          table.sort(sample)
          while #sample > 20 do table.remove(sample) end
          return sample
        end)())
        lines[#lines + 1] = "page_cluster_summary.pass1_only = " .. format_bucket_entries(collect_top_buckets(summary.pass1_only_addresses, 0x1000, 5))
        lines[#lines + 1] = "page_cluster_summary.pass2_only = " .. format_bucket_entries(collect_top_buckets(summary.pass2_only_addresses, 0x1000, 5))
        lines[#lines + 1] = "region_cluster_summary.pass1_only = " .. format_bucket_entries(collect_top_buckets(summary.pass1_only_addresses, 0x10000, 5))
        lines[#lines + 1] = "region_cluster_summary.pass2_only = " .. format_bucket_entries(collect_top_buckets(summary.pass2_only_addresses, 0x10000, 5))
        lines[#lines + 1] = "segment_cluster_summary.pass1_only = " .. format_bucket_entries(collect_top_buckets(summary.pass1_only_addresses, 0x100000, 5))
        lines[#lines + 1] = "segment_cluster_summary.pass2_only = " .. format_bucket_entries(collect_top_buckets(summary.pass2_only_addresses, 0x100000, 5))
        lines[#lines + 1] = "interpretation_hint.pass1_vs_pass2 = " .. build_pass_interpretation_hint(
          summary.pass1_only_addresses,
          summary.pass2_only_addresses,
          collect_top_buckets(summary.pass1_only_addresses, 0x1000, 5),
          collect_top_buckets(summary.pass2_only_addresses, 0x1000, 5)
        )
        lines[#lines + 1] = "known_true_raw_admission_path = " .. tostring(summary.known_true_raw_admission_path)
        lines[#lines + 1] = "known_true_rank_position = " .. tostring(summary.known_true_rank_position)
        lines[#lines + 1] = "best_candidate = " .. tostring(hex_u64(summary.best_candidate_addr))
        lines[#lines + 1] = "best_score = " .. tostring(summary.best_score)
        lines[#lines + 1] = "second_score = " .. tostring(summary.second_score)
        lines[#lines + 1] = "score_gap = " .. tostring(summary.score_gap)
        lines[#lines + 1] = ""
      end

      lines[#lines + 1] = "matched_in_all_three_count = " .. tostring(overlap.matched_in_all_three_count)
      lines[#lines + 1] = "matched_in_any_two_count = " .. tostring(overlap.matched_in_any_two_count)
      lines[#lines + 1] = "matched_unique_to_each_count = " .. tostring(overlap.matched_unique_to_each_count)
      lines[#lines + 1] = "matched_only_in_no_probe_A = " .. format_address_sample(only_a)
      lines[#lines + 1] = "matched_only_in_with_probe = " .. format_address_sample(only_w)
      lines[#lines + 1] = "matched_only_in_no_probe_B = " .. format_address_sample(only_b)
      lines[#lines + 1] = "page_cluster_summary.no_probe_A = " .. format_bucket_entries(page_top_no_probe_a)
      lines[#lines + 1] = "page_cluster_summary.with_probe = " .. format_bucket_entries(page_top_with_probe)
      lines[#lines + 1] = "page_cluster_summary.no_probe_B = " .. format_bucket_entries(page_top_no_probe_b)
      lines[#lines + 1] = "region_cluster_summary.no_probe_A = " .. format_bucket_entries(region_top_no_probe_a)
      lines[#lines + 1] = "region_cluster_summary.with_probe = " .. format_bucket_entries(region_top_with_probe)
      lines[#lines + 1] = "region_cluster_summary.no_probe_B = " .. format_bucket_entries(region_top_no_probe_b)
      lines[#lines + 1] = "segment_cluster_summary.no_probe_A = " .. format_bucket_entries(segment_top_no_probe_a)
      lines[#lines + 1] = "segment_cluster_summary.with_probe = " .. format_bucket_entries(segment_top_with_probe)
      lines[#lines + 1] = "segment_cluster_summary.no_probe_B = " .. format_bucket_entries(segment_top_no_probe_b)
      lines[#lines + 1] = "dominant_delta_candidates = " .. format_delta_candidates(delta_candidates)
      lines[#lines + 1] = "interpretation_hint = " .. tostring(interpretation_hint)
      if no_probe_snapshot_analysis ~= nil then
        lines[#lines + 1] = "delayed_snapshot_intersection_enabled = " .. tostring(no_probe_snapshot_analysis.delayed_snapshot_intersection_enabled)
        lines[#lines + 1] = "delayed_snapshot_no_probe_stable_intersection_count = " .. tostring(no_probe_snapshot_analysis.delayed_snapshot_no_probe_stable_intersection_count)
        lines[#lines + 1] = "delayed_snapshot_no_probe_union_count = " .. tostring(no_probe_snapshot_analysis.delayed_snapshot_no_probe_union_count)
        lines[#lines + 1] = "delayed_snapshot_no_probe_A_only_count = " .. tostring(no_probe_snapshot_analysis.delayed_snapshot_no_probe_A_only_count)
        lines[#lines + 1] = "delayed_snapshot_no_probe_B_only_count = " .. tostring(no_probe_snapshot_analysis.delayed_snapshot_no_probe_B_only_count)
        lines[#lines + 1] = "delayed_snapshot_known_true_in_intersection = " .. tostring(no_probe_snapshot_analysis.delayed_snapshot_known_true_in_intersection)
        lines[#lines + 1] = "matched_only_in_no_probe_A_vs_B = " .. format_address_sample(no_probe_snapshot_analysis.matched_only_in_no_probe_A_vs_B)
        lines[#lines + 1] = "matched_only_in_no_probe_B_vs_A = " .. format_address_sample(no_probe_snapshot_analysis.matched_only_in_no_probe_B_vs_A)
        lines[#lines + 1] = "matched_in_no_probe_intersection = " .. format_address_sample(no_probe_snapshot_analysis.matched_in_no_probe_intersection)
        lines[#lines + 1] = "page_cluster_summary.no_probe_A_only = " .. format_bucket_entries(no_probe_snapshot_analysis.page_cluster_summary_no_probe_A_only)
        lines[#lines + 1] = "page_cluster_summary.no_probe_B_only = " .. format_bucket_entries(no_probe_snapshot_analysis.page_cluster_summary_no_probe_B_only)
        lines[#lines + 1] = "page_cluster_summary.no_probe_intersection = " .. format_bucket_entries(no_probe_snapshot_analysis.page_cluster_summary_no_probe_intersection)
        lines[#lines + 1] = "region_cluster_summary.no_probe_A_only = " .. format_bucket_entries(no_probe_snapshot_analysis.region_cluster_summary_no_probe_A_only)
        lines[#lines + 1] = "region_cluster_summary.no_probe_B_only = " .. format_bucket_entries(no_probe_snapshot_analysis.region_cluster_summary_no_probe_B_only)
        lines[#lines + 1] = "region_cluster_summary.no_probe_intersection = " .. format_bucket_entries(no_probe_snapshot_analysis.region_cluster_summary_no_probe_intersection)
        lines[#lines + 1] = "segment_cluster_summary.no_probe_A_only = " .. format_bucket_entries(no_probe_snapshot_analysis.segment_cluster_summary_no_probe_A_only)
        lines[#lines + 1] = "segment_cluster_summary.no_probe_B_only = " .. format_bucket_entries(no_probe_snapshot_analysis.segment_cluster_summary_no_probe_B_only)
        lines[#lines + 1] = "segment_cluster_summary.no_probe_intersection = " .. format_bucket_entries(no_probe_snapshot_analysis.segment_cluster_summary_no_probe_intersection)
        lines[#lines + 1] = "interpretation_hint.no_probe_A_vs_B = " .. tostring(no_probe_snapshot_analysis.interpretation_hint)
      end
      -- [stable-intersection-diagnostic-diff]
      if stable_summary ~= nil then
        lines[#lines + 1] = "stable_no_probe_intersection_enabled = " .. tostring(stable_summary.stable_no_probe_intersection_enabled)
        lines[#lines + 1] = "stable_intersection_snapshot_A_filtered_count = " .. tostring(stable_summary.stable_intersection_snapshot_A_filtered_count)
        lines[#lines + 1] = "stable_intersection_snapshot_B_filtered_count = " .. tostring(stable_summary.stable_intersection_snapshot_B_filtered_count)
        lines[#lines + 1] = "[stable_no_probe_intersection]"
        lines[#lines + 1] = "stable_intersection_enabled = " .. tostring(stable_summary.stable_intersection_enabled)
        lines[#lines + 1] = "stable_intersection_base_snapshot = " .. tostring(stable_summary.stable_intersection_base_snapshot)
        lines[#lines + 1] = "stable_intersection_filtered_count = " .. tostring(stable_summary.stable_intersection_filtered_count)
        lines[#lines + 1] = "stable_intersection_snapshot_A_only_count = " .. tostring(stable_summary.stable_intersection_snapshot_A_only_count)
        lines[#lines + 1] = "stable_intersection_snapshot_B_only_count = " .. tostring(stable_summary.stable_intersection_snapshot_B_only_count)
        lines[#lines + 1] = "stable_intersection_canonical_source_count = " .. tostring(stable_summary.stable_intersection_canonical_source_count)
        lines[#lines + 1] = "stable_intersection_downstream_input_count = " .. tostring(stable_summary.stable_intersection_downstream_input_count)
        lines[#lines + 1] = "stable_intersection_true_in_filtered = " .. tostring(stable_summary.stable_intersection_true_in_filtered)
        lines[#lines + 1] = "stable_intersection_prescored_count = " .. tostring(stable_summary.stable_intersection_prescored_count)
        lines[#lines + 1] = "stable_intersection_selected_count = " .. tostring(stable_summary.stable_intersection_selected_count)
        lines[#lines + 1] = "stable_intersection_known_true_rank_position = " .. tostring(stable_summary.stable_intersection_known_true_rank_position)
        lines[#lines + 1] = "stable_intersection_best_candidate = " .. tostring(hex_u64(stable_summary.stable_intersection_best_candidate))
        lines[#lines + 1] = "stable_intersection_best_score = " .. tostring(stable_summary.stable_intersection_best_score)
        lines[#lines + 1] = "stable_intersection_second_score = " .. tostring(stable_summary.stable_intersection_second_score)
        lines[#lines + 1] = "stable_intersection_score_gap = " .. tostring(stable_summary.stable_intersection_score_gap)
        lines[#lines + 1] = "mode_total_ms = " .. tostring(stable_summary.mode_total_ms)
        lines[#lines + 1] = "known_timed_ms = " .. tostring(stable_summary.known_timed_ms)
        lines[#lines + 1] = "uninstrumented_gap_ms = " .. tostring(stable_summary.uninstrumented_gap_ms)
        lines[#lines + 1] = "uninstrumented_gap_ratio = " .. tostring(stable_summary.uninstrumented_gap_ratio)
        lines[#lines + 1] = "runner_setup_ms = " .. tostring(stable_summary.runner_setup_ms)
        lines[#lines + 1] = "mode_config_ms = " .. tostring(stable_summary.mode_config_ms)
        lines[#lines + 1] = "collector_call_ms = " .. tostring(stable_summary.collector_call_ms)
        lines[#lines + 1] = "collector_ms = " .. tostring(stable_summary.collector_ms)
        lines[#lines + 1] = "filter_ms = " .. tostring(stable_summary.filter_ms)
        lines[#lines + 1] = "prescore_ms = " .. tostring(stable_summary.prescore_ms)
        lines[#lines + 1] = "prescore_read_ms = " .. tostring(stable_summary.prescore_read_ms)
        lines[#lines + 1] = "prescore_score_ms = " .. tostring(stable_summary.prescore_score_ms)
        lines[#lines + 1] = "prescore_sort_ms = " .. tostring(stable_summary.prescore_sort_ms)
        lines[#lines + 1] = "prescore_select_ms = " .. tostring(stable_summary.prescore_select_ms)
        lines[#lines + 1] = "prescore_detail_ms = " .. tostring(stable_summary.prescore_detail_ms)
        lines[#lines + 1] = "stable_intersection_ms = " .. tostring(stable_summary.stable_intersection_ms)
        lines[#lines + 1] = "stable_snapshot_A_ms = " .. tostring(stable_summary.stable_snapshot_A_ms)
        lines[#lines + 1] = "stable_snapshot_B_ms = " .. tostring(stable_summary.stable_snapshot_B_ms)
        lines[#lines + 1] = "stable_intersection_build_ms = " .. tostring(stable_summary.stable_intersection_build_ms)
        lines[#lines + 1] = "report_render_ms = " .. tostring(stable_summary.report_render_ms)
        lines[#lines + 1] = "compact_report_enabled = " .. tostring(stable_summary.compact_report_enabled)
        lines[#lines + 1] = "skipped_verbose_report_sections = " .. tostring(stable_summary.skipped_verbose_report_sections)
        lines[#lines + 1] = "verbose_report_section_count = " .. tostring(stable_summary.verbose_report_section_count)
        lines[#lines + 1] = "stable_report_render_ms = " .. tostring(stable_summary.stable_report_render_ms)
        lines[#lines + 1] = "diagnostic_render_ms = " .. tostring(stable_summary.diagnostic_render_ms)
        lines[#lines + 1] = "console_print_ms = " .. tostring(stable_summary.console_print_ms)
        lines[#lines + 1] = "file_write_ms = " .. tostring(stable_summary.file_write_ms)
        lines[#lines + 1] = "write_log_ms = " .. tostring(stable_summary.write_log_ms)
        lines[#lines + 1] = "total_ms = " .. tostring(stable_summary.total_ms)
        lines[#lines + 1] = "log_size_bytes = " .. tostring(stable_summary.log_size_bytes)
      end
      lines[#lines + 1] = ""
    end
  end

  return table.concat(lines, "\r\n")
end

local function resolve_mode_config(mode_entry)
  if type(mode_entry) == "string" then
    local preset = MODE_PRESETS[mode_entry]
    if preset == nil then
      error("unknown mode preset: " .. tostring(mode_entry))
    end
    return {
      mode = preset.mode,
      probe_full_foundlist = preset.probe_full_foundlist,
    }
  end

  if type(mode_entry) ~= "table" then
    error("unsupported mode entry: " .. tostring(mode_entry))
  end

  local preset = MODE_PRESETS[mode_entry.name or mode_entry.mode]
  if preset == nil then
    error("unknown mode preset: " .. tostring(mode_entry.name or mode_entry.mode))
  end

  return {
    mode = mode_entry.mode or mode_entry.name or preset.mode,
    probe_full_foundlist = mode_entry.probe_full_foundlist,
  }
end

local function run_case_mode(case_cfg, mode_entry, batch_id)
  local total_start_ms = now_ms()
  local mode_config_start_ms = now_ms()
  local mode_cfg = resolve_mode_config(mode_entry)
  if mode_cfg.probe_full_foundlist == nil then
    local preset = MODE_PRESETS[mode_cfg.mode]
    mode_cfg.probe_full_foundlist = preset and preset.probe_full_foundlist or false
  end
  local mode_config_ms = elapsed_ms(mode_config_start_ms)

  local runner_setup_start_ms = now_ms()
  active_log_lines = {}
  local safe_session = sanitize_token(case_cfg.session_id)
  local safe_case = sanitize_token(case_cfg.case_id)
  local log_path = string.format(
    "%s\\%s__%s__%s__%s.log",
    OUTPUT_DIR,
    batch_id,
    safe_session,
    safe_case,
    sanitize_token(mode_cfg.mode)
  )
  local runner_setup_ms = elapsed_ms(runner_setup_start_ms)

  local collector_ms = nil
  local report_render_ms = nil
  local console_print_ms = nil
  local compact_report_enabled = nil
  local skipped_verbose_report_sections = nil
  local verbose_report_section_count = nil
  local ok, bundle_or_err = xpcall(function()
    local module_load_start_ms = now_ms()
    load_modules()
    runner_setup_ms = runner_setup_ms + elapsed_ms(module_load_start_ms)

    local collector_start_ms = now_ms()
    local bundle = MVP0FoundList.run({
      max_candidates = case_cfg.max_candidates,
      scan_budget = case_cfg.scan_budget,
      target_value_pattern = case_cfg.target_value_pattern,
      target_value_float = case_cfg.target_value_float,
      session_id = case_cfg.session_id,
      filter_target_match = case_cfg.filter_target_match,
      use_prescore_selection = case_cfg.use_prescore_selection,
      stable_filter_intersection_enabled = case_cfg.stable_filter_intersection_enabled,
      probe_full_foundlist = mode_cfg.probe_full_foundlist,
      known_true_addr = case_cfg.known_true_addr,
    })
    collector_ms = elapsed_ms(collector_start_ms)

    local report_console_start_ms = console_print_total_ms
    local report_render_start_ms = now_ms()
    local emit_verbose_report = should_emit_verbose_bundle_report(case_cfg, bundle, bundle.result)
    local report_policy
    if emit_verbose_report then
      report_policy = make_report_policy(false, "none", 2)
      emit_bundle_report(case_cfg, mode_cfg, bundle, report_policy)
    else
      report_policy = make_report_policy(true, "truth_probe_logs, report_text", 0)
      emit_compact_bundle_report(case_cfg, mode_cfg, bundle, report_policy)
    end
    compact_report_enabled = report_policy.compact_report_enabled
    skipped_verbose_report_sections = report_policy.skipped_verbose_report_sections
    verbose_report_section_count = report_policy.verbose_report_section_count
    report_render_ms = elapsed_ms(report_render_start_ms)
    console_print_ms = console_print_total_ms - report_console_start_ms
    return bundle
  end, debug.traceback)

  if not ok then
    print("=== run_error ===")
    print(bundle_or_err)
  end

  local log_text = table.concat(active_log_lines, "\r\n") .. "\r\n"
  local log_size_bytes = #log_text
  local write_start_ms = now_ms()
  write_text_file(log_path, log_text)
  local write_log_ms = elapsed_ms(write_start_ms)
  local file_write_ms = write_log_ms
  active_log_lines = nil
  local total_ms = elapsed_ms(total_start_ms)

  if not ok then
    return finalize_timing_summary({
      case_id = case_cfg.case_id,
      case_config_loaded = case_cfg.case_config_loaded,
      case_config_path = case_cfg.case_config_path,
      known_true_addr_source = case_cfg.known_true_addr_source,
      target_value_source = case_cfg.target_value_source,
      diagnostic_level = case_cfg.diagnostic_level,
      session_id = case_cfg.session_id,
      mode = mode_cfg.mode,
      raw_count = nil,
      unique_count = nil,
      filtered_count = nil,
      matched_count = nil,
      value_mismatch_count = nil,
      read_failed_count = nil,
      retry_recovered_count = nil,
      retry_still_mismatch_count = nil,
      retry_read_failed_count = nil,
      delayed_recheck_enabled = nil,
      delayed_recheck_candidate_count = nil,
      delayed_recovered_count = nil,
      delayed_still_mismatch_count = nil,
      delayed_read_failed_count = nil,
      stable_intersection_enabled = nil,
      pass1_matched_count = nil,
      pass2_matched_count = nil,
      intersection_filtered_count = nil,
      pass1_only_count = nil,
      pass2_only_count = nil,
      pass1_read_failed_count = nil,
      pass2_read_failed_count = nil,
      pass1_matched_addresses = {},
      pass2_matched_addresses = {},
      pass1_only_addresses = {},
      pass2_only_addresses = {},
      matched_addresses = {},
      probe_full_foundlist = mode_cfg.probe_full_foundlist,
      known_true_addr = case_cfg.known_true_addr,
      target_value_addr = case_cfg.target_value_addr,
      target_value_pattern = case_cfg.target_value_pattern,
      target_value_float = case_cfg.target_value_float,
      mode_config_ms = mode_config_ms,
      runner_setup_ms = runner_setup_ms,
      collector_ms = collector_ms,
      collector_call_ms = collector_ms,
      filter_ms = nil,
      prescore_ms = nil,
      stable_intersection_ms = nil,
      report_render_ms = report_render_ms,
      compact_report_enabled = compact_report_enabled,
      skipped_verbose_report_sections = skipped_verbose_report_sections,
      verbose_report_section_count = verbose_report_section_count,
      diagnostic_render_ms = nil,
      console_print_ms = console_print_ms,
      file_write_ms = file_write_ms,
      write_log_ms = write_log_ms,
      total_ms = total_ms,
      log_size_bytes = log_size_bytes,
      log_path = log_path,
      error = bundle_or_err,
    })
  end

  local filter_debug = get_filter_debug_snapshot()
  local summary = build_run_summary(case_cfg, mode_cfg, bundle_or_err, log_path, filter_debug, {
    mode_config_ms = mode_config_ms,
    runner_setup_ms = runner_setup_ms,
    collector_ms = collector_ms,
    collector_call_ms = collector_ms,
    stable_intersection_ms = nil,
    report_render_ms = report_render_ms,
    compact_report_enabled = compact_report_enabled,
    skipped_verbose_report_sections = skipped_verbose_report_sections,
    verbose_report_section_count = verbose_report_section_count,
    console_print_ms = console_print_ms,
    file_write_ms = file_write_ms,
    write_log_ms = write_log_ms,
    total_ms = total_ms,
    log_size_bytes = log_size_bytes,
  })
  finalize_timing_summary(summary)
  local diagnostic_render_start_ms = now_ms()
  print_run_summary(summary)
  summary.diagnostic_render_ms = elapsed_ms(diagnostic_render_start_ms)
  return summary
end

local function main()
  if type(getLuaEngine) == "function" then
    local engine = getLuaEngine()
    if engine ~= nil and type(engine.show) == "function" then
      engine.show()
    end
  end

  ensure_directory(OUTPUT_DIR)

  local batch_id = os.date("%Y%m%d-%H%M%S")
  local summaries = {}

  for _, case_cfg in ipairs(RUN_CASES) do
    local case_summaries = {}
    for _, mode_entry in ipairs(case_cfg.modes or {}) do
      local summary = run_case_mode(case_cfg, mode_entry, batch_id)
      summaries[#summaries + 1] = summary
      case_summaries[summary.mode] = summary
    end

    local runtime_empty_diagnostics = build_runtime_empty_diagnostics(case_summaries)
    apply_runtime_empty_diagnostics(case_summaries.no_probe_A, runtime_empty_diagnostics)
    apply_runtime_empty_diagnostics(case_summaries.with_probe, runtime_empty_diagnostics)
    apply_runtime_empty_diagnostics(case_summaries.no_probe_B, runtime_empty_diagnostics)

    local stable_summary = run_stable_intersection_mode(case_cfg, case_summaries.no_probe_A, case_summaries.no_probe_B, batch_id, runtime_empty_diagnostics)
    if stable_summary ~= nil then
      summaries[#summaries + 1] = stable_summary
    end
  end

  local summary_path = string.format("%s\\%s__summary.txt", OUTPUT_DIR, batch_id)
  write_text_file(summary_path, render_summary_file(batch_id, summaries))
  local diagnostic_diff_path = string.format("%s\\%s__diagnostic_diff.txt", OUTPUT_DIR, batch_id)
  write_text_file(diagnostic_diff_path, render_diagnostic_diff_file(batch_id, summaries))

  print("=== batch_output ===")
  print_kv("summary_path", summary_path)
  print_kv("diagnostic_diff_path", diagnostic_diff_path)
  print_kv("batch_runs", #summaries)
end

main()
