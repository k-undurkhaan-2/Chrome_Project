# H3-A7-Q1-QSG-D1 — 合成测试矩阵（待实施）

**PLAN_ONLY；本轮所有新增测试 NOT_RUN，未编写/运行 mock PoC。**
G1 LIVE NOT APPROVED；L01–L12 = **0 PASS / 0 FAIL / 12 NOT_RUN**；L12-MISSING/DISABLED/INVALID 全部 NOT_RUN。

参照 [调用清单](h3_a7_q1_qsg_writer_inventory.md)、[接口契约](h3_a7_q1_qsg_contract.md) 和 [设计接缝](h3_a7_q1_qsg_design_review.md)。未来仅在获得QSG-R2有限授权后实施以下合成测试；真实CE、一次性目标、原生内存、真实pipe及已启用local config均不属于本计划的执行权限。

## 1. 测试器与观测原则

使用原冻结Single collector/ranker和纯布局数据，在隔离Lua mock/table/bytearray世界中运行新候选；不导入 tests/ce_mvp_disposable_target.py，不加载kernel32、不打开CE/进程。Lua5.3覆盖真实公开loader签名；Lua5.4仅覆盖其支持的core/adapter模型，公开loader应仍拒绝非5.3，不能为了测试修改版本守卫。

新fake transport支持确定性时钟、分片/丢包/重复/乱序、断线及每个持久边界崩溃注入；fake store提供独占与journal/head/anchor失败点；raw spy记录实际fake原语调用顺序、地址、value bits和次数。测试器不得只用core.write_count来断言0 writes。受控并发使用barrier/event，不依赖任意sleep碰运气。

每个用例独立保留输入candidate/policy hashes、origin=SYNTHETIC、注入点、预留R/claim/实际fake raw D、状态/资源/事件序号/错误码、结束账本和独立verifier结论。禁止测试器给预期结果贴上CE live来源。测试中的每个独立新session只是隔离样例；跨Start/reload用例必须共用一个enrollment，不能重建fixture冒充预算持久性。

记号：R=持久reserve消费数；D=fake raw真正调用数；“0后续”允许故障前已有一次raw；临界损坏无法准确重建R时，必须封锁并保守保留不确定消耗。所有下表状态均为**计划/NOT_RUN**。

## 2. NORMAL 等价性与显式端口

| ID | 路由 / 输入 / 故障注入 | 预期结果与观察 |
| --- | --- | --- |
| N01 | 新旧R1/候选对同一unique、zero、ambiguous、incomplete、invalid、129+、drift、relocate trace；QSG文件不存在 | native/mock调用序列、return/错误、core状态、计数、清理、日志一致；没有Python/IPC探测 |
| N02 | QSG文件存在但损坏；NORMAL | 不读取、不加载该文件；行为等同缺失插件 |
| N03 | loader导入两次、CT四个syntaxcheck block、status/evidence/print_evidence | singleton不变；八个目标API attempted counters=0；print仅既有输出；没有QSG后台工作 |
| N04 | raw依次返回true/false/nil/1、抛可识别异常对象 | adapter保留第一个结果；成功严格==true；既有WRITE_FAILED或原异常传播；无额外调用或retry |
| N05 | NORMAL Stop/Start、cleanup失败、active/cleanup重入、late tick | 原ALREADY_RUNNING/CLEANUP_IN_PROGRESS/cleanup锁和资源行为一致；每run计数原样重置 |
| N06 | 省略adapter第四/第五参数；旧mock使用第四source；public loader Lua5.4 | 旧签名兼容；source字段不被误当mode；非5.3公开入口仍拒绝 |
| P01 | 原R1构造后改fake全局writeFloat的负向对照 | captured raw仍被调用，late wrapper未调用；明确这是mock反例，不对真实_G monkey-patch |
| P02 | 显式QSG工厂在构造时注入，走W01/W02/W03/W04/W05 | 每个实际写点均先走唯一port；spy证明先reserve/claim后raw；不凭函数名计数声称覆盖 |
| P03 | QUALIFICATION缺插件/工厂/method、未知版本、factory抛错 | Start拒绝；R=0/D=0；无NORMAL fallback；已创建资源全部清理 |
| P04 | 选择QUALIFICATION失败后试图切NORMAL；运行中卸载；重复dofile | mode latch保留；D=0新增；不能通过错误初始化解除资格模式 |
| P05 | 直接调用持有的QUALIFICATION adapter.write_float，伪造addr/value | 无run/candidate绑定拒绝；调用者不能传scenario/authorization覆盖上下文 |
| P06 | port scope拒绝发生在legacy write_intent之后 | core.write_count/adapter_write_attempts可+1；R=0、D=0；sidecar明确deny，verifier不套旧intent=dispatch |
| P07 | readback成功但缺core_verified或target post | 不输出PASS；旧core/readback顺序未被target IPC打断 |

