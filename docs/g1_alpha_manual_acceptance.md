# G1-ALPHA-PREP-2：CE / Lua / CT 只读全量评分人工操作单

交付状态：`READY_G1_ALPHA_PREP_2_CE_CT_READONLY_MANUAL_ACCEPTANCE`。已实现 **CT 显式调用 → Lua 宿主模块 → 原有 AC6 → 合成记录全量评分、Rank-1 提议及普通报告**。这表示候选已可供人工验收；实际 CE 宿主观察尚未运行，维护者决定是否接受此只读范围。整体 Alpha Pre-release 仍为 BLOCKED。

维护者批准：`APPROVE_G1_ALPHA_PREP_2_CE_CT_HOSTED_SCORING`。实现提交为 `b86c226e2b0b90f3da2ebf79fcafc1f595c996c1`，直接父提交为批准基线 `f67c2b1ab619b4a03fa6e8ce055ea4a3fe3b5b5b`；签名、父链和远端分支已独立核验。测试及完整文件身份见[交付记录](../reports/2026-11-26/g1-alpha-prep-2-delivery.md)。

## 1. 使用哪些文件

| 维护文件 | 用途 |
| --- | --- |
| `src/ce_mvp.CT` | 实际 CT 模板，新增 ID 3 只读入口；原有 ID 1/2 保留 |
| `src/prepare_ce_mvp.py` | 现有离线准备机制，生成与同目录 Lua 绑定的 `ce_mvp.local.CT` |
| `src/ce_mvp_readonly.lua` | 新只读宿主模块，提供 `run_example()` 与 `evaluate(records, options)` |
| `src/examples/g1_alpha_population.example.lua` | 与已有 JSON 示例相同的三条公开人工记录，无 truth 标签 |
| `src/mvp0_foundlist_collector.lua`、`src/mvp0_offline_scoring.lua`、`src/mvp0_candidate_report.lua` | 原有 AC6、AC5 和评分核心，算法行为不变 |
| `src/ce_mvp.lua`、`src/ce_mvp_core.lua`、`src/ce_mvp_adapter.lua` | 模板保留的原生路径依赖，未改动；本次验收不调用 |

本机已生成独立公开文件包，保留了原来 `src/ce_mvp.local.CT` 和私有配置。人工验收只打开：

`D:\armedforces.io-v2\reports\2026-11-26\g1-alpha-prep-2-manual\src\ce_mvp.local.CT`

该文件 SHA-256：`c7d93bd95b6830d59f279b5db164593cc645348ce7283d484d3adfb93f94da4a`。同目录所有 Lua 和 `examples/` 必须一起保留；完整清单为上级目录的 `file-identities.json`。生成 CT 绑定绝对路径，移动文件包后必须重新运行包内 `prepare_ce_mvp.py`，CT 哈希也会相应变化。其他平台的检出换行方式可能改变文件字节哈希，应重新记录本地身份。

如在另一检出目录准备，复制上表全部维护文件到一个新建的专用目录，保持 `examples/` 相对结构，再用已有 Python 执行该目录内的 `prepare_ce_mvp.py`。它只生成 CT，不启动 CE、不运行评分。不要覆盖已有人工作业使用的生成 CT；无需复制或提供任何 `.local.lua` 私有配置。

## 2. 前提和唯一 CT 操作

使用 **Windows x64 CE 7.6 / Lua 5.3**，开启一个全新、专用且没有目标进程的 CE 会话。该版本组合是人工验收要求，本次自动验证使用的是 Lupa 中真实 Lua 5.3，并非 CE。无需目标 PID、原始地址、游戏数据或任何私有配置。

1. 先核对上述 CT 路径、SHA-256、实现提交和同目录模块。可用 `Get-FileHash -Algorithm SHA256 -LiteralPath '上述完整 CT 路径'`。
2. 手动打开该生成 CT，打开 CE 的 Lua Engine 输出窗口。表中所有记录均应未激活；加载本身不应产生新评分结果。
3. **只勾选 ID 3：`G1 Full population - READ ONLY synthetic example (check once; uncheck is inert)`。** 保持 ID 1 `H3-A7 Start` 和 ID 2 `Status` 未选中；不附加任何进程，也不使用扫描、写入或其他原有动作控件。
4. 记录这一轮从 `[G1-READONLY] invocation=BEGIN` 到最终 `invocation=COMPLETE` 的输出。普通报告保留原貌；ACCEPT 或报告中的 “direct use” 等历史措辞均不授权动作。
5. 调用结束后取消勾选 ID 3。取消勾选不再评分，也不是运行期间的取消按钮；本入口没有定时器或恢复循环。再次勾选是另一次人工请求，不是自动续跑。

