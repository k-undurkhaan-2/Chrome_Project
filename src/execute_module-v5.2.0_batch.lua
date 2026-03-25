-- execute_module-v5.2.0
-- Batch no-probe / with-probe runner with automatic log persistence.

local REPORT_MODULE_PATH = [[D:\Lua Developer\mvp0_candidate_report.lua]]
local COLLECTOR_MODULE_PATH = [[D:\Lua Developer\mvp0_foundlist_collector.lua]]
local OUTPUT_DIR = [[D:\armedforces.io-v2\log\auto_output]]

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

local RUN_CASES = {
  {
    case_id = "case_01",
    session_id = "collector-retest-wide-2",
    known_true_addr = 0x100061C8D48,
    target_value_pattern = 0x42C80000,
    target_value_float = 100.0,
    max_candidates = 100,
    scan_budget = 8000,
    filter_target_match = true,
    use_prescore_selection = true,
    stable_filter_intersection_enabled = false,
    modes = {
      {name = "no_probe_A", probe_full_foundlist = false},
      {name = "with_probe", probe_full_foundlist = true},
      {name = "no_probe_B", probe_full_foundlist = false},
    },
  },
}

local original_print = print
local active_log_lines = nil

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
  original_print(...)
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

  return {
    delayed_snapshot_intersection_enabled = true,
    no_probe_stable_intersection_count = #full_intersection,
    no_probe_union_count = count_set_members(union_set),
    no_probe_A_only_count = #full_a_only,
    no_probe_B_only_count = #full_b_only,
    known_true_in_no_probe_stable_intersection = (known_true_addr ~= nil) and (intersection_set[known_true_addr] == true) or nil,
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
  }
end

local function emit_bundle_report(case_cfg, mode_cfg, bundle)
  local result = (bundle and bundle.result) or {}

  print("=== run_config ===")
  print_kv("case_id", case_cfg.case_id)
  print_kv("session_id", case_cfg.session_id)
  print_kv("mode", mode_cfg.mode)
  print_hex_kv("known_true_addr", case_cfg.known_true_addr)
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

  print_log_table("truth_probe_logs", bundle and bundle.truth_probe_logs)

  print("=== known_true_debug ===")
  print_kv("known_true_rank_position", pick_known_true_field(bundle, result, "known_true_rank_position"))
  print_kv("known_true_base_score", pick_known_true_field(bundle, result, "known_true_base_score"))
  print_kv("known_true_final_score", pick_known_true_field(bundle, result, "known_true_final_score"))
  print_kv("known_true_tie_break_vector", pick_known_true_field(bundle, result, "known_true_tie_break_vector"))

  print("=== report_text ===")
  if result and result.report_text then
    print(result.report_text)
  else
    print("bundle.result.report_text = nil")
  end
end

