-- Route B / MVP-0 candidate scoring report for Cheat Engine Lua
--
-- Usage example inside Cheat Engine Lua Engine:
--
-- dofile('mvp0_candidate_report.lua')
--
-- local input = MVP0.make_input({
--   0x28A061C8958,
--   0x28A06E2F394,
--   0x28A0730B620,
--   0x28A077B6710,
--   0x28A077B692C,
-- }, 0x42C80000, { target_value_float = 100.0, session_id = 'session-3' })
--
-- local result = MVP0.run(input)
-- print(result.report_text)

local MVP0 = {}

local FRONT_KEYS = {"f08", "f18", "f20"}
local TAIL_KEYS = {"f68", "f70", "f78"}
local STRUCT_KEYS = {"f08", "f18", "f20", "f58", "f68", "f70", "f78"}
local FAMILY_PAIR_KEYS = {
  {"f08", "f18"},
  {"f08", "f20"},
  {"f08", "f58"},
  {"f08", "f68"},
  {"f08", "f70"},
  {"f08", "f78"},
  {"f18", "f20"},
  {"f18", "f58"},
  {"f18", "f68"},
  {"f18", "f70"},
  {"f18", "f78"},
  {"f20", "f58"},
  {"f20", "f68"},
  {"f20", "f70"},
  {"f20", "f78"},
  {"f58", "f68"},
  {"f58", "f70"},
  {"f58", "f78"},
  {"f68", "f70"},
  {"f68", "f78"},
  {"f70", "f78"},
}
local MIRROR_PAIRS = {
  {"f08", "f68"},
  {"f18", "f70"},
  {"f20", "f78"},
}
local ALT_MIRROR_PAIRS = {
  {"f08", "f78"},
  {"f18", "f70"},
  {"f20", "f68"},
}

MVP0.CONFIG = {
  value_offset = 0x28,
  offsets = {
    f08 = 0x08,
    f18 = 0x18,
    f20 = 0x20,
    f28 = 0x28,
    f58 = 0x58,
    f68 = 0x68,
    f70 = 0x70,
    f78 = 0x78,
  },
  suspicious = {
    [0x00000000] = true,
    [0x3F800000] = true,
    [0xBF800000] = true,
    [0x42C80000] = true,
    [0x43300000] = true,
    [0x43320000] = true,
    [0x43800000] = true,
  },
  ranking = {
    local_weights = {
      target_match = 10,
      nonzero_field = 2,
      not_floatlike_field = 2,
      status_nonzero = 3,
      status_small_int = 1,
      status_not_floatlike = 2,
      penalty_empty_front = 8,
      penalty_empty_tail = 8,
      penalty_floatlike_3plus = 10,
      penalty_floatlike_5plus = 15,
      penalty_value_copy = 6,
      legacy_pointer_balanced_bonus = 4,
      legacy_pointer_diverse_bonus = 2,
      legacy_pointer_unbalanced_penalty = 3,
      legacy_template_penalty = 4,
      legacy_template_heavy_penalty = 7,
      legacy_mirrored_penalty = 4,
      legacy_mirrored_heavy_penalty = 7,
      legacy_code_blob_penalty = 5,
      legacy_code_blob_heavy_penalty = 8,
      legacy_small_int_dependency_penalty = 3,
    },
    thresholds = {
      address_floor = 0x10000,
      alignment_mask = 0x3,
      near_distance = 0x400,
      same_page_shift = 12,
      same_region_shift = 16,
      legacy_pointer_bucket_shift = 12,
      min_coherent_front_pointers = 2,
      min_coherent_tail_pointers = 2,
      pointer_reward_min_regions = 2,
      pointer_reward_max_regions = 4,
      distinct_anchor_distance = 0x2000,
      mild_blob_score = 8,
      heavy_blob_score = 14,
      packed_run_threshold = 3,
      monotonic_run_threshold = 3,
      max_dense_page_count = 2,
      tail_cluster_min_pairs = 3,
      mild_family_size = 3,
      medium_family_size = 5,
      heavy_family_size = 9,
      mirrored_family_repeat_min = 3,
    },
    adjustments = {
      pointer_reward_cap = 4,
      code_blob_penalty_mild = 2,
      code_blob_penalty_heavy = 8,
      clone_penalty_mild = 2,
      clone_penalty_medium = 5,
      clone_penalty_heavy = 8,
      mirrored_penalty = 3,
    },
  },
  confidence = {
    high_gap = 10,
    medium_gap = 5,
  },
  recommendation = {
    accept_min_score = 30,
    review_min_score = 20,
  },
}

local function u32(n)
  if n == nil then
    return nil
  end
  if n < 0 then
    return n + 0x100000000
  end
  return n
end

local function hex_u32(n)
  if n == nil then
    return "nil"
  end
  return string.format("0x%08X", u32(n))
end

local function hex_u64(n)
  if n == nil then
    return "nil"
  end
  return string.format("0x%X", n)
end

local function read_u32(addr)
  return u32(readInteger(addr))
end

local function read_f32(addr)
  return readFloat(addr)
end

local function is_suspicious_float_like(x)
  return MVP0.CONFIG.suspicious[u32(x)] == true
end

local function is_small_int_like(x)
  x = u32(x)
  return x ~= 0 and x < 0x1000
end

local function is_legacy_pointer_like(x)
  x = u32(x)
  return x ~= 0
    and not is_suspicious_float_like(x)
    and not is_small_int_like(x)
    and x >= MVP0.CONFIG.ranking.thresholds.address_floor
end

local function abs_delta(a, b)
  local delta = a - b
  if delta < 0 then
    delta = -delta
  end
  return delta
end

local function count_suspicious(values)
  local count = 0
  for _, v in ipairs(values) do
    if is_suspicious_float_like(v) then
      count = count + 1
    end
  end
  return count
end

local function count_unique_map_keys(map)
  local count = 0
  for _ in pairs(map) do
    count = count + 1
  end
  return count
end

local function count_matching_pairs(candidate, pairs)
  local matches = 0
  for _, pair in ipairs(pairs) do
    local a = u32(candidate[pair[1]])
    local b = u32(candidate[pair[2]])
    if a ~= 0 and a == b then
      matches = matches + 1
    end
  end
  return matches
end

