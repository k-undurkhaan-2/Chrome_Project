getLuaEngine().show()
-- 1) 先加载评分器
dofile([[D:\Lua Developer\mvp0_candidate_report.lua]])

-- 2) 从当前扫描结果里取前 N 个地址
local function collect_candidates_from_foundlist(limit)
  limit = limit or 10

  local fl = getAddressList()
  local memscan = getCurrentMemscan()
  local foundlist = createFoundList(memscan)

  foundlist.initialize()

  local candidates = {}
  local count = math.min(foundlist.Count, limit)

  for i = 0, count - 1 do
    local addr_str = foundlist.Address[i]
    local addr_num = getAddress(addr_str)
    table.insert(candidates, addr_num)
  end

  foundlist.destroy()
  return candidates
end

-- 3) 打印候选，方便你确认
local function print_candidates(candidates)
  print('=== Candidates ===')
  for i, addr in ipairs(candidates) do
    print(string.format('%02d: 0x%X', i, addr))
  end
  print('==================')
end

-- 4) 跑 MVP0
local function run_mvp0_from_foundlist(target_pattern_u32, target_value_float, session_id, limit)
  local candidates = collect_candidates_from_foundlist(limit or 10)

  if #candidates == 0 then
    showMessage('No scan results found. Please do a memory scan first.')
    return nil
  end

  print_candidates(candidates)

  local input = MVP0.make_input(candidates, target_pattern_u32, {
    target_value_float = target_value_float,
    session_id = session_id or 'foundlist-test'
  })

  local result = MVP0.run(input)

  print(result.report_text)
  showMessage(result.report_text)

  return result
end

-- 5) 示例：如果你当前测试值是 100.0f
-- 0x42C80000 = float 100.0
run_mvp0_from_foundlist(0x42C80000, 100.0, 'manual-scan-session', 8)