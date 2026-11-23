# H3-A7-Q1-QSG-D1 — Writer inventory

**静态审查；未执行源码或测试；G1 LIVE NOT APPROVED。** L01–L12：0 PASS / 0 FAIL / 12 NOT_RUN。
行号取本次哈希匹配的 R1 文件。配套 [设计](h3_a7_q1_qsg_design_review.md)、[契约](h3_a7_q1_qsg_contract.md)、[测试计划](h3_a7_q1_qsg_synthetic_test_plan.md)。

## 1. 证据等级

S=本轮读取源码得到的控制流/能力边；H=已有历史合成材料或测试定义，本轮未重跑；P=拟议 R2 验证；L=未来授权 CE 观察，全部 NOT_RUN。S 不等于运行证明，H 不等于本轮执行，任何等级均不表示 OS 全局拦截。

## 2. 加载与对象构造顺序

| 次序 | 实际位置 | 动作和边界 |
| --- | --- | --- |
| 1 | [CT](../../src/ce_mvp.CT) L8–19 / L26–35 | Start/Stop/Status 的四个 Lua block 都先检查 syntaxcheck；CT 无顶层 LuaScript、启用数据记录或 asm 写指令 |
| 2 | [loader](../../src/ce_mvp.lua) L2–9、L77 | 已有 _G.H3A7_CE_MVP 则返回；否则只定义 API/路径后注入；无 adapter 或 config 执行 |
| 3 | loader L10–25 | public start 检查旧 instance 的 running/cleanup；pcall 内验证 Lua 5.3，空环境加载数据 config，然后 core.validate |
| 4 | loader L26；[adapter](../../src/ce_mvp_adapter.lua) L11–31 | 把真实 _G 作为 ce 传入；L13–18 捕获 f.writeFloat 等函数；检测 CE 版本/位数及解析固定 kernel32 API |
| 5 | adapter L139–205 | env._G=env；提供只读 CE 代理；加载 candidate_report 后加载 foundlist_collector |
| 6 | [ranker](../../src/mvp0_candidate_report.lua) L3002；[collector](../../src/mvp0_foundlist_collector.lua) L2236 | 向私有 env 注入 MVP0 和 MVP0FoundList，并返回模块表，不向真实 _G 注入这些模块 |
| 7 | loader L27；[core](../../src/ce_mvp_core.lua) L94–161、L233–239 | core.new 再 validate，保存 adapter，设置非阻断 observer 和运行/身份 guard |
| 8 | loader L28；core L340–361；adapter L309–313 | start 转 ATTACHING，创建 50ms control timer，回调 core.tick |

适配器构造后再改全局 writeFloat 对 f.writeFloat 无效。历史负向对照见 [test_g1_infra.py](../../tests/qualification/test_g1_infra.py) L299–306；本轮只读该测试，没有执行。

## 3. 每一条真实可达写入路线

所有 raw 写点都记为 W0=adapter L97 的 f.writeFloat(addr,value)，核心调用记为 C0=core L297。

