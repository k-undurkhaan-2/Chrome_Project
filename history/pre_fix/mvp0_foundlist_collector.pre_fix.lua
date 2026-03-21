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
  default_bucket_shift = 20,      -- 1 MiB-ish region buckets
  default_max_per_bucket = 3,
  default_probe_full_foundlist = true,
  default_probe_window_radius = 256,
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

local function collect_windowed_raw_foundlist_addresses(foundlist, total, wanted, known_true_addr, probe_window_radius)
  local probe_logs = {}
  local true_in_raw = false
  local true_in_full_foundlist = false
  local true_index = find_known_true_index(foundlist, total, known_true_addr)
  local indices = {}
  local used = {}

  if true_index ~= nil then
    true_in_full_foundlist = true
    append_probe_log(probe_logs, 'full_foundlist', string.format('known_true_addr found at full index %d', true_index))
  elseif known_true_addr ~= nil then
    append_probe_log(probe_logs, 'full_foundlist', 'known_true_addr not found in full foundlist')
  end

  local spread_indices = collect_even_spread_indices(total, wanted)
  for _, idx in ipairs(spread_indices) do
    if not used[idx] then
      used[idx] = true
      indices[#indices + 1] = idx
    end
  end

  if true_index ~= nil and not used[true_index] then
    local radius = probe_window_radius or MVP0FoundList.CONFIG.default_probe_window_radius
    local start_idx = math.max(0, true_index - radius)
    local end_idx = math.min(total - 1, true_index + radius)
    append_probe_log(probe_logs, 'raw', string.format(
      'known_true_addr was not admitted by even-spread raw sampling; injecting probe window [%d, %d] around true index',
      start_idx, end_idx
    ))

    for idx = start_idx, end_idx do
      if #indices >= wanted then
        break
      end
      if not used[idx] then
        used[idx] = true
        indices[#indices + 1] = idx
      end
    end

    if not used[true_index] and #indices >= wanted then
      append_probe_log(probe_logs, 'raw', 'probe window could not admit known_true_addr because raw budget was already saturated')
    end
  elseif true_index ~= nil then
    append_probe_log(probe_logs, 'raw', 'known_true_addr already admitted by even-spread raw sampling')
  end

  table.sort(indices)

  local addresses = {}
  for _, idx in ipairs(indices) do
    local addr = to_address_number(foundlist.Address[idx])
    if known_true_addr ~= nil and addr == known_true_addr then
      true_in_raw = true
    end
    addresses[#addresses + 1] = addr
  end

  if known_true_addr ~= nil then
    if true_in_raw then
      append_probe_log(probe_logs, 'raw', 'known_true_addr admitted into raw set')
    else
      append_probe_log(probe_logs, 'raw', 'known_true_addr still missing from raw set after probe-window admission')
    end
  end

  return addresses, true_in_raw, true_in_full_foundlist, probe_logs, true_index
end

local function collect_raw_foundlist_addresses(scan_budget, known_true_addr, probe_full_foundlist, probe_window_radius)
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
  local probe_logs = {}
  local true_index = nil

  if total == 0 then
    foundlist.destroy()
    return addresses, 0, true_in_raw, true_in_full_foundlist, probe_logs, true_index
  end

  local wanted = total
  if scan_budget ~= nil then
    wanted = math.min(total, scan_budget)
  end

  if wanted <= 0 then
    foundlist.destroy()
    if known_true_addr ~= nil then
      append_probe_log(probe_logs, 'raw', 'scan_budget <= 0, raw admission skipped')
    end
    return addresses, total, true_in_raw, true_in_full_foundlist, probe_logs, true_index
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
  else
    addresses, true_in_raw, true_in_full_foundlist, probe_logs, true_index =
      collect_windowed_raw_foundlist_addresses(foundlist, total, wanted, known_true_addr, probe_window_radius)

    if not probe_full_foundlist and known_true_addr ~= nil and true_index == nil then
      append_probe_log(probe_logs, 'full_foundlist', 'probe_full_foundlist disabled, full-foundlist truth probe skipped')
    end
  end

  foundlist.destroy()
  return addresses, total, true_in_raw, true_in_full_foundlist, probe_logs, true_index
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

  if target_value_pattern == nil then
    error('target_value_pattern is required.')
  end

  local raw_addresses, raw_count, true_in_raw, true_in_full_foundlist, truth_probe_logs, true_foundlist_index =
    collect_raw_foundlist_addresses(scan_budget, known_true_addr, probe_full_foundlist, probe_window_radius)
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
    selected_addresses, prescored_count, prescore_cutoff_score, prescore_tied_count, true_in_prescored, true_in_selected =
      select_top_scored_diverse(sorted_addresses, max_candidates, target_value_pattern, bucket_shift, max_per_bucket, known_true_addr)
    selection_strategy = 'prescore_diverse_top_scored'
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
    known_true_addr = known_true_addr,
    true_foundlist_index = true_foundlist_index,
    probe_window_radius = probe_window_radius,
    truth_probe_logs = truth_probe_logs,
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
