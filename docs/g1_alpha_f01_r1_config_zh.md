# F01-R1：原始配置合同与标准 Alpha 使用说明

标准 ID1 已能识别并校验维护中的
[`ce_mvp_config.example.lua`](../src/ce_mvp_config.example.lua) 完整配置。
配置校验、Alpha 参数适用性、实际参数应用、运行能力和执行授权分别报告。
**真实目标的标准产品仍然 BLOCKED**：当前标准路径没有获准的外部完整输入消费者，
也没有可由配置启用的已合格 native 操作闭环。修改 PID 或开启写入意图不能解决这些依赖。

本轮源码提交为 `41a0a47ee2515eeaa7531f1f67d80307448f69fe`。
范围结果为 `READY_G1_ALPHA_F01_R1_CONFIG_CONTRACT_ACCEPTANCE`，仅表示纠正后的配置实现
及现有自有表模型消费者经过验证；产品就绪、CE 宿主人工验收和 native 资格均未成立。
最终接受由维护者单独决定。[验证回执](../reports/2026-11-26/g1-alpha-f01-r1-delivery.md)
记录检查、真实失败及修正、签名推送和 F01–F04 剩余依赖。

## 普通 src 安装与私有文件保护

运行入口保持 Windows x64 / CE 7.6 / 内嵌 Lua 5.3 / CT。普通安装沿用
`src/ce_mvp.lua`、`src/ce_mvp.CT`、`src/prepare_ce_mvp.py` 及原有依赖；没有新增 GUI、CLI、
启动器、后端或安装器。Python 准备脚本只做离线路径绑定。

配置文件固定为**实际绑定的 `ce_mvp.lua` 同目录**的 `ce_mvp_config.local.lua`，
与当前工作目录无关。已有私有配置继续保留，不迁移、不改名、不覆盖、不提交。
公开示例仍保留全部原始数据值，包括 `target_pid=0`、`write_enabled=false`；本轮只纠正注释。

新安装且确实缺少本地配置时，可复制一次。以下命令不启动 CE，也不修改已有文件：

```powershell
$sourceDir = 'D:\armedforces.io-v2\src' # 改为实际安装的 src
$localConfig = Join-Path $sourceDir 'ce_mvp_config.local.lua'
if (-not (Test-Path -LiteralPath $localConfig)) {
  [System.IO.File]::Copy((Join-Path $sourceDir 'ce_mvp_config.example.lua'), $localConfig, $false)
}
$localTable = Join-Path $sourceDir 'ce_mvp.local.CT'
if (-not (Test-Path -LiteralPath $localTable)) {
  & 'D:\armedforces.io-v2\.venv\Scripts\python.exe' (Join-Path $sourceDir 'prepare_ce_mvp.py')
}
```

已有生成 CT 时保留它，确认它绑定当前安装；本轮没有覆盖实际安装的 CT 或私有配置。
CT 的路径绑定随安装位置变化，不能将其他目录的 CT 当作当前目录入口。需要移动或重新
准备时使用单独安装目录，不能运行准备脚本去覆盖应保留的 CT。本轮不另交付合成候选包。

仅加载 CT、Lua 模块或进行语法检查都不读取配置。明确勾选普通 **ID1 Start** 才读取一次。
**ID2** 只观察缓存；取消 ID1 执行 Stop；**ID3** 继续作为独立的一次性只读合成示例。
支持的持久配置路径不需要每次在 Lua Console 选择模式。本轮自动化执行的是实际默认
CT 脚本和原有表模型推进器；没有观察 CE 宿主自动推进、实际进程或产品效果。

安全示例直接 Start 的预期结果是：`ORIGINAL / VALID / ACCEPTED`，同时
`config_application=NOT_APPLIED`、`runtime_capability=STANDARD_INPUT_UNAVAILABLE`、
`execution_readiness=BLOCKED_SAFE_DEFAULT`、`config_block=ALPHA_CONFIG_TARGET_REQUIRED`。
这表示模板被识别，且执行仍被拒绝。不要为消除该状态而启用 native 写入。

## 合同字段与实际含义

以下规则来自共享原验证器和实际消费者，不能由注释推定额外能力。
`validate_contract` 复用原验证逻辑，允许安全占位 PID 0 和布尔值 false 作为结构有效数据；
原 `validate` 和执行核心仍要求正 PID 与 `write_enabled=true`，原错误顺序保持不变。
默认值只在原验证器本来提供默认值的字段上补全，其余必填项缺失即拒绝。

