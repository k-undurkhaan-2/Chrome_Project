"""Real Lua 5.3/5.4, real Single collector/ranker, mocked CE and Win32 only.

The entrypoint's CE runtime gate is separately tested with genuine Lua versions.
No test opens a native process, loads a Win32 DLL or invokes the live helper.
"""
from importlib import import_module
import ast
from pathlib import Path
import xml.etree.ElementTree as ET

import pytest
from fixtures import ce_mvp_target_layout as layout

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
SOURCES = {p.name: p.read_text(encoding="utf-8") for p in SRC.glob("*.lua")
           if p.name.startswith("ce_mvp") or p.name in (
               "mvp0_candidate_report.lua", "mvp0_foundlist_collector.lua")}


@pytest.fixture(params=["lua53", "lua54"])
def runtime(request):
    # Missing interpreters are failures, not synthetic compatibility skips.
    module = import_module("lupa." + request.param)
    lua = module.LuaRuntime(unpack_returned_tuples=True)
    assert lua.eval("_VERSION") == {"lua53": "Lua 5.3", "lua54": "Lua 5.4"}[request.param]
    factory = lua.execute((ROOT / "tests/fixtures/ce_mvp_mock.lua").read_text(encoding="utf-8"))
    w = factory.new(lua.table_from(SOURCES))
    lua.globals().w = w
    return lua, w


def good(w):
    o = w.object(0x100128)
    assert w.start() is True
    w.until_state("MONITORING")
    return o


@pytest.mark.parametrize("edit,reason", [
    ("w.cfg.target_pid=nil", "INVALID_TARGET_PID"),
    ("w.cfg.target_pid=0", "INVALID_TARGET_PID"),
    ("w.cfg.target_pid=1.5", "INVALID_TARGET_PID"),
    ("w.cfg.target_pid='101'", "INVALID_TARGET_PID"),
    ("w.cfg.write_value=0/0", "INVALID_FLOAT32"),
    ("w.cfg.write_value=math.huge", "INVALID_FLOAT32"),
    ("w.cfg.write_value=1e39", "FLOAT32_OVERFLOW"),
    ("w.cfg.write_value='125'", "INVALID_FLOAT32"),
    ("w.cfg.write_enabled=false", "WRITE_DISABLED"),
    ("w.cfg.write_enabled='true'", "WRITE_DISABLED"),
    ("w.cfg.value_type='double'", "UNSUPPORTED_VALUE_TYPE"),
    ("w.cfg.screening_profile='full'", "UNSUPPORTED_PROFILE"),
    ("w.cfg.scan.scan_budget=129", "INVALID_SCAN_SETTINGS"),
    ("w.cfg.scan.max_candidates=1", "INVALID_SCAN_SETTINGS"),
    ("w.cfg.scan.filter_target_match=false", "INVALID_SCAN_SETTINGS"),
    ("w.cfg.scan.use_prescore_selection=false", "INVALID_SCAN_SETTINGS"),
    ("w.cfg.scan.target_value_pattern=0", "SCAN_PATTERN_MISMATCH"),
    ("w.cfg.scan.stop_address=w.cfg.scan.start_address", "INVALID_SCAN_RANGE"),
    ("w.cfg.scan.start_address='process+123'", "INVALID_SCAN_ADDRESS"),
    ("w.cfg.scan.known_true_addr=0x100128", "UNKNOWN_SCAN_FIELD"),
    ("w.cfg.monitor_interval_ms=0", "INVALID_MONITOR_INTERVAL_MS"),
    ("w.cfg.invalid_confirmations=0", "INVALID_INVALID_CONFIRMATIONS"),
    ("w.cfg.max_rescan_attempts=-1", "INVALID_MAX_RESCAN_ATTEMPTS"),
    ("w.cfg.max_backoff_ms=100;w.cfg.rescan_backoff_ms=200", "INCONSISTENT_BACKOFF"),
    ("w.cfg.log_path='bad.lua'", "INVALID_LOG_PATH"),
    ("w.cfg.engineering_extensions.h3_a4_approval=true", "UNSUPPORTED_ENGINEERING_EXTENSION"),
    ("w.cfg.engineering_extensions.strict_attachment=true", "UNSUPPORTED_ENGINEERING_EXTENSION"),
    ("setmetatable(w.cfg,{})", "INVALID_CONFIG"),
    ("w.cfg.diagnostics={enabled=true}", "INVALID_DIAGNOSTICS"),
    ("w.cfg.diagnostics={enabled='yes'}", "INVALID_DIAGNOSTICS"),
    ("w.cfg.diagnostics={enabled=false,cleanup_start_probe=true}", "INVALID_DIAGNOSTICS"),
    ("w.cfg.diagnostics={enabled=true,session_token='bad token',event_limit=512}", "INVALID_DIAGNOSTICS"),
    ("w.cfg.diagnostics={enabled=true,session_token='test',event_limit=2049}", "INVALID_DIAGNOSTICS"),
    ("w.cfg.diagnostics={enabled=false,sink=function() end}", "UNKNOWN_DIAGNOSTICS_FIELD"),
])
def test_config_rejects_before_any_ce_access(runtime, edit, reason):
    lua, w = runtime
    lua.execute(edit)
    with pytest.raises(Exception, match=reason):
        w.start()
    assert len(w.native_calls) == w.open_calls == w.reads == len(w.writes) == 0


