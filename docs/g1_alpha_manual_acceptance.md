# G1-ALPHA-PREP-3-R1：中文人工验收操作单

## 1. 生效范围修正（2026-11-26）

维护者决定：`APPROVE_G1_ALPHA_PREP_3_R1_REMOVE_MANDATORY_COOPERATIVE_INTERFACE`。以 `f1a3cc2132e41c0b334089e340e774fdcf488dda` 为基线，取消专用应用 exporter、动作/回读 API、生命周期 API 作为 Alpha 架构验收的强制前提。已有协作接口可以使用；接口缺失本身不再构成阻断，也不新增应用 SDK 前提。

产品架构保持 **CE 7.6 + Lua 5.3 + CT**；ID1 是 Start 入口，ID3 保持只读合成评分入口。Python 启动器仅为可选工程工具。R1 使用已有自有受控夹具、全量评分、状态机和接口完成最小集成，不新增启动器、适配器框架、测试框架或研究阶段。

这是后继规格决定，不追溯改写 [PREP-3 操作单](https://github.com/k-undurkhaan-2/Chrome_Project/blob/f1a3cc2132e41c0b334089e340e774fdcf488dda/docs/g1_alpha_manual_acceptance.md)或[历史交付记录](../reports/2026-11-26/g1-alpha-prep-3-delivery.md)。PREP-3 当时是文档交付 `PARTIAL_G1_ALPHA_PREP_3`；PREP-2 包仍是 PREP-2，不能改名充当本次集成版本。

当前提交落实范围修正；R1 代码集成与候选包尚待本轮实际验证后填写。不得据此把任一原 G1 行改为 PASS。

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

当前允许的集成/验证仅限无目标的显式自有合成记录及现有受控 test doubles。必须从实际 ID1 loader/状态机路径验证，不能以独立 ID3 示例替代。动作/回读边界可以通过既有合成设施验证，但不得转发真实目标写入；模拟结果不是 native write/readback 证据。原生动作未经资格或授权时，人工项目写 **UNSUPPORTED / NOT_RUN**。

本轮集成完成后，本节填写真实 CT/Lua 候选路径、提交、文件身份、依赖、启动步骤、独立预期及停止条件。在此之前不得启用原生 ID1 配置来冒充 R1 full 模式，不覆盖原有 local CT、私有配置或历史包。

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
