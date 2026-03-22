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

MVP0FoundList.CONFIG = {
  default_max_candidates = 20,
  default_scan_budget = 2000,
  default_filter_target_match = true,
  default_use_prescore_selection = true,
  default_bucket_shift = 20,      -- ~1 MiB buckets
  default_max_per_bucket = 3,
  default_probe_full_foundlist = true,
  default_layer1_min_score = 39,
  default_layer2_min_score = 30,
  default_layer1_quota_ratio = 0.40,
  default_layer2_quota_ratio = 0.40,
}

local function assert_mvp0_loaded()
  if type(MVP0) ~= 'table'
    or type(MVP0.make_input) ~= 'function'
    or type(MVP0.run) ~= 'function'
    or type(MVP0.score_candidate) ~= 'function'
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

local function read_u32(addr)
  return u32(readInteger(addr))
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

local function flags_to_set(flags)
  local set = {}
  if type(flags) == 'table' then
    for _, flag in ipairs(flags) do
      set[flag] = true
    end
  end
  return set
end

local function collect_raw_foundlist_addresses(scan_budget, known_true_addr, probe_full_foundlist)
  local memscan = getCurrentMemscan()
  if memscan == nil then
    error('No active memscan was found. Run a Cheat Engine scan first.')
  end

  local foundlist = createFoundList(memscan)
  foundlist.initialize()

  local addresses = {}
  local total = foundlist.Count
  local true_in_raw = false
  local true_in_full_foundlist = false

  if total == 0 then
    foundlist.destroy()
    return addresses, 0, true_in_raw, true_in_full_foundlist
  end

  local wanted = total
  if scan_budget ~= nil then
    wanted = math.min(total, scan_budget)
  end

  if wanted <= 0 then
    foundlist.destroy()
    return addresses, total, true_in_raw, true_in_full_foundlist
  end

  if wanted >= total then
    for i = 0, total - 1 do
      local addr = to_address_number(foundlist.Address[i])
      if known_true_addr ~= nil and addr == known_true_addr then
        true_in_raw = true
        true_in_full_foundlist = true
      end
      table.insert(addresses, addr)
    end
  else
    local used = {}
    for slot = 1, wanted do
      local ratio = (slot - 1) / math.max(wanted - 1, 1)
      local index = math.floor(ratio * (total - 1))
      if used[index] == nil then
        used[index] = true
        local addr = to_address_number(foundlist.Address[index])
        if known_true_addr ~= nil and addr == known_true_addr then
          true_in_raw = true
        end
        table.insert(addresses, addr)
      end
    end

    if probe_full_foundlist and known_true_addr ~= nil then
      for i = 0, total - 1 do
        local addr = to_address_number(foundlist.Address[i])
        if addr == known_true_addr then
          true_in_full_foundlist = true
          break
        end
      end
    end
  end

  foundlist.destroy()
  return addresses, total, true_in_raw, true_in_full_foundlist
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

local function filter_target_match(addresses, target_value_pattern, known_true_addr)
  local filtered = {}
  local true_in_filtered = false

  for _, addr in ipairs(addresses) do
    local ok, value = pcall(read_u32, addr)
    if ok and value == target_value_pattern then
      if known_true_addr ~= nil and addr == known_true_addr then
        true_in_filtered = true
      end
      table.insert(filtered, addr)
    end
  end

  return filtered, true_in_filtered
end

local function sort_numeric(addresses)
  table.sort(addresses, function(a, b)
    return a < b
  end)
  return addresses
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
  local pool = {}
  local true_in_prescored = false

  for _, value_addr in ipairs(addresses) do
    local ok, candidate = pcall(MVP0.build_candidate, value_addr)
    if ok and candidate ~= nil then
      local score_result = MVP0.score_candidate(candidate, target_value_pattern)
      local flag_set = flags_to_set(score_result.flags)
      local item = {
        addr = value_addr,
        score = score_result.score,
        hard_pass = score_result.hard_pass,
        flags = score_result.flags,
        flag_set = flag_set,
        candidate = candidate,
      }
      if known_true_addr ~= nil and value_addr == known_true_addr then
        true_in_prescored = true
      end
      table.insert(pool, item)
    end
  end

  table.sort(pool, function(a, b)
    if a.score == b.score then
      return a.addr < b.addr
    end
    return a.score > b.score
  end)

  return pool, true_in_prescored