local function build_run_summary(case_cfg, mode_cfg, bundle, log_path, filter_debug)
  local result = (bundle and bundle.result) or {}
  local best = result and result.best or nil

  return {
    case_id = case_cfg.case_id,
    session_id = case_cfg.session_id,
    mode = mode_cfg.mode,
    probe_full_foundlist = mode_cfg.probe_full_foundlist,
    known_true_addr = case_cfg.known_true_addr,
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
  print_kv("session_id", summary.session_id)
  print_kv("mode", summary.mode)
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
  if summary.stable_intersection_base_snapshot ~= nil then
    print_kv("stable_intersection_enabled", summary.stable_intersection_enabled)
    print_kv("stable_intersection_base_snapshot", summary.stable_intersection_base_snapshot)
    print_kv("stable_intersection_filtered_count", summary.stable_intersection_filtered_count)
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
    lines[#lines + 1] = "known_true_addr = " .. tostring(hex_u64(summary.known_true_addr))
    lines[#lines + 1] = "probe_full_foundlist = " .. tostring(summary.probe_full_foundlist)
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
    if summary.stable_intersection_base_snapshot ~= nil then
      lines[#lines + 1] = "stable_intersection_enabled = " .. tostring(summary.stable_intersection_enabled)
      lines[#lines + 1] = "stable_intersection_base_snapshot = " .. tostring(summary.stable_intersection_base_snapshot)
      lines[#lines + 1] = "stable_intersection_filtered_count = " .. tostring(summary.stable_intersection_filtered_count)
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
      lines[#lines + 1] = "--- " .. tostring(key) .. " ---"
      lines[#lines + 1] = "delayed_snapshot_intersection_enabled = " .. tostring(analysis.delayed_snapshot_intersection_enabled)
      lines[#lines + 1] = "no_probe_stable_intersection_count = " .. tostring(analysis.no_probe_stable_intersection_count)
      lines[#lines + 1] = "no_probe_union_count = " .. tostring(analysis.no_probe_union_count)
      lines[#lines + 1] = "no_probe_A_only_count = " .. tostring(analysis.no_probe_A_only_count)
      lines[#lines + 1] = "no_probe_B_only_count = " .. tostring(analysis.no_probe_B_only_count)
      lines[#lines + 1] = "known_true_in_no_probe_stable_intersection = " .. tostring(analysis.known_true_in_no_probe_stable_intersection)
      lines[#lines + 1] = "matched_only_in_no_probe_A_vs_B = " .. format_address_sample(analysis.matched_only_in_no_probe_A_vs_B)
      lines[#lines + 1] = "matched_only_in_no_probe_B_vs_A = " .. format_address_sample(analysis.matched_only_in_no_probe_B_vs_A)
      lines[#lines + 1] = "matched_in_no_probe_intersection = " .. format_address_sample(analysis.matched_in_no_probe_intersection)
      lines[#lines + 1] = ""
    end
  end

  return table.concat(lines, "\r\n")
end

local function emit_stable_intersection_report(case_cfg, bundle, summary)
  print("=== stable_intersection_experiment ===")
  print_kv("case_id", case_cfg.case_id)
  print_kv("session_id", case_cfg.session_id)
  print_kv("mode", "stable_no_probe_intersection")
  print_kv("stable_intersection_enabled", summary.stable_intersection_enabled)
  print_kv("stable_intersection_base_snapshot", summary.stable_intersection_base_snapshot)
  print_kv("stable_intersection_filtered_count", summary.stable_intersection_filtered_count)
  print_kv("stable_intersection_true_in_filtered", summary.stable_intersection_true_in_filtered)
  print_kv("stable_intersection_prescored_count", summary.stable_intersection_prescored_count)
  print_kv("stable_intersection_selected_count", summary.stable_intersection_selected_count)
  print_kv("stable_intersection_known_true_rank_position", summary.stable_intersection_known_true_rank_position)
  print_hex_kv("stable_intersection_best_candidate", summary.stable_intersection_best_candidate)
  print_kv("stable_intersection_best_score", summary.stable_intersection_best_score)
  print_kv("stable_intersection_second_score", summary.stable_intersection_second_score)
  print_kv("stable_intersection_score_gap", summary.stable_intersection_score_gap)
  print_kv("no_probe_stable_intersection_count", summary.no_probe_stable_intersection_count)
  print_kv("no_probe_union_count", summary.no_probe_union_count)
  print_kv("no_probe_A_only_count", summary.no_probe_A_only_count)
  print_kv("no_probe_B_only_count", summary.no_probe_B_only_count)
  print_kv("known_true_in_no_probe_stable_intersection", summary.known_true_in_no_probe_stable_intersection)

  print("=== report_text ===")
  if bundle and bundle.result and bundle.result.report_text then
    print(bundle.result.report_text)
  else
    print("bundle.result.report_text = nil")
  end
end

local function build_stable_intersection_summary(case_cfg, bundle, log_path, analysis, base_snapshot)
  local result = (bundle and bundle.result) or {}
  local best = result and result.best or nil

  return {
    case_id = case_cfg.case_id,
    session_id = case_cfg.session_id,
    mode = "stable_no_probe_intersection",
    probe_full_foundlist = false,
    known_true_addr = case_cfg.known_true_addr,
    raw_count = nil,
    unique_count = nil,
    known_true_rank_position = bundle and bundle.known_true_rank_position or nil,
    known_true_final_score = bundle and bundle.known_true_final_score or nil,
    true_in_selected = bundle and bundle.true_in_selected or nil,
    known_true_raw_admission_path = base_snapshot and base_snapshot.known_true_raw_admission_path or nil,
    selected_count = bundle and bundle.selected_count or nil,
    filtered_count = analysis and analysis.no_probe_stable_intersection_count or nil,
    matched_count = analysis and analysis.no_probe_stable_intersection_count or nil,
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
    stable_intersection_enabled = true,
    stable_intersection_base_snapshot = "no_probe_B",
    stable_intersection_filtered_count = analysis and analysis.no_probe_stable_intersection_count or nil,
    stable_intersection_true_in_filtered = bundle and bundle.true_in_filtered or nil,
    stable_intersection_prescored_count = bundle and bundle.prescored_count or nil,
    stable_intersection_selected_count = bundle and bundle.selected_count or nil,
    stable_intersection_known_true_rank_position = bundle and bundle.known_true_rank_position or nil,
    stable_intersection_best_candidate = best and best.candidate and best.candidate.value_addr or nil,
    stable_intersection_best_score = result and result.best and result.best.score or nil,
    stable_intersection_second_score = result and result.second and result.second.score or nil,
    stable_intersection_score_gap = result and result.score_gap or nil,
    no_probe_stable_intersection_count = analysis and analysis.no_probe_stable_intersection_count or nil,
    no_probe_union_count = analysis and analysis.no_probe_union_count or nil,
    no_probe_A_only_count = analysis and analysis.no_probe_A_only_count or nil,
    no_probe_B_only_count = analysis and analysis.no_probe_B_only_count or nil,
    known_true_in_no_probe_stable_intersection = analysis and analysis.known_true_in_no_probe_stable_intersection or nil,
    best_candidate_addr = best and best.candidate and best.candidate.value_addr or nil,
    best_score = result and result.best and result.best.score or nil,
    second_score = result and result.second and result.second.score or nil,
    score_gap = result and result.score_gap or nil,
    confidence = result and result.confidence or nil,
    log_path = log_path,
  }
end

local function run_stable_intersection_mode(case_cfg, no_probe_a, no_probe_b, batch_id)
  local analysis = build_no_probe_snapshot_intersection_analysis(no_probe_a, no_probe_b)
  if analysis == nil then
    return nil
  end

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

  local ok, bundle_or_err = xpcall(function()
    load_modules()
    local bundle = MVP0FoundList.run_from_filtered_addresses({
      filtered_addresses = analysis.full_intersection_addresses,
      max_candidates = case_cfg.max_candidates,
      target_value_pattern = case_cfg.target_value_pattern,
      target_value_float = case_cfg.target_value_float,
      session_id = case_cfg.session_id,
      use_prescore_selection = case_cfg.use_prescore_selection,
      known_true_addr = case_cfg.known_true_addr,
      known_true_raw_admission_path = no_probe_b and no_probe_b.known_true_raw_admission_path or nil,
      raw_probe_full_foundlist_enabled = false,
      session_mode = "stable_no_probe_intersection",
      source_mode = "stable_no_probe_intersection",
    })

    local summary = build_stable_intersection_summary(case_cfg, bundle, log_path, analysis, no_probe_b)
    emit_stable_intersection_report(case_cfg, bundle, summary)
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
  write_text_file(log_path, log_text)
  active_log_lines = nil

  if not ok then
    return {
      case_id = case_cfg.case_id,
      session_id = case_cfg.session_id,
      mode = "stable_no_probe_intersection",
      known_true_addr = case_cfg.known_true_addr,
      log_path = log_path,
      error = bundle_or_err,
      stable_intersection_enabled = true,
      stable_intersection_base_snapshot = "no_probe_B",
      stable_intersection_filtered_count = analysis.no_probe_stable_intersection_count,
      stable_intersection_true_in_filtered = nil,
      stable_intersection_prescored_count = nil,
      stable_intersection_selected_count = nil,
      stable_intersection_known_true_rank_position = nil,
      stable_intersection_best_candidate = nil,
      stable_intersection_best_score = nil,
      stable_intersection_second_score = nil,
      stable_intersection_score_gap = nil,
      no_probe_stable_intersection_count = analysis.no_probe_stable_intersection_count,
      no_probe_union_count = analysis.no_probe_union_count,
      no_probe_A_only_count = analysis.no_probe_A_only_count,
      no_probe_B_only_count = analysis.no_probe_B_only_count,
      known_true_in_no_probe_stable_intersection = analysis.known_true_in_no_probe_stable_intersection,
    }
  end

  print_run_summary(bundle_or_err.summary)
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

      lines[#lines + 1] = "--- " .. tostring(key) .. " ---"

      for _, summary in ipairs({no_probe_a, with_probe, no_probe_b}) do
        lines[#lines + 1] = "[" .. tostring(summary.mode) .. "]"
        lines[#lines + 1] = "raw_count = " .. tostring(summary.raw_count)
        lines[#lines + 1] = "unique_count = " .. tostring(summary.unique_count)
        lines[#lines + 1] = "filtered_count = " .. tostring(summary.filtered_count)
        lines[#lines + 1] = "matched_count = " .. tostring(summary.matched_count)
        lines[#lines + 1] = "value_mismatch_count = " .. tostring(summary.value_mismatch_count)
        lines[#lines + 1] = "read_failed_count = " .. tostring(summary.read_failed_count)
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
        lines[#lines + 1] = "no_probe_stable_intersection_count = " .. tostring(no_probe_snapshot_analysis.no_probe_stable_intersection_count)
        lines[#lines + 1] = "no_probe_union_count = " .. tostring(no_probe_snapshot_analysis.no_probe_union_count)
        lines[#lines + 1] = "no_probe_A_only_count = " .. tostring(no_probe_snapshot_analysis.no_probe_A_only_count)
        lines[#lines + 1] = "no_probe_B_only_count = " .. tostring(no_probe_snapshot_analysis.no_probe_B_only_count)
        lines[#lines + 1] = "known_true_in_no_probe_stable_intersection = " .. tostring(no_probe_snapshot_analysis.known_true_in_no_probe_stable_intersection)
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
      if stable_summary ~= nil then
        lines[#lines + 1] = "[stable_no_probe_intersection]"
        lines[#lines + 1] = "stable_intersection_enabled = " .. tostring(stable_summary.stable_intersection_enabled)
        lines[#lines + 1] = "stable_intersection_base_snapshot = " .. tostring(stable_summary.stable_intersection_base_snapshot)
        lines[#lines + 1] = "stable_intersection_filtered_count = " .. tostring(stable_summary.stable_intersection_filtered_count)
        lines[#lines + 1] = "stable_intersection_true_in_filtered = " .. tostring(stable_summary.stable_intersection_true_in_filtered)
        lines[#lines + 1] = "stable_intersection_prescored_count = " .. tostring(stable_summary.stable_intersection_prescored_count)
        lines[#lines + 1] = "stable_intersection_selected_count = " .. tostring(stable_summary.stable_intersection_selected_count)
        lines[#lines + 1] = "stable_intersection_known_true_rank_position = " .. tostring(stable_summary.stable_intersection_known_true_rank_position)
        lines[#lines + 1] = "stable_intersection_best_candidate = " .. tostring(hex_u64(stable_summary.stable_intersection_best_candidate))
        lines[#lines + 1] = "stable_intersection_best_score = " .. tostring(stable_summary.stable_intersection_best_score)
        lines[#lines + 1] = "stable_intersection_second_score = " .. tostring(stable_summary.stable_intersection_second_score)
        lines[#lines + 1] = "stable_intersection_score_gap = " .. tostring(stable_summary.stable_intersection_score_gap)
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
  local mode_cfg = resolve_mode_config(mode_entry)
  if mode_cfg.probe_full_foundlist == nil then
    local preset = MODE_PRESETS[mode_cfg.mode]
    mode_cfg.probe_full_foundlist = preset and preset.probe_full_foundlist or false
  end

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

  local ok, bundle_or_err = xpcall(function()
    load_modules()

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

    emit_bundle_report(case_cfg, mode_cfg, bundle)
    return bundle
  end, debug.traceback)

  if not ok then
    print("=== run_error ===")
    print(bundle_or_err)
  end

  local log_text = table.concat(active_log_lines, "\r\n") .. "\r\n"
  write_text_file(log_path, log_text)
  active_log_lines = nil

  if not ok then
    return {
      case_id = case_cfg.case_id,
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
      log_path = log_path,
      error = bundle_or_err,
    }
  end

  local filter_debug = get_filter_debug_snapshot()
  local summary = build_run_summary(case_cfg, mode_cfg, bundle_or_err, log_path, filter_debug)
  print_run_summary(summary)
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

    local stable_summary = run_stable_intersection_mode(case_cfg, case_summaries.no_probe_A, case_summaries.no_probe_B, batch_id)
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