def test_happy_path_complete_state_trace_and_twenty_monitor_ticks(runtime):
    lua, w = runtime
    good(w)
    s = w.loop.status()
    assert (s.pid, s.scan_count, s.write_count, s.last_written_bits, s.last_readback_bits) == (
        101, 1, 1, 0x42FA0000, 0x42FA0000)
    assert s.last_written == s.last_readback == 125.0
    w.step(40)
    assert w.loop.status().monitor_checks >= 20
    assert len(w.writes) == len(w.scans) == 1
    states = [v.split("state=")[1].split()[0] for _, v in s.events.items() if "state=" in v]
    assert states == ["ATTACHING", "SCREENING", "CANDIDATE_CHECK", "WRITING", "READBACK", "MONITORING"]
    assert w.loop.status().attachment_handle_status == "ATTACHMENT_HANDLE_UNVERIFIED"
    assert w.loop.status().authorization_status == "NOT_PRODUCTION_AUTHORIZED"
    assert lua.globals().MVP0 is None and lua.globals().MVP0FoundList is None
    w.loop.stop(); w.loop.stop(); w.clean()


@pytest.mark.parametrize("invalidation", ["unmapped", "unreadable", "structure", "allocation", "protection"])
def test_confirmed_invalidation_rescans_and_writes_only_fresh_address(runtime, invalidation):
    lua, w = runtime
    old = good(w)
    if invalidation == "unmapped": old.mapped = False
    elif invalidation == "unreadable": old.readable = False
    elif invalidation == "structure": old.memory[old.addr + 0x30] = 8
    elif invalidation == "allocation": old.alloc = 0x110000
    else: old.protect = 0x20
    w.object(0x101128)
    w.until_state("RESCAN_BACKOFF")
    assert w.loop.status().candidate_address is None
    w.until_state("MONITORING")
    assert [v.addr for _, v in w.writes.items()] == [0x100128, 0x101128]
    assert len(w.scans) == 2
    assert w.loop.status().last_readback_bits == 0x42FA0000
    w.loop.stop(); w.clean()


def test_finite_numeric_drift_and_transient_unreadability_do_not_write(runtime):
    _, w = runtime
    o = good(w)
    o.memory[o.addr] = 0x42280000  # 42.0; deliberately different from both config values
    w.step(40)
    o.readable = False; w.step(2)
    assert w.loop.status().invalid_count == 1
    o.readable = True; w.step(4)
    assert w.loop.status().invalid_count == 0
    assert len(w.writes) == len(w.scans) == 1
    w.loop.stop(); w.clean()


@pytest.mark.parametrize("stage", ["ATTACHING", "SCREENING", "CANDIDATE_CHECK", "WRITING", "MONITORING"])
@pytest.mark.parametrize("fault,reason", [
    ("w.alive=false", "PID_EXITED"),
    ("w.creation=w.creation+1", "PID_IDENTITY_MISMATCH"),
    ("w.opened=999", "CE_TARGET_CHANGED"),
    ("w.ce_handle=999", "CE_TARGET_CHANGED"),
    ("w.fail.times=true", "IDENTITY_UNCERTAIN"),
    ("w.fail.wait=true", "IDENTITY_UNCERTAIN"),
])
def test_identity_loss_stops_before_further_memory_operations(runtime, stage, fault, reason):
    lua, w = runtime
    w.object(0x100128); w.start()
    # ATTACHING is tested after initial attach but before scan acquisition.
    if stage == "ATTACHING": w.step()
    else: w.until_state(stage)
    writes, reads = len(w.writes), w.reads
    lua.execute(fault); w.step(20)
    s = w.loop.status()
    assert s.state == "ERROR" and reason in s.last_error
    assert len(w.writes) == writes and w.reads == reads
    w.clean()


@pytest.mark.parametrize("fault,reason", [
    ("w.fail.open=true", "PROCESS_OPEN_FAILED"),
    ("w.fail.attach=true", "CE_TARGET_CHANGED"),
    ("w.fail.ce_creation=1", "PID_IDENTITY_MISMATCH"),
    ("w.fail.native_pid=999", "PID_IDENTITY_MISMATCH"),
])
def test_attachment_rejects_before_scan(runtime, fault, reason):
    lua, w = runtime
    lua.execute(fault); w.start(); w.step()
    assert reason in w.loop.status().last_error
    assert len(w.scans) == len(w.writes) == w.reads == 0
    w.clean()


def test_no_matches_are_bounded_and_backoff_is_exponential(runtime):
    _, w = runtime
    w.start(); w.until_state("ERROR")
    assert w.loop.status().last_error == "RESCAN_LIMIT_EXHAUSTED"
    assert len(w.scans) == 4 and len(w.writes) == 0
    starts = [v.due - 50 for _, v in w.scans.items()]
    assert starts[1] - starts[0] >= 200
    assert starts[2] - starts[1] >= 200
    assert starts[3] - starts[2] >= 400
    w.clean()


