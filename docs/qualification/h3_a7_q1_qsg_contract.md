# H3-A7-Q1-QSG-D1 — Writer / Broker / Scope / Evidence 契约

**PROPOSED_DESIGN_ONLY。没有实现或运行以下接口。G1 LIVE NOT APPROVED。**
本轮 synthetic 未执行；L01–L12 维持 0 PASS / 0 FAIL / 12 NOT_RUN。
本契约约束未来 QSG-R2 候选；不能把示例请求、模式字符串或授权 ID 当作批准。

关联：[设计审查](h3_a7_q1_qsg_design_review.md)、[写入清单](h3_a7_q1_qsg_writer_inventory.md)、[测试矩阵](h3_a7_q1_qsg_synthetic_test_plan.md)。

## 1. 信任与依赖方向

NORMAL: loader -> adapter -> local NormalWriter -> captured raw writeFloat。没有 QSG import、Python、broker、pipe、授权文件访问或额外 clock/native 调用。

QUALIFICATION: loader 的私有模式锁 -> 构造时 execution context -> QSG Writer -> Scope Guard + Session Supervisor -> Host Session Budget Broker -> Durable Store；Recorder Adapter 接收各角色自身事件，Offline Verifier 只读取封存证据。broker 不持有 CE raw，不调用目标写 API；target recorder 只读取/准备自己的获准区域；真正的 MVP raw 只在 CE 内的 QSG Writer 最末分支出现一次。

可信前提：固定候选及组件 hashes、独立保留的授权/enrollment/head 锚、正常宿主与文件权限、真实 CE/target 观察、无篡改过的 Lua/global 或并发人工写。pipe 名、SHA 链、PID 字符串、source 标签和客户端 approved=true 都不独自建立信任。已有 A4 review-only 结果不能代替本次完整授权；A6/R3 独立 T1 不变。

## 2. 类型与来源

所有协议记录有严格版本、字段白名单、类型/长度限制。未知字段/版本、重复 JSON key、NaN/Infinity、布尔冒充整数、非规范 bits、非整数地址均拒绝。网络上的地址和64位时钟用规范字符串，避免 JSON 浮点精度损失；进程内 Lua 地址须为精确整数。

| 类型 | 必要字段与约束 | 可信来源 |
| --- | --- | --- |
| AuthorizationRef | authorization_id、approval_record_sha256、candidate_manifest_sha256、approved_operations、approver/operator refs、window、evidence destination ref、caps、stop conditions | 未来独立完整批准记录；不由 CE client 创建/自签放行 |
| SessionBinding | session_id、enrollment_sha256、authorization_id、policy_digest、retained_head_ref、schema_versions | broker 已有受信任 enrollment；reload 只能 reopen，不能 provision |
| PeerIdentity | role、pid、creation_filetime（16大写hex且非零）、image_sha256、component_manifest_sha256、logon/session binding | 宿主独立 OS 查询 + 已固定可执行文件；CE/broker/target 各自绑定 |
| TargetIdentity | designation A/B、pid、creation_filetime、image_sha256、target_program_manifest_sha256 | 创建身份同时核对 target self / host query / CE 查询token；Python 情况固定解释器、脚本、layout/provider，不能只 hash python.exe 或 recorder.py |
| AllocationBinding | allocation_id、target_identity_digest、base、size=65536、allocation_generation、active page map、retired set、target event head | target 自有新区域生命周期 + host/adapter mapping 核对；旧地址/静态 PID 不得填充 |
| RunLease | run_id、client_epoch、writer_id、run_generation、target/allocation refs、phase_id、phase_sequence、deadline | Supervisor 与 broker 的已确认当前状态；新 run 不改变 session quota |
| CandidateEvidence | address、mapping、七个结构字段、discovery_bits、raw/scanned/filtered/selected counts、qualified_count、hard_pass、recommendation、diagnostic sequence refs | adapter 的实际 choose/poll 输出及 core evidence；不能由调用方填常数代替 |
| WriteRequest | request_id、全部 binding digests、phase_sequence、address、value_bits、candidate evidence refs、prewrite checkpoint digest、CE identity sample refs、writer_id、generation、client_epoch | QSG 将实际端口参数与固定 run 合并；调用者只能提供本次 addr/value，不能覆盖 scope |
| Reservation | attempt_id、request_digest、scope_digest、ledger_seq/head、policy/enrollment digest、phase、peer/writer/epoch/generation、expiry | broker 排他持久提交后生成；一个 attempt 永久消耗一单位 |

