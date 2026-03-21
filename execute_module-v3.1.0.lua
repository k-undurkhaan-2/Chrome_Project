getLuaEngine().show()

dofile([[D:\Lua Developer\mvp0_candidate_report.lua]])
dofile([[D:\Lua Developer\mvp0_foundlist_collector.lua]])

local bundle = MVP0FoundList.run({
  max_candidates = 100,
  scan_budget = 8000,
  target_value_pattern = 0x42C80000,
  target_value_float = 100.0,
  session_id = 'collector-retest-wide-2',
  filter_target_match = true,
  use_prescore_selection = true,
  known_true_addr = 0x2C2061C8D48,
})

print('raw_count              = ' .. tostring(bundle.raw_count))
print('scanned_count          = ' .. tostring(bundle.scanned_count))
print('unique_count           = ' .. tostring(bundle.unique_count))
print('filtered_count         = ' .. tostring(bundle.filtered_count))
print('prescored_count        = ' .. tostring(bundle.prescored_count))
print('selected_count         = ' .. tostring(bundle.selected_count))
print('selection_strategy     = ' .. tostring(bundle.selection_strategy))
print('true_in_full_foundlist = ' .. tostring(bundle.true_in_full_foundlist))
print('true_in_raw            = ' .. tostring(bundle.true_in_raw))
print('true_in_unique         = ' .. tostring(bundle.true_in_unique))
print('true_in_filtered       = ' .. tostring(bundle.true_in_filtered))
print('true_in_prescored      = ' .. tostring(bundle.true_in_prescored))
print('true_in_selected       = ' .. tostring(bundle.true_in_selected))

print(bundle.result.report_text)