getLuaEngine().show()

dofile([[D:\Lua Developer\mvp0_candidate_report.lua]])
dofile([[D:\Lua Developer\\mvp0_foundlist_collector.lua]])

local bundle = MVP0FoundList.run({
  max_candidates = 20,
  scan_budget = 2000,
  target_value_pattern = 0x42C80000,
  target_value_float = 100.0,
  session_id = 'collector-retest-1',
  filter_target_match = true,
})

print('raw_count      = ' .. tostring(bundle.raw_count))
print('scanned_count  = ' .. tostring(bundle.scanned_count))
print('unique_count   = ' .. tostring(bundle.unique_count))
print('filtered_count = ' .. tostring(bundle.filtered_count))
print('selected_count = ' .. tostring(bundle.selected_count))
print('scan_budget    = ' .. tostring(bundle.scan_budget))
print('max_candidates = ' .. tostring(bundle.max_candidates))

print('=== candidate_value_addrs ===')
for i, addr in ipairs(bundle.candidate_value_addrs) do
  print(string.format('%02d: 0x%X', i, addr))
end

print(bundle.result.report_text)
showMessage(bundle.result.report_text)