value_bits 固定形状 0xXXXXXXXX；Q1 search=0x42C80000，write=0x42FA0000，drift=0x42280000。请求 value 重新 pack('<f') 的结果须等于 value_bits 和许可 bits；不按显示数字、epsilon 或 Lua 数值相等来授权。

## 3. 模块接口

以下为语言无关签名说明，不是可执行 PoC。

| 模块 | 接口 | 结果与失败行为 |
| --- | --- | --- |
| Loader | configure_execution({mode,context}) | 仅未启动时配置；选择 QUALIFICATION 后 latch 不可回退 NORMAL；缺 context 进入失败锁。正常 start()/stop() 签名不变 |
| Execution factory | prepare_start(validated_config) -> RunContext | 核对模式、授权/候选、scope、broker/recorder readiness，再允许构造；config validation 仍先执行以保留 L12 原拒绝 |
| Execution factory | build_writer(raw, BoundaryChecks, RunContext) -> WriterPort | 在 adapter 构造期间调用；raw 不被公开；工厂缺失/异常不得返回 NormalWriter |
| WriterPort | write_float32({address,value,value_bits}) -> raw first result | NORMAL 透传；QUALIFICATION 做本节后文唯一 dispatch 流程；deny 抛固定 QSG 错误码，由原 core pcall 终止 |
| Scope Guard | validate_start(config,scope); validate_request(request,snapshots); recheck_before_raw(receipt) | 只返回完整绑定证据或拒绝；没有“未知时放行” |
| Supervisor | bind_core(readonly_getters,stop); before_tick(); after_tick(); sync_before_write() | 检查 generation、phase、deadline、证据缺口；收集退休/回读/cleanup。安全失败转 FAILED_CLOSED；局部清理必须仍可进行 |
| Supervisor | enter_phase(expected_sequence,new_phase,evidence_refs) | broker 持久确认、允许的阶段顺序、无未决 dispatch 后才切换；不能靠 request.scenario 自由换额度 |
| Supervisor | revoke_run(reason); stop_complete(cleanup); seal_session() | 先本地撤销，再通知 broker；失联保留未决/消耗，绝不重设额度 |
| Broker | open_session(binding,peer) -> SessionView | 只恢复既有 enrollment；缺失/坏账本/锚变更/锁占用拒绝；不会启动新 session |
| Broker | begin_run(run_request); accept_start(run); end_run(run,cleanup) | 最多一个 active run；preflight 不算成功 Start；不确定的 pending Start 保守占用 slot，不能新 run 绕开 |
| Broker | retire(identity,allocation,address,event_refs) | 永久保存该实例/区域的退休地址；有数据冲突即封锁，不自动取消退休 |
| Broker | reserve_once(WriteRequest) -> Reservation | 排他验证后先持久扣额；重复 request/checkpoint/nonce 拒绝，无可派发的幂等重放响应 |
| Broker | claim_dispatch(attempt_id,request_digest,epoch,generation) -> DispatchReceipt | 原子消费该 reservation 的唯一 dispatch 权；先写 claim 再返回；重复 claim 拒绝，不再次发 grant |
| Broker | record_outcome(attempt_id,result,event_digest) | 只记录，不退款；重复同值可返回只读 ack，冲突失败；不能产生新 grant |
| Broker | query_attempt(attempt_id) -> read-only status | 仅用于离线/受控对账；不返回可重新派发的 receipt，不决定自动重试 |
| Recorder Adapter | prepare_prewrite(context); append_event(event); bind_readback(attempt,core_seq,target_checkpoint); seal() | append 必须有有界确认；不可用/丢事件立即失去后续写资格；不修改旧证据 |
| Offline Verifier | verify(sealed_bundle,external_seals,policy,requested_cases) | 独立重建预算/状态/关联，输出 design/infra/synthetic/live 四个轴；不加载 controller/gate/target 执行逻辑 |

BoundaryChecks 由 adapter 内部绑定，不能接受外来可执行 Lua：检查 core running、poison/closed、当前 CE PID+borrowed handle、query/CE token、选中 candidate、mapping、原 discovery bits 和当前 port generation。选择函数限定在已审计构造依赖中，数据 config 继续空环境执行。

