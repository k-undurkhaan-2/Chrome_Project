getLuaEngine().show()

dofile([[D:\Lua Developer\mvp0_candidate_report.lua]])
dofile([[D:\Lua Developer\mvp0_foundlist_collector.lua]])

local KNOWN_TRUE_ADDR = 0x21A061C8D48

local bundle = MVP0FoundList.run({
  max_candidates = 100,
  scan_budget = 8000,
  target_value_pattern = 0x42C80000,
  target_value_float = 100.0,
  session_id = 'collector-retest-wide-2',
  filter_target_match = true,
  use_prescore_selection = true,
  known_true_addr = KNOWN_TRUE_ADDR,
})

local result = (bundle and bundle.result) or {}

local function printKV(label, value)
  print(string.format('%-22s = %s', label, tostring(value)))
end

local function printHexKV(label, value)
  if value == nil then
    printKV(label, nil)
  else
    print(string.format('%-22s = 0x%X', label, value))
  end
end

local function pickKnownTrueField(name)
  if bundle and bundle[name] ~= nil then
    return bundle[name]
  end
  if result and result[name] ~= nil then
    return result[name]
  end
  return nil
end

local function printLogTable(title, t)
  print('=== ' .. title .. ' ===')

  if t == nil then
    print('nil')
    return
  end

  if type(t) ~= 'table' then
    print(tostring(t))
    return
  end

  local hasArrayItems = false
  for i, v in ipairs(t) do
    hasArrayItems = true
    print(string.format('%02d: %s', i, tostring(v)))
  end

  if not hasArrayItems then
    local keys = {}
    for k, _ in pairs(t) do
      table.insert(keys, k)
    end

    table.sort(keys, function(a, b)
      return tostring(a) < tostring(b)
    end)

    for _, k in ipairs(keys) do
      print(tostring(k) .. ' = ' .. tostring(t[k]))
    end
  end
end

print('=== collector_stats ===')
printKV('raw_count', bundle.raw_count)
printKV('scanned_count', bundle.scanned_count)
printKV('unique_count', bundle.unique_count)
printKV('filtered_count', bundle.filtered_count)
printKV('prescored_count', bundle.prescored_count)
printKV('selected_count', bundle.selected_count)
printKV('selection_strategy', bundle.selection_strategy)

print('=== truth_probe_flags ===')
printKV('true_in_full_foundlist', bundle.true_in_full_foundlist)
printKV('true_in_raw', bundle.true_in_raw)
printKV('true_in_unique', bundle.true_in_unique)
printKV('true_in_filtered', bundle.true_in_filtered)
printKV('true_in_prescored', bundle.true_in_prescored)
printKV('true_in_selected', bundle.true_in_selected)

print('=== extra_probe_debug ===')
printHexKV('known_true_addr', KNOWN_TRUE_ADDR)
printKV('true_foundlist_index', bundle.true_foundlist_index)
printKV('probe_window_radius', bundle.probe_window_radius)

printLogTable('truth_probe_logs', bundle.truth_probe_logs)

print('=== known_true_debug ===')
printKV('known_true_rank_position', pickKnownTrueField('known_true_rank_position'))
printKV('known_true_base_score', pickKnownTrueField('known_true_base_score'))
printKV('known_true_final_score', pickKnownTrueField('known_true_final_score'))
printKV('known_true_tie_break_vector', pickKnownTrueField('known_true_tie_break_vector'))

print('=== report_text ===')
if result and result.report_text then
  print(result.report_text)
else
  print('bundle.result.report_text = nil')
end