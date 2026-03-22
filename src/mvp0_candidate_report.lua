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

MVP0_REPORT_BUILD_TAG = "probe-20260321-v1"

print("[MVP0] REPORT_BUILD_TAG = " .. tostring(MVP0_REPORT_BUILD_TAG))
print("[MVP0] REPORT_SOURCE = " .. tostring(debug.getinfo(1, "S").source))

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
      base_legacy_pointer_balanced_bonus = 1,
      base_legacy_pointer_diverse_bonus = 0,
      base_legacy_pointer_unbalanced_penalty = 1,
      base_legacy_template_penalty = 1,
      base_legacy_template_heavy_penalty = 2,
      base_legacy_mirrored_penalty = 1,
      base_legacy_mirrored_heavy_penalty = 2,
      base_legacy_code_blob_penalty = 1,
      base_legacy_code_blob_heavy_penalty = 2,
      base_legacy_small_int_dependency_penalty = 1,
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
      pointer_reward_min_alignment = 3,
      pointer_reward_min_regions = 2,
      pointer_reward_max_regions = 5,
      distinct_anchor_distance = 0x2000,
      anchor_region_peer_cap = 2,
      mild_blob_score = 6,
      medium_blob_score = 12,
      heavy_blob_score = 18,
      packed_run_threshold = 2,
      monotonic_run_threshold = 2,
      max_dense_page_count = 2,
      tail_cluster_min_pairs = 3,
      family_dense_same_page_min = 2,
      mild_family_size = 2,
      medium_family_size = 4,
      heavy_family_size = 6,
      mirrored_family_repeat_min = 2,
      scalar_score_mild = 6,
      scalar_score_medium = 10,
      scalar_score_heavy = 14,
      text_score_mild = 6,
      text_score_medium = 10,
      text_score_heavy = 14,
      ascii_printable_min = 0x20,
      ascii_printable_max = 0x7E,
      dominant_cluster_majority_min = 4,
      dominant_cluster_majority_ratio = 0.7,
    },
    adjustments = {
      pointer_reward_cap = 5,
      isolated_split_penalty = 2,
      code_blob_penalty_mild = 3,
      code_blob_penalty_medium = 6,
      code_blob_penalty_heavy = 10,
      scalar_block_penalty_mild = 3,
      scalar_block_penalty_medium = 6,
      scalar_block_penalty_heavy = 10,
      text_block_penalty_mild = 3,
      text_block_penalty_medium = 6,
      text_block_penalty_heavy = 10,
      clone_penalty_mild = 3,
      clone_penalty_medium = 6,
      clone_penalty_heavy = 10,
      clone_penalty_signature_surcharge = 2,
      mirrored_penalty = 4,
    },
    scalar_high_bytes = {
      [0x3B] = true, [0x3C] = true, [0x3D] = true, [0x3E] = true,
      [0x3F] = true, [0x40] = true, [0x41] = true, [0x42] = true,
      [0xBB] = true, [0xBC] = true, [0xBD] = true, [0xBE] = true,
      [0xBF] = true, [0xC0] = true, [0xC1] = true, [0xC2] = true,
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
  if type(n) ~= "number" then
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
  local ok, value = pcall(readInteger, addr)
  if not ok then
    return nil
  end
  return u32(value)
end

local function read_f32(addr)
  local ok, value = pcall(readFloat, addr)
  if not ok or type(value) ~= "number" then
    return nil
  end
  return value
end

local function is_suspicious_float_like(x)
  local value = u32(x)
  if value == nil then
    return false
  end
  return MVP0.CONFIG.suspicious[value] == true
end

local function is_small_int_like(x)
  x = u32(x)
  if x == nil then
    return false
  end
  return x ~= 0 and x < 0x1000
end

local function is_legacy_pointer_like(x)
  x = u32(x)
  if x == nil then
    return false
  end
  return x ~= 0
    and not is_suspicious_float_like(x)
    and not is_small_int_like(x)
    and x >= MVP0.CONFIG.ranking.thresholds.address_floor
end

local function is_zero_u32(x)
  local value = u32(x)
  return value ~= nil and value == 0
end

local function is_nonzero_u32(x)
  local value = u32(x)
  return value ~= nil and value ~= 0
end

local function equal_u32(a, b)
  local left = u32(a)
  local right = u32(b)
  return left ~= nil and right ~= nil and left == right
end

local function log_field_guard(candidate_addr, field_name, raw_value, helper_name, note)
  print(string.format(
    "[MVP0][nil-guard] candidate=%s field=%s raw=%s helper=%s note=%s",
    hex_u64(candidate_addr),
    tostring(field_name),
    tostring(raw_value),
    tostring(helper_name),
    tostring(note)
  ))
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
    if a ~= nil and b ~= nil and a ~= 0 and a == b then
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

local function fixed_cluster_size_bucket(value)
  if value == nil or value <= 1 then
    return "1"
  end
  if value == 2 then
    return "2"
  end
  if value == 3 then
    return "3"
  end
  return "4+"
end

local function fixed_score_bucket(value, mild_threshold, medium_threshold, heavy_threshold)
  if value == nil or value < mild_threshold then
    return "0"
  end
  if value < medium_threshold then
    return "low"
  end
  if value < heavy_threshold then
    return "medium"
  end
  return "high"
end

local function compact_family_class_pattern(family_field_classes)
  local codes = {}
  for _, token in ipairs(family_field_classes or {}) do
    local _, code = string.match(token, "([^:]+):(.+)")
    codes[#codes + 1] = code or "X"
  end
  return table.concat(codes, "")
end

local function dominant_majority_threshold(address_shaped_count)
  local cfg = MVP0.CONFIG.ranking.thresholds
  return math.max(cfg.dominant_cluster_majority_min, math.ceil(address_shaped_count * cfg.dominant_cluster_majority_ratio))
end

local function dominant_cluster_is_majority(dominant_cluster_size, address_shaped_count)
  if address_shaped_count == nil or address_shaped_count <= 0 then
    return false
  end
  return dominant_cluster_size >= dominant_majority_threshold(address_shaped_count)
end

local function little_endian_bytes(value)
  value = u32(value) or 0
  return {
    value % 0x100,
    math.floor(value / 0x100) % 0x100,
    math.floor(value / 0x10000) % 0x100,
    math.floor(value / 0x1000000) % 0x100,
  }
end

local function is_printable_ascii(byte_value)
  local cfg = MVP0.CONFIG.ranking.thresholds
  return byte_value >= cfg.ascii_printable_min and byte_value <= cfg.ascii_printable_max
end

local function decode_ieee754_float(word)
  word = u32(word) or 0
  local sign = math.floor(word / 0x80000000) % 2
  local exponent = math.floor(word / 0x800000) % 0x100
  local mantissa = word % 0x800000

  if exponent == 255 then
    return nil
  end

  local value
  if exponent == 0 then
    if mantissa == 0 then
      value = 0.0
    else
      value = (mantissa / 8388608.0) * (2 ^ -126)
    end
  else
    value = (1.0 + (mantissa / 8388608.0)) * (2 ^ (exponent - 127))
  end

  if sign == 1 then
    value = -value
  end

  return value
end

local function is_reasonable_scalar_float(word)
  local value = decode_ieee754_float(word)
  if value == nil then
    return false, nil
  end
  local absolute = math.abs(value)
  if absolute < 1.0e-6 or absolute > 1.0e6 then
    return false, value
  end
  return true, value
end

local function is_utf16ish_word(word)
  local bytes = little_endian_bytes(word)
  return
    bytes[2] == 0
    and bytes[4] == 0
    and is_printable_ascii(bytes[1])
    and is_printable_ascii(bytes[3])
end

local function printable_ascii_count(word)
  local bytes = little_endian_bytes(word)
  local count = 0
  for _, byte_value in ipairs(bytes) do
    if is_printable_ascii(byte_value) then
      count = count + 1
    end
  end
  return count
end

local function longest_adjacent_printable_run(word)
  local bytes = little_endian_bytes(word)
  local best = 0
  local run = 0
  for _, byte_value in ipairs(bytes) do
    if is_printable_ascii(byte_value) then
      run = run + 1
      if run > best then
        best = run
      end
    else
      run = 0
    end
  end
  return best
end

local function is_ascii_textish_word(word)
  local printable = printable_ascii_count(word)
  if printable >= 4 then
    return true
  end
  if printable >= 3 and longest_adjacent_printable_run(word) >= 2 then
    return true
  end
  return false
end

local function collect_adjacent_text_chunks(word)
  local bytes = little_endian_bytes(word)
  local chunks = {}
  local seen = {}

  for start_index = 1, 3 do
    if is_printable_ascii(bytes[start_index]) and is_printable_ascii(bytes[start_index + 1]) then
      local pair = string.char(bytes[start_index], bytes[start_index + 1])
      if not seen[pair] then
        chunks[#chunks + 1] = pair
        seen[pair] = true
      end
    end
  end

  for start_index = 1, 2 do
    if is_printable_ascii(bytes[start_index])
        and is_printable_ascii(bytes[start_index + 1])
        and is_printable_ascii(bytes[start_index + 2]) then
      local triplet = string.char(bytes[start_index], bytes[start_index + 1], bytes[start_index + 2])
      if not seen[triplet] then
        chunks[#chunks + 1] = triplet
        seen[triplet] = true
      end
    end
  end

  return chunks
end

local function text_chunk_signature(word)
  local chunks = collect_adjacent_text_chunks(word)
  if #chunks == 0 then
    return nil
  end
  table.sort(chunks)
  return table.concat(chunks, "|")
end

local function is_strong_scalar_suspicious_value(word)
  local high_byte = math.floor((u32(word) or 0) / 0x1000000) % 0x100
  if MVP0.CONFIG.ranking.scalar_high_bytes[high_byte] then
    return true
  end
  local ok = is_reasonable_scalar_float(word)
  return ok
end

local function is_strong_text_suspicious_value(word)
  return is_ascii_textish_word(word) or is_utf16ish_word(word)
end

local function penalty_from_score(score, mild_threshold, medium_threshold, heavy_threshold, mild_penalty, medium_penalty, heavy_penalty)
  if score == nil or score < mild_threshold then
    return 0
  end
  if score < medium_threshold then
    return mild_penalty
  end
  if score < heavy_threshold then
    return medium_penalty
  end
  return heavy_penalty
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

local function build_field_info(candidate_addr, key, value, cfg)
  local info = {
    key = key,
    value = u32(value),
    raw_value = value,
    field_state = "scalar",
    is_zero = false,
    is_small_int = false,
    is_floatlike = false,
    is_address_shaped = false,
    is_aligned = false,
    is_unreadable = false,
    zone = "status",
  }

  if key == "f08" or key == "f18" or key == "f20" then
    info.zone = "front"
  elseif key == "f68" or key == "f70" or key == "f78" then
    info.zone = "tail"
  end

  if type(info.value) ~= "number" then
    info.field_state = "unreadable"
    info.is_unreadable = true
    log_field_guard(candidate_addr, key, value, "build_field_info", "non_numeric_value")
    return info
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
    local value = u32(candidate[key]) or 0
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
    local value = u32(candidate[key]) or 0
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
  local relation_matrix = {}
  local primary_edges = {}
  local same_region_edges = {}
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
    pointer_cluster_count = 0,
    front_cluster_count = 0,
    tail_cluster_count = 0,
    front_non_singleton_cluster_count = 0,
    tail_non_singleton_cluster_count = 0,
    dominant_cluster_size = 0,
    dominant_cluster_covers_majority = false,
    cluster_layout = "scattered",
    has_valid_anchor = false,
    valid_anchor_key = nil,
    weak_split_like = false,
    strong_split_like = false,
    isolated_split_like = false,
    scalar_block_score = 0,
    text_block_score = 0,
    mirrored_pairs = math.max(
      count_matching_pairs(features.candidate, MIRROR_PAIRS),
      count_matching_pairs(features.candidate, ALT_MIRROR_PAIRS)
    ),
    dense_field_keys = {},
    family_field_classes = {},
    family_scalar_bucket = "0",
    family_text_bucket = "0",
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

      info.pre_scalar_like = is_strong_scalar_suspicious_value(info.value) == true
      info.pre_text_like = is_strong_text_suspicious_value(info.value)
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

  for idx, info in ipairs(address_entries) do
    info.entry_index = idx
    info.same_page_count = 0
    info.same_region_count = 0
    info.near_count = 0
    primary_edges[idx] = {}
    same_region_edges[idx] = {}
    relation_matrix[idx] = {}
  end

  for i = 1, #address_entries do
    local a = address_entries[i]
    for j = i + 1, #address_entries do
      local b = address_entries[j]
      local bucket = relation_bucket(a.value, b.value, cfg)
      metrics.relation_buckets[a.key .. "-" .. b.key] = bucket
      relation_matrix[i][j] = bucket
      relation_matrix[j][i] = bucket

      if bucket == "eq" then
        metrics.relation_counts.eq_pairs = metrics.relation_counts.eq_pairs + 1
      elseif bucket == "same_page" then
        metrics.relation_counts.same_page_pairs = metrics.relation_counts.same_page_pairs + 1
        a.same_page_count = a.same_page_count + 1
        b.same_page_count = b.same_page_count + 1
        primary_edges[i][j] = true
        primary_edges[j][i] = true
      elseif bucket == "same_region" then
        metrics.relation_counts.same_region_pairs = metrics.relation_counts.same_region_pairs + 1
        a.same_region_count = a.same_region_count + 1
        b.same_region_count = b.same_region_count + 1
        same_region_edges[i][j] = true
        same_region_edges[j][i] = true
      elseif bucket == "near" then
        metrics.relation_counts.near_pairs = metrics.relation_counts.near_pairs + 1
        a.near_count = a.near_count + 1
        b.near_count = b.near_count + 1
        primary_edges[i][j] = true
        primary_edges[j][i] = true
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

  local function make_cluster(member_indices)
    local cluster = {
      member_indices = {},
      size = 0,
      front_count = 0,
      tail_count = 0,
      status_count = 0,
      page_map = {},
      region_map = {},
      page_count = 0,
      region_count = 0,
      primary_page = nil,
      primary_region = nil,
    }

    for _, member_index in ipairs(member_indices) do
      local info = address_entries[member_index]
      cluster.member_indices[#cluster.member_indices + 1] = member_index
      cluster.size = cluster.size + 1
      cluster.page_map[info.page] = (cluster.page_map[info.page] or 0) + 1
      cluster.region_map[info.region] = (cluster.region_map[info.region] or 0) + 1

      if info.zone == "front" then
        cluster.front_count = cluster.front_count + 1
      elseif info.zone == "tail" then
        cluster.tail_count = cluster.tail_count + 1
      else
        cluster.status_count = cluster.status_count + 1
      end
    end

    cluster.page_count = count_unique_map_keys(cluster.page_map)
    cluster.region_count = count_unique_map_keys(cluster.region_map)

    local best_page_count = 0
    for page, count in pairs(cluster.page_map) do
      if count > best_page_count then
        best_page_count = count
        cluster.primary_page = page
      end
    end

    local best_region_count = 0
    for region, count in pairs(cluster.region_map) do
      if count > best_region_count then
        best_region_count = count
        cluster.primary_region = region
      end
    end

    return cluster
  end

  local function build_clusters_from_edges(edges)
    local visited = {}
    local clusters = {}

    for start_index = 1, #address_entries do
      if not visited[start_index] then
        local stack = {start_index}
        local members = {}
        visited[start_index] = true

        while #stack > 0 do
          local current = stack[#stack]
          stack[#stack] = nil
          members[#members + 1] = current

          for peer_index in pairs(edges[current] or {}) do
            if not visited[peer_index] then
              visited[peer_index] = true
              stack[#stack + 1] = peer_index
            end
          end
        end

        clusters[#clusters + 1] = make_cluster(members)
      end
    end

    return clusters
  end

  local function cluster_has_same_region_bridge(cluster_a, cluster_b)
    for _, member_a in ipairs(cluster_a.member_indices) do
      for _, member_b in ipairs(cluster_b.member_indices) do
        if same_region_edges[member_a] ~= nil and same_region_edges[member_a][member_b] then
          return true
        end
      end
    end
    return false
  end

  local function merged_cluster_would_form_majority_blob(cluster_a, cluster_b)
    local merged_size = cluster_a.size + cluster_b.size
    local merged_front = cluster_a.front_count + cluster_b.front_count
    local merged_tail = cluster_a.tail_count + cluster_b.tail_count
    return
      dominant_cluster_is_majority(merged_size, metrics.address_shaped_count)
      and merged_front >= 2
      and merged_tail >= 2
  end

  local function merge_clusters(cluster_a, cluster_b)
    local merged_members = {}
    for _, member_index in ipairs(cluster_a.member_indices) do
      merged_members[#merged_members + 1] = member_index
    end
    for _, member_index in ipairs(cluster_b.member_indices) do
      merged_members[#merged_members + 1] = member_index
    end
    return make_cluster(merged_members)
  end

  local clusters = build_clusters_from_edges(primary_edges)

  local merged = true
  while merged do
    merged = false
    for i = 1, #clusters do
      if merged then
        break
      end
      for j = i + 1, #clusters do
        if cluster_has_same_region_bridge(clusters[i], clusters[j])
            and not merged_cluster_would_form_majority_blob(clusters[i], clusters[j]) then
          clusters[i] = merge_clusters(clusters[i], clusters[j])
          table.remove(clusters, j)
          merged = true
          break
        end
      end
    end
  end

  local clusters_by_id = {}
  for cluster_index, cluster in ipairs(clusters) do
    cluster.id = cluster_index
    clusters_by_id[cluster_index] = cluster
    for _, member_index in ipairs(cluster.member_indices) do
      local info = address_entries[member_index]
      info.cluster_id = cluster_index
      info.cluster_size = cluster.size
    end
  end

  local dominant_cluster = nil
  local dominant_tail_cluster = nil
  local dominant_front_cluster = nil
  local front_outside_tail = false

  metrics.front_regionally_distinct =
    metrics.front_region_count >= 2
    or (
      metrics.relation_counts.front_same_page_pairs == 0
      and metrics.relation_counts.front_same_region_pairs <= 1
    )

  for _, cluster in ipairs(clusters) do
    if dominant_cluster == nil
        or cluster.size > dominant_cluster.size
        or (cluster.size == dominant_cluster.size and (cluster.front_count + cluster.tail_count) > (dominant_cluster.front_count + dominant_cluster.tail_count)) then
      dominant_cluster = cluster
    end

    if cluster.front_count > 0 then
      metrics.front_cluster_count = metrics.front_cluster_count + 1
      if cluster.size >= 2 then
        metrics.front_non_singleton_cluster_count = metrics.front_non_singleton_cluster_count + 1
      end
    end
    if cluster.tail_count > 0 then
      metrics.tail_cluster_count = metrics.tail_cluster_count + 1
      if cluster.size >= 2 then
        metrics.tail_non_singleton_cluster_count = metrics.tail_non_singleton_cluster_count + 1
      end
    end
    if cluster.front_count > 0 or cluster.tail_count > 0 then
      metrics.pointer_cluster_count = metrics.pointer_cluster_count + 1
    end

    if dominant_tail_cluster == nil
        or cluster.tail_count > dominant_tail_cluster.tail_count
        or (cluster.tail_count == dominant_tail_cluster.tail_count and cluster.size > dominant_tail_cluster.size) then
      dominant_tail_cluster = cluster
    end

    if dominant_front_cluster == nil
        or cluster.front_count > dominant_front_cluster.front_count
        or (cluster.front_count == dominant_front_cluster.front_count and cluster.size > dominant_front_cluster.size) then
      dominant_front_cluster = cluster
    end
  end

  if dominant_cluster ~= nil then
    metrics.dominant_cluster_size = dominant_cluster.size
    metrics.dominant_cluster_covers_majority =
      dominant_cluster_is_majority(dominant_cluster.size, metrics.address_shaped_count)
  end

  if dominant_tail_cluster ~= nil and dominant_tail_cluster.tail_count <= 0 then
    dominant_tail_cluster = nil
  end
  if dominant_front_cluster ~= nil and dominant_front_cluster.front_count <= 0 then
    dominant_front_cluster = nil
  end

  if dominant_tail_cluster ~= nil then
    for _, info in ipairs(address_entries) do
      if info.zone == "front" and info.cluster_id ~= dominant_tail_cluster.id then
        front_outside_tail = true
        break
      end
    end
  end

  local dominant_cluster_front_tail_merged =
    dominant_cluster ~= nil
    and dominant_cluster.front_count >= 2
    and dominant_cluster.tail_count >= 2
    and metrics.dominant_cluster_covers_majority

  if dominant_cluster_front_tail_merged then
    metrics.cluster_layout = "single_blob"
  elseif dominant_front_cluster ~= nil
      and dominant_tail_cluster ~= nil
      and dominant_front_cluster.id ~= dominant_tail_cluster.id
      and (
        dominant_front_cluster.primary_page ~= dominant_tail_cluster.primary_page
        or dominant_front_cluster.primary_region ~= dominant_tail_cluster.primary_region
      ) then
    metrics.cluster_layout = "front_tail_split"
  else
    metrics.cluster_layout = "scattered"
  end

  local anchor_candidates = {"f58", "f08", "f18", "f20", "f68", "f70", "f78"}
  for _, key in ipairs(anchor_candidates) do
    local info = features.field_info[key]
    if info ~= nil and info.is_address_shaped then
      local outside_dominant_dense =
        dominant_cluster == nil
        or dominant_cluster.size < 2
        or info.cluster_id ~= dominant_cluster.id
      local separated_from_tail =
        dominant_tail_cluster == nil
        or info.page ~= dominant_tail_cluster.primary_page
        or info.region ~= dominant_tail_cluster.primary_region
      local structurally_independent =
        dominant_tail_cluster == nil
        or info.cluster_id ~= dominant_tail_cluster.id
        or info.cluster_size == 1

      if outside_dominant_dense
          and separated_from_tail
          and structurally_independent
          and not info.pre_scalar_like
          and not info.pre_text_like then
        metrics.has_valid_anchor = true
        metrics.valid_anchor_key = key
        break
      end
    end
  end

  if metrics.cluster_layout ~= "single_blob"
      and metrics.cluster_layout ~= "front_tail_split"
      and dominant_tail_cluster ~= nil
      and dominant_tail_cluster.tail_count >= 1
      and front_outside_tail
      and metrics.has_valid_anchor then
    metrics.cluster_layout = "anchor_plus_tail_cluster"
  end

  local f58_info = features.field_info.f58
  if f58_info ~= nil and f58_info.is_address_shaped and dominant_cluster ~= nil then
    metrics.f58_in_dense_cluster =
      f58_info.cluster_id == dominant_cluster.id
      and dominant_cluster.size >= 2
  end

  metrics.tail_cluster_confined =
    dominant_tail_cluster ~= nil
    and dominant_tail_cluster.tail_count >= 2
    and metrics.relation_counts.cross_same_page_pairs == 0

  metrics.dense_cluster_majority_tail =
    dominant_tail_cluster ~= nil
    and dominant_tail_cluster.tail_count >= 2
    and (dominant_front_cluster == nil or dominant_tail_cluster.size >= dominant_front_cluster.size)

  local raw_values = {}
  for i, info in ipairs(address_entries) do
    raw_values[i] = info.value
  end
  metrics.packed_run_length = compute_max_packed_run(raw_values, cfg.near_distance)
  metrics.monotonic_run_length = compute_monotonic_run(ordered_address_entries, cfg.near_distance)

  local coherent_cluster_ids = {}
  if metrics.cluster_layout == "front_tail_split" then
    coherent_cluster_ids[dominant_front_cluster.id] = true
    coherent_cluster_ids[dominant_tail_cluster.id] = true
  elseif metrics.cluster_layout == "anchor_plus_tail_cluster" then
    if dominant_tail_cluster ~= nil then
      coherent_cluster_ids[dominant_tail_cluster.id] = true
    end
    if dominant_front_cluster ~= nil and dominant_front_cluster.id ~= (dominant_tail_cluster and dominant_tail_cluster.id or -1) then
      coherent_cluster_ids[dominant_front_cluster.id] = true
    end
  elseif metrics.cluster_layout == "scattered" then
    for _, cluster in ipairs(clusters) do
      if cluster.size >= 2 then
        coherent_cluster_ids[cluster.id] = true
      end
    end
  end

  for _, key in ipairs(STRUCT_KEYS) do
    local info = features.field_info[key]
    if info ~= nil and info.is_address_shaped then
      local same_page_count = info.same_page_count or 0
      local same_region_count = info.same_region_count or 0
      local near_count = info.near_count or 0
      local in_coherent_cluster = coherent_cluster_ids[info.cluster_id] == true
      local is_valid_anchor = metrics.valid_anchor_key == info.key
      local dense_clustered =
        same_page_count >= 1
        and (
          near_count >= 1
          or same_region_count >= 2
        )

      info.pointer_like = false
      if is_valid_anchor then
        info.pointer_like = true
        info.pointer_anchor = true
      elseif metrics.cluster_layout == "front_tail_split" or metrics.cluster_layout == "anchor_plus_tail_cluster" then
        info.pointer_like = in_coherent_cluster
      elseif metrics.cluster_layout == "scattered" then
        info.pointer_like = in_coherent_cluster and not info.pre_scalar_like and not info.pre_text_like
      end

      if info.pointer_like then
        metrics.pointer_fields[#metrics.pointer_fields + 1] = info.key
        metrics.pointer_alignment_count = metrics.pointer_alignment_count + 1
        if info.zone == "front" then
          metrics.front_pointer_count = metrics.front_pointer_count + 1
        elseif info.zone == "tail" then
          metrics.tail_pointer_count = metrics.tail_pointer_count + 1
        end
      elseif dense_clustered then
        append_unique(metrics.dense_field_keys, info.key)
      end
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
    and math.abs(metrics.front_pointer_count - metrics.tail_pointer_count) <= 2
  metrics.pointer_diverse =
    metrics.pointer_region_count >= cfg.pointer_reward_min_regions
    and metrics.pointer_region_count <= cfg.pointer_reward_max_regions
  metrics.weak_split_like =
    metrics.cluster_layout == "front_tail_split"
    and metrics.dominant_cluster_size == 1
    and metrics.pointer_alignment_count <= 3
    and not (
      metrics.front_non_singleton_cluster_count >= 1
      and metrics.tail_non_singleton_cluster_count >= 1
    )
  metrics.strong_split_like =
    metrics.cluster_layout == "front_tail_split"
    and (
      metrics.dominant_cluster_size >= 2
      or metrics.pointer_alignment_count >= 4
      or metrics.pointer_region_count >= 3
      or (
        metrics.front_non_singleton_cluster_count >= 1
        and metrics.tail_non_singleton_cluster_count >= 1
      )
    )
  metrics.isolated_split_like =
    metrics.cluster_layout == "front_tail_split"
    and metrics.front_non_singleton_cluster_count == 0
    and metrics.tail_non_singleton_cluster_count == 0
    and not metrics.has_valid_anchor
    and (
      metrics.pointer_alignment_count <= 2
      or metrics.pointer_region_count <= 2
    )

  metrics.code_blob_score =
    (metrics.relation_counts.same_page_pairs * 4)
    + (metrics.relation_counts.same_region_pairs * 2)
    + (metrics.relation_counts.near_pairs * 2)
    + (metrics.relation_counts.cross_same_page_pairs * 4)
    + (metrics.relation_counts.cross_same_region_pairs * 2)
    + (math.max(0, metrics.packed_run_length - cfg.packed_run_threshold + 1) * 3)
    + (math.max(0, metrics.monotonic_run_length - cfg.monotonic_run_threshold + 1) * 3)
    + (math.max(0, metrics.clustered_field_count - cfg.max_dense_page_count + 1) * 2)
    + (math.max(0, metrics.dominant_page_count - 1) * 2)
    + (math.max(0, metrics.dominant_region_count - 2) * 1)

  if metrics.cluster_layout == "single_blob" then
    metrics.code_blob_score = metrics.code_blob_score + 6
  end
  if dominant_cluster_front_tail_merged then
    metrics.code_blob_score = metrics.code_blob_score + 4
  end
  if metrics.f58_in_dense_cluster then
    metrics.code_blob_score = metrics.code_blob_score + 2
  end
  if metrics.packed_run_length >= cfg.packed_run_threshold + 1 then
    metrics.code_blob_score = metrics.code_blob_score + 2
  end
  if metrics.monotonic_run_length >= cfg.monotonic_run_threshold + 1 then
    metrics.code_blob_score = metrics.code_blob_score + 2
  end

  metrics.blob_safeguard =
    metrics.cluster_layout == "front_tail_split"
    or metrics.cluster_layout == "anchor_plus_tail_cluster"

  metrics.pointer_like_mask = join_or_none(metrics.pointer_fields)

  local scalar_like_field_count = 0
  local scalar_values = {}
  local scalar_high_byte_counts = {}
  local scalar_float_bucket_counts = {}

  local text_word_count = 0
  local utf16_word_count = 0
  local text_chunk_counts = {}

  for _, key in ipairs(STRUCT_KEYS) do
    local info = features.field_info[key]
    if info ~= nil and not info.is_zero and not info.is_unreadable then
      local cluster = clusters_by_id[info.cluster_id]
      local strong_pointer_evidence =
        info.pointer_like
        and (
          (cluster ~= nil and cluster.size >= 2)
          or metrics.valid_anchor_key == info.key
        )

      local scalar_like_field =
        not strong_pointer_evidence
        and (
          info.is_floatlike
          or info.pre_scalar_like
        )

      local ascii_textish_word = is_ascii_textish_word(info.value)
      local utf16_word = is_utf16ish_word(info.value)
      local text_chunks = collect_adjacent_text_chunks(info.value)
      local text_like_field =
        not strong_pointer_evidence
        and (
          ascii_textish_word
          or utf16_word
        )

      info.strong_scalar_like = scalar_like_field
      info.strong_text_like = text_like_field

      if scalar_like_field then
        scalar_like_field_count = scalar_like_field_count + 1
        local high_byte = math.floor(info.value / 0x1000000) % 0x100
        scalar_high_byte_counts[high_byte] = (scalar_high_byte_counts[high_byte] or 0) + 1

        local reasonable_float, scalar_float = is_reasonable_scalar_float(info.value)
        if reasonable_float then
          scalar_values[#scalar_values + 1] = { key = key, float = scalar_float }
          local float_bucket = string.format("%.3f", scalar_float)
          scalar_float_bucket_counts[float_bucket] = (scalar_float_bucket_counts[float_bucket] or 0) + 1
        end
      end

      if text_like_field then
        if ascii_textish_word then
          text_word_count = text_word_count + 1
        end
        if utf16_word then
          utf16_word_count = utf16_word_count + 1
        end
        for _, chunk in ipairs(text_chunks) do
          text_chunk_counts[chunk] = (text_chunk_counts[chunk] or 0) + 1
        end
      end
    end
  end

  local opposed_pair_count = 0
  local smooth_pair_count = 0
  for i = 1, #scalar_values do
    for j = i + 1, #scalar_values do
      local left = scalar_values[i].float
      local right = scalar_values[j].float
      local tolerance = math.max(0.05, 0.10 * math.max(math.abs(left), math.abs(right)))
      if left * right < 0 and math.abs(left + right) <= tolerance then
        opposed_pair_count = opposed_pair_count + 1
      end
      if math.abs(left - right) <= tolerance then
        smooth_pair_count = smooth_pair_count + 1
      end
    end
  end

  local scalar_template_repeat_count = 0
  for _, count in pairs(scalar_high_byte_counts) do
    if count > 1 then
      scalar_template_repeat_count = scalar_template_repeat_count + (count - 1)
    end
  end
  for _, count in pairs(scalar_float_bucket_counts) do
    if count > 1 then
      scalar_template_repeat_count = scalar_template_repeat_count + (count - 1)
    end
  end

  local repeated_text_chunk_count = 0
  for _, count in pairs(text_chunk_counts) do
    if count > 1 then
      repeated_text_chunk_count = repeated_text_chunk_count + (count - 1)
    end
  end

  metrics.scalar_block_score =
    (2 * scalar_like_field_count)
    + (3 * opposed_pair_count)
    + (2 * smooth_pair_count)
    + (2 * scalar_template_repeat_count)
    + ((metrics.pointer_alignment_count <= 1) and 3 or 0)

  metrics.text_block_score =
    (3 * text_word_count)
    + (2 * utf16_word_count)
    + (2 * repeated_text_chunk_count)
    + ((metrics.pointer_alignment_count == 0) and 3 or 0)

  if text_word_count < 2 and repeated_text_chunk_count == 0 and utf16_word_count == 0 then
    metrics.text_block_score = 0
  end

  metrics.family_scalar_bucket =
    fixed_score_bucket(metrics.scalar_block_score, cfg.scalar_score_mild, cfg.scalar_score_medium, cfg.scalar_score_heavy)
  metrics.family_text_bucket =
    fixed_score_bucket(metrics.text_block_score, cfg.text_score_mild, cfg.text_score_medium, cfg.text_score_heavy)

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
    elseif info.pointer_like and info.key == metrics.valid_anchor_key then
      class_code = "A"
    elseif info.pointer_like then
      class_code = "P"
    elseif dominant_cluster ~= nil and info.is_address_shaped and info.cluster_id == dominant_cluster.id and dominant_cluster.size >= 2 then
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
    target_match = equal_u32(candidate.f28, target_value_pattern),
    field_info = {},
    float_like_count = 0,
    front_empty = is_zero_u32(candidate.f08) and is_zero_u32(candidate.f18) and is_zero_u32(candidate.f20),
    tail_empty = is_zero_u32(candidate.f68) and is_zero_u32(candidate.f70) and is_zero_u32(candidate.f78),
    value_copy_like = equal_u32(candidate.f20, target_value_pattern) and equal_u32(candidate.f28, target_value_pattern),
    strong_front_block = is_nonzero_u32(candidate.f08) and is_nonzero_u32(candidate.f18) and is_nonzero_u32(candidate.f20),
    strong_tail_block = is_nonzero_u32(candidate.f68) and is_nonzero_u32(candidate.f70) and is_nonzero_u32(candidate.f78),
  }

  for _, key in ipairs(STRUCT_KEYS) do
    features.field_info[key] = build_field_info(candidate.value_addr, key, candidate[key], cfg)
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
    strong_structure_bonus = 0,
    sparse_anchor_tail_penalty = 0,
    anchored_fragmented_split_penalty = 0,
    one_sided_anchorless_split_penalty = 0,
    isolated_split_penalty = 0,
    code_blob_penalty = 0,
    scalar_block_penalty = 0,
    text_block_penalty = 0,
    clone_penalty = 0,
    mirrored_penalty = 0,
    code_blob_score = features.advanced_layout.code_blob_score,
    scalar_block_score = features.advanced_layout.scalar_block_score,
    text_block_score = features.advanced_layout.text_block_score,
    template_family_id = "pending",
    clone_family_id = "pending",
    template_family_size = 1,
    pointer_alignment_count = features.advanced_layout.pointer_alignment_count,
    pointer_region_count = features.advanced_layout.pointer_region_count,
    pointer_fields = features.advanced_layout.pointer_like_mask,
    pointer_cluster_count = features.advanced_layout.pointer_cluster_count,
    front_cluster_count = features.advanced_layout.front_cluster_count,
    tail_cluster_count = features.advanced_layout.tail_cluster_count,
    front_non_singleton_cluster_count = features.advanced_layout.front_non_singleton_cluster_count,
    tail_non_singleton_cluster_count = features.advanced_layout.tail_non_singleton_cluster_count,
    dominant_cluster_size = features.advanced_layout.dominant_cluster_size,
    cluster_layout = features.advanced_layout.cluster_layout,
    has_valid_anchor = features.advanced_layout.has_valid_anchor,
    dominant_cluster_covers_majority = features.advanced_layout.dominant_cluster_covers_majority,
    isolated_split_like = features.advanced_layout.isolated_split_like,
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
    if is_nonzero_u32(value) then
      result.base_score = result.base_score + w.nonzero_field
      add_breakdown(result, w.nonzero_field, key .. "_nonzero")
      result.reasons_positive[#result.reasons_positive + 1] = key .. " nonzero"
    end
    if type(value) == "number" and not is_suspicious_float_like(value) then
      result.base_score = result.base_score + w.not_floatlike_field
      add_breakdown(result, w.not_floatlike_field, key .. "_not_floatlike")
      result.reasons_positive[#result.reasons_positive + 1] = key .. " not float-like"
    end
  end

  for _, key in ipairs(TAIL_KEYS) do
    local value = candidate[key]
    if is_nonzero_u32(value) then
      result.base_score = result.base_score + w.nonzero_field
      add_breakdown(result, w.nonzero_field, key .. "_nonzero")
      result.reasons_positive[#result.reasons_positive + 1] = key .. " nonzero"
    end
    if type(value) == "number" and not is_suspicious_float_like(value) then
      result.base_score = result.base_score + w.not_floatlike_field
      add_breakdown(result, w.not_floatlike_field, key .. "_not_floatlike")
      result.reasons_positive[#result.reasons_positive + 1] = key .. " not float-like"
    end
  end

  if is_nonzero_u32(candidate.f58) then
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
  if type(candidate.f58) == "number" and not is_suspicious_float_like(candidate.f58) then
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
    result.base_score = result.base_score + w.base_legacy_pointer_balanced_bonus
    if w.base_legacy_pointer_balanced_bonus ~= 0 then
      add_breakdown(result, w.base_legacy_pointer_balanced_bonus, "legacy_pointer_balanced_compat")
    end
  end
  if legacy.pointer_diverse then
    result.base_score = result.base_score + w.base_legacy_pointer_diverse_bonus
    if w.base_legacy_pointer_diverse_bonus ~= 0 then
      add_breakdown(result, w.base_legacy_pointer_diverse_bonus, "legacy_pointer_diverse_compat")
    end
  end
  if legacy.pointer_unbalanced then
    result.base_score = result.base_score - w.base_legacy_pointer_unbalanced_penalty
    add_breakdown(result, -w.base_legacy_pointer_unbalanced_penalty, "legacy_pointer_unbalanced_compat")
    result.reasons_negative[#result.reasons_negative + 1] = "pointer-like fields are concentrated on one side"
  end
  if legacy.template_clone_like then
    result.base_score = result.base_score - w.base_legacy_template_penalty
    add_breakdown(result, -w.base_legacy_template_penalty, "legacy_template_clone_compat")
  end
  if legacy.template_clone_heavy then
    result.base_score = result.base_score - w.base_legacy_template_heavy_penalty
    add_breakdown(result, -w.base_legacy_template_heavy_penalty, "legacy_template_clone_heavy_compat")
  end
  if legacy.mirrored_layout_like then
    result.base_score = result.base_score - w.base_legacy_mirrored_penalty
    add_breakdown(result, -w.base_legacy_mirrored_penalty, "legacy_mirrored_layout_compat")
  end
  if legacy.mirrored_layout_heavy then
    result.base_score = result.base_score - w.base_legacy_mirrored_heavy_penalty
    add_breakdown(result, -w.base_legacy_mirrored_heavy_penalty, "legacy_mirrored_layout_heavy_compat")
  end
  if legacy.code_blob_like then
    result.base_score = result.base_score - w.base_legacy_code_blob_penalty
    add_breakdown(result, -w.base_legacy_code_blob_penalty, "legacy_code_blob_compat")
  end
  if legacy.code_blob_heavy then
    result.base_score = result.base_score - w.base_legacy_code_blob_heavy_penalty
    add_breakdown(result, -w.base_legacy_code_blob_heavy_penalty, "legacy_code_blob_heavy_compat")
  end
  if legacy.small_int_dependency_like then
    result.base_score = result.base_score - w.base_legacy_small_int_dependency_penalty
    add_breakdown(result, -w.base_legacy_small_int_dependency_penalty, "legacy_small_int_dependency_compat")
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
  local class_pattern = compact_family_class_pattern(advanced.family_field_classes)
  local blob_bucket = fixed_score_bucket(
    advanced.code_blob_score,
    cfg.mild_blob_score,
    cfg.medium_blob_score,
    cfg.heavy_blob_score
  )
  tokens[#tokens + 1] = "cls:" .. class_pattern
  tokens[#tokens + 1] = "layout:" .. tostring(advanced.cluster_layout)
  tokens[#tokens + 1] = "fptr:" .. fixed_count_bucket(advanced.front_pointer_count)
  tokens[#tokens + 1] = "tptr:" .. fixed_count_bucket(advanced.tail_pointer_count)
  tokens[#tokens + 1] = "align:" .. fixed_count_bucket(advanced.pointer_alignment_count)
  tokens[#tokens + 1] = "preg:" .. fixed_count_bucket(advanced.pointer_region_count)
  tokens[#tokens + 1] = "dom:" .. fixed_cluster_size_bucket(advanced.dominant_cluster_size)
  tokens[#tokens + 1] = "fns:" .. fixed_count_bucket(advanced.front_non_singleton_cluster_count)
  tokens[#tokens + 1] = "tns:" .. fixed_count_bucket(advanced.tail_non_singleton_cluster_count)
  tokens[#tokens + 1] = "scalar:" .. fixed_score_bucket(advanced.scalar_block_score, cfg.scalar_score_mild, cfg.scalar_score_medium, cfg.scalar_score_heavy)
  tokens[#tokens + 1] = "text:" .. fixed_score_bucket(advanced.text_block_score, cfg.text_score_mild, cfg.text_score_medium, cfg.text_score_heavy)
  tokens[#tokens + 1] = "blob:" .. blob_bucket
  tokens[#tokens + 1] = "mirror:" .. fixed_count_bucket(advanced.mirrored_pairs)

  return table.concat(tokens, "|")
end

local function build_clone_family_id(scored_candidate)
  local features = scored_candidate.local_features
  local advanced = features.advanced_layout
  local cfg = MVP0.CONFIG.ranking.thresholds
  local tokens = {}
  local blob_bucket = fixed_score_bucket(
    advanced.code_blob_score,
    cfg.mild_blob_score,
    cfg.medium_blob_score,
    cfg.heavy_blob_score
  )
  tokens[#tokens + 1] = "layout:" .. tostring(advanced.cluster_layout)
  tokens[#tokens + 1] = "fptr:" .. fixed_count_bucket(advanced.front_pointer_count)
  tokens[#tokens + 1] = "tptr:" .. fixed_count_bucket(advanced.tail_pointer_count)
  tokens[#tokens + 1] = "align:" .. fixed_count_bucket(advanced.pointer_alignment_count)
  tokens[#tokens + 1] = "preg:" .. fixed_count_bucket(advanced.pointer_region_count)
  tokens[#tokens + 1] = "dom:" .. fixed_cluster_size_bucket(advanced.dominant_cluster_size)
  tokens[#tokens + 1] = "fns:" .. fixed_count_bucket(advanced.front_non_singleton_cluster_count)
  tokens[#tokens + 1] = "tns:" .. fixed_count_bucket(advanced.tail_non_singleton_cluster_count)
  tokens[#tokens + 1] = "scalar:" .. fixed_score_bucket(advanced.scalar_block_score, cfg.scalar_score_mild, cfg.scalar_score_medium, cfg.scalar_score_heavy)
  tokens[#tokens + 1] = "text:" .. fixed_score_bucket(advanced.text_block_score, cfg.text_score_mild, cfg.text_score_medium, cfg.text_score_heavy)
  tokens[#tokens + 1] = "blob:" .. blob_bucket
  tokens[#tokens + 1] = "mirror:" .. fixed_count_bucket(advanced.mirrored_pairs)

  return table.concat(tokens, "|")
end

function MVP0.build_ranking_context(scored_candidates)
  local clone_family_counts = {}
  local clone_family_meta = {}
  local context = {
    clone_family_counts = clone_family_counts,
    clone_family_meta = clone_family_meta,
  }

  for _, scored_candidate in ipairs(scored_candidates) do
    local family_id = build_template_family_id(scored_candidate)
    local clone_family_id = build_clone_family_id(scored_candidate)
    local advanced = scored_candidate.local_features.advanced_layout
    local scalar_bucket = fixed_score_bucket(
      advanced.scalar_block_score,
      MVP0.CONFIG.ranking.thresholds.scalar_score_mild,
      MVP0.CONFIG.ranking.thresholds.scalar_score_medium,
      MVP0.CONFIG.ranking.thresholds.scalar_score_heavy
    )
    local text_bucket = fixed_score_bucket(
      advanced.text_block_score,
      MVP0.CONFIG.ranking.thresholds.text_score_mild,
      MVP0.CONFIG.ranking.thresholds.text_score_medium,
      MVP0.CONFIG.ranking.thresholds.text_score_heavy
    )
    local blob_bucket = fixed_score_bucket(
      advanced.code_blob_score,
      MVP0.CONFIG.ranking.thresholds.mild_blob_score,
      MVP0.CONFIG.ranking.thresholds.medium_blob_score,
      MVP0.CONFIG.ranking.thresholds.heavy_blob_score
    )

    scored_candidate.template_family_id = family_id
    scored_candidate.clone_family_id = clone_family_id
    clone_family_counts[clone_family_id] = (clone_family_counts[clone_family_id] or 0) + 1
    clone_family_meta[clone_family_id] = {
      cluster_layout = advanced.cluster_layout,
      scalar_bucket = scalar_bucket,
      text_bucket = text_bucket,
      blob_bucket = blob_bucket,
    }
  end

  return context
end

local function compute_pointer_reward(scored_candidate)
  local thresholds = MVP0.CONFIG.ranking.thresholds
  local adjustments = MVP0.CONFIG.ranking.adjustments
  local advanced = scored_candidate.local_features.advanced_layout
  local pointer_field_count = #(advanced.pointer_fields or {})
  local two_sided_split_support =
    advanced.front_non_singleton_cluster_count > 0
    and advanced.tail_non_singleton_cluster_count > 0
  local reward = 0

  if advanced.pointer_alignment_count < thresholds.pointer_reward_min_alignment then
    return 0
  end

  if advanced.weak_split_like then
    reward = 0
  elseif advanced.strong_split_like
      and advanced.front_pointer_count >= thresholds.min_coherent_front_pointers
      and advanced.tail_pointer_count >= thresholds.min_coherent_tail_pointers then
    reward = 3
    if advanced.pointer_region_count >= 3 then
      reward = reward + 1
    end
    if advanced.dominant_cluster_size >= 2
        or (
          advanced.front_non_singleton_cluster_count >= 1
          and advanced.tail_non_singleton_cluster_count >= 1
        ) then
      reward = reward + 1
    end
  elseif advanced.cluster_layout == "anchor_plus_tail_cluster"
      and advanced.tail_cluster_count >= 1
      and advanced.tail_pointer_count >= thresholds.min_coherent_tail_pointers
      and (
        advanced.front_pointer_count >= 1
        or advanced.has_valid_anchor
      ) then
    reward = 3
  elseif advanced.pointer_balanced then
    reward = 2
  elseif advanced.pointer_region_count >= thresholds.pointer_reward_min_regions then
    reward = 1
  end

  if reward > 0 and advanced.pointer_region_count >= thresholds.pointer_reward_min_regions
      and advanced.pointer_region_count <= thresholds.pointer_reward_max_regions
      and not advanced.strong_split_like then
    reward = reward + 1
  end
  if reward > 0 and advanced.has_valid_anchor then
    reward = reward + 1
  end

  -- Reserve higher pointer rewards for layouts with real split support; do not let
  -- scattered or singleton-heavy weak splits ride a few pointer-like fields to the top.
  if advanced.cluster_layout == "scattered" then
    reward = math.min(reward, 1)
  elseif advanced.cluster_layout == "front_tail_split"
      and not two_sided_split_support
      and advanced.dominant_cluster_size <= 2
      and advanced.pointer_alignment_count <= 3
      and pointer_field_count <= 3 then
    reward = math.min(reward, 1)
  elseif advanced.cluster_layout == "anchor_plus_tail_cluster"
      and advanced.pointer_alignment_count <= 3
      and advanced.pointer_region_count <= 2
      and pointer_field_count <= 3
      and advanced.dominant_cluster_size <= 2 then
    reward = math.min(reward, 2)
  end

  if advanced.cluster_layout == "single_blob" and advanced.code_blob_score >= thresholds.heavy_blob_score then
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

  if advanced.cluster_layout == "front_tail_split" or advanced.cluster_layout == "anchor_plus_tail_cluster" then
    if advanced.code_blob_score >= thresholds.mild_blob_score then
      return adjustments.code_blob_penalty_mild
    end
    return 0
  end

  if advanced.cluster_layout == "single_blob"
      or (
        advanced.dominant_cluster_covers_majority
        and advanced.relation_counts.cross_same_page_pairs > 0
      )
      or advanced.f58_in_dense_cluster then
    if advanced.code_blob_score >= thresholds.heavy_blob_score then
      return adjustments.code_blob_penalty_heavy
    end
    if advanced.code_blob_score >= thresholds.medium_blob_score then
      return adjustments.code_blob_penalty_medium
    end
  end

  if advanced.code_blob_score >= thresholds.heavy_blob_score then
    return adjustments.code_blob_penalty_heavy
  end
  if advanced.code_blob_score >= thresholds.medium_blob_score
      or advanced.packed_run_length >= thresholds.packed_run_threshold + 1
      or advanced.monotonic_run_length >= thresholds.monotonic_run_threshold + 1 then
    return adjustments.code_blob_penalty_medium
  end
  if advanced.code_blob_score >= thresholds.mild_blob_score then
    return adjustments.code_blob_penalty_mild
  end
  return 0
end

local function compute_isolated_split_penalty(scored_candidate)
  local adjustments = MVP0.CONFIG.ranking.adjustments
  local advanced = scored_candidate.local_features.advanced_layout
  local penalty_should_fire =
    advanced.cluster_layout == "front_tail_split"
    and advanced.front_non_singleton_cluster_count == 0
    and advanced.tail_non_singleton_cluster_count == 0
    and not advanced.has_valid_anchor
    and (
      advanced.pointer_alignment_count <= 2
      or advanced.pointer_region_count <= 2
    )

  if penalty_should_fire then
    return adjustments.isolated_split_penalty
  end
  return 0
end

local function compute_scalar_block_penalty(scored_candidate)
  local thresholds = MVP0.CONFIG.ranking.thresholds
  local adjustments = MVP0.CONFIG.ranking.adjustments
  local advanced = scored_candidate.local_features.advanced_layout
  local penalty = penalty_from_score(
    advanced.scalar_block_score,
    thresholds.scalar_score_mild,
    thresholds.scalar_score_medium,
    thresholds.scalar_score_heavy,
    adjustments.scalar_block_penalty_mild,
    adjustments.scalar_block_penalty_medium,
    adjustments.scalar_block_penalty_heavy
  )

  if advanced.cluster_layout == "front_tail_split"
      and advanced.front_cluster_count >= 1
      and advanced.tail_cluster_count >= 1 then
    penalty = math.min(penalty, adjustments.scalar_block_penalty_mild)
  elseif advanced.cluster_layout == "anchor_plus_tail_cluster"
      and advanced.tail_cluster_count >= 1
      and advanced.has_valid_anchor then
    penalty = math.min(penalty, adjustments.scalar_block_penalty_mild)
  end

  return penalty
end

local function compute_text_block_penalty(scored_candidate)
  local thresholds = MVP0.CONFIG.ranking.thresholds
  local adjustments = MVP0.CONFIG.ranking.adjustments
  local advanced = scored_candidate.local_features.advanced_layout
  local penalty = penalty_from_score(
    advanced.text_block_score,
    thresholds.text_score_mild,
    thresholds.text_score_medium,
    thresholds.text_score_heavy,
    adjustments.text_block_penalty_mild,
    adjustments.text_block_penalty_medium,
    adjustments.text_block_penalty_heavy
  )

  if advanced.cluster_layout == "front_tail_split"
      and advanced.front_cluster_count >= 1
      and advanced.tail_cluster_count >= 1 then
    penalty = math.min(penalty, adjustments.text_block_penalty_mild)
  elseif advanced.cluster_layout == "anchor_plus_tail_cluster"
      and advanced.tail_cluster_count >= 1
      and advanced.has_valid_anchor then
    penalty = math.min(penalty, adjustments.text_block_penalty_mild)
  end

  return penalty
end

local function compute_clone_penalty(scored_candidate, family_size, context)
  local thresholds = MVP0.CONFIG.ranking.thresholds
  local adjustments = MVP0.CONFIG.ranking.adjustments
  local family_meta = context.clone_family_meta[scored_candidate.clone_family_id] or {}
  local advanced = scored_candidate.local_features.advanced_layout
  local penalty = 0

  if family_size >= thresholds.heavy_family_size then
    penalty = adjustments.clone_penalty_heavy
  elseif family_size >= thresholds.medium_family_size then
    penalty = adjustments.clone_penalty_medium
  elseif family_size >= thresholds.mild_family_size then
    penalty = adjustments.clone_penalty_mild
  end

  if penalty > 0 and (
      family_meta.cluster_layout == "single_blob"
      or family_meta.scalar_bucket == "medium"
      or family_meta.scalar_bucket == "high"
      or family_meta.text_bucket == "medium"
      or family_meta.text_bucket == "high"
    ) then
    penalty = penalty + adjustments.clone_penalty_signature_surcharge
  end

  if penalty > 0
      and family_meta.cluster_layout == "scattered"
      and advanced.pointer_alignment_count <= 2
      and (
        family_size >= thresholds.medium_family_size
        or family_meta.scalar_bucket ~= "0"
        or family_meta.text_bucket ~= "0"
      ) then
    penalty = penalty + adjustments.clone_penalty_signature_surcharge
  end

  return penalty
end

local function compute_strong_structure_bonus(scored_candidate)
  local advanced = scored_candidate.local_features.advanced_layout
  local pointer_field_count = #(advanced.pointer_fields or {})
  local split_layout =
    advanced.cluster_layout == "front_tail_split"
    or advanced.cluster_layout == "anchor_plus_tail_cluster"

  if split_layout
      and advanced.has_valid_anchor
      and advanced.front_non_singleton_cluster_count > 0
      and advanced.tail_non_singleton_cluster_count > 0
      and advanced.pointer_alignment_count >= 5
      and advanced.pointer_region_count >= 3
      and pointer_field_count >= 5 then
    return 1
  end

  return 0
end

local function compute_sparse_anchor_tail_penalty(scored_candidate)
  local advanced = scored_candidate.local_features.advanced_layout
  local pointer_field_count = #(advanced.pointer_fields or {})

  if advanced.cluster_layout == "anchor_plus_tail_cluster"
      and advanced.has_valid_anchor
      and advanced.pointer_alignment_count <= 3
      and advanced.pointer_region_count <= 2
      and pointer_field_count <= 3
      and advanced.dominant_cluster_size <= 2 then
    if advanced.pointer_alignment_count == 3
        and advanced.pointer_region_count == 2
        and pointer_field_count == 3 then
      return 3
    end
    return 2
  end

  return 0
end

local function compute_anchored_fragmented_split_penalty(scored_candidate)
  local advanced = scored_candidate.local_features.advanced_layout
  local pointer_field_count = #(advanced.pointer_fields or {})

  if advanced.cluster_layout == "front_tail_split"
      and advanced.has_valid_anchor
      and advanced.front_non_singleton_cluster_count == 0
      and advanced.tail_non_singleton_cluster_count == 0
      and advanced.dominant_cluster_size <= 1
      and advanced.pointer_alignment_count <= 3
      and pointer_field_count <= 3 then
    if advanced.pointer_region_count <= 3 then
      return 3
    end
    return 2
  end

  return 0
end

function MVP0.compute_one_sided_anchorless_split_penalty(candidate)
  local advanced = candidate.local_features.advanced_layout
  local pointer_field_count = #(advanced.pointer_fields or {})

  if advanced.cluster_layout == "front_tail_split"
      and not advanced.has_valid_anchor
      and advanced.front_non_singleton_cluster_count == 1
      and advanced.tail_non_singleton_cluster_count == 0
      and advanced.dominant_cluster_size == 2
      and advanced.pointer_alignment_count == 3
      and advanced.pointer_region_count == 2
      and pointer_field_count == 3 then
    return 2
  end

  return 0
end

local function compute_scattered_singleton_penalty(scored_candidate, pointer_reward)
  local advanced = scored_candidate.local_features.advanced_layout
  local pointer_field_count = #(advanced.pointer_fields or {})

  -- Suppress scattered, singleton-only pseudo-objects that survive only because
  -- they do not trip any existing split/clone/scalar/text penalties.
  if advanced.cluster_layout == "scattered"
      and advanced.pointer_alignment_count <= 1
      and advanced.pointer_region_count <= 1
      and advanced.dominant_cluster_size <= 1
      and advanced.front_non_singleton_cluster_count == 0
      and advanced.tail_non_singleton_cluster_count == 0
      and pointer_field_count <= 1
      and pointer_reward == 0 then
    return 2
  end

  return 0
end

local function compute_anchored_one_sided_weak_split_penalty(scored_candidate, pointer_reward, strong_structure_bonus)
  local advanced = scored_candidate.local_features.advanced_layout
  local pointer_field_count = #(advanced.pointer_fields or {})
  local one_sided_non_singleton_support =
    (advanced.front_non_singleton_cluster_count > 0 and advanced.tail_non_singleton_cluster_count == 0)
    or (advanced.front_non_singleton_cluster_count == 0 and advanced.tail_non_singleton_cluster_count > 0)

  -- Suppress anchored front-tail splits that only have one-sided non-singleton support
  -- and otherwise only moderate pointer support; these should not sit near robust
  -- two-sided objects even if they retain a small pointer reward.
  if advanced.cluster_layout == "front_tail_split"
      and advanced.has_valid_anchor
      and one_sided_non_singleton_support
      and advanced.dominant_cluster_size <= 2
      and advanced.pointer_alignment_count <= 4
      and advanced.pointer_region_count <= 3
      and pointer_field_count <= 4
      and pointer_reward <= 2
      and strong_structure_bonus == 0 then
    if advanced.pointer_alignment_count <= 3
        and advanced.pointer_region_count <= 2
        and pointer_field_count <= 3
        and pointer_reward <= 1 then
      return 3
    end
    return 2
  end

  return 0
end

function MVP0.apply_rank_adjustments(scored_candidate, context)
  local thresholds = MVP0.CONFIG.ranking.thresholds
  local adjustments = MVP0.CONFIG.ranking.adjustments
  local advanced = scored_candidate.local_features.advanced_layout
  local family_size = context.clone_family_counts[scored_candidate.clone_family_id] or 1
  local pointer_reward = compute_pointer_reward(scored_candidate)
  local strong_structure_bonus = compute_strong_structure_bonus(scored_candidate)
  local sparse_anchor_tail_penalty = compute_sparse_anchor_tail_penalty(scored_candidate)
  local anchored_fragmented_split_penalty = compute_anchored_fragmented_split_penalty(scored_candidate)
  local one_sided_anchorless_split_penalty = MVP0.compute_one_sided_anchorless_split_penalty(scored_candidate)
  local anchored_one_sided_weak_split_penalty =
    compute_anchored_one_sided_weak_split_penalty(scored_candidate, pointer_reward, strong_structure_bonus)
  local scattered_singleton_penalty = compute_scattered_singleton_penalty(scored_candidate, pointer_reward)
  local anchorless_partial_split_penalty = 0
  local isolated_split_penalty = compute_isolated_split_penalty(scored_candidate)
  local code_blob_penalty = compute_code_blob_penalty(scored_candidate)
  local scalar_block_penalty = compute_scalar_block_penalty(scored_candidate)
  local text_block_penalty = compute_text_block_penalty(scored_candidate)
  local clone_penalty = compute_clone_penalty(scored_candidate, family_size, context)
  local mirrored_penalty = 0
  local split_layout =
    advanced.cluster_layout == "front_tail_split"
    or advanced.cluster_layout == "anchor_plus_tail_cluster"
  local two_sided_split_support =
    advanced.front_non_singleton_cluster_count > 0
    and advanced.tail_non_singleton_cluster_count > 0

  if split_layout
      and not advanced.has_valid_anchor
      and not two_sided_split_support
      and (
        advanced.pointer_alignment_count <= 3
        or advanced.pointer_region_count <= 2
      ) then
    anchorless_partial_split_penalty = 1
  end

  if anchorless_partial_split_penalty > 0
      and advanced.cluster_layout == "front_tail_split"
      and advanced.dominant_cluster_size <= 2
      and pointer_reward <= 1
      and advanced.pointer_alignment_count <= 3
      and advanced.pointer_region_count <= 2 then
    anchorless_partial_split_penalty = 2
  end

  if family_size >= thresholds.mirrored_family_repeat_min and advanced.mirrored_pairs >= 2 then
    mirrored_penalty = adjustments.mirrored_penalty
  end

  if pointer_reward > 0 then
    add_flag(scored_candidate, "pointer_balanced")
    add_flag(scored_candidate, "pointer_diverse")
    add_flag(scored_candidate, "coherent_pointer_layout")
  end
  if strong_structure_bonus > 0 then
    add_flag(scored_candidate, "strong_structure_layout")
  end
  if sparse_anchor_tail_penalty > 0 then
    add_flag(scored_candidate, "sparse_anchor_tail_like")
  end
  if anchored_fragmented_split_penalty > 0 then
    add_flag(scored_candidate, "anchored_fragmented_split_like")
  end
  if one_sided_anchorless_split_penalty > 0 then
    add_flag(scored_candidate, "one_sided_anchorless_split_like")
  end
  if anchored_one_sided_weak_split_penalty > 0 then
    add_flag(scored_candidate, "anchored_one_sided_weak_split_like")
  end
  if scattered_singleton_penalty > 0 then
    add_flag(scored_candidate, "scattered_singleton_like")
  end
  if anchorless_partial_split_penalty > 0 then
    add_flag(scored_candidate, "anchorless_partial_split_like")
  end
  if isolated_split_penalty > 0 then
    add_flag(scored_candidate, "isolated_split_like")
  end
  if code_blob_penalty > 0 then
    add_flag(scored_candidate, "code_blob_like")
  end
  if scalar_block_penalty > 0 then
    add_flag(scored_candidate, "scalar_block_like")
  end
  if text_block_penalty > 0 then
    add_flag(scored_candidate, "text_block_like")
  end
  if clone_penalty > 0 then
    add_flag(scored_candidate, "template_clone_family")
  end
  if mirrored_penalty > 0 then
    add_flag(scored_candidate, "mirrored_family_like")
  end

  scored_candidate.pointer_reward = pointer_reward
  scored_candidate.strong_structure_bonus = strong_structure_bonus
  scored_candidate.sparse_anchor_tail_penalty = sparse_anchor_tail_penalty
  scored_candidate.anchored_fragmented_split_penalty = anchored_fragmented_split_penalty
  scored_candidate.one_sided_anchorless_split_penalty = one_sided_anchorless_split_penalty
  scored_candidate.anchorless_partial_split_penalty = anchorless_partial_split_penalty
  scored_candidate.isolated_split_penalty = isolated_split_penalty
  scored_candidate.code_blob_penalty = code_blob_penalty
  scored_candidate.scalar_block_penalty = scalar_block_penalty
  scored_candidate.text_block_penalty = text_block_penalty
  scored_candidate.clone_penalty = clone_penalty
  scored_candidate.mirrored_penalty = mirrored_penalty
  scored_candidate.clone_family_id = scored_candidate.clone_family_id or "pending"
  scored_candidate.template_family_size = family_size
  scored_candidate.pointer_alignment_count = advanced.pointer_alignment_count
  scored_candidate.pointer_region_count = advanced.pointer_region_count
  scored_candidate.pointer_fields = advanced.pointer_like_mask
  scored_candidate.pointer_cluster_count = advanced.pointer_cluster_count
  scored_candidate.front_cluster_count = advanced.front_cluster_count
  scored_candidate.tail_cluster_count = advanced.tail_cluster_count
  scored_candidate.front_non_singleton_cluster_count = advanced.front_non_singleton_cluster_count
  scored_candidate.tail_non_singleton_cluster_count = advanced.tail_non_singleton_cluster_count
  scored_candidate.dominant_cluster_size = advanced.dominant_cluster_size
  scored_candidate.cluster_layout = advanced.cluster_layout
  scored_candidate.has_valid_anchor = advanced.has_valid_anchor
  scored_candidate.dominant_cluster_covers_majority = advanced.dominant_cluster_covers_majority
  scored_candidate.isolated_split_like = advanced.isolated_split_like
  scored_candidate.scalar_block_score = advanced.scalar_block_score
  scored_candidate.text_block_score = advanced.text_block_score

  local adjustment_parts = {}
  if pointer_reward > 0 then
    adjustment_parts[#adjustment_parts + 1] = string.format("+%d pointer_reward", pointer_reward)
  end
  if strong_structure_bonus > 0 then
    adjustment_parts[#adjustment_parts + 1] = string.format("+%d strong_structure_bonus", strong_structure_bonus)
  end
  if sparse_anchor_tail_penalty > 0 then
    adjustment_parts[#adjustment_parts + 1] =
      string.format("-%d sparse_anchor_tail_penalty", sparse_anchor_tail_penalty)
  end
  if anchored_fragmented_split_penalty > 0 then
    adjustment_parts[#adjustment_parts + 1] =
      string.format("-%d anchored_fragmented_split_penalty", anchored_fragmented_split_penalty)
  end
  if one_sided_anchorless_split_penalty > 0 then
    adjustment_parts[#adjustment_parts + 1] =
      string.format("-%d one_sided_anchorless_split_penalty", one_sided_anchorless_split_penalty)
  end
  if anchored_one_sided_weak_split_penalty > 0 then
    adjustment_parts[#adjustment_parts + 1] =
      string.format("-%d anchored_one_sided_weak_split_penalty", anchored_one_sided_weak_split_penalty)
  end
  if scattered_singleton_penalty > 0 then
    adjustment_parts[#adjustment_parts + 1] =
      string.format("-%d scattered_singleton_penalty", scattered_singleton_penalty)
  end
  if anchorless_partial_split_penalty > 0 then
    adjustment_parts[#adjustment_parts + 1] =
      string.format("-%d anchorless_partial_split_penalty", anchorless_partial_split_penalty)
  end
  if isolated_split_penalty > 0 then
    adjustment_parts[#adjustment_parts + 1] =
      string.format("-%d isolated_split_penalty(no_anchor_no_non_singleton_split_support)", isolated_split_penalty)
  end
  if code_blob_penalty > 0 then
    adjustment_parts[#adjustment_parts + 1] = string.format("-%d code_blob_penalty", code_blob_penalty)
  end
  if scalar_block_penalty > 0 then
    adjustment_parts[#adjustment_parts + 1] = string.format("-%d scalar_block_penalty", scalar_block_penalty)
  end
  if text_block_penalty > 0 then
    adjustment_parts[#adjustment_parts + 1] = string.format("-%d text_block_penalty", text_block_penalty)
  end
  if clone_penalty > 0 then
    adjustment_parts[#adjustment_parts + 1] = string.format("-%d clone_penalty", clone_penalty)
  end
  if mirrored_penalty > 0 then
    adjustment_parts[#adjustment_parts + 1] = string.format("-%d mirrored_penalty", mirrored_penalty)
  end

  scored_candidate.total_adjustment =
    pointer_reward
    + strong_structure_bonus
    - sparse_anchor_tail_penalty
    - anchored_fragmented_split_penalty
    - one_sided_anchorless_split_penalty
    - anchored_one_sided_weak_split_penalty
    - scattered_singleton_penalty
    - anchorless_partial_split_penalty
    - isolated_split_penalty
    - code_blob_penalty
    - scalar_block_penalty
    - text_block_penalty
    - clone_penalty
    - mirrored_penalty
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
    "final=%d|family=%d|pointer=%d|isolated=%d|blob=%d|scalar=%d|text=%d|clone=%d|mirror=%d|neg=%d|addr=%s",
    scored_candidate.final_score,
    family_size,
    pointer_reward,
    isolated_split_penalty,
    code_blob_penalty,
    scalar_block_penalty,
    text_block_penalty,
    clone_penalty,
    mirrored_penalty,
    negative_count,
    hex_u64(scored_candidate.candidate.value_addr)
  )

  local rank_reasons = {}
  if pointer_reward > 0 then
    rank_reasons[#rank_reasons + 1] =
      string.format("pointer reward favored %s cluster layout", advanced.cluster_layout)
  end
  if strong_structure_bonus > 0 then
    rank_reasons[#rank_reasons + 1] =
      "strong structure bonus favored anchored two-sided split layout with dense pointer support"
  end
  if sparse_anchor_tail_penalty > 0 then
    rank_reasons[#rank_reasons + 1] =
      "sparse anchor-plus-tail penalty fired on weak anchor-plus-tail layout with only sparse pointer support"
  end
  if anchored_fragmented_split_penalty > 0 then
    rank_reasons[#rank_reasons + 1] =
      "anchored fragmented split penalty fired on singleton-only split layout despite valid anchor"
  end
  if one_sided_anchorless_split_penalty > 0 then
    rank_reasons[#rank_reasons + 1] =
      "one-sided anchorless split penalty fired on weak front-tail split with only one-sided support"
  end
  if anchored_one_sided_weak_split_penalty > 0 then
    rank_reasons[#rank_reasons + 1] =
      "anchored one-sided weak split penalty fired on anchored front-tail split with only one-sided non-singleton support and weak pointer support"
  end
  if scattered_singleton_penalty > 0 then
    rank_reasons[#rank_reasons + 1] =
      "scattered singleton penalty fired on pointer-poor scattered layout with no non-singleton support"
  end
  if anchorless_partial_split_penalty > 0 then
    rank_reasons[#rank_reasons + 1] =
      "anchorless partial split penalty fired on one-sided split layout without valid anchor"
  end
  if isolated_split_penalty > 0 then
    rank_reasons[#rank_reasons + 1] =
      "isolated split penalty fired on fragmentary split layout with no valid anchor and no non-singleton split support"
  end
  if code_blob_penalty > 0 then
    if advanced.cluster_layout == "front_tail_split" or advanced.cluster_layout == "anchor_plus_tail_cluster" then
      rank_reasons[#rank_reasons + 1] = "blob penalty capped at mild by split-cluster safeguard"
    else
      rank_reasons[#rank_reasons + 1] = "blob penalty fired on dominant dense layout"
    end
  end
  if scalar_block_penalty > 0 then
    rank_reasons[#rank_reasons + 1] = "scalar penalty fired on float-like/scalar template"
  end
  if text_block_penalty > 0 then
    rank_reasons[#rank_reasons + 1] = "text penalty fired on little-endian ASCII/UTF16-like chunks"
  end
  if clone_penalty > 0 then
    if advanced.cluster_layout == "scattered" and advanced.pointer_alignment_count <= 2 then
      rank_reasons[#rank_reasons + 1] =
        "family size " .. tostring(family_size) .. " raised clone penalty on scattered pointer-poor family"
    else
      rank_reasons[#rank_reasons + 1] = "family size " .. tostring(family_size) .. " raised clone penalty"
    end
  end
  if mirrored_penalty > 0 then
    rank_reasons[#rank_reasons + 1] = "mirrored family surcharge applied"
  end
  if #rank_reasons == 0 then
    rank_reasons[1] = "rank follows base_score with no extra adjustments"
  elseif scored_candidate.total_adjustment == 0 then
    rank_reasons[#rank_reasons + 1] = "net final adjustments cancel to zero"
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
  if a.isolated_split_penalty ~= b.isolated_split_penalty then
    return a.isolated_split_penalty < b.isolated_split_penalty
  end
  if a.code_blob_penalty ~= b.code_blob_penalty then
    return a.code_blob_penalty < b.code_blob_penalty
  end
  if a.scalar_block_penalty ~= b.scalar_block_penalty then
    return a.scalar_block_penalty < b.scalar_block_penalty
  end
  if a.text_block_penalty ~= b.text_block_penalty then
    return a.text_block_penalty < b.text_block_penalty
  end
  if a.clone_penalty ~= b.clone_penalty then
    return a.clone_penalty < b.clone_penalty
  end
  if a.mirrored_penalty ~= b.mirrored_penalty then
    return a.mirrored_penalty < b.mirrored_penalty
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

  local function read_field_u32(field_name, field_addr)
    local value = read_u32(field_addr)
    if type(value) ~= "number" then
      log_field_guard(c.value_addr, field_name, value, "read_u32", "unreadable_or_nil")
      return nil
    end
    return value
  end

  local function read_field_f32(field_name, field_addr)
    local value = read_f32(field_addr)
    if value == nil then
      log_field_guard(c.value_addr, field_name, value, "read_f32", "unreadable_or_nil")
      return nil
    end
    return value
  end

  c.f08 = read_field_u32("f08", c.base_addr + off.f08)
  c.f18 = read_field_u32("f18", c.base_addr + off.f18)
  c.f20 = read_field_u32("f20", c.base_addr + off.f20)
  c.f28 = read_field_u32("f28", c.base_addr + off.f28)
  c.f58 = read_field_u32("f58", c.base_addr + off.f58)
  c.f68 = read_field_u32("f68", c.base_addr + off.f68)
  c.f70 = read_field_u32("f70", c.base_addr + off.f70)
  c.f78 = read_field_u32("f78", c.base_addr + off.f78)
  c.f28_float = read_field_f32("f28_float", c.base_addr + off.f28)

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
  if best.scalar_block_penalty > 0 then
    add_reason("best candidate triggered scalar-block penalty " .. tostring(best.scalar_block_penalty))
  end
  if best.text_block_penalty > 0 then
    add_reason("best candidate triggered text-block penalty " .. tostring(best.text_block_penalty))
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
      and best.scalar_block_penalty == 0
      and best.text_block_penalty == 0
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
  local final_decision = recommendation or rank.final_decision
  local summary_confidence = final_decision and final_decision.confidence or rank.confidence
  local summary_manual_review = final_decision and final_decision.manual_review_required or rank.manual_review
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
  table.insert(lines, "Confidence: " .. tostring(summary_confidence))
  table.insert(lines, "Manual review: " .. tostring(summary_manual_review))
  table.insert(lines, "=======================")
  table.insert(lines, "")

  if final_decision then
    table.insert(lines, "=== Recommendation ===")
    table.insert(lines, "Recommendation: " .. final_decision.recommendation)
    table.insert(lines, "Confidence: " .. tostring(final_decision.confidence))
    table.insert(lines, "Manual review required: " .. tostring(final_decision.manual_review_required))
    if final_decision.recommended_candidate then
      table.insert(lines, "Recommended value addr: " .. hex_u64(final_decision.recommended_candidate.candidate.value_addr))
      table.insert(lines, "Recommended base addr : " .. hex_u64(final_decision.recommended_candidate.candidate.base_addr))
      table.insert(lines, "Recommended score     : " .. tostring(final_decision.recommended_candidate.score))
    end
    if #final_decision.rationale > 0 then
      table.insert(lines, "Rationale: " .. table.concat(final_decision.rationale, "; "))
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
    table.insert(lines, "scalar_block_score = " .. tostring(scored_candidate.scalar_block_score))
    table.insert(lines, "scalar_block_penalty = " .. tostring(scored_candidate.scalar_block_penalty))
    table.insert(lines, "text_block_score = " .. tostring(scored_candidate.text_block_score))
    table.insert(lines, "text_block_penalty = " .. tostring(scored_candidate.text_block_penalty))
    table.insert(lines, "template_family_id = " .. tostring(scored_candidate.template_family_id))
    table.insert(lines, "clone_family_id = " .. tostring(scored_candidate.clone_family_id))
    table.insert(lines, "template_family_size = " .. tostring(scored_candidate.template_family_size))
    table.insert(lines, "clone_penalty = " .. tostring(scored_candidate.clone_penalty))
    table.insert(lines, "mirrored_penalty = " .. tostring(scored_candidate.mirrored_penalty))
    table.insert(lines, "pointer_reward = " .. tostring(scored_candidate.pointer_reward))
    table.insert(lines, "strong_structure_bonus = " .. tostring(scored_candidate.strong_structure_bonus or 0))
    table.insert(lines, "sparse_anchor_tail_penalty = " .. tostring(scored_candidate.sparse_anchor_tail_penalty or 0))
    table.insert(lines, "anchored_fragmented_split_penalty = " .. tostring(scored_candidate.anchored_fragmented_split_penalty or 0))
    table.insert(lines, "one_sided_anchorless_split_penalty = " .. tostring(scored_candidate.one_sided_anchorless_split_penalty or 0))
    table.insert(lines, "anchorless_partial_split_penalty = " .. tostring(scored_candidate.anchorless_partial_split_penalty or 0))
    table.insert(lines, "isolated_split_penalty = " .. tostring(scored_candidate.isolated_split_penalty))
    table.insert(lines, "pointer_alignment_count = " .. tostring(scored_candidate.pointer_alignment_count))
    table.insert(lines, "pointer_region_count = " .. tostring(scored_candidate.pointer_region_count))
    table.insert(lines, "pointer_fields = " .. tostring(scored_candidate.pointer_fields))
    table.insert(lines, "pointer_cluster_count = " .. tostring(scored_candidate.pointer_cluster_count))
    table.insert(lines, "front_cluster_count = " .. tostring(scored_candidate.front_cluster_count))
    table.insert(lines, "tail_cluster_count = " .. tostring(scored_candidate.tail_cluster_count))
    table.insert(lines, "front_non_singleton_cluster_count = " .. tostring(scored_candidate.front_non_singleton_cluster_count))
    table.insert(lines, "tail_non_singleton_cluster_count = " .. tostring(scored_candidate.tail_non_singleton_cluster_count))
    table.insert(lines, "dominant_cluster_size = " .. tostring(scored_candidate.dominant_cluster_size))
    table.insert(lines, "cluster_layout = " .. tostring(scored_candidate.cluster_layout))
    table.insert(lines, "has_valid_anchor = " .. tostring(scored_candidate.has_valid_anchor))
    table.insert(lines, "dominant_cluster_covers_majority = " .. tostring(scored_candidate.dominant_cluster_covers_majority))
    table.insert(lines, "isolated_split_like = " .. tostring(scored_candidate.isolated_split_like))
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
  ranked.final_decision = ranked.recommendation
  ranked.report_text = MVP0.render_report(ranked, input_payload, ranked.recommendation)
  return ranked
end

_G.MVP0 = MVP0
return MVP0
