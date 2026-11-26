"""Real Lua 5.3/5.4, real Single collector/ranker, mocked CE and Win32 only.

The entrypoint's CE runtime gate is separately tested with genuine Lua versions.
No test opens a native process, loads a Win32 DLL or invokes the live helper.
"""
from importlib import import_module
import ast
import json
import platform
import time
from pathlib import Path
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET

import pytest
from fixtures import ce_mvp_target_layout as layout
from prepare_ce_mvp import MODULES, REQUIRED_FILES, lua_path, prepare

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
SOURCES = {name: (SRC / name).read_text(encoding="utf-8")
           for name in (*MODULES, "ce_mvp_config.example.lua")}


@pytest.fixture(params=["lua53", "lua54"])
def runtime(request):
    return make_runtime(request.param)


def make_runtime(version):
    # Missing interpreters are failures, not synthetic compatibility skips.
    module = import_module("lupa." + version)
    lua = module.LuaRuntime(unpack_returned_tuples=True, max_memory=256 * 1024 * 1024)
    assert lua.eval("_VERSION") == {"lua53": "Lua 5.3", "lua54": "Lua 5.4"}[version]
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
    ("w.cfg.scan.scan_budget=65537", "INVALID_SCAN_SETTINGS"),
    ("w.cfg.scan.max_candidates=129", "INVALID_SCAN_SETTINGS"),
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


@pytest.mark.parametrize("action,reason", [("w.loop.stop()", "OPERATOR_STOP"),
                                          ("w.loop.tick()", "REENTRANT_TIMER")])
def test_process_cancellation_inside_guarded_reader_cannot_resume_writing(runtime, action, reason):
    lua, w = runtime
    process_population(lua, w, 129, (129,))
    lua.execute("w.hook=function(e) if e=='read' then w.hook=nil; " + action + " end end")
    w.start(); w.step(20)
    assert reason in w.loop.status().stop_reason and len(w.writes) == 0
    assert not w.loop.status().scope_complete
    w.clean()


def test_process_scope_relocation_retires_old_address_and_preserves_one_write_per_selection(runtime):
    lua, w = runtime
    process_population(lua, w, 1, (1,))
    w.cfg.max_rescan_attempts = 1
    w.start(); w.until_state("MONITORING")
    w.objects[1].memory[w.objects[1].addr] = 0x42280000
    w.step(20)
    assert len(w.writes) == len(w.scans) == 1
    w.objects[1].mapped = False
    w.object(0x102128)
    w.until_state("RESCAN_BACKOFF"); w.until_state("MONITORING")
    assert [row.addr for _, row in w.writes.items()] == [0x100128, 0x102128]
    assert w.loop.status().raw_match_count == w.loop.status().evaluated_count == 1
    assert w.loop.status().scope_complete
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
    ("ambiguous", "CANDIDATE_NOT_QUALIFIED"), ("weak", "CANDIDATE_NOT_QUALIFIED"),
    ("overflow", "CANDIDATE_NOT_QUALIFIED"), ("incomplete", "SCAN_COMPLETION_UNCERTAIN"),
    ("read_fault", "SCREENING_READ_FAILED"), ("callback", "SCREENING_CALLBACK"),
    ("timeout", "SCAN_TIMEOUT"),
])
def test_failed_screening_never_writes_and_disposes_resources(runtime, kind, reason):
    lua, w = runtime
    reset_worker_counters(lua, w)
    w.object(0x100128, "weak" if kind == "weak" else None)
    if kind == "ambiguous": w.object(0x101128)
    if kind == "overflow":
        for i in range(129): w.object(0x102000 + i * 0x100)
    if kind == "incomplete": qualification_mode(lua)
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
    reset_worker_counters(lua, w)
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


def test_builtin_clock_runs_when_zero_argument_native_bridge_returns_nil(runtime):
    _, w = runtime
    symbol = w.ce.getAddressSafe("kernel32.GetTickCount64", True)
    for tick in (350241093, 350241203, 350241328):
        w.time = tick
        assert w.ce.executeCodeLocalEx(symbol) is None
        assert w.ce.getTickCount() == tick
    process_scope(w)
    good(w)
    w.loop.stop(); w.clean()
    calls = list(w.native_calls.values())[3:]
    assert all(call.name != "GetTickCount64" and len(call.args) > 0 for call in calls)
    assert {call.name for call in calls} == {
        "OpenProcess", "CloseHandle", "GetProcessId", "GetProcessTimes",
        "WaitForSingleObject", "VirtualQueryEx", "GetSystemInfo",
    }


def test_builtin_clock_needs_no_native_clock_symbol(runtime):
    _, w = runtime
    w.fail.symbol = "GetTickCount64"
    good(w)
    assert w.loop.status().last_readback_bits == 0x42FA0000
    w.loop.stop(); w.clean()


@pytest.mark.parametrize("provider", ["nil", "false", "42"])
def test_missing_builtin_clock_rejects_before_attachment(runtime, provider):
    lua, w = runtime
    lua.execute("w.ce.getTickCount=" + provider)
    with pytest.raises(Exception, match="CE_API_MISSING:getTickCount"):
        w.start()
    assert len(w.native_calls) == w.open_calls == w.opened == w.reads == 0
    assert len(w.scans) == len(w.writes) == len(w.timers) == 0
    w.clean()


BAD_TICKS = ["nil", "-1", "0.5", "math.huge", "-math.huge", "0/0",
             "'100'", "false", "math.maxinteger * 1.0 + 4096", "w.time-1"]


@pytest.mark.parametrize("tick", BAD_TICKS)
@pytest.mark.parametrize("stage", ["ATTACHING", "SCREENING", "CANDIDATE_CHECK", "WRITING", "MONITORING"])
def test_invalid_builtin_clock_stops_before_further_work(runtime, stage, tick):
    lua, w = runtime
    w.object(0x100128); w.start(); w.until_state(stage)
    before = (w.open_calls, w.opened, len(w.scans), w.reads, len(w.writes))
    last_check = w.loop.status().last_check_ms
    lua.execute("w.hook=function(e) if e=='getTickCount' then w.time=" + tick + " end end")
    w.loop.tick(); w.loop.tick()
    s = w.loop.status()
    assert s.state == "ERROR" and s.stop_reason == "CLOCK_UNCERTAIN"
    assert s.last_check_ms == last_check and s.cleanup_ok
    assert (w.open_calls, w.opened, len(w.scans), w.reads, len(w.writes)) == before
    if stage == "ATTACHING":
        assert before == (0, 0, 0, 0, 0) and s.identity_token is None
        assert s.scan_count == s.write_count == s.cycle_id == 0 and not s.scope_resolved
    w.clean()


@pytest.mark.parametrize("tick", BAD_TICKS[:-1] + ["0"])
def test_collection_rejects_bad_builtin_tick_after_valid_control_tick(runtime, tick):
    lua, w = runtime
    w.object(0x100128); w.start(); w.step(2)
    reads = w.reads
    lua.execute("""
      local calls=0
      w.hook=function(e)
        if e=='getTickCount' then
          calls=calls+1
          if calls==2 then w.time=""" + tick + """ end
        end
      end
    """)
    w.step(); w.loop.tick()
    s = w.loop.status()
    assert s.last_check_ms == 150 and s.stop_reason == "CLOCK_UNCERTAIN"
    assert s.state == "ERROR" and s.cleanup_ok
    assert w.reads == reads and len(w.scans) == 1 and len(w.writes) == 0
    w.clean()


def test_builtin_clock_keeps_collection_timeout_on_shared_origin(runtime):
    lua, w = runtime
    w.object(0x100128); w.start(); w.step(2)
    reads = w.reads
    lua.execute("""
      local calls=0
      w.hook=function(e)
        if e=='getTickCount' then
          calls=calls+1
          if calls==2 then w.time=w.time+w.cfg.scan_timeout_ms end
        end
      end
    """)
    w.step()
    s = w.loop.status()
    assert s.last_check_ms == 150 and s.stop_reason == "SCAN_TIMEOUT"
    assert s.state == "ERROR" and w.reads == reads and len(w.writes) == 0
    w.clean()


@pytest.mark.parametrize("origin", [0, 0xFFFFFFFF - 100, 2**53 + 1])
def test_builtin_clock_preserves_full_width_and_equal_ticks(runtime, origin):
    _, w = runtime
    w.time = origin
    good(w)
    s = w.loop.status()
    assert s.last_check_ms == w.time and s.last_check_ms > origin
    for _ in range(5):
        w.loop.tick()
    after = w.loop.status()
    assert after.state == "MONITORING" and after.last_check_ms == s.last_check_ms
    assert after.monitor_checks == s.monitor_checks and len(w.scans) == len(w.writes) == 1
    w.step(2)
    assert w.loop.status().monitor_checks == s.monitor_checks + 1
    w.loop.stop(); w.clean()


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


def test_actual_loader_and_ct_start_stop_scripts_under_mock_ce(runtime, tmp_path):
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
    source_dir = portable_source(tmp_path)
    table_path = prepare(source_dir)
    entry = SOURCES["ce_mvp.lua"]
    api = lua.execute(entry, name="@" + (source_dir / "ce_mvp.lua").as_posix())
    if lua.eval("_VERSION") != "Lua 5.3":
        assert api.start()[0] is False
        assert w.open_calls == 0
        return
    prestart = lua.execute((ROOT / "tests/fixtures/ce_mvp_prestart_guard.lua").read_text(encoding="utf-8"))
    guard = prestart.new(lua.globals(), "synthetic")
    guard.install()
    w.cfg.write_enabled = False
    assert "WRITE_DISABLED" in api.start()[1]
    w.cfg.write_enabled = True; w.cfg.scan.scan_budget = 65537
    assert "INVALID_SCAN_SETTINGS" in api.start()[1]
    w.cfg.scan.scan_budget = 128
    assert all(value == 0 for _, value in guard.snapshot().attempted_calls.items())
    assert api.evidence().reason == "NO_RUN"
    guard.restore()
    w.object(0x100128)
    script = ET.parse(table_path).find(".//AssemblerScript").text
    enable, disable = script.split("[DISABLE]")
    start_code = enable.split("{$lua}")[1].split("{$asm}")[0]
    stop_code = disable.split("{$lua}")[1].split("{$asm}")[0]
    lua.globals().syntaxcheck = True; lua.execute(start_code)
    assert w.open_calls == w.active_timers == 0
    lua.globals().syntaxcheck = False; lua.execute(start_code)
    assert api.start() == (False, "ALREADY_RUNNING")
    w.step(80)
    assert api.status().state == "MONITORING" and len(w.writes) == 1
    assert api.status().write_admission_basis == "LEGACY_SCOPE_ACCEPT"
    assert any(line == "[H3-A7] write_admission_basis=LEGACY_SCOPE_ACCEPT" for line in w.lines.values())
    assert api.evidence().scan_scope.write_admission_basis == "LEGACY_SCOPE_ACCEPT"
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


