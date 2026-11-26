# G1-ALPHA-PREP-1：只读候选版本与人工验收操作单

交付状态：`PARTIAL_G1_ALPHA_PREP_1`。可运行的部分是**自有程序显式提供的有限表数据快照 → AC6 全量评分 → Rank-1 提议及普通报告**。本次没有应用级操作/回读闭环，也没有应用进程身份、退出或对象有效性的在线接口。相关项目必须记为 `UNSUPPORTED`，不能按实机停止检查通过处理。最终 Alpha 决定由维护者人工作出。

实现提交：`bbc92001814e118206852eb65399a28d2673f617`；其父提交是批准基线 `b13ea8b12b6b57f981227b06abf1a31a3a3907cd`。实现提交已 GPG 签名，已通过 HTTPS 推送到现有 `armedforces.io-v2` 分支，并独立核验远端签名、父提交和 HEAD。当前文档提交是后续交付说明；验收时用 `git rev-parse HEAD` 记录实际检出身份。无需重置工作区或切换分支。

## 1. 实际入口、环境和依赖

| 文件 | 用途 |
| --- | --- |
| `src/run_alpha_candidate.py` | 单次执行的命令行入口；只读取指定 JSON，结果写到标准输出 |
| `src/examples/g1_alpha_population.example.json` | 三条公开人工构造记录，无 truth 标签，无私有配置 |
| `src/mvp0_foundlist_collector.lua` | 原有 AC6 入口，未改动 |
| `src/mvp0_offline_scoring.lua` | 原有 AC5 全量覆盖、输入及结果核对，未改动 |
| `src/mvp0_candidate_report.lua` | 原有特征、评分、排名、建议和报告，未改动 |
| `tests/test_alpha_candidate.py` | 现有 pytest 套件中的小型入口回归，不是新的测试框架 |

本次实测环境：Windows 11 build 22631、PowerShell 7.6.9、CPython 3.14.3 x64、Lupa 2.8，分别运行其 Lua 5.3 和 Lua 5.4。从源码检出目录运行，三个 Lua 文件必须与启动脚本同处 `src/`。此入口没有添加 wheel 内 Lua 资源打包，也没有新增 CLI 安装命令。其他环境未在本次验证。

使用仓库已有 `.venv`；不读取或覆盖 `run_case_config.local.lua`、`ce_mvp_config.local.lua` 等私有配置。已有环境无需安装任何新依赖。若准备全新本地环境，仅在 `.venv` 不存在时创建，再安装本次已实测的 Lupa 版本；以下新建环境命令未在本次重复运行：

```powershell
Set-Location 'D:\armedforces.io-v2'
# 仅用于尚无 .venv 的环境；需要已安装 CPython 3.14 x64。
if (-not (Test-Path -LiteralPath '.venv')) { py -3.14 -m venv .venv }
.\.venv\Scripts\python.exe -m pip install 'lupa==2.8'
```

日常启动不需要 pytest、CE、管理员权限、目标 PID、进程附加或任何原生操作后端。

## 2. 启动及正常观察

先确认当前目录和运行时，再直接运行公开示例：

```powershell
Set-Location 'D:\armedforces.io-v2'
git rev-parse HEAD
.\.venv\Scripts\python.exe -B -c "import sys, lupa, lupa.lua53, lupa.lua54; print(sys.version); print('Lupa', lupa.__version__)"
.\.venv\Scripts\python.exe -B .\src\run_alpha_candidate.py --help
.\.venv\Scripts\python.exe -B .\src\run_alpha_candidate.py --input .\src\examples\g1_alpha_population.example.json
```

默认使用 Lua 5.4；加 `--lua lua53` 可选择本次也已验证的 Lua 5.3。默认输出覆盖摘要和完整普通报告；加 `--json` 输出完整 AC6 completion envelope、普通报告及只读状态。JSON 中 Lua 的数字下标保留为字符串对象键，例如 `evaluation.result.ranked."1"`；空 Lua 表输出为 `{}`。

维护者应在运行前独立记录下面的公开示例预期。预期只写在操作单与测试断言中，没有作为 truth 传给评价器：

| 观察项 | 示例预期 |
| --- | --- |
| 人工构造的完整输入 | 3 条，身份依次为 `1048872`、`1049384`、`1049896` |
| 完成性 | `status=COMPLETE`、`completed=true`、`population_mode=full`、`population_complete=true` |
| 计数 | supplied / distinct / eligible / selected / fully_scored / ranked 均为 3；duplicates / excluded 均为 0 |
| 身份覆盖 | eligible、selected 和 ranked 的身份集合完全相同，每个排名身份恰好出现一次 |
| Rank-1 | `proposed_rank1=1048872`，普通报告中的对应身份为 `0x100128`，得分 46 |
| 原始建议 | `ACCEPT`、`HIGH`、`manual_review_required=false` |
| 动作及恢复 | `action_permitted=false`；操作和生命周期状态均为 `UNSUPPORTED...`；`automatic_recovery=false` |

