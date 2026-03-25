-- Minimal FoundList-based candidate acquisition helper for MVP-0
--
-- Usage example inside Cheat Engine Lua Engine:
--
-- dofile('mvp0_candidate_report.lua')
-- dofile('mvp0_foundlist_collector.lua')
--
-- local bundle = MVP0FoundList.run({
--   max_candidates = 20,
--   scan_budget = 2000,
--   target_value_pattern = 0x42C80000,
--   target_value_float = 100.0,
--   session_id = 'session-6',
--   filter_target_match = true,
--   use_prescore_selection = true,
--   known_true_addr = 0x2B0061C8D48,
-- })
--
-- print(bundle.result.report_text)
-- print('true_in_full_foundlist = ' .. tostring(bundle.true_in_full_foundlist))
-- print('true_in_raw            = ' .. tostring(bundle.true_in_raw))
-- print('true_in_unique         = ' .. tostring(bundle.true_in_unique))
-- print('true_in_filtered       = ' .. tostring(bundle.true_in_filtered))
-- print('true_in_prescored      = ' .. tostring(bundle.true_in_prescored))
-- print('true_in_selected       = ' .. tostring(bundle.true_in_selected))

local MVP0FoundList = {}
MVP0FoundList.LAST_FILTER_DEBUG = nil

MVP0FoundList.CONFIG = {
  default_max_candidates = 20,
  default_scan_budget = 2000,
  default_filter_target_match = true,
  default_use_prescore_selection = true,
  default_bucket_shift = 20,      -- 1 MiB-ish region buckets
  default_max_per_bucket = 3,
  default_probe_full_foundlist = true,
  default_probe_window_radius = 256,
  raw_even_ratio = 0.70,
  raw_structure_ratio = 0.15,
  raw_neighborhood_ratio = 0.15,
  raw_structure_scout_budget = 2048,
  raw_neighborhood_radius = 2,
  raw_structure_signature_cap = 2,
}

local function assert_mvp0_loaded()
  if type(MVP0) ~= 'table'
    or type(MVP0.make_input) ~= 'function'
    or type(MVP0.run) ~= 'function'
    or type(MVP0.score_candidate) ~= 'function'
    or type(MVP0.compare_scored_candidates) ~= 'function'
  then
    error("MVP0 module is not loaded. Run dofile('mvp0_candidate_report.lua') first.")
  end
end

local function u32(n)
  if n == nil then
    return nil
  end
  if n < 0 then
    return n + 0x100000000
  end
  return n
end

local function read_u32(addr, raw_debug_state, value_addr, field_name)
  local ok, value = pcall(readInteger, addr)
  if not ok or value == nil then
    if raw_debug_state ~= nil then
      raw_debug_state.raw_read_fail_count = (raw_debug_state.raw_read_fail_count or 0) + 1
      if field_name ~= nil then
        local field_counts = raw_debug_state.raw_read_fail_field_counts
        if field_counts ~= nil then
          field_counts[field_name] = (field_counts[field_name] or 0) + 1
        end
      end
      if value_addr ~= nil then
        raw_debug_state.last_read_fail_candidate_addr = value_addr
      end
    end
    return nil
  end
  return u32(value)
end

local function to_address_number(addr_value)
  if type(addr_value) == 'number' then
    return addr_value
  end
  return getAddress(addr_value)
end

local function region_bucket(addr, shift)
  return math.floor(addr / (2 ^ shift))
end

local FRONT_KEYS = {"f08", "f18", "f20"}
local TAIL_KEYS = {"f68", "f70", "f78"}
local STRUCT_KEYS = {"f08", "f18", "f20", "f58", "f68", "f70", "f78"}

local function fixed_count_bucket(value)
  if value == nil or value <= 0 then
    return "0"
  end
  if value == 1 then
    return "1"
  end
  if value == 2 then
    return "2"
  end
  return "3+"
end

local function is_small_int_like(x)
  x = u32(x)
  return type(x) == 'number' and x ~= 0 and x < 0x1000
end

local function is_suspicious_float_like(x)
  local value = u32(x)
  if type(value) ~= 'number' then
    return false
  end
  return MVP0.CONFIG.suspicious[value] == true
end

local function is_pointer_like_rough(x)
  local value = u32(x)
  if type(value) ~= 'number' then
    return false
  end

  local thresholds = MVP0.CONFIG.ranking.thresholds
  return value ~= 0
    and value >= thresholds.address_floor
    and (value % (thresholds.alignment_mask + 1)) == 0
    and not is_small_int_like(value)
    and not is_suspicious_float_like(value)
end

local function compute_raw_quota_plan(wanted)
  local even_quota = math.floor(wanted * MVP0FoundList.CONFIG.raw_even_ratio)
  local structure_quota = math.floor(wanted * MVP0FoundList.CONFIG.raw_structure_ratio)
  local neighborhood_quota = wanted - even_quota - structure_quota

  if even_quota < 1 then
    even_quota = math.min(1, wanted)
  end
  if neighborhood_quota < 0 then
    neighborhood_quota = 0
  end

  local total = even_quota + structure_quota + neighborhood_quota
  if total < wanted then
    even_quota = even_quota + (wanted - total)
  elseif total > wanted then
    local overflow = total - wanted
    local trim = math.min(neighborhood_quota, overflow)
    neighborhood_quota = neighborhood_quota - trim
    overflow = overflow - trim
    if overflow > 0 then
      trim = math.min(structure_quota, overflow)
      structure_quota = structure_quota - trim
      overflow = overflow - trim
    end
    if overflow > 0 then
      even_quota = math.max(0, even_quota - overflow)
    end
  end

  return {
    even_quota = even_quota,
    structure_quota = structure_quota,
    neighborhood_quota = neighborhood_quota,
  }
end

local function bump_count(map, key, delta)
  if key == nil then
    return
  end
  map[key] = (map[key] or 0) + (delta or 1)
  if map[key] <= 0 then
    map[key] = nil
  end
end

