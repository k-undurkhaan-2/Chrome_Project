# 标准 Alpha 候选：安装与受控使用说明（预发布准备）

本说明对应已有的 **ALPHA_STANDARD / ALPHA_FULL 自有合成评估候选**。
工程准备材料可供审阅，发布资格仍为 **NOT ESTABLISHED / BLOCKED**。
当前标准完整路径只实现显式 `OWNED_SYNTHETIC` 输入；普通预配置目标工作流、
非合成完整采集及原生操作尚未交付，不能把本候选当作完整原生产品。

本次仅整理文档，不执行或安排人工/有效性测试。维护者独立安排有效性验收。
候选专属的完整步骤继续以[现有标准人工验收单](g1_alpha_integration_1_manual_acceptance.md)为准；
本说明不扩大其授权，也不提供真实目标操作方法。

## 候选与安装位置

| 项目 | 固定身份或要求 |
| --- | --- |
| 环境 | Windows x64，CE 7.6 / Lua 5.3；受控使用保持 **No Process Selected** |
| 已有候选目录 | `D:\armedforces.io-v2\reports\2026-11-26\g1-alpha-integration-1-manual-final` |
| 装载文件 | 上述目录中的 `src\ce_mvp.local.CT`，3003 字节 |
| CT SHA-256 | `023ed8e3d1a41841b3f22e826a55f2e23f3860d2ef73c6859079123d4797f4d6` |
| 可执行源码提交 | `6190a9f93ec72560ca5db5e616bc4cd411795efc` |
| 原候选交付提交 | `603f3b420e7fefe027981aa64f6c2f0d2a7c7e7e` |
| 完整身份依据 | [13 文件清单](../reports/2026-11-26/g1-alpha-integration-1-file-identities.json)；人工单第 1 节含完整文件集、长度和哈希核对命令 |

这里的“安装”是保留已有候选目录并装载其本地 CT，没有新增安装器。
先按人工单核对全部 13 个文件，不能只看 CT 文件名。维护源码中的 `src/ce_mvp.CT`
是模板，候选目录里的 `src/ce_mvp.local.CT` 才是已绑定路径的产物。
准备时只使用原有 Python 工具，运行这个受控候选不需要 Python、SDK、额外启动器或目标应用。

CT 包含绝对路径，**该哈希不能移植到其他安装位置**。不要移动目录后沿用原身份，
不要在本次准备中重新生成或覆盖候选。若文件缺失、路径变化或哈希不符，停止使用并交由维护者处理。
先前的 `g1-alpha-integration-1-manual` 已被最终结果检查修复后的 `manual-final` 替代；
历史 PREP-3-R1 包、源码目录原有 local CT 和自动保存 CT 都不能替代本候选。

## 已有受控范围内的使用顺序

维护者决定使用现有人工单时，按其原步骤操作；下面仅说明入口关系，不要求重新执行已完成的测试。

1. 使用新的 CE 7.6 会话，核对 Lua 5.3、无既有 `H3A7_CE_MVP` 单例且保持
   **No Process Selected**。装载上述固定 CT，ID1、ID2、ID3 初始均不勾选。
2. 按人工单第 2 节的原 Lua 片段，通过已有 `configure_execution` 显式选择
   `mode='ALPHA_STANDARD', input_source='OWNED_SYNTHETIC'`。此选择本身不启动或评分。
3. 只有显式勾选 **ID1 Start** 才启动已有自有表夹具的完整求值和模拟编排。
   具体夹具推进、结果核对、映射故障与操作员停止片段继续引用人工单，不增加测试场景。
4. **ID2 Status** 观察缓存状态，不重新评分或发起目标活动。
   **ID3 READ ONLY** 是独立的一次性公开合成示例，不是 ID1 的前置步骤；无需重复历史 ID3 验收。
5. 取消 ID1 勾选是明确停止。Alpha 使用 `ALPHA_STOP_ONLY`，可检测失败后停止并清理，
   不自动重扫、重选、重新附加或恢复；新运行需要明确人工 Start。

未显式选择允许输入时，默认 Start 返回 **`ALPHA_INPUT_REQUIRED`** 并保持无动作。
不要为消除此提示而选择真实进程、填写私有配置、删除单例、绕过模式锁或切换其他模式。
若先误启动，按原人工单重开 CE 后正确选择输入。现有工程和资格模式不属于本说明的替代路径。

## 结果含义与停止条件

“full”只表示已提供的 distinct eligible 成员完整评分和统一排序，必须同时核对精确身份及
`supplied = distinct + duplicates`、`distinct = eligible + excluded`、
`eligible = selected = fully_scored = ranked`。它不证明外部采集完整性或全局唯一性。
`scan_mode_domain=configured_address_scope` 与 `scoring_mode=full` 是不同维度。
原有分数、排序、confidence、recommendation、review 和动作准入要求全部保留。

模拟写入/回读仅发生在自有表夹具中；`action_permitted=false`，
native operation/readback 为 **UNSUPPORTED / NOT_RUN**。ACCEPT、高分、排名正确或历史人工 PASS
均不授予真实目标操作权限。合法 EMPTY、完成后的 REVIEW/REJECT 与错误必须区分。

身份/文件不一致、缺失或不完整输入、计数不符、取消、评分或访问/操作失败、资源耗尽时停止，
不将错误改成成功 EMPTY/REJECT，不显示旧成功结果，也不自动改用 bounded。
清理不确定时保留 **`CLEANUP_UNCERTAIN_RELOAD_CE`**，不得绕过；CE 无响应时不能宣称清理成功。
ID3 为同步执行，取消勾选不等于中途取消。UI 响应、进程峰值、取消延迟、硬超时、容量/SLA
和语义存活保证均未由本次准备建立；未测项保持 UNKNOWN/NOT_RUN。

## 验收与发布状态

| 独立事项 | 当前状态 |
| --- | --- |
| 文件身份与准备材料 | 13 文件、12 源码 blob 及同路径 CT 渲染一致；本次只做只读完整性/文档检查 |
| 历史自动证据 | 复用标准最终 349 passed 和已记录包验证；较早通过集合有重叠，不能相加 |
| 历史 PREP-3-R1 M6 | 已登记限定 PASS，仅对应原候选，不转移到当前标准候选 |
| 当前标准候选 CE 人工验收 | **NOT_RUN / NOT_ESTABLISHED** |
| 独立产品有效性验收 | **NOT_RUN / NOT_ESTABLISHED**；维护者自行安排 |
| 原生资格及发布 | **NOT ESTABLISHED / BLOCKED**，另需适用技术条件和独立维护者决定 |

`ATTACHMENT_HANDLE_UNVERIFIED`、`QSG_NATIVE_BACKEND_NOT_QUALIFIED`、
`NOT_PRODUCTION_AUTHORIZED`、`IMPLEMENTED_PENDING_CE_QUALIFICATION` 全部有效。
G1 保持 **0 PASS / 0 FAIL / 1 INDETERMINATE / 11 NOT_RUN**；AC8 >=95% 及原有限域
100/100、AC/PAIR、L01/L12、N0/MIN/LOCAL suspension、Generation 2 和原资源限制不变。
旧 P4-R2 发布前提与本候选范围的对应关系也未被本次准备豁免。

完整条件、证据来源、负责人和版本建议见[预发布就绪清单](../reports/2026-11-26/g1-alpha-pre-release-prep-1-readiness.md)。
`v2.0.0-alpha.1` 只是未来命名建议，未设为版本、Tag 或 Release。
不分发包，不提交私有配置、真实目标标识、原始日志或签名材料；维护者仅依据绑定到实际候选的证据另行决定接受和发布。