local function append_unique(list, value)
  for _, existing in ipairs(list) do
    if existing == value then
      return
    end
  end
  list[#list + 1] = value
end

local function join_or_none(list)
  if list == nil or #list == 0 then
    return "none"
  end
  return table.concat(list, ", ")
end

local function relation_bucket(a, b, cfg)
  if a == nil or b == nil or a == 0 or b == 0 then
    return "na"
  end
  if a == b then
    return "eq"
  end

  local page_a = math.floor(a / (2 ^ cfg.same_page_shift))
  local page_b = math.floor(b / (2 ^ cfg.same_page_shift))
  if page_a == page_b then
    return "same_page"
  end

  local region_a = math.floor(a / (2 ^ cfg.same_region_shift))
  local region_b = math.floor(b / (2 ^ cfg.same_region_shift))
  if region_a == region_b then
    return "same_region"
  end

  if abs_delta(a, b) <= cfg.near_distance then
    return "near"
  end

  return "far"
end

local function count_near_adjacent_pairs(sorted_values, max_delta)
  local count = 0
  for i = 1, #sorted_values - 1 do
    if abs_delta(sorted_values[i + 1], sorted_values[i]) <= max_delta then
      count = count + 1
    end
  end
  return count
end

local function add_flag(scored_candidate, flag)
  append_unique(scored_candidate.flags, flag)
end

local function has_flag(scored_candidate, wanted_flag)
  for _, flag in ipairs(scored_candidate.flags) do
    if flag == wanted_flag then
      return true
    end
  end
  return false
end

local function add_breakdown(scored_candidate, amount, label)
  local sign = "+"
  if amount < 0 then
    sign = "-"
  end
  scored_candidate.score_breakdown_parts[#scored_candidate.score_breakdown_parts + 1] =
    string.format("%s%d %s", sign, math.abs(amount), label)
end

local function compute_max_packed_run(values, max_delta)
  if #values == 0 then
    return 0
  end

  local sorted = {}
  for i, value in ipairs(values) do
    sorted[i] = value
  end
  table.sort(sorted)

  local best = 1
  local run = 1
  for i = 2, #sorted do
    if abs_delta(sorted[i], sorted[i - 1]) <= max_delta then
      run = run + 1
    else
      run = 1
    end
    if run > best then
      best = run
    end
  end
  return best
end

local function compute_monotonic_run(entries, max_delta)
  if #entries == 0 then
    return 0
  end

  local best = 1
  local run = 1
  local last_sign = 0

  for i = 2, #entries do
    local delta = entries[i].value - entries[i - 1].value
    local sign = 0
    if delta > 0 then
      sign = 1
    elseif delta < 0 then
      sign = -1
    end

    if sign ~= 0 and abs_delta(entries[i].value, entries[i - 1].value) <= max_delta then
      if last_sign == 0 or last_sign == sign then
        run = run + 1
      else
        run = 2
      end
      last_sign = sign
    else
      run = 1
      last_sign = 0
    end

    if run > best then
      best = run
    end
  end

  return best
end

local function build_field_info(key, value, cfg)
  local info = {
    key = key,
    value = u32(value),
    field_state = "scalar",
    is_zero = false,
    is_small_int = false,
    is_floatlike = false,
    is_address_shaped = false,
    is_aligned = false,
    zone = "status",
  }

  if key == "f08" or key == "f18" or key == "f20" then
    info.zone = "front"
  elseif key == "f68" or key == "f70" or key == "f78" then
    info.zone = "tail"
  end

  if info.value == 0 then
    info.field_state = "zero"
    info.is_zero = true
    return info
  end

  if is_small_int_like(info.value) then
    info.field_state = "small_int"
    info.is_small_int = true
    return info
  end

  if is_suspicious_float_like(info.value) then
    info.field_state = "floatlike"
    info.is_floatlike = true
    return info
  end

  info.is_aligned = (info.value % (cfg.alignment_mask + 1)) == 0
  if info.is_aligned and info.value >= cfg.address_floor then
    info.field_state = "addr_shaped"
    info.is_address_shaped = true
  end

  return info
end

local function analyze_legacy_layout(candidate)
  local cfg = MVP0.CONFIG.ranking.thresholds
  local pointer_values = {}
  local nonzero_value_counts = {}
  local metrics = {
    front_pointer_count = 0,
    tail_pointer_count = 0,
    pointer_like_count = 0,
    pointer_bucket_count = 0,
    dense_pointer_bucket_count = 0,
    near_pointer_pairs = 0,
    duplicate_nonzero_groups = 0,
    duplicate_nonzero_fields = 0,
    mirrored_pairs = 0,
    pointer_balance_delta = 0,
    pointer_balanced = false,
    pointer_diverse = false,
    pointer_unbalanced = false,
    template_clone_like = false,
    template_clone_heavy = false,
    mirrored_layout_like = false,
    mirrored_layout_heavy = false,
    code_blob_like = false,
    code_blob_heavy = false,
    small_int_dependency_like = false,
  }
  local pointer_bucket_counts = {}

  for _, key in ipairs(FRONT_KEYS) do
    local value = u32(candidate[key])
    if value ~= 0 then
      nonzero_value_counts[value] = (nonzero_value_counts[value] or 0) + 1
    end
    if is_legacy_pointer_like(value) then
      metrics.front_pointer_count = metrics.front_pointer_count + 1
      metrics.pointer_like_count = metrics.pointer_like_count + 1
      pointer_values[#pointer_values + 1] = value
    end
  end

  for _, key in ipairs(TAIL_KEYS) do
    local value = u32(candidate[key])
    if value ~= 0 then
      nonzero_value_counts[value] = (nonzero_value_counts[value] or 0) + 1
    end
    if is_legacy_pointer_like(value) then
      metrics.tail_pointer_count = metrics.tail_pointer_count + 1
      metrics.pointer_like_count = metrics.pointer_like_count + 1
      pointer_values[#pointer_values + 1] = value
    end
  end

  for _, count in pairs(nonzero_value_counts) do
    if count > 1 then
      metrics.duplicate_nonzero_groups = metrics.duplicate_nonzero_groups + 1
      metrics.duplicate_nonzero_fields = metrics.duplicate_nonzero_fields + (count - 1)
    end
  end

  metrics.mirrored_pairs = math.max(
    count_matching_pairs(candidate, MIRROR_PAIRS),
    count_matching_pairs(candidate, ALT_MIRROR_PAIRS)
  )

  table.sort(pointer_values)
  for _, value in ipairs(pointer_values) do
    local bucket = math.floor(value / (2 ^ cfg.legacy_pointer_bucket_shift))
    pointer_bucket_counts[bucket] = (pointer_bucket_counts[bucket] or 0) + 1
    if pointer_bucket_counts[bucket] > metrics.dense_pointer_bucket_count then
      metrics.dense_pointer_bucket_count = pointer_bucket_counts[bucket]
    end
  end

  metrics.pointer_bucket_count = count_unique_map_keys(pointer_bucket_counts)
  metrics.near_pointer_pairs = count_near_adjacent_pairs(pointer_values, cfg.near_distance)
  metrics.pointer_balance_delta = math.abs(metrics.front_pointer_count - metrics.tail_pointer_count)
  metrics.pointer_balanced =
    metrics.front_pointer_count > 0
    and metrics.tail_pointer_count > 0
    and metrics.pointer_balance_delta <= 1
  metrics.pointer_diverse =
    metrics.pointer_like_count >= 4
    and metrics.pointer_bucket_count >= 3
  metrics.pointer_unbalanced =
    metrics.pointer_like_count >= 4
    and (
      metrics.front_pointer_count == 0
      or metrics.tail_pointer_count == 0
      or metrics.pointer_balance_delta >= 2
    )
  metrics.template_clone_like =
    metrics.duplicate_nonzero_groups >= 1
    and metrics.duplicate_nonzero_fields >= 2
  metrics.template_clone_heavy =
    metrics.duplicate_nonzero_groups >= 2
    or metrics.duplicate_nonzero_fields >= 3
  metrics.mirrored_layout_like = metrics.mirrored_pairs >= 2
  metrics.mirrored_layout_heavy = metrics.mirrored_pairs >= 3
  metrics.code_blob_like =
    metrics.pointer_like_count >= 4
    and metrics.pointer_bucket_count <= 2
    and (
      metrics.near_pointer_pairs >= 2
      or metrics.dense_pointer_bucket_count >= 3
    )
  metrics.code_blob_heavy =
    metrics.pointer_like_count >= 5
    and metrics.pointer_bucket_count <= 2
    and (
      metrics.near_pointer_pairs >= 3
      or metrics.dense_pointer_bucket_count >= 4
    )
  metrics.small_int_dependency_like =
    is_small_int_like(candidate.f58)
    and not metrics.pointer_balanced
    and (
      metrics.pointer_like_count < 4
      or metrics.template_clone_like
      or metrics.mirrored_layout_like
      or metrics.code_blob_like
    )

  return metrics
end

local function analyze_advanced_layout(features)
  local cfg = MVP0.CONFIG.ranking.thresholds
  local address_entries = {}
  local ordered_address_entries = {}
  local page_counts = {}
  local region_counts = {}
  local front_region_counts = {}
  local tail_region_counts = {}
  local metrics = {
    relation_counts = {
      same_page_pairs = 0,
      same_region_pairs = 0,
      near_pairs = 0,
      eq_pairs = 0,
      far_pairs = 0,
      front_same_page_pairs = 0,
      tail_same_page_pairs = 0,
      cross_same_page_pairs = 0,
      front_same_region_pairs = 0,
      tail_same_region_pairs = 0,
      cross_same_region_pairs = 0,
    },
    relation_buckets = {},
    page_counts = page_counts,
    region_counts = region_counts,
    address_shaped_count = 0,
    page_count = 0,
    region_count = 0,
    dominant_page_count = 0,
    dominant_region_count = 0,
    clustered_field_count = 0,
    packed_run_length = 0,
    monotonic_run_length = 0,
    front_region_count = 0,
    tail_region_count = 0,
    front_regionally_distinct = false,
    tail_cluster_confined = false,
    anchor_distinct = false,
    f58_in_dense_cluster = false,
    pointer_fields = {},
    pointer_like_mask = "",
    pointer_alignment_count = 0,
    pointer_region_count = 0,
    pointer_balanced = false,
    pointer_diverse = false,
    front_pointer_count = 0,
    tail_pointer_count = 0,
    code_blob_score = 0,
    dense_cluster_majority_tail = false,
    blob_safeguard = false,
    mirrored_pairs = math.max(
      count_matching_pairs(features.candidate, MIRROR_PAIRS),
      count_matching_pairs(features.candidate, ALT_MIRROR_PAIRS)
    ),
    dense_field_keys = {},
    family_field_classes = {},
  }

  for _, key in ipairs(STRUCT_KEYS) do
    local info = features.field_info[key]
    if info ~= nil and info.is_address_shaped then
      local page = math.floor(info.value / (2 ^ cfg.same_page_shift))
      local region = math.floor(info.value / (2 ^ cfg.same_region_shift))
      info.page = page
      info.region = region
      page_counts[page] = (page_counts[page] or 0) + 1
      region_counts[region] = (region_counts[region] or 0) + 1

      if info.zone == "front" then
        front_region_counts[region] = (front_region_counts[region] or 0) + 1
      elseif info.zone == "tail" then
        tail_region_counts[region] = (tail_region_counts[region] or 0) + 1
      end

      address_entries[#address_entries + 1] = info
      ordered_address_entries[#ordered_address_entries + 1] = info
    end
  end

  metrics.address_shaped_count = #address_entries
  metrics.page_count = count_unique_map_keys(page_counts)
  metrics.region_count = count_unique_map_keys(region_counts)
  metrics.front_region_count = count_unique_map_keys(front_region_counts)
  metrics.tail_region_count = count_unique_map_keys(tail_region_counts)

  for _, count in pairs(page_counts) do
    if count > metrics.dominant_page_count then
      metrics.dominant_page_count = count
    end
    if count >= 2 then
      metrics.clustered_field_count = metrics.clustered_field_count + count
    end
  end

  for _, count in pairs(region_counts) do
    if count > metrics.dominant_region_count then
      metrics.dominant_region_count = count
    end
  end

  for _, info in ipairs(address_entries) do
    info.same_page_count = 0
    info.same_region_count = 0
    info.near_count = 0
  end

  for i = 1, #address_entries do
    local a = address_entries[i]
    for j = i + 1, #address_entries do
      local b = address_entries[j]
      local bucket = relation_bucket(a.value, b.value, cfg)
      metrics.relation_buckets[a.key .. "-" .. b.key] = bucket

      if bucket == "eq" then
        metrics.relation_counts.eq_pairs = metrics.relation_counts.eq_pairs + 1
      elseif bucket == "same_page" then
        metrics.relation_counts.same_page_pairs = metrics.relation_counts.same_page_pairs + 1
        a.same_page_count = a.same_page_count + 1
        b.same_page_count = b.same_page_count + 1
      elseif bucket == "same_region" then
        metrics.relation_counts.same_region_pairs = metrics.relation_counts.same_region_pairs + 1
        a.same_region_count = a.same_region_count + 1
        b.same_region_count = b.same_region_count + 1
      elseif bucket == "near" then
        metrics.relation_counts.near_pairs = metrics.relation_counts.near_pairs + 1
        a.near_count = a.near_count + 1
        b.near_count = b.near_count + 1
      else
        metrics.relation_counts.far_pairs = metrics.relation_counts.far_pairs + 1
      end

      local same_page = math.floor(a.value / (2 ^ cfg.same_page_shift)) == math.floor(b.value / (2 ^ cfg.same_page_shift))
      local same_region = math.floor(a.value / (2 ^ cfg.same_region_shift)) == math.floor(b.value / (2 ^ cfg.same_region_shift))

      if same_page then
        if a.zone == "front" and b.zone == "front" then
          metrics.relation_counts.front_same_page_pairs = metrics.relation_counts.front_same_page_pairs + 1
        elseif a.zone == "tail" and b.zone == "tail" then
          metrics.relation_counts.tail_same_page_pairs = metrics.relation_counts.tail_same_page_pairs + 1
        else
          metrics.relation_counts.cross_same_page_pairs = metrics.relation_counts.cross_same_page_pairs + 1
        end
      end

      if same_region then
        if a.zone == "front" and b.zone == "front" then
          metrics.relation_counts.front_same_region_pairs = metrics.relation_counts.front_same_region_pairs + 1
        elseif a.zone == "tail" and b.zone == "tail" then
          metrics.relation_counts.tail_same_region_pairs = metrics.relation_counts.tail_same_region_pairs + 1
        else
          metrics.relation_counts.cross_same_region_pairs = metrics.relation_counts.cross_same_region_pairs + 1
        end
      end
    end
  end

  metrics.front_regionally_distinct =
    metrics.front_region_count >= 2
    or (
      metrics.relation_counts.front_same_page_pairs == 0
      and metrics.relation_counts.front_same_region_pairs <= 1
    )

  local f58_info = features.field_info.f58
  if f58_info ~= nil and f58_info.is_address_shaped then
    local page_count = page_counts[f58_info.page] or 0
    local region_count = region_counts[f58_info.region] or 0
    metrics.f58_in_dense_cluster = page_count >= 2 or region_count >= 3
    metrics.anchor_distinct = page_count == 1 and region_count == 1
  end

  metrics.tail_cluster_confined =
    metrics.relation_counts.tail_same_page_pairs >= cfg.tail_cluster_min_pairs
    and metrics.relation_counts.front_same_page_pairs == 0
    and metrics.relation_counts.cross_same_page_pairs == 0

  metrics.dense_cluster_majority_tail =
    metrics.relation_counts.tail_same_page_pairs > metrics.relation_counts.front_same_page_pairs
    and metrics.relation_counts.tail_same_page_pairs >= cfg.tail_cluster_min_pairs

  local raw_values = {}
  for i, info in ipairs(address_entries) do
    raw_values[i] = info.value
  end
  metrics.packed_run_length = compute_max_packed_run(raw_values, cfg.near_distance)
  metrics.monotonic_run_length = compute_monotonic_run(ordered_address_entries, cfg.near_distance)

  for _, info in ipairs(address_entries) do
    local same_page_count = info.same_page_count or 0
    local same_region_count = info.same_region_count or 0
    local near_count = info.near_count or 0
    local is_anchor = info.key == "f58" and metrics.anchor_distinct
    local dense_clustered =
      same_page_count >= 1
      and (
        near_count >= 1
        or same_region_count >= 2
      )

    local tail_cluster_pointer_ok =
      info.zone == "tail"
      and metrics.tail_cluster_confined
      and metrics.front_regionally_distinct
      and metrics.anchor_distinct

    if is_anchor or ((same_region_count + near_count) >= 1 and (not dense_clustered or tail_cluster_pointer_ok)) then
      info.pointer_like = true
      metrics.pointer_fields[#metrics.pointer_fields + 1] = info.key
      metrics.pointer_alignment_count = metrics.pointer_alignment_count + 1
      if info.zone == "front" then
        metrics.front_pointer_count = metrics.front_pointer_count + 1
      elseif info.zone == "tail" then
        metrics.tail_pointer_count = metrics.tail_pointer_count + 1
      end
    else
      info.pointer_like = false
      if dense_clustered then
        append_unique(metrics.dense_field_keys, info.key)
      end
    end

    if info.pointer_like and info.key == "f58" and metrics.anchor_distinct then
      info.pointer_anchor = true
    end
  end

  local pointer_region_map = {}
  for _, info in ipairs(address_entries) do
    if info.pointer_like then
      pointer_region_map[info.region] = true
    end
  end
  metrics.pointer_region_count = count_unique_map_keys(pointer_region_map)
  metrics.pointer_balanced =
    metrics.front_pointer_count >= cfg.min_coherent_front_pointers
    and metrics.tail_pointer_count >= cfg.min_coherent_tail_pointers
    and math.abs(metrics.front_pointer_count - metrics.tail_pointer_count) <= 1
  metrics.pointer_diverse =
    metrics.pointer_region_count >= cfg.pointer_reward_min_regions
    and metrics.pointer_region_count <= cfg.pointer_reward_max_regions

  metrics.code_blob_score =
    (metrics.relation_counts.same_page_pairs * 3)
    + (metrics.relation_counts.same_region_pairs * 2)
    + (metrics.relation_counts.near_pairs * 2)
    + (math.max(0, metrics.packed_run_length - cfg.packed_run_threshold + 1) * 2)
    + (math.max(0, metrics.monotonic_run_length - cfg.monotonic_run_threshold + 1) * 2)
    + (math.max(0, metrics.clustered_field_count - cfg.max_dense_page_count + 1) * 2)

  if metrics.f58_in_dense_cluster then
    metrics.code_blob_score = metrics.code_blob_score + 3
  end
  if metrics.relation_counts.cross_same_page_pairs > 0 then
    metrics.code_blob_score = metrics.code_blob_score + 2
  end

  metrics.blob_safeguard =
    metrics.front_regionally_distinct
    and metrics.anchor_distinct
    and metrics.tail_cluster_confined

  metrics.pointer_like_mask = join_or_none(metrics.pointer_fields)

  for _, key in ipairs(STRUCT_KEYS) do
    local info = features.field_info[key]
    local class_code = "X"
    if info == nil then
      class_code = "X"
    elseif info.is_zero then
      class_code = "Z"
    elseif info.is_small_int then
      class_code = "S"
    elseif info.is_floatlike then
      class_code = "F"
    elseif info.pointer_like and info.key == "f58" and metrics.anchor_distinct then
      class_code = "A"
    elseif info.pointer_like then
      class_code = "P"
    elseif info.is_address_shaped and (info.same_page_count or 0) >= 1 then
      class_code = "C"
    elseif info.is_address_shaped then
      class_code = "D"
    end
    metrics.family_field_classes[#metrics.family_field_classes + 1] = key .. ":" .. class_code
  end

  return metrics
end

function MVP0.extract_local_features(candidate, target_value_pattern)
  local cfg = MVP0.CONFIG.ranking.thresholds
  local features = {
    candidate = candidate,
    target_value_pattern = target_value_pattern,
    target_match = candidate.f28 == target_value_pattern,
    field_info = {},
    float_like_count = 0,
    front_empty = candidate.f08 == 0 and candidate.f18 == 0 and candidate.f20 == 0,
    tail_empty = candidate.f68 == 0 and candidate.f70 == 0 and candidate.f78 == 0,
    value_copy_like = candidate.f20 == target_value_pattern and candidate.f28 == target_value_pattern,
    strong_front_block = candidate.f08 ~= 0 and candidate.f18 ~= 0 and candidate.f20 ~= 0,
    strong_tail_block = candidate.f68 ~= 0 and candidate.f70 ~= 0 and candidate.f78 ~= 0,
  }

  for _, key in ipairs(STRUCT_KEYS) do
    features.field_info[key] = build_field_info(key, candidate[key], cfg)
  end

  features.float_like_count = count_suspicious({
    candidate.f18, candidate.f20, candidate.f58,
    candidate.f68, candidate.f70, candidate.f78,
  })
  features.object_like = features.strong_front_block and features.strong_tail_block
  features.legacy_layout = analyze_legacy_layout(candidate)
  features.advanced_layout = analyze_advanced_layout(features)

  return features
end

function MVP0.score_base_candidate(features)
  local w = MVP0.CONFIG.ranking.local_weights
  local candidate = features.candidate
  local result = {
    candidate = candidate,
    hard_pass = true,
    flags = {},
    reasons_positive = {},
    reasons_negative = {},
    score_breakdown_parts = {},
    base_score = 0,
    prescore_score = 0,
    final_score = 0,
    score = 0,
    total_adjustment = 0,
    local_features = features,
    pointer_reward = 0,
    code_blob_penalty = 0,
    clone_penalty = 0,
    mirrored_penalty = 0,
    code_blob_score = features.advanced_layout.code_blob_score,
    template_family_id = "pending",
    template_family_size = 1,
    pointer_alignment_count = features.advanced_layout.pointer_alignment_count,
    pointer_region_count = features.advanced_layout.pointer_region_count,
    pointer_fields = features.advanced_layout.pointer_like_mask,
    tie_break_vector = "",
    rank_reason = "",
    rank_position = nil,
  }

  if features.target_match then
    result.base_score = result.base_score + w.target_match
    add_breakdown(result, w.target_match, "target_match")
    add_flag(result, "target_match")
    result.reasons_positive[#result.reasons_positive + 1] = "target value matches"
  else
    result.hard_pass = false
    result.reasons_negative[#result.reasons_negative + 1] = "target value mismatch"
  end

  for _, key in ipairs(FRONT_KEYS) do
    local value = candidate[key]
    if value ~= 0 then
      result.base_score = result.base_score + w.nonzero_field
      add_breakdown(result, w.nonzero_field, key .. "_nonzero")
      result.reasons_positive[#result.reasons_positive + 1] = key .. " nonzero"
    end
    if not is_suspicious_float_like(value) then
      result.base_score = result.base_score + w.not_floatlike_field
      add_breakdown(result, w.not_floatlike_field, key .. "_not_floatlike")
      result.reasons_positive[#result.reasons_positive + 1] = key .. " not float-like"
    end
  end

  for _, key in ipairs(TAIL_KEYS) do
    local value = candidate[key]
    if value ~= 0 then
      result.base_score = result.base_score + w.nonzero_field
      add_breakdown(result, w.nonzero_field, key .. "_nonzero")
      result.reasons_positive[#result.reasons_positive + 1] = key .. " nonzero"
    end
    if not is_suspicious_float_like(value) then
      result.base_score = result.base_score + w.not_floatlike_field
      add_breakdown(result, w.not_floatlike_field, key .. "_not_floatlike")
      result.reasons_positive[#result.reasons_positive + 1] = key .. " not float-like"
    end
  end

  if candidate.f58 ~= 0 then
    result.base_score = result.base_score + w.status_nonzero
    add_breakdown(result, w.status_nonzero, "f58_nonzero")
    result.reasons_positive[#result.reasons_positive + 1] = "f58 nonzero"
  end
  if is_small_int_like(candidate.f58) then
    result.base_score = result.base_score + w.status_small_int
    add_breakdown(result, w.status_small_int, "f58_small_int")
    add_flag(result, "small_int_status")
    result.reasons_positive[#result.reasons_positive + 1] = "status field is small-int-like"
  end
  if not is_suspicious_float_like(candidate.f58) then
    result.base_score = result.base_score + w.status_not_floatlike
    add_breakdown(result, w.status_not_floatlike, "f58_not_floatlike")
    result.reasons_positive[#result.reasons_positive + 1] = "f58 not float-like"
  end

  if features.front_empty then
    result.base_score = result.base_score - w.penalty_empty_front
    add_breakdown(result, -w.penalty_empty_front, "empty_front")
    result.reasons_negative[#result.reasons_negative + 1] = "front block is empty"
  end
  if features.tail_empty then
    result.base_score = result.base_score - w.penalty_empty_tail
    add_breakdown(result, -w.penalty_empty_tail, "empty_tail")
    result.reasons_negative[#result.reasons_negative + 1] = "tail block is empty"
  end

  if features.float_like_count >= 3 then
    result.base_score = result.base_score - w.penalty_floatlike_3plus
    add_breakdown(result, -w.penalty_floatlike_3plus, "floatlike_3plus")
    add_flag(result, "float_block_like")
    result.reasons_negative[#result.reasons_negative + 1] = "too many float-like fields"
  end
  if features.float_like_count >= 5 then
    result.base_score = result.base_score - w.penalty_floatlike_5plus
    add_breakdown(result, -w.penalty_floatlike_5plus, "floatlike_5plus")
    result.reasons_negative[#result.reasons_negative + 1] = "candidate resembles float block"
  end

  if features.value_copy_like then
    result.base_score = result.base_score - w.penalty_value_copy
    add_breakdown(result, -w.penalty_value_copy, "value_copy_like")
    add_flag(result, "value_copy_like")
    result.reasons_negative[#result.reasons_negative + 1] = "candidate resembles value copy block"
  end

  if features.strong_front_block then
    add_flag(result, "strong_front_block")
    result.reasons_positive[#result.reasons_positive + 1] = "front metadata present"
  end
  if features.strong_tail_block then
    add_flag(result, "strong_tail_block")
    result.reasons_positive[#result.reasons_positive + 1] = "tail reference block present"
  end
  if features.object_like then
    add_flag(result, "object_like")
  end

  local legacy = features.legacy_layout
  if legacy.pointer_balanced then
    result.base_score = result.base_score + w.legacy_pointer_balanced_bonus
    add_breakdown(result, w.legacy_pointer_balanced_bonus, "legacy_pointer_balanced")
  end
  if legacy.pointer_diverse then
    result.base_score = result.base_score + w.legacy_pointer_diverse_bonus
    add_breakdown(result, w.legacy_pointer_diverse_bonus, "legacy_pointer_diverse")
  end
  if legacy.pointer_unbalanced then
    result.base_score = result.base_score - w.legacy_pointer_unbalanced_penalty
    add_breakdown(result, -w.legacy_pointer_unbalanced_penalty, "legacy_pointer_unbalanced")
    result.reasons_negative[#result.reasons_negative + 1] = "pointer-like fields are concentrated on one side"
  end
  if legacy.template_clone_like then
    result.base_score = result.base_score - w.legacy_template_penalty
    add_breakdown(result, -w.legacy_template_penalty, "legacy_template_clone")
  end
  if legacy.template_clone_heavy then
    result.base_score = result.base_score - w.legacy_template_heavy_penalty
    add_breakdown(result, -w.legacy_template_heavy_penalty, "legacy_template_clone_heavy")
  end
  if legacy.mirrored_layout_like then
    result.base_score = result.base_score - w.legacy_mirrored_penalty
    add_breakdown(result, -w.legacy_mirrored_penalty, "legacy_mirrored_layout")
  end
  if legacy.mirrored_layout_heavy then
    result.base_score = result.base_score - w.legacy_mirrored_heavy_penalty
    add_breakdown(result, -w.legacy_mirrored_heavy_penalty, "legacy_mirrored_layout_heavy")
  end
  if legacy.code_blob_like then
    result.base_score = result.base_score - w.legacy_code_blob_penalty
    add_breakdown(result, -w.legacy_code_blob_penalty, "legacy_code_blob")
  end
  if legacy.code_blob_heavy then
    result.base_score = result.base_score - w.legacy_code_blob_heavy_penalty
    add_breakdown(result, -w.legacy_code_blob_heavy_penalty, "legacy_code_blob_heavy")
  end
  if legacy.small_int_dependency_like then
    result.base_score = result.base_score - w.legacy_small_int_dependency_penalty
    add_breakdown(result, -w.legacy_small_int_dependency_penalty, "legacy_small_int_dependency")
  end

  result.prescore_score = result.base_score
  result.final_score = result.base_score
  result.score = result.base_score

  return result
end

function MVP0.score_candidate(candidate, target_value_pattern)
  local features = MVP0.extract_local_features(candidate, target_value_pattern)
  return MVP0.score_base_candidate(features)
end

local function build_template_family_id(scored_candidate)
  local features = scored_candidate.local_features
  local advanced = features.advanced_layout
  local cfg = MVP0.CONFIG.ranking.thresholds
  local tokens = {}

  tokens[#tokens + 1] = table.concat(advanced.family_field_classes, ",")

  local relation_tokens = {}
  for _, pair in ipairs(FAMILY_PAIR_KEYS) do
    local key = pair[1] .. "-" .. pair[2]
    local bucket = advanced.relation_buckets[key]
    if bucket == nil then
      local left = features.field_info[pair[1]]
      local right = features.field_info[pair[2]]
      local left_value = left and left.value or 0
      local right_value = right and right.value or 0
      bucket = relation_bucket(left_value, right_value, cfg)
    end
    relation_tokens[#relation_tokens + 1] = key .. ":" .. bucket
  end

  tokens[#tokens + 1] = table.concat(relation_tokens, ",")
  tokens[#tokens + 1] = "mirror:" .. tostring(advanced.mirrored_pairs)
  tokens[#tokens + 1] = "packed:" .. tostring(advanced.packed_run_length)
  tokens[#tokens + 1] = "blobguard:" .. tostring(advanced.blob_safeguard)

  return table.concat(tokens, "|")
end

function MVP0.build_ranking_context(scored_candidates)
  local family_counts = {}
  local context = {
    family_counts = family_counts,
  }

  for _, scored_candidate in ipairs(scored_candidates) do
    local family_id = build_template_family_id(scored_candidate)
    scored_candidate.template_family_id = family_id
    family_counts[family_id] = (family_counts[family_id] or 0) + 1
  end

  return context
end

local function compute_pointer_reward(scored_candidate)
  local thresholds = MVP0.CONFIG.ranking.thresholds
  local adjustments = MVP0.CONFIG.ranking.adjustments
  local advanced = scored_candidate.local_features.advanced_layout

  if not advanced.pointer_balanced then
    return 0
  end
  if not advanced.pointer_diverse then
    return 0
  end
  if not advanced.anchor_distinct then
    return 0
  end

  local reward = 0
  if advanced.front_pointer_count >= thresholds.min_coherent_front_pointers then
    reward = reward + 1
  end
  if advanced.tail_pointer_count >= thresholds.min_coherent_tail_pointers then
    reward = reward + 1
  end
  if advanced.pointer_region_count >= thresholds.pointer_reward_min_regions
      and advanced.pointer_region_count <= thresholds.pointer_reward_max_regions then
    reward = reward + 1
  end
  if advanced.front_regionally_distinct and advanced.anchor_distinct then
    reward = reward + 1
  end

  if advanced.code_blob_score >= thresholds.heavy_blob_score and not advanced.blob_safeguard then
    reward = 0
  end

  if reward > adjustments.pointer_reward_cap then
    reward = adjustments.pointer_reward_cap
  end
  return reward
end

local function compute_code_blob_penalty(scored_candidate)
  local thresholds = MVP0.CONFIG.ranking.thresholds
  local adjustments = MVP0.CONFIG.ranking.adjustments
  local advanced = scored_candidate.local_features.advanced_layout

  if advanced.code_blob_score >= thresholds.heavy_blob_score and not advanced.blob_safeguard then
    return adjustments.code_blob_penalty_heavy
  end
  if advanced.code_blob_score >= thresholds.mild_blob_score then
    return adjustments.code_blob_penalty_mild
  end
  return 0
end

local function compute_clone_penalty(family_size)
  local thresholds = MVP0.CONFIG.ranking.thresholds
  local adjustments = MVP0.CONFIG.ranking.adjustments

  if family_size >= thresholds.heavy_family_size then
    return adjustments.clone_penalty_heavy
  end
  if family_size >= thresholds.medium_family_size then
    return adjustments.clone_penalty_medium
  end
  if family_size >= thresholds.mild_family_size then
    return adjustments.clone_penalty_mild
  end
  return 0
end

function MVP0.apply_rank_adjustments(scored_candidate, context)
  local thresholds = MVP0.CONFIG.ranking.thresholds
  local adjustments = MVP0.CONFIG.ranking.adjustments
  local advanced = scored_candidate.local_features.advanced_layout
  local family_size = context.family_counts[scored_candidate.template_family_id] or 1
  local pointer_reward = compute_pointer_reward(scored_candidate)
  local code_blob_penalty = compute_code_blob_penalty(scored_candidate)
  local clone_penalty = compute_clone_penalty(family_size)
  local mirrored_penalty = 0

  if family_size >= thresholds.mirrored_family_repeat_min and advanced.mirrored_pairs >= 2 then
    mirrored_penalty = adjustments.mirrored_penalty
  end

  if pointer_reward > 0 then
    add_flag(scored_candidate, "pointer_balanced")
    add_flag(scored_candidate, "pointer_diverse")
    add_flag(scored_candidate, "coherent_pointer_layout")
  end
  if code_blob_penalty > 0 then
    add_flag(scored_candidate, "code_blob_like")
  end
  if clone_penalty > 0 then
    add_flag(scored_candidate, "template_clone_family")
  end
  if mirrored_penalty > 0 then
    add_flag(scored_candidate, "mirrored_family_like")
  end

  scored_candidate.pointer_reward = pointer_reward
  scored_candidate.code_blob_penalty = code_blob_penalty
  scored_candidate.clone_penalty = clone_penalty
  scored_candidate.mirrored_penalty = mirrored_penalty
  scored_candidate.template_family_size = family_size
  scored_candidate.pointer_alignment_count = advanced.pointer_alignment_count
  scored_candidate.pointer_region_count = advanced.pointer_region_count
  scored_candidate.pointer_fields = advanced.pointer_like_mask

  local adjustment_parts = {}
  if pointer_reward > 0 then
    adjustment_parts[#adjustment_parts + 1] = string.format("+%d pointer_reward", pointer_reward)
  end
  if code_blob_penalty > 0 then
    adjustment_parts[#adjustment_parts + 1] = string.format("-%d code_blob_penalty", code_blob_penalty)
  end
  if clone_penalty > 0 then
    adjustment_parts[#adjustment_parts + 1] = string.format("-%d clone_penalty", clone_penalty)
  end
  if mirrored_penalty > 0 then
    adjustment_parts[#adjustment_parts + 1] = string.format("-%d mirrored_penalty", mirrored_penalty)
  end

  scored_candidate.total_adjustment =
    pointer_reward - code_blob_penalty - clone_penalty - mirrored_penalty
  scored_candidate.final_score = scored_candidate.base_score + scored_candidate.total_adjustment
  scored_candidate.score = scored_candidate.final_score

  local score_parts = {}
  for _, part in ipairs(scored_candidate.score_breakdown_parts) do
    score_parts[#score_parts + 1] = part
  end
  for _, part in ipairs(adjustment_parts) do
    score_parts[#score_parts + 1] = part
  end
  if #score_parts == 0 then
    score_parts[1] = "no score changes"
  end
  scored_candidate.score_breakdown = table.concat(score_parts, "; ")

  local negative_count = #scored_candidate.reasons_negative
  scored_candidate.tie_break_vector = string.format(
    "final=%d|family=%d|pointer=%d|blob=%d|clone=%d|mirror=%d|neg=%d",
    scored_candidate.final_score,
    family_size,
    pointer_reward,
    scored_candidate.code_blob_score,
    clone_penalty,
    mirrored_penalty,
    negative_count
  )

  local rank_reasons = {}
  if pointer_reward > 0 then
    rank_reasons[#rank_reasons + 1] = "coherent pointer layout"
  end
  if code_blob_penalty > 0 then
    if advanced.blob_safeguard then
      rank_reasons[#rank_reasons + 1] = "tail-cluster blob penalty capped by anchor/front safeguard"
    else
      rank_reasons[#rank_reasons + 1] = "blob-like packed layout penalized"
    end
  end
  if clone_penalty > 0 then
    rank_reasons[#rank_reasons + 1] = "family size " .. tostring(family_size) .. " raised clone penalty"
  end
  if mirrored_penalty > 0 then
    rank_reasons[#rank_reasons + 1] = "mirrored family surcharge applied"
  end
  if #rank_reasons == 0 then
    rank_reasons[1] = "rank follows base_score with no extra adjustments"
  end
  scored_candidate.rank_reason = table.concat(rank_reasons, "; ")
end

function MVP0.compare_final_candidates(a, b)
  if a == nil then
    return false
  end
  if b == nil then
    return true
  end

  if a.final_score ~= b.final_score then
    return a.final_score > b.final_score
  end
  if a.template_family_size ~= b.template_family_size then
    return a.template_family_size < b.template_family_size
  end
  if a.pointer_reward ~= b.pointer_reward then
    return a.pointer_reward > b.pointer_reward
  end
  if a.code_blob_score ~= b.code_blob_score then
    return a.code_blob_score < b.code_blob_score
  end
  if a.clone_penalty ~= b.clone_penalty then
    return a.clone_penalty < b.clone_penalty
  end

  local a_negative = #(a.reasons_negative or {})
  local b_negative = #(b.reasons_negative or {})
  if a_negative ~= b_negative then
    return a_negative < b_negative
  end

  local a_addr = (a.candidate and a.candidate.value_addr) or 0
  local b_addr = (b.candidate and b.candidate.value_addr) or 0
  return a_addr < b_addr
end

function MVP0.compare_scored_candidates(a, b)
  return MVP0.compare_final_candidates(a, b)
end

function MVP0.rank_candidates(scored)
  local context = MVP0.build_ranking_context(scored)
  for _, scored_candidate in ipairs(scored) do
    MVP0.apply_rank_adjustments(scored_candidate, context)
  end

  table.sort(scored, function(a, b)
    return MVP0.compare_final_candidates(a, b)
  end)

  for index, scored_candidate in ipairs(scored) do
    scored_candidate.rank_position = index
  end

  local best = scored[1]
  local second = scored[2]
  local gap = 0
  if best ~= nil then
    gap = second and (best.score - second.score) or best.score
  end

  local confidence
  if gap >= MVP0.CONFIG.confidence.high_gap then
    confidence = "HIGH"
  elseif gap >= MVP0.CONFIG.confidence.medium_gap then
    confidence = "MEDIUM"
  else
    confidence = "LOW"
  end

  return {
    best = best,
    second = second,
    ranked = scored,
    score_gap = gap,
    confidence = confidence,
    manual_review = (confidence == "LOW"),
  }
end

function MVP0.make_input(candidate_value_addrs, target_value_pattern, opts)
  opts = opts or {}
  return {
    candidate_value_addrs = candidate_value_addrs,
    target_value_pattern = u32(target_value_pattern),
    target_value_float = opts.target_value_float,
    session_id = opts.session_id,
  }
end

function MVP0.build_candidate(value_addr)
  local c = {}
  local off = MVP0.CONFIG.offsets

  c.value_addr = value_addr
  c.base_addr = value_addr - MVP0.CONFIG.value_offset

  c.f08 = read_u32(c.base_addr + off.f08)
  c.f18 = read_u32(c.base_addr + off.f18)
  c.f20 = read_u32(c.base_addr + off.f20)
  c.f28 = read_u32(c.base_addr + off.f28)
  c.f58 = read_u32(c.base_addr + off.f58)
  c.f68 = read_u32(c.base_addr + off.f68)
  c.f70 = read_u32(c.base_addr + off.f70)
  c.f78 = read_u32(c.base_addr + off.f78)
  c.f28_float = read_f32(c.base_addr + off.f28)

  return c
end

function MVP0.recommend_action(rank)
  local best = rank.best
  local second = rank.second
  local cfg = MVP0.CONFIG.recommendation
  local result = {
    recommended_candidate = best,
    recommendation = "REJECT",
    confidence = rank.confidence,
    score_gap = rank.score_gap,
    manual_review_required = true,
    rationale = {},
  }

  local function add_reason(reason)
    result.rationale[#result.rationale + 1] = reason
  end

  if best == nil then
    add_reason("no candidates available")
    return result
  end

  if has_flag(best, "object_like") then
    add_reason("best candidate has object-like structure")
  end
  if best.pointer_reward > 0 then
    add_reason("best candidate has a coherent pointer layout")
  end
  if best.clone_penalty > 0 then
    add_reason("best candidate belongs to template family size " .. tostring(best.template_family_size))
  end
  if best.code_blob_penalty > 0 then
    add_reason("best candidate triggered code-blob penalty " .. tostring(best.code_blob_penalty))
  end
  if second ~= nil then
    add_reason("score gap over second place is " .. tostring(rank.score_gap))
  else
    add_reason("only one matching candidate was scored")
  end

  if rank.confidence == "HIGH"
      and best.final_score >= cfg.accept_min_score
      and has_flag(best, "object_like")
      and best.pointer_reward > 0
      and best.code_blob_penalty == 0
      and best.clone_penalty == 0
      and best.mirrored_penalty == 0 then
    result.recommendation = "ACCEPT"
    result.manual_review_required = false
    add_reason("high-confidence candidate is suitable for direct use")
    return result
  end

  if best.final_score < cfg.review_min_score then
    result.recommendation = "REJECT"
    result.manual_review_required = true
    add_reason("top candidate score is below the review threshold")
    return result
  end

  result.recommendation = "REVIEW"
  result.manual_review_required = true
  add_reason("manual review is recommended before acting on this candidate")
  return result
end

function MVP0.render_report(rank, input_payload, recommendation)
  local lines = {}
  table.insert(lines, "=== Session Summary ===")
  if input_payload.session_id then
    table.insert(lines, "Session: " .. tostring(input_payload.session_id))
  end
  table.insert(lines, "Candidates: " .. tostring(#rank.ranked))
  table.insert(lines, "Target value pattern: " .. hex_u32(input_payload.target_value_pattern))
  if input_payload.target_value_float ~= nil then
    table.insert(lines, "Target value float: " .. tostring(input_payload.target_value_float))
  end
  if rank.best then
    table.insert(lines, "Best candidate: " .. hex_u64(rank.best.candidate.value_addr))
    table.insert(lines, "Best base: " .. hex_u64(rank.best.candidate.base_addr))
    table.insert(lines, "Best score: " .. tostring(rank.best.score))
  end
  if rank.second then
    table.insert(lines, "Second score: " .. tostring(rank.second.score))
  end
  table.insert(lines, "Score gap: " .. tostring(rank.score_gap))
  table.insert(lines, "Confidence: " .. rank.confidence)
  table.insert(lines, "Manual review: " .. tostring(rank.manual_review))
  table.insert(lines, "=======================")
  table.insert(lines, "")

  if recommendation then
    table.insert(lines, "=== Recommendation ===")
    table.insert(lines, "Recommendation: " .. recommendation.recommendation)
    table.insert(lines, "Confidence: " .. recommendation.confidence)
    table.insert(lines, "Manual review required: " .. tostring(recommendation.manual_review_required))
    if recommendation.recommended_candidate then
      table.insert(lines, "Recommended value addr: " .. hex_u64(recommendation.recommended_candidate.candidate.value_addr))
      table.insert(lines, "Recommended base addr : " .. hex_u64(recommendation.recommended_candidate.candidate.base_addr))
      table.insert(lines, "Recommended score     : " .. tostring(recommendation.recommended_candidate.score))
    end
    if #recommendation.rationale > 0 then
      table.insert(lines, "Rationale: " .. table.concat(recommendation.rationale, "; "))
    end
    table.insert(lines, "======================")
    table.insert(lines, "")
  end

  for _, scored_candidate in ipairs(rank.ranked) do
    local c = scored_candidate.candidate
    table.insert(lines, "--- Candidate #" .. tostring(scored_candidate.rank_position) .. " ---")
    table.insert(lines, "value_addr = " .. hex_u64(c.value_addr))
    table.insert(lines, "base_addr  = " .. hex_u64(c.base_addr))
    table.insert(lines, "f08 = " .. hex_u32(c.f08))
    table.insert(lines, "f18 = " .. hex_u32(c.f18))
    table.insert(lines, "f20 = " .. hex_u32(c.f20))
    table.insert(lines, "f28 = " .. hex_u32(c.f28) .. " (" .. tostring(c.f28_float) .. ")")
    table.insert(lines, "f58 = " .. hex_u32(c.f58))
    table.insert(lines, "f68 = " .. hex_u32(c.f68))
    table.insert(lines, "f70 = " .. hex_u32(c.f70))
    table.insert(lines, "f78 = " .. hex_u32(c.f78))
    table.insert(lines, "rank_position = " .. tostring(scored_candidate.rank_position))
    table.insert(lines, "base_score = " .. tostring(scored_candidate.base_score))
    table.insert(lines, "prescore_score = " .. tostring(scored_candidate.prescore_score))
    table.insert(lines, "final_score = " .. tostring(scored_candidate.final_score))
    table.insert(lines, "total adjustment = " .. tostring(scored_candidate.total_adjustment))
    table.insert(lines, "score = " .. tostring(scored_candidate.score))
    table.insert(lines, "hard_pass = " .. tostring(scored_candidate.hard_pass))
    table.insert(lines, "flags = " .. join_or_none(scored_candidate.flags))
    table.insert(lines, "score_breakdown = " .. tostring(scored_candidate.score_breakdown))
    table.insert(lines, "code_blob_score = " .. tostring(scored_candidate.code_blob_score))
    table.insert(lines, "code_blob_penalty = " .. tostring(scored_candidate.code_blob_penalty))
    table.insert(lines, "template_family_id = " .. tostring(scored_candidate.template_family_id))
    table.insert(lines, "template_family_size = " .. tostring(scored_candidate.template_family_size))
    table.insert(lines, "clone_penalty = " .. tostring(scored_candidate.clone_penalty))
    table.insert(lines, "mirrored_penalty = " .. tostring(scored_candidate.mirrored_penalty))
    table.insert(lines, "pointer_reward = " .. tostring(scored_candidate.pointer_reward))
    table.insert(lines, "pointer_alignment_count = " .. tostring(scored_candidate.pointer_alignment_count))
    table.insert(lines, "pointer_region_count = " .. tostring(scored_candidate.pointer_region_count))
    table.insert(lines, "pointer_fields = " .. tostring(scored_candidate.pointer_fields))
    table.insert(lines, "tie_break_vector = " .. tostring(scored_candidate.tie_break_vector))
    table.insert(lines, "rank_reason = " .. tostring(scored_candidate.rank_reason))
    table.insert(lines, "positive = " .. join_or_none(scored_candidate.reasons_positive))
    table.insert(lines, "negative = " .. join_or_none(scored_candidate.reasons_negative))
    table.insert(lines, "")
  end

  return table.concat(lines, "\n")
end

function MVP0.run(input_payload)
  local candidates = {}
  for _, value_addr in ipairs(input_payload.candidate_value_addrs) do
    candidates[#candidates + 1] = MVP0.build_candidate(value_addr)
  end

  local scored = {}
  for _, candidate in ipairs(candidates) do
    scored[#scored + 1] = MVP0.score_candidate(candidate, input_payload.target_value_pattern)
  end

  local ranked = MVP0.rank_candidates(scored)
  ranked.recommendation = MVP0.recommend_action(ranked)
  ranked.report_text = MVP0.render_report(ranked, input_payload, ranked.recommendation)
  return ranked
end

_G.MVP0 = MVP0
return MVP0
