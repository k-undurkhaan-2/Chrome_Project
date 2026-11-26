# G1-ALPHA-PREP-3：实际交付范围与中文人工验收操作单

交付状态：**`PARTIAL_G1_ALPHA_PREP_3`**。维护者已批准首期集成，并在接口核查后明确选择「按已确认缺口交付 PARTIAL」。当前没有可供 ID1 全量产品验收的新集成候选；可核验的实际 CE / Lua / CT 代码仍为批准基线 `3a8fa0876fcb0e972af6e657693948207484ec86`。本次更新操作单及事实记录，未改运行代码，也不把既有 ID3 只读功能算作 ID1 集成。

本单取代此前的当前操作指引。[PREP-2 原操作单](https://github.com/k-undurkhaan-2/Chrome_Project/blob/3a8fa0876fcb0e972af6e657693948207484ec86/docs/g1_alpha_manual_acceptance.md)和[原交付记录](../reports/2026-11-26/g1-alpha-prep-2-delivery.md)保留为历史。其「CE 观察尚未运行」是当时的状态；维护者后来提供并确认了下文所列的有限正向观察。本任务不重跑该观察或历史测试。

## 1. 当前可用功能与确切缺口

| 项目 | 已核实的当前行为 | 本期验收状态 |
| --- | --- | --- |
| CT ID1 `H3-A7 Start` | 经 `ce_mvp.lua` 构造原生 `ce_mvp_adapter.lua`，使用 CE/Win32 附加、扫描、读取、写入和回读，仍使用原有有界候选策略 | **BLOCKED**：未连接获准的应用协作接口与 AC6 full；本单不要求启用 ID1 |
| 全量评分 | AC6 显式记录入口调用 AC5，保留原评分、完整共同 cohort、排序、建议和 review 字段 | **已有合成数据能力**；不证明应用完整导出或 ID1 集成 |
| CT ID3 | `ce_mvp_readonly.lua.run_example()` 一次同步求值公开三条合成记录，仅提议完成结果的 Rank-1 | **保留只读工程观察入口**；已有有限人工正向证据，本次不再执行 |
| 协作动作及回读 | 未找到已建立并文档化的所有者授权应用动作/回读接口；原生 writer 仍是 CE `writeFloat` | **UNSUPPORTED / NOT_RUN**；ACCEPT 不授予动作权限 |
| 应用身份、退出、对象有效性 | 未找到对应的应用生命周期接口；原生 PID/创建时间、映射和字段检查不是应用对象语义证明 | **UNSUPPORTED / NOT_RUN** |
| Alpha 停止且不恢复 | 原核心在零候选或确认失效时仍进入 `RESCAN_BACKOFF`；身份异常等终止路径及清理保护保留 | **未集成**；既有工程恢复行为未更改，不能标成 Alpha 不恢复模式 |
| 严格资格及资源保护 | 原 NORMAL 与 QUALIFICATION 区别、资格/身份/准入/回读/清理保护及预算保持原样 | **未放宽**；不是产品资格通过或发布许可 |

阻塞涉及三个必要接口：**可证明来源与完整性的自有应用有限记录导出；绑定身份且保留所有现有准入条件的协作动作/回读；报告退出、身份变化、对象无效和访问/操作失败的生命周期接口**。AC6 接收器只处理传入表，不实现这些接口；QSG 和 handoff 合成模型也不能替代它们。代码定位见[本期交付记录](../reports/2026-11-26/g1-alpha-prep-3-delivery.md)。

当前停在文件与事实核对，不启动 CE、不附加进程、不进行目标读写。不存在通过配置开关即可启用的 PREP-3 full 产品模式；不要把 `population_mode` 填入原生配置、提高候选预算、删除准入条件或改用 ID3 来填补集成缺口。

## 2. 实际文件、版本、依赖与当前操作

维护源码位于 `D:\armedforces.io-v2\src\`：

| 文件 | 用途 |
| --- | --- |
| `ce_mvp.CT` | 实际 CT 模板；ID1 Start、ID2 Status、ID3 只读示例 |
| `ce_mvp.lua`、`ce_mvp_core.lua`、`ce_mvp_adapter.lua` | 既有产品 loader、状态机及原生适配器，本期不执行 |
| `mvp0_foundlist_collector.lua`、`mvp0_offline_scoring.lua`、`mvp0_candidate_report.lua` | 原 AC6 / AC5 和评分实现，未修改 |
| `ce_mvp_readonly.lua`、`examples/g1_alpha_population.example.lua` | 既有 ID3 模块及公开合成示例，未修改 |
| `prepare_ce_mvp.py` | 既有离线路径绑定工具，本期没有运行或重新生成 CT |

保留的实际文件包：

`D:\armedforces.io-v2\reports\2026-11-26\g1-alpha-prep-2-manual\src\ce_mvp.local.CT`

该 CT 的 SHA-256：`c7d93bd95b6830d59f279b5db164593cc645348ce7283d484d3adfb93f94da4a`。

完整的 11 文件 SHA-256 清单位于同包上级的 `file-identities.json`。本期已逐项重新计算并匹配清单，10 个维护文件逐字节匹配当前源码，Git 内容身份也匹配批准基线；生成 CT 的 ID1/ID3 绝对路径绑定与模板一致。未覆盖工作区原有 `src/ce_mvp.local.CT`、私有配置或任何既有包。**这个包仍是 PREP-2 包，不是新 ID1 集成版本。**

既有宿主依赖为 Windows x64 / CE 7.6 / Lua 5.3；本期没有启动这些组件。Python 只用于既有工程工具和本期静态文件核验，不是产品启动器。生成 CT 必须保留同目录模块及 `examples/`，其绝对路径绑定不能在移动后继续沿用。公开包没有 `ce_mvp_config.local.lua`，也没有应用协作接口配置。不要复制其他会话的私有配置、PID、地址或授权来尝试启动 ID1。

维护者当前的文件核对步骤：

1. 核对本任务最终给出的文档提交 SHA、父提交和 GitHub 有效签名；运行代码身份仍为上述基线。
2. 执行下面的只读命令，与本单哈希及已有清单对照。
3. 将 ID1、动作/回读、生命周期及本期性能观察分别记录为 BLOCKED、UNSUPPORTED 或 NOT_RUN；到此停止，不打开 CT 或重复 ID3 观察。

```powershell
Get-FileHash -Algorithm SHA256 -LiteralPath 'D:\armedforces.io-v2\reports\2026-11-26\g1-alpha-prep-2-manual\src\ce_mvp.local.CT'
Get-Content -LiteralPath 'D:\armedforces.io-v2\reports\2026-11-26\g1-alpha-prep-2-manual\file-identities.json' -Raw
```

## 3. 已有观察的准确范围

根据本任务文档记录，维护者已提供实际 CE console transcript，并确认指定 CT、无目标进程、仅 ID3 的条件。三条合成记录正向观察显示：`COMPLETE`、full coverage、与预期精确匹配的合成身份、Rank-1 得分 **46**、runner-up 得分 **-36**、`ACCEPT/HIGH`、`action_permitted=false`、`automatic_recovery=false`。保留这一有限正向结论，不要求再次执行。

本期没有重新运行或独立重演该 transcript。其证明范围不延伸到未观察的 AA Boolean 返回值、失败控制、空集/无效预算人工步骤、大池、动作/回读、生命周期或停止测试。ID3 无恢复循环也不能证明 ID1 满足本期停止要求。PREP-2 的 66 项离线检查及原文件包 smoke 是历史证据，不计作本期新测试。

AC8 的 **100/100 Rank-1、48 ACCEPT、52 REVIEW、3/3 独立控制 NO_ACCEPT** 继续限于其有限合成域；AC5/AC6 全量合同及 AC9 的 103-case 回归和离线转换优化也作为历史证据保留。它们都不是原生准入、应用完整性或动作许可。

## 4. 接口齐备后才能进行的人工验收项目

下表是未满足前提的验收记录要求，**不是当前可执行的 ID1 步骤，也不请求重跑历史活动**。只有既有接口被明确提供、实际 ID1 集成完成、全部现有门禁可满足并取得维护者相应决定后，才能给出与该实现对应的启动步骤；本任务不假设接口或模拟结果已经存在。

| 独立项目 | 模式、来源和独立预期 | 必须观察和记录 | 当前状态 |
| --- | --- | --- | --- |
| supplied-population 全量求值 | 明确 full；仅自有授权接口提供的有限记录；所有者在求值前独立确定成员、资格判定和预期 Rank-1，truth 不参与评分 | supplied = distinct + duplicates；distinct = eligible + excluded；eligible = selected = fully_scored = ranked；逐一核对身份成员、唯一性、排名和完整报告。共同全量上下文不得被独立批次赢家替代 | ID1 接口缺失，BLOCKED |
| 结果与错误 | 只接受本轮完整结果；唯一提议为完成结果的 Rank-1，保留原建议和 review 字段 | 空 eligible 集为 EMPTY/普通 REJECT；非空普通 REVIEW/REJECT 仍可为 COMPLETE；错误/取消/不完整结果不得伪装 EMPTY、旧结果或 bounded 回退；full 仍禁止两个 count-budget 字段 | 本期未运行新行为，NOT_RUN |
| 正确率 | 保留预先声明且可评价正向域的 **>=95%** Rank-1 标准，独立预期先于评分 | 正确 Rank-1 + REVIEW 可算命中；未知真值不能算命中。无效/未完成/未尝试保留计划分母；另报完成池正确率；控制域独立报告 NO_ACCEPT。小型人工观察不构成新独立准确率活动 | 重用 AC8 有限域结论，不启动新 campaign |
| 耗时、内存、响应性 | 记录实际宿主、输入规模及测量口径，不添加数值 SLA | 维护者记录实际耗时/内存和 UI 体验并决定可接受性；没有测量就写 UNKNOWN。排名通过不能替代响应性通过 | 未测，UNKNOWN |
| 动作与回读 | 文档化协作接口、身份绑定、既有独立资格及全部动作门禁先成立 | 原建议不授予权限；记录实际动作、立即回读和保护结果，保持 ownership/cleanup 约束；任一门禁不足则不执行 | UNSUPPORTED / NOT_RUN |
| 生命周期与停止 | 应用提供身份、退出、对象无效及操作失败报告；独立记录事件来源 | 报告退出/身份变化/对象无效、检测到访问或操作失败、或无法确立必要条件时停止；保留停止原因及清理诊断。停止后不得自动重试、扫描、重新选择、附加或启动；新运行需明确人工决定 | UNSUPPORTED / NOT_RUN |

supplied-population 成员及计数完整，只证明**已提供集合**的覆盖，不证明应用导出/采集完整。PID 仍在、存储可读或值相同，也不能证明对象身份和语义有效性。发生不确定状态、身份/计数不一致、缺失完成字段、内存耗尽或宿主无响应时，本轮不得算成功；保存最小事实并停止，不自动重试或缩小规模转模式。

## 5. 资源边界、回报与保留状态

数量、内存、耗时、响应性和输出策略分别记录。原生默认 2000/20、验证范围 65536/128 是原工程配置，不能称为 CE 整体容量上限。AC5/AC6 full 是全部 eligible 或明确不成功，没有任意规模承诺。ID3 为同步 Lua 调用，取消勾选不提供抢占式取消；CE 的 full allocator 上限、硬超时和可接受响应性仍未建立，不能隐藏截断候选、报告或核验字段来制造通过。

小型离线夹具的 256 MiB Lua 上限曾不足以承载部分 18,498–20,000 条历史输入；4 GiB Lua / 8 GiB 采样 worker 是历史离线测试上限，均不是 CE 设置或测得的原生需求。本期没有提高预算或资源限制，没有新增 worker、supervisor、测试框架、启动器或只读替代入口。

维护者本次只需回报：文档提交与文件身份是否匹配、是否接受本单的 PARTIAL 范围、仍缺少哪些既有接口。未来独立人工验收如获准，最少回报模式和脱敏来源、预先确定的独立预期、本轮计数与成员核对结论、Rank-1/建议/review、实际耗时/内存/响应性、动作及回读状态、生命周期事件及停止/清理诊断、有无自动恢复、各项 NOT_RUN/UNKNOWN 和本地证据路径。私有输入、真实身份及原始日志留在本地，不提交。

本期未启动 CE、运行目标、生产测试或任何历史测试。G1 历史汇总保持 **0 PASS / 0 FAIL / 1 INDETERMINATE / 11 NOT_RUN**；L01、前瞻性修正 L12、AC/PAIR 结论、严格资格/附加限制及 N0/MIN/LOCAL suspension 不变。保留 `IMPLEMENTED_PENDING_CE_QUALIFICATION`、`ATTACHMENT_HANDLE_UNVERIFIED`、`NOT_PRODUCTION_AUTHORIZED`、`QSG_NATIVE_BACKEND_NOT_QUALIFIED` 和 Alpha Pre-release BLOCKED。

最终人工验收及任何替代既有发布条件的决定由维护者另行记录，不追溯改写历史 PASS。本任务不创建 Tag、Release、新分支或 PR，也不自动发布或启动后续阶段。
