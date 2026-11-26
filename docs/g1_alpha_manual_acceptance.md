# G1-ALPHA-PREP-3-R1：中文人工验收操作单

## 1. 生效范围修正（2026-11-26）

维护者决定：`APPROVE_G1_ALPHA_PREP_3_R1_REMOVE_MANDATORY_COOPERATIVE_INTERFACE`。以 `f1a3cc2132e41c0b334089e340e774fdcf488dda` 为基线，取消专用应用 exporter、动作/回读 API、生命周期 API 作为 Alpha 架构验收的强制前提。已有协作接口可以使用；接口缺失本身不再构成阻断，也不新增应用 SDK 前提。

产品架构保持 **CE 7.6 + Lua 5.3 + CT**；ID1 是 Start 入口，ID3 保持只读合成评分入口。Python 启动器仅为可选工程工具。R1 使用已有自有受控夹具、全量评分、状态机和接口完成最小集成，不新增启动器、适配器框架、测试框架或研究阶段。

这是后继规格决定，不追溯改写 [PREP-3 操作单](https://github.com/k-undurkhaan-2/Chrome_Project/blob/f1a3cc2132e41c0b334089e340e774fdcf488dda/docs/g1_alpha_manual_acceptance.md)或[历史交付记录](../reports/2026-11-26/g1-alpha-prep-3-delivery.md)。PREP-3 当时是文档交付 `PARTIAL_G1_ALPHA_PREP_3`；PREP-2 包仍是 PREP-2，不能改名充当本次集成版本。

交付状态：**`READY_G1_ALPHA_PREP_3_R1_CONTROLLED_MANUAL_ACCEPTANCE`**，严格限于下述实际 ID1 自有合成夹具候选。源码提交为 `d3aadb33aab01f77bd9e45479975b5421188825c`；包内 CT/Lua 已通过真实 Lua 5.3 的受控执行检查，**本轮尚未在 CE 宿主进行人工验收**。此标记不代表 native 资格、生产许可或发布就绪，不把任一原 G1 行改为 PASS。

## 2. 验收概念与保留门禁

| 独立项目 | 生效标准 |
| --- | --- |
| supplied-population 全量求值 | 所有已提供的 distinct eligible 成员使用现有共同上下文评分和统一排序。核对 supplied = distinct + duplicates、distinct = eligible + excluded、eligible = selected = fully_scored = ranked，以及逐项精确身份成员。这不证明外部采集覆盖所有可能对象。 |
| 结果与错误 | 完整结果才可提议 Rank-1；保留原 scorer、结构资格、cohort、比较器、tie、confidence、recommendation 和 review。空 eligible 的合法 EMPTY 与错误分开。资源耗尽、缺失/不完整输入、取消、评分异常均不成功，不显示旧结果、不伪造 REJECT/EMPTY、不自动退回 bounded。大预算不是 full。 |
| 排名正确率 | 保留 AC8 已登记的计划正向池至少 **95%**、全部完成并核对覆盖的标准及历史 **100/100**。独立 truth 先于评分；Rank-1 正确的 REVIEW 可算命中。不新增 admission-positive 资格条件到排名指标，不重跑准确率活动。 |
| 建议与动作权限 | 高分、ACCEPT、排名人工接受均不授予操作权限。保留 identity、qualification、authorization、recommendation、admission、立即回读和 cleanup 保护。原生 writer 及严格资格合同不变。 |
| 生命周期 | 仅覆盖现有可观察的身份/退出、访问或操作错误。可读地址、PID 存活、值相同都不证明对象语义身份有效。不得新增语义存活算法。 |
| Alpha 停止策略 | 可检测的身份/退出、有效性或操作失败在允许的编排边界停止/报错并清理；不自动重启、重扫、重选、重新附加或恢复。Alpha 外的历史工程恢复行为可保留。新运行需要维护者明确人工启动。 |
| 最终核定 | 维护者依据实际候选人工决定可接受性；这不替代其他强制技术门禁，也不追溯通过历史 G1 行。 |

`ATTACHMENT_HANDLE_UNVERIFIED`、`QSG_NATIVE_BACKEND_NOT_QUALIFIED`、`NOT_PRODUCTION_AUTHORIZED`、`IMPLEMENTED_PENDING_CE_QUALIFICATION` 及适用发布限制继续有效。取消接口前提没有授权扩展外部进程发现、采集、写入、注入、权限或资源上限。第三方应用/游戏不在本次执行范围内。

## 3. 本轮候选与允许执行范围

实际候选目录：`D:\armedforces.io-v2\reports\2026-11-26\g1-alpha-prep-3-r1-manual\`。

打开其中 **`src\ce_mvp.local.CT`**，其 SHA-256 为：

`2e6d3d5403d9ed5f156d313998ef3ac867b4735b77a67b920d8ac34cad5439a8`

[13 文件身份清单及本包 smoke 结果](../reports/2026-11-26/g1-alpha-prep-3-r1-file-identities.json)记录 12 个维护文件的来源提交/Git blob/实际 SHA-256，以及生成 CT 的 SHA-256。[本轮交付记录](../reports/2026-11-26/g1-alpha-prep-3-r1-delivery.md)记录变更、命令、真实失败与修正、签名提交和限制。候选包是独立生成的本地输出；源码和清单已提交，没有发布 Release。不要打开源码目录原有 local CT 或历史 PREP-2 包代替本候选。

依赖仍为 Windows x64 / CE 7.6 / Lua 5.3。包内保留 `src/` 模块、公开 `examples/` 和原有 `tests/fixtures/ce_mvp_mock.lua`；该 fixture 是受控模式的显式依赖，不是新的产品 SDK。Python 只用于现有 `prepare_ce_mvp.py` 的路径绑定，验收启动不需要 Python。生成 CT 绑定绝对路径，移动目录后需用现有准备工具重新生成并重新记录哈希，不能继续沿用本清单。

本候选的 ID1 显式选择 **ALPHA_CONTROLLED**，从同包读取公开合成记录，固定构造既有表数据 CE/Win32 替身，经实际 `ce_mvp.lua` → `ce_mvp_adapter.lua` → `ce_mvp_core.lua` 执行。全量结果由 AC6/AC5 原入口产生；ID1 不调用 ID3。受控构造不读取私有 `ce_mvp_config.local.lua`，不接收外部 CE API 或自定义 writer；普通/严格资格构造仍走原门禁，未接入新的外部 full 能力。

只有夹具表中的模拟读写；真实 operation/readback 为 **UNSUPPORTED / NOT_RUN**，不属于本单可执行人工测试。状态中的 PID、地址、身份 token 和 `write_count` 都是合成模型数据。`action_permitted=false` 和 native NOT_RUN 与模拟写入一次并不矛盾。`global_uniqueness_proven=false` 保留；已提供集合的 full 不证明外部采集完整。

### 3.1 核对并启动实际 ID1

1. 在新的 CE 会话中确认 Lua 为 5.3，保持无目标进程，核对包内文件清单后打开上述生成 CT。不要附加应用或加载私有配置。若有其他安装的 `H3A7_CE_MVP` 单例，重开 CE；不要手工删除保护或切换到 native 模式。
2. 勾选 **ID1 `H3-A7 Start`**。这启动真实编排状态机，初始为 ATTACHING；fixture 的 timer 是表模型，需要下述已有 `step` 控制推进，不会自动执行宿主进程扫描。
3. 在 CE Lua console 执行以下片段。这里的 `step(10)` 是 10 次模拟时钟推进；每步的 50 ms **不是实测耗时**。只把 `getTickCount` 的差值和 Lua 当前占用写入相应观察栏，内存前后值不是进程峰值。

```lua
local m = assert(H3A7_CE_MVP)
local w = assert(m.controlled_fixture(), 'Wrong candidate: controlled fixture required')
local t0, kb0 = getTickCount(), collectgarbage('count')
w.step(10)
local elapsed, kb1 = getTickCount() - t0, collectgarbage('count')
print('measured_step_ms=' .. elapsed .. ' lua_kib_before=' .. kb0 .. ' lua_kib_after=' .. kb1)
local s, e = m.status(), m.evaluation()
assert(e, 'No completed evaluation; record the error and stop')
print('evaluation=' .. e.status .. ' full=' .. tostring(e.population_complete))
for _, k in ipairs({'supplied','distinct','duplicates','eligible','excluded','selected','fully_scored','ranked'}) do
  print(k .. '=' .. e.counts[k])
end
for _, k in ipairs({'supplied','distinct','eligible'}) do
  for i, id in ipairs(e.identities[k]) do print(k .. '[' .. i .. ']=' .. string.format('0x%X', id)) end
end
for i, id in ipairs(e.collection.candidate_value_addrs) do print('selected[' .. i .. ']=' .. string.format('0x%X', id)) end
for i, row in ipairs(e.result.ranked) do print('ranked[' .. i .. ']=' .. string.format('0x%X', row.candidate.value_addr)) end
print(e.result.report_text)
```

评分前独立预期如下，来自公开人工构造夹具，不从本轮结果反推 truth：

| 观察项目 | 独立预期 |
| --- | --- |
| 完成与覆盖 | COMPLETE；completed=true、population_mode=full、population_complete=true；supplied/distinct/eligible/selected/fully_scored/ranked 均为 3；duplicates/excluded 均为 0 |
| 精确成员 | supplied、distinct、eligible、selected、ranked 的成员均为 `0x100128, 0x100328, 0x100528`，无额外或缺失身份；本例排名顺序也相同 |
| 排名与建议 | Rank-1 `0x100128`，得分 46；runner-up -36；ACCEPT/HIGH，manual_review_required=false |
| 原操作边界（模拟） | MONITORING；scan_count=1、write_count=1；last_written_bits=last_readback_bits=`0x42FA0000`（125.0）；替身 native scan 对象数量为 0 |
| 权限与范围 | execution_mode=ALPHA_CONTROLLED、decision_scope=OWNED_SYNTHETIC_FULL、write_admission_basis=SYNTHETIC_ONLY_SCOPE_ACCEPT；action_permitted=false、native_operation_status/native_readback_status=NOT_RUN |
| 停止策略 | lifecycle_policy=ALPHA_STOP_ONLY、automatic_recovery=false；rescan_attempts=0，无 retry_at |

推荐字段和 full 结果可通过 `H3A7_CE_MVP.evaluation()` 检查；它返回副本。ID2 打印状态，`H3A7_CE_MVP.print_evidence()` 打印带 synthetic 来源的现有诊断。它们不能成为真实 native 操作或资格证据。ID3 保持既有只读行为，本任务不要求重复历史 ID3 观察。

### 3.2 观察停止、清理和不恢复

正常到达 MONITORING 后，使用同一公开 fixture 的既有故障字段：

```lua
local m = H3A7_CE_MVP
local w = assert(m.controlled_fixture())
w.objects[1].mapped = false
w.step(4)
local s = m.status()
print('stop=' .. tostring(s.stop_reason) .. ' cleanup_ok=' .. tostring(s.cleanup_ok))
local reads, writes, opens, scans = w.reads, #w.writes, w.open_calls, #w.scans
w.object(0x101128)
w.step(200)
print('no_recovery=' .. tostring(w.reads == reads and #w.writes == writes and w.open_calls == opens and #w.scans == scans))
w.clean()
```

应观察 ERROR、running=false、`ALPHA_STOP:MAPPING_CHANGED`、cleanup_ok=true、candidate_address=nil、rescan_attempts=0、retry_at=nil，以及 no_recovery=true。新增合成替代对象后也不恢复；`w.clean()` 无错误表示原 fixture 所跟踪的 timer/scan/observer/stream/FoundList 已释放。这只是可检测映射失败，不是语义身份算法。

维护者若需分别观察其他边界，每次先取消 ID1 勾选，再明确人工勾选建立新夹具。启动后推进前设置 `w.fail.write_nil=true` 可观察模拟 WRITE_FAILED；设置 `w.fail.write_no_change=true` 可观察模拟 READBACK_MISMATCH。正常运行后设置 `w.alive=false` 可观察 PID_EXITED，设置 `w.creation=w.creation+1` 可观察 PID_IDENTITY_MISMATCH。沿用上面的 `w.step`、状态和清理检查即可；不要求重跑整个 G1 矩阵。清理不确定时停止，不尝试绕过 `CLEANUP_UNCERTAIN_RELOAD_CE`。

另一次明确人工启动到 MONITORING 后，取消 ID1 勾选应得到 STOPPED / OPERATOR_STOP 和 cleanup_ok=true。之后 `w.step(200)` 不应产生新活动。出现错误时保留本轮错误状态；缺失、取消、资源耗尽或评分异常时不能以 `evaluation()==nil` 推断 EMPTY/REJECT，也不能引用上一轮结果。full 完成后因 REVIEW/REJECT 被原操作准入拒绝时，完整排名可以保留，动作仍未执行，两项分别记录。

## 4. 人工验收分别记录

维护者使用交付候选的明确受控模式，逐项记录，不能用一个总 PASS 掩盖未观察项目：

1. full 完成状态、计数等式、精确身份成员及唯一性；输入来源及范围。
2. 评分前独立确定的 Rank-1 truth、实际 Rank-1、命中与否；未知真值写 UNKNOWN。
3. 现有 recommendation、confidence、manual review；与动作授权分开。
4. 实际耗时、资源占用、宿主与 UI 响应性；未测写 UNKNOWN。本任务不建立数值 native 容量或性能 SLA。
5. operation/readback 的模拟边界结果及真实操作 NOT_RUN/UNSUPPORTED 状态；不得混写。
6. 可观察的停止原因、清理结果、停止后是否发生自动重扫/重选/恢复；读取可达性不证明语义有效性。

遇到输入不完整、身份/计数不一致、缺少完成字段、取消、评分/访问/操作异常、内存耗尽或宿主无响应，本轮停止且不得算成功。不自动重试或缩小规模切换模式。私有输入、真实身份及原始运行日志留在本地，不提交。

## 5. 历史证据与未测范围

复用 AC5–AC9、G1-N1/N2 和 PREP-2 的原范围证据。AC8 的 **100/100 Rank-1、48 ACCEPT、52 REVIEW、3/3 独立控制 NO_ACCEPT** 只适用于其有限合成域；AC9 的 103-case 回归和优化不构成本轮新测试。不重跑 100 池、PAIR、L01 或整个 G1 矩阵。

PREP-2 的 66 项离线检查及维护者确认的无目标 ID3 transcript 保留为历史：三条合成记录 COMPLETE、full coverage、精确身份匹配、Rank-1 **46**、runner-up **-36**、ACCEPT/HIGH、action_permitted=false、automatic_recovery=false。它们不证明 ID1 集成、真实动作/回读或 Alpha 停止行为。

原生 2000/20 默认与 65536/128 验证范围不是 CE 整体容量；历史离线 256 MiB、4 GiB/8 GiB 限制也不是 CE 配置或 native 需求。本轮不提高资源限制。同步 Lua 调用的取消响应、CE allocator、硬超时及 UI 响应性只按实际观察报告。

G1 保持 **0 PASS / 0 FAIL / 1 INDETERMINATE / 11 NOT_RUN**。L01、L12、AC/PAIR、N0/MIN/LOCAL suspension 和 Generation 2 不变。Alpha Pre-release 发布条件仍未满足；本任务不创建 Tag、Release、PR、新分支或自动后续任务。