NORMAL 不用 pcall 包装 raw、不归一化 true/false/nil/1、不改变异常对象、不加日志/重试。QUALIFICATION 的结构化 Error={code,stage,attempt_id?,reservation_consumed,dispatch_may_have_happened,retryable=false} 只存 sidecar；抛入 core 的只有固定短 code，避免 core tostring(table) 丢掉原因或泄露配置。raw false 仍可返回 false，由 core 得到 WRITE_FAILED；raw 异常归为 INDETERMINATE 并抛 QSG_RAW_EXCEPTION。

## 4. 唯一 dispatch 顺序

1. 在本地非重入锁下确认 mode=QUALIFICATION、session ARMED、run generation 活跃、无旧 outstanding dispatch。否则 raw=0。
2. 同步读取并检查当前 core evidence：无 dropped_events/telemetry_error/sequence gap；绑定实际候选和退休状态。recorder 无法接受本次预写事件则 raw=0。
3. 校验 scope、phase、CE/target 身份、allocation/page 状态；要求目标自身提供新的、未使用的 prewrite checkpoint，原 bits=0x42C80000。与 CE 实际采样/候选证据关联，不由 CE 代目标制造 checkpoint。
4. reserve_once 在 broker 的 session 排他事务内再次核对授权、窗口、预算与 scope。journal+head+retained anchor 提交完整后才回复 Reservation。任一步不确定则关闭 session；CE 不派发。
5. claim_dispatch 持久标记一次 dispatch 权。Receipt 必须与当前请求、writer/epoch/generation、scope/hash、阶段和时限逐字匹配。缺 ack、过期 ack、错序、重复或来自旧连接的 ack 全部拒绝。
6. CE 在任何 IPC 之后执行最终本地 running/identity/mapping/value/retirement/deadline 复查，确认本地取消尚未发生。失败消耗原 reservation，raw=0；不得重新 reserve 同一操作。
7. 把该 receipt 标记为本地 USED，再进入唯一 captured_raw(address,value) 调用。最终检查与该调用之间不 yield、不泵 UI 消息、不等待 IPC、不执行任意 callback。一次 port 调用 raw 最多一次。
8. 记录返回/异常；额度不论结果都保留。true 才回到原 immediate readback；readback 与 target post-checkpoint 用 attempt_id/事件 digest 关联。任何记录/回读失败关闭后续派发，不自动补写。

claim 不是第二次扣额，而是同一个 consumed reservation 的一次性状态迁移。reserve 和 claim 分离，是把原 budget.py 在一个 Python 锁内调用 fake_write 的模型改为跨进程协议所必需，不能把该 Python callback 直接当成 live IPC。

跨进程只能保证此可信实现的 **at-most-once**；不能保证每个已预留操作恰好执行一次。PRECALL/DISPATCH_ATTEMPTED 是已进入派发边界的保守证据，崩溃恰发生在它与 raw 之间时仍可能没有实际写入。不能把预留或 claim 自己解释成成功，更不能因目标值未变就退款。

## 5. 预算不变量与重放/崩溃

令 R 为固定 authorization_id + qualification session_id 的所有持久 reservations（包括失败/过期/没有 raw 的记录）。D 为已审计 writer 的唯一 raw 派发边界数。

- 0 <= D <= |R| <= 3。
- R[L04]+R[L07] <= 2；R[L10] <= 1；其余 L 的 reservation=0、raw=0。
- 每个 attempt 最多一个 claim；每个 receipt 最多一个本地 raw；所有 request_id/checkpoint/nonce 永不复用。
- 成功、false、nil/非布尔、throw、partial、readback mismatch、timeout、崩溃、预留后过期均不退款、不自动重试。
- Stop/Start、public loader singleton reload、CE 重启后的受控 rebind、run ID 变化、目标 A/B 变化均不改变 enrollment 与计数。
- B 只参与 L11 拒绝，零写。正常 L04->L05->L06->L07->L08 属于同一 positive run；L10 第二个 Start 虽为同 L10，首轮已耗尽它的一次额度。
- 资格场景计划只允许 L04 一次初写和 L07 一次恢复；联合额度2并不允许把两次都用于重试 L04。broker 的 phase 机每个预定写 step 至多授权一次。
- 保留 R1 其余限制：最多9个目标实例、仅L11可2个同时存活、最多9个成功 Start、session<=60分钟、每独立 phase<=5分钟；现有每 Start 最多5次恢复/重扫限制不扩大。

