# F01：标准 Alpha 持久配置说明

本次只交付已授权 `OWNED_SYNTHETIC` 输入的配置接缝。配置一次后，普通生成 CT 的
**ID1 Start** 会读取并验证配置，不需要先在 Lua Console 调用 `configure_execution`。
这不代表真实输入采集、native 操作或完整 Alpha 产品已经可用。F02–F04 仍未交付。

## 候选身份与安装

- 源码提交：`79c6a3dfadabfa66afb652dda4ea4c9535ee5388`。
- 独立目录：`D:\armedforces.io-v2\reports\2026-11-26\g1-alpha-f01-candidate`。
- 普通 CT：该目录的 `src\ce_mvp.local.CT`；2909 字节，SHA-256
  `76d966213fed39d27b491f86f3fc1af9d38ab97ea544a4f9a9b3db1ab85cb7d7`。
- [15 文件身份清单](../reports/2026-11-26/g1-alpha-f01-file-identities.json)包含
  13 个维护文件的 Git blob、SHA-256、长度，以及生成 CT 和公开示例的本地配置副本。
  [交付与验证回执](../reports/2026-11-26/g1-alpha-f01-delivery.md)区分实际检查与未验证项。
- 这个独立候选已含与公开 Alpha 示例逐字节相同的 `src\ce_mvp_config.local.lua`，
  **不含操作员原有私有配置**；无需再次复制。原安装、历史候选及工程示例均保留。

候选按现有准备脚本的默认模式生成，`controlled=false`，没有使用 `--alpha-controlled`。
CT 绑定本候选的 Lua 绝对路径；移动目录后需在新目录重新运行现有准备脚本并重新登记
文件身份，旧哈希不再适用。Python 仅用于离线准备；没有增加运行时启动器或 SDK。

其他独立安装需要配置时，只在目标不存在的情况下复制一次，先将 `$sourceDir` 改为
实际绑定安装的 `src` 目录。已有私有配置时停止，由操作员自行安排独立安装，不能覆盖
或把旧工程配置改名当作标准 Alpha 配置：

```powershell
$sourceDir = 'D:\path-to-your-isolated-installation\src'
$example = Join-Path $sourceDir 'ce_mvp_alpha_config.example.lua'
$localConfig = Join-Path $sourceDir 'ce_mvp_config.local.lua'
if (Test-Path -LiteralPath $localConfig) { throw 'Existing local config: do not overwrite' }
[System.IO.File]::Copy($example, $localConfig, $false)
```

普通入口的操作为：在新 CE 7.6 / Lua 5.3 会话中保持 **No Process Selected**，加载
上述生成 CT，明确勾选 ID1 Start；ID2 查看缓存状态，取消 ID1 停止。加载 CT 本身
不会读取配置或启动工作。F01 没有改变原合成夹具的推进方式；自动化检查用既有表模型
推进函数观察结果，不能据此宣称 CE 中真实目标流程或自动效果已经验证。本页不要求
重做历史人工合成测试，也不安排有效性验收。

## 配置字段与优先级

标准配置文件只接受下面三个字符串字段，不能增加其他字段：

```lua
return {
  schema = 'g1.alpha.config.v1',
  mode = 'ALPHA_STANDARD',
  input_source = 'OWNED_SYNTHETIC',
}
```

| 字段 | 唯一支持的值及含义 |
| --- | --- |
| `schema` | `g1.alpha.config.v1`，明确区分标准 Alpha 数据格式与旧工程配置。 |
| `mode` | `ALPHA_STANDARD`，走普通 ID1 的 Alpha full profile。 |
| `input_source` | `OWNED_SYNTHETIC`，显式选择已有公开合成输入；不会隐式选择 mock。 |

配置位置始终是**实际绑定的 `ce_mvp.lua` 同目录**的 `ce_mvp_config.local.lua`，与调用者
工作目录无关。验证全部通过后才发布选择并创建既有夹具。旧的
`ce_mvp_config.example.lua` 保持工程模式含义，没有被重新解释；标准配置不能选择
`ENGINEERING_BOUNDED`、`QUALIFICATION` 或 `ALPHA_CONTROLLED`。

1. 已锁定的显式 API 选择优先，并保留原模式及授权合同；Alpha 的该路径不读取本地
   配置。显式选择本身无效时也不能靠有效配置修复或回退。