end

local function append_diverse_from_pool(selected, selected_map, bucket_counts, pool, quota, bucket_shift, max_per_bucket, known_true_addr)
  local true_in_selected = false
  local added = 0

  for _, item in ipairs(pool) do
    if added >= quota then
      break
    end

    if not selected_map[item.addr] then
      local bucket = region_bucket(item.addr, bucket_shift)
      local count = bucket_counts[bucket] or 0
      if count < max_per_bucket then
        bucket_counts[bucket] = count + 1
        selected_map[item.addr] = true
        table.insert(selected, item.addr)
        added = added + 1
        if known_true_addr ~= nil and item.addr == known_true_addr then
          true_in_selected = true
        end
      end
    end
  end

  return added, true_in_selected
end

local function append_fill_from_pool(selected, selected_map, pool, wanted_count, known_true_addr)
  local true_in_selected = false

  for _, item in ipairs(pool) do
    if #selected >= wanted_count then
      break
    end

    if not selected_map[item.addr] then
      selected_map[item.addr] = true
      table.insert(selected, item.addr)
      if known_true_addr ~= nil and item.addr == known_true_addr then
        true_in_selected = true
      end
    end
  end

  return true_in_selected
end

local function classify_layers(scored_pool, cfg)
  local layer1 = {}
  local layer2 = {}
  local layer3 = {}

  for _, item in ipairs(scored_pool) do
    local fs = item.flag_set
    local object_like = fs['object_like'] == true
    local float_block_like = fs['float_block_like'] == true

    if item.score >= cfg.layer1_min_score and object_like and not float_block_like then
      table.insert(layer1, item)
    elseif item.score >= cfg.layer2_min_score then
      table.insert(layer2, item)
    else
      table.insert(layer3, item)
    end
  end

  return layer1, layer2, layer3
end