若 CE 要求选择目标、触发原生 Start，或出现与预期不符的访问/动作，立即停止本轮验收并报告实际情况。这里没有安装额外 CE 插件或运行历史 L01 的步骤。

## 3. 应观察什么（以下全部是预期，不是 CE 实测）

| 项目 | 三条公开记录的预期 |
| --- | --- |
| 状态 | `scope=OWNED_SYNTHETIC_TABLES_READ_ONLY`，`state=COMPLETED_READ_ONLY` |
| 完成性 | `status=COMPLETE`，`completed=true`，`population_mode=full`，`population_complete=true` |
| 计数 | supplied / distinct / eligible / selected / fully_scored / ranked 均为 3；duplicates / excluded 为 0 |
| 身份序列 | supplied、distinct、eligible、selected、ranked 均为 `0x100128,0x100328,0x100528`；检查成员及唯一性，不能只看计数 |
| Rank-1 | `proposed_rank1=1048872`（即人工身份 `0x100128`），普通报告得分 46 |
| 原始建议 | `ACCEPT`、`HIGH`、`manual_review_required=false`，保留完整普通报告 |
| 权限与能力 | `action_permitted=false`、`automatic_recovery=false`；action/lifecycle 为 `UNSUPPORTED...`，`semantic_validity=UNVERIFIED_SYNTHETIC_SNAPSHOT_ONLY` |
| 本轮结束 | 最后一行含 `invocation=COMPLETE; recommendation grants no action authority` |

`addr`、`memory` 及这些数值只是沿用 AC5/AC6 数据结构的人工身份和字典内容，不读取任何外部进程。此小示例已在离线 Lua 下观察到上述结果；实际 CE 是否输出一致仍需人工记录。勾选状态不是成功证据，源代码检查和 Lua chunk 执行也不能证明 AA Boolean 返回值。

## 4. 小型空集／拒绝观察与停止条件

以下可选人工步骤只在同一个无目标专用 CE 的 Lua Engine 中执行，使用交付包内模块和空合成记录。不要操作原生 Start，也不要为延长运行扩大数据规模。

<!-- G1 CE empty example -->
```lua
local m=dofile([[D:/armedforces.io-v2/reports/2026-11-26/g1-alpha-prep-2-manual/src/ce_mvp_readonly.lua]])
local outcome=m.evaluate({}, {population_mode='full', target_value_pattern=0x42C80000})
print(outcome.evaluation.status, outcome.evaluation.result.recommendation.recommendation,
  outcome.proposed_rank1, outcome.action_permitted)
print(outcome.evaluation.result.report_text)
```

预期为空集 `EMPTY`、普通 `REJECT`、无 Rank-1（nil）、不允许动作（false）；eligible/selected/fully_scored/ranked 均为零。`evaluate` 返回完整结果而不自行打印。它无缓存；操作者自行保存的变量不能作为下一轮失败的结果。

<!-- G1 CE invalid example -->
```lua
local m=dofile([[D:/armedforces.io-v2/reports/2026-11-26/g1-alpha-prep-2-manual/src/ce_mvp_readonly.lua]])
local ok, cause=pcall(function()
  return m.evaluate({}, {population_mode='full', target_value_pattern=0x42C80000, scan_budget=1})
end)
print(ok, cause)
```

预期 `ok=false`，原错误含 `OFFLINE_INVALID_OPTIONS: full mode forbids count budgets`；无成功结果、Rank-1 或重试。这里的 `ok` 是 Lua `pcall` 返回值，不是 AA 返回值。`max_candidates` 在 full 模式也被禁止，含 false/0 等取值；不得删除模式声明来回退。

| 条件 | 必须如何记录／停止 |
| --- | --- |
| 文件缺失、数据/模式无效、AC6 完成性不足、评分/报告异常 | 原错误抛给宿主；本轮失败，不能称 EMPTY/REJECT，不能复用上一轮结果 |
| BEGIN 后无完整结果或没有最终 COMPLETE | 未成功；停止验收，报告可见错误与缺失字段，不能据旧输出补齐 |
| 内存耗尽、宿主中断、窗口无响应 | 本轮失败或未完成；按普通人工方式退出专用 CE 会话，不自动重试、缩小输入或转 bounded。无法观察到取消时记 NOT_RUN |
| 操作者取消勾选 | 仅在控制权返回后清除勾选；不承诺抢占同步 Lua 调用，不代表已验证取消保护 |
| 自有应用退出、重启、对象失效或动作失败 | 本入口无对应协作接口，记 UNSUPPORTED，不能把文件可读或排名成功当作对象语义有效 |