## 3. 预算、持久化、崩溃与并发

| ID | 场景 / 注入点 | 预期R/D与结果 |
| --- | --- | --- |
| B01 | 同session L04=1 -> L07=1 -> Stop -> L10=1 -> 第四次 | 前三R=3/D=3；第四R不增/D不增，QSG_CAP |
| B02 | positive分组已用2，尝试第三positive；另测L10已用1再写 | 即使global未满也按分组拒绝；不把余量跨组借用 |
| B03 | L01/02/03/05/06/08/09/11/12分别强制请求port；包含每个L09/L12子case | 各自R=0/D=0；QSG_ZERO_PHASE；不存在未知L默认放行 |
| B04 | L04失败后换request_id申请第二L04；L07完成后继续恢复 | phase/step策略拒绝；联合cap2不允许同阶段silent retry |
| B05 | raw false/nil/1/throw/true但不改值、partial模型、readback失败 | 单次R=1、D=1；失败/不确定不退款，后续自动ticks不写 |
| B06 | reserve成功后、claim前崩溃 | R=1/D=0；旧锁/未决状态保留，reload不重置 |
| B07 | claim落盘后ack丢失；receipt后但raw前崩溃 | R=1/D=0；重发claim/旧receipt均不能再次派发 |
| B08 | raw之后outcome ack丢失/recorder宕机 | R=1、D=1；0后续raw；verifier INCONCLUSIVE或有矛盾时FAIL |
| B09 | journal append/flush、head temp create/fsync/replace、anchor确认逐点失败 | raw=0；若无法证明账本状态则FAILED_CLOSED，不能新账本接着写 |
| B10 | ledger/head/enrollment缺失、截断、digest改、pending文件、权限拒绝 | Start/port拒绝；D=0；保留旧文件，不自动修复/删锁 |
| B11 | 连续Stop/Start、换run/session字符串、Lua reload、模拟CE重启与同授权rebind | 原enrollment和R保留；新run不退款；擅自session变化拒绝 |
| B12 | 第一次有效reserve与串行重复完全同request/checkpoint | 原R<=1/D<=1；重复明确deny，不返回可dispatch的旧ack |
| B13 | 两线程/两broker owner同时reserve同request；两个不同request抢剩余1额 | 排他控制，最多1次reserve/dispatch成功；第二拒绝；不能各自得到3额 |
| B14 | raw中重入writer、timer重入、递归reserve | 本地非重入+broker全会话锁；最多原一次D；递归不增加grant |
| B15 | reserve落盘期间时窗/phase过期，或clock倒退 | R按已提交消费；raw=0；不等待/重试到新窗口 |
| B16 | 第10次成功Start；第三并发目标；第10实例；第61分钟/第6phase分钟 | 对应准入拒绝，scope不扩展；L12拒绝和L10guard probe不冒充成功Start |
| B17 | 正常关闭再open；崩溃残锁再open；试图重provision旧authority | 正常恢复原R；残锁fail closed；同authority新session拒绝 |
| B18 | claim token在同writer重复、换epoch、换writer、换CE实例后重放 | 旧token全部无新D；新writer不能恢复旧本地unused状态 |
| B19 | query_attempt/outcome/ping的响应被当成grant | 类型/绑定拒绝；所有只读响应D=0 |

## 4. Scope、身份与传输