@pytest.mark.parametrize("kind,reason", [
    ("ambiguous", "AMBIGUOUS_CANDIDATES"), ("weak", "CANDIDATE_NOT_QUALIFIED"),
    ("overflow", "CANDIDATE_BUDGET_EXCEEDED"), ("incomplete", "SCAN_COMPLETION_UNCERTAIN"),
    ("read_fault", "SCREENING_READ_FAILED"), ("callback", "SCREENING_CALLBACK"),
    ("timeout", "SCAN_TIMEOUT"),
])
def test_failed_screening_never_writes_and_disposes_resources(runtime, kind, reason):
    _, w = runtime
    w.object(0x100128, "weak" if kind == "weak" else None)
    if kind == "ambiguous": w.object(0x101128)
    if kind == "overflow":
        for i in range(129): w.object(0x102000 + i * 0x100)
    if kind == "incomplete": w.fail.progress = True
    if kind == "read_fault": w.fail.unreadable = 0x100108
    if kind == "callback": w.fail.initialize = "throw"
    if kind == "timeout": w.fail.no_complete = True
    w.start(); w.until_state("ERROR")
    assert reason in w.loop.status().last_error
    assert len(w.writes) == 0
    w.clean()


@pytest.mark.parametrize("fault,reason", [
    ("w.fail.write_return=false", "WRITE_FAILED"),
    ("w.fail.write_return=1", "WRITE_FAILED"),
    ("w.fail.write_nil=true", "WRITE_FAILED"),
    ("w.fail.write='throw'", "INJECTED_write"),
    ("w.fail.write_no_change=true", "READBACK_MISMATCH"),
    ("w.fail.readback_float=124.0", "READBACK_MISMATCH"),
])
def test_failed_write_and_readback_are_terminal_not_rescan_requests(runtime, fault, reason):
    lua, w = runtime
    w.object(0x100128); lua.execute(fault); w.start(); w.until_state("ERROR")
    assert reason in w.loop.status().last_error
    assert len(w.writes) <= 1 and len(w.scans) == 1
    w.step(100); assert len(w.writes) <= 1
    w.clean()


@pytest.mark.parametrize("state", ["ATTACHING", "SCREENING", "CANDIDATE_CHECK", "WRITING", "MONITORING", "RESCAN_BACKOFF"])
def test_stop_and_repeated_start_are_idempotent_and_stale_callbacks_are_inert(runtime, state):
    _, w = runtime
    if state != "RESCAN_BACKOFF": w.object(0x100128)
    w.start(); w.until_state(state)
    assert w.loop.start() == (False, "ALREADY_RUNNING")
    writes = len(w.writes)
    callbacks = [v.saved_callback for _, v in w.scans.items()]
    w.loop.stop(); w.loop.stop()
    for index, fn in enumerate(callbacks): fn(w.scans[index + 1])
    w.step(20)
    assert w.loop.status().state == "STOPPED" and len(w.writes) == writes
    w.clean()


def test_reentrant_timer_fails_closed_even_inside_swallowing_collector_pcall(runtime):
    lua, w = runtime
    w.object(0x100128); w.start()
    lua.execute("w.hook=function(event) if event=='read' then w.hook=nil; w.loop.tick() end end")
    w.until_state("ERROR")
    assert w.loop.status().last_error == "REENTRANT_TIMER"
    assert len(w.writes) == 0
    w.clean()


def test_mutated_config_and_status_snapshot_cannot_change_run(runtime):
    _, w = runtime
    w.object(0x100128); w.start()
    w.cfg.target_pid = 999; w.cfg.write_value = 9; w.cfg.scan.target_value_pattern = 0
    w.loop.status().state = "WRITING"
    w.until_state("MONITORING")
    assert w.writes[1].value == 125
    w.loop.stop(); w.clean()


def test_cleanup_uncertainty_blocks_restart_and_is_observable(runtime):
    lua, w = runtime
    enable_diagnostics(lua)
    good(w); w.fail.close = True
    w.loop.stop()
    assert w.loop.status().state == "ERROR" and w.loop.status().cleanup_ok is False
    assert w.loop.start() == (False, "CLEANUP_UNCERTAIN_RELOAD_CE")
    assert w.loop.evidence().cleanup_ok is False
    assert events(w, "query_handle_close")[0].api_success is False
    assert events(w, "cleanup_complete")[0].cleanup_ok is False


def test_clock_rollback_and_logging_failure_never_enable_more_writes(runtime):
    _, w = runtime
    good(w); w.fail.log = "throw"; w.time = 0; w.loop.tick()
    assert w.loop.status().last_error == "CLOCK_UNCERTAIN"
    assert w.loop.status().log_error == "LOG_OUTPUT_FAILED"
    assert len(w.writes) == 1
    w.clean()


def test_exact_float32_rounding(runtime):
    _, w = runtime
    for requested, expected_bits in [(0.1, 0x3DCCCCCD), (-0.0, 0x80000000), (1e-46, 0)]:
        rounded, bits = w.core.float32(requested)
        assert bits == expected_bits