| 中断点 | 持久状态 / raw 上界 | 后续规则 |
| --- | --- | --- |
| 预检查拒绝，尚无 reserve | R 不变，raw=0 | 记录 DENY；不自动修正输入重试 |
| journal 写一半或 head/anchor 不确定 | ledger 不可信，raw=0 | FAILED_CLOSED；不重建空账本、不删除 pending/lock；保守视为可能已占额，禁止后续派发 |
| reserve 已提交，ack 丢失 | R+1，raw=0 | 额度消费；不重发 reserve 换 receipt；query 只能查看 |
| reserve 后 CE/broker 崩溃 | R+1，raw<=1（依 claim/证据判断） | 无 stale-lock 自动回收；恢复须保留旧消耗，未决不能重发 |
| claim 已提交，ack 丢失/Stop/超期 | R+1，raw=0 或不确定 | claim 不可重用；旧 epoch/token 作废 |
| raw 内部 throw/返回丢失 | R+1，raw<=1 | INDETERMINATE，无 retry/refund |
| raw 后 recorder/存储失败 | R+1，本次可能已写 | 0 后续 raw；不能声称整个场景0写；核验 INCONCLUSIVE 或 FAIL |
| 重复/并发 request 或 claim | 至多首个原请求占额和派发 | 第二个明确拒绝；共享 global gate 排他，不按 client/run 单独算3次 |

新 client_epoch / writer_id 只用来使旧回执失效，不能作预算 namespace。broker 对 session 只允许一个活跃 writer；reload 必须先撤销旧 epoch，并保留已 claim 的不确定状态。已有旧回复即使合法签名/摘要一致，也不能被新 writer 接受。

Durable Store 契约是：排他所有权、追加 ledger、严格链/外部 head 核对、同步持久化成功后 ack、无 silent repair。原 budget.py 的 fsync+replace 是参考，尚非 Windows 物理断电承诺。恢复正常关闭会话和恢复崩溃会话必须分开：前者读取同一账本；后者保留锁和不确定状态，需独立审查对账，不能为了继续测试删锁。若所有存储/锚都可被同一恶意主体回滚，本设计不声称抵抗该主体。

## 6. Scope Guard 细则

每次请求和 reserve 后 final check 都必须通过，不能只在 Start 时检查：

1. 当前完整授权仍在窗口内、候选与插件/broker/runtime hashes 相符；origin=LIVE 的字符串不是授权。CE实例、broker peer 和目标实例必须与 enrollment 绑定。
2. PID 为正整数；creation FILETIME 非零且一致；held query handle 与 CE-reported token 对应同一实例并仍存活；opened PID/borrowed handle 未切换。宿主另核对目标镜像及解释器/脚本 provenance，访问失败直接拒绝。
3. allocation_id、base、65536大小、target identity、allocation generation 全匹配，来自新自有区域；不能把同 PID 的另一块内存当成相同 allocation。已释放、退役、unknown region 都拒绝。
4. 使用不溢出的差值检查：0 <= address-base <= 65532、address%4=0、base/address 在允许用户地址界限内。scan 必须等于 base..base+65535；candidate 的 address-0x20..address+0x53 全在区域内。
5. 当前整个必需结构满足原 adapter mapping/七字段规则；MEM_COMMIT、PAGE_READWRITE、MEM_PRIVATE，目标 active pages 覆盖四字节，未发生 page retire/decommit。仍保留原 Single 阈值、完整人数与唯一性检查。
6. 实际 value pack 的原始bits=许可bits；checkpoint 未使用、对应当前 phase/request，目标 self 原值和 CE prewrite 原值都为 search bits。旧成功 readback 不是新的 prewrite 授权。
7. target/adapter 两侧退休集合的并集永久拒绝，按 session+target instance+allocation+address 绑定；跨 Start 不清空。若两侧生命周期不同步，拒绝直到明确证据，但不自动重试当前 attempt。
8. session/phase/receipt 时钟不倒退，事件有明确 clock origin；最终检查仍在窗口内。禁止直接相减 CE、target、broker 的 monotonic 值。

Scope Guard 无法让 raw writeFloat 使用 broker 自己的进程 handle；检查后到 OS 写之间仍有平台竞态。最终短区间不允许本程序 yield/人工切换只是约束，不是 OS 原子性证明。CE attachment handle 独立等价性仍未验证，不能据此宣称任意并发对手下也绝不写错进程。