| ID | 故障注入 | 预期 |
| --- | --- | --- |
| S01 | PID错、PID相同creation变、creation零/不可读、query与borrowed不符 | 拒绝；reserve前R=0/D=0；reserve后保留R但D=0 |
| S02 | 镜像hash错、Python解释器正确但script/layout/provider错、CE/broker peer冒充 | provenance/peer拒绝；不能只信target自报hash |
| S03 | address=base-4、base+65536、base+65533、错类型、过大/溢出、未对齐 | 全拒绝；边界有效base与base+65532单独测试纯4字节规则；实际candidate另须完整context |
| S04 | size=65532/65540、allocation_id换、同base新allocation generation、非自有区域 | 全拒绝；scan不是精确65536也拒绝 |
| S05 | value四字节在区内但address-0x20或+0x53越界；page未commit/只读/guard；mapping变 | scope或原结构校验拒绝，0raw |
| S06 | 跨Start退役地址恢复可读、旧page再commit、core/target退休不同步 | 永久拒绝旧地址；缺退休关联就关闭写资格 |
| S07 | bits与value pack不同、大小写/宽度错误、NaN/Infinity、signed-zero混淆、未经批准的finite值 | exact bits拒绝；不使用显示精度/epsilon |
| S08 | target B加入positive请求；同session把A配额转给B | B仅L11，R=0/D=0新增；累计namespace保持同一 |
| S09 | reserve后、claim后、finalcheck前切CE target或Stop | R若已预留则消费；旧generation/身份拒绝，raw=0 |
| S10 | 在raw已进入时Stop或递归tick；随后迟到callback | 最多当前一次D；消费R；不能承诺撤销已有调用；后续D=0 |
| S11 | phase_sequence重放/跳跃/从L05冒充L07、过期prewrite checkpoint、checkpoint重用 | 拒绝；不能通过给request换scenario获得额度 |
| T01 | 插件/IPC/broker unavailable，connection refused/权限拒绝 | Start拒绝或FAILED_CLOSED；D=0，无无限等待 |
| T02 | length0/65537、短header/body、分片、粘帧、多余字段、重复key、坏UTF-8 | 有界解析；合法分片只完成一次；其余deny，D=0 |
| T03 | ack错误request_digest/epoch/sequence、乱序/迟到/重复ack | 不接受为grant；原预留保留；D不增 |
| T04 | 在每次读少量数据前靠近deadline，模拟slow response | 整体deadline不刷新；到期关闭；不是每片都重新250ms |
| T05 | broker持久化超过总期限、cancel与response同调度、reconnect旧response | deadline/cancel先后规则明确；USED/REVOKED不能回到可写；无自动retry |
| T06 | 缺peer身份能力/未知timeout单位/transport声明不具备有限取消 | 资格初始化拒绝；不得因为mock通过就启用内置LuaPipe |

真实CE上的pipe超时单位、完整操作上限、Stop响应时延、peer handle和断电持久性不在上述合成PASS的证明范围，均为NOT_RUN。

## 5. 独立证据与verifier故障矩阵

| ID | 注入 / 原始证据 | 独立核验要求 |
| --- | --- | --- |
| E01 | recorder启动前不可用、写前append拒绝 | D=0；不伪造FAILED_CLOSED已落盘；缺证据不能PASS |
| E02 | core dropped_events>0、telemetry_error、缺序号、旧snapshot rollback | supervisor关闭writer；verifier FAIL/INCONCLUSIVE而非PASS |
| E03 | A0/A1在新run重用、缺raw候选binding、同alias不同address | 必须按run/seq绑定；禁止support.py式硬编码地址；冲突FAIL |
| E04 | target/CE post bits不等、readInteger/readFloat bits不等、write bits不等 | FAIL；真值显示相同也不能掩盖bit mismatch |
| E05 | 少CE派发、少target pre/post、少budget、少outcome、少cleanup | INCONCLUSIVE；明确矛盾/坏chain优先FAIL；所有reservation仍计消费 |
| E06 | orphan raw、重复claim/attempt、零预算phase raw、R>3 | FAIL，不靠controller提供的PASS旗标 |
| E07 | raw true但缺原core readback_verified；target值未变而raw返回false | 不PASS；不退款；独立区分失败和证据不足 |
| E08 | 修改事件但不改digest、重算chain但外部seal未变、删整段stream | FAIL；测试不能证明同一攻击者替换所有外部锚仍可发现 |
| E09 | 把SYNTHETIC origin换CE_LIVE、mixed origins、声称embedded Lua已运行 | 拒绝live提升；live仍NOT_RUN，无MVP_ACCEPTED |
| E10 | 各actor monotonic epoch错开但因果anchors有效；反例缺anchors | 前者依链可判模型成功，后者INCONCLUSIVE；绝不跨钟相减 |
| E11 | 修改controller/gate输出PASS，保持原始坏证据；禁止verifier import控制实现 | 结论仍FAIL；独立性由输入和依赖检查证实 |
| E12 | 原始事件含token/config/无关memory dump或未知字段 | schema拒绝；公开report仅输出安全码/alias/digest；原证据不就地脱敏覆写 |