def reset_worker_counters(lua, w, total=8945664):
    w.progress_snapshot = lua.table_from({
        "TotalAddressesToScan": total, "CurrentlyScanned": 0, "ResultsFound": 0})


def qualification_mode(lua):
    # Adapter-mode isolation only; real QSG broker/writer tests remain separate.
    # No invented native terminal-success/error capability is supplied.
    lua.execute("""
      w.execution={mode='QUALIFICATION',version='qsg.v1',
        assert_ready=function() end,check_local=function() end,
        bind_candidate=function() end,readback=function() end,revoke=function() end,
        wrap_tick=function(fn) return fn end,
        build_writer=function(raw) return {write_float32=raw} end}
    """)


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
    ("ambiguous", 2, "CANDIDATE_NOT_QUALIFIED"), ("over_limit", 129, "CANDIDATE_NOT_QUALIFIED"),
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
    assert population.raw_match_count == count and population.native_count_limited is False
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
        population = events(w, "candidate_population")[0]
        assert population.raw_count == 129 and population.collection_complete is False
        assert population.scanned_count == 128 and population.ranked_count == 128
        assert events(w, "scan_progress")
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


@pytest.mark.parametrize("qualification", [False, True])
def test_incomplete_scan_progress_is_separate_from_incomplete_structure(runtime, qualification):
    lua, w = runtime
    enable_diagnostics(lua)
    if qualification: qualification_mode(lua)
    w.object(0x100128); w.fail.progress = True
    w.start(); w.until_state("ERROR" if qualification else "MONITORING")
    progress = events(w, "scan_progress")[0]
    assert progress.scanned_addresses < progress.total_addresses
    assert not w.loop.status().scan_complete and not w.loop.status().global_uniqueness_proven
    if qualification:
        assert "SCAN_COMPLETION_UNCERTAIN" in w.loop.status().last_error
        assert events(w, "scan_population_complete") == []
        assert w.loop.evidence().counters.adapter_write_attempts == 0
    else:
        assert w.loop.status().result_ready and w.loop.status().collection_complete
        assert w.loop.evidence().counters.verified_writes == 1
    w.loop.stop(); w.clean()


@pytest.mark.parametrize("scenario,count,total", [
    ("reported_pattern", 4, 8945664),
    ("baseline_unique", 1, layout.PAGE_SIZE),
    ("zero_match", 0, layout.PAGE_SIZE),
])
@pytest.mark.parametrize("mode", ["bounded", "process"])
@pytest.mark.parametrize("qualification", [False, True])
def test_p4_released_worker_counters_remain_unproven_without_success_status(runtime, scenario, count, total, mode, qualification):
    """Reproduce the observation, not a new native test or a success oracle.

    Callback + readable results + reset counters cannot distinguish normal
    teardown from cancellation/partial results or a late controller failure.
    NORMAL may use the result under Option A; QUALIFICATION still rejects it.
    No mock-only terminal status is added and no native completeness is claimed.
    """
    lua, w = runtime
    enable_diagnostics(lua)
    if qualification: qualification_mode(lua)
    w.cfg.max_rescan_attempts = 0
    if scenario == "reported_pattern":
        # Four arbitrary synthetic matches, not the operator's fixture candidates.
        for i in range(4):
            w.object(0x100128 + i * 0x1000)
    else:
        plan = layout.plan(scenario)
        w.use_layout(lua.table_from(plan["pages"]), lua.table_from(plan["words"]))
        assert w.cfg.scan.stop_address - w.cfg.scan.start_address + 1 == layout.RESERVATION_SIZE
    if mode == "process": process_scope(w)
    reset_worker_counters(lua, w, total)
    accepted = not qualification and scenario == "baseline_unique"
    w.start(); w.until_state("MONITORING" if accepted else "ERROR")
    s = w.loop.status()
    assert len(events(w, "scan_done_observed")) == 1
    assert events(w, "scan_population")[0].raw_match_count == count
    progress = events(w, "scan_progress")[0]
    assert (progress.total_addresses, progress.scanned_addresses, progress.progress_results) == (total, 0, 0)
    assert not s.scan_complete and not s.scope_complete and not s.global_uniqueness_proven
    if qualification:
        assert s.last_error == "SCAN_COMPLETION_UNCERTAIN"
        assert events(w, "scan_population_complete") == []
        assert not s.result_ready and not s.collection_complete
        assert w.reads == len(w.writes) == w.loop.evidence().counters.adapter_readback_calls == 0
    else:
        ready = events(w, "scan_population_complete")[0]
        assert ready.result_ready and not ready.scan_complete
        assert "native terminal success unverified" in ready.completeness_reason
        assert s.result_ready and s.collection_complete
        assert events(w, "candidate_population")[0].raw_count == count
        assert len(w.writes) == w.loop.evidence().counters.verified_writes == int(accepted)
        if accepted:
            assert s.ranking_recommendation == "ACCEPT" and s.write_admission_basis == "LEGACY_SCOPE_ACCEPT"
            assert w.writes[1].addr == s.ranking_best_address
            assert s.last_written_bits == s.last_readback_bits == 0x42FA0000
            w.step(40)
            assert w.loop.status().monitor_checks == 20 and len(w.scans) == len(w.writes) == 1
        else:
            expected = "RESCAN_LIMIT_EXHAUSTED" if count == 0 else "CANDIDATE_NOT_QUALIFIED"
            assert expected in s.last_error and s.write_admission_basis == "NONE"
    w.loop.stop()
    assert w.loop.evidence().cleanup_ok
    assert w.scans[1].hasError is None and w.scans[1].GetErrorString is None
    w.clean()


@pytest.mark.parametrize("snapshot", [
    False, {}, {"TotalAddressesToScan": 0, "CurrentlyScanned": 0, "ResultsFound": 0},
    {"TotalAddressesToScan": -1, "CurrentlyScanned": -1, "ResultsFound": 0},
    {"TotalAddressesToScan": 1.5, "CurrentlyScanned": 1.5, "ResultsFound": 0},
    {"TotalAddressesToScan": 4096, "ResultsFound": 0},
    {"TotalAddressesToScan": 4096, "CurrentlyScanned": 4096},
])
@pytest.mark.parametrize("qualification", [False, True])
def test_p4_default_or_unavailable_progress_cannot_prove_empty_scan(runtime, snapshot, qualification):
    lua, w = runtime
    enable_diagnostics(lua)
    if qualification: qualification_mode(lua)
    w.cfg.max_rescan_attempts = 0
    w.progress_snapshot = lua.table_from(snapshot) if isinstance(snapshot, dict) else snapshot
    w.start(); w.until_state("ERROR")
    assert w.loop.status().last_error == ("SCAN_COMPLETION_UNCERTAIN" if qualification else "RESCAN_LIMIT_EXHAUSTED")
    assert len(events(w, "scan_done_observed")) == 1
    assert events(w, "scan_population")[0].raw_match_count == 0
    assert not w.loop.status().scan_complete and not w.loop.status().global_uniqueness_proven
    assert w.loop.status().result_ready is (not qualification)
    assert len(events(w, "scan_population_complete")) == int(not qualification)
    assert w.reads == len(w.writes) == 0
    assert w.loop.evidence().cleanup_ok
    w.clean()


@pytest.mark.parametrize("fault,reason", [
    ("w.fail.first_scan='throw'", "INJECTED_first_scan"),
    ("w.fail.initialize='throw'", "INJECTED_initialize"),
    ("w.fail.getProgress='throw'", "INJECTED_getProgress"),
    ("w.hook=function(e) if e=='initialize' then w.latest_foundlist.Count=-1 end end", "INVALID_FOUNDLIST_COUNT"),
    ("w.hook=function(e) if e=='getProgress' then w.hook=nil; w.loop.stop() end end", "OPERATOR_STOP"),
])
@pytest.mark.parametrize("native_fallback", [False, True])
def test_p4_r1_observed_api_failure_or_stop_is_terminal_even_with_ready_callback(runtime, fault, reason, native_fallback):
    lua, w = runtime
    if native_fallback:
        process_scope(w); w.fail.scan_policy = True
    w.object(0x100128); reset_worker_counters(lua, w)
    lua.execute(fault)
    w.start(); w.until_state("STOPPED" if reason == "OPERATOR_STOP" else "ERROR")
    assert reason in w.loop.status().stop_reason
    w.step(100)
    assert len(w.scans) == 1 and len(w.writes) == 0 and w.loop.status().cleanup_ok
    w.clean()


@pytest.mark.parametrize("mode", ["baseline_unique", "zero_match"])
def test_p4_retained_counters_preserve_existing_synthetic_fixture_flow(runtime, mode):
    lua, w = runtime
    enable_diagnostics(lua)
    plan = layout.plan(mode)
    w.use_layout(lua.table_from(plan["pages"]), lua.table_from(plan["words"]))
    w.cfg.max_rescan_attempts = 0
    count = 1 if mode == "baseline_unique" else 0
    # Existing strict evidence rule only; this is not CE 7.6 teardown evidence.
    w.progress_snapshot = lua.table_from({"TotalAddressesToScan": layout.PAGE_SIZE,
        "CurrentlyScanned": layout.PAGE_SIZE, "ResultsFound": count})
    w.start(); w.until_state("MONITORING" if count else "ERROR")
    assert w.loop.status().scan_complete and w.loop.status().collection_complete
    assert events(w, "scan_population")[0].raw_match_count == count
    assert len(w.writes) == count
    if count:
        assert w.loop.status().last_readback_bits == 0x42FA0000
        w.step(40)
        assert w.loop.status().monitor_checks >= 20 and len(w.scans) == 1
    else:
        assert w.loop.status().last_error == "RESCAN_LIMIT_EXHAUSTED"
        assert w.reads == 0
    w.loop.stop(); w.clean()