## 7. Supervisor 与证据绑定的具体衔接

- loader 先保留原 active/cleanup 拒绝，再验证 config，再 prepare_start；L12 的三个无效 config 不触发 broker、adapter/native 构造，诊断仍是 missing-file / WRITE_DISABLED / INVALID_SCAN_SETTINGS。
- adapter 构造期间将原 timer callback 交给 wrap_tick。before_tick 检查本地 lease 和安全状态；after_tick 排空 core.evidence 并关联 raw candidate/alias。所有异常归并为 fail-closed；清理不依赖 broker 可用。
- 在 scan 成功返回 candidate 后记录其真实地址/实例/region；core evidence 中该次 ranking_summary 的 alias/sequence 必须与此返回一一绑定。writer 再用 write_intent 事件校验同一地址。不得采用现有 support.py L143 中写死的 A0/A1 地址绑定。
- 原 core 的 address_retired 只经过被动诊断；after_tick/sync_before_write 读到该事件后按已绑定 alias 将 retire 提交 broker。没有退役确认不得授权后续恢复写。这样无需修改 core，也不依赖其 observer 抛错阻断。
- 原 core write_intent 在端口之前；新 sidecar 标注 legacy_counter_semantics=PORT_ENTRY_IN_QUALIFICATION。raw计数只由 QSG 边界记录，旧 verifier 的 intent=dispatch 断言不能用于新协议。NORMAL仍是原含义。
- 原 readback 在同一 tick 紧随成功 write，不在二者之间插入 target IPC；adapter sidecar 取实际返回 bits，after_tick 再绑定 core readback_verified 和 target 独立 post checkpoint。没有任一方则不判成功。
- phase 由已批准计划和 broker phase_sequence 驱动。L02/L03 只观察，进入 L04 写 phase 前可由外围 supervisor 暂缓下一次 tick（有界 HOLD，不执行 core callback）；阶段确认后再继续。L05/L06零写、L07恢复、L08退出均独立打点，不事后重标 write 场景。phase HOLD 不是自动写重试，超时关闭。
- Stop先递增 generation/撤销本地writer；自动 finish 的 adapter.close 同样先撤销。L10 cleanup_start_probe 在 core.cleanup_pending=true 时直接获得原拒绝；不能被新的 mode gate 抢先改成别的诊断。
- 失败初始化若尚无 core，loader负责关闭已创建adapter及run lease；若已有core，由原stop释放资源。close/timer wrapper 均要幂等；异常日志不能截断剩余清理。

## 8. IPC 契约与候选传输

仅允许本机、双向鉴别且有界的请求/响应。不接受远程主机、任意命令、Lua代码、shell、可执行路径、文件写目的地、内存dump或任意读写请求。target checkpoint 仅能取本次许可的单个四字节 word。

framing 草案：固定4字节 little-endian无符号body长度 + canonical UTF-8/ASCII JSON body；1..65536字节，先验长再分配；一次一帧，partial read/write 必须完成同一帧且不刷新整体deadline；多余/截断/坏编码/重复key/错version拒绝。request_id、单调connection_sequence、connection_epoch、message_type、session/policy digest、body digest 是必需包封；response必须回显请求digest且仅允许明确 ACK/DENY/ERROR。

仅 reserve/claim 返回短期有绑定的回执；普通 ping、query、outcome ack 不能获得写能力。pipe重连后必须新epoch，旧未决请求不重发。broker持有session独占锁并限制单个writer；不要依赖 LuaPipe.lock 的递归锁实现非重入。

拟议合成参数：每个RPC完整期限<=250ms、一个write授权流程完整期限<=1000ms、dispatch receipt本地剩余lease<=100ms；均是待验证设计上限，不是本机测量结果。每次等待必须同时受session/phase/transaction更早期限限制，不得使用0/nil无限等待或 OnAboutToTimeout 延长。超时后一律关闭连接、作废receipt、0后续raw；未决reservation仍消费。Stop应先设本地cancel再做有界等待；不得用泵UI消息换取响应性。

本机 celua.txt L3269和L3309对timeout单位相互冲突，native连接等待/取消/peer-handle可用性均NOT_RUN。R2用fake transport验证契约，不将毫秒数字盲传到CE。若真实transport达不到有界期限和peer鉴别，保持BLOCKED，不提供live writer。