## 6. L01–L12 单独验收矩阵

以下每行是未来模型要求，live列当前全部NOT_RUN。合成成功也不得更改该列。

| 项 | 独立setup/观察 | 允许MVP写尝试 | 必须保留的模型证据 |
| --- | --- | ---: | --- |
| L01 | 惰性导入、四个CT Lua syntax block、guard恢复 | 0 | 八项attempted-call before/after均0、未读config、STOPPED、无QSG自启 |
| L02 | positive run的原实例attach | 0 | host/target/CE创建身份和镜像绑定，不用历史PID |
| L03 | 完整Single扫描到唯一合格candidate，写phase尚未进入 | 0 | raw=1完整population、qualified=1、hardpass/ACCEPT、candidate绑定；cap128不变 |
| L04 | 明确进入初写phase | 1 | reserve/claim/raw/两侧exact bits和core verified的一致anchors |
| L05 | 独立phase >=20连续有效monitor cycles | 0新增 | 连续序号且未restart；scan/write/verified无增量；19次反例不得PASS |
| L06 | 单独target drift至0x42280000，>=3有效观察 | 0新增 | target planned_drift/self sample和CEvalue；不重扫不重写，不能复用L05区间 |
| L07 | 同run/同原进程实例，新page/不同地址；旧址退役 | 1 | target retire/decommit、core retire/broker永久退休、新candidate/位模式、scope无扩大 |
| L08 | 原target退出/身份失效 | 0新增 | terminal原因、清理、后续计数不增，不按name重新attach |
| L09-zero | 独立zero_match布局 | 0 | actual matched0、bounded scan/backoff、无raw |
| L09-ambiguous | 独立两合格结构 | 0 | count2/qualified2/AMBIGUOUS，不靠tie-break选一个 |
| L09-129_plus | 同64KiB内129个真实aligned search words | 0 | hard/configured cap128，FoundList129+明确拒绝；不降低cap冒充 |
| L09-incomplete | 值可读、必需结构跨未提交page | 0 | required-read failure、SCREENING_READ_FAILED，与invalid分开 |
| L09-invalid | 完整可读但结构无效 | 0 | count1、qualified0、CANDIDATE_NOT_QUALIFIED |
| L10 | 一次初写；active Start拒绝；Stop内probe拒绝；cleanup；同目标zero_match第二Start | 共1 | 原ALREADY_RUNNING/CLEANUP_IN_PROGRESS；两轮清理；每Stop后>=3 intervals稳定；第二run预算不重置 |
| L11 | 仅批准A/B；A=zero、B=unique，切到B | 0 | CE_TARGET_CHANGED；切换后A/B无新MVPread/scan/write；B自采100不代表OS零写证明 |
| L12-MISSING | 有效safe config移出/模型缺失，public Start一次 | 0 | 实际missing-file诊断含ce_mvp_config.local.lua；不是虚构MISSING_CONFIG；无adapter构造 |
| L12-DISABLED | otherwise valid，write_enabled=false | 0 | WRITE_DISABLED；八个before/after guard counters全0 |
| L12-INVALID | Otherwise valid config, `write_enabled=true`, `scan.scan_budget=65537`, `scan.max_candidates=128` | 0 | Start=false with `INVALID_SCAN_SETTINGS` before adapter construction or scan/write activity; not L09 overflow |