@pytest.mark.parametrize("callback", ["absent", "wrong_sender", "premature"])
def test_p4_zero_progress_does_not_replace_current_terminal_callback(runtime, callback):
    lua, w = runtime
    enable_diagnostics(lua)
    w.object(0x100128)
    w.fail.no_complete = True
    w.cfg.scan_timeout_ms = 1000
    w.progress_snapshot = lua.table_from({"TotalAddressesToScan": 0,
        "CurrentlyScanned": 0, "ResultsFound": 0})
    w.start(); w.step(2)
    if callback == "wrong_sender":
        w.scans[1].saved_callback(lua.table())
    elif callback == "premature":
        # The mock refuses FoundList initialization before its scanner is done.
        w.scans[1].saved_callback(w.scans[1])
    w.until_state("ERROR")
    expected = "FoundList read before completion" if callback == "premature" else "SCAN_TIMEOUT"
    assert expected in w.loop.status().last_error
    assert not w.loop.status().scan_complete and len(w.foundlist_history) == 0
    assert w.reads == len(w.writes) == 0
    assert w.loop.evidence().cleanup_ok
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


def portable_source(tmp_path, name="relocated checkout [test] & 'quoted'"):
    source_dir = tmp_path / name / "src"
    source_dir.mkdir(parents=True)
    for name in (*REQUIRED_FILES, "ce_mvp_config.example.lua", "ce_mvp.CT", "prepare_ce_mvp.py"):
        (source_dir / name).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(SRC / name, source_dir / name)
    return source_dir


def table_lua(path):
    return [code.split("{$asm}")[0]
            for script in ET.parse(path).findall(".//AssemblerScript")
            for code in script.text.split("{$lua}")[1:]]


@pytest.mark.parametrize("name", ["ASCII with spaces [x] & 'quote'", "\u79fb\u52a8\u76ee\u5f55 [x] & 'quote'"])
def test_portable_preparation_cli_is_deterministic_private_and_cwd_independent(tmp_path, name):
    source_dir = portable_source(tmp_path, name)
    before = {p.relative_to(source_dir): p.read_bytes() for p in source_dir.rglob("*") if p.is_file()}
    result = subprocess.run([sys.executable, str(source_dir / "prepare_ce_mvp.py")],
                            cwd=tmp_path, capture_output=True)
    assert result.returncode == 0, result.stderr
    output = source_dir / "ce_mvp.local.CT"
    first = output.read_bytes()
    assert b"\r" not in first and first.decode("ascii")
    assert not (source_dir / "ce_mvp_config.local.lua").exists()
    # A pre-existing private file must not even be parsed or replaced.
    private = source_dir / "ce_mvp_config.local.lua"
    private.write_bytes(b"this is deliberately not valid Lua\n")
    assert prepare(source_dir).read_bytes() == first
    assert private.read_bytes() == b"this is deliberately not valid Lua\n"
    assert all((source_dir / name).read_bytes() == data for name, data in before.items())
    assert {p.relative_to(source_dir) for p in source_dir.rglob("*") if p.is_file()} == (
        set(before) | {Path(output.name), Path(private.name)})


def test_portable_records_are_inert_and_template_requires_preparation(runtime, tmp_path):
    lua, w = runtime
    output = prepare(portable_source(tmp_path))
    lua.execute("for k,v in pairs(w.ce) do _G[k]=v end; dofile=function() error('UNEXPECTED_LOAD') end")
    for path in (SRC / "ce_mvp.CT", output):
        table = ET.parse(path)
        assert table.find("LuaScript") is None and table.findall(".//Active") == []
        records = table.findall(".//CheatEntry")
        assert [r.findtext("ID") for r in records] == ["1", "2", "3"]
        assert "Start (uncheck to Stop" in records[0].findtext("Description")
        assert "Status" in records[1].findtext("Description")
        assert "READ ONLY" in records[2].findtext("Description")
        lua.globals().syntaxcheck = True
        for code in table_lua(path):
            lua.compile(code)
            lua.execute(code)
        lua.globals().syntaxcheck = False
        # Start-disable (Stop), Status-enable and Status-disable are inert before Start.
        for code in table_lua(path)[1:4] + table_lua(path)[5:]:
            lua.execute(code)
    with pytest.raises(Exception, match="CE_MVP_TABLE_NOT_PREPARED"):
        lua.execute(table_lua(SRC / "ce_mvp.CT")[0])
    assert w.open_calls == w.reads == len(w.writes) == len(w.native_calls) == 0


@pytest.mark.parametrize("path", [
    "C:\\space & quotes\\a'\"b\\ce_mvp.lua",
    "C:/\u79fb\u52a8/]]; error('INJECTED') --/ce_mvp.lua",
    "C:/]]></AssemblerScript><LuaScript>injected</LuaScript>/[DISABLE]/{$asm}/ce_mvp.lua",
])
def test_portable_path_encoding_round_trips_in_real_lua_and_xml(runtime, path):
    lua, _ = runtime
    literal = lua_path(path)
    assert lua.eval(literal) == path
    xml = ET.fromstring("<AssemblerScript><![CDATA[return " + literal + "]]></AssemblerScript>")
    assert lua.execute(xml.text) == path


@pytest.mark.parametrize("path", ["", "C:/nul\0/ce_mvp.lua", "C:/line\n/ce_mvp.lua"])
def test_portable_invalid_paths_reject(path):
    with pytest.raises(ValueError, match="INVALID_ENTRYPOINT_PATH"):
        lua_path(path)


@pytest.mark.parametrize("missing", REQUIRED_FILES)
def test_portable_missing_module_fails_without_output_or_config(tmp_path, missing):
    source_dir = portable_source(tmp_path)
    (source_dir / missing).unlink()
    with pytest.raises(ValueError, match="MISSING_MODULE"):
        prepare(source_dir)
    assert not (source_dir / "ce_mvp.local.CT").exists()
    assert not (source_dir / "ce_mvp_config.local.lua").exists()


@pytest.mark.parametrize("bad_template", ["<CheatTable/>", "local entrypoint=nil -- H3A7_LOCAL_ENTRYPOINT<"])
def test_portable_bad_template_does_not_overwrite_local_output(tmp_path, bad_template):
    source_dir = portable_source(tmp_path)
    output = prepare(source_dir)
    before = output.read_bytes()
    (source_dir / "ce_mvp.CT").write_text(bad_template, encoding="utf-8")
    with pytest.raises((ValueError, ET.ParseError)):
        prepare(source_dir)
    assert output.read_bytes() == before


def test_portable_real_file_loading_has_no_config_fallback_or_implicit_enable(tmp_path):
    lua = import_module("lupa.lua53").LuaRuntime(unpack_returned_tuples=True)
    source_dir = portable_source(tmp_path)
    start = table_lua(prepare(source_dir))[0]
    lua.execute("openProcess=function() error('UNEXPECTED_ATTACH') end")
    with pytest.raises(Exception, match="ce_mvp_config.local.lua"):
        lua.execute(start)
    assert lua.globals().H3A7_CE_MVP.status().state == "STOPPED"
    sample = (source_dir / "ce_mvp_config.example.lua").read_text(encoding="utf-8")
    cfg = lua.execute(sample)
    assert cfg.target_pid == 0 and cfg.write_enabled is False
    local = source_dir / "ce_mvp_config.local.lua"
    # Explicit test fixture copies only; the preparation helper never creates config.
    local.write_text(sample, encoding="utf-8")
    with pytest.raises(Exception, match="INVALID_TARGET_PID"):
        lua.execute(start)
    local.write_text(sample.replace("target_pid = 0,", "target_pid = 101,"), encoding="utf-8")
    with pytest.raises(Exception, match="WRITE_DISABLED"):
        lua.execute(start)
    (source_dir / "ce_mvp_core.lua").unlink()
    with pytest.raises(Exception, match="ce_mvp_core.lua"):
        lua.execute(start)
    (source_dir / "ce_mvp.lua").unlink()
    with pytest.raises(Exception, match="ce_mvp.lua"):
        lua.execute(start)


def test_portable_unicode_paths_route_to_exact_siblings_under_unicode_file_io(tmp_path):
    # Stock Windows Lupa uses narrow C file I/O, unlike a Unicode-capable host.
    # Use explicit Python UTF-8 file I/O + real Lua compilation for this routing
    # test; native CE Unicode filename handling still requires qualification.
    lua = import_module("lupa.lua53").LuaRuntime(unpack_returned_tuples=True)
    source_dir = portable_source(tmp_path, "\u79fb\u52a8\u76ee\u5f55 with spaces")
    output = prepare(source_dir)
    sample = source_dir / "ce_mvp_config.example.lua"
    shutil.copyfile(sample, source_dir / "ce_mvp_config.local.lua")
    loaded = []

    def read_source(path):
        loaded.append(Path(path))
        assert Path(path).parent == source_dir
        return Path(path).read_text(encoding="utf-8")

    lua.globals().read_source = read_source
    lua.execute("""
      loadfile=function(path, mode, env) return load(read_source(path),'@'..path,mode,env) end
      dofile=function(path) return assert(loadfile(path,'t',_G))() end
      openProcess=function() error('UNEXPECTED_ATTACH') end
    """)
    with pytest.raises(Exception, match="INVALID_TARGET_PID"):
        lua.execute(table_lua(output)[0])
    assert loaded == [source_dir / name for name in
                      ("ce_mvp.lua", "ce_mvp_config.local.lua", "ce_mvp_core.lua")]


def test_portable_table_rejects_singleton_from_another_installation(runtime, tmp_path):
    lua, w = runtime
    lua.execute(SOURCES["ce_mvp.lua"], name="@C:/other installation/src/ce_mvp.lua")
    with pytest.raises(Exception, match="CE_MVP_DIFFERENT_INSTALLATION_RELOAD_CE"):
        lua.execute(table_lua(prepare(portable_source(tmp_path)))[0])
    assert w.open_calls == w.reads == len(w.writes) == len(w.native_calls) == 0