local function format_count_map(map)
  local parts = {}
  for key, value in pairs(map or {}) do
    parts[#parts + 1] = tostring(key) .. '=' .. tostring(value)
  end
  table.sort(parts)
  if #parts == 0 then
    return 'none'
  end
  return table.concat(parts, ', ')
end

local function record_reject_reason(raw_debug_state, reason)
  if raw_debug_state == nil or reason == nil then
    return
  end
  bump_count(raw_debug_state.raw_quota_reject_reason_counts, reason, 1)
end

local function add_raw_index(indices, used, source_by_index, source_counts, idx, source)
  if idx == nil or idx < 0 or used[idx] then
    return false
  end
  used[idx] = true
  indices[#indices + 1] = idx
  source_by_index[idx] = source
  bump_count(source_counts, source, 1)
  return true
end

local function count_truthy_keys(map)
  local count = 0
  for _, value in pairs(map) do
    if value then
      count = count + 1
    end
  end
  return count
end

local function collect_candidate_snapshot(value_addr, raw_debug_state)
  local off = MVP0.CONFIG.offsets
  local base_addr = value_addr - MVP0.CONFIG.value_offset
  return {
    value_addr = value_addr,
    base_addr = base_addr,
    f08 = read_u32(base_addr + off.f08, raw_debug_state, value_addr, 'f08'),
    f18 = read_u32(base_addr + off.f18, raw_debug_state, value_addr, 'f18'),
    f20 = read_u32(base_addr + off.f20, raw_debug_state, value_addr, 'f20'),
    f28 = read_u32(base_addr + off.f28, raw_debug_state, value_addr, 'f28'),
    f58 = read_u32(base_addr + off.f58, raw_debug_state, value_addr, 'f58'),
    f68 = read_u32(base_addr + off.f68, raw_debug_state, value_addr, 'f68'),
    f70 = read_u32(base_addr + off.f70, raw_debug_state, value_addr, 'f70'),
    f78 = read_u32(base_addr + off.f78, raw_debug_state, value_addr, 'f78'),
  }
end

local function evaluate_raw_structure(foundlist, idx, target_value_pattern, feature_cache, raw_debug_state)
  if feature_cache[idx] ~= nil then
    return feature_cache[idx]
  end

  local value_addr = to_address_number(foundlist.Address[idx])
  local snapshot = collect_candidate_snapshot(value_addr, raw_debug_state)
  local thresholds = MVP0.CONFIG.ranking.thresholds
  local feature = {
    index = idx,
    addr = value_addr,
    snapshot = snapshot,
    target_match = snapshot.f28 == target_value_pattern,
    front_nonzero_count = 0,
    tail_nonzero_count = 0,
    nonzero_count = 0,
    front_pointer_count = 0,
    tail_pointer_count = 0,
    pointer_count = 0,
    pointer_region_count = 0,
    pointer_coherent_pairs = 0,
    small_int_count = 0,
    duplicate_nonzero_count = 0,
    layout_hint = 'weak',
    structure_eligible = false,
    score = 0,
    signature = 'weak',
    rejection_reason = nil,
  }

  local pointer_values = {}
  local pointer_region_map = {}
  local nonzero_counts = {}

  for _, key in ipairs(FRONT_KEYS) do
    local value = snapshot[key]
    if type(value) == 'number' and value ~= 0 then
      feature.front_nonzero_count = feature.front_nonzero_count + 1
      feature.nonzero_count = feature.nonzero_count + 1
      nonzero_counts[value] = (nonzero_counts[value] or 0) + 1
    end
    if is_pointer_like_rough(value) then
      feature.front_pointer_count = feature.front_pointer_count + 1
      feature.pointer_count = feature.pointer_count + 1
      pointer_values[#pointer_values + 1] = value
      pointer_region_map[region_bucket(value, thresholds.same_region_shift)] = true
    elseif is_small_int_like(value) then
      feature.small_int_count = feature.small_int_count + 1
    end
  end

  for _, key in ipairs(TAIL_KEYS) do
    local value = snapshot[key]
    if type(value) == 'number' and value ~= 0 then
      feature.tail_nonzero_count = feature.tail_nonzero_count + 1
      feature.nonzero_count = feature.nonzero_count + 1
      nonzero_counts[value] = (nonzero_counts[value] or 0) + 1
    end
    if is_pointer_like_rough(value) then
      feature.tail_pointer_count = feature.tail_pointer_count + 1
      feature.pointer_count = feature.pointer_count + 1
      pointer_values[#pointer_values + 1] = value
      pointer_region_map[region_bucket(value, thresholds.same_region_shift)] = true
    elseif is_small_int_like(value) then
      feature.small_int_count = feature.small_int_count + 1
    end
  end

  if is_small_int_like(snapshot.f58) then
    feature.small_int_count = feature.small_int_count + 1
  end

  for _, count in pairs(nonzero_counts) do
    if count > 1 then
      feature.duplicate_nonzero_count = feature.duplicate_nonzero_count + (count - 1)
    end
  end

  feature.pointer_region_count = count_truthy_keys(pointer_region_map)

  for i = 1, #pointer_values do
    for j = i + 1, #pointer_values do
      if region_bucket(pointer_values[i], thresholds.same_region_shift) == region_bucket(pointer_values[j], thresholds.same_region_shift) then
        feature.pointer_coherent_pairs = feature.pointer_coherent_pairs + 1
      end
    end
  end

  local front_signal = feature.front_nonzero_count >= 2 or feature.front_pointer_count >= 1
  local tail_signal = feature.tail_nonzero_count >= 2 or feature.tail_pointer_count >= 1
  local two_sided_signal = front_signal and tail_signal

  if feature.front_pointer_count > 0 and feature.tail_pointer_count > 0 then
    feature.layout_hint = 'front_tail_like'
  elseif feature.tail_pointer_count >= 1 and tail_signal and front_signal and feature.pointer_count >= 3 then
    feature.layout_hint = 'anchor_tail_like'
  elseif feature.pointer_count >= 2 then
    feature.layout_hint = 'scattered_pointer_like'
  end

  if feature.target_match then
    feature.score = feature.score + 6
  end
  if front_signal then
    feature.score = feature.score + 2
  end
  if tail_signal then
    feature.score = feature.score + 2
  end
  if two_sided_signal then
    feature.score = feature.score + 3
  end
  if feature.front_pointer_count > 0 and feature.tail_pointer_count > 0 then
    feature.score = feature.score + 3
  end
  feature.score = feature.score + math.min(feature.pointer_count, 4)
  if feature.pointer_region_count >= 2 then
    feature.score = feature.score + 2
  end
  if feature.pointer_coherent_pairs >= 1 then
    feature.score = feature.score + 1
  end
  if feature.nonzero_count >= 5 then
    feature.score = feature.score + 1
  end
  if feature.layout_hint == 'anchor_tail_like' then
    feature.score = feature.score + 1
  end
  if feature.duplicate_nonzero_count >= 2 then
    feature.score = feature.score - 1
  end
  if feature.small_int_count >= 4 and feature.pointer_count <= 1 then
    feature.score = feature.score - 4
  end
  if feature.pointer_count == 0 then
    feature.score = feature.score - 2
  end

  local has_structure_signal =
    feature.target_match
    and feature.nonzero_count >= 4
    and (
      (feature.front_pointer_count > 0 and feature.tail_pointer_count > 0)
      or (two_sided_signal and feature.pointer_count >= 2)
      or (feature.layout_hint == 'anchor_tail_like' and feature.pointer_count >= 3)
    )
  feature.structure_eligible = has_structure_signal

  if feature.structure_eligible then
    feature.rejection_reason = 'eligible'
  elseif not feature.target_match then
    feature.rejection_reason = 'not_target_match'
  elseif feature.nonzero_count < 4 then
    feature.rejection_reason = 'insufficient_nonzero'
  elseif feature.pointer_count == 0 then
    feature.rejection_reason = 'pointerless'
  elseif feature.small_int_count >= 4 and feature.pointer_count <= 1 then
    feature.rejection_reason = 'small_int_heavy'
  elseif feature.duplicate_nonzero_count >= 2 and feature.pointer_count <= 1 then
    feature.rejection_reason = 'duplicate_heavy'
  elseif feature.pointer_region_count < 2 then
    feature.rejection_reason = 'weak_pointer_regions'
  else
    feature.rejection_reason = 'weak_structure_signal'
  end

  feature.signature = table.concat({
    'layout:' .. feature.layout_hint,
    'fnz:' .. fixed_count_bucket(feature.front_nonzero_count),
    'tnz:' .. fixed_count_bucket(feature.tail_nonzero_count),
    'fp:' .. fixed_count_bucket(feature.front_pointer_count),
    'tp:' .. fixed_count_bucket(feature.tail_pointer_count),
    'pc:' .. fixed_count_bucket(feature.pointer_count),
    'pr:' .. fixed_count_bucket(feature.pointer_region_count),
    'si:' .. fixed_count_bucket(feature.small_int_count),
  }, '|')

  feature_cache[idx] = feature
  return feature
end

local function append_probe_log(logs, stage, message)
  table.insert(logs, string.format('[%s] %s', stage, message))
end

local function find_known_true_index(foundlist, total, known_true_addr)
  if known_true_addr == nil then
    return nil
  end

  for i = 0, total - 1 do
    local addr = to_address_number(foundlist.Address[i])
    if addr == known_true_addr then
      return i
    end
  end

  return nil
end

local function collect_even_spread_indices(total, wanted)
  local indices = {}
  local used = {}

  if wanted >= total then
    for i = 0, total - 1 do
      indices[#indices + 1] = i
    end
    return indices
  end

  for slot = 1, wanted do
    local ratio = (slot - 1) / math.max(wanted - 1, 1)
    local index = math.floor(ratio * (total - 1))
    if not used[index] then
      used[index] = true
      indices[#indices + 1] = index
    end
  end

  table.sort(indices)
  return indices
end

local function find_replacement_position(indices, true_index, start_idx, end_idx)
  local best_pos = nil
  local best_distance = nil
  local best_in_window = false

  for pos, idx in ipairs(indices) do
    local in_window = idx >= start_idx and idx <= end_idx
    local distance = math.abs(idx - true_index)
    if best_pos == nil
        or (in_window and not best_in_window)
        or (in_window == best_in_window and distance < best_distance) then
      best_pos = pos
      best_distance = distance
      best_in_window = in_window
    end
  end

  return best_pos
end

local function collect_windowed_raw_foundlist_addresses(foundlist, total, wanted, known_true_addr, probe_full_foundlist, probe_window_radius, target_value_pattern)
  local probe_logs = {}
  local true_in_raw = false
  local true_in_full_foundlist = false
  local true_in_full_foundlist_checked = false
  local true_index = nil
  local indices = {}
  local used = {}
  local source_by_index = {}
  local source_counts = {}
  local feature_cache = {}
  local known_true_raw_admission_path = nil
  local quota_plan = compute_raw_quota_plan(wanted)
  local fill_quota = math.max(0, wanted - quota_plan.even_quota - quota_plan.structure_quota - quota_plan.neighborhood_quota)
  local probe_quota = probe_full_foundlist and 1 or 0
  local even_used = 0
  local structure_used = 0
  local neighborhood_used = 0
  local fill_used = 0
  local probe_used = 0
  local structure_scout_count = 0
  local structure_eligible_count = 0
  local raw_debug_state = {
    raw_read_fail_count = 0,
    raw_read_fail_field_counts = {},
    raw_quota_reject_reason_counts = {},
    raw_neighbor_dedup_drops = 0,
    last_read_fail_candidate_addr = nil,
  }

  if probe_full_foundlist and known_true_addr ~= nil then
    true_in_full_foundlist_checked = true
    true_index = find_known_true_index(foundlist, total, known_true_addr)
    if true_index ~= nil then
      true_in_full_foundlist = true
      append_probe_log(probe_logs, 'full_foundlist', string.format('known_true_addr found at full index %d', true_index))
    else
      append_probe_log(probe_logs, 'full_foundlist', 'known_true_addr not found in full foundlist')
    end
  elseif known_true_addr ~= nil then
    append_probe_log(probe_logs, 'full_foundlist', 'probe_full_foundlist disabled, full-foundlist truth probe skipped')
    append_probe_log(probe_logs, 'raw_admission', 'probe window safety net disabled for this raw admission pass')
  end

  local spread_indices = collect_even_spread_indices(total, math.min(total, quota_plan.even_quota))
  for _, idx in ipairs(spread_indices) do
    if add_raw_index(indices, used, source_by_index, source_counts, idx, 'even_spread') then
      even_used = even_used + 1
    end
  end

  local structure_ranked = {}
  if quota_plan.structure_quota > 0 or quota_plan.neighborhood_quota > 0 then
    local scout_budget = math.min(total, math.max(quota_plan.structure_quota * 4, MVP0FoundList.CONFIG.raw_structure_scout_budget))
    local scout_indices = collect_even_spread_indices(total, scout_budget)

    for _, idx in ipairs(scout_indices) do
      local feature = evaluate_raw_structure(foundlist, idx, target_value_pattern, feature_cache, raw_debug_state)
      structure_scout_count = structure_scout_count + 1
      if feature.structure_eligible then
        structure_eligible_count = structure_eligible_count + 1
        structure_ranked[#structure_ranked + 1] = feature
      else
        record_reject_reason(raw_debug_state, feature.rejection_reason)
      end
    end
  end

  table.sort(structure_ranked, function(a, b)
    if a.score ~= b.score then
      return a.score > b.score
    end
    return a.addr < b.addr
  end)

  local structure_signature_counts = {}
  local neighborhood_seeds = {}

  for _, feature in ipairs(structure_ranked) do
    if structure_used >= quota_plan.structure_quota then
      break
    end

    local signature_count = structure_signature_counts[feature.signature] or 0
    if signature_count < MVP0FoundList.CONFIG.raw_structure_signature_cap then
      if add_raw_index(indices, used, source_by_index, source_counts, feature.index, 'structure_quota') then
        structure_signature_counts[feature.signature] = signature_count + 1
        structure_used = structure_used + 1
        neighborhood_seeds[#neighborhood_seeds + 1] = feature
      elseif source_by_index[feature.index] == 'even_spread' then
        neighborhood_seeds[#neighborhood_seeds + 1] = feature
        record_reject_reason(raw_debug_state, 'structure_already_selected')
      else
        record_reject_reason(raw_debug_state, 'structure_duplicate')
      end
    else
      record_reject_reason(raw_debug_state, 'structure_signature_cap')
    end
  end

  for _, feature in ipairs(structure_ranked) do
    if #neighborhood_seeds >= math.max(1, quota_plan.neighborhood_quota) then
      break
    end
    if source_by_index[feature.index] == 'even_spread' then
      neighborhood_seeds[#neighborhood_seeds + 1] = feature
    end
  end

  local neighbor_radius = MVP0FoundList.CONFIG.raw_neighborhood_radius
  for _, seed in ipairs(neighborhood_seeds) do
    if neighborhood_used >= quota_plan.neighborhood_quota then
      break
    end

    for distance = 1, neighbor_radius do
      if neighborhood_used >= quota_plan.neighborhood_quota then
        break
      end

      local left_idx = seed.index - distance
      if left_idx >= 0 then
        if add_raw_index(indices, used, source_by_index, source_counts, left_idx, 'neighborhood_quota') then
          neighborhood_used = neighborhood_used + 1
        elseif used[left_idx] then
          raw_debug_state.raw_neighbor_dedup_drops = raw_debug_state.raw_neighbor_dedup_drops + 1
          record_reject_reason(raw_debug_state, 'neighborhood_duplicate')
        end
      else
        record_reject_reason(raw_debug_state, 'neighborhood_out_of_bounds')
      end

      if neighborhood_used >= quota_plan.neighborhood_quota then
        break
      end

      local right_idx = seed.index + distance
      if right_idx < total then
        if add_raw_index(indices, used, source_by_index, source_counts, right_idx, 'neighborhood_quota') then
          neighborhood_used = neighborhood_used + 1
        elseif used[right_idx] then
          raw_debug_state.raw_neighbor_dedup_drops = raw_debug_state.raw_neighbor_dedup_drops + 1
          record_reject_reason(raw_debug_state, 'neighborhood_duplicate')
        end
      else
        record_reject_reason(raw_debug_state, 'neighborhood_out_of_bounds')
      end
    end
  end

  if #indices < wanted then
    local fill_indices = collect_even_spread_indices(total, math.min(total, math.max(wanted * 2, 256)))
    for _, idx in ipairs(fill_indices) do
      if #indices >= wanted then
        break
      end
      if add_raw_index(indices, used, source_by_index, source_counts, idx, 'fill_from_remaining') then
        fill_used = fill_used + 1
      end
    end
  end

  if #indices < wanted then
    for idx = 0, total - 1 do
      if #indices >= wanted then
        break
      end
      if add_raw_index(indices, used, source_by_index, source_counts, idx, 'fill_from_remaining') then
        fill_used = fill_used + 1
      end
    end
  end

  if probe_full_foundlist and true_index ~= nil and not used[true_index] then
    local radius = probe_window_radius or MVP0FoundList.CONFIG.default_probe_window_radius
    local start_idx = math.max(0, true_index - radius)
    local end_idx = math.min(total - 1, true_index + radius)
    append_probe_log(probe_logs, 'raw', string.format(
      'known_true_addr was not admitted by hybrid raw sampling; injecting probe window [%d, %d] around true index',
      start_idx, end_idx
    ))

    if #indices < wanted then
      add_raw_index(indices, used, source_by_index, source_counts, true_index, 'probe_window')
      probe_used = probe_used + 1
      append_probe_log(probe_logs, 'raw', 'known_true_addr injected into raw set from probe window')
    else
      local replace_pos = find_replacement_position(indices, true_index, start_idx, end_idx)
      if replace_pos ~= nil then
        local replaced_index = indices[replace_pos]
        bump_count(source_counts, source_by_index[replaced_index], -1)
        used[replaced_index] = nil
        indices[replace_pos] = true_index
        used[true_index] = true
        source_by_index[true_index] = 'probe_window'
        source_by_index[replaced_index] = nil
        bump_count(source_counts, 'probe_window', 1)
        probe_used = probe_used + 1
        append_probe_log(probe_logs, 'raw', string.format(
          'raw budget saturated; replaced sampled index %d with known_true_addr index %d',
          replaced_index,
          true_index
        ))
      end
    end
  elseif probe_full_foundlist and true_index ~= nil then
    append_probe_log(probe_logs, 'raw', 'known_true_addr already admitted by hybrid raw sampling via ' .. tostring(source_by_index[true_index]))
  end

  table.sort(indices)

  local addresses = {}
  for _, idx in ipairs(indices) do
    local addr = to_address_number(foundlist.Address[idx])
    if known_true_addr ~= nil and addr == known_true_addr then
      true_in_raw = true
      known_true_raw_admission_path = source_by_index[idx]
    end
    addresses[#addresses + 1] = addr
  end

  append_probe_log(probe_logs, 'raw_admission', string.format(
    'strategy=hybrid even=%d/%d structure=%d/%d neighborhood=%d/%d fill=%d/%d probe=%d/%d total=%d/%d',
    even_used,
    quota_plan.even_quota,
    structure_used,
    quota_plan.structure_quota,
    neighborhood_used,
    quota_plan.neighborhood_quota,
    fill_used,
    fill_quota,
    probe_used,
    probe_quota,
    #indices,
    wanted
  ))
  append_probe_log(probe_logs, 'raw_admission', string.format(
    'source_counts even=%d structure=%d neighborhood=%d fill=%d probe=%d scout=%d eligible=%d',
    source_counts.even_spread or 0,
    source_counts.structure_quota or 0,
    source_counts.neighborhood_quota or 0,
    source_counts.fill_from_remaining or 0,
    source_counts.probe_window or 0,
    structure_scout_count,
    structure_eligible_count
  ))
  append_probe_log(probe_logs, 'raw_admission', string.format(
    'read_fail_count=%d neighbor_dedup_drops=%d last_read_fail_candidate=%s',
    raw_debug_state.raw_read_fail_count or 0,
    raw_debug_state.raw_neighbor_dedup_drops or 0,
    tostring(raw_debug_state.last_read_fail_candidate_addr)
  ))
  append_probe_log(probe_logs, 'raw_admission', 'reject_counts ' .. format_count_map(raw_debug_state.raw_quota_reject_reason_counts))

  if known_true_addr ~= nil then
    if true_in_raw then
      append_probe_log(probe_logs, 'raw', 'known_true_addr admitted into raw set')
      append_probe_log(probe_logs, 'raw_admission', 'known_true_addr raw admission path = ' .. tostring(known_true_raw_admission_path))
    else
      if probe_full_foundlist then
        append_probe_log(probe_logs, 'raw', 'known_true_addr still missing from raw set after probe-window admission')
      else
        append_probe_log(probe_logs, 'raw', 'known_true_addr missing from raw set in no-probe raw admission pass')
      end
      append_probe_log(probe_logs, 'raw_admission', 'known_true_addr raw admission path = missing')
    end
  end

  return addresses, true_in_raw, true_in_full_foundlist, probe_logs, true_index, {
    strategy = 'hybrid_even_structure_neighborhood',
    even_quota = quota_plan.even_quota,
    structure_quota = quota_plan.structure_quota,
    neighborhood_quota = quota_plan.neighborhood_quota,
    fill_quota = fill_quota,
    probe_quota = probe_quota,
    even_used = even_used,
    structure_used = structure_used,
    neighborhood_used = neighborhood_used,
    fill_used = fill_used,
    probe_used = probe_used,
    source_counts = source_counts,
    structure_scout_count = structure_scout_count,
    structure_eligible_count = structure_eligible_count,
    known_true_path = known_true_raw_admission_path,
    probe_full_foundlist = probe_full_foundlist,
    raw_read_fail_count = raw_debug_state.raw_read_fail_count,
    raw_read_fail_field_counts = raw_debug_state.raw_read_fail_field_counts,
    raw_quota_reject_reason_counts = raw_debug_state.raw_quota_reject_reason_counts,
    raw_neighbor_dedup_drops = raw_debug_state.raw_neighbor_dedup_drops,
    true_in_full_foundlist_checked = true_in_full_foundlist_checked,
  }
end

local function collect_raw_foundlist_addresses(scan_budget, known_true_addr, probe_full_foundlist, probe_window_radius, target_value_pattern)
  local memscan = getCurrentMemscan()
  if memscan == nil then
    error('No active memscan was found. Run a Cheat Engine scan first.')
  end

  local foundlist = createFoundList(memscan)
  foundlist.initialize()

  local addresses = {}
  local total = foundlist.Count
  local wanted = total
  if scan_budget ~= nil then
    wanted = math.min(total, scan_budget)
  end

  local true_in_raw = false
  local true_in_full_foundlist = false
  local true_in_full_foundlist_checked = false
  local probe_logs = {}
  local true_index = nil
  local raw_admission_debug = {
    strategy = 'full_foundlist',
    even_quota = math.max(wanted, 0),
    structure_quota = 0,
    neighborhood_quota = 0,
    fill_quota = 0,
    probe_quota = probe_full_foundlist and 1 or 0,
    even_used = 0,
    structure_used = 0,
    neighborhood_used = 0,
    fill_used = 0,
    probe_used = 0,
    source_counts = {},
    known_true_path = nil,
    probe_full_foundlist = probe_full_foundlist,
    raw_read_fail_count = 0,
    raw_read_fail_field_counts = {},
    raw_quota_reject_reason_counts = {},
    raw_neighbor_dedup_drops = 0,
    true_in_full_foundlist_checked = false,
  }

  if total == 0 then
    foundlist.destroy()
    return addresses, 0, true_in_raw, true_in_full_foundlist, probe_logs, true_index, raw_admission_debug
  end

  if wanted <= 0 then
    foundlist.destroy()
    if known_true_addr ~= nil then
      append_probe_log(probe_logs, 'raw', 'scan_budget <= 0, raw admission skipped')
    end
    return addresses, total, true_in_raw, true_in_full_foundlist, probe_logs, true_index, raw_admission_debug
  end

  if wanted >= total then
    if known_true_addr ~= nil then
      true_in_full_foundlist_checked = true
      raw_admission_debug.true_in_full_foundlist_checked = true
    end
    for i = 0, total - 1 do
      local addr = to_address_number(foundlist.Address[i])
      if known_true_addr ~= nil and addr == known_true_addr then
        true_in_raw = true
        true_in_full_foundlist = true
      end
      table.insert(addresses, addr)
    end
    raw_admission_debug.even_used = #addresses
    raw_admission_debug.source_counts.full_foundlist = #addresses
    if true_in_raw then
      raw_admission_debug.known_true_path = 'full_foundlist'
    end
    if known_true_addr ~= nil then
      if true_in_full_foundlist then
        append_probe_log(probe_logs, 'full_foundlist', 'known_true_addr found in full foundlist')
      else
        append_probe_log(probe_logs, 'full_foundlist', 'known_true_addr not found in full foundlist')
      end
      if true_in_raw then
        append_probe_log(probe_logs, 'raw', 'known_true_addr admitted because raw covers full foundlist')
      else
        append_probe_log(probe_logs, 'raw', 'known_true_addr missing even though raw covers full foundlist')
      end
    end
    append_probe_log(probe_logs, 'raw_admission', string.format(
      'strategy=full_foundlist total=%d/%d probe_enabled=%s',
      #addresses,
      total,
      tostring(probe_full_foundlist)
    ))
    append_probe_log(probe_logs, 'raw_admission', string.format(
      'source_counts full_foundlist=%d',
      raw_admission_debug.source_counts.full_foundlist or 0
    ))
    append_probe_log(probe_logs, 'raw_admission', string.format(
      'read_fail_count=%d neighbor_dedup_drops=%d last_read_fail_candidate=%s',
      raw_admission_debug.raw_read_fail_count or 0,
      raw_admission_debug.raw_neighbor_dedup_drops or 0,
      tostring(raw_admission_debug.last_read_fail_candidate_addr)
    ))
    append_probe_log(probe_logs, 'raw_admission', 'reject_counts ' .. format_count_map(raw_admission_debug.raw_quota_reject_reason_counts))
    if known_true_addr ~= nil then
      append_probe_log(probe_logs, 'raw_admission', 'known_true_addr raw admission path = ' .. tostring(raw_admission_debug.known_true_path or 'missing'))
    end
  else
    addresses, true_in_raw, true_in_full_foundlist, probe_logs, true_index, raw_admission_debug =
      collect_windowed_raw_foundlist_addresses(foundlist, total, wanted, known_true_addr, probe_full_foundlist, probe_window_radius, target_value_pattern)
    true_in_full_foundlist_checked = raw_admission_debug and raw_admission_debug.true_in_full_foundlist_checked or false
  end

  foundlist.destroy()
  return addresses, total, true_in_raw, true_in_full_foundlist, probe_logs, true_index, raw_admission_debug
end

local function dedupe_addresses(addresses, known_true_addr)
  local seen = {}
  local unique = {}
  local true_in_unique = false

  for _, addr in ipairs(addresses) do
    if not seen[addr] then
      seen[addr] = true
      if known_true_addr ~= nil and addr == known_true_addr then
        true_in_unique = true
      end
      table.insert(unique, addr)
    end
  end

  return unique, true_in_unique
end

local function build_address_set(addresses)
  local set = {}
  for _, addr in ipairs(addresses or {}) do
    set[addr] = true
  end
  return set
end

local function filter_target_match_single_pass(addresses, target_value_pattern, known_true_addr)
  local matched = {}
  local true_in_filtered = false
  local mismatch_addresses = {}
  local stats = {
    matched_count = 0,
    value_mismatch_count = 0,
    read_failed_count = 0,
    retry_recovered_count = 0,
    retry_still_mismatch_count = 0,
    retry_read_failed_count = 0,
  }

  for _, addr in ipairs(addresses) do
    local ok, value = pcall(read_u32, addr)
    if not ok or type(value) ~= 'number' then
      stats.read_failed_count = stats.read_failed_count + 1
    elseif value == target_value_pattern then
      stats.matched_count = stats.matched_count + 1
      if known_true_addr ~= nil and addr == known_true_addr then
        true_in_filtered = true
      end
      table.insert(matched, addr)
    else
      local retry_ok, retry_value = pcall(read_u32, addr)
      if retry_ok and type(retry_value) == 'number' and retry_value == target_value_pattern then
        stats.retry_recovered_count = stats.retry_recovered_count + 1
        stats.matched_count = stats.matched_count + 1
        if known_true_addr ~= nil and addr == known_true_addr then
          true_in_filtered = true
        end
        table.insert(matched, addr)
      else
        stats.value_mismatch_count = stats.value_mismatch_count + 1
        if not retry_ok or type(retry_value) ~= 'number' then
          stats.retry_read_failed_count = stats.retry_read_failed_count + 1
        else
          stats.retry_still_mismatch_count = stats.retry_still_mismatch_count + 1
        end
        mismatch_addresses[#mismatch_addresses + 1] = addr
      end
    end
  end

  return matched, true_in_filtered, mismatch_addresses, stats
end

local function filter_target_match(addresses, target_value_pattern, known_true_addr, stable_filter_intersection_enabled, delayed_recheck_enabled)
  if delayed_recheck_enabled == nil then
    delayed_recheck_enabled = true
  end

  if stable_filter_intersection_enabled then
    local pass1_matched, _, _, pass1_stats =
      filter_target_match_single_pass(addresses, target_value_pattern, known_true_addr)
    local pass2_matched, _, _, pass2_stats =
      filter_target_match_single_pass(addresses, target_value_pattern, known_true_addr)
    local pass1_set = build_address_set(pass1_matched)
    local pass2_set = build_address_set(pass2_matched)
    local filtered = {}
    local pass1_only = {}
    local pass2_only = {}
    local true_in_filtered = false

    for _, addr in ipairs(pass1_matched) do
      if pass2_set[addr] then
        if known_true_addr ~= nil and addr == known_true_addr then
          true_in_filtered = true
        end
        table.insert(filtered, addr)
      else
        table.insert(pass1_only, addr)
      end
    end

    for _, addr in ipairs(pass2_matched) do
      if not pass1_set[addr] then
        table.insert(pass2_only, addr)
      end
    end

    local stats = {
      matched_count = pass1_stats.matched_count,
      value_mismatch_count = pass1_stats.value_mismatch_count,
      read_failed_count = pass1_stats.read_failed_count,
      retry_recovered_count = pass1_stats.retry_recovered_count,
      retry_still_mismatch_count = pass1_stats.retry_still_mismatch_count,
      retry_read_failed_count = pass1_stats.retry_read_failed_count,
      delayed_recheck_enabled = false,
      delayed_recheck_candidate_count = 0,
      delayed_recovered_count = 0,
      delayed_still_mismatch_count = 0,
      delayed_read_failed_count = 0,
      stable_intersection_enabled = true,
      pass1_matched_count = #pass1_matched,
      pass2_matched_count = #pass2_matched,
      intersection_filtered_count = #filtered,
      pass1_only_count = #pass1_only,
      pass2_only_count = #pass2_only,
      pass1_read_failed_count = pass1_stats.read_failed_count,
      pass2_read_failed_count = pass2_stats.read_failed_count,
      pass1_matched_addresses = pass1_matched,
      pass2_matched_addresses = pass2_matched,
      pass1_only_addresses = pass1_only,
      pass2_only_addresses = pass2_only,
    }

    return filtered, true_in_filtered, stats
  end

  local filtered, true_in_filtered, delayed_candidates, stats =
    filter_target_match_single_pass(addresses, target_value_pattern, known_true_addr)

  stats.delayed_recheck_enabled = delayed_recheck_enabled
  stats.delayed_recheck_candidate_count = delayed_recheck_enabled and #delayed_candidates or 0
  stats.delayed_recovered_count = 0
  stats.delayed_still_mismatch_count = 0
  stats.delayed_read_failed_count = 0
  stats.stable_intersection_enabled = false
  stats.pass1_matched_count = 0
  stats.pass2_matched_count = 0
  stats.intersection_filtered_count = 0
  stats.pass1_only_count = 0
  stats.pass2_only_count = 0
  stats.pass1_read_failed_count = 0
  stats.pass2_read_failed_count = 0
  stats.pass1_matched_addresses = {}
  stats.pass2_matched_addresses = {}
  stats.pass1_only_addresses = {}
  stats.pass2_only_addresses = {}

  if not delayed_recheck_enabled then
    return filtered, true_in_filtered, stats
  end

  for _, addr in ipairs(delayed_candidates) do
    local delayed_ok, delayed_value = pcall(read_u32, addr)
    if delayed_ok and type(delayed_value) == 'number' and delayed_value == target_value_pattern then
      stats.delayed_recovered_count = stats.delayed_recovered_count + 1
      if known_true_addr ~= nil and addr == known_true_addr then
        true_in_filtered = true
      end
      table.insert(filtered, addr)
    elseif not delayed_ok or type(delayed_value) ~= 'number' then
      stats.delayed_read_failed_count = stats.delayed_read_failed_count + 1
    else
      stats.delayed_still_mismatch_count = stats.delayed_still_mismatch_count + 1
    end
  end

  return filtered, true_in_filtered, stats
end

local function sort_numeric(addresses)
  table.sort(addresses, function(a, b)
    return a < b
  end)
  return addresses
end

local function copy_numeric_array(addresses)
  local copied = {}
  for i, addr in ipairs(addresses or {}) do
    copied[i] = addr
  end
  return copied
end

local function select_evenly(addresses, wanted_count, known_true_addr)
  if wanted_count == nil or wanted_count <= 0 or #addresses <= wanted_count then
    local true_in_selected = false
    if known_true_addr ~= nil then
      for _, addr in ipairs(addresses) do
        if addr == known_true_addr then
          true_in_selected = true
          break
        end
      end
    end
    return addresses, true_in_selected
  end

  if wanted_count == 1 then
    local chosen = { addresses[1] }
    return chosen, (known_true_addr ~= nil and addresses[1] == known_true_addr)
  end

  local selected = {}
  local last_index = 0
  local true_in_selected = false

  for slot = 1, wanted_count do
    local ratio = (slot - 1) / (wanted_count - 1)
    local index = math.floor(ratio * (#addresses - 1)) + 1

    if index <= last_index then
      index = last_index + 1
    end
    if index > #addresses then
      index = #addresses
    end

    local addr = addresses[index]
    if known_true_addr ~= nil and addr == known_true_addr then
      true_in_selected = true
    end
    table.insert(selected, addr)
    last_index = index
  end

  return selected, true_in_selected
end

local function build_scored_pool(addresses, target_value_pattern, known_true_addr)
  local scored = {}
  local true_in_prescored = false

  for _, value_addr in ipairs(addresses) do
    local ok, candidate = pcall(MVP0.build_candidate, value_addr)
    if ok and candidate ~= nil then
      local score_result = MVP0.score_candidate(candidate, target_value_pattern)
      if known_true_addr ~= nil and value_addr == known_true_addr then
        true_in_prescored = true
      end
      table.insert(scored, {
        addr = value_addr,
        prescore_score = score_result.prescore_score,
        hard_pass = score_result.hard_pass,
        flags = score_result.flags,
        score_result = score_result,
      })
    end
  end

  table.sort(scored, function(a, b)
    if a.prescore_score ~= b.prescore_score then
      return a.prescore_score > b.prescore_score
    end
    return a.addr < b.addr
  end)

  return scored, true_in_prescored
end

local function select_top_scored_diverse(addresses, wanted_count, target_value_pattern, bucket_shift, max_per_bucket, known_true_addr)
  if wanted_count == nil or wanted_count <= 0 or #addresses <= wanted_count then
    local true_in_selected = false
    if known_true_addr ~= nil then
      for _, addr in ipairs(addresses) do
        if addr == known_true_addr then
          true_in_selected = true
          break
        end
      end
    end
    return addresses, #addresses, nil, nil, true, true_in_selected
  end

  local scored, true_in_prescored = build_scored_pool(addresses, target_value_pattern, known_true_addr)

  local selected = {}
  local bucket_counts = {}
  local deferred = {}
  local cutoff_score = nil
  local tied_count = nil
  local true_in_selected = false

  for _, item in ipairs(scored) do
    local bucket = region_bucket(item.addr, bucket_shift)
    local count = bucket_counts[bucket] or 0
    if count < max_per_bucket and #selected < wanted_count then
      bucket_counts[bucket] = count + 1
      table.insert(selected, item.addr)
      if known_true_addr ~= nil and item.addr == known_true_addr then
        true_in_selected = true
      end
    else
      table.insert(deferred, item)
    end
  end

  if #selected < wanted_count then
    for _, item in ipairs(deferred) do
      if #selected >= wanted_count then
        break
      end
      table.insert(selected, item.addr)
      if known_true_addr ~= nil and item.addr == known_true_addr then
        true_in_selected = true
      end
    end
  end

  if #selected > 0 then
    local cutoff_addr = selected[#selected]
    for _, item in ipairs(scored) do
      if item.addr == cutoff_addr then
        cutoff_score = item.prescore_score
        break
      end
    end

    if cutoff_score ~= nil then
      tied_count = 0
      for _, item in ipairs(scored) do
        if item.prescore_score == cutoff_score then
          tied_count = tied_count + 1
        end
      end
    end
  end

  return selected, #scored, cutoff_score, tied_count, true_in_prescored, true_in_selected
end

function MVP0FoundList.collect(opts)
  assert_mvp0_loaded()

  opts = opts or {}
  local max_candidates = opts.max_candidates or MVP0FoundList.CONFIG.default_max_candidates
  local scan_budget = opts.scan_budget
  local target_value_pattern = u32(opts.target_value_pattern)
  local should_filter = opts.filter_target_match
  local use_prescore_selection = opts.use_prescore_selection
  local bucket_shift = opts.bucket_shift or MVP0FoundList.CONFIG.default_bucket_shift
  local max_per_bucket = opts.max_per_bucket or MVP0FoundList.CONFIG.default_max_per_bucket
  local known_true_addr = opts.known_true_addr and to_address_number(opts.known_true_addr) or nil
  local probe_full_foundlist = opts.probe_full_foundlist
  local probe_window_radius = opts.probe_window_radius
  local stable_filter_intersection_enabled = opts.stable_filter_intersection_enabled == true
  local delayed_recheck_enabled = opts.delayed_recheck_enabled

  if scan_budget == nil then
    scan_budget = MVP0FoundList.CONFIG.default_scan_budget
  end
  if should_filter == nil then
    should_filter = MVP0FoundList.CONFIG.default_filter_target_match
  end
  if use_prescore_selection == nil then
    use_prescore_selection = MVP0FoundList.CONFIG.default_use_prescore_selection
  end
  if probe_full_foundlist == nil then
    probe_full_foundlist = MVP0FoundList.CONFIG.default_probe_full_foundlist
  end
  if probe_window_radius == nil then
    probe_window_radius = MVP0FoundList.CONFIG.default_probe_window_radius
  end
  if delayed_recheck_enabled == nil then
    delayed_recheck_enabled = true
  end

  if target_value_pattern == nil then
    error('target_value_pattern is required.')
  end

  local raw_addresses, raw_count, true_in_raw, true_in_full_foundlist, truth_probe_logs, true_foundlist_index, raw_admission_debug =
    collect_raw_foundlist_addresses(scan_budget, known_true_addr, probe_full_foundlist, probe_window_radius, target_value_pattern)
  local unique_addresses, true_in_unique = dedupe_addresses(raw_addresses, known_true_addr)
  local filtered_addresses = unique_addresses
  local true_in_filtered = true_in_unique
  local filter_debug = nil

  if should_filter then
    filtered_addresses, true_in_filtered, filter_debug =
      filter_target_match(unique_addresses, target_value_pattern, known_true_addr, stable_filter_intersection_enabled, delayed_recheck_enabled)
    append_probe_log(truth_probe_logs, 'filter', string.format(
      'filter_target_match enabled unique=%d matched=%d value_mismatch=%d read_failed=%d retry_recovered=%d retry_still_mismatch=%d retry_read_failed=%d delayed_recheck_enabled=%s delayed_candidates=%d delayed_recovered=%d delayed_still_mismatch=%d delayed_read_failed=%d stable_intersection_enabled=%s pass1_matched=%d pass2_matched=%d intersection_filtered=%d pass1_only=%d pass2_only=%d final_filtered=%d probe_enabled=%s',
      #unique_addresses,
      filter_debug and filter_debug.matched_count or #filtered_addresses,
      filter_debug and filter_debug.value_mismatch_count or 0,
      filter_debug and filter_debug.read_failed_count or 0,
      filter_debug and filter_debug.retry_recovered_count or 0,
      filter_debug and filter_debug.retry_still_mismatch_count or 0,
      filter_debug and filter_debug.retry_read_failed_count or 0,
      tostring(filter_debug and filter_debug.delayed_recheck_enabled or false),
      filter_debug and filter_debug.delayed_recheck_candidate_count or 0,
      filter_debug and filter_debug.delayed_recovered_count or 0,
      filter_debug and filter_debug.delayed_still_mismatch_count or 0,
      filter_debug and filter_debug.delayed_read_failed_count or 0,
      tostring(filter_debug and filter_debug.stable_intersection_enabled or false),
      filter_debug and filter_debug.pass1_matched_count or 0,
      filter_debug and filter_debug.pass2_matched_count or 0,
      filter_debug and filter_debug.intersection_filtered_count or 0,
      filter_debug and filter_debug.pass1_only_count or 0,
      filter_debug and filter_debug.pass2_only_count or 0,
      #filtered_addresses,
      tostring(probe_full_foundlist)
    ))
  else
    append_probe_log(truth_probe_logs, 'filter', string.format(
      'filter_target_match disabled unique=%d probe_enabled=%s',
      #unique_addresses,
      tostring(probe_full_foundlist)
    ))
  end

  local sorted_addresses = sort_numeric(filtered_addresses)
  MVP0FoundList.LAST_FILTER_DEBUG = {
    unique_count = #unique_addresses,
    matched_count = filter_debug and filter_debug.matched_count or #sorted_addresses,
    value_mismatch_count = filter_debug and filter_debug.value_mismatch_count or 0,
    read_failed_count = filter_debug and filter_debug.read_failed_count or 0,
    retry_recovered_count = filter_debug and filter_debug.retry_recovered_count or 0,
    retry_still_mismatch_count = filter_debug and filter_debug.retry_still_mismatch_count or 0,
    retry_read_failed_count = filter_debug and filter_debug.retry_read_failed_count or 0,
    delayed_recheck_enabled = filter_debug and filter_debug.delayed_recheck_enabled or false,
    delayed_recheck_candidate_count = filter_debug and filter_debug.delayed_recheck_candidate_count or 0,
    delayed_recovered_count = filter_debug and filter_debug.delayed_recovered_count or 0,
    delayed_still_mismatch_count = filter_debug and filter_debug.delayed_still_mismatch_count or 0,
    delayed_read_failed_count = filter_debug and filter_debug.delayed_read_failed_count or 0,
    stable_intersection_enabled = filter_debug and filter_debug.stable_intersection_enabled or false,
    pass1_matched_count = filter_debug and filter_debug.pass1_matched_count or 0,
    pass2_matched_count = filter_debug and filter_debug.pass2_matched_count or 0,
    intersection_filtered_count = filter_debug and filter_debug.intersection_filtered_count or 0,
    pass1_only_count = filter_debug and filter_debug.pass1_only_count or 0,
    pass2_only_count = filter_debug and filter_debug.pass2_only_count or 0,
    pass1_read_failed_count = filter_debug and filter_debug.pass1_read_failed_count or 0,
    pass2_read_failed_count = filter_debug and filter_debug.pass2_read_failed_count or 0,
    pass1_matched_addresses = sort_numeric(copy_numeric_array(filter_debug and filter_debug.pass1_matched_addresses or {})),
    pass2_matched_addresses = sort_numeric(copy_numeric_array(filter_debug and filter_debug.pass2_matched_addresses or {})),
    pass1_only_addresses = sort_numeric(copy_numeric_array(filter_debug and filter_debug.pass1_only_addresses or {})),
    pass2_only_addresses = sort_numeric(copy_numeric_array(filter_debug and filter_debug.pass2_only_addresses or {})),
    matched_addresses = copy_numeric_array(sorted_addresses),
  }

  local selected_addresses
  local prescored_count = nil
  local selection_strategy = nil
  local prescore_cutoff_score = nil
  local prescore_tied_count = nil
  local true_in_prescored = false
  local true_in_selected = false

  if use_prescore_selection and #sorted_addresses > 0 then
    selected_addresses, prescored_count, prescore_cutoff_score, prescore_tied_count, true_in_prescored, true_in_selected =
      select_top_scored_diverse(sorted_addresses, max_candidates, target_value_pattern, bucket_shift, max_per_bucket, known_true_addr)
    selection_strategy = 'prescore_diverse_top_scored'
  else
    selected_addresses, true_in_selected = select_evenly(sorted_addresses, max_candidates, known_true_addr)
    selection_strategy = 'evenly_spread'
    true_in_prescored = false
  end

  local true_in_full_foundlist_checked = raw_admission_debug and raw_admission_debug.true_in_full_foundlist_checked or false
  local true_in_full_foundlist_value = nil
  if true_in_full_foundlist_checked then
    true_in_full_foundlist_value = true_in_full_foundlist
  end

  local true_in_full_foundlist_observed = true_in_full_foundlist_value
  if known_true_addr ~= nil and not true_in_full_foundlist_checked then
    true_in_full_foundlist_observed = 'skipped'
  end

  return {
    source_mode = 'foundlist',
    raw_count = raw_count,
    scanned_count = #raw_addresses,
    unique_count = #unique_addresses,
    filtered_count = #filtered_addresses,
    selected_count = #selected_addresses,
    candidate_value_addrs = selected_addresses,
    filter_target_match = should_filter,
    target_value_pattern = target_value_pattern,
    scan_budget = scan_budget,
    max_candidates = max_candidates,
    use_prescore_selection = use_prescore_selection,
    prescored_count = prescored_count,
    selection_strategy = selection_strategy,
    prescore_cutoff_score = prescore_cutoff_score,
    prescore_tied_count = prescore_tied_count,
    bucket_shift = bucket_shift,
    max_per_bucket = max_per_bucket,
    known_true_addr = known_true_addr,
    true_foundlist_index = true_foundlist_index,
    probe_window_radius = probe_window_radius,
    truth_probe_logs = truth_probe_logs,
    raw_admission_strategy = raw_admission_debug and raw_admission_debug.strategy or nil,
    raw_even_spread_quota = raw_admission_debug and raw_admission_debug.even_quota or nil,
    raw_structure_quota = raw_admission_debug and raw_admission_debug.structure_quota or nil,
    raw_neighborhood_quota = raw_admission_debug and raw_admission_debug.neighborhood_quota or nil,
    raw_fill_quota = raw_admission_debug and raw_admission_debug.fill_quota or nil,
    raw_probe_quota = raw_admission_debug and raw_admission_debug.probe_quota or nil,
    raw_even_spread_used = raw_admission_debug and raw_admission_debug.even_used or nil,
    raw_structure_used = raw_admission_debug and raw_admission_debug.structure_used or nil,
    raw_neighborhood_used = raw_admission_debug and raw_admission_debug.neighborhood_used or nil,
    raw_fill_used = raw_admission_debug and raw_admission_debug.fill_used or nil,
    raw_probe_used = raw_admission_debug and raw_admission_debug.probe_used or nil,
    raw_admission_source_counts = raw_admission_debug and raw_admission_debug.source_counts or nil,
    raw_structure_scout_count = raw_admission_debug and raw_admission_debug.structure_scout_count or nil,
    raw_structure_eligible_count = raw_admission_debug and raw_admission_debug.structure_eligible_count or nil,
    known_true_raw_admission_path = raw_admission_debug and raw_admission_debug.known_true_path or nil,
    raw_probe_full_foundlist_enabled = raw_admission_debug and raw_admission_debug.probe_full_foundlist,
    raw_read_fail_count = raw_admission_debug and raw_admission_debug.raw_read_fail_count or nil,
    raw_read_fail_field_counts = raw_admission_debug and raw_admission_debug.raw_read_fail_field_counts or nil,
    raw_quota_reject_reason_counts = raw_admission_debug and raw_admission_debug.raw_quota_reject_reason_counts or nil,
    raw_neighbor_dedup_drops = raw_admission_debug and raw_admission_debug.raw_neighbor_dedup_drops or nil,
    true_in_full_foundlist_checked = true_in_full_foundlist_checked,
    true_in_full_foundlist = true_in_full_foundlist_value,
    true_in_full_foundlist_observed = true_in_full_foundlist_observed,
    true_in_raw = true_in_raw,
    true_in_unique = true_in_unique,
    true_in_filtered = true_in_filtered,
    true_in_prescored = true_in_prescored,
    true_in_selected = true_in_selected,
  }
end

local function collect_from_filtered_addresses(opts)
  assert_mvp0_loaded()

  opts = opts or {}
  local max_candidates = opts.max_candidates or MVP0FoundList.CONFIG.default_max_candidates
  local target_value_pattern = u32(opts.target_value_pattern)
  local use_prescore_selection = opts.use_prescore_selection
  local bucket_shift = opts.bucket_shift or MVP0FoundList.CONFIG.default_bucket_shift
  local max_per_bucket = opts.max_per_bucket or MVP0FoundList.CONFIG.default_max_per_bucket
  local known_true_addr = opts.known_true_addr and to_address_number(opts.known_true_addr) or nil
  local filtered_addresses = copy_numeric_array(opts.filtered_addresses or {})
  local true_in_filtered = false

  if opts.preserve_filtered_order ~= true then
    filtered_addresses = sort_numeric(filtered_addresses)
  end

  if use_prescore_selection == nil then
    use_prescore_selection = MVP0FoundList.CONFIG.default_use_prescore_selection
  end
  if target_value_pattern == nil then
    error('target_value_pattern is required.')
  end

  for _, addr in ipairs(filtered_addresses) do
    if known_true_addr ~= nil and addr == known_true_addr then
      true_in_filtered = true
      break
    end
  end

  local selected_addresses
  local prescored_count = nil
  local selection_strategy = nil
  local prescore_cutoff_score = nil
  local prescore_tied_count = nil
  local true_in_prescored = false
  local true_in_selected = false

  if use_prescore_selection and #filtered_addresses > 0 then
    selected_addresses, prescored_count, prescore_cutoff_score, prescore_tied_count, true_in_prescored, true_in_selected =
      select_top_scored_diverse(filtered_addresses, max_candidates, target_value_pattern, bucket_shift, max_per_bucket, known_true_addr)
    selection_strategy = 'prescore_diverse_top_scored'
  else
    selected_addresses, true_in_selected = select_evenly(filtered_addresses, max_candidates, known_true_addr)
    selection_strategy = 'evenly_spread'
    true_in_prescored = false
  end

  return {
    source_mode = opts.source_mode or 'filtered_override',
    raw_count = nil,
    scanned_count = nil,
    unique_count = nil,
    filtered_count = #filtered_addresses,
    selected_count = #selected_addresses,
    candidate_value_addrs = selected_addresses,
    filter_target_match = true,
    target_value_pattern = target_value_pattern,
    scan_budget = nil,
    max_candidates = max_candidates,
    use_prescore_selection = use_prescore_selection,
    prescored_count = prescored_count,
    selection_strategy = selection_strategy,
    prescore_cutoff_score = prescore_cutoff_score,
    prescore_tied_count = prescore_tied_count,
    bucket_shift = bucket_shift,
    max_per_bucket = max_per_bucket,
    known_true_addr = known_true_addr,
    true_foundlist_index = nil,
    probe_window_radius = nil,
    truth_probe_logs = opts.truth_probe_logs or {},
    known_true_raw_admission_path = opts.known_true_raw_admission_path,
    raw_probe_full_foundlist_enabled = opts.raw_probe_full_foundlist_enabled,
    true_in_full_foundlist_checked = nil,
    true_in_full_foundlist = nil,
    true_in_full_foundlist_observed = nil,
    true_in_raw = nil,
    true_in_unique = nil,
    true_in_filtered = true_in_filtered,
    true_in_prescored = true_in_prescored,
    true_in_selected = true_in_selected,
    session_mode = opts.session_mode,
  }
end

local function copy_string_array(items)
  local copied = {}
  for i, item in ipairs(items or {}) do
    copied[i] = item
  end
  return copied
end

local function copy_option_table(opts)
  local copied = {}
  for key, value in pairs(opts or {}) do
    copied[key] = value
  end
  return copied
end

local function run_stable_no_probe_intersection(opts)
  local snapshot_a_opts = copy_option_table(opts)
  snapshot_a_opts.stable_no_probe_intersection_enabled = false
  snapshot_a_opts.stable_filter_intersection_enabled = false
  snapshot_a_opts.delayed_recheck_enabled = false
  snapshot_a_opts.probe_full_foundlist = false
  snapshot_a_opts.session_mode = 'no_probe'

  local snapshot_a = MVP0FoundList.collect(snapshot_a_opts)
  local snapshot_a_filtered = copy_numeric_array(MVP0FoundList.LAST_FILTER_DEBUG and MVP0FoundList.LAST_FILTER_DEBUG.matched_addresses or {})

  local snapshot_b_opts = copy_option_table(opts)
  snapshot_b_opts.stable_no_probe_intersection_enabled = false
  snapshot_b_opts.stable_filter_intersection_enabled = false
  snapshot_b_opts.delayed_recheck_enabled = false
  snapshot_b_opts.probe_full_foundlist = false
  snapshot_b_opts.session_mode = 'no_probe'

  local snapshot_b = MVP0FoundList.collect(snapshot_b_opts)
  local snapshot_b_filtered = copy_numeric_array(MVP0FoundList.LAST_FILTER_DEBUG and MVP0FoundList.LAST_FILTER_DEBUG.matched_addresses or {})
  local stable_filtered = {}
  local snapshot_a_set = build_address_set(snapshot_a_filtered)

  for _, addr in ipairs(snapshot_b_filtered) do
    if snapshot_a_set[addr] then
      stable_filtered[#stable_filtered + 1] = addr
    end
  end

  local truth_probe_logs = copy_string_array(snapshot_b.truth_probe_logs)
  append_probe_log(truth_probe_logs, 'filter', string.format(
    'stable_no_probe_intersection enabled snapshot_A_filtered=%d snapshot_B_filtered=%d final_filtered=%d canonical_source=no_probe_B',
    #snapshot_a_filtered,
    #snapshot_b_filtered,
    #stable_filtered
  ))

  local bundle = collect_from_filtered_addresses({
    filtered_addresses = stable_filtered,
    preserve_filtered_order = true,
    max_candidates = opts.max_candidates,
    target_value_pattern = opts.target_value_pattern,
    target_value_float = opts.target_value_float,
    use_prescore_selection = opts.use_prescore_selection,
    bucket_shift = opts.bucket_shift,
    max_per_bucket = opts.max_per_bucket,
    known_true_addr = opts.known_true_addr,
    known_true_raw_admission_path = snapshot_b.known_true_raw_admission_path,
    raw_probe_full_foundlist_enabled = false,
    truth_probe_logs = truth_probe_logs,
    session_mode = opts.session_mode or 'stable_no_probe_intersection',
    source_mode = 'stable_no_probe_intersection',
  })

  bundle.raw_count = snapshot_b.raw_count
  bundle.scanned_count = snapshot_b.scanned_count
  bundle.unique_count = snapshot_b.unique_count
  bundle.scan_budget = snapshot_b.scan_budget
  bundle.probe_window_radius = snapshot_b.probe_window_radius
  bundle.true_foundlist_index = snapshot_b.true_foundlist_index
  bundle.raw_admission_strategy = snapshot_b.raw_admission_strategy
  bundle.raw_even_spread_quota = snapshot_b.raw_even_spread_quota
  bundle.raw_structure_quota = snapshot_b.raw_structure_quota
  bundle.raw_neighborhood_quota = snapshot_b.raw_neighborhood_quota
  bundle.raw_fill_quota = snapshot_b.raw_fill_quota
  bundle.raw_probe_quota = snapshot_b.raw_probe_quota
  bundle.raw_even_spread_used = snapshot_b.raw_even_spread_used
  bundle.raw_structure_used = snapshot_b.raw_structure_used
  bundle.raw_neighborhood_used = snapshot_b.raw_neighborhood_used
  bundle.raw_fill_used = snapshot_b.raw_fill_used
  bundle.raw_probe_used = snapshot_b.raw_probe_used
  bundle.raw_admission_source_counts = snapshot_b.raw_admission_source_counts
  bundle.raw_structure_scout_count = snapshot_b.raw_structure_scout_count
  bundle.raw_structure_eligible_count = snapshot_b.raw_structure_eligible_count
  bundle.raw_read_fail_count = snapshot_b.raw_read_fail_count
  bundle.raw_read_fail_field_counts = snapshot_b.raw_read_fail_field_counts
  bundle.raw_quota_reject_reason_counts = snapshot_b.raw_quota_reject_reason_counts
  bundle.raw_neighbor_dedup_drops = snapshot_b.raw_neighbor_dedup_drops
  bundle.true_in_full_foundlist_checked = snapshot_b.true_in_full_foundlist_checked
  bundle.true_in_full_foundlist = snapshot_b.true_in_full_foundlist
  bundle.true_in_full_foundlist_observed = snapshot_b.true_in_full_foundlist_observed
  bundle.true_in_raw = snapshot_b.true_in_raw
  bundle.true_in_unique = snapshot_b.true_in_unique
  bundle.stable_no_probe_intersection_enabled = true
  bundle.stable_intersection_snapshot_A_filtered_count = #snapshot_a_filtered
  bundle.stable_intersection_snapshot_B_filtered_count = #snapshot_b_filtered
  bundle.stable_intersection_filtered_count = #stable_filtered
  bundle.stable_intersection_canonical_source_count = #snapshot_b_filtered
  bundle.stable_intersection_downstream_input_count = #stable_filtered
  bundle.stable_intersection_true_in_filtered = bundle.true_in_filtered
  bundle.session_mode = opts.session_mode or 'stable_no_probe_intersection'

  MVP0FoundList.LAST_FILTER_DEBUG = {
    unique_count = snapshot_b.unique_count,
    matched_count = #stable_filtered,
    value_mismatch_count = 0,
    read_failed_count = 0,
    retry_recovered_count = 0,
    retry_still_mismatch_count = 0,
    retry_read_failed_count = 0,
    delayed_recheck_enabled = false,
    delayed_recheck_candidate_count = 0,
    delayed_recovered_count = 0,
    delayed_still_mismatch_count = 0,
    delayed_read_failed_count = 0,
    stable_intersection_enabled = false,
    pass1_matched_count = 0,
    pass2_matched_count = 0,
    intersection_filtered_count = 0,
    pass1_only_count = 0,
    pass2_only_count = 0,
    pass1_read_failed_count = 0,
    pass2_read_failed_count = 0,
    pass1_matched_addresses = {},
    pass2_matched_addresses = {},
    pass1_only_addresses = {},
    pass2_only_addresses = {},
    matched_addresses = copy_numeric_array(stable_filtered),
    stable_no_probe_intersection_enabled = true,
    stable_intersection_snapshot_A_filtered_count = #snapshot_a_filtered,
    stable_intersection_snapshot_B_filtered_count = #snapshot_b_filtered,
    stable_intersection_filtered_count = #stable_filtered,
    stable_intersection_canonical_source_count = #snapshot_b_filtered,
    stable_intersection_downstream_input_count = #stable_filtered,
  }

  return bundle
end

function MVP0FoundList.build_input(opts)
  local collected = MVP0FoundList.collect(opts)
  collected.input = MVP0.make_input(collected.candidate_value_addrs, collected.target_value_pattern, {
    target_value_float = opts and opts.target_value_float,
    session_id = opts and opts.session_id,
    session_mode = collected.session_mode or ((collected.raw_probe_full_foundlist_enabled == true) and 'with_probe' or 'no_probe'),
  })
  return collected
end

function MVP0FoundList.run_from_filtered_addresses(opts)
  local bundle = collect_from_filtered_addresses(opts)
  bundle.input = MVP0.make_input(bundle.candidate_value_addrs, bundle.target_value_pattern, {
    target_value_float = opts and opts.target_value_float,
    session_id = opts and opts.session_id,
    session_mode = bundle.session_mode or (opts and opts.session_mode) or 'stable_no_probe_intersection',
  })
  bundle.result = MVP0.run(bundle.input)

  bundle.known_true_rank_position = nil
  bundle.known_true_base_score = nil
  bundle.known_true_final_score = nil
  bundle.known_true_tie_break_vector = nil

  if bundle.known_true_addr ~= nil and bundle.result ~= nil and bundle.result.ranked ~= nil then
    for _, scored_candidate in ipairs(bundle.result.ranked) do
      local candidate = scored_candidate.candidate
      if candidate ~= nil and candidate.value_addr == bundle.known_true_addr then
        bundle.known_true_rank_position = scored_candidate.rank_position
        bundle.known_true_base_score = scored_candidate.base_score
        bundle.known_true_final_score = scored_candidate.final_score
        bundle.known_true_tie_break_vector = scored_candidate.tie_break_vector
        break
      end
    end
  end

  return bundle
end

function MVP0FoundList.run(opts)
  if opts and opts.stable_no_probe_intersection_enabled == true then
    local bundle = run_stable_no_probe_intersection(opts)
    bundle.input = MVP0.make_input(bundle.candidate_value_addrs, bundle.target_value_pattern, {
      target_value_float = opts and opts.target_value_float,
      session_id = opts and opts.session_id,
      session_mode = bundle.session_mode or 'stable_no_probe_intersection',
    })
    bundle.result = MVP0.run(bundle.input)

    bundle.known_true_rank_position = nil
    bundle.known_true_base_score = nil
    bundle.known_true_final_score = nil
    bundle.known_true_tie_break_vector = nil

    if bundle.known_true_addr ~= nil and bundle.result ~= nil and bundle.result.ranked ~= nil then
      for _, scored_candidate in ipairs(bundle.result.ranked) do
        local candidate = scored_candidate.candidate
        if candidate ~= nil and candidate.value_addr == bundle.known_true_addr then
          bundle.known_true_rank_position = scored_candidate.rank_position
          bundle.known_true_base_score = scored_candidate.base_score
          bundle.known_true_final_score = scored_candidate.final_score
          bundle.known_true_tie_break_vector = scored_candidate.tie_break_vector
          break
        end
      end
    end

    return bundle
  end

  local bundle = MVP0FoundList.build_input(opts)
  bundle.result = MVP0.run(bundle.input)

  bundle.known_true_rank_position = nil
  bundle.known_true_base_score = nil
  bundle.known_true_final_score = nil
  bundle.known_true_tie_break_vector = nil

  if bundle.known_true_addr ~= nil and bundle.result ~= nil and bundle.result.ranked ~= nil then
    for _, scored_candidate in ipairs(bundle.result.ranked) do
      local candidate = scored_candidate.candidate
      if candidate ~= nil and candidate.value_addr == bundle.known_true_addr then
        bundle.known_true_rank_position = scored_candidate.rank_position
        bundle.known_true_base_score = scored_candidate.base_score
        bundle.known_true_final_score = scored_candidate.final_score
        bundle.known_true_tie_break_vector = scored_candidate.tie_break_vector
        break
      end
    end
  end

  return bundle
end

_G.MVP0FoundList = MVP0FoundList
return MVP0FoundList