@pytest.mark.parametrize("requested,bits", [(0.1, 0x3DCCCCCD), (-0.0, 0x80000000)])
def test_transaction_writes_the_rounded_float32_and_verifies_exact_bits(runtime, requested, bits):
    _, w = runtime
    w.cfg.write_value = requested
    good(w)
    s = w.loop.status()
    assert s.last_written_bits == s.last_readback_bits == bits
    w.loop.stop(); w.clean()


def test_table_has_no_open_time_script_or_active_record_and_lua_syntax_is_real(runtime):
    lua, _ = runtime
    table = ET.parse(SRC / "ce_mvp.CT").getroot()
    assert table.find("LuaScript") is None
    assert table.findall(".//Active") == []
    for entry in table.findall(".//AssemblerScript"):
        for code in entry.text.split("{$lua}")[1:]:
            lua.compile(code.split("{$asm}")[0])
    for name, code in SOURCES.items(): lua.compile(code, name=name)


def test_loader_is_inert_and_singleton(runtime):
    lua, _ = runtime
    entry = SOURCES["ce_mvp.lua"]
    lua.execute("loadfile=function() error('UNEXPECTED_FILE_ACCESS') end")
    api = lua.execute(entry, name="@D:/repo/src/ce_mvp.lua")
    api2 = lua.execute(entry, name="@D:/repo/src/ce_mvp.lua")
    lua.globals().api, lua.globals().api2 = api, api2
    assert lua.eval("api==api2") is True
    ok, reason = api.start()
    assert ok is False
    assert ("UNEXPECTED_FILE_ACCESS" if lua.eval("_VERSION") == "Lua 5.3"
            else "CE_ENTRYPOINT_REQUIRES_LUA_5_3") in reason


def test_ranked_qualified_object_is_not_first_foundlist_entry(runtime):
    _, w = runtime
    w.object(0x100128, "weak"); w.object(0x101128)
    w.start(); w.until_state("MONITORING")
    assert w.writes[1].addr == 0x101128
    w.loop.stop(); w.clean()


def test_empty_then_qualified_population_recovers_after_backoff(runtime):
    _, w = runtime
    w.start(); w.until_state("RESCAN_BACKOFF"); w.object(0x100128)
    w.until_state("MONITORING")
    assert len(w.writes) == 1 and len(w.scans) == 2
    w.loop.stop(); w.clean()


def test_retired_address_cannot_be_reused_after_it_becomes_readable_again(runtime):
    _, w = runtime
    o = good(w); o.readable = False
    w.until_state("RESCAN_BACKOFF")
    o.readable = True; o.memory[o.addr] = 0x42C80000
    w.until_state("ERROR")
    assert w.loop.status().last_error == "RETIRED_CANDIDATE"
    assert len(w.writes) == 1
    w.clean()


def test_no_retry_budget_stops_on_invalidation(runtime):
    _, w = runtime
    w.cfg.max_rescan_attempts = 0
    o = good(w); o.mapped = False
    w.until_state("ERROR")
    assert w.loop.status().last_error == "RESCAN_LIMIT_EXHAUSTED"
    assert len(w.scans) == len(w.writes) == 1
    w.clean()


@pytest.mark.parametrize("change", ["o.memory[o.addr]=0x42280000", "o.memory[o.addr+0x30]=0", "o.mapped=false"])
def test_prewrite_revalidation_aborts_changed_candidates(runtime, change):
    lua, w = runtime
    lua.globals().o = w.object(0x100128)
    w.start(); w.until_state("WRITING"); lua.execute(change); w.step()
    assert w.loop.status().last_error == "PREWRITE_CANDIDATE_CHANGED"
    assert len(w.writes) == 0
    w.clean()


@pytest.mark.parametrize("hook,reason", [
    ("first_scan", "INJECTED_first_scan"),
    ("destroy_scan", "SCAN_CLEANUP_FAILED"),
    ("destroy_foundlist", "FOUNDLIST_CLEANUP_FAILED"),
])
def test_partial_resource_creation_and_cleanup_failure(runtime, hook, reason):
    _, w = runtime
    w.object(0x100128); w.fail[hook] = "throw"
    w.start(); w.until_state("ERROR")
    assert reason in w.loop.status().last_error
    assert len(w.writes) == 0
    if hook.startswith("destroy"):
        assert w.loop.status().cleanup_ok is False
        assert w.loop.start() == (False, "CLEANUP_UNCERTAIN_RELOAD_CE")
    w.clean()


def test_logging_failure_before_attach_is_terminal(runtime):
    _, w = runtime
    w.fail.log = "throw"
    assert w.start() == (False, "LOG_OUTPUT_FAILED")
    assert w.loop.status().state == "ERROR"
    assert w.open_calls == len(w.writes) == 0
    w.clean()