def test_portable_output_and_private_config_are_ignored_without_hiding_template():
    ignored = subprocess.run(["git", "check-ignore", "--no-index", "src/ce_mvp.local.CT",
                              "src/ce_mvp_config.local.lua", "src/ce_mvp.CT",
                              "src/prepare_ce_mvp.py"], cwd=ROOT,
                             text=True, capture_output=True, check=True)
    assert ignored.stdout.splitlines() == ["src/ce_mvp.local.CT", "src/ce_mvp_config.local.lua"]


def process_scope(w):
    w.cfg.scan.start_address = None
    w.cfg.scan.stop_address = None


@pytest.mark.parametrize("explicit", [False, True])
def test_process_scope_uses_verified_os_bounds_after_identity_and_is_readonly(runtime, explicit):
    lua, w = runtime
    process_scope(w)
    if explicit:
        w.cfg.scan.mode = "process"
    enable_diagnostics(lua)
    assert len(w.native_calls) == w.open_calls == w.reads == 0
    good(w)
    s = w.loop.status()
    assert s.scan_mode == "process" and s.scope_resolved and s.scope_complete
    assert s.scan_start_address == w.scans[1].args[6] == 0x10000
    assert s.scan_stop_address == w.scans[1].args[7] == 0x7FFFFFFEFFFF
    assert "GetSystemInfo" in s.bounds_source and s.alignment_bytes == 4
    assert w.scans[1].policy.MEM_PRIVATE is True
    assert w.scans[1].policy.MEM_IMAGE is w.scans[1].policy.MEM_MAPPED is False
    assert "MEM_PRIVATE" in s.scan_policy
    native = [c.name for _, c in w.native_calls.items()]
    assert native.index("GetProcessTimes") < native.index("GetSystemInfo")
    before = (len(w.native_calls), w.reads)
    s.scan_start_address = 999
    w.loop.evidence().scan_scope.scan_stop_address = 999
    assert w.loop.status().scan_start_address == 0x10000
    assert w.loop.evidence().scan_scope.scan_stop_address == 0x7FFFFFFEFFFF
    assert before == (len(w.native_calls), w.reads)
    w.loop.stop(); w.clean()


@pytest.mark.parametrize("mode", [None, "bounded"])
@pytest.mark.parametrize("policy", [None, True, "non_callable", "throw"])
def test_legacy_bounds_keep_their_meaning_without_system_info(runtime, mode, policy):
    _, w = runtime
    w.cfg.scan.mode = mode
    w.fail.scan_policy = policy
    w.fail.symbol = "GetSystemInfo"
    good(w)
    s = w.loop.status()
    assert s.scan_mode == "bounded"
    assert s.scan_policy == "+W-X-C; aligned exact Float32 bits"
    assert w.scans[1].policy is None
    assert (s.scan_start_address, s.scan_stop_address) == (0x100000, 0x11FFFF)
    assert not any(c.name == "GetSystemInfo" for _, c in w.native_calls.items())
    w.loop.stop(); w.clean()


@pytest.mark.parametrize("policy", [True, "non_callable"])
@pytest.mark.parametrize("retained_counters", [False, True])
def test_p4_r2_normal_auto_bounds_use_native_policy_without_global_claim(runtime, policy, retained_counters):
    lua, w = runtime
    process_scope(w)
    w.cfg.scan.scan_budget = w.cfg.scan.max_candidates = None
    w.fail.scan_policy = policy
    enable_diagnostics(lua)
    if not retained_counters: reset_worker_counters(lua, w)
    good(w)
    s = w.loop.status()
    assert s.scan_mode == "process" and s.scope_resolved
    assert "GetSystemInfo" in s.bounds_source
    assert (s.scan_start_address, s.scan_stop_address) == (0x10000, 0x7FFFFFFEFFFF)
    assert (w.scans[1].args[6], w.scans[1].args[7]) == (s.scan_start_address, s.scan_stop_address)
    assert w.scans[1].policy is None
    assert s.scan_policy == "CE native/default memory types (NORMAL bounded-policy fallback); +W-X-C; aligned exact Float32 bits"
    assert "MEM_PRIVATE" not in s.scan_policy and "MEM_PRIVATE" in s.candidate_policy
    assert (s.raw_admission_budget, s.ranking_budget) == (2000, 20)
    assert s.result_ready and s.collection_complete and s.coverage == "full_population"
    # The historical counter rule describes this native view, never all private memory.
    assert s.scan_complete is retained_counters and s.scope_complete is retained_counters
    assert not s.global_uniqueness_proven
    assert s.decision_scope == "LEGACY_SINGLE_SCOPE" and s.write_admission_basis == "LEGACY_SCOPE_ACCEPT"
    assert s.last_written_bits == s.last_readback_bits == 0x42FA0000
    assert len(events(w, "scan_invocation")) == len(events(w, "scan_done_observed")) == 1
    assert events(w, "scan_population_complete")[0].scan_complete is retained_counters
    assert not events(w, "candidate_admitted")[0].global_uniqueness_proven
    assert w.loop.evidence().scan_scope.scan_policy == s.scan_policy
    assert "pending" in events(w, "scan_scope_resolved")[0].scan_policy
    w.step(40)
    assert w.loop.status().monitor_checks >= 20 and len(w.scans) == len(w.writes) == 1
    w.loop.stop(); w.clean()


@pytest.mark.parametrize("policy,qualification", [(True, True), ("non_callable", True),
                                                  ("throw", False), ("throw", True)])
def test_p4_r2_strict_missing_policy_and_real_override_failures_remain_terminal(runtime, policy, qualification):
    lua, w = runtime
    process_scope(w); w.fail.scan_policy = policy
    w.object(0x100128)
    if qualification: qualification_mode(lua)
    w.start(); w.until_state("ERROR")
    s = w.loop.status()
    assert ("INJECTED_scan_policy" if policy == "throw" else "PROCESS_SCAN_POLICY_UNAVAILABLE") in s.last_error
    assert s.scope_resolved and "pending" in s.scan_policy and "MEM_PRIVATE" not in s.scan_policy
    assert not s.result_ready and not s.scan_complete and not s.global_uniqueness_proven
    assert s.decision_scope == ("QSG_FULL_POPULATION" if qualification else "LEGACY_SINGLE_SCOPE")
    assert s.write_admission_basis == "NONE"
    assert len(w.scans) == 1 and w.scans[1].args is None and w.scans[1].policy is None
    assert len(w.foundlist_history) == len(w.writes) == w.reads == 0
    assert s.cleanup_ok
    w.clean()


@pytest.mark.parametrize("fault,reason", [
    ("weak", "CANDIDATE_NOT_QUALIFIED"), ("ambiguous", "CANDIDATE_NOT_QUALIFIED"),
    ("image", "CANDIDATE_MAPPING_INVALID"), ("mapped", "CANDIDATE_MAPPING_INVALID"),
    ("read", "SCREENING_READ_FAILED"), ("changed", "CANDIDATE_CHANGED"),
    ("destroy_foundlist", "FOUNDLIST_CLEANUP_FAILED"), ("destroy_scan", "SCAN_CLEANUP_FAILED"),
])
def test_p4_r2_native_policy_keeps_candidate_and_cleanup_protections(runtime, fault, reason):
    lua, w = runtime
    process_scope(w); w.fail.scan_policy = True
    reset_worker_counters(lua, w)
    candidate = w.object(0x100128, "weak" if fault == "weak" else None)
    if fault == "ambiguous": w.object(0x101128)
    if fault in ("image", "mapped"): candidate.kind = 0x1000000 if fault == "image" else 0x40000
    if fault == "read": w.fail.unreadable = candidate.addr - 0x20
    if fault.startswith("destroy_"): w.fail[fault] = "throw"
    w.start()
    if fault == "changed":
        w.until_state("CANDIDATE_CHECK"); candidate.memory[candidate.addr - 0x20] = 7
    w.until_state("ERROR")
    s = w.loop.status()
    assert reason in s.last_error and not s.global_uniqueness_proven
    w.step(100)
    assert len(w.scans) == 1 and len(w.writes) == 0
    assert s.cleanup_ok is (not fault.startswith("destroy_"))
    w.clean()


@pytest.mark.parametrize("edit,reason", [
    ("w.cfg.scan.start_address=nil", "INCOMPLETE_SCAN_RANGE"),
    ("w.cfg.scan.stop_address=nil", "INCOMPLETE_SCAN_RANGE"),
    ("w.cfg.scan.mode='process'", "CONFLICTING_SCAN_RANGE"),
    ("w.cfg.scan.mode='auto'", "INVALID_SCAN_MODE"),
    ("w.cfg.scan.mode=false", "INVALID_SCAN_MODE"),
    ("w.cfg.scan.mode='bounded';w.cfg.scan.start_address=nil;w.cfg.scan.stop_address=nil", "INCOMPLETE_SCAN_RANGE"),
    ("w.cfg.scan.stop_address=0x7FFFFFFFFFFFFFFF", "INVALID_SCAN_ADDRESS"),
])
def test_scope_configuration_rejects_before_ce_access(runtime, edit, reason):
    lua, w = runtime
    lua.execute(edit)
    with pytest.raises(Exception, match=reason):
        w.start()
    assert len(w.native_calls) == w.open_calls == w.reads == len(w.writes) == 0


@pytest.mark.parametrize("edit,reason", [
    ("w.fail.system_info_no_output=true", "PROCESS_SCOPE_UNAVAILABLE"),
    ("w.fail.local_write=true", "SYSTEM_INFO_BUFFER_FAILED"),
    ("w.system_info_override={[0]=0}", "PROCESS_SCOPE_UNAVAILABLE"),
    ("w.system_info_override={[4]=0}", "PROCESS_SCOPE_UNAVAILABLE"),
    ("w.system_info_override={[8]=0}", "PROCESS_SCOPE_UNAVAILABLE"),
    ("w.system_info_override={[8]=0x7FFFFFFFFFFF0000,[16]=-65537}", "PROCESS_SCOPE_UNAVAILABLE"),
    ("w.system_info_override={[16]=0x7FFFFFFFFFFFFFFF}", "PROCESS_SCOPE_UNAVAILABLE"),
    ("w.system_info_override={[16]=0x10000}", "PROCESS_SCOPE_UNAVAILABLE"),
    ("w.system_info_override={[16]=0x7FFFFFFEFFF0}", "PROCESS_SCOPE_UNAVAILABLE"),
    ("w.system_info_override={[40]=4096}", "PROCESS_SCOPE_UNAVAILABLE"),
    ("w.hook=function(e) if e=='GetSystemInfo' then w.creation=w.creation+1 end end", "PID_IDENTITY_MISMATCH"),
])
def test_uncertain_process_scope_cannot_scan_or_write(runtime, edit, reason):
    lua, w = runtime
    process_scope(w)
    lua.execute(edit)
    w.start(); w.until_state("ERROR")
    assert reason in w.loop.status().last_error
    assert w.loop.status().scope_complete is False
    assert w.reads == len(w.writes) == 0
    assert all(ms.args is None for _, ms in w.scans.items())
    w.clean()


