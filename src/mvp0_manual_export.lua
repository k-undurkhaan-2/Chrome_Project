-- SPDX-License-Identifier: GPL-3.0-only
-- Manual read-only CE export: dofile(absolute_path).export(). Loading is inert.
local M = {}
local module_path = debug.getinfo(1, 'S').source:sub(2):gsub('\\', '/')
local root = module_path:match('^(.*)/src/[^/]+$')
local OFFSETS = {-0x20, -0x10, -8, 0, 0x30, 0x40, 0x48, 0x50}
local MAX_ADDR = 2^53 - 1
local serial = 0

local function check(ok, message)
  if not ok then error('EXPORT_FAILED: ' .. message, 0) end
end

local function plain(t)
  return type(t) == 'table' and getmetatable(t) == nil
end

local function integer(n, low, high)
  return type(n) == 'number' and n == n and n % 1 == 0 and n >= low and n <= high
end

local function fields(t, allowed)
  check(plain(t), 'plain data table required')
  for k in pairs(t) do check(allowed[k], 'unsupported data field: ' .. tostring(k)) end
end

local function dense(t)
  check(plain(t), 'plain population array required')
  local n = 0
  for k in pairs(t) do
    n = n + 1
    check(integer(k, 1, #t), 'sparse population')
  end
  check(n == #t, 'sparse population')
  return n
end

local function copy_data(value, active)
  if type(value) ~= 'table' then
    check(type(value) == 'string' or type(value) == 'boolean' or type(value) == 'number',
      'non-data snapshot value')
    return value
  end
  check(plain(value) and not active[value], 'metatable or cyclic snapshot')
  active[value] = true
  local result = {}
  for key, item in pairs(value) do
    check(type(key) == 'string' or type(key) == 'number', 'non-data snapshot key')
    result[key] = copy_data(item, active)
  end
  active[value] = nil
  return result
end

local function unchanged(source, frozen)
  if type(source) ~= 'table' then return source == frozen end
  if not plain(source) or not plain(frozen) then return false end
  for key, value in pairs(frozen) do
    if not unchanged(rawget(source, key), value) then return false end
  end
  for key in pairs(source) do if frozen[key] == nil then return false end end
  return true
end

local function quote(s)
  check(utf8.len(s) ~= nil, 'invalid UTF-8')
  return '"' .. s:gsub('[%z\1-\31\\"]', function(c)
    return string.format('\\u%04x', c:byte())
  end) .. '"'
end

-- All tables here are JSON objects. The population is streamed as JSONL;
-- numeric word-map keys become decimal object keys, restored by the loader.
local function json(v)
  if type(v) == 'string' then return quote(v) end
  if type(v) == 'boolean' then return tostring(v) end
  if type(v) == 'number' then
    check(v == v and math.abs(v) < math.huge, 'nonfinite number')
    if v % 1 == 0 then return string.format('%.0f', v) end
    return (string.format('%.17g', v):gsub(',', '.'))
  end
  check(plain(v), 'non-data value')
  local keys, out = {}, {}
  for k in pairs(v) do keys[#keys + 1] = k end
  table.sort(keys, function(a, b) return tostring(a) < tostring(b) end)
  for _, k in ipairs(keys) do
    local key = type(k) == 'number' and string.format('%.0f', k) or k
    out[#out + 1] = quote(key) .. ':' .. json(v[k])
  end
  return '{' .. table.concat(out, ',') .. '}'
end

local function validate_options(o)
  fields(o, {population_mode=true, scan_budget=true, max_candidates=true,
    target_value_pattern=true, target_value_float=true, session_id=true,
    filter_target_match=true, use_prescore_selection=true})
  check(o.target_value_pattern == nil or integer(o.target_value_pattern, 0, 0xFFFFFFFF),
    'invalid target_value_pattern')
  check(o.target_value_float == nil or (type(o.target_value_float) == 'number'
    and o.target_value_float == o.target_value_float and math.abs(o.target_value_float) < math.huge),
    'invalid target_value_float')
  check(o.session_id == nil or type(o.session_id) == 'string', 'invalid session_id')
  for _, k in ipairs({'filter_target_match', 'use_prescore_selection'}) do
    check(o[k] == nil or o[k] == true, 'invalid ' .. k)
  end
  check(o.population_mode == nil or o.population_mode == 'bounded'
    or o.population_mode == 'full', 'invalid population_mode')
  if o.population_mode == 'full' then
    check(o.scan_budget == nil and o.max_candidates == nil, 'full mode forbids budgets')
  else
    local scan, candidates = o.scan_budget or 2000, o.max_candidates or 20
    check(o.scan_budget == nil or integer(o.scan_budget, 1, 65536), 'invalid scan_budget')
    check(o.max_candidates == nil or integer(o.max_candidates, 1, 128), 'invalid max_candidates')
    check(candidates <= scan, 'inconsistent budgets')
  end
end

local function same_map(a, b)
  if a == nil or b == nil then return a == b end
  for k, v in pairs(a) do if b[k] ~= v then return false end end
  for k, v in pairs(b) do if a[k] ~= v then return false end end
  return true
end

local function inspect(s)
  fields(s, {records=true, authorized_owned=true, source_category=true, permission_disposition=true,
    capture_utc=true, source_id=true, configuration_id=true, source_revision=true, algorithm_revision=true,
    expected_source_count=true, population_basis=true, acquisition_completeness=true,
    evaluation_options=true, observation_started_utc=true, observation_finished_utc=true,
    capture_wall_ms=true, source_snapshot_status=true, source_error=true, ce_capture=true})
  check(s.authorized_owned == true, 'owned-test authorization required')
  check(s.permission_disposition == 'EXPRESSLY_APPROVED', 'express data-export permission required')
  check(s.source_category == 'AUTHORIZED_REAL_PRODUCTION'
    or s.source_category == 'AUTHORIZED_REPRESENTATIVE_REAL'
    or s.source_category == 'ARTIFICIAL_FIXTURE' or s.source_category == 'UNKNOWN',
    'explicit source category required')
  local n = dense(s.records)
  check(s.expected_source_count == nil or integer(s.expected_source_count, 0, MAX_ADDR),
    'invalid expected source count')
  local basis = s.population_basis == nil and 'UNKNOWN' or s.population_basis
  local acquisition = s.acquisition_completeness == nil and 'UNKNOWN' or s.acquisition_completeness
  check(basis == 'INITIAL_SNAPSHOT' or basis == 'BOUNDED_OR_FILTERED' or basis == 'UNKNOWN',
    'invalid population basis')
  check(acquisition == 'SUPPLIER_ASSERTED_COMPLETE' or acquisition == 'INCOMPLETE'
    or acquisition == 'UNKNOWN', 'invalid acquisition completeness')
  local source_status = s.source_snapshot_status == nil and 'UNKNOWN' or s.source_snapshot_status
  check(source_status == 'OPERATOR_FROZEN_COPY' or source_status == 'CE_SEQUENTIAL_READ' or source_status == 'UNKNOWN'
    or source_status == 'UNAVAILABLE' or source_status == 'INCONSISTENT', 'invalid source status')
  check(s.source_error == nil or (type(s.source_error) == 'string' and #s.source_error > 0),
    'invalid source error')
  check(s.capture_wall_ms == nil or integer(s.capture_wall_ms, 0, MAX_ADDR), 'invalid capture wall time')
  local opts = s.evaluation_options == nil and {} or s.evaluation_options
  validate_options(opts)
  local counts = {source_count=n, exported_count=n, duplicate_occurrences=0,
    unavailable_identities=0, unavailable_words=0, records_without_replay_schema=0,
    undeclared_missing_words=0, conflicting_observations=0}
  local seen, words, relevant = {}, {}, {}
  local any_observations = false
  for _, r in ipairs(s.records) do
    fields(r, {addr=true, mapped=true, protect=true, memory=true, unavailable=true})
    check(r.addr == nil or r.addr == false or type(r.addr) == 'string'
      or integer(r.addr, 1, MAX_ADDR), 'invalid identity')
    if type(r.addr) == 'string' then check(#r.addr > 0, 'empty identity') end
    check(r.mapped == nil or type(r.mapped) == 'boolean', 'invalid mapped observation')
    check(r.protect == nil or integer(r.protect, 0, 0xFFFFFFFF), 'invalid protect observation')
    check(r.memory == nil or plain(r.memory), 'invalid memory map')
    check(r.unavailable == nil or plain(r.unavailable), 'invalid unavailable map')
    any_observations = any_observations or r.mapped ~= nil or r.protect ~= nil or r.memory ~= nil
    if r.addr == nil or r.addr == false then
      counts.unavailable_identities = counts.unavailable_identities + 1
    else
      if seen[r.addr] then
        counts.duplicate_occurrences = counts.duplicate_occurrences + 1
        local p = seen[r.addr]
        if p.mapped ~= r.mapped or p.protect ~= r.protect or not same_map(p.memory, r.memory) then
          counts.conflicting_observations = counts.conflicting_observations + 1
        end
      else seen[r.addr] = r end
    end
    if type(r.addr) == 'number' then
      for _, off in ipairs(OFFSETS) do relevant[r.addr + off] = true end
    end
    for addr, value in pairs(r.memory or {}) do
      check(integer(addr, 1, MAX_ADDR) and integer(value, 0, 0xFFFFFFFF), 'invalid word')
      if r.mapped then
        if words[addr] ~= nil and words[addr] ~= value then
          counts.conflicting_observations = counts.conflicting_observations + 1
        end
        words[addr] = value
      end
    end
    for addr, value in pairs(r.unavailable or {}) do
      check(integer(addr, 1, MAX_ADDR) and value == true and (r.memory or {})[addr] == nil,
        'invalid unavailable word')
      counts.unavailable_words = counts.unavailable_words + 1
    end
  end
  for _, r in ipairs(s.records) do
    for addr in pairs(r.memory or {}) do check(relevant[addr], 'word outside supplied record contract') end
    for addr in pairs(r.unavailable or {}) do
      check(relevant[addr], 'unavailable word outside supplied record contract')
      if r.mapped and words[addr] ~= nil then
        counts.conflicting_observations = counts.conflicting_observations + 1
      end
    end
    if type(r.addr) ~= 'number' or r.mapped == nil or r.protect == nil or r.memory == nil then
      counts.records_without_replay_schema = counts.records_without_replay_schema + 1
    elseif r.mapped then
      for _, off in ipairs(OFFSETS) do
        local addr = r.addr + off
        if words[addr] == nil and not (r.unavailable or {})[addr] then
          counts.undeclared_missing_words = counts.undeclared_missing_words + 1
        end
      end
    end
  end
  local inventory = counts.unavailable_identities == 0
    and (s.expected_source_count == nil or s.expected_source_count == n)
  local replay = counts.records_without_replay_schema == 0 and counts.undeclared_missing_words == 0
    and counts.conflicting_observations == 0 and opts.target_value_pattern ~= nil
  local issues = {}
  if not inventory then issues.identity_or_count_mismatch = true end
  if basis ~= 'INITIAL_SNAPSHOT' then issues.original_first_pass_not_established = true end
  if acquisition == 'INCOMPLETE' then issues.acquisition_incomplete = true end
  if source_status ~= 'OPERATOR_FROZEN_COPY' and source_status ~= 'CE_SEQUENTIAL_READ' then
    issues.source_not_frozen = true
  end
  if s.source_error ~= nil then issues.source_error_reported = true end
  if s.source_category == 'UNKNOWN' then issues.source_category_unknown = true end
  local disposition
  if next(issues) ~= nil then
    disposition = 'INCOMPLETE'
  elseif replay then disposition = 'REPLAY_READY'
  elseif not any_observations then disposition = 'ADDRESS_ONLY'
  else disposition = 'INCOMPLETE' end
  if not replay then issues.replay_observations_or_settings_missing = true end
  if counts.conflicting_observations > 0 then issues.conflicting_observations = true end
  local m = {format='MVP0_MANUAL_EXPORT', version=1, outcome=disposition,
    source_category=s.source_category, permission_disposition=s.permission_disposition,
    authorized_owned=true, population_basis=basis, source_snapshot_status=source_status,
    source_error=s.source_error or 'NONE_REPORTED', issues=issues,
    capture_wall_ms=s.capture_wall_ms or 'UNKNOWN',
    acquisition_completeness=acquisition, supplied_population_exported=true,
    inventory_complete=inventory, replay_observations_complete=replay,
    expected_source_count=s.expected_source_count or 'UNKNOWN', counts=counts,
    evaluation_options=opts, label_status='UNKNOWN', ce_capture=s.ce_capture}
  for _, key in ipairs({'capture_utc', 'source_id', 'configuration_id', 'source_revision', 'algorithm_revision',
      'observation_started_utc', 'observation_finished_utc'}) do
    check(s[key] == nil or (type(s[key]) == 'string' and #s[key] > 0), 'invalid ' .. key)
    m[key] = s[key] or 'UNKNOWN'
  end
  return m
end

local function label_record(input, count)
  if input == nil then return {status='UNKNOWN', outcomes={}} end
  fields(input, {independent=true, basis=true, outcomes=true})
  check(input.independent == true and type(input.basis) == 'string' and #input.basis > 0,
    'independent label basis required')
  check(plain(input.outcomes), 'label occurrence map required')
  for index, outcome in pairs(input.outcomes) do
    check(integer(index, 1, count), 'label occurrence outside supplied population')
    check(outcome == 'POSITIVE' or outcome == 'NEGATIVE' or outcome == 'UNKNOWN'
      or outcome == 'AMBIGUOUS', 'invalid independent outcome')
  end
  return {status='SUPPLIED_INDEPENDENT', independent=true, basis=input.basis, outcomes=input.outcomes}
end

local function exists(path)
  local f, _, code = io.open(path, 'rb')
  if f then check(f:close(), 'existence check close failed'); return true end
  check(code == 2, 'cannot establish unused output path')
  return false
end

local function enum_is(value, name)
  return value == name or (type(_G[name]) == 'number' and value == _G[name])
end

local function scan_settings(ms)
  check(enum_is(ms.LastScanType, 'stFirstScan'), 'current CE result must be a completed First Scan')
  check(ms.LastScanWasRegionScan == false and enum_is(ms.ScanOption, 'soExactValue'),
    'AC5/AC6 requires an Exact Value First Scan, not an unknown-value or range scan')
  check(ms.OnlyOneResult ~= true and ms.IsUnique ~= true and ms.LuaFormula ~= true
    and ms.inverseScan ~= true, 'limited, formula or inverted scans are not supported')
  local single = enum_is(ms.VariableType, 'vtSingle')
  check(single or enum_is(ms.VariableType, 'vtDword'), 'AC5/AC6 requires Float or 4 Bytes results')
  check(type(ms.LastScanValue) == 'string' and type(ms.Hexadecimal) == 'boolean',
    'CE scan value/representation unavailable')
  check(not single or not ms.Hexadecimal, 'Float scan input must be decimal; hexadecimal Float semantics are unsupported')
  local value = ms.LastScanValue:match('^%s*(.-)%s*$')
  local bits, target_float
  if ms.Hexadecimal then
    value = value:gsub('^0[xX]', ''):gsub('^%$', '')
    check(value:match('^%x+$') and #value <= 8, 'scan value is not a literal uint32 hexadecimal value')
    bits = tonumber(value, 16)
  elseif single then
    local number = tonumber((value:gsub(',', '.')))
    check(number and number == number and math.abs(number) < math.huge, 'finite literal Float scan value unavailable')
    bits = string.unpack('<I4', string.pack('<f', number))
  else
    check(value:match('^[+-]?%d+$'), 'scan value is not a literal 4 Bytes integer')
    local number = tonumber(value)
    check(integer(number, -0x80000000, 0xFFFFFFFF), '4 Bytes scan value out of range')
    bits = number % 2^32
  end
  if single then
    target_float = string.unpack('<f', string.pack('<I4', bits))
    check(target_float == target_float and math.abs(target_float) < math.huge, 'nonfinite Float scan value')
  end
  return {scan_type='stFirstScan', variable_type=single and 'vtSingle' or 'vtDword',
    scan_option='soExactValue', scan_value=ms.LastScanValue, hexadecimal=ms.Hexadecimal},
    {population_mode='full', target_value_pattern=bits, target_value_float=target_float}
end

local function region_table()
  local regions = enumMemoryRegions()
  check(type(regions) == 'table', 'CE enumMemoryRegions did not supply mapping observations')
  for _, r in ipairs(regions) do
    check(integer(r.BaseAddress, 0, MAX_ADDR) and integer(r.RegionSize, 1, MAX_ADDR)
      and integer(r.State, 0, 0xFFFFFFFF) and integer(r.Protect, 0, 0xFFFFFFFF),
      'CE supplied invalid region metadata')
  end
  table.sort(regions, function(a, b) return a.BaseAddress < b.BaseAddress end)
  return regions
end

local function region_at(regions, addr)
  local low, high = 1, #regions
  while low <= high do
    local mid = (low + high) // 2
    local r = regions[mid]
    if addr < r.BaseAddress then high = mid - 1
    elseif addr >= r.BaseAddress + r.RegionSize then low = mid + 1
    else return r end
  end
end

local function mapping(r)
  if not r then return {} end -- Unknown is never invented as unmapped/protect=0.
  return {base=r.BaseAddress, size=r.RegionSize, state=r.State, protect=r.Protect,
    allocation_base=r.AllocationBase, kind=r.Type}
end

local function size_only_expansion(before, after)
  -- Missing or malformed attributes cannot establish unchanged region identity.
  for _, m in ipairs({before, after}) do
    if not (integer(m.base, 0, MAX_ADDR) and integer(m.size, 1, MAX_ADDR - m.base)
      and integer(m.allocation_base, 0, MAX_ADDR) and integer(m.state, 0, 0xFFFFFFFF)
      and integer(m.protect, 0, 0xFFFFFFFF) and integer(m.kind, 0, 0xFFFFFFFF)) then
      return false
    end
  end
  return after.size > before.size and before.base == after.base
    and before.allocation_base == after.allocation_base and before.state == after.state
    and before.protect == after.protect and before.kind == after.kind
end

local function inaccessible(r)
  return r and (r.State ~= 0x1000 or (r.Protect & 0x101) ~= 0 or r.Protect == 0)
end

local function result_file_count(ms)
  -- CE's NORMAL result file: a 7-byte short-string header followed by native
  -- CE pointer-sized addresses. FoundList.Count uses this size, not its UI cap.
  check(type(ms.ScanresultFolder) == 'string' and #ms.ScanresultFolder > 0,
    'CE completed-result folder unavailable')
  check(type(cheatEngineIs64Bit) == 'function', 'CE host pointer size unavailable')
  local wide = cheatEngineIs64Bit()
  check(type(wide) == 'boolean', 'CE host pointer size unavailable')
  local f, why = io.open(ms.ScanresultFolder:gsub('[/\\]$', '') .. '/ADDRESSES.TMP', 'rb')
  check(f, 'CE completed First Scan address file unavailable: ' .. tostring(why))
  local header, bytes = f:read(7), f:seek('end')
  local closed = f:close()
  local width = wide and 8 or 4
  check(closed and header == '\6NORMAL' and integer(bytes, 7, MAX_ADDR)
    and (bytes - 7) % width == 0, 'CE completed address file is not a valid NORMAL result')
  return (bytes - 7) // width
end

local function capture_ce()
  for _, name in ipairs({'getCurrentMemscan', 'getOpenedProcessID', 'readInteger', 'enumMemoryRegions'}) do
    check(type(_G[name]) == 'function', 'CE read-only capability unavailable: ' .. name)
  end
  local pid, ms = getOpenedProcessID(), getCurrentMemscan()
  check(integer(pid, 1, 0xFFFFFFFF), 'no already attached owned-test process')
  check(ms ~= nil, 'current CE MemScan unavailable')
  scan_settings(ms)
  check(type(ms.waitTillDone) == 'function', 'CE MemScan.waitTillDone unavailable')
  ms.waitTillDone() -- Only joins the existing scan; never starts or refines one.
  local settings, opts = scan_settings(ms)
  local fl = ms.FoundList
  check(fl ~= nil, 'completed CE MemScan.FoundList unavailable')
  local count = fl.Count
  -- getProgress().ResultsFound can reset to zero after CE frees scan workers.
  check(integer(count, 0, MAX_ADDR) and result_file_count(ms) == count,
    'CE FoundList count does not match the completed scan result')
  local started = getTickCount()
  local s = {records={}, authorized_owned=true, permission_disposition='EXPRESSLY_APPROVED',
    source_category='AUTHORIZED_REPRESENTATIVE_REAL', source_id='CE_PID_' .. tostring(pid),
    population_basis='INITIAL_SNAPSHOT', acquisition_completeness='UNKNOWN',
    source_snapshot_status='CE_SEQUENTIAL_READ', expected_source_count=count,
    evaluation_options=opts, observation_started_utc=os.date('!%Y-%m-%dT%H:%M:%SZ'),
    ce_capture={process_id=pid, settings=settings, atomic=false, mapping_changes={}, warnings={}}}
  local function same_source()
    check(getOpenedProcessID() == pid and getCurrentMemscan() == ms,
      'CE attachment or selected scan changed during capture')
  end
  local function address(index)
    local raw = fl.Address[index]
    local addr = type(raw) == 'string' and tonumber(raw, 16) or raw
    check(integer(addr, 0x21, MAX_ADDR - 0x53), 'CE result address unavailable at index ' .. index)
    return addr
  end
  -- Freeze every source occurrence before any observations; no collector/budget.
  for index = 0, count - 1 do s.records[index + 1] = {addr=address(index), memory={}, unavailable={}} end
  same_source()
  local regions = region_table()
  for _, r in ipairs(s.records) do
    same_source()
    local region = region_at(regions, r.addr)
    if region then r.mapped, r.protect = region.State == 0x1000, region.Protect end
    for _, off in ipairs(OFFSETS) do
      local addr = r.addr + off
      local ok, word = false, nil
      if not inaccessible(region_at(regions, addr)) and not inaccessible(region_at(regions, addr + 3)) then
        ok, word = pcall(readInteger, addr)
      end
      if ok and integer(word, -0x80000000, 0xFFFFFFFF) then
        r.memory[addr] = word % 2^32
      else r.unavailable[addr] = true end
    end
  end
  same_source()
  local after = region_table()
  for index, r in ipairs(s.records) do
    local before_map, after_map = mapping(region_at(regions, r.addr)), mapping(region_at(after, r.addr))
    if not same_map(before_map, after_map) then
      s.ce_capture.mapping_changes[index] = {before=before_map, after=after_map}
      if size_only_expansion(before_map, after_map) then
        local warnings = s.ce_capture.warnings
        warnings.size_only_region_expansion = (warnings.size_only_region_expansion or 0) + 1
      else
        s.source_error = 'CE candidate mapping changed during capture; see ce_capture.mapping_changes'
        s.source_snapshot_status = 'INCONSISTENT'
      end
    end
    check(address(index - 1) == r.addr, 'CE First Scan membership changed during capture')
  end
  same_source()
  check(fl.Count == count and result_file_count(ms) == count
    and unchanged(scan_settings(ms), settings), 'CE First Scan settings/count changed during capture')
  s.observation_finished_utc = os.date('!%Y-%m-%dT%H:%M:%SZ')
  s.capture_utc = s.observation_finished_utc
  s.capture_wall_ms = (getTickCount() - started) % 2^32
  return s
end

local function ensure_output_directory()
  -- LuaFileSystem ships with CE (also used by its bundled autosave utility).
  local ok, fs = pcall(require, 'lfs')
  if type(fs) ~= 'table' then fs = _G.lfs end
  check(ok and type(fs) == 'table', 'CE bundled LuaFileSystem unavailable')
  for _, suffix in ipairs({'/log', '/log/base-pool-snapshot'}) do
    local path = root .. suffix
    if fs.attributes(path, 'mode') ~= 'directory' then
      local made, why = fs.mkdir(path)
      check(made, 'cannot create local output directory ' .. path .. ': ' .. tostring(why))
    end
  end
end

function M.export(snapshot, independent_labels)
  check(root ~= nil and (root:match('^%a:/') or root:sub(1, 1) == '/'),
    'load exporter using its absolute repository path')
  check(type(md5file) == 'function' and type(getTickCount) == 'function',
    'CE local-file checksum and wall timer required')
  local direct = snapshot == nil
  if direct then
    ensure_output_directory()
    snapshot = capture_ce()
  end
  local start = getTickCount()
  local started_utc = os.date('!%Y-%m-%dT%H:%M:%SZ')
  -- Retain the existing plain-data serializer internally. The ordinary operator
  -- entry constructs these records above, without a provider or preparation API.
  check(plain(snapshot), 'plain snapshot required')
  local frozen = copy_data(snapshot, {})
  local frozen_labels
  if independent_labels ~= nil then frozen_labels = copy_data(independent_labels, {}) end
  local labels = label_record(frozen_labels, dense(frozen.records))
  local m = inspect(frozen)
  local source_changed = not unchanged(snapshot, frozen)
  local output = root .. '/log/base-pool-snapshot/'
  local names, id
  repeat
    serial = serial + 1
    id = os.date('!%Y%m%dT%H%M%SZ') .. '-' .. tostring(serial)
    names = {reservation=output .. 'manual-export-' .. id .. '.reserved',
      records=output .. 'manual-export-' .. id .. '.records.jsonl',
      labels=output .. 'manual-export-' .. id .. '.labels.json',
      pending=output .. 'manual-export-' .. id .. '.manifest.pending',
      manifest=output .. 'manual-export-' .. id .. '.manifest.json'}
    local occupied = false
    for _, path in pairs(names) do occupied = exists(path) or occupied end
    if not occupied then break end
  until false
  -- Like the existing manual evidence writer: one serialized invocation per
  -- output directory. Reservations survive failures and are never reused.
  local active
  local output_bytes = 0
  local function write(path, emit)
    check(not exists(path), 'output already exists')
    active = assert(io.open(path, 'wb'))
    emit(function(text)
      check(active:write(text), 'output write failed')
      output_bytes = output_bytes + #text
    end)
    local f = active
    active = nil
    check(f:close(), 'output close failed')
  end
  local function digest(path)
    local hash = md5file(path)
    check(type(hash) == 'string' and #hash == 32 and hash:match('^%x+$'), 'checksum failed')
    return hash:lower()
  end
  local ok, result = pcall(function()
    write(names.reservation, function(put) put(id .. '\n') end)
    m.dataset_id, m.export_started_utc = id, started_utc
    local bytes = 0
    write(names.records, function(put)
      for _, record in ipairs(frozen.records) do
        local line = json(record) .. '\n'
        put(line)
        bytes = bytes + #line
      end
    end)
    m.records = {file=names.records:match('[^/]+$'), bytes=bytes,
      hash_algorithm='MD5', hash=digest(names.records), count=m.counts.exported_count}
    labels.format, labels.version = 'MVP0_INDEPENDENT_LABELS', 1
    labels.dataset_id, labels.records_md5 = id, m.records.hash
    write(names.labels, function(put)
      put(json(labels) .. '\n')
    end)
    m.label_status = labels.status
    m.labels_file = names.labels:match('[^/]+$')
    source_changed = source_changed or not unchanged(snapshot, frozen)
    m.source_unchanged_at_checks = not source_changed
    if source_changed then
      m.outcome, m.source_snapshot_status = 'INCOMPLETE', 'CHANGED_DURING_EXPORT'
      m.issues.source_changed_during_export = true
    end
    m.export_finished_utc = os.date('!%Y-%m-%dT%H:%M:%SZ')
    m.export_wall_ms = (getTickCount() - start) % 2^32
    m.output_bytes_excluding_manifest = output_bytes
    m.timer_boundary = 'entry through copy, validation, records close/hash, label close and final source check; excludes manifest publication'
    write(names.pending, function(put) put(json(m) .. '\n') end)
    check(not exists(names.manifest), 'manifest already exists')
    check(os.rename(names.pending, names.manifest), 'manifest publication failed')
    return {outcome=m.outcome, dataset_id=id, manifest_path=names.manifest,
      exported_count=m.counts.exported_count, export_wall_ms=m.export_wall_ms,
      records_bytes=bytes, output_bytes=output_bytes}
  end)
  if not ok then
    if active then pcall(active.close, active) end
    error('EXPORT_FAILED: ' .. tostring(result), 0)
  end
  if direct then
    print(string.format('MVP0 export: %s | occurrences=%d | capture_ms=%d | export_ms=%d\n%s',
      result.outcome, result.exported_count, snapshot.capture_wall_ms, result.export_wall_ms, result.manifest_path))
    local expansions = snapshot.ce_capture.warnings.size_only_region_expansion
    if expansions then
      print(string.format('WARNING: size-only region expansion at %d occurrence(s); see ce_capture.mapping_changes. '
        .. 'Capture is non-atomic; live data and truth stability are not established.', expansions))
    end
    if result.outcome ~= 'REPLAY_READY' then
      print('Dataset is not replay-ready; inspect manifest issues and counts. ' .. (snapshot.source_error or ''))
    end
  end
  return result
end

return M