def test_bounded_logging_reserves_terminal_reason(runtime):
    _, w = runtime
    w.cfg.log_limit = 16; w.cfg.max_rescan_attempts = 15
    w.cfg.max_backoff_ms = 100
    w.start(); w.until_state("ERROR")
    assert len(w.lines) <= 16 and len(w.loop.status().events) <= 16
    assert "stop_reason=RESCAN_LIMIT_EXHAUSTED" in w.lines[len(w.lines)]
    w.clean()


@pytest.mark.parametrize("fault,reason", [
    ("w.ce.readFloat=nil", "CE_API_MISSING:readFloat"),
    ("w.ce.vtDword=nil", "CE_ENUM_MISSING:vtDword"),
    ("w.fail.ce_version=5", "REQUIRES_CE_7_6"),
    ("w.fail.x86=true", "REQUIRES_CE_X64_WINDOWS"),
    ("w.fail.symbol='GetProcessTimes'", "WIN32_API_MISSING:GetProcessTimes"),
])
def test_missing_native_capabilities_are_explicit_and_never_attach(runtime, fault, reason):
    lua, w = runtime
    lua.execute(fault)
    with pytest.raises(Exception, match=reason): w.start()
    assert w.open_calls == len(w.scans) == len(w.writes) == w.streams == 0


def test_readback_failure_does_not_become_invalidation(runtime):
    lua, w = runtime
    w.object(0x100128); w.start(); w.until_state("WRITING")
    lua.execute("w.hook=function(event) if event=='write' then w.hook=nil; w.fail.unreadable=0x100128 end end")
    w.until_state("ERROR")
    assert w.loop.status().last_error == "READBACK_MISMATCH"
    assert len(w.writes) == len(w.scans) == 1
    w.clean()


def test_actual_loader_and_ct_start_stop_scripts_under_mock_ce(runtime):
    lua, w = runtime
    # Exercise saved configuration loading, native adapter wiring and the public
    # singleton, not just construction through the test factory.
    lua.globals().sources = lua.table_from(SOURCES)
    enable_diagnostics(lua)
    lua.execute("""
      for k,v in pairs(w.ce) do _G[k]=v end
      loadfile=function(path, mode, env)
        local name=path:match('[^/\\\\]+$')
        if name=='ce_mvp_config.local.lua' then
          assert(env.openProcess==nil and env.io==nil)
          return function() return w.cfg end
        end
        if name=='ce_mvp_adapter.lua' then
          return function()
            local m=assert(load(sources[name], '@'..path, mode, env))()
            local new=m.new
            m.new=function(cfg,ce,loader) return new(cfg,ce,loader,'synthetic') end
            return m
          end
        end
        return load(assert(sources[name]), '@'..path, mode, env)
      end
      dofile=function(path) return assert(loadfile(path,'t',_G))() end
    """)
    entry = SOURCES["ce_mvp.lua"]
    api = lua.execute(entry, name="@D:/repo/src/ce_mvp.lua")
    if lua.eval("_VERSION") != "Lua 5.3":
        assert api.start()[0] is False
        assert w.open_calls == 0
        return
    prestart = lua.execute((ROOT / "tests/fixtures/ce_mvp_prestart_guard.lua").read_text(encoding="utf-8"))
    guard = prestart.new(lua.globals(), "synthetic")
    guard.install()
    w.cfg.write_enabled = False
    assert "WRITE_DISABLED" in api.start()[1]
    w.cfg.write_enabled = True; w.cfg.scan.scan_budget = 129
    assert "INVALID_SCAN_SETTINGS" in api.start()[1]
    w.cfg.scan.scan_budget = 128
    assert all(value == 0 for _, value in guard.snapshot().attempted_calls.items())
    assert api.evidence().reason == "NO_RUN"
    guard.restore()
    w.object(0x100128)
    script = ET.parse(SRC / "ce_mvp.CT").find(".//AssemblerScript").text
    enable, disable = script.split("[DISABLE]")
    start_code = enable.split("{$lua}")[1].split("{$asm}")[0]
    stop_code = disable.split("{$lua}")[1].split("{$asm}")[0]
    lua.globals().syntaxcheck = True; lua.execute(start_code)
    assert w.open_calls == w.active_timers == 0
    lua.globals().syntaxcheck = False; lua.execute(start_code)
    assert api.start() == (False, "ALREADY_RUNNING")
    w.step(80)
    assert api.status().state == "MONITORING" and len(w.writes) == 1
    lua.execute(stop_code); w.clean()
    w.objects[1].memory[0x100128] = 0x42C80000
    lua.execute(start_code); w.step(80)
    assert len(w.writes) == 2 and api.status().state == "MONITORING"
    lua.execute(stop_code); w.clean()
    w.objects[1].memory[0x100128] = 0x42C80000
    w.cfg.diagnostics.cleanup_start_probe = True
    lua.execute(start_code); w.step(2)  # owned scan is still pending
    lua.execute("""
      w.hook=function(event)
        if event=='destroy_scan' then
          w.hook=nil
          local ok,reason=H3A7_CE_MVP.start()
          assert(not ok and reason=='CLEANUP_IN_PROGRESS')
          w.restart_during_cleanup_blocked=true
        end
      end
    """)
    lua.execute(stop_code)
    assert w.restart_during_cleanup_blocked is True and len(w.writes) == 2
    evidence = api.evidence()
    assert evidence.source == "synthetic"
    probes = [e for _, e in evidence.events.items() if e.event_type == "cleanup_start_probe"]
    assert len(probes) == 1 and probes[0].accepted is False
    assert probes[0].reason == "CLEANUP_IN_PROGRESS"
    assert evidence.counters.rejected_starts == 2  # one built-in and one mock reentry
    reads, native = w.reads, len(w.native_calls)
    api.print_evidence()
    printed = [line for _, line in w.lines.items() if line.startswith("[H3-A7-EVIDENCE]")]
    assert printed and 'source="synthetic"' in printed[-1]
    assert "counters.adapter_write_attempts=0" in printed[-1]
    assert "0x100128" not in "\n".join(printed)
    assert (w.reads, len(w.native_calls)) == (reads, native)
    w.clean()