local function select_layered_diverse(scored_pool, wanted_count, cfg, known_true_addr)
  if wanted_count == nil or wanted_count <= 0 or #scored_pool <= wanted_count then
    local selected = {}
    local true_in_selected = false
    for _, item in ipairs(scored_pool) do
      table.insert(selected, item.addr)
      if known_true_addr ~= nil and item.addr == known_true_addr then
        true_in_selected = true
      end
    end
    return selected, nil, nil, true_in_selected
  end

  local layer1, layer2, layer3 = classify_layers(scored_pool, cfg)
  local q1 = math.floor(wanted_count * cfg.layer1_quota_ratio)
  local q2 = math.floor(wanted_count * cfg.layer2_quota_ratio)
  local q3 = wanted_count - q1 - q2

  local selected = {}
  local selected_map = {}
  local bucket_counts = {}
  local true_in_selected = false

  local _, hit1 = append_diverse_from_pool(selected, selected_map, bucket_counts, layer1, q1, cfg.bucket_shift, cfg.max_per_bucket, known_true_addr)
  local _, hit2 = append_diverse_from_pool(selected, selected_map, bucket_counts, layer2, q2, cfg.bucket_shift, cfg.max_per_bucket, known_true_addr)
  local _, hit3 = append_diverse_from_pool(selected, selected_map, bucket_counts, layer3, q3, cfg.bucket_shift, cfg.max_per_bucket, known_true_addr)
  true_in_selected = hit1 or hit2 or hit3

  if #selected < wanted_count then
    local all_pools = { layer1, layer2, layer3 }
    for _, pool in ipairs(all_pools) do
      local hit_fill = append_fill_from_pool(selected, selected_map, pool, wanted_count, known_true_addr)
      true_in_selected = true_in_selected or hit_fill
      if #selected >= wanted_count then
        break
      end
    end
  end

  local cutoff_score = nil
  local tied_count = nil
  if #selected > 0 then
    local cutoff_addr = selected[#selected]
    for _, item in ipairs(scored_pool) do
      if item.addr == cutoff_addr then
        cutoff_score = item.score
        break
      end
    end
    if cutoff_score ~= nil then
      tied_count = 0
      for _, item in ipairs(scored_pool) do
        if item.score == cutoff_score then
          tied_count = tied_count + 1
        end
      end
    end
  end

  return selected, cutoff_score, tied_count, true_in_selected
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
  local layer1_min_score = opts.layer1_min_score or MVP0FoundList.CONFIG.default_layer1_min_score
  local layer2_min_score = opts.layer2_min_score or MVP0FoundList.CONFIG.default_layer2_min_score
  local layer1_quota_ratio = opts.layer1_quota_ratio or MVP0FoundList.CONFIG.default_layer1_quota_ratio
  local layer2_quota_ratio = opts.layer2_quota_ratio or MVP0FoundList.CONFIG.default_layer2_quota_ratio

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

  if target_value_pattern == nil then
    error('target_value_pattern is required.')
  end

  local raw_addresses, raw_count, true_in_raw, true_in_full_foundlist =
    collect_raw_foundlist_addresses(scan_budget, known_true_addr, probe_full_foundlist)

  local unique_addresses, true_in_unique = dedupe_addresses(raw_addresses, known_true_addr)

  local filtered_addresses = unique_addresses
  local true_in_filtered = true_in_unique

  if should_filter then
    filtered_addresses, true_in_filtered = filter_target_match(unique_addresses, target_value_pattern, known_true_addr)
  end

  local sorted_addresses = sort_numeric(filtered_addresses)

  local selected_addresses
  local prescored_count = nil
  local selection_strategy = nil
  local prescore_cutoff_score = nil
  local prescore_tied_count = nil
  local true_in_prescored = false
  local true_in_selected = false

  if use_prescore_selection and #sorted_addresses > 0 then
    local scored_pool
    scored_pool, true_in_prescored = build_scored_pool(sorted_addresses, target_value_pattern, known_true_addr)
    prescored_count = #scored_pool

    selected_addresses, prescore_cutoff_score, prescore_tied_count, true_in_selected =
      select_layered_diverse(scored_pool, max_candidates, {
        bucket_shift = bucket_shift,
        max_per_bucket = max_per_bucket,
        layer1_min_score = layer1_min_score,
        layer2_min_score = layer2_min_score,
        layer1_quota_ratio = layer1_quota_ratio,
        layer2_quota_ratio = layer2_quota_ratio,
      }, known_true_addr)

    selection_strategy = 'prescore_layered_diverse'
  else
    selected_addresses, true_in_selected = select_evenly(sorted_addresses, max_candidates, known_true_addr)
    selection_strategy = 'evenly_spread'
    true_in_prescored = false
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
    layer1_min_score = layer1_min_score,
    layer2_min_score = layer2_min_score,
    layer1_quota_ratio = layer1_quota_ratio,
    layer2_quota_ratio = layer2_quota_ratio,
    known_true_addr = known_true_addr,
    true_in_full_foundlist = true_in_full_foundlist,
    true_in_raw = true_in_raw,
    true_in_unique = true_in_unique,
    true_in_filtered = true_in_filtered,
    true_in_prescored = true_in_prescored,
    true_in_selected = true_in_selected,
  }
end

function MVP0FoundList.build_input(opts)
  local collected = MVP0FoundList.collect(opts)
  collected.input = MVP0.make_input(collected.candidate_value_addrs, collected.target_value_pattern, {
    target_value_float = opts and opts.target_value_float,
    session_id = opts and opts.session_id,
  })
  return collected
end

function MVP0FoundList.run(opts)
  local bundle = MVP0FoundList.build_input(opts)
  bundle.result = MVP0.run(bundle.input)
  return bundle
end

_G.MVP0FoundList = MVP0FoundList
return MVP0FoundList