@pytest.mark.parametrize("edit,reason", [
    ("w.fail.symbol='GetSystemInfo'", "WIN32_API_MISSING:GetSystemInfo"),
    ("w.ce.writeIntegerLocal=nil", "CE_API_MISSING:writeIntegerLocal"),
])
def test_process_scope_missing_local_apis_fail_before_attachment(runtime, edit, reason):
    lua, w = runtime
    process_scope(w); lua.execute(edit)
    with pytest.raises(Exception, match=reason):
        w.start()
    assert w.open_calls == w.reads == len(w.writes) == 0


def test_process_scope_stops_mid_scan_without_claiming_completeness(runtime):
    _, w = runtime
    process_scope(w); w.fail.no_complete = True
    w.start(); w.step(2)
    w.loop.stop(); w.step(5)
    assert w.loop.status().scope_complete is False and len(w.writes) == 0
    w.clean()


@pytest.mark.parametrize("addr", [0x100129, 0x10000, 0x7FFFFFFEFFFC])
def test_process_scope_rejects_unaligned_or_edge_context_candidates(runtime, addr):
    _, w = runtime
    process_scope(w); w.object(addr)
    w.start(); w.until_state("ERROR")
    assert len(w.writes) == 0 and w.loop.status().scope_complete is False
    w.clean()


@pytest.mark.parametrize("value,bits", [(-0.0, 0x80000000), (1e-46, 0), (0.1, 0x3DCCCCCD)])
def test_process_scope_validates_exact_search_bits_without_bounds(runtime, value, bits):
    _, w = runtime
    process_scope(w)
    w.cfg.scan.target_value_float = value
    w.cfg.scan.target_value_pattern = bits
    validated = w.core.validate(w.cfg)
    assert validated.scan.mode == "process" and validated.scan.target_bits == bits
    assert w.open_calls == w.reads == 0


def process_population(lua, w, count, good_indices=()):
    process_scope(w)
    w.cfg.max_rescan_attempts = 0
    w.cfg.scan_timeout_ms = 120000
    w.record_native_calls = False  # bound the mock guard trace for large inputs
    lua.execute("""
      w.fast_index={}
      function w.populate(count, good)
        for i=1,count do
          local o=w.object(0x100128+(i-1)*0x100, 'weak')
          if good[i] then
            local fields={0x10011200,0x10013800,0x10042100,0x10060000,0x10025600,0x10028400,0x10086300}
            for j,offset in ipairs({-0x20,-0x10,-8,0x30,0x40,0x48,0x50}) do o.memory[o.addr+offset]=fields[j] end
          end
          o.size=0x2000000
        end
      end
    """)
    w.populate(count, lua.table_from({i: True for i in good_indices}))


def legacy_reference(lua, w):
    """Run the original Single pipeline over the same fake native scan population."""
    return lua.execute("""
      local env={}; for k,v in pairs(_G) do env[k]=v end; env._G=env; env.print=function() end
      env.readInteger=function(addr) return assert(w.locate(addr)).memory[addr] end
      env.readFloat=function(addr) return string.unpack('<f',string.pack('<I4',env.readInteger(addr))) end
      env.getAddress=function(addr) return type(addr)=='number' and addr or tonumber(addr,16) end
      env.getCurrentMemscan=function() return {} end
      env.createFoundList=function()
        local fl={Count=0,Address={}}
        for _,o in ipairs(w.objects) do
          if o.mapped and o.protect==4 and o.memory[o.addr]==0x42C80000 then
            fl.Address[fl.Count]=o.addr; fl.Count=fl.Count+1
          end
        end
        fl.initialize=function() end; fl.destroy=function() end; return fl
      end
      local report=w.load('mvp0_candidate_report.lua',env)
      local collector=w.load('mvp0_foundlist_collector.lua',env)
      local settings=w.core.validate(w.cfg).scan
      return collector.run({scan_budget=settings.scan_budget,max_candidates=settings.max_candidates,
        target_value_pattern=0x42C80000,target_value_float=100.0,filter_target_match=true,
        use_prescore_selection=true,probe_full_foundlist=false,stable_filter_intersection_enabled=false})
    """)


def mutate_scope_result(lua, mutation):
    """Fault injection at the collector return boundary; legacy sources stay intact."""
    lua.execute("""
      local load_original=w.load
      w.load=function(name,env)
        local module=load_original(name,env)
        if name=='mvp0_foundlist_collector.lua' then
          local run_original=module.run
          module.run=function(...)
            local bundle=run_original(...)
            local r=bundle.result
    """ + mutation + """
            return bundle
          end
        end
        return module
      end
    """)


@pytest.mark.parametrize("mutation,reason", [
    ("r.recommendation.recommendation='REJECT'", "CANDIDATE_NOT_QUALIFIED"),
    ("r.recommendation.recommendation='REVIEW'", "CANDIDATE_NOT_QUALIFIED"),
    ("r.recommendation.manual_review_required=true", "CANDIDATE_NOT_QUALIFIED"),
    ("r.recommendation.manual_review_required=nil", "INVALID_RANK_RESULT"),
    ("r.best.hard_pass=false", "CANDIDATE_NOT_QUALIFIED"),
    ("r.best.hard_pass=1", "INVALID_RANK_RESULT"),
    ("bundle.result=nil", "INVALID_RANK_RESULT"),
    ("r.best=nil", "INVALID_RANK_RESULT"),
    ("r.best.candidate=nil", "INVALID_RANK_RESULT"),
    ("r.best.final_score=0/0", "INVALID_RANK_RESULT"),
    ("r.best=r.second", "INVALID_RANK_RESULT"),
    ("r.recommendation.recommended_candidate=r.second", "INVALID_RANK_RESULT"),
    ("r.final_decision={recommendation='REJECT'}", "INVALID_RANK_RESULT"),
    ("r.best.candidate.value_addr=0x100129", "FOUND_ADDRESS_OUT_OF_RANGE"),
    ("r.best.candidate.value_addr=0x200128", "CANDIDATE_NOT_SELECTED"),
    ("r.best.candidate.f58=nil", "CANDIDATE_UNREADABLE"),
    ("r.best.candidate.f58=7", "CANDIDATE_CHANGED"),
    ("r.best.candidate.f28=nil", "CANDIDATE_NOT_QUALIFIED"),
    ("r.best.candidate.f28_float=99", "CANDIDATE_NOT_QUALIFIED"),
    ("bundle.scanned_count=0", "INVALID_SCOPE_COUNTS"),
    ("bundle.raw_count=bundle.raw_count+1", "FOUNDLIST_COUNT_CHANGED"),
])
def test_rev1_malformed_or_nonaccept_scope_never_writes(runtime, mutation, reason):
    lua, w = runtime
    reset_worker_counters(lua, w)
    process_population(lua, w, 129, (129,))
    w.cfg.scan.scan_budget = 128; w.cfg.scan.max_candidates = 20
    enable_diagnostics(lua)
    mutate_scope_result(lua, mutation)
    w.start(); w.until_state("ERROR")
    assert reason in w.loop.status().last_error
    assert len(w.writes) == w.loop.evidence().counters.adapter_write_attempts == 0
    assert not w.loop.status().global_uniqueness_proven
    w.clean()


@pytest.mark.parametrize("count", [2, 30000])
@pytest.mark.parametrize("qualification", [False, True])
def test_rev1_original_accept_is_authoritative_only_in_normal_mode(runtime, count, qualification):
    lua, w = runtime
    process_population(lua, w, count, (1, count))
    w.cfg.scan.scan_budget = 2000; w.cfg.scan.max_candidates = 20
    # The unchanged ranker scores these independent ACCEPTs 36 and 46, gap 10.
    # Its combined recommendation is ACCEPT for the late, stronger object.
    for offset in (-8, 0x30, 0x40, 0x48):
        w.objects[1].memory[w.objects[1].addr + offset] = 1
    reference = legacy_reference(lua, w)
    assert reference.result.recommendation.recommendation == "ACCEPT"
    assert reference.result.best.candidate.value_addr == w.objects[count].addr
    assert reference.result.best.final_score == 46 and reference.result.score_gap == 10
    enable_diagnostics(lua)
    if qualification:
        qualification_mode(lua)
    w.start(); w.until_state("ERROR" if qualification else "MONITORING")
    s = w.loop.status()
    assert s.qualified_count == 2 and s.ranking_recommendation == "ACCEPT"
    assert not s.global_uniqueness_proven
    if qualification:
        reason = "AMBIGUOUS_CANDIDATES" if count == 2 else "INCOMPLETE_CANDIDATE_POPULATION"
        assert reason in s.last_error and len(w.writes) == 0
        assert s.decision_scope == "QSG_FULL_POPULATION" and s.write_admission_basis == "NONE"
    else:
        assert s.write_admission_basis == "LEGACY_SCOPE_ACCEPT" and len(w.writes) == 1
        assert w.writes[1].addr == reference.result.best.candidate.value_addr
        assert s.last_written_bits == s.last_readback_bits == 0x42FA0000
    w.loop.stop(); w.clean()