只要出现异常、身份/计数不一致、结果不完整或未知状态，就保留事实并停止本轮，不自动进入其他阶段。

## 5. 运行边界与已有 Python 辅助工具

新宿主入口直接在 CE Lua 5.3 内同步执行；只读取显式提供的有限合成表，固定白名单加载同目录三个既有模块。公开示例通过空环境加载，不能访问宿主 API。对其他自有记录，可由所有者在受信任的本地 Lua 调用中显式传给 `evaluate(records, options)`；输入格式及成员核对沿用 [AC5/AC6 合同](algorithm_a_offline_scoring.md#raw-ac5-api-and-shared-contracts)。只读入口要求明确 full；原有 AC6 bounded 工程接口和原生 `scan.mode` 的含义不变。

**尚未实现**：应用内导出器、协作动作/回读接口、应用身份与退出接口、语义对象有效性判断，以及新入口的抢占取消或生命周期闭环。没有采集外部数据、任意进程地址输入端口、后台 worker/supervisor、PID 监控或自动恢复。也没有为 CE 建立 allocator 上限、硬超时、输出限制或可用提交量监督；没有已证实的 CE 容量／延迟 SLA。这些缺口不允许通过静默截断、提高限制或误报成功掩盖。

本次小型自动测试沿用 **256 MiB Lua allocator** 的现有测试环境；只验证三条记录和小型异常场景，不代表 CE 也有该保护或可支持 18,498–20,000 条。F1 已证明旧 256 MiB 配置在受测 worker 上不支持相应大池。AC8/AC9 的 4 GiB Lua、8 GiB 采样 worker 及既有时间/输出/宿主资源限制仅是历史离线测试包络，不能转移成原生 CE 保证。

原有 `src/run_alpha_candidate.py` 和 JSON 示例原样保留为辅助工具。已有 `.venv` 可执行：

```powershell
.\.venv\Scripts\python.exe -B .\src\run_alpha_candidate.py --input .\src\examples\g1_alpha_population.example.json --lua lua53
```

Python 的输入 8 MiB、Lua 256 MiB、输出 256 MiB 和 240 秒协作 deadline 不变；它也没有大池容量保证。其 PREP-1 历史说明和验证见[原交付记录](../reports/2026-11-26/g1-alpha-prep-1-delivery.md)。本次没有修改或重复运行该启动器。

## 6. 人工回报与保留状态

维护者回报以下必要摘要即可，原始日志保留本地 `reports/当天日期/` 的独立目录，不提交日志、私有输入或失败转储：

- 检出 commit、生成 CT 完整路径及哈希、实际 CE 版本、Lua `_VERSION`，是否为全新无目标会话。
- 仅 ID 3 被调用的操作记录；输入来源为本公开三条记录；独立预期与实际字段对照。
- 当前调用的完成标记、计数、全部身份成员、Rank-1、得分、原建议和 review 标志。
- 成功、空集、无效预算各自实际观察或 NOT_RUN；停止原因、是否出现任何再次求值，以及本地证据路径。
- AA 返回值只有实际观察到才能报告；未观察就明确 NOT_RUN，不用离线 Lua 的结果替代。

本次 Codex 实际完成了 66 项针对性离线检查和生成文件包的三条记录 smoke；**CE 宿主运行、AA 返回值及上述人工步骤均 NOT_RUN**。没有重复 AC8、F2/F3、AC9、G1-N1/N2、PAIR、L01 或全 G1 矩阵。

保留历史 AC/PAIR 结论；AC8 的 100/100 只适用于其有限合成域，AC9 只优化离线 worker。G1 仍为 **0 PASS / 0 FAIL / 1 INDETERMINATE / 11 NOT_RUN**，L02–L12 不解暂停。`IMPLEMENTED_PENDING_CE_QUALIFICATION`、`ATTACHMENT_HANDLE_UNVERIFIED`、`NOT_PRODUCTION_AUTHORIZED`、`QSG_NATIVE_BACKEND_NOT_QUALIFIED`、`HISTORICAL_ROOT_CAUSE=INDETERMINATE`、N0/MIN/LOCAL publishing suspension 和 Alpha Pre-release BLOCKED 均不变。没有 Tag、Release、新分支或 PR；Generation 2 独立，后续阶段不自动启动。