这些数字只是兼容现有 AC5/AC6 表结构的人工身份及数据，不是实际目标进程地址。普通报告仍含历史建议措辞；即使出现 ACCEPT 或 “direct use”，也没有任何动作授权。

如需保存本次人工观察，在 `reports/当天日期/` 下创建独立目录。以下命令不覆盖已有输入或私有配置，目录重名则停止：

```powershell
$alphaRun = Join-Path 'reports' ((Get-Date -Format 'yyyy-MM-dd') + '\g1-alpha-manual-' + (Get-Date -Format 'HHmmss'))
New-Item -ItemType Directory -Path $alphaRun -ErrorAction Stop | Out-Null
Copy-Item -LiteralPath 'src/examples/g1_alpha_population.example.json' -Destination (Join-Path $alphaRun 'population.json') -ErrorAction Stop
.\.venv\Scripts\python.exe -B .\src\run_alpha_candidate.py --input (Join-Path $alphaRun 'population.json') --json > (Join-Path $alphaRun 'result.log') 2> (Join-Path $alphaRun 'error.log')
$alphaExit = $LASTEXITCODE
Write-Output "exit=$alphaExit"
if ($alphaExit -eq 0) {
    $alphaResult = Get-Content -LiteralPath (Join-Path $alphaRun 'result.log') -Raw | ConvertFrom-Json
    $alphaResult | Select-Object state, proposed_rank1, action_permitted, action_status, lifecycle_status, automatic_recovery
    $alphaResult.evaluation.counts
    $alphaResult.evaluation.result.recommendation.recommendation
}
```

只有退出码 0 才能读取本次成功结果。运行时 `.log` 文件已被现有 `.gitignore` 排除；不要提交本地输入、私有导出、运行日志或失败转储。向维护者报告必要的脱敏摘要及本地证据路径即可。

## 3. 自有应用输入的准备要求

内置示例无需外部应用或外部测试输入。对其他自有数据，应用所有者须明确授权导出，并由应用自身提供完整、冻结的有限记录集合。仓库没有应用内导出器；不能用本入口寻找、扫描、附加或读取第三方进程。需要动态应用行为或操作闭环时，先停止该部分验收并记录缺口。

输入是 UTF-8 JSON（可带 BOM），顶层必须且只能包含：