@pytest.mark.parametrize("fault,reason", [
    ("w.latest_foundlist.Count=19999", "FOUNDLIST_COUNT_CHANGED"),
    ("w.latest_foundlist.Address[19999]=nil", "FOUND_ADDRESS_OUT_OF_RANGE"),
    ("w.latest_foundlist.Address[19999]=w.latest_foundlist.Address[0]", "DUPLICATE_FOUND_ADDRESS"),
    ("w.creation=w.creation+1", "PID_IDENTITY_MISMATCH"),
    ("w.opened=999", "CE_TARGET_CHANGED"),
    ("w.ce_handle=999", "CE_TARGET_CHANGED"),
    ("w.objects[20000].protect=0x20", "CANDIDATE_MAPPING_INVALID"),
    ("w.fail.unreadable=w.objects[20000].addr-0x20", "SCREENING_READ_FAILED"),
])
def test_rev1_large_pool_integrity_failures_still_block_write(runtime, fault, reason):
    lua, w = runtime
    reset_worker_counters(lua, w)
    process_population(lua, w, 20000, (20000,))
    w.cfg.scan.scan_budget = 2000; w.cfg.scan.max_candidates = 20
    w.start()
    while (w.loop.status().raw_inspected_count or 0) < 8:
        w.step(); assert w.loop.status().running
    lua.execute(fault)
    w.until_state("ERROR")
    assert reason in w.loop.status().last_error and len(w.writes) == 0
    assert not w.loop.status().global_uniqueness_proven
    w.clean()


@pytest.mark.parametrize("count", [20000, 30000])
@pytest.mark.parametrize("recommendation", ["REJECT", "REVIEW"])
def test_rev1_large_pool_original_reject_and_review_remain_authoritative(runtime, count, recommendation):
    lua, w = runtime
    reset_worker_counters(lua, w)
    process_population(lua, w, count, (1, count) if recommendation == "REVIEW" else ())
    w.cfg.scan.scan_budget = 2000; w.cfg.scan.max_candidates = 20
    reference = legacy_reference(lua, w)
    assert reference.result.recommendation.recommendation == recommendation
    assert reference.result.recommendation.manual_review_required is True
    w.start(); w.until_state("ERROR")
    s = w.loop.status()
    assert "CANDIDATE_NOT_QUALIFIED" in s.last_error and len(w.writes) == 0
    assert s.ranking_recommendation == recommendation
    assert s.ranking_best_address == reference.result.best.candidate.value_addr
    assert s.ranking_best_score == reference.result.best.final_score
    assert s.raw_match_count == count and s.raw_admitted_count == 2000 and s.ranked_count == 20
    assert s.write_admission_basis == "NONE" and not s.global_uniqueness_proven
    w.clean()


@pytest.mark.parametrize("mode", ["bounded", "process"])
@pytest.mark.parametrize("released_counters", [False, True])
def test_rev1_large_scoped_accept_monitor_and_fresh_recovery(runtime, mode, released_counters):
    lua, w = runtime
    count = 30000 if released_counters else 20000
    if released_counters: reset_worker_counters(lua, w)
    process_population(lua, w, count, (count,))
    w.cfg.scan.scan_budget = None; w.cfg.scan.max_candidates = None
    w.cfg.max_rescan_attempts = 1
    if mode == "bounded":
        w.cfg.scan.mode = mode
        w.cfg.scan.start_address = 0x100000; w.cfg.scan.stop_address = 0x20FFFFF
    enable_diagnostics(lua, limit=2048)
    w.start(); w.until_state("MONITORING")
    old = w.objects[count]
    old.memory[old.addr] = 0x42280000
    before = w.loop.status().monitor_checks
    w.step(200)
    assert w.loop.status().monitor_checks == before + 100
    assert len(w.scans) == len(w.writes) == 1
    old.mapped = False
    fresh = w.object(0x100128 + count * 0x100); fresh.size = 0x2000000
    w.fail.no_complete = True
    w.until_state("RESCAN_BACKOFF"); w.until_state("SCREENING"); w.step()
    pending = w.loop.status()
    assert pending.cycle_id == 2 and pending.write_admission_basis == "NONE"
    assert pending.raw_match_count is None and not pending.global_uniqueness_proven
    assert not pending.result_ready and not pending.scan_complete
    assert w.scans[1].dead and w.foundlist_history[1].dead
    w.scans[1].saved_callback(w.scans[1]); w.scans[1].saved_callback(w.scans[2])
    w.step(3)
    assert w.loop.status().raw_match_count is None and len(w.writes) == 1
    reference = legacy_reference(lua, w)
    w.fail.no_complete = False
    w.until_state("MONITORING")
    s = w.loop.status()
    assert len(w.scans) == len(w.foundlist_history) == len(w.writes) == 2
    assert w.writes[2].addr == fresh.addr == reference.result.best.candidate.value_addr
    assert s.raw_match_count == count and s.raw_admitted_count == 2000 and s.ranked_count == 20
    assert s.result_ready and s.scan_complete is (not released_counters)
    assert s.last_written_bits == s.last_readback_bits == 0x42FA0000
    assert s.write_admission_basis == "LEGACY_SCOPE_ACCEPT" and not s.global_uniqueness_proven
    evidence = w.loop.evidence()
    assert evidence.scan_scope.write_admission_basis == s.write_admission_basis
    assert evidence.scan_scope.coverage == "sampled_or_reduced"
    assert evidence.counters.verified_writes == 2 and evidence.dropped_events == 0
    assert [e.cycle_id for e in events(w, "candidate_admitted")] == [1, 2]
    if released_counters:
        assert all((e.total_addresses, e.scanned_addresses, e.progress_results) == (8945664, 0, 0)
                   for e in events(w, "scan_progress"))
        w.alive = False; w.until_state("ERROR")
        assert "PID_EXITED" in w.loop.status().last_error and len(w.writes) == 2
    w.loop.stop(); w.clean()


@pytest.mark.parametrize("count", [0, 1, 128, 129, 1001])
def test_complete_pool_visits_every_index_and_accepts_a_late_unique_candidate(runtime, count):
    lua, w = runtime
    process_population(lua, w, count, (count,) if count else ())
    w.cfg.scan.scan_budget = max(128, count)
    lua.execute("w.hook=function(e) if e=='write' then w.at_write=w.loop.status() end end")
    complete = count <= 128
    w.start(); w.until_state("MONITORING" if count else "ERROR")
    s = w.loop.status()
    assert s.raw_match_count == s.raw_inspected_count == s.raw_admitted_count == count
    assert s.ranked_count == min(count, 128) and s.scan_complete
    assert s.collection_complete is complete and s.scope_complete is complete
    assert s.qualified_count == (1 if count else 0)
    if count:
        assert len(w.writes) == 1 and w.writes[1].addr == 0x100128 + (count - 1) * 0x100
        assert w.at_write.collected_count == count
        assert w.at_write.evaluated_count == min(count, 128)
        assert s.last_written_bits == s.last_readback_bits == 0x42FA0000
        assert s.ranking_best_address == w.objects[count].addr
        assert s.global_uniqueness_proven is complete
        assert s.write_admission_basis == "LEGACY_SCOPE_ACCEPT"
    else:
        assert s.last_error == "RESCAN_LIMIT_EXHAUSTED" and len(w.writes) == 0
    w.loop.stop(); w.clean()


@pytest.mark.parametrize("count,good_indices,reason", [
    (129, (1, 129), "CANDIDATE_NOT_QUALIFIED"),
    (1001, (9, 1001), "CANDIDATE_NOT_QUALIFIED"),
    (128, (), "CANDIDATE_NOT_QUALIFIED"),
])
def test_complete_pool_counts_independent_qualifiers_across_chunks(runtime, count, good_indices, reason):
    lua, w = runtime
    process_population(lua, w, count, good_indices)
    w.cfg.scan.scan_budget = count
    w.start(); w.until_state("ERROR")
    s = w.loop.status()
    assert reason in s.last_error and len(w.writes) == 0
    assert s.raw_match_count == s.raw_admitted_count == count
    assert s.ranked_count == min(count, 128)
    assert s.scope_complete is (count <= 128) and s.qualified_count == len(good_indices)
    assert not s.global_uniqueness_proven
    w.clean()


@pytest.mark.parametrize("fault,reason", [
    ("w.loop.stop()", "OPERATOR_STOP"),
    ("w.creation=w.creation+1", "PID_IDENTITY_MISMATCH"),
    ("w.time=w.time+w.cfg.scan_timeout_ms", "SCAN_TIMEOUT"),
    ("w.latest_foundlist.Count=127", "FOUNDLIST_COUNT_CHANGED"),
    ("w.latest_foundlist.Address[100]=nil", "FOUND_ADDRESS_OUT_OF_RANGE"),
    ("w.latest_foundlist.Address[100]=w.latest_foundlist.Address[0]", "DUPLICATE_FOUND_ADDRESS"),
    ("w.fail.unreadable=w.objects[128].addr-0x20", "SCREENING_READ_FAILED"),
    ("w.objects[128].protect=0x20", "CANDIDATE_MAPPING_INVALID"),
    ("w.objects[128].size=0x7FFFFFFFFFFFFFFF", "CANDIDATE_MAPPING_INVALID"),
    ("w.objects[128].memory[w.objects[128].addr]=0x42280000", "CANDIDATE_NOT_QUALIFIED"),
])
def test_incomplete_process_population_never_writes(runtime, fault, reason):
    lua, w = runtime
    reset_worker_counters(lua, w)
    process_population(lua, w, 128, (128,))
    w.cfg.scan.collection_batch_size = 16
    w.start()
    while (w.loop.status().raw_inspected_count or 0) < 8:
        w.step()
        assert w.loop.status().running
    assert w.loop.status().raw_inspected_count < 128
    lua.execute(fault)
    if reason != "OPERATOR_STOP": w.until_state("ERROR")
    s = w.loop.status()
    assert reason in s.stop_reason and len(w.writes) == 0 and not s.global_uniqueness_proven
    assert not s.running
    w.clean()


@pytest.mark.parametrize("edit,reason", [
    ("w.fail.progress=true", "SCAN_COMPLETION_UNCERTAIN"),
    ("w.fail.results_count=999", "SCAN_COMPLETION_UNCERTAIN"),
    ("w.fail.no_complete=true;w.cfg.scan_timeout_ms=1000", "SCAN_TIMEOUT"),
    ("w.hook=function(e) if e=='initialize' then w.latest_foundlist.Count=127 end end", "SCAN_COMPLETION_UNCERTAIN"),
    ("w.hook=function(e) if e=='getTickCount' and w.loop.status().state=='CANDIDATE_CHECK' then w.objects[128].memory[w.objects[128].addr-0x20]=7 end end", "CANDIDATE_CHANGED"),
    ("w.fail.destroy_foundlist='throw'", "FOUNDLIST_CLEANUP_FAILED"),
    ("w.fail.destroy_scan='throw'", "SCAN_CLEANUP_FAILED"),
])
def test_process_scan_completion_drift_and_cleanup_faults_are_terminal(runtime, edit, reason):
    lua, w = runtime
    if reason == "SCAN_COMPLETION_UNCERTAIN": qualification_mode(lua)
    else: reset_worker_counters(lua, w)
    process_population(lua, w, 128, (128,)); lua.execute(edit)
    w.start(); w.until_state("ERROR")
    assert reason in w.loop.status().last_error and len(w.writes) == 0
    assert not w.loop.status().running
    w.clean()