def test_manual_fixture_is_statically_inert_and_matches_real_qualified_structure(runtime):
    _, w = runtime
    source = (ROOT / "tests/ce_mvp_disposable_target.py").read_text(encoding="utf-8")
    tree = ast.parse(source)  # Do not import or execute any native target code.
    assert all(isinstance(n, (ast.Import, ast.ImportFrom, ast.FunctionDef, ast.If, ast.Expr)) for n in tree.body)
    assert len([n for n in tree.body if isinstance(n, ast.If)]) == 1
    assert ast.unparse(tree.body[-1].test) == "__name__ == '__main__'"
    assert ast.unparse(tree.body[-1].body[0]) == "main()"
    compile(source, "manual_fixture", "exec")
    o = w.object(0x100128)
    for offset, bits in layout.STRUCTURE.items():
        assert o.memory[o.addr + offset] == bits
    w.start(); w.until_state("MONITORING"); w.loop.stop(); w.clean()


def enable_diagnostics(lua, *, limit=512, cleanup_probe=False):
    lua.execute("w.cfg.diagnostics={enabled=true,session_token='R1-synthetic',event_limit=%d,"
                "cleanup_start_probe=%s}" % (limit, str(cleanup_probe).lower()))


def events(w, kind):
    return [e for _, e in w.loop.evidence().events.items() if e.event_type == kind]