| ID / 场景 | 完整跳转链和分支条件 | 原始调用 / 拟议拦截位置 | 本轮证据与后续要求 |
| --- | --- | --- | --- |
| W01 初写 L04 | CT/direct public start -> adapter/core 构造 -> tick/do_tick -> ATTACHING L252 -> SCREENING L263 -> begin_scan/poll_scan -> choose -> CANDIDATE_CHECK L283 -> WRITING L289 -> C0 -> adapter.write_float L93 -> checked/config/intent -> W0 -> immediate readback | W0；在 adapter 构造时选择唯一 port，再以 port 替换 L97 | S；P 必须断言 reserve 落盘在 fake raw 之前、地址/bits 完全一致；L NOT_RUN |
| W02 初始零候选后出现候选 | SCREENING ready,nil -> core L275 backoff -> L240–248 -> RESCAN_BACKOFF L261 -> SCREENING -> W01 后半段 | 仍 C0/W0；没有先写再 retry | S；P 验证空扫描不预留，后来的初写只派发一次；L NOT_RUN |
| W03 监控失效恢复 L07 | MONITORING L312 -> valid=false；连续 invalid_confirmations -> retired L324/address_retired L325 -> selected=nil -> backoff L327 -> 新扫描 -> 不在 retired 的新地址 -> C0/W0 | 同一个 port；额外要求 broker 退休集跨 run/session 持久保存，旧地址不得再授权 | S；H 旧模型有不同地址恢复；P 验证同实例、独立退休/目标 decommit/新 candidate；L NOT_RUN |
| W04 Stop 后重启 | public stop -> core.finish -> cleanup 完成 -> public start L10–28 新 adapter/core -> W01 | 新 port 实例必须继续同一个 broker enrollment；NORMAL 原计数归零，资格预算不归零 | S；P Stop/Start/reload 和新 run ID 不增加配额；L NOT_RUN |
| W05 L10 首次写入 | L10 第一 Start=baseline_unique -> W01；active Start -> loader L16 ALREADY_RUNNING；Stop 的 core L206 probe -> loader L17 CLEANUP_IN_PROGRESS；cleanup 后第二 Start=zero_match -> 无候选 | 第一轮 W0 最多一次；第二轮及两个重入拒绝不派发 | S；H 公共 loader mock 定义；P 原拒绝诊断/清理证据及 >=3 intervals 稳定分别验证；L NOT_RUN |
| W06 raw false/nil/非布尔/throw | W0 返回 -> adapter L98 result==true 计数；core L297 非 true 则 WRITE_FAILED；throw 传播到 tick 的 pcall；finish -> 清理 | port 只调用 raw 一次；已预留额度一律消费，无自动重试 | S；P false/nil/1/throw/返回丢失分别注入；L NOT_RUN |
| W07 raw true 后回读失败 | W0 -> guard -> READBACK -> a.readback -> bits/value 精确检查 core L303–305；不一致/异常 -> finish | 不通过“补写/恢复原值”解决失败；本次预留照常消费 | S；P true 但不改值、partial 模型、Integer/Float 不一致；L NOT_RUN |
| W08 回调/重入/Stop 竞争 | core.tick L334 busy 时 finish；OnScanDone 只设 done；late tick 在 L333 返回；Stop 使 running=false/epoch++；每 primitive 前 checked -> guard | 若 raw 尚未进入，final guard/generation 拒绝；若已进入最多保留该一次，不能撤销或退款 | S；P 在 reserve 等待、receipt 后、raw 内、cleanup 内分别调度注入；L NOT_RUN |
| W09 直接调用构造后的 adapter API | a 返回 write_float 函数；core 以外的合成构造方可保有 a；正常 loader 未导出 instance/adapter | 构造时 QUALIFICATION port 不依赖仅 core 调用者；直接 a.write_float 仍需绑定 run/scenario/有效 candidate，不能自造 context | S；P 绕过 core 直接调用也拒绝无上下文的写；L NOT_RUN |

W02 是扫描后再发现候选；W03 是失效后的恢复。两者均不是对失败 raw 的重试。现有 retired 表仅属于单个 core，公开 Start 会新建它；资格 broker 的退休约束不能沿用这个单次运行生命周期。

## 4. 明确没有写入的分支