2. 没有显式 API 选择时，首次人工 ID1 Start 读取本地标准配置。缺失或无效就拒绝。
3. 运行中、ID2、Stop、清理中或清理不确定时均不重新读取。清理成功后的下一次人工
   Start 才重新读取标准配置，并先清除旧轮评价。有效值仍只能是同一个允许的选择。
4. 配置错误锁住当前 CE 会话。修正文件后须重新打开 CE；重复加载同一单例、再次 Start
   或补做 API 选择都不能解除锁。模式变更同样遵守原有重新加载要求。

这沿用**可信本地 Lua 配置**惯例。文件只应由操作员提供上面的数据表。返回函数、嵌套
表等不合字段类型的值及任意附加字段都会被拒绝；程序不调用配置提供的回调。空 Lua
环境不等于任意代码沙箱，也不提供硬执行时限或资源界限，不要执行来源不明的 Lua 文件。

## ID2 与错误处理

ID2 新增 `config_source`、`config_admission`、`config_error`，只观察缓存，不重新读取配置、
评分或操作目标。普通配置启动成功显示 `LOCAL_CONFIG / ACCEPTED / nil`；显式 Alpha
选择显示 `EXPLICIT_API / ACCEPTED`；工程/资格模式的标准配置准入显示 `NOT_APPLICABLE`。
`ACCEPTED` 只表示配置准入，不表示评价完成、操作授权或 native 资格。

| 诊断 | 含义 |
| --- | --- |
| `ALPHA_INPUT_REQUIRED: ALPHA_CONFIG_MISSING` | 本地文件缺失，保留原输入必需含义；`config_error=ALPHA_CONFIG_MISSING`。 |
| `ALPHA_CONFIG_UNREADABLE` | 文件打开、读取或关闭失败；不输出操作系统错误或路径。 |
| `ALPHA_CONFIG_SYNTAX` / `ALPHA_CONFIG_EVALUATION_FAILED` | Lua 语法不合法或可信本地配置求值失败；不输出原始错误。 |
| `ALPHA_CONFIG_SHAPE` / `ALPHA_CONFIG_FIELD_TYPE` | 返回值不是普通表，或字段不是字符串。 |
| `ALPHA_CONFIG_REQUIRED_FIELD` / `ALPHA_CONFIG_UNKNOWN_FIELD` | 缺少三个必需字段之一，或出现白名单外字段。 |
| `ALPHA_CONFIG_SCHEMA` / `ALPHA_CONFIG_MODE` / `ALPHA_CONFIG_INPUT` | 版本、模式或输入不受支持。 |
| `QSG_MODE_LOCKED` | 既有选择锁生效，不允许切换模式或用另一条路径解锁。 |
| `CLEANUP_IN_PROGRESS` / `CLEANUP_UNCERTAIN_RELOAD_CE` | 原清理保护生效；未通过前不读取新配置或重启。 |

错误不会创建新夹具、进入评分、自动重试、切换模式或开放写权限。新的 Start 在配置
阶段失败后，ID2 不会把上一轮 COMPLETE 当成本轮成功。原有评价、覆盖、资格与生命周期
字段保留，ID3 仍是独立的一次性只读示例，ID1 无需先执行 ID3。

## 隐私和范围

不要在此配置放入密码、凭据、PID、地址、native 授权、factory、回调或 writer。
运行程序和准备脚本不创建、迁移或覆盖操作员配置。真实安装的本地配置及生成 CT 已在
Git 忽略规则中；F01 的独立候选、测试目录及本地完整回执也被定向忽略。只提交公开示例、
源码、测试与脱敏交付清单，不提交私有配置或原始运行日志。

`ALPHA_STOP_ONLY`、清理与重启保护、严格资格 factory/writer 门禁及原资源限制不变。
外部发现/采集、native 读写/注入、新后端、目标参数和授权均未增加。
`ATTACHMENT_HANDLE_UNVERIFIED`、`QSG_NATIVE_BACKEND_NOT_QUALIFIED`、
`NOT_PRODUCTION_AUTHORIZED`、`IMPLEMENTED_PENDING_CE_QUALIFICATION` 全部保留。
F02–F04、真实输入的完整配置可用性、独立有效性验收、native 资格及发布条件仍开放。
