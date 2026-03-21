-- ===== MVP0 FoundList Smoke Test =====
getLuaEngine().show()
-- 1) 修改为你本地实际路径
local BASE_DIR = [[D:\Lua Developer]]

local REPORT_FILE = BASE_DIR .. [[\mvp0_candidate_report.lua]]
local COLLECTOR_FILE = BASE_DIR .. [[\mvp0_foundlist_collector.lua]]

-- 2) 先加载核心评分器，再加载 FoundList collector
dofile(REPORT_FILE)
dofile(COLLECTOR_FILE)

-- 3) 运行参数
local TARGET_VALUE_PATTERN = 0x42C80000   -- 100.0f
local TARGET_VALUE_FLOAT   = 100.0
local SESSION_ID           = 'foundlist-smoke-test'
local MAX_CANDIDATES       = 10
local FILTER_TARGET_MATCH  = true

-- 4) 执行采集 + 评分
local bundle = MVP0FoundList.run({
  max_candidates = MAX_CANDIDATES,
  target_value_pattern = TARGET_VALUE_PATTERN,
  target_value_float = TARGET_VALUE_FLOAT,
  session_id = SESSION_ID,
  filter_target_match = FILTER_TARGET_MATCH,
})

-- 5) 打印基础统计
print('=== MVP0 FoundList Collector Stats ===')
print('source_mode      = ' .. tostring(bundle.source_mode))
print('raw_count        = ' .. tostring(bundle.raw_count))
print('scanned_count    = ' .. tostring(bundle.scanned_count))
print('unique_count     = ' .. tostring(bundle.unique_count))
print('selected_count   = ' .. tostring(bundle.selected_count))
print('filter_target    = ' .. tostring(bundle.filter_target_match))
print('target_pattern   = 0x' .. string.format('%08X', bundle.target_value_pattern))
print('=====================================')

-- 6) 打印最终送入 MVP0 的候选地址
print('=== Selected candidate_value_addrs ===')
for i, addr in ipairs(bundle.candidate_value_addrs) do
  print(string.format('%02d: 0x%X', i, addr))
end
print('=====================================')

-- 7) 打印完整报告
print(bundle.result.report_text)

-- 8) 弹窗显示报告
showMessage(bundle.result.report_text)