| 分支 | 静态依据 | 资格测试必须观察什么 |
| --- | --- | --- |
| load/status/evidence | loader 顶层只定义 API；evidence/status 返回快照，status 会打印但无 native 操作 | 导入、CT syntax、status/evidence 不启动 QSG/IPC/target；L01 八个 attempted-call 计数全零 |
| L05 有效监控 | core L319 只清 invalid_count | >=20 个连续有效 monitor_result；扫描、port/raw/verified 计数不变 |
| L06 finite drift | adapter.valid L128–133 接受任何 finite 当前值；不比较已写入值 | >=3 次独立漂移监控，0x42280000；不重扫/不重写 |
| 未达到阈值的瞬时失效 | core L321–327 在阈值前不 backoff | 不写；若恢复有效，invalid_count 归零 |
| 退役地址重现 | core L284 RETIRED_CANDIDATE；拟议 session 退休集另作持久检查 | 旧地址即使可读、值恢复 100，也不 reserve/raw |
| L09 五个负向 | adapter FoundList 上限/完整性 -> read_failure -> choose 唯一性和 hard pass | zero、ambiguous、129_plus、incomplete、invalid 五项独立零写；不能降 cap 代替129 |
| L11 切换 | adapter.check_identity L66–72 在 target read/write 前校验 opened PID/borrowed handle 和创建 token | B 无 MVP scan/read/write；A/B 配额不分裂，B 永远零写 |
| L12 三个拒绝 | loader L23 missing；core.validate L47 WRITE_DISABLED、L75–77 INVALID_SCAN_SETTINGS，均在 adapter.new 前 | 缺失/disabled/scan_budget=129 三次各自 Start 诊断与零活动，保留前次 evidence 不能冒充新证据 |
| scanner completion | adapter L256–259 只赋 task.done=true；disposed 后忽略 | callback 不直接 collect/write；重复/迟到不新增派发 |
| dispose/close | adapter L290–338 仅释放 scanner/timer/query handle/local stream | 清理失败可阻止未来 Start，不能触发补写；borrowed handle 不关闭 |

## 5. collector/ranker 路由检查

adapter.poll_scan L275–281 的协程调用 collector.run，传入固定 single/full-population 参数，无外部执行回调。collector L2212–2213 调 build_input -> collect L1572 -> collect_raw_foundlist_addresses L939 -> FoundList proxy；proxy 在 adapter L179 对超过128先拒绝，故不会把截断候选集假装全体。后续 filter 使用 readInteger，prescore 的 build_scored_pool L1388–1392 调 ranker.build_candidate/score_candidate。ranker L2757–2792 只经 read_u32/read_f32 读九个字段，L2980–2998 再评分/排名/推荐/渲染；可选 on_rank_complete 在本链不传入。adapter.choose L210–248 才形成包含地址/字段/mapping 的 candidate 返回 core。

env 能力清单由 adapter L139–169 显式构造，没有 write API、require/loadfile/dofile 或 executor 对象。ranker/collector 全文件检索未发现实际目标写原语；已查的 dynamic/global 用法是私有模块导出和 debug.getinfo。结合实际入口、固定 opts 和回传 candidate 的路径，可得当前 pinned 源码没有第二目标写通道；不推导成恶意代码隔离证明。

## 6. API 与计数兼容要求

现有 a.write_float(addr,value) 是点调用；拟议 port:write_float32(request) 是内部方法，不改变 core 调用约定。现有 raw 第一返回值原样返回，adapter 只将 result==true 计入成功；core 要求严格 true，否则停止。保留正常错误对象传播和 loader/core 的既有 pcall 边界。

R1 core.write_count 在调用 adapter 前增加；adapter_write_attempts 在 W0 前的 write_intent 时增加。替换为端口后 QUALIFICATION 的授权拒绝可能发生在这两个计数之后，故它们只作 transaction/port-entry 观察；用新 raw_dispatch_attempts 证明 raw 次数。新 verifier 必须允许一个 deny 对应零 reserve/零 raw，或一个已消费 reservation 对应零 raw；不能沿用旧 intent 数等于 raw 数的断言。NORMAL 的操作顺序和计数保持不变。

## 7. 仍需验证的证据

S 已覆盖函数级可达链，但本轮没有动态执行、没有 CE 内部实现覆盖证明。R2 合成须观察唯一 port、不可直接 fallback、可靠 alias/retirement 绑定、同步故障后的零后续 raw，以及新旧 NORMAL trace 一致。实际 CE 的 writeFloat 实现、IPC、取消时延、所有权/镜像核验和断电持久性均为 L/NOT_RUN；完整独立 G1 批准之前不进入这些路径。
