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
-- })
--
-- print(bundle.result.report_text)

local MVP0FoundList = {}

MVP0FoundList.CONFIG = {
  default_max_candidates = 20,
  default_scan_budget = 2000,
  default_filter_target_match = true,
}

local function assert_mvp0_loaded()
  if type(MVP0) ~= 'table' or type(MVP0.make_input) ~= 'function' or type(MVP0.run) ~= 'function' then
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

local function collect_raw_foundlist_addresses(scan_budget)
  local memscan = getCurrentMemscan()
  if memscan == nil then
    error('No active memscan was found. Run a Cheat Engine scan first.')
  end

  local foundlist = createFoundList(memscan)
  foundlist.initialize()

  local addresses = {}
  local total = foundlist.Count
  local count = total

  if scan_budget ~= nil then
    count = math.min(total, scan_budget)
  end

  for i = 0, count - 1 do
    table.insert(addresses, to_address_number(foundlist.Address[i]))
  end

  foundlist.destroy()

  return addresses, total
end

local function dedupe_addresses(addresses)
  local seen = {}
  local unique = {}

  for _, addr in ipairs(addresses) do
    if not seen[addr] then
      seen[addr] = true
      table.insert(unique, addr)
    end
  end

  return unique
end

local function filter_target_match(addresses, target_value_pattern)
  local filtered = {}

  for _, addr in ipairs(addresses) do
    local ok, value = pcall(read_u32, addr)
    if ok and value == target_value_pattern then
      table.insert(filtered, addr)
    end
  end

  return filtered
end

local function select_evenly(addresses, wanted_count)
  if wanted_count == nil or wanted_count <= 0 or #addresses <= wanted_count then
    return addresses
  end

  if wanted_count == 1 then
    return { addresses[1] }
  end

  local selected = {}
  local last_index = 0

  for slot = 1, wanted_count do
    local ratio = (slot - 1) / (wanted_count - 1)
    local index = math.floor(ratio * (#addresses - 1)) + 1

    if index <= last_index then
      index = last_index + 1
    end
    if index > #addresses then
      index = #addresses
    end

    table.insert(selected, addresses[index])
    last_index = index
  end

  return selected
end

local function sort_numeric(addresses)
  table.sort(addresses, function(a, b)
    return a < b
  end)
  return addresses
end

function MVP0FoundList.collect(opts)
  assert_mvp0_loaded()

  opts = opts or {}
  local max_candidates = opts.max_candidates or MVP0FoundList.CONFIG.default_max_candidates
  local scan_budget = opts.scan_budget
  local target_value_pattern = u32(opts.target_value_pattern)
  local should_filter = opts.filter_target_match

  if scan_budget == nil then
    scan_budget = MVP0FoundList.CONFIG.default_scan_budget
  end

  if should_filter == nil then
    should_filter = MVP0FoundList.CONFIG.default_filter_target_match
  end

  if target_value_pattern == nil then
    error('target_value_pattern is required.')
  end

  local raw_addresses, raw_count = collect_raw_foundlist_addresses(scan_budget)
  local unique_addresses = dedupe_addresses(raw_addresses)
  local filtered_addresses = unique_addresses

  if should_filter then
    filtered_addresses = filter_target_match(unique_addresses, target_value_pattern)
  end

  local sorted_addresses = sort_numeric(filtered_addresses)
  local selected_addresses = select_evenly(sorted_addresses, max_candidates)

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