| 原始顶层字段 | 校验与默认 | 标准 Alpha 的有效含义 |
| --- | --- | --- |
| `target_pid` | 必填整数；结构校验 0..4294967295，执行校验 1..4294967295；示例 0 | 0 拒绝 Start；无按进程名回退。自有表模型只匹配固定虚拟身份 101，其他 PID 不会重绑定夹具或打开进程。真实身份消费者仍缺失。 |
| `screening_profile` | 必须为 `single` | 使用原 Single 评分规则；Alpha 的全量 supplied population 是另一个维度，不能将此值改为 `full`。 |
| `value_type` | 必须为 `float32` | 原 Float32 解释、位模式和读回检查；不支持新值类型。 |
| `write_value` | 必填有限数；按 `string.pack('<f')` 舍入，溢出拒绝；示例 125.0 | 受控路径传至既有表模型操作及精确读回，不使用夹具默认值覆盖。实际 native 操作 BLOCKED。 |
| `write_enabled` | 结构校验必须是布尔；示例 false | false 阻塞执行；true 只是配置意图，不是所有权、资格或操作授权。 |
| `scan` | 必填普通表；字段见下表 | 搜索值与适用检查点进入已有消费者；没有外部发现或采集扩展。 |
| `monitor_interval_ms` | 必填整数 100..60000；示例 1000 | 进入既有监控调度；受控验证观察到了 250 ms 间隔。真实目标监控消费者仍未就绪。 |
| `invalid_confirmations` | 必填整数 1..20；示例 2 | **工程专用**。Alpha 在第一次已观察到的无效状态停止，不等待该阈值，不增加检测能力。 |
| `min_rescan_spacing_ms` | 必填整数 100..600000；示例 2000 | **工程恢复专用**；Alpha 不重扫，该参数不生效。 |
| `rescan_backoff_ms` | 必填整数 100..600000；示例 1000 | **工程恢复专用**；Alpha 不退避重试。 |
| `max_backoff_ms` | 同上，且不得小于 `rescan_backoff_ms`；示例 30000 | **工程恢复专用**；保留原校验，不获得自动恢复能力。 |
| `max_rescan_attempts` | 原结构范围整数 0..50；示例 5 | **工程恢复专用**；Alpha 实际恢复次数为 0。解析范围不改变严格资格既有每 Start / session 上限。 |
| `scan_timeout_ms` | 必填整数 1000..600000；示例 120000 | 进入原核心和适配器时钟检查；包括已观察到的收集/评分时间。不是可抢占同步评分或 native 调用的硬超时保证。 |
| `log_limit` | 必填整数 16..2000；示例 200 | 原核心历史事件数及适配器运行日志行数上限；终止原因保留。ID2 的状态打印不属于该运行日志行数。 |
| `log_path` | 可选；最多 512 字符、盘符绝对路径、`.log` 后缀、无控制字符 | 既有追加日志消费者；目录须存在，输出失败停止。未配置时不写文件。ID2 不披露此路径或原始文件错误。 |
| `diagnostics` | 可选普通表；默认 `{enabled=false}`；见下文 | 原有被动事件记录；不会授予或执行 native 操作。 |
| `engineering_extensions` | 必填普通表；见下文 | 现有扩展开关只能关闭；不能从配置启用授权组件。 |

| `scan` 字段 | 校验与默认 | 标准 Alpha 的有效含义 |
| --- | --- | --- |
| `mode` | 可选 `process` / `bounded`；无边界时默认 process，有成对边界时默认 bounded | process 在现有表模型中只用于模拟地址范围和映射检查，不能代表 native process scan 已可用。bounded 是已识别但与标准 profile **冲突**的设置。 |
| `start_address`, `stop_address` | 可选但必须成对；整数或 `0x` 十六进制字符串，0x10000..0x7FFFFFFFFFFF；差至少 128；process 不可带边界 | 原工程/资格边界语义保留。标准 Alpha 报 `ALPHA_PROFILE_BOUNDED_SCOPE`，不会忽略边界或回退到截断执行。 |
| `target_value_float` | 必填有限 Float32；示例 100.0 | 进入已有 supplied-record 评分消费者和候选再检查。 |
| `target_value_pattern` | 必填 uint32，须等于上述舍入值的位模式；示例 0x42C80000 | 进入实际过滤和再检查；设为 42 的位模式时，仍为 100 的公开输入得到 EMPTY、零操作，不会改写输入以迎合配置。 |
| `scan_budget` | 可选，默认 2000；整数 1..65536 | **工程原始收集预算**。Alpha 全量模式不把它传作数量限制；不能用它证明全覆盖。 |
| `max_candidates` | 可选，默认 20；整数 1..128，且不大于 scan_budget | **工程排名预算**。Alpha 对供应的全部合格成员评分；两预算均为 1 的受控检查仍排名 3 人。 |
| `filter_target_match` | 必须为 true | 传入既有完整 supplied-record 路径；不能关闭精确匹配。 |
| `use_prescore_selection` | 必须为 true | 传入既有路径；全量模式保留所有合格成员，不由该开关引入截断。 |
| `collection_batch_size` | 可选，默认 256；整数 16..2048 | 进入已有适配器操作检查点，含候选资格检查；不是对 AC5 同步表评分增加抢占能力。 |
| `collection_slice_ms` | 可选，默认 10；整数 1..25 | 同一已有适配器检查点的时间片；没有新增宿主 UI 延迟保证。 |
| `process_candidate_limit`, `process_chunk_candidates`, `process_slice_ms` | 原验证器识别的废弃名称；任一非 nil 即拒绝 | `OBSOLETE_PROCESS_BUDGET_USE_LEGACY_INTAKE_SETTINGS`；从未被当作有效新预算接受。 |

`diagnostics` 仅接受 `enabled`、`session_token`、`event_limit`、`cleanup_start_probe`。
`enabled` 必须是布尔值。启用时必须提供 1..64 个字母数字/下划线/连字符组成的 token，
以及整数 32..2048 的 event_limit；关闭时原验证器不要求这两个值，也不消费它们。
可选 cleanup_start_probe 必须为布尔，true 要求 enabled=true。这个 L10 专用探针在标准
Alpha 中报 `ALPHA_PROFILE_QUALIFICATION_PROBE`，仅保留原显式资格路径的合同。
诊断证据本身含会话 token 等配置数据；不要将私有 `evidence()` 或日志当作可公开的 ID2 摘要。

`engineering_extensions` 只接受 `h3_a3_store`、`h3_a4_approval`、`strict_attachment`；
出现的值必须为 false，空表也符合原语义。任一启用值都会被原验证器拒绝。
未知顶层字段、未知嵌套字段、不合类型、数值越界及位模式不一致均拒绝；程序不会调用配置回调。
这是可信本地 Lua 数据约定，空求值环境不是不可信代码沙箱，也没有新增执行时限。

## 显式受控输入、选择优先级与重启

完整原始配置可附加既有 Alpha 选择字段 `input_source='OWNED_SYNTHETIC'`。
这是标准 loader 的可选扩展；loader 取出它后复用原配置验证器。未配置时没有隐式输入。
其他字符串单独报告不支持的能力，非字符串为字段类型错误。原合同无需 `schema` 或 `mode`；
工程/严格资格配置继续使用原合同，不接受此标准专用扩展。

这一显式选择只连接仓库现有固定自有表模型，虚拟身份为 101。
本轮测试在**隔离测试目录**从原始公开模板构造配置，明确选择该模型，再设置模型身份和
模型写入意图，观察非默认操作值、搜索位模式、监控间隔、超时、日志和诊断。
没有复制操作员配置、创建真实进程或扩展 native writer。这是参数消费者验证，不能当作
真实应用的配置教程。实际安装的安全默认值和私有文件均未被改动。

旧 [`ce_mvp_alpha_config.example.lua`](../src/ce_mvp_alpha_config.example.lua) 的三个字段继续
兼容，但明确标为**历史合成选择器**；ID2 报 `SYNTHETIC_SELECTOR_V1`、
`SYNTHETIC_SELECTION_ONLY`、`FIXTURE_DEFAULTS_ONLY`。它不代表原产品配置生效。

1. 已锁定的显式 API 选择优先。显式 Alpha 选择不读取本地配置，ID2 的
   `EXPLICIT_API / FIXTURE_DEFAULTS_ONLY` 表示采用既有测试默认值。无效显式选择不能靠文件修复。
2. 未显式选择时，普通 ID1 Start 读取绑定目录内的配置。先验证完整合同，再判断 profile、
   安全占位/意图及已有能力。只有上述受控路径可以进入现有模型消费者。
3. 运行中、ID2、Stop、重入、清理进行中或清理不确定时都不重读文件。
   清理成功后的主动 Start 才读取新快照，并先清除旧评价和参数应用状态。
4. 配置错误、profile 冲突或能力阻塞锁住本会话。修正文件后须新 CE 会话；模式不能由文件
   或重复加载单例改成工程/资格模式。`CLEANUP_UNCERTAIN_RELOAD_CE` 保持原拒绝语义。

## ID2 状态的判读

| 状态轴 | 示例与解释 |
| --- | --- |
| 文件识别 | `config_file_status=NOT_READ/READ/MISSING/UNREADABLE`；只来自已发生的 Start。 |
| 合同 | `config_contract=ORIGINAL/SYNTHETIC_SELECTOR_V1`；没有从文件成功识别时为 NOT_CHECKED。 |
| 结构校验 | `config_validation=VALID/INVALID/NOT_RUN/NOT_CHECKED`；缺失/不可读文件是 NOT_RUN。`config_error` 只保存固定校验代码。 |
| 准入 | `config_admission=ACCEPTED` 表示数据或显式选择准入，不能单独证明任何操作可运行。 |
| Profile | `COMPATIBLE_WITH_ENGINEERING_ONLY_FIELDS`、`CONFLICT` 或 `SYNTHETIC_SELECTION_ONLY`。 |
| 参数应用 | `config_application=NOT_APPLIED/APPLIED_OWNED_SYNTHETIC/FIXTURE_DEFAULTS_ONLY`；逐项 `config_effect.*` 说明工程专用、未配置、关闭或实际表模型消费者。 |
| 能力 | `runtime_capability=STANDARD_INPUT_UNAVAILABLE/OWNED_SYNTHETIC_ONLY/UNSUPPORTED_INPUT`。 |
| 执行条件 | `execution_readiness=BLOCKED_SAFE_DEFAULT/BLOCKED_CONFIGURED_INTENT/BLOCKED_PROFILE/BLOCKED_CAPABILITY/OWNED_TEST_ONLY`；`config_block` 给出固定原因。 |
| 授权与资格 | `action_permitted=false`；四个既有资格/授权阻塞字段保持原值，见下文。 |

配置有效但阻塞时，`config_error=nil` 与 `config_block` 同时存在是正常且必要的区分。
`ALPHA_STANDARD_INPUT_UNAVAILABLE` 指标准外部输入消费者缺失；
`ALPHA_SYNTHETIC_IDENTITY_MISMATCH` 指原配置身份与固定模型不符。
原验证错误如 `UNKNOWN_CONFIG_FIELD`、`UNKNOWN_SCAN_FIELD`、`SCAN_PATTERN_MISMATCH`
不会被改写成“原字段不受支持”。文件/语法/求值失败继续使用脱敏 `ALPHA_CONFIG_*` 代码。

ID2 不重读、不评分、不检查目标，也不输出原配置的 PID、身份 token、地址、操作/读回值、
工程预算或事件正文。返回的适用性表是副本，不能反向修改运行配置。运行错误中不安全的
详情变为 `ALPHA_RUNTIME_FAILURE`。检查前后配置读取、评分、操作、证据及日志计数保持一致。
ID3 不依赖 ID1，也不替代标准产品的输入或操作能力。

## 剩余产品阻塞与停止范围

| 要求 | 本轮结论 | 尚缺消费者或门禁 |
| --- | --- | --- |
| F01 原配置合同 | 识别、共享校验、安全拒绝、受控适用参数应用已验证；产品级要求仍 OPEN | 真实身份、扫描输入、操作、监控等字段缺少标准获准运行消费者；配置本身无法补足。 |
| F02 全部供应候选交接 | OPEN；已有合成全量路径保持原证据 | 实际标准输入来源及完整候选人口交接尚未交付/接受。 |
| F03 读回/监控失败停止 | OPEN；保留既有停止和清理保护 | 真实消费者及其读回/监控失效语义和验收未成立；合成故障不等于真实产品闭环。 |
| F04 获准自动操作/读回 | BLOCKED | 标准 native writer、独立身份/句柄证据、资格与逐次授权；本轮没有新增或激活。 |

`ATTACHMENT_HANDLE_UNVERIFIED`、`QSG_NATIVE_BACKEND_NOT_QUALIFIED`、
`NOT_PRODUCTION_AUTHORIZED`、`IMPLEMENTED_PENDING_CE_QUALIFICATION` 全部保留。
G1 历史矩阵仍为 0 PASS / 0 FAIL / 1 INDETERMINATE / 11 NOT_RUN；既有资源限制、
N0/MIN/LOCAL 发布暂停及其他资格条件不变。本轮 CE 宿主验收、native 执行、真实产品有效性
验收均为 NOT_RUN，没有安排维护者测试，没有创建 Tag、Release、PR、新分支或后续任务。
工作停止在 F01-R1 交付。
