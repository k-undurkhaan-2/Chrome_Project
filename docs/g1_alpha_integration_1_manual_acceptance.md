# G1-ALPHA-INTEGRATION-1：标准 ID1 中文人工验收单

维护者授权：`APPROVE_G1_ALPHA_INTEGRATION_1_STANDARD_ID1_FULL_POPULATION`。
交付状态：`READY_G1_ALPHA_INTEGRATION_1_CONTROLLED_MANUAL_ACCEPTANCE`。
这是标准入口的受控验收交接，**本候选的 CE 宿主人工验收尚未执行**，不代表 native 资格或发布许可。
历史 M6 的限定 PASS 见[独立回执](../reports/2026-11-26/g1-alpha-prep-3-r1-manual-acceptance.md)，不能转移给本候选。

## 1. 核对候选与环境

- 使用 Windows x64、**CE 7.6 / Lua 5.3**，新建 CE 会话，始终保持 **No Process Selected**。
- 候选目录：`D:\armedforces.io-v2\reports\2026-11-26\g1-alpha-integration-1-manual-final\`。
- 打开其中 `src\ce_mvp.local.CT`；ID1 Start/Stop、ID2 Status、ID3 READ ONLY 初始均不勾选。
- 源码：`6190a9f93ec72560ca5db5e616bc4cd411795efc`。
- CT SHA-256：`023ed8e3d1a41841b3f22e826a55f2e23f3860d2ef73c6859079123d4797f4d6`；3003 字节。
- [13 文件身份清单](../reports/2026-11-26/g1-alpha-integration-1-file-identities.json)与[交付/验证回执](../reports/2026-11-26/g1-alpha-integration-1-delivery.md)记录精确来源和验证。

只使用上述 **manual-final** 候选。先前生成的 `g1-alpha-integration-1-manual` 已由最终结果边界修复后的候选替代，仍保留为历史输出，未获 CE 人工接受；不要用它代替本单候选。

CT 由维护模板的**默认准备命令、不带 `--alpha-controlled`**生成，保留 `controlled=false`；默认加载器是 `ALPHA_STANDARD`，产品 profile 是 `ALPHA_FULL`。不会自动选择模拟输入，也不会读取私有配置或补做 native 采集。输入缺失时 Start 返回 `ALPHA_INPUT_REQUIRED` 并保持无动作；先误启动的会话须重开 CE 后正确选择输入，不删除单例或绕过模式锁。

包内只包含维护文件、公开夹具及生成 CT，无私有配置。Python 只在离线准备时使用；人工运行不要求启动 Python、SDK、其他启动器或目标应用。路径已绑定，移动候选目录后原 CT 哈希不再可用，需另行准备并重新登记身份。

在 PowerShell 核对完整文件集及每个哈希/长度：

```powershell
$candidate = 'D:\armedforces.io-v2\reports\2026-11-26\g1-alpha-integration-1-manual-final'
$manifest = Get-Content -LiteralPath 'D:\armedforces.io-v2\reports\2026-11-26\g1-alpha-integration-1-file-identities.json' -Raw | ConvertFrom-Json
$actual = @(Get-ChildItem -LiteralPath $candidate -File -Recurse | ForEach-Object { $_.FullName.Substring($candidate.Length + 1).Replace('\','/') })
if (Compare-Object @($manifest.files.path) $actual -CaseSensitive) { throw 'Candidate file set mismatch' }
foreach ($f in $manifest.files) {
  $p = Join-Path $candidate $f.path
  if ((Get-Item -LiteralPath $p).Length -ne $f.bytes -or (Get-FileHash -Algorithm SHA256 -LiteralPath $p).Hash.ToLowerInvariant() -ne $f.sha256) { throw "Candidate identity mismatch: $($f.path)" }
}
'ALL_13_IDENTITIES_MATCH'
```

## 2. 先显式选择测试输入，再勾选标准 ID1

本次只允许已有的公开三成员 owned table fixture。**不要选择进程，不加载私有配置，不切换工程或资格模式。** 在 CE Lua console 执行以下选择；它仅锁定模式和输入，不启动、附加或评分：

```lua
print('CE_LUA_VERSION=' .. _VERSION)
print('EXISTING_SINGLETON=' .. tostring(H3A7_CE_MVP~=nil))
assert(_VERSION=='Lua 5.3' and H3A7_CE_MVP==nil, 'Use a fresh CE 7.6 session')
local m=dofile('D:/armedforces.io-v2/reports/2026-11-26/g1-alpha-integration-1-manual-final/src/ce_mvp.lua')
assert(m.configure_execution({mode='ALPHA_STANDARD',input_source='OWNED_SYNTHETIC'}))
local s=m.status()
assert(s.execution_mode=='ALPHA_STANDARD' and s.product_profile=='ALPHA_FULL' and not s.running)
assert(m.controlled_fixture()==nil and m.evaluation()==nil)
```

随后明确勾选 **ID1 Start**。`controlled_fixture()` 是复用的测试访问接口名称；当前 execution_mode 必须仍是 **ALPHA_STANDARD**，不能以 ALPHA_CONTROLLED 代替本次验收。ID1 直接经原 adapter/core 和 AC6/AC5 全量评分，不调用 ID3。

评分前的独立预期来自公开人工构造记录：

| 项目 | 独立预期 |
| --- | --- |
| 身份 | `0x100128`, `0x100328`, `0x100528`；本例 supplied/distinct/eligible/selected 的成员及 ranked 顺序均如此 |
| 完成 | COMPLETE，completed=true，population_mode=full，population_complete=true |
| 计数 | supplied/distinct/eligible/selected/fully_scored/ranked 均为 3；duplicates/excluded 均为 0 |
| Rank-1 | `0x100128`，46 分；第二名 -36，第三名 -36，gap=82 |
| 建议 | ACCEPT/HIGH，manual_review_required=false；不授予 native 动作权限 |
| 编排 | MONITORING；scan_count=1、write_count=1；模拟写入/回读均为 `0x42FA0000`（125.0） |
| 范围 | data_provenance=synthetic、acquisition_mode=supplied_records、external_acquisition_status=NOT_RUN、scoring_mode=full；global_uniqueness_proven=false |
| 门禁 | action_permitted=false，native operation/readback=NOT_RUN，ALPHA_STOP_ONLY，automatic_recovery=false |

推进现有表模型并记录实际读数：

```lua
local m=assert(H3A7_CE_MVP)
local w=assert(m.controlled_fixture())
local t0,kb0=getTickCount(),collectgarbage('count')
w.step(10)
local elapsed,kb1=getTickCount()-t0,collectgarbage('count')
print('measured_step_ms=' .. elapsed .. ' lua_kib_before=' .. kb0 .. ' lua_kib_after=' .. kb1)
local s,e=m.status(),assert(m.evaluation(), 'No completed evaluation: stop and record error')
assert(e.status=='COMPLETE' and e.completed and e.population_mode=='full' and e.population_complete)
for _,k in ipairs({'supplied','distinct','duplicates','eligible','excluded','selected','fully_scored','ranked'}) do print(k .. '=' .. e.counts[k]) end
local truth={0x100128,0x100328,0x100528}
for _,k in ipairs({'supplied','distinct','eligible'}) do
  assert(#e.identities[k]==3)
  for i,id in ipairs(e.identities[k]) do assert(id==truth[i]); print(k .. '[' .. i .. ']=' .. string.format('0x%X',id)) end
end
assert(#e.collection.candidate_value_addrs==3 and #e.result.ranked==3)
for i,id in ipairs(e.collection.candidate_value_addrs) do assert(id==truth[i]); print('selected[' .. i .. ']=' .. string.format('0x%X',id)) end
for i,row in ipairs(e.result.ranked) do assert(row.candidate.value_addr==truth[i]); print('ranked[' .. i .. ']=' .. string.format('0x%X',row.candidate.value_addr)) end
assert(e.result.best.final_score==46 and e.result.second.final_score==-36)
assert(s.state=='MONITORING' and s.execution_mode=='ALPHA_STANDARD')
print(e.result.report_text)
print('fixture_native_scan_objects=' .. #w.scans)
```

`w.step(10)` 的 50 ms/tick 是模拟时间；上面 `getTickCount` 的差值才是本次宿主耗时。Lua 前后占用不是进程峰值；UI 响应性需单独观察，未测项写 UNKNOWN。合成 PID、地址、身份、API 名和写入计数都不是 native 证据。真实 operation/readback 对本候选为 **UNSUPPORTED / NOT_RUN**。

## 3. ID2 与停止检查

勾选/取消 **ID2 Status** 只观察缓存状态，不发起评分或操作。检查 `evaluation_status/evaluation_completed`、八个 `evaluation_*` 计数、`identity_reconciled`、排名和 recommendation/review、权限、生命周期和 cleanup 字段。

`scan_mode=bounded` 原义是**配置的地址范围**，由 `scan_mode_domain=configured_address_scope` 明示；不是评分预算模式。实际评分字段为 `scoring_mode=full` 和已完成结果中的 `population_mode=full`。`coverage_scope=supplied_distinct_eligible_only` 不证明完整外部采集。完整 REVIEW/REJECT 与合法 EMPTY 可以保留完整求值，同时原准入拒绝动作；输入/评分/资源错误或取消则不显示成功或旧轮结果。

在 MONITORING 后注入既有表模型的映射故障：

```lua
local m=H3A7_CE_MVP
local w=assert(m.controlled_fixture())
w.objects[1].mapped=false
w.step(4)
local s=m.status()
assert(s.state=='ERROR' and not s.running and s.stop_reason=='ALPHA_STOP:MAPPING_CHANGED')
assert(s.cleanup_ok and s.candidate_address==nil and s.rescan_attempts==0 and s.retry_at==nil)
local reads,writes,opens,scans=w.reads,#w.writes,w.open_calls,#w.scans
w.object(0x101128); w.step(200)
local quiet=w.reads==reads and #w.writes==writes and w.open_calls==opens and #w.scans==scans
assert(quiet); w.clean()
print('no_recovery=' .. tostring(quiet) .. ' cleanup_check_returned=true')
```

此时先前已完成的求值仍可观察，编排状态为 ERROR；它不代表新的成功运行。随后**取消 ID1 勾选，再明确人工勾选**，建立新夹具。再次执行第 2 节推进片段到 MONITORING，然后**取消 ID1 勾选**，核对操作员停止：

```lua
local m=H3A7_CE_MVP
local w=assert(m.controlled_fixture())
local s=m.status()
assert(s.state=='STOPPED' and s.stop_reason=='OPERATOR_STOP' and s.cleanup_ok and not s.running)
local reads,writes,opens,scans=w.reads,#w.writes,w.open_calls,#w.scans
w.step(200)
assert(w.reads==reads and #w.writes==writes and w.open_calls==opens and #w.scans==scans)
w.clean()
print('operator_stop=true no_post_stop_activity=true cleanup_check_returned=true')
```

ID3 仍为独立一次性只读公开示例；无需先运行它才能启动 ID1，本次不要求重复历史 ID3 人工验收。停止后不自动重扫、重选、附加或恢复。映射故障测试不建立语义存活保证。

## 4. 停止条件、回传与未决事项

文件身份不匹配、模式不符、完整性/身份/计数不一致、取消、评分/访问/操作错误或资源耗尽时停止，不把错误算作 EMPTY/REJECT，不自动换 bounded。cleanup 不确定时停止使用，不绕过 `CLEANUP_UNCERTAIN_RELOAD_CE`。若 CE 无响应，不宣称已完成清理，报告实际状态。

请只回传本候选的脱敏摘要：候选哈希与文件集核对结果；CE 版本、Lua 版本和 No Process Selected；显式 ALPHA_STANDARD/OWNED_SYNTHETIC 选择；实际完成/计数/精确合成身份/Rank-1/建议；模拟写入回读及 native NOT_RUN；映射失败和操作员停止的 cleanup/no-recovery；实际耗时、Lua 占用、UI 观察及 UNKNOWN 项。不要提交私有配置、真实进程身份、原始日志或内存数据。人工接受结论由维护者另行给出。

现有授权范围没有非合成标准输入源，默认因此关闭失败；本次未增加采集或 native writer。工程路径通过显式 `ENGINEERING_BOUNDED` 保留，严格 `QUALIFICATION` 仍要求原 factory/全部门禁，均不属于本人工单执行范围。

`ATTACHMENT_HANDLE_UNVERIFIED`、`QSG_NATIVE_BACKEND_NOT_QUALIFIED`、`NOT_PRODUCTION_AUTHORIZED`、`IMPLEMENTED_PENDING_CE_QUALIFICATION` 全部保留。G1 **0 PASS / 0 FAIL / 1 INDETERMINATE / 11 NOT_RUN**；AC8 >=95% 及原有限域历史 100/100、L01/L12、AC/PAIR、N0/MIN/LOCAL suspension、Generation 2、原资源限制和发布条件不变。native 资格、完整外部采集、全局唯一性、容量/SLA、UI 或语义存活保证均未建立。本任务不发布 Tag、Release、PR，也不自动进入后续任务。