- `schema: 1`，`population_id`（1–80 个英文字母、数字、点、下划线或连字符），`complete: true`。
- `supplied_count`：实际输入条数；`supplied_identities`：对应 `records` 的完整身份序列，顺序和重复必须一致。
- `records`：数组；每条只有 `addr`、`mapped`、`protect`、`memory`。字段语义和校验沿用 [AC5/AC6 合同](algorithm_a_offline_scoring.md#raw-ac5-api-and-shared-contracts)。JSON `memory` 的键是正整数的十进制字符串，值是 uint32 整数；启动器仅还原键类型，不补造缺失特征。
- `options`：示例中的明确 `population_mode: "full"` 和 `target_value_pattern`。其他已支持选项沿用 AC6；full 禁止 `scan_budget` 和 `max_candidates`。truth、live、action 和未知选项均不允许。不可用 null 绕过字段校验。

完整性声明只是提供者的声明；消费端核对声明与实际输入，以及 AC6 返回的源/去重/合格/选中/排名身份和计数，不能证明应用是否漏导出对象。独立预期和验收 truth 应由维护者另行保存，不能写入 records/options。

保留可选 bounded 工程路径：在独立副本中显式设 `population_mode: "bounded"`，可设既有合法预算。它仍输出真实模式、子集覆盖和普通建议；此入口的 `proposed_rank1` 为 null，不能代替 full 完整结果。本次小型回归验证了该兼容性，没有修改产品/native 的配置含义。

## 4. 停止观察和退出码

入口每次只调用一次 AC6，没有定时器、重新寻址、重扫、恢复、后台进程或重试。手动再次启动是新的只读求值；不复用之前的成功结果。

用刚才的公开示例副本做一次“提供者声明不完整”的停止观察：

```powershell
$alphaInvalid = Get-Content -LiteralPath (Join-Path $alphaRun 'population.json') -Raw | ConvertFrom-Json
$alphaInvalid.complete = $false
$alphaInvalid | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath (Join-Path $alphaRun 'incomplete.json') -Encoding utf8
.\.venv\Scripts\python.exe -B .\src\run_alpha_candidate.py --input (Join-Path $alphaRun 'incomplete.json') --json > (Join-Path $alphaRun 'stopped.log') 2> (Join-Path $alphaRun 'stopped-error.log')
$alphaStopExit = $LASTEXITCODE
Write-Output "exit=$alphaStopExit"
Get-Content -LiteralPath (Join-Path $alphaRun 'stopped-error.log')
```

预期：退出码 1，标准输出为空，错误含 `ALPHA_POPULATION_NOT_DECLARED_COMPLETE`；进程退出后没有自动重新启动。不要把不完整输入称为 EMPTY 或 REJECT 结果。原本成功的 `result.log` 只能代表之前那次运行。

| 情况 | 实际行为或限制 |
| --- | --- |
| 输入无效、声明不完整、AC6 失败/不完整结果、资源异常 | 退出码 1，保留原异常及 traceback；不输出成功排名，不回退 bounded |
| 求值期间输入文件内容变动或文件无法再读 | 发布前复读校验失败并停止；这只是快照文件检查，不是应用生命周期监测 |
| 操作者在运行期间按 Ctrl+C | Python 收到中断时退出码 130，输出 `OPERATOR_CANCELLED`；Lua 指令钩子提供协作检查点，无自动恢复 |
| 小示例在 Ctrl+C 前已运行完 | 记录取消观察 `NOT_RUN`；不要为延长运行而扩大为新统计测试。本次自动回归已用安全异常替身验证中断传播 |
| 参数使用错误 | argparse 退出码 2，无评价结果 |
| 应用报告进程退出、身份变化、无效对象或操作失败 | `UNSUPPORTED`：没有接入该应用接口，不得声称已观察到停止或回读保护 |

本入口不会把未知的应用状态当成有效状态：输出明确标记生命周期未支持且始终不允许动作。没有检测到错误、文件仍可读、离线 Rank-1 正确，都不能证明语义对象身份仍然有效。

## 5. 最小人工判定与已知限制

维护者记录：检出 commit、运行时、输入来源/独立预期、实际覆盖计数及身份、Rank-1、普通建议、退出码、停止原因和证据路径。正常观察满足第 2 节、停止观察满足第 4 节，才可以人工接受**这部分只读候选交付**。任何前提失败或状态未知时停止；保留失败，不能将 NOT_RUN/UNSUPPORTED 改成通过。启动器不输出最终 Alpha PASS，也不替维护者作发布决定。

仍缺少的集成功能是：自有应用已文档化的操作及相应回读接口、该应用的身份/退出/有效性接口及其停止/清理接线。原有 CE 执行、准入、回读、取消和恢复保护没有改动；此次没有绕过这些保护，也没有把测试替身当作真实应用操作。当前候选不具备动作闭环，不能进行相应实机验收。后续如提供合适的现成协作接口，需另行明确其授权和语义后才能接入。

此启动器用于小型本地交付：输入上限 8 MiB，Lua allocator 上限 256 MiB（沿用现有小型测试运行时），输出上限 256 MiB；超限整次失败，不截断候选。240 秒是协作 deadline，不能中断任意阻塞的系统调用；输出大小在序列化后检查，非 Python 总内存硬上限。它不是历史大池 worker/supervisor，不包含其宿主可用提交量或私有内存采样监督。历史 AC6/N1 大池的调用者保护及证据保持原样，不向此小型入口转移大池容量或性能保证。

历史结果仅复用：AC8 在声明的合成域中 Rank-1 为 100/100，满足 >=95% 算法标准；AC9 103/103 parity；G1-N1 两个 18,498 条记录池完成；G1-N2 364 项检查通过。这些不是本次新增独立观察。本次验证详情见 [交付记录](../reports/2026-11-26/g1-alpha-prep-1-delivery.md)。

G1 保持 **0 PASS / 0 FAIL / 1 INDETERMINATE / 11 NOT_RUN**；历史 AC/PAIR 结论、`IMPLEMENTED_PENDING_CE_QUALIFICATION`、`ATTACHMENT_HANDLE_UNVERIFIED`、`NOT_PRODUCTION_AUTHORIZED`、`QSG_NATIVE_BACKEND_NOT_QUALIFIED`、`HISTORICAL_ROOT_CAUSE=INDETERMINATE` 及 N0/MIN/LOCAL publishing suspension 均不变。Alpha Pre-release 仍然 BLOCKED，需单独的维护者发布决定并解决适用约束。本次不运行生产/第三方测试，不创建 Tag、Release、分支或 PR，不涉及 Generation 2。