@pytest.mark.parametrize("change,reason", [
    ("w.objects[128].memory[w.objects[128].addr+0x30]=7", "CANDIDATE_CHANGED"),
    ("w.latest_foundlist.Address[0]=w.latest_foundlist.Address[1]", "FOUNDLIST_ADDRESS_CHANGED"),
])
def test_complete_snapshots_are_revalidated_before_global_ranking(runtime, change, reason):
    lua, w = runtime
    reset_worker_counters(lua, w)
    process_population(lua, w, 128, (128,))
    w.cfg.scan.collection_batch_size = 16
    w.start()
    if reason == "CANDIDATE_CHANGED":
        w.until_state("CANDIDATE_CHECK")
    else:
        while (w.loop.status().raw_inspected_count or 0) < 8:
            w.step(); assert w.loop.status().running
    lua.execute(change); w.until_state("ERROR")
    assert reason in w.loop.status().last_error and len(w.writes) == 0
    assert not w.loop.status().running
    w.clean()


@pytest.mark.parametrize("count,limit", [(129, 128), (1001, 1000), (8193, 8192)])
def test_process_admission_budget_reports_actual_count_and_allows_scope_accept(runtime, count, limit):
    lua, w = runtime
    process_population(lua, w, count, (count,))
    w.cfg.scan.scan_budget = limit
    w.start(); w.until_state("MONITORING")
    s = w.loop.status()
    assert s.ranking_recommendation == "ACCEPT" and s.write_admission_basis == "LEGACY_SCOPE_ACCEPT"
    assert s.raw_match_count == count and s.raw_admitted_count == limit
    assert s.ranked_count <= 128 and s.coverage == "sampled_or_reduced"
    assert not s.scope_complete and not s.global_uniqueness_proven and len(w.writes) == 1
    assert w.writes[1].addr == w.objects[count].addr
    w.loop.stop(); w.clean()


@pytest.mark.parametrize("key,value", [("process_candidate_limit", 8193), ("process_candidate_limit", 0),
    ("process_chunk_candidates", 0), ("process_chunk_candidates", 33), ("process_slice_ms", 26)])
def test_process_resource_settings_reject_before_attachment(runtime, key, value):
    _, w = runtime
    process_scope(w); w.cfg.scan[key] = value
    with pytest.raises(Exception, match="OBSOLETE_PROCESS_BUDGET_USE_LEGACY_INTAKE_SETTINGS"):
        w.start()
    assert w.open_calls == w.reads == len(w.writes) == 0


def test_process_resource_settings_cannot_change_legacy_budget_meaning(runtime):
    _, w = runtime
    w.cfg.scan.process_candidate_limit = 8192
    with pytest.raises(Exception, match="OBSOLETE_PROCESS_BUDGET_USE_LEGACY_INTAKE_SETTINGS"):
        w.start()
    assert w.open_calls == 0


def test_process_time_slice_yields_inside_candidate_reads(runtime):
    lua, w = runtime
    process_population(lua, w, 2, (2,))
    lua.execute("w.hook=function(e) if e=='getTickCount' then w.time=w.time+3 end end")
    w.start(); w.step(3)
    assert w.loop.status().collected_count == 0 and len(w.writes) == 0
    w.until_state("MONITORING")
    assert len(w.writes) == 1
    w.loop.stop(); w.clean()


@pytest.mark.parametrize("count,kind", [(129, "weak"), (129, "clones"), (129, "mixed"),
                                       (1001, "mixed"), (1001, "late_unique"), (30001, "mixed")])
@pytest.mark.parametrize("budgets", [(128, 128), (2000, 20)])
def test_complete_stream_matches_full_legacy_collector_and_global_ranker(runtime, count, kind, budgets):
    lua, w = runtime
    process_population(lua, w, count, (count,) if kind == "late_unique" else ())
    w.cfg.scan.scan_budget, w.cfg.scan.max_candidates = budgets
    lua.globals().population_kind = kind
    lua.execute("""
      local patterns={
        {0,0,0,0,0,0,0}, {1,2,3,4,5,6,7},
        {0x3F800000,0x3F800000,0,0,0x43300000,0,0},
        {0x10040000,0x10040000,0x10040000,1,0x10040000,0x10040000,0x10040000},
        {0x41424344,0x45464748,0x494A4B4C,0,0x51525354,0x55565758,0x595A3031},
        {0x10011200,0x10013800,0x10042100,0x10060000,0x10025600,0x10028400,0x10086300}}
      for i,o in ipairs(w.objects) do
        local fields=population_kind=='clones' and patterns[6]
          or (population_kind=='mixed' and patterns[(i%#patterns)+1])
        if fields then
          for j,offset in ipairs({-0x20,-0x10,-8,0x30,0x40,0x48,0x50}) do o.memory[o.addr+offset]=fields[j] end
        end
      end
      -- Full legacy reference, isolated in-memory reads, no CE/Win32 or write API.
      local env={}; for k,v in pairs(_G) do env[k]=v end; env._G=env; env.print=function() end
      env.readInteger=function(addr) return assert(w.locate(addr)).memory[addr] end
      env.readFloat=function(addr) return string.unpack('<f',string.pack('<I4',env.readInteger(addr))) end
      env.getAddress=function(addr) return type(addr)=='number' and addr or tonumber(addr,16) end
      env.getCurrentMemscan=function() return {} end
      env.createFoundList=function()
        local fl={Count=#w.objects,Address={}}
        for i,o in ipairs(w.objects) do fl.Address[i-1]=o.addr end
        fl.initialize=function() end; fl.destroy=function() end; return fl
      end
      local report=w.load('mvp0_candidate_report.lua',env)
      local collector=w.load('mvp0_foundlist_collector.lua',env)
      local bundle=collector.run({scan_budget=w.cfg.scan.scan_budget,max_candidates=w.cfg.scan.max_candidates,
        target_value_pattern=0x42C80000,target_value_float=100.0,filter_target_match=true,
        use_prescore_selection=true,probe_full_foundlist=false,stable_filter_intersection_enabled=false})
      assert(bundle.raw_count==#w.objects and bundle.scanned_count==math.min(#w.objects,w.cfg.scan.scan_budget))
      local r=bundle.result; local qualifiers=0
      for _,scored in ipairs(r.ranked) do
        local one=report.rank_candidates({report.score_candidate(scored.candidate,0x42C80000)})
        if one.best.hard_pass and report.recommend_action(one).recommendation=='ACCEPT' then qualifiers=qualifiers+1 end
      end
      w.reference={best=r.best.candidate.value_addr,second=r.second and r.second.candidate.value_addr,
        score=r.best.final_score,family=r.best.template_family_size,confidence=r.confidence,
        gap=r.score_gap,recommendation=r.recommendation.recommendation,qualified=qualifiers}
      -- Native stream keeps the identical order: legacy sampling is order-sensitive.
    """)
    enable_diagnostics(lua)
    w.start()
    complete = count <= min(budgets)
    accepted = w.reference.recommendation == "ACCEPT"
    w.until_state("MONITORING" if accepted else "ERROR")
    s = w.loop.status()
    assert s.scope_complete is complete and s.raw_match_count == count
    assert s.evaluated_count == min(count, budgets[1])
    assert (s.ranking_best_address, s.ranking_second_address, s.ranking_best_score,
            s.ranking_best_family_size, s.ranking_score_gap, s.ranking_confidence, s.qualified_count) == (
        w.reference.best, w.reference.second, w.reference.score, w.reference.family,
        w.reference.gap, w.reference.confidence, w.reference.qualified)
    assert events(w, "ranking_summary")[-1].recommendation == w.reference.recommendation
    assert len(w.writes) == (1 if accepted else 0)
    w.loop.stop(); w.clean()


@pytest.mark.parametrize("count", [0, 1, 128, 129, 19276, 20000, 30000, 30001, 65537])
def test_r1_native_foundlist_keeps_actual_count_and_legacy_defaults(runtime, count, record_property):
    lua, w = runtime
    process_population(lua, w, count, (count,) if count else ())
    w.cfg.scan.scan_budget = None; w.cfg.scan.max_candidates = None
    reference = legacy_reference(lua, w)
    enable_diagnostics(lua)
    start = time.perf_counter()
    w.start(); w.until_state("MONITORING" if count else "ERROR")
    elapsed = time.perf_counter() - start
    s = w.loop.status()
    assert s.raw_match_count == len(w.scans[1].addresses) == count
    assert s.raw_admitted_count == min(count, 2000)
    assert s.unique_count == s.filtered_count == s.prescored_count == min(count, 2000)
    assert s.selected_count == s.ranked_count == min(count, 20)
    assert s.raw_admitted_count <= s.raw_inspected_count <= min(count, 4048)
    assert s.scan_complete and s.collection_complete is (count <= 20)
    assert s.raw_admission_budget == 2000 and s.ranking_budget == 20
    assert len(w.lines) <= w.cfg.log_limit and len(w.loop.evidence().events) <= 512
    assert s.raw_admitted_count == reference.scanned_count
    assert s.filtered_count == reference.filtered_count and s.prescored_count == (reference.prescored_count or 0)
    assert s.selected_count == reference.selected_count and s.ranked_count == len(reference.result.ranked)
    if count:
        assert s.ranking_best_address == reference.result.best.candidate.value_addr == w.writes[1].addr
        assert s.ranking_best_score == reference.result.best.final_score
        assert s.ranking_recommendation == reference.result.recommendation.recommendation == "ACCEPT"
        assert s.write_admission_basis == "LEGACY_SCOPE_ACCEPT" and len(w.writes) == 1
        assert s.last_written_bits == s.last_readback_bits == 0x42FA0000
        assert w.loop.evidence().scan_scope.write_admission_basis == s.write_admission_basis
        admission = events(w, "candidate_admitted")[-1]
        assert admission.write_admission_basis == s.write_admission_basis
        assert admission.global_uniqueness_proven is s.global_uniqueness_proven
    if count > 20:
        assert s.ranking_best_address == w.objects[count].addr  # last raw hit survives original selection
        assert not s.global_uniqueness_proven and s.coverage == "sampled_or_reduced"
    elif count == 1:
        assert s.global_uniqueness_proven and s.last_readback_bits == 0x42FA0000
    else:
        assert s.last_error == "RESCAN_LIMIT_EXHAUSTED" and len(w.writes) == 0
    assert elapsed < 120 and w.time < w.cfg.scan_timeout_ms
    record_property("r1_performance", json.dumps({"raw_count": count, "wall_seconds": elapsed,
        "lua": lua.eval("_VERSION"), "python": platform.python_version(), "platform": platform.system(),
        "sampled_peak_lua_bytes": int(w.peak_lua_kb * 1024), "lua_memory_ceiling_bytes": 256 * 1024 * 1024,
        "admitted": s.raw_admitted_count, "inspected": s.raw_inspected_count, "ranked": s.ranked_count,
        "filtered": s.filtered_count, "prescored": s.prescored_count, "selected": s.selected_count,
        "best_address": s.ranking_best_address, "score": s.ranking_best_score,
        "recommendation": s.ranking_recommendation, "writes": len(w.writes),
        "write_admission_basis": s.write_admission_basis, "coverage": s.coverage,
        "global_uniqueness_proven": s.global_uniqueness_proven,
        "fake_elapsed_ms": w.time, "native_acceptance": False}))
    w.loop.stop(); w.clean()