L12三个子项各需独立Start结果、guard before/after/restored、retained evidence无变化；前次L10 evidence须标PRIOR_RUN_OR_NO_RUN，不当作新run。保持L12附件的三项范围和session额度不变。L10内probe与active拒绝不消耗write reservation；L10第二run仍计一个成功Start但不获得新写配额。

### G1-S3 D2.4 prospective L12 erratum (2026-11-26)

Authority: `APPROVE_G1_S1_D2_DECISION_REGISTRATION_AND_L12_ERRATUM`.
The L12-INVALID row above is the corrected prospective example. This
authoritative erratum supersedes `scan_budget=129,max_candidates=128` in the
frozen [R1 plan, "L12 rejected configuration"](../ce_mvp_q1_r1_plan.md#l12-rejected-configuration)
and the local, ignored `docs/codex_tasks/h3_a7_q1_l12_three_case_addendum.md`,
"Three independently observed future rejections" INVALID row and "Future
setup, observation and restoration order" step 6. Those original files and
historical observations remain unchanged.

At baseline `01924ab753d784400ed15d9efe12339820df8a15`, the unchanged
[validator](../../src/ce_mvp_core.lua#L86-L94) permits `scan_budget` 1–65536,
`max_candidates` 1–128 and `max_candidates <= scan_budget`. Thus 129/128 alone
is valid; 65537/128 deliberately exceeds the intake range. The
[existing three-case synthetic test](../../tests/qualification/test_qsg_acceptance.py#L194-L208)
already uses 65537; this is static corroboration, not a new execution or live
result. The correction raises no limit and supplies no L09 overflow evidence.

MISSING, DISABLED and INVALID remain three independently required rejections:
the correct public-entry diagnostic, all eight attempted-call counters zero
before and after, no scan/write activity, unchanged retained prior-run
counters, successful guard restoration and required safe-state restoration.
Prior singleton evidence remains labelled retained evidence, never fresh L12
telemetry. No case substitutes for another, and no synthetic result passes L12.
In the existing separately authorized procedure, restore `write_enabled=false`
and the original 128/128 settings as already required.

This erratum authorizes no live input preparation, execution or qualification
result and changes no validation code. All three L12 cases remain
NOT_RUN/PAUSED; the current [G1 and product state](../algorithm_a_offline_scoring.md#retained-g1-and-product-state)
is unchanged. The earlier D1 status statements remain historical records.

## 7. 执行顺序、回归和准入

1. 先做新增文件/签名/唯一raw能力/模式依赖的静态核验，确认仅获准两处生产文件修改，旧R1原字节/manifest、collector/ranker/Full/D2/A6/R3/L12未覆盖。
2. 跑N/P，再B/S/T/E的确定性故障注入。每个失败保留原日志和manifest，不修改原失败结果来“变绿”。
3. 跑完整L模型链并独立封存CE/target/budget/supervisor streams，交给不加载控制代码的verifier；所有origin仍SYNTHETIC。
4. 以上通过后，跑原有 tests/test_h3_a7_ce_mvp.py、tests/qualification/test_g1_infra.py 聚焦回归和全仓库合成回归，保留实际命令、版本、退出码、计数和新旧差异。若旧测试断言需变化，必须具体说明其语义依据，不能删测试掩盖退化。
5. 生成独立QSG-R2候选manifest；未证明任一路径强制经过port、NORMAL不等价、证据绑定不全或transport不满足契约，均保持BLOCKED_WRITE_GUARD_WIRING/相应PARTIAL，不推进live。

历史G1-INFRA报告的405 focused、4950全仓库及95 subtests只是[历史summary](../../reports/2026-11-20/h3_a7_q1_g1_infra_summary_20261120T065113Z.md)中的记录。本轮未运行任何一项，也没有生成新的测试通过计数。D1实际验证仅限保护hash、文档引用/内部一致性和git diff --check。