@pytest.mark.parametrize("mode,count", [
    ("baseline_unique", 1), ("zero_match", 0), ("ambiguous", 2), ("over_limit", 129),
    ("incomplete_structure", 1), ("invalid_structure", 1), ("value_drift", 0), ("relocate", 1),
])
def test_fixture_bytes_and_bounds_without_native_target(mode, count):
    import struct
    p = layout.plan(mode, 1 if mode == "relocate" else 0)
    memory = bytearray(layout.RESERVATION_SIZE)
    for offset, bits in p["words"].items():
        assert offset % 4 == 0 and offset // layout.PAGE_SIZE in p["pages"]
        struct.pack_into("<I", memory, offset, bits)
    matches = [a for a in range(0, len(memory), 4)
               if a // layout.PAGE_SIZE in p["pages"] and struct.unpack_from("<I", memory, a)[0] == layout.SEARCH_BITS]
    assert len(matches) == count
    assert len(memory) == 65536 and len(p["pages"]) <= 2
    assert all(a - 0x20 >= 0 and a + 0x53 < len(memory) for a in matches)
    if mode == "incomplete_structure":
        assert matches[0] // layout.PAGE_SIZE in p["pages"]
        assert (matches[0] + 0x30) // layout.PAGE_SIZE not in p["pages"]
    elif mode == "invalid_structure":
        assert all(struct.unpack_from("<I", memory, matches[0] + k)[0] == 0 for k in layout.STRUCTURE)


def test_fixture_command_transitions_are_bounded_and_drift_is_value_only():
    drift = layout.transition("value_drift", "baseline_unique", 0)
    assert drift["words"] == {0x128: layout.DRIFT_BITS}
    relocated = layout.transition("relocate", drift["mode"], 0)
    assert relocated["pages"] == (1,) and relocated["positions"] == (0x1128,)
    assert layout.transition("drift", "relocate", 1)["words"] == {0x1128: layout.DRIFT_BITS}
    for page in range(15):
        assert layout.transition("relocate", "relocate", page)["pages"] == (page + 1,)
    for mode, page, command in [("relocate", 15, "relocate"), ("ambiguous", 0, "relocate"),
                                ("over_limit", 0, "drift"), ("baseline_unique", 0, "arbitrary")]:
        with pytest.raises(ValueError):
            layout.transition(command, mode, page)
    for mode in layout.MODES[:6]:
        assert layout.transition(mode, "zero_match", 0) == layout.plan(mode)


@pytest.mark.parametrize("mode,count,reason", [
    ("baseline_unique", 1, None), ("zero_match", 0, "RESCAN_LIMIT_EXHAUSTED"),
    ("ambiguous", 2, "AMBIGUOUS_CANDIDATES"), ("over_limit", 129, "CANDIDATE_BUDGET_EXCEEDED"),
    ("incomplete_structure", 1, "SCREENING_READ_FAILED"),
    ("invalid_structure", 1, "CANDIDATE_NOT_QUALIFIED"),
])
def test_actual_fixture_layout_through_unchanged_collector_and_ranker(runtime, mode, count, reason):
    lua, w = runtime
    enable_diagnostics(lua)
    p = layout.plan(mode)
    w.use_layout(lua.table_from(p["pages"]), lua.table_from(p["words"]))
    w.start(); w.until_state("ERROR" if reason else "MONITORING")
    population = events(w, "scan_population")[0]
    assert population.raw_match_count == count and population.hard_limit == 128
    assert len(w.scans[1].addresses) == count
    if reason:
        assert reason in w.loop.status().last_error
        assert len(w.writes) == w.loop.evidence().counters.adapter_write_attempts == 0
    else:
        ranking = events(w, "ranking_summary")[0]
        assert ranking.qualified_count == 1 and ranking.recommendation == "ACCEPT"
        assert ranking.best_score >= 30 and ranking.hard_pass is True
        assert events(w, "candidate_population")[0].collection_complete is True
        assert w.loop.evidence().counters.verified_writes == 1
    if mode == "ambiguous":
        assert events(w, "ranking_summary")[0].qualified_count == 2
    if mode == "over_limit":
        blocked = events(w, "scan_population_blocked")[0]
        assert blocked.raw_match_count == 129 and blocked.collection_complete is False
        assert events(w, "scan_progress") == []  # no extra native query for telemetry
    if mode == "incomplete_structure":
        assert events(w, "candidate_population")[0].read_failure is True
    if mode == "invalid_structure":
        assert events(w, "ranking_summary")[0].qualified_count == 0
    w.loop.stop(); w.clean()


def test_diagnostics_snapshots_are_readonly_and_distinguish_twenty_stable_cycles_drift_relocation(runtime):
    lua, w = runtime
    enable_diagnostics(lua)
    old = good(w)
    before = w.loop.evidence()
    reads, native = w.reads, len(w.native_calls)
    before.counters.adapter_read_calls = -99
    before.events[1].state_after = "MUTATED"
    fresh = w.loop.evidence()
    assert fresh.counters.adapter_read_calls == reads
    assert fresh.events[1].state_after == "ATTACHING"
    assert w.reads == reads and len(w.native_calls) == native
    assert fresh.identity.query_token == fresh.identity.ce_reported_token == w.loop.status().identity_token
    w.step(40)
    stable = w.loop.evidence()
    assert stable.counters.valid_monitor_checks - fresh.counters.valid_monitor_checks == 20
    assert stable.counters.invalid_monitor_checks == 0
    assert stable.counters.adapter_write_attempts == stable.counters.adapter_scan_invocations == 1
    assert stable.counters.adapter_read_calls == w.reads
    old.memory[old.addr] = layout.DRIFT_BITS
    w.step(6)
    drift = w.loop.evidence()
    assert drift.counters.valid_monitor_checks - stable.counters.valid_monitor_checks == 3
    assert drift.counters.adapter_write_attempts == drift.counters.adapter_scan_invocations == 1
    assert events(w, "valid_value_observed")[-1].value_bits == layout.DRIFT_BITS
    old.mapped = False; w.object(0x101128)
    w.until_state("RESCAN_BACKOFF"); w.until_state("MONITORING")
    assert events(w, "address_retired")[0].address_label == "A0"
    verified = events(w, "readback_verified")
    assert [e.address_label for e in verified] == ["A0", "A1"]
    assert all(e.write_intent_bits == e.readback_bits == e.float_bits == 0x42FA0000 for e in verified)
    e = w.loop.evidence()
    assert e.counters.adapter_readback_calls == e.counters.verified_writes == 2
    assert e.counters.adapter_read_calls == w.reads and e.source == "synthetic"
    assert all(row.address is None and row.source == "synthetic" for _, row in e.events.items())
    w.loop.stop(); w.clean()


@pytest.mark.parametrize("fault,successes", [("write_no_change", 1), ("write_nil", 0), ("write", 0)])
def test_telemetry_distinguishes_attempt_success_and_verified_write(runtime, fault, successes):
    lua, w = runtime
    enable_diagnostics(lua)
    w.object(0x100128); w.fail[fault] = "throw" if fault == "write" else True
    w.start(); w.until_state("ERROR")
    evidence = w.loop.evidence()
    assert evidence.counters.adapter_write_attempts == 1
    assert evidence.counters.adapter_write_successes == successes
    assert evidence.counters.verified_writes == 0
    assert evidence.stop_reason and events(w, "cleanup_complete")[0].cleanup_ok is True
    w.clean()


def test_telemetry_cancel_cleanup_probe_and_late_callbacks(runtime):
    lua, w = runtime
    enable_diagnostics(lua, cleanup_probe=True)
    w.start(); w.step(2)
    assert w.loop.start() == (False, "ALREADY_RUNNING")
    callback = w.scans[1].saved_callback
    w.loop.stop(); w.loop.stop()
    evidence = w.loop.evidence()
    probe = events(w, "cleanup_start_probe")[0]
    assert probe.call_ok is True and probe.accepted is False and probe.reason == "CLEANUP_IN_PROGRESS"
    assert evidence.counters.cleanup_attempts == 1 and evidence.counters.rejected_starts == 2
    assert evidence.counters.scan_cancel_requests == evidence.counters.scan_disposals == 1
    callback(w.scans[1]); w.step(40)
    assert w.loop.evidence().last_sequence == evidence.last_sequence
    assert w.reads == len(w.writes) == 0
    w.clean()


def test_telemetry_identity_mismatch_shows_no_reads_or_writes_after_switch(runtime):
    lua, w = runtime
    enable_diagnostics(lua); good(w)
    before = w.loop.evidence()
    w.opened = 999; w.step(10)
    after = w.loop.evidence()
    assert after.stop_reason == "CE_TARGET_CHANGED"
    assert after.identity.check_complete is False
    assert after.counters.identity_checks == before.counters.identity_checks + 1
    assert after.counters.adapter_read_calls == before.counters.adapter_read_calls
    assert after.counters.adapter_write_attempts == before.counters.adapter_write_attempts
    w.clean()


def test_diagnostics_disabled_and_bounded_ring_report_honestly(runtime):
    lua, w = runtime
    good(w)
    assert w.loop.evidence().enabled is False
    w.loop.stop(); w.clean()
    enable_diagnostics(lua, limit=32)
    w.objects[1].memory[0x100128] = layout.SEARCH_BITS
    w.start(); w.until_state("MONITORING"); w.step(100)
    e = w.loop.evidence()
    assert len(e.events) == 32 and e.dropped_events > 0 and e.telemetry_error is None
    assert e.counters.valid_monitor_checks == 50
    assert e.events[1].sequence == e.dropped_events + 1
    w.loop.stop(); w.clean()


def test_incomplete_scan_progress_is_separate_from_incomplete_structure(runtime):
    lua, w = runtime
    enable_diagnostics(lua)
    w.object(0x100128); w.fail.progress = True
    w.start(); w.until_state("ERROR")
    progress = events(w, "scan_progress")[0]
    assert progress.scanned_addresses < progress.total_addresses
    assert "SCAN_COMPLETION_UNCERTAIN" in w.loop.status().last_error
    assert events(w, "scan_population_complete") == []
    assert w.loop.evidence().counters.adapter_write_attempts == 0
    w.clean()


@pytest.mark.parametrize("scenario", ["unique", "empty", "ambiguous", "overflow", "read_failure", "switch"])
def test_opt_in_diagnostics_preserves_operation_order_and_terminal_decisions(runtime, scenario):
    lua, _ = runtime
    factory = lua.execute((ROOT / "tests/fixtures/ce_mvp_mock.lua").read_text(encoding="utf-8"))
    observed = []
    for diagnostics in (False, True):
        w = factory.new(lua.table_from(SOURCES)); lua.globals().w = w
        if diagnostics:
            enable_diagnostics(lua)
        if scenario != "empty":
            w.object(0x100128)
        if scenario == "ambiguous":
            w.object(0x101128)
        if scenario == "overflow":
            for index in range(128):
                w.object(0x102000 + index * 0x100)
        if scenario == "read_failure":
            w.fail.unreadable = 0x100108
        w.start()
        if scenario == "switch":
            w.until_state("MONITORING"); w.opened = 999
        w.until_state("MONITORING" if scenario == "unique" else "ERROR")
        if scenario == "unique":
            w.step(40)
        w.loop.stop(); w.clean()
        s = w.loop.status()
        native = [(v.name, tuple(a for _, a in v.args.items())) for _, v in w.native_calls.items()]
        observed.append((native, w.reads, len(w.writes), s.state, s.last_error, s.stop_reason,
                         s.scan_count, s.write_count, s.monitor_checks))
    assert observed[0] == observed[1]


def test_l01_prestart_api_guard_is_inert_counts_attempts_and_restores(runtime):
    lua, w = runtime
    module = lua.execute((ROOT / "tests/fixtures/ce_mvp_prestart_guard.lua").read_text(encoding="utf-8"))
    guard = module.new(w.ce, "synthetic")
    assert guard.snapshot().installed is False and w.reads == 0
    guard.install()
    # Loading the product entry and AA syntax checking must make zero attempts.
    lua.execute(SOURCES["ce_mvp.lua"], name="@D:/repo/src/ce_mvp.lua")
    lua.globals().syntaxcheck = True
    for script in ET.parse(SRC / "ce_mvp.CT").findall(".//AssemblerScript"):
        for code in script.text.split("{$lua}")[1:]:
            lua.execute(code.split("{$asm}")[0])
    assert all(v == 0 for _, v in guard.snapshot().attempted_calls.items())
    with pytest.raises(Exception, match="L01_UNEXPECTED_API:writeFloat"):
        w.ce.writeFloat(0x100128, 125)
    assert guard.snapshot().attempted_calls.writeFloat == 1 and len(w.writes) == 0
    guard.restore(); guard.restore()
    assert guard.snapshot().installed is False