@pytest.mark.parametrize("count", [19276, 30001])
def test_r1_full_raw_admission_keeps_legacy_ranking_budget_and_allows_scope_accept(runtime, count, record_property):
    lua, w = runtime
    process_population(lua, w, count, (count,))
    w.cfg.scan.scan_budget = count; w.cfg.scan.max_candidates = 20
    start = time.perf_counter()
    w.start(); w.until_state("MONITORING")
    record_property("r1_full_intake_performance", json.dumps({"raw_count": count,
        "wall_seconds": time.perf_counter() - start, "lua": lua.eval("_VERSION"),
        "sampled_peak_lua_bytes": int(w.peak_lua_kb * 1024), "fake_elapsed_ms": w.time,
        "lua_memory_ceiling_bytes": 256 * 1024 * 1024}))
    s = w.loop.status()
    assert s.raw_match_count == s.raw_inspected_count == s.raw_admitted_count == s.filtered_count == count
    assert s.prescored_count == count and s.ranked_count == 20
    assert s.raw_admission_complete and not s.ranking_complete and not s.global_uniqueness_proven
    assert s.ranking_best_address == w.objects[count].addr
    assert s.write_admission_basis == "LEGACY_SCOPE_ACCEPT" and len(w.writes) == 1
    assert s.last_written_bits == s.last_readback_bits == 0x42FA0000
    w.loop.stop(); w.clean()


@pytest.mark.parametrize("raw_budget,rank_budget", [(2000, 20), (65536, 128), (129, 1), (128, 128)])
def test_r1_independent_legacy_budgets_are_valid_before_any_ce_access(runtime, raw_budget, rank_budget):
    _, w = runtime
    w.cfg.scan.scan_budget = raw_budget; w.cfg.scan.max_candidates = rank_budget
    c = w.core.validate(w.cfg)
    assert c.scan.scan_budget == raw_budget and c.scan.max_candidates == rank_budget
    assert w.open_calls == w.reads == len(w.writes) == 0


@pytest.mark.parametrize("key,value", [("scan_budget", 0), ("scan_budget", 65537),
    ("max_candidates", 0), ("max_candidates", 129), ("collection_batch_size", 15),
    ("collection_batch_size", 2049), ("collection_slice_ms", 0), ("collection_slice_ms", 26)])
def test_r1_intake_and_cooperative_budgets_fail_closed(runtime, key, value):
    _, w = runtime
    w.cfg.scan[key] = value
    with pytest.raises(Exception, match="INVALID_(SCAN_SETTINGS|COLLECTION_BUDGET)"):
        w.start()
    assert w.open_calls == w.reads == len(w.writes) == 0


def test_r1_float32_bits_do_not_match_literal_dword_integer_100(runtime):
    _, w = runtime
    process_scope(w)
    expected = w.object(0x100128)
    integer = w.object(0x101128); integer.memory[integer.addr] = 100
    w.start(); w.until_state("MONITORING")
    args = w.scans[1].args
    assert args[2] == w.ce.vtDword and args[4] == "42C80000" and args[11] is True
    assert int(args[4], 16) != 100 and w.loop.status().raw_match_count == 1
    assert len(w.writes) == 1 and w.writes[1].addr == expected.addr
    assert integer.memory[integer.addr] == 100 and w.loop.status().last_readback_bits == 0x42FA0000
    w.loop.stop(); w.clean()


@pytest.mark.parametrize("mode,native_fallback", [("bounded", False), ("process", False), ("process", True)])
def test_r1_recovery_cycles_use_fresh_native_objects_and_clear_previous_evidence(runtime, mode, native_fallback):
    lua, w = runtime
    if mode == "process": process_scope(w)
    if native_fallback: w.fail.scan_policy = True
    enable_diagnostics(lua, limit=2048)
    current = good(w)
    for cycle in (2, 3):
        before = w.loop.status().monitor_checks
        current.memory[current.addr] = 0x42280000  # Healthy finite drift: never rewrite.
        w.step(200)
        assert w.loop.status().monitor_checks >= before + 100
        assert len(w.scans) == len(w.writes) == cycle - 1
        previous = w.scans[cycle - 1]
        assert previous.dead and w.foundlist_history[cycle - 1].dead
        current.mapped = False
        current = w.object(0x100128 + (cycle - 1) * 0x2000)
        w.fail.no_complete = True
        w.until_state("RESCAN_BACKOFF"); w.until_state("SCREENING"); w.step()
        pending = w.loop.status()
        assert pending.cycle_id == cycle and pending.scan_count == cycle
        assert pending.raw_match_count is None and pending.coverage == "pending"
        assert pending.raw_admitted_count == pending.ranked_count == pending.qualified_count == 0
        assert pending.ranking_best_address is None and pending.ranking_recommendation is None
        assert not pending.scan_complete and not pending.collection_complete and not pending.global_uniqueness_proven
        assert len(w.foundlist_history) == cycle - 1
        # Both an authentic old sender and a forged new sender remain inert.
        previous.saved_callback(previous); previous.saved_callback(w.scans[cycle])
        w.step(3)
        assert w.loop.status().raw_match_count is None and len(w.writes) == cycle - 1
        assert len(w.foundlist_history) == cycle - 1
        w.fail.no_complete = False
        w.until_state("MONITORING")
        assert len(w.writes) == len(w.scans) == len(w.foundlist_history) == cycle
        assert w.writes[cycle].addr == current.addr
        assert w.foundlist_history[cycle].scan_id == cycle
        assert w.foundlist_history[cycle].Address[0] == format(current.addr, "X")
        assert w.loop.status().cycle_id == cycle
        assert w.loop.status().global_uniqueness_proven is (not native_fallback)
        assert w.loop.status().last_readback_bits == 0x42FA0000
    lifecycle = [(row.event, row.scan_id) for row in w.lifecycle.values()]
    assert lifecycle == [(event, cycle) for cycle in (1, 2, 3) for event in (
        "scan_created", "first_scan", "foundlist_created", "foundlist_destroyed", "scan_destroyed")]
    for kind in ("scan_invocation", "scan_population", "candidate_population", "ranking_summary", "scan_disposed"):
        assert [row.cycle_id for row in events(w, kind)] == [1, 2, 3]
    assert w.loop.evidence().dropped_events == 0
    w.loop.stop(); w.clean()


@pytest.mark.parametrize("fault,reason", [("system_info_no_output", "PROCESS_SCOPE_UNAVAILABLE"),
                                         ("create_scan", "INJECTED_create_scan")])
def test_r1_failed_fresh_scan_setup_cannot_keep_previous_unique_ranking(runtime, fault, reason):
    _, w = runtime
    process_scope(w)
    old = good(w)
    assert w.loop.status().global_uniqueness_proven and w.loop.status().ranking_best_address == old.addr
    old.mapped = False; w.object(0x102128)
    w.fail[fault] = True if fault == "system_info_no_output" else "throw"
    w.until_state("ERROR")
    s = w.loop.status()
    assert reason in s.last_error and s.cycle_id == 2
    assert s.raw_match_count is None and s.ranking_best_address is None and s.ranking_best_score is None
    assert s.raw_admitted_count == s.ranked_count == s.qualified_count == 0
    assert s.coverage == "pending" and not s.scope_complete and not s.global_uniqueness_proven
    assert len(w.scans) == len(w.foundlist_history) == len(w.writes) == 1
    w.clean()


@pytest.mark.parametrize("mode", ["bounded", "process"])
@pytest.mark.parametrize("fault,reason", [("timeout", "SCAN_TIMEOUT"), ("empty", "RESCAN_LIMIT_EXHAUSTED"),
                                         ("exit", "PID_EXITED")])
def test_r1_recovery_never_reuses_previous_population_when_fresh_scan_fails(runtime, mode, fault, reason):
    _, w = runtime
    if mode == "process": process_scope(w)
    w.cfg.max_rescan_attempts = 1
    old = good(w); old.mapped = False
    if fault == "timeout":
        w.object(0x102128); w.fail.no_complete = True
    elif fault == "exit":
        w.alive = False
    w.until_state("ERROR")
    s = w.loop.status()
    assert reason in s.last_error and len(w.writes) == 1
    assert len(w.scans) == s.cycle_id == (1 if fault == "exit" else 2)
    assert len(w.foundlist_history) == (2 if fault == "empty" else 1)
    if fault != "exit":
        assert not s.global_uniqueness_proven and s.ranking_best_address is None
        assert s.raw_match_count == (0 if fault == "empty" else None)
    assert s.cleanup_ok
    w.clean()