候选named pipe必须显式限制DACL/本地会话，并验证实际peer PID+creation+image；不能只靠随机pipe名字。Windows文档说明可指定安全描述符和查询pipe对端PID，但是否能通过当前CE Lua接口安全取得所需handle仍待查。[Pipe access](https://learn.microsoft.com/en-us/windows/win32/ipc/named-pipe-security-and-access-rights)、[Client PID](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-getnamedpipeclientprocessid)、[Server PID](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-getnamedpipeserverprocessid)

## 9. 错误分类

| code族 / 例子 | 消费语义 | 资格结果 |
| --- | --- | --- |
| QSG_MODE_LOCKED / QSG_PLUGIN_MISSING / QSG_VERSION / QSG_NOT_ARMED | 无新reserve | 拒绝Start或port；不得fallback |
| QSG_AUTH_INVALID / QSG_CANDIDATE_HASH / QSG_PEER_UNTRUSTED | 无新reserve | FAILED_CLOSED |
| QSG_IPC_TIMEOUT / QSG_FRAME / QSG_ACK_MISMATCH / QSG_EPOCH | 若已有reserve则保留；未知则保守未决 | 不重连重发写；0后续raw |
| QSG_LEDGER_MISSING / QSG_LEDGER_CORRUPT / QSG_PERMISSION / QSG_DURABILITY / QSG_LOCKED | 不可信消耗不得归零 | 全session封锁；保留损坏文件 |
| QSG_PID / QSG_CREATION / QSG_IMAGE / QSG_CE_TARGET_CHANGED | reserve前0，reserve后已消费 | 拒绝并停止 |
| QSG_ALLOCATION / QSG_RANGE / QSG_ALIGNMENT / QSG_RETIRED / QSG_BITS / QSG_CANDIDATE | 同上 | 不扩大范围、不降阈值、不自动修复 |
| QSG_ZERO_PHASE / QSG_CAP / QSG_PHASE_SEQUENCE / QSG_EXPIRED | 同上 | 拒绝；无额度补偿 |
| QSG_REPLAY / QSG_REENTRANT / QSG_GENERATION_REVOKED | 原reservation保留，重复不加派发 | 拒绝并撤销当前run资格 |
| QSG_RECORDER_UNAVAILABLE / QSG_EVIDENCE_GAP / QSG_BINDING | 原已消费保留 | 写前raw0，写后只保证0后续raw；核验不能PASS |
| QSG_RAW_EXCEPTION / QSG_RESULT_UNCERTAIN / QSG_POSTCALL_RECORD | 已消费 | raw最多1，FAIL/INCONCLUSIVE，绝不retry |

错误记录只含固定code、阶段、ID/digest和消耗事实；不保存访问令牌、私有config内容、原生异常任意字符串或无关内存。CE原status中地址输出属于私有采证通道，公开报告只用绑定别名/摘要。

## 10. 事件schema草案

新增 qsg.event.v1 与旧 evidence schema=1 分开版本化；不改历史schema/事件。每条记录严格白名单，payload按kind校验。

| 所有事件包封字段 | 规范 |
| --- | --- |
| schema / origin / source / actor | schema=qsg.event.v1；origin=SYNTHETIC或未来专门实现的CE_LIVE/TARGET_LIVE/BROKER_HOST；DERIVED只用于结论，不能混入原始观察；当前实现不得接受live |
| authorization_id / session_id / enrollment_digest / policy_digest | 固定会话锚；synthetic明确使用测试锚，不冒充批准 |
| run_id / phase_id / phase_sequence / client_epoch / writer_id / generation | 所有跨Start/reload/phase关联均显式，不以A0字符串当全局地址 |
| event_id / stream_id / sequence / clock | 序号从1连续；stream按角色+实例+epoch唯一；UTC和monotonic字符串均附clock origin |
| kind / data / refs | kind专属payload；跨源因果使用request/attempt/checkpoint/event digest refs |
| previous_digest / content_digest | canonical JSON排除content_digest后SHA-256；首previous为全0；另存完整文件sha、条数和末head |

| kind / 发出方 | 最小payload与含义 |
| --- | --- |
| SESSION_BOUND / PHASE_ENTERED / RUN_STARTED / RUN_STOPPED / SESSION_SEALED / broker+supervisor | binding/phase/cleanup/时间窗与唯一generation；无写能力 |
| TARGET_ALLOCATION / TARGET_COMMIT / TARGET_RETIRE / TARGET_DECOMMIT / TARGET_RELEASE / target | identity、allocation/base/size/generation/page range、owning证明ref；与CE预算分开记录目标自写 |
| TARGET_CHECKPOINT / target | 真实self_sample bits、address/allocation、anchor、phase、可选attempt；pre/post分别记录 |
| CE_CANDIDATE_BOUND / CE_RETIRED / supervisor sidecar | 真实candidate地址与core run/session_token/diagnostic sequence/alias映射，结构/完整性refs |
| DECISION_DENY / scope或broker或writer | request_digest、code、stage、是否已消费、是否可能派发 |
| RESERVED / broker | attempt_id、request/scope digest、完整绑定refs、consumed=true、ledger/head/持久化证明ref |
| DISPATCH_CLAIMED / broker | attempt_id、reservation_digest、writer/epoch/generation、dispatch_nonce、expiry；只是权限消费 |
| DISPATCH_ATTEMPTED / CE QSG Writer | attempt_id、claim_digest、真实地址/bits/身份ref、local ordinal；表明派发边界，崩溃时不保证raw已完成 |
| DISPATCH_RETURNED / CE QSG Writer | attempt_id、raw_return_class TRUE/FALSE/NONBOOLEAN、raw exception固定分类；TRUE不等于verified |
| UNCERTAIN / FAILED_CLOSED / supervisor或broker | 最后可信锚、未决attempt、reason、revoke generation；必须保留历史消耗 |
| CE_READBACK / CE_CORE_VERIFIED / sidecar | 原readInteger bits、readFloat重新编码bits、core readback_verified序号、attempt、target post anchor |

recorder append失败若无法保存FAILED_CLOSED事件，本地仍必须关闭writer；离线通过缺口判INCONCLUSIVE，不能假装已经记录失败事件。ring快照与新增sidecar都应有有界容量；满时停止，不能滚掉旧证据继续验收。

## 11. 独立验证契约

Verifier输入：外部保留的policy/enrollment/bundle seals、各源原始事件、各文件sha/head/count、候选/runtime manifest及请求case列表。它独立实现预算/阶段/scope校验，不调用broker的判定函数、不相信控制器的PASS字段；允许共享纯canonical JSON/哈希编码，但不能共享授权决策结果。

1. 验证版本、来源、链和外部seal；跨actor不能相减monotonic；mixed synthetic/live不能生成LIVE_PASS。
2. 按authorization+session重建所有reservation，不因缺outcome/Stop/reload而删除；累计<=3且分组<=2/1/0。核对每个claim与reservation、每个CE派发与唯一claim，无孤立派发/重复attempt。
3. 检查所有candidate/identity/region/phase/time refs；确认退休先于后续拒绝或新址恢复，所有case有独立边界。unknown、缺源、缺alias映射不能按“未发生”处理。
4. 对成功候选要求raw返回true、原core exact-bit readback、target独立post checkpoint三者一致，且pre checkpoint先发生并未重用。两侧bits冲突=FAIL；证据缺失或raw结果未知=INCONCLUSIVE，若同时有明确违规则FAIL优先。
5. reservation无dispatch合法消费但不能算成功；claim/PRECALL无outcome也不能PASS。QUALIFICATION中的legacy意图计数可能大于raw计数，须每条由deny/reserve/dispatch解释，不套用旧intent=dispatch规则。
6. L05>=20连续有效周期、L06独立>=3漂移观察、L07同run/同实例新地址+退休；L09五项和L12三项逐项检查。目标snapshot不能证明writer是谁，也不能排除两次采样之间的瞬时写。

结论轴：DESIGN_STATUS为本设计判定；INFRA_STATUS描述组件验证；SYNTHETIC_STATUS只能是SYNTHETIC_PASS/FAIL/INCONCLUSIVE/NOT_RUN；LIVE_STATUS逐L仅在未来真实授权证据齐全时才可能LIVE_PASS，否则FAIL/INCONCLUSIVE/NOT_RUN。当前live始终NOT_RUN、G1=NOT_APPROVED，不能由新verifier的一次synthetic成功转成MVP_ACCEPTED。

可预见的未来CLI退出语义：0=全部请求项在其明确origin下证据完整；1=矛盾/违规/损坏；2=缺失/未知/未观察。退出0也不是授权标记。独立验证指逻辑与原始来源的分离，本轮只有当前Codex静态审查，没有独立人工reviewer或新增subagent验证。
