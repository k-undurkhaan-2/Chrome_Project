"""WRITE-B1 / WRITE-B3-R1: real Lua 5.4 with table-backed memory, never live CE.

The optional backend is the same isolated lupa.lua54 used by screening tests.
Runner startup config I/O and main() are removed in memory for integration
checks. No runtime config, process, registry, baseline or log file is accessed.
"""

from pathlib import Path
import re

import pytest


ROOT = Path(__file__).resolve().parents[1]
EXECUTOR = ROOT / "src/mvp0_value_executor.lua"
BATCH = ROOT / "src/execute_module-v5.2.0_batch.lua"
ADDRESS = 0x12345000
ORIGINAL = 12.5
ORIGINAL_PATTERN = 0x41480000
REQUESTED = 17.75
REQUESTED_PATTERN = 0x418E0000
SOURCE_BATCH = "20261116-000500"
LOG_ROOT = str(ROOT / "log/auto_output").replace("/", "\\")


def evidence_io(lua):
    """Only Lua strings are read/written, including durable-request simulations."""
    lua.execute("""
        files = {}; opened_paths = {}; file_writes = 0
        io = {open = function(path, mode)
            opened_paths[#opened_paths + 1] = {path = path, mode = mode}
            assert(mode == 'rb' or mode == 'wb')
            if io_open_error then error('synthetic file open error') end
            if mode == 'rb' then
                if files[path] == nil then return nil, 'missing', missing_file_code or 2 end
                return {
                    read = function(self, limit)
                        if io_read_error then error('synthetic read error') end
                        return files[path]:sub(1, limit)
                    end,
                    close = function() return not io_close_failure end,
                }
            end
            file_writes = file_writes + 1
            files[path] = ''
            return {
                write = function(self, text)
                    if reservation_write_failure then return nil end
                    files[path] = text
                    if expire_during_reservation then now = expire_during_reservation end
                    if change_during_reservation then memory[0x12345000] = pattern(18) end
                    return self
                end,
                close = function() return not reservation_close_failure end,
            }
        end}
    """)


def configure_restore(lua, cfg, written, *, source_case, source_session, source_request):
    cfg.execution_addr_source = "restore_source_batch_execution_addr"
    cfg.case_id = "synthetic-restore"
    cfg.session_id = source_session
    cfg.restore_source_batch_id = SOURCE_BATCH
    cfg.restore_source_case_id = source_case
    cfg.restore_source_session_id = source_session
    cfg.restore_execution_addr = written.execution_addr
    cfg.restore_expected_current_float = written.readback_float
    cfg.restore_expected_current_pattern = written.readback_pattern
    cfg.restore_write_value_float = written.rollback_value_float
    cfg.restore_write_value_pattern = written.rollback_value_pattern
    cfg.execution_write_request_id = "synthetic-restore-request"
    cfg.execution_armed_at_utc = "2026-11-16T00:05:00Z"
    cfg.execution_arm_expires_at_utc = "2026-11-16T00:15:00Z"
    cfg.restore_process_attestation = lua.table_from({
        "identity_basis": "operator_reconfirmed", "same_process_confirmed": True,
        "source_receipt_confirmed": True, "request_id": cfg.execution_write_request_id,
        "case_id": cfg.case_id, "session_id": source_session,
        "source_write_request_id": source_request, "source_batch_id": SOURCE_BATCH,
        "confirmed_at_utc": "2026-11-16T00:05:00Z",
        "source": {"pid": 4242, "started_at_utc": "2026-11-15T23:00:00Z",
                   "executable": "synthetic-chrome.exe", "scene": "synthetic-scene"},
        "current": {"pid": 4242, "started_at_utc": "2026-11-15T23:00:00Z",
                    "executable": "synthetic-chrome.exe", "scene": "synthetic-scene"},
    }, recursive=True)


@pytest.fixture
def env():
    lua54 = pytest.importorskip("lupa.lua54", reason="requires isolated Lua 5.4 backend")
    lua = lua54.LuaRuntime(register_eval=False, register_builtins=False)
    assert lua.eval("_VERSION") == "Lua 5.4"
    lua.execute("""
        python = nil; io = nil; package = nil; require = nil
        dofile = nil; loadfile = nil
        now = '2026-11-16T00:05:00Z'
        os = {clock = function() return 0 end, date = function(format)
            assert(format == '!%Y-%m-%dT%H:%M:%SZ')
            return now
        end}
        memory = {[0x12345000] = 0x41480000}
        writes = {}; reads = 0; printed = {}
        print = function(...) printed[#printed + 1] = table.concat({...}, '\t') end
        function pattern(value) return string.unpack('<I4', string.pack('<f', value)) end
        function from_pattern(bits) return string.unpack('<f', string.pack('<I4', bits)) end
        local function fault(kind, value)
            if kind == 'error' then error('synthetic read error') end
            if kind == 'nil' then return nil end
            if kind == 'false' then return false end
            if kind == 'string' then return 'unreadable' end
            if kind == 'nan' then return 0/0 end
            if kind == 'inf' then return math.huge end
            if kind == 'fraction' then return 1.25 end
            if kind == 'overflow' then return 0x100000000 end
            return value
        end
        readInteger = function(addr)
            reads = reads + 1
            local value = memory[addr]
            if signed_integer and value >= 0x80000000 then value = value - 0x100000000 end
            return fault(integer_fault, value)
        end
        readFloat = function(addr)
            reads = reads + 1
            if expire_after_read then now = expire_after_read end
            return fault(float_fault, float_override or from_pattern(memory[addr]))
        end
        writeFloat = function(addr, value)
            writes[#writes + 1] = {addr = addr, value = value}
            if write_behavior == 'error' then error('synthetic write error') end
            if write_behavior == 'false' then return false end
            if write_behavior == 'nil' then return nil end
            if write_behavior == 'number' then return 1 end
            if write_behavior ~= 'no_change' then memory[addr] = pattern(value) end
            integer_fault = after_integer_fault; float_fault = after_float_fault
            float_override = after_float_override
            if write_behavior == 'false_after_write' then return false end
            return true
        end
        opts = {
            config = {
                case_id = 'synthetic-case', session_id = 'synthetic-session',
                validation_profile = 'full', execution_mode = 'write', write_enabled = true,
                execution_confirm = 'I_ACCEPT_WRITE_TO_LIVE_MEMORY',
                execution_write_request_id = 'synthetic-request',
                execution_armed_at_utc = '2026-11-16T00:00:00Z',
                execution_arm_expires_at_utc = '2026-11-16T00:10:00Z',
                write_value_float = 17.75, write_value_pattern = 0x418E0000,
                known_true_addr = 0x12345000,
                target_value_float = 12.5, target_value_pattern = 0x41480000,
            },
            summary = {
                case_id = 'synthetic-case', session_id = 'synthetic-session',
                validation_profile = 'full', run_valid = true, collector_empty = false,
                mode = 'stable_no_probe_intersection', known_true_addr = 0x12345000,
                stable_intersection_best_candidate = 0x12345000,
                stable_intersection_known_true_rank_position = 1,
                target_value_float = 12.5, target_value_pattern = 0x41480000,
            },
            rank_guard = {
                ok = true, rank_A = 1, rank_W = 1, rank_B = 1,
                case_id = 'synthetic-case', session_id = 'synthetic-session', validation_profile = 'full',
            },
        }
    """)
    source = EXECUTOR.read_text(encoding="utf-8")
    lua.compile(source)
    executor = lua.execute(source)
    return lua, executor, lua.globals().opts


def evaluate(env, mutation=""):
    lua, executor, opts = env
    lua.execute(mutation)
    return executor.evaluate(opts)


def assert_rejected(env, result, failure):
    assert result.execution_failure_class == failure
    assert result.execution_preconditions_ok is False
    assert result.write_attempted is result.restore_attempted is False
    assert result.write_ok is result.execution_success is False
    assert len(env[0].globals().writes) == 0


@pytest.mark.parametrize("mode,enabled", [("disabled", False), ("disabled", True)])
def test_disabled_single_never_reads_or_writes_even_with_leftover_write_fields(env, mode, enabled):
    lua, executor, opts = env
    opts.config.validation_profile = opts.summary.validation_profile = "single"
    opts.config.execution_mode, opts.config.write_enabled = mode, enabled
    opts.config.require_full_profile = False
    result = executor.evaluate(opts)
    assert result.execution_enabled is result.write_attempted is result.execution_success is False
    assert lua.globals().reads == len(lua.globals().writes) == 0


@pytest.mark.parametrize("mutation,failure", [
    ("opts.config.execution_mode = 'unknown'", "invalid_execution_mode"),
    ("opts.summary.validation_profile = 'unknown'", "invalid_validation_profile"),
    ("opts.summary.validation_profile = 'quick'", "profile_not_full"),
    ("opts.summary.validation_profile = 'single'; opts.config.require_full_profile = false", "single_detect_only"),
    ("opts.config.validation_profile = 'single'; opts.config.require_full_profile = false", "single_detect_only"),
    ("opts.config.case_id = nil", "execution_identity_mismatch"),
    ("opts.config.session_id = ' '", "execution_identity_mismatch"),
    ("opts.summary.case_id = 'old-case'", "execution_identity_mismatch"),
    ("opts.summary.session_id = 'old-session'", "execution_identity_mismatch"),
    ("opts.config.validation_profile = 'quick'", "execution_identity_mismatch"),
    ("opts.summary.run_valid = false", "run_not_valid"),
    ("opts.summary.error = 'failed'", "run_not_valid"),
    ("opts.summary.failure_class = 'failed'", "run_not_valid"),
    ("opts.summary.collector_empty = true", "collector_empty"),
    ("opts.summary.stable_intersection_best_candidate = nil", "missing_execution_addr"),
    ("opts.summary.stable_intersection_best_candidate = 0", "invalid_execution_addr"),
    ("opts.summary.stable_intersection_best_candidate = -1", "invalid_execution_addr"),
    ("opts.summary.stable_intersection_best_candidate = 1.5", "invalid_execution_addr"),
    ("opts.summary.stable_intersection_best_candidate = 0/0", "invalid_execution_addr"),
    ("opts.summary.stable_intersection_best_candidate = math.huge", "invalid_execution_addr"),
    ("opts.summary.stable_intersection_best_candidate = 0x20000000000000", "invalid_execution_addr"),
    ("opts.summary.stable_intersection_best_candidate = '0x12345000'", "invalid_execution_addr"),
    ("opts.summary.stable_intersection_known_true_rank_position = 2", "stable_rank_not_1"),
    ("opts.rank_guard = nil", "rank_guard_failed"),
    ("opts.rank_guard.ok = false", "rank_guard_failed"),
    ("opts.rank_guard.rank_W = nil", "rank_guard_failed"),
    ("opts.rank_guard.rank_B = 2", "rank_guard_failed"),
    ("opts.rank_guard.case_id = 'old-case'", "rank_guard_failed"),
    ("opts.rank_guard.session_id = 'old-session'", "rank_guard_failed"),
    ("opts.rank_guard.validation_profile = 'single'", "rank_guard_failed"),
    ("opts.summary.known_true_addr = nil; opts.config.known_true_addr = nil", "missing_known_true_addr"),
    ("opts.known_true_addr = 0x12345004", "known_true_identity_mismatch"),
    ("opts.summary.known_true_addr = 1; opts.config.known_true_addr = 1", "known_true_mismatch"),
    ("opts.config.write_enabled = false", "write_disabled"),
    ("opts.config.execution_confirm = nil", "missing_execution_confirm"),
    ("opts.config.execution_confirm = 'WRITE_ONCE'", "missing_execution_confirm"),
    ("opts.config.execution_write_request_id = ' '", "missing_execution_arm"),
    ("opts.config.execution_armed_at_utc = nil", "missing_execution_arm"),
    ("opts.config.execution_arm_expires_at_utc = nil", "missing_execution_arm"),
    ("opts.config.write_method = 'integer'", "unsupported_write_method"),
    ("opts.config.write_value_float = nil", "invalid_write_value_float"),
    ("opts.config.write_value_float = 0/0", "invalid_write_value_float"),
    ("opts.config.write_value_float = math.huge", "invalid_write_value_float"),
    ("opts.config.write_value_float = 1e40", "invalid_write_value_float"),
    ("opts.config.write_value_pattern = 1", "write_value_pattern_mismatch"),
    ("opts.config.readback_tolerance = -1", "invalid_readback_tolerance"),
    ("opts.config.readback_tolerance = 'bad'", "invalid_readback_tolerance"),
    ("opts.config.readback_tolerance = 0/0", "invalid_readback_tolerance"),
    ("opts.config.readback_tolerance = math.huge", "invalid_readback_tolerance"),
    ("opts.config.target_value_pattern = nil; opts.summary.target_value_pattern = nil", "missing_target_value_pattern"),
    ("opts.summary.target_value_pattern = 1", "target_value_identity_mismatch"),
    ("opts.target_value_pattern = 1", "target_value_identity_mismatch"),
    ("opts.config.target_value_float = 10", "target_value_identity_mismatch"),
    ("memory[0x12345000] = pattern(13)", "old_value_mismatch"),
    ("float_override = 13", "old_value_inconsistent"),
    ("readInteger = nil", "old_value_read_failed"),
    ("readFloat = nil", "old_value_read_failed"),
    ("writeFloat = nil", "write_api_unavailable"),
])
def test_preconditions_reject_without_a_write(env, mutation, failure):
    assert_rejected(env, evaluate(env, mutation), failure)


@pytest.mark.parametrize("field", ["integer_fault", "float_fault"])
@pytest.mark.parametrize("fault", ["nil", "error", "false", "string", "nan", "inf"])
def test_failed_read_apis_reject(env, field, fault):
    assert_rejected(env, evaluate(env, f"{field} = '{fault}'"), "old_value_read_failed")


@pytest.mark.parametrize("fault", ["fraction", "overflow"])
def test_malformed_integer_reads_reject(env, fault):
    assert_rejected(env, evaluate(env, f"integer_fault = '{fault}'"), "old_value_read_failed")


@pytest.mark.parametrize("armed,expires,now,failure", [
    ("2026-11-16T00:00:00Z", "2026-11-16T00:05:00Z", "2026-11-16T00:05:00Z", "execution_arm_expired"),
    ("2026-11-16T00:00:00Z", "2026-11-16T00:04:59Z", "2026-11-16T00:05:00Z", "execution_arm_expired"),
    ("2026-11-16T00:06:00Z", "2026-11-16T00:10:00Z", "2026-11-16T00:05:00Z", "invalid_execution_arm_window"),
    ("2026-11-16T00:10:00Z", "2026-11-16T00:00:00Z", "2026-11-16T00:05:00Z", "invalid_execution_arm_window"),
    ("2026-11-16T00:00:00Z", "2026-11-16T00:00:00Z", "2026-11-16T00:05:00Z", "invalid_execution_arm_window"),
    ("2026-02-29T00:00:00Z", "2026-11-16T00:10:00Z", "2026-11-16T00:05:00Z", "missing_execution_arm"),
    ("2026-11-31T00:00:00Z", "2026-11-16T00:10:00Z", "2026-11-16T00:05:00Z", "missing_execution_arm"),
    ("2026-11-16T24:00:00Z", "2026-11-16T00:10:00Z", "2026-11-16T00:05:00Z", "missing_execution_arm"),
    ("2026-11-16T00:00:00+08:00", "2026-11-16T00:10:00Z", "2026-11-16T00:05:00Z", "missing_execution_arm"),
    ("2026-11-16T00:00:00Z", "2026-11-16T00:10:00Z", "bad-clock", "missing_execution_arm"),
])
def test_arm_windows_are_strict_utc(env, armed, expires, now, failure):
    lua, _, opts = env
    opts.config.execution_armed_at_utc = armed
    opts.config.execution_arm_expires_at_utc = expires
    lua.globals().now = now
    assert_rejected(env, evaluate(env), failure)


def test_expiry_during_prewrite_reads_is_rechecked(env):
    assert_rejected(env, evaluate(env, "expire_after_read = '2026-11-16T00:10:00Z'"), "execution_arm_expired")
    assert env[0].globals().reads == 2


@pytest.mark.parametrize("enabled", [False, True])
def test_dry_run_reports_preview_without_writes(env, enabled):
    lua, _, opts = env
    opts.config.execution_mode = "dry_run"
    opts.config.write_enabled = enabled
    result = evaluate(env)
    assert result.execution_preconditions_ok is True
    assert result.write_ready is enabled
    assert result.execution_failure_class is None
    assert result.write_readiness_failure_class == (None if enabled else "write_disabled")
    assert result.execution_addr == ADDRESS
    assert result.old_value_float == ORIGINAL and result.old_value_pattern == ORIGINAL_PATTERN
    assert result.requested_write_value_float == REQUESTED
    assert result.requested_write_value_pattern == REQUESTED_PATTERN
    assert result.write_attempted is result.write_ok is result.execution_success is False
    assert result.rollback_available is False
    assert lua.globals().reads == 2 and len(lua.globals().writes) == 0


def test_unarmed_dry_run_reads_but_does_not_claim_write_ready(env):
    result = evaluate(env, "opts.config.execution_mode = 'dry_run'; opts.config.execution_confirm = nil")
    assert result.execution_preconditions_ok is True and result.write_ready is False
    assert result.write_readiness_failure_class == "missing_execution_confirm"
    assert env[0].globals().reads == 2 and len(env[0].globals().writes) == 0


@pytest.mark.parametrize("mutation,failure", [
    ("opts.rank_guard.rank_A = 2", "rank_guard_failed"),
    ("opts.config.write_value_pattern = 1", "write_value_pattern_mismatch"),
    ("memory[0x12345000] = pattern(13)", "old_value_mismatch"),
])
def test_dry_run_keeps_data_and_rank_gates(env, mutation, failure):
    assert_rejected(env, evaluate(env, "opts.config.execution_mode = 'dry_run'; " + mutation), failure)


def test_successful_write_is_exactly_one_write_with_two_readbacks(env):
    result = evaluate(env)
    g = env[0].globals()
    assert result.write_attempted is result.write_api_ok is result.write_ok is result.readback_ok is True
    assert result.execution_success is result.rollback_available is True
    assert result.restore_attempted is result.restore_write_ok is result.restore_readback_ok is False
    assert result.rollback_value_float == ORIGINAL and result.rollback_value_pattern == ORIGINAL_PATTERN
    assert result.readback_float == REQUESTED and result.readback_pattern == REQUESTED_PATTERN
    assert result.execution_failure_class is None
    assert result.execution_arm_seconds_remaining == 300
    assert len(g.writes) == 1 and g.reads == 4
    assert g.writes[1].addr == ADDRESS and g.writes[1].value == REQUESTED


def test_requested_value_is_rounded_to_float32_before_write(env):
    result = evaluate(env, "opts.config.write_value_float = 0.1; opts.config.write_value_pattern = nil")
    assert result.write_ok is True
    assert result.requested_write_value_float == pytest.approx(0.10000000149011612, abs=1e-16)
    assert result.requested_write_value_pattern == 0x3DCCCCCD
    assert result.readback_delta == 0


def test_signed_integer_pattern_and_negative_original_are_supported(env):
    result = evaluate(env, """
        memory[0x12345000] = pattern(-12.5); signed_integer = true
        opts.config.target_value_float = -12.5; opts.summary.target_value_float = -12.5
        opts.config.target_value_pattern = -1052246016; opts.summary.target_value_pattern = 0xC1480000
    """)
    assert result.write_ok is True
    assert result.rollback_value_float == -12.5 and result.rollback_value_pattern == 0xC1480000


@pytest.mark.parametrize("behavior", ["false", "nil", "error", "number", "false_after_write"])
def test_write_api_failure_never_implies_success_or_automatic_rollback(env, behavior):
    result = evaluate(env, f"write_behavior = '{behavior}'")
    assert result.write_attempted is True
    assert result.write_api_ok is result.write_ok is result.readback_ok is result.execution_success is False
    assert result.execution_failure_class == "write_failed"
    assert result.rollback_available is True and result.restore_attempted is False
    assert len(env[0].globals().writes) == 1


@pytest.mark.parametrize("mutation,failure", [
    ("write_behavior = 'no_change'", "readback_mismatch"),
    ("after_integer_fault = 'nil'", "readback_read_failed"),
    ("after_integer_fault = 'error'", "readback_read_failed"),
    ("after_float_fault = 'nil'", "readback_read_failed"),
    ("after_float_fault = 'error'", "readback_read_failed"),
    ("after_float_fault = 'nan'", "readback_read_failed"),
    ("after_float_override = 18", "readback_mismatch"),
    ("after_float_override = 17.75001", "readback_mismatch"),
    ("after_float_override = 18; opts.config.readback_tolerance = 10", "readback_mismatch"),
    ("write_behavior = 'no_change'; after_float_override = 17.75", "readback_mismatch"),
])
def test_readback_failure_is_not_write_success(env, mutation, failure):
    result = evaluate(env, mutation)
    assert result.write_attempted is result.write_api_ok is True
    assert result.write_ok is result.readback_ok is result.execution_success is False
    assert result.execution_failure_class == failure
    assert result.restore_attempted is False and len(env[0].globals().writes) == 1


def prepare_restore(env):
    """Use genuine execution results and runner-rendered source evidence."""
    written = evaluate(env)
    assert written.execution_success is True
    lua, _, opts = env
    cfg = opts.config
    api = runner_api(env)
    summary, log = api.receipts(SOURCE_BATCH, cfg, opts.summary, written)
    evidence_io(lua)
    lua.globals().files[f"{LOG_ROOT}\\{SOURCE_BATCH}__summary.txt"] = summary
    lua.globals().files[f"{LOG_ROOT}\\{SOURCE_BATCH}__{cfg.session_id}__{cfg.case_id}__stable_no_probe_intersection.log"] = log
    configure_restore(lua, cfg, written, source_case=cfg.case_id,
                      source_session=cfg.session_id, source_request=cfg.execution_write_request_id)
    opts.summary = None
    opts.rank_guard = None
    lua.execute("writes = {}; reads = 0")


def test_explicit_restore_checks_current_state_then_writes_and_verifies_original(env):
    prepare_restore(env)
    result = evaluate(env)
    assert result.restore_current_value_match is result.restore_attempted is True
    assert result.restore_write_ok is result.restore_readback_ok is result.execution_success is True
    assert result.write_ok is True and result.execution_failure_class is None
    assert result.readback_float == ORIGINAL and result.readback_pattern == ORIGINAL_PATTERN
    g = env[0].globals()
    assert len(g.writes) == 1 and g.writes[1].value == ORIGINAL and g.reads == 6


@pytest.mark.parametrize("mutation,failure", [
    ("memory[0x12345000] = pattern(18)", "restore_old_value_mismatch"),
    ("opts.config.restore_source_batch_id = nil", "missing_restore_source_batch_id"),
    ("opts.config.restore_execution_addr = nil", "missing_restore_execution_addr"),
    ("opts.config.restore_execution_addr = 0", "invalid_restore_execution_addr"),
    ("opts.config.restore_expected_current_pattern = nil", "missing_restore_expected_current"),
    ("opts.config.restore_write_value_float = nil", "missing_restore_write_value"),
    ("opts.config.restore_write_value_pattern = 1", "restore_value_pattern_mismatch"),
    ("opts.config.restore_expected_current_float = 1", "restore_value_pattern_mismatch"),
    ("opts.config.restore_write_value_float = math.huge", "restore_value_pattern_mismatch"),
    ("opts.config.session_id = 'stale'", "restore_source_identity_mismatch"),
    ("opts.config.execution_confirm = nil", "missing_execution_confirm"),
    ("now = '2026-11-16T00:15:00Z'", "execution_arm_expired"),
])
def test_restore_rejects_without_second_write(env, mutation, failure):
    prepare_restore(env)
    assert_rejected(env, evaluate(env, mutation), failure)


@pytest.mark.parametrize("mutation,api_ok,readback_ok,failure", [
    ("write_behavior = 'false'", False, False, "write_failed"),
    ("write_behavior = 'nil'", False, False, "write_failed"),
    ("write_behavior = 'error'", False, False, "write_failed"),
    ("write_behavior = 'no_change'", True, False, "readback_mismatch"),
    ("after_float_fault = 'nil'", True, False, "readback_read_failed"),
])
def test_restore_api_and_readback_failures_are_distinct(env, mutation, api_ok, readback_ok, failure):
    prepare_restore(env)
    result = evaluate(env, mutation)
    assert result.restore_attempted is True
    assert result.restore_write_ok is api_ok and result.restore_readback_ok is readback_ok
    assert result.execution_success is result.write_ok is False
    assert result.execution_failure_class == failure and len(env[0].globals().writes) == 1


def test_restore_dry_run_performs_zero_writes(env):
    prepare_restore(env)
    result = evaluate(env, "opts.config.execution_mode = 'dry_run'")
    assert result.execution_preconditions_ok is result.restore_current_value_match is True
    assert result.requested_write_value_float == ORIGINAL
    assert result.restore_attempted is result.restore_readback_ok is False
    assert len(env[0].globals().writes) == 0


def runner_api(env):
    lua, _, _ = env
    source = BATCH.read_text(encoding="utf-8")
    lua.compile(source)
    startup = "RUN_CASES = apply_local_case_config(RUN_CASES, LOCAL_CASE_CONFIG_PATH)"
    assert source.count(startup) == 1
    source = source.replace(startup, "-- Synthetic test: no config I/O.")
    source, tail = source.rsplit("\nmain()", 1)
    assert not tail.strip()
    return lua.execute(source + """
        load_value_executor = function() return MVP0ValueExecutor end
        return {
            evaluate = evaluate_value_execution, guard = build_execution_rank_guard,
            apply = apply_execution_fields, append = append_execution_lines,
            default = build_default_execution_result, print = print_execution_fields,
            apply_config = apply_local_case_config,
            restore_config = apply_restore_case_fields, config_path = LOCAL_CASE_CONFIG_PATH,
            receipts = function(batch, cfg, summary, result)
                summary.stable_intersection_base_snapshot = 'no_probe_B'
                apply_execution_fields(summary, result)
                active_log_lines = {}
                emit_compact_stable_intersection_report(cfg, summary, {})
                print_execution_fields(summary)
                local log = table.concat(active_log_lines, '\\r\\n')
                active_log_lines = nil
                return render_summary_file(batch, {summary}), log
            end,
        }
    """)


def test_runner_evaluates_real_executor_and_persists_transaction_fields(env):
    lua, _, opts = env
    api = runner_api(env)
    result = api.evaluate(opts.config, opts.summary, opts.rank_guard)
    assert result.execution_success is True and len(lua.globals().writes) == 1
    api.apply(opts.summary, result)
    lines = lua.table()
    api.append(lines, opts.summary)
    api.print(opts.summary)
    saved = "\n".join(lines.values())
    for key in ("execution_identity_ok", "execution_success", "write_api_ok", "write_ok", "readback_ok"):
        assert f"{key} = true" in saved
    for key in ("restore_attempted", "restore_write_ok", "restore_readback_ok"):
        assert f"{key} = false" in saved


@pytest.mark.parametrize("mutation", [
    "w.run_valid = false", "w.error = 'failed'", "w.collector_empty = true",
    "w.case_id = 'stale'", "w.session_id = 'stale'", "w.validation_profile = 'single'",
    "w.known_true_rank_position = 2",
])
def test_runner_guard_rejects_invalid_or_unrelated_awb_summaries(env, mutation):
    lua, _, _ = env
    api = runner_api(env)
    lua.execute("""
        function summary()
            return {case_id = 'synthetic-case', session_id = 'synthetic-session',
                    validation_profile = 'full', run_valid = true, known_true_rank_position = 1}
        end
        a = summary(); w = summary(); b = summary()
    """)
    g = lua.globals()
    assert api.guard(g.a, g.w, g.b).ok is True
    lua.execute(mutation)
    assert api.guard(g.a, g.w, g.b).ok is False


@pytest.mark.parametrize("missing", [None, False, 42])
def test_runner_guard_handles_missing_or_unusable_summaries(env, missing):
    lua, _, _ = env
    api = runner_api(env)
    valid = lua.eval("{case_id='case', session_id='session', validation_profile='full', run_valid=true, known_true_rank_position=1}")
    for summaries in ((missing, valid, valid), (valid, missing, valid), (valid, valid, missing)):
        assert api.guard(*summaries).ok is False


@pytest.mark.parametrize("profile", ["full", "quick"])
def test_runner_disabled_defaults_remain_nonwriting(env, profile):
    lua, _, opts = env
    api = runner_api(env)
    opts.config.validation_profile = opts.summary.validation_profile = profile
    opts.config.execution_mode, opts.config.write_enabled = "disabled", False
    result = api.evaluate(opts.config, opts.summary, None)
    assert result.execution_enabled is result.write_attempted is False
    assert lua.globals().reads == len(lua.globals().writes) == 0


def test_runner_reports_malformed_rejected_values_without_formatting_error(env):
    lua, _, opts = env
    api = runner_api(env)
    opts.config.write_value_pattern = float("nan")
    result = api.evaluate(opts.config, opts.summary, opts.rank_guard)
    assert_rejected(env, result, "write_value_pattern_mismatch")
    api.print(result)
    lines = lua.table()
    api.append(lines, result)
    assert "execution_failure_class = write_value_pattern_mismatch" in "\n".join(lines.values())


def test_single_screening_ignores_leftover_write_and_restore_fields():
    from test_screening_single_mode import assert_no_execution, runtime

    lua, api, cfg = runtime()
    cfg.write_value_float, cfg.write_value_pattern = REQUESTED, REQUESTED_PATTERN
    cfg.execution_confirm = "I_ACCEPT_WRITE_TO_LIVE_MEMORY"
    cfg.execution_write_request_id = "leftover-arm"
    cfg.restore_execution_addr = ADDRESS
    cfg.restore_source_batch_id = "old-batch"
    api.main()
    assert cfg.execution_mode == "disabled" and cfg.write_enabled is False
    assert_no_execution(lua)


def full_main_runtime(mode):
    from test_stable_prescore_optimization import COLLECTOR, TRUTH, new_runtime

    lua = new_runtime(COLLECTOR.read_text(encoding="utf-8"), count=120)
    lua.execute(EXECUTOR.read_text(encoding="utf-8"))
    source = BATCH.read_text(encoding="utf-8")
    source = source.replace(
        "RUN_CASES = apply_local_case_config(RUN_CASES, LOCAL_CASE_CONFIG_PATH)",
        "-- Synthetic test: no config I/O.",
    )
    source, tail = source.rsplit("\nmain()", 1)
    assert not tail.strip()
    api = lua.execute(source + """
        saved = {}; writes = {}; evaluation_count = 0; execution_results = {}
        os.date = function(format)
            return format == '!%Y-%m-%dT%H:%M:%SZ' and '2026-11-16T00:05:00Z' or '20261116-000500'
        end
        ensure_directory = function() end
        load_modules = function() active_snapshot = 0 end
        load_value_executor = function() return MVP0ValueExecutor end
        write_text_file = function(path, text) saved[path] = text end
        local original_evaluate = evaluate_value_execution
        evaluate_value_execution = function(cfg, summary, guard)
            evaluation_count = evaluation_count + 1
            -- Use the real A/W/B guard generated from the real synthetic run.
            assert(summary.mode == 'stable_no_probe_intersection' and guard.ok == true)
            local integer_reader, float_reader = readInteger, readFloat
            local current = 100.0
            readInteger = function(addr)
                assert(addr == cfg.known_true_addr)
                return string.unpack('<I4', string.pack('<f', current))
            end
            readFloat = function(addr) assert(addr == cfg.known_true_addr); return current end
            writeFloat = function(addr, value)
                assert(addr == cfg.known_true_addr)
                writes[#writes + 1] = {addr = addr, value = value}
                current = value
                return true
            end
            local result = original_evaluate(cfg, summary, guard)
            execution_results[#execution_results + 1] = result
            readInteger, readFloat = integer_reader, float_reader
            return result
        end
        return {main = main, config = RUN_CASES[1]}
    """)
    cfg = api.config
    cfg.case_id = "synthetic-full"
    cfg.session_id = "synthetic-session"
    cfg.known_true_addr = TRUTH
    cfg.execution_mode, cfg.write_enabled = mode, mode == "write"
    cfg.write_value_float, cfg.write_value_pattern = REQUESTED, REQUESTED_PATTERN
    cfg.execution_confirm = "I_ACCEPT_WRITE_TO_LIVE_MEMORY"
    cfg.execution_write_request_id = "synthetic-full-request"
    cfg.execution_armed_at_utc = "2026-11-16T00:00:00Z"
    cfg.execution_arm_expires_at_utc = "2026-11-16T00:10:00Z"
    return lua, api, cfg


@pytest.mark.parametrize("mode,expected_writes", [("disabled", 0), ("dry_run", 0), ("write", 1)])
def test_full_main_real_screening_guard_executor_and_saved_outputs(mode, expected_writes):
    lua, api, cfg = full_main_runtime(mode)
    api.main()
    g = lua.globals()
    assert g.evaluation_count == 1 and len(g.writes) == expected_writes
    result = g.execution_results[1]
    assert result.execution_failure_class is None
    assert result.write_ok is result.execution_success is (mode == "write")
    assert result.restore_readback_ok is False
    for path, text in g.saved.items():
        if path.endswith(("__summary.txt", "__diagnostic_diff.txt", "__stable_no_probe_intersection.log")):
            normalized = re.sub(r"[ \t]+=", " =", text)
            assert f"execution_success = {str(mode == 'write').lower()}" in normalized
            assert "restore_readback_ok = false" in normalized
    assert len(list(g.saved.items())) == 6  # A/W/B/stable logs plus summary and diagnostic diff.


def restore_main_api(env, *, missing_collectors=False, load_config=False):
    lua, _, opts = env
    source = BATCH.read_text(encoding="utf-8")
    lua.compile(source)
    if not load_config:
        source = source.replace(
            "RUN_CASES = apply_local_case_config(RUN_CASES, LOCAL_CASE_CONFIG_PATH)",
            "-- Synthetic: no runtime config I/O.",
        )
    source, tail = source.rsplit("\nmain()", 1)
    assert not tail.strip()
    api = lua.execute(source + """
        saved = {}; collector_calls = 0; evaluation_count = 0; restore_summaries = {}
        local sequence = 0
        os.date = function(format)
            if format == '!%Y-%m-%dT%H:%M:%SZ' then return now end
            sequence = sequence + 1
            return string.format('20261116-0005%02d', sequence)
        end
        local function forbidden()
            collector_calls = collector_calls + 1
            error('restore must never collect, rank or truth-probe')
        end
        MVP0FoundList = setmetatable({}, {__index = function() forbidden() end})
        MVP0 = setmetatable({}, {__index = function() forbidden() end})
        getCurrentMemscan = forbidden; createFoundList = forbidden; getFoundList = forbidden
        getTickCount = forbidden; load_modules = forbidden
        build_execution_rank_guard = forbidden; run_stable_intersection_mode = forbidden
        run_case_mode = forbidden; get_case_mode_entries = forbidden
        ensure_directory = function() end
        load_value_executor = function() return MVP0ValueExecutor end
        write_text_file = function(path, text) saved[path] = text end
        local evaluate = evaluate_value_execution
        evaluate_value_execution = function(cfg, summary, guard)
            assert(summary == nil and guard == nil)
            evaluation_count = evaluation_count + 1
            local result = evaluate(cfg, summary, guard)
            restore_results = result
            return result
        end
        local render = render_summary_file
        render_summary_file = function(batch, summaries)
            restore_summaries = summaries
            return render(batch, summaries)
        end
        return {main = main, cases = RUN_CASES}
    """)
    if not load_config:
        api.cases[1] = opts.config
    if missing_collectors:
        lua.execute("MVP0FoundList = nil; MVP0 = nil; getCurrentMemscan = nil; createFoundList = nil; getFoundList = nil")
    return api


@pytest.mark.parametrize("missing_collectors", [False, True])
def test_independent_main_restores_actual_full_write_with_no_collector_apis(env, missing_collectors):
    # Real Full A/W/B/stable -> actual executor -> actual source log renderers.
    source_lua, source_api, source_cfg = full_main_runtime("write")
    source_cfg.write_value_float, source_cfg.write_value_pattern = 999.0, 0x4479C000
    source_api.main()
    written = source_lua.globals().execution_results[1]
    assert written.execution_success is True and written.rollback_value_float == 100.0
    assert len(source_lua.globals().writes) == 1
    source_files = dict(source_lua.globals().saved.items())

    # A new Lua runtime receives only the immutable evidence and current memory.
    lua, _, opts = env
    evidence_io(lua)
    for path, text in source_files.items():
        lua.globals().files[path] = text
    configure_restore(lua, opts.config, written, source_case=source_cfg.case_id,
                      source_session=source_cfg.session_id, source_request=source_cfg.execution_write_request_id)
    lua.globals().memory[written.execution_addr] = written.readback_pattern
    opts.config.known_true_addr = None
    opts.config.target_value_float = opts.config.target_value_pattern = None
    opts.summary = False
    opts.rank_guard = None
    opts.config.execution_mode, opts.config.write_enabled = "dry_run", False
    api = restore_main_api(env, missing_collectors=missing_collectors)
    api.main()
    g = lua.globals()
    preview = g.restore_results
    assert preview.execution_preconditions_ok is preview.restore_source_evidence_ok is True
    assert preview.write_ready is preview.write_attempted is preview.restore_attempted is False
    assert preview.write_readiness_failure_class == "write_disabled"
    assert g.collector_calls == len(g.writes) == g.file_writes == 0
    assert len(list(g.saved.items())) == 3

    opts.config.execution_mode, opts.config.write_enabled = "write", True
    api.main()
    restored = g.restore_results
    assert restored.restore_write_ok is restored.restore_readback_ok is restored.execution_success is True
    assert restored.restore_request_reserved is True
    assert restored.readback_float == 100.0 and restored.readback_pattern == 0x42C80000
    assert len(g.writes) == 1 and g.writes[1].value == 100.0
    assert g.collector_calls == 0 and g.reads == 8
    assert g.file_writes == 1 and len(list(g.saved.items())) == 6
    summary = g.restore_summaries[1]
    assert summary.mode == "restore_only"
    assert summary.run_valid is summary.baseline_eligible is summary.screening_performed is False
    for path, text in g.saved.items():
        assert path.endswith(("__restore_only.log", "__summary.txt", "__diagnostic_diff.txt"))
        assert "mode = restore_only" in text and "baseline_eligible = false" in text
        assert "screening_performed = false" in text and "run_valid = false" in text
        assert "restore_source_evidence_ok = true" in text
        assert "restore_identity_basis = operator_reconfirmed" in text
        assert "restore_process_measured = false" in text
        assert "restore_source_case_id = synthetic-full" in text
        assert "restore_source_session_id = synthetic-session" in text
        assert "restore_source_batch_id = " + SOURCE_BATCH in text
        for field in ("execution_write_request_id", "execution_armed_at_utc", "execution_arm_expires_at_utc",
                      "execution_addr", "restore_expected_current_pattern", "restore_write_value_pattern",
                      "write_attempted", "restore_attempted", "restore_write_ok", "restore_readback_ok"):
            assert f"{field} = " in text
    for path, text in source_files.items():
        assert g.files[path] == text


@pytest.mark.parametrize("summary", [None, False, 42, "not a screening summary"])
def test_restore_does_not_dereference_invalid_screening_summary_or_rank(env, summary):
    prepare_restore(env)
    env[2].summary = summary
    env[2].rank_guard = False
    result = evaluate(env, "opts.config.known_true_addr = nil; opts.config.target_value_pattern = 1")
    assert result.execution_success is True
    assert result.rank_guard_ok is False


@pytest.mark.parametrize("mutation,failure", [
    ("opts.config.restore_source_batch_id = '../20261116-000500'", "invalid_restore_source_identity"),
    ("opts.config.restore_source_case_id = '..'", "invalid_restore_source_identity"),
    ("opts.config.restore_source_session_id = 'x/y'", "invalid_restore_source_identity"),
    ("opts.config.restore_source_case_id = 'other'", "restore_source_identity_mismatch"),
    ("opts.config.restore_source_session_id = 'other'", "restore_source_identity_mismatch"),
    ("opts.config.restore_execution_addr = 0x12345004", "restore_source_address_mismatch"),
    ("opts.config.restore_expected_current_float = 18; opts.config.restore_expected_current_pattern = pattern(18)", "restore_source_value_mismatch"),
    ("opts.config.restore_write_value_float = 13; opts.config.restore_write_value_pattern = pattern(13)", "restore_source_value_mismatch"),
    ("opts.config.restore_process_attestation = nil", "restore_process_attestation_invalid"),
    ("opts.config.restore_process_attestation.identity_basis = 'measured'", "restore_process_attestation_invalid"),
    ("opts.config.restore_process_attestation.same_process_confirmed = false", "restore_process_attestation_invalid"),
    ("opts.config.restore_process_attestation.source_receipt_confirmed = false", "restore_process_attestation_invalid"),
    ("opts.config.restore_process_attestation.request_id = 'other'", "restore_process_attestation_invalid"),
    ("opts.config.restore_process_attestation.source_write_request_id = 'other'", "restore_process_attestation_invalid"),
    ("opts.config.restore_process_attestation.source_batch_id = 'other'", "restore_process_attestation_invalid"),
    ("opts.config.restore_process_attestation.case_id = 'other'", "restore_process_attestation_invalid"),
    ("opts.config.restore_process_attestation.session_id = 'other'", "restore_process_attestation_invalid"),
    ("opts.config.restore_process_attestation.current.pid = 4243", "restore_process_identity_changed"),
    ("opts.config.restore_process_attestation.current.pid = 0", "restore_process_attestation_invalid"),
    ("opts.config.restore_process_attestation.current.pid = '4242'", "restore_process_attestation_invalid"),
    ("opts.config.restore_process_attestation.current.started_at_utc = '2026-11-15T23:01:00Z'", "restore_process_identity_changed"),
    ("opts.config.restore_process_attestation.current.executable = 'other.exe'", "restore_process_identity_changed"),
    ("opts.config.restore_process_attestation.current.scene = 'other-scene'", "restore_process_identity_changed"),
    ("opts.config.restore_process_attestation.current.scene = 'unknown'", "restore_process_attestation_invalid"),
    ("opts.config.restore_process_attestation.confirmed_at_utc = '2026-11-16T00:06:00Z'", "restore_process_attestation_invalid"),
    ("opts.config.restore_process_attestation.confirmed_at_utc = '2026-11-15T23:00:00Z'", "restore_process_attestation_invalid"),
    ("opts.config.restore_process_attestation.confirmed_at_utc = '2026-11-16T00:04:59Z'", "restore_attestation_predates_arm"),
    ("opts.config.execution_write_request_id = 'synthetic-request'; opts.config.restore_process_attestation.request_id = 'synthetic-request'", "restore_authorization_reused"),
    ("opts.config.execution_armed_at_utc = '2026-11-16T00:00:00Z'", "restore_authorization_reused"),
    ("opts.config.execution_arm_expires_at_utc = '2026-11-16T00:15:01Z'", "restore_arm_too_long"),
    ("opts.config.execution_armed_at_utc = nil", "missing_execution_arm"),
    ("opts.config.execution_arm_expires_at_utc = nil", "missing_execution_arm"),
    ("opts.config.execution_confirm = nil", "missing_execution_confirm"),
    ("opts.config.write_enabled = false", "write_disabled"),
    ("opts.config.execution_mode = 'typo'", "invalid_execution_mode"),
    ("opts.config.validation_profile = 'single'; opts.config.require_full_profile = false", "single_detect_only"),
    ("opts.config.validation_profile = 'quick'; opts.config.require_full_profile = false", "profile_not_full"),
    ("readInteger = nil", "old_value_read_failed"),
    ("readFloat = nil", "old_value_read_failed"),
    ("writeFloat = nil", "write_api_unavailable"),
    ("float_override = 18", "old_value_inconsistent"),
    ("float_override = 17.750000001", "restore_old_value_mismatch"),
    ("opts.config.require_old_value_match = false; opts.config.require_known_true_match = false; memory[0x12345000] = pattern(18)", "restore_old_value_mismatch"),
    ("expire_after_read = '2026-11-16T00:15:00Z'", "execution_arm_expired"),
    ("expire_during_reservation = '2026-11-16T00:15:00Z'", "execution_arm_expired"),
    ("change_during_reservation = true", "restore_old_value_mismatch"),
    ("reservation_write_failure = true", "restore_request_reservation_failed"),
    ("reservation_close_failure = true", "restore_request_reservation_failed"),
    ("missing_file_code = 13", "restore_request_check_failed"),
    ("io = nil", "restore_evidence_io_unavailable"),
    ("io_open_error = true", "restore_source_evidence_missing"),
    ("io_read_error = true", "restore_source_evidence_malformed"),
    ("io_close_failure = true", "restore_source_evidence_malformed"),
])
def test_restore_independent_safety_rejections(env, mutation, failure):
    prepare_restore(env)
    assert_rejected(env, evaluate(env, mutation), failure)


@pytest.mark.parametrize("mutation,expected", [
    ("write_ok = true", "restore_source_write_not_successful"),
    ("write_api_ok = true", "restore_source_write_not_successful"),
    ("readback_ok = true", "restore_source_write_not_successful"),
    ("execution_success = true", "restore_source_write_not_successful"),
    ("old_value_read_ok = true", "restore_source_write_not_successful"),
    ("rank_guard_ok = true", "restore_source_write_not_successful"),
    ("execution_arm_valid = true", "restore_source_write_not_successful"),
])
def test_failed_source_evidence_even_when_both_files_agree_is_rejected(env, mutation, expected):
    prepare_restore(env)
    for path, text in list(env[0].globals().files.items()):
        # Normalize renderer alignment before editing both real receipts.
        text = re.sub(r"[ \t]+=", " =", text)
        env[0].globals().files[path] = text.replace(mutation, mutation.replace("true", "false"))
    assert_rejected(env, evaluate(env), expected)


@pytest.mark.parametrize("kind,failure", [
    ("missing_summary", "restore_source_evidence_missing"),
    ("missing_log", "restore_source_evidence_missing"),
    ("forged_config_receipt", "restore_source_evidence_missing"),
    ("mismatching_log", "restore_source_evidence_mismatch"),
    ("duplicate_key", "restore_source_evidence_malformed"),
    ("duplicate_stable_block", "restore_source_evidence_malformed"),
    ("wrong_batch", "restore_source_evidence_malformed"),
    ("truncated", "restore_source_evidence_malformed"),
    ("oversized", "restore_source_evidence_malformed"),
    ("nul", "restore_source_evidence_malformed"),
])
def test_missing_forged_ambiguous_and_malformed_source_evidence(env, kind, failure):
    prepare_restore(env)
    lua, _, opts = env
    files = lua.globals().files
    summary_path = f"{LOG_ROOT}\\{SOURCE_BATCH}__summary.txt"
    log_path = next(path for path in files if path.endswith(".log"))
    summary = files[summary_path]
    if kind in ("missing_summary", "forged_config_receipt"):
        files[summary_path] = None
        if kind == "forged_config_receipt":
            opts.config.restore_source_receipt = summary
            opts.config.restore_evidence_root = "another-root"
    elif kind == "missing_log":
        files[log_path] = None
    elif kind == "mismatching_log":
        files[log_path] = re.sub(r"(write_ok\s+= )true", r"\g<1>false", files[log_path])
    elif kind == "duplicate_key":
        files[log_path] += "\nwrite_ok = true\n"
    elif kind == "duplicate_stable_block":
        files[summary_path] = summary + summary
    elif kind == "wrong_batch":
        files[summary_path] = summary.replace(SOURCE_BATCH, "20261116-000400")
    elif kind == "truncated":
        files[summary_path] = summary[:100]
    elif kind == "oversized":
        files[log_path] = "x" * (1024 * 1024 + 1)
    elif kind == "nul":
        files[log_path] += "\0"
    assert_rejected(env, evaluate(env), failure)


@pytest.mark.parametrize("mode", ["disabled", "dry_run", "write"])
def test_restore_main_disabled_preview_and_failure_outputs_never_scan(env, mode):
    prepare_restore(env)
    env[2].config.execution_mode = mode
    if mode == "write":
        env[0].execute("opts.config.restore_process_attestation.current.pid = 4243")
    api = restore_main_api(env)
    api.main()
    g = env[0].globals()
    assert g.collector_calls == len(g.writes) == g.file_writes == 0
    assert len(list(g.saved.items())) == 3
    for text in g.saved.values():
        assert "restore_attempted = false" in text and "execution_success = false" in text
        if mode == "write":
            assert "execution_failure_class = restore_process_identity_changed" in text
    if mode == "disabled":
        assert g.reads == 0 and len(g.opened_paths) == 3  # read-only output collision checks


@pytest.mark.parametrize("behavior", [None, "false", "nil", "error", "false_after_write", "no_change"])
def test_restore_request_consumed_even_on_uncertain_write_and_executor_reload(env, behavior):
    prepare_restore(env)
    lua, _, opts = env
    lua.globals().write_behavior = behavior
    result = evaluate(env)
    assert result.restore_request_reserved is result.restore_attempted is True
    assert len(lua.globals().writes) == 1
    # Simulate module reload and even a current value returning to the written bits.
    lua.execute("memory[0x12345000] = pattern(17.75); writes = {}")
    reloaded = lua.execute(EXECUTOR.read_text(encoding="utf-8"))
    assert_rejected(env, reloaded.evaluate(opts), "restore_request_reused")


def test_unexpected_exception_after_restore_write_retains_attempt_evidence(env):
    prepare_restore(env)
    result = evaluate(env, """
        local write = writeFloat
        writeFloat = function(addr, value)
            local ok = write(addr, value)
            readFloat = function() return 12.5 end
            string.unpack = function() error('unexpected packing failure') end
            return ok
        end
    """)
    assert result.execution_failure_class == "executor_exception"
    assert result.restore_attempted is result.write_attempted is result.restore_write_ok is True
    assert result.execution_success is result.restore_readback_ok is False
    assert len(env[0].globals().writes) == 1


def test_restore_arm_and_attestation_are_loaded_without_config_defaults(env):
    prepare_restore(env)
    lua, _, opts = env
    api = runner_api(env)
    lua.globals().loaded_config = opts.config
    lua.execute("""
        io = {open = function() return {close = function() return true end} end}
        dofile = function(path) return loaded_config end
    """)
    cases = lua.table_from([lua.table_from({"session_id": "default-session"})])
    api.apply_config(cases, api.config_path)
    api.restore_config(cases[1])
    parsed = cases[1]
    assert parsed.session_id == opts.config.session_id
    assert parsed.restore_source_case_id == opts.config.restore_source_case_id
    assert parsed.restore_source_session_id == opts.config.restore_source_session_id
    assert parsed.restore_process_attestation.request_id == opts.config.execution_write_request_id


@pytest.mark.parametrize("mode,enabled", [("disabled", False), ("dry_run", False), ("write", True)])
def test_single_with_explicit_restore_source_never_hands_off_to_executor(mode, enabled):
    from test_screening_single_mode import assert_no_execution, runtime

    lua, api, cfg = runtime()
    cfg.execution_mode, cfg.write_enabled = mode, enabled
    cfg.execution_addr_source = "restore_source_batch_execution_addr"
    if mode == "disabled":
        api.main()
    else:
        with pytest.raises(Exception, match="single requires"):
            api.main()
        assert len(lua.globals().captured_runs) == 0
    assert_no_execution(lua)


def test_restore_does_not_access_poisoned_ranking_summary(env):
    prepare_restore(env)
    result = evaluate(env, """
        local poison = {__index = function() error('screening summary must not be accessed') end}
        opts.summary = setmetatable({}, poison)
        opts.rank_guard = setmetatable({}, poison)
    """)
    assert result.execution_success is True


@pytest.mark.parametrize("collision", ["source_batch", "summary", "diff", "log", "unreadable"])
def test_restore_main_rejects_output_collisions_before_memory_access(env, collision):
    prepare_restore(env)
    lua, _, _ = env
    api = restore_main_api(env)
    files = lua.globals().files
    expected = "restore_output_exists"
    if collision == "source_batch":
        lua.execute("os.date = function() return '20261116-000500' end")
        expected = "restore_output_collides_with_source"
    elif collision == "unreadable":
        lua.execute("missing_file_code = 13")
        expected = "restore_output_check_failed"
    else:
        suffix = {"summary": "summary.txt", "diff": "diagnostic_diff.txt",
                  "log": "synthetic-session__synthetic-restore__restore_only.log"}[collision]
        files[f"{LOG_ROOT}\\20261116-000501__{suffix}"] = "preserved previous output"
    before = dict(files.items())
    with pytest.raises(Exception, match=expected):
        api.main()
    g = lua.globals()
    assert len(g.writes) == g.reads == g.evaluation_count == g.collector_calls == 0
    assert not list(g.saved.items())
    assert dict(files.items()) == before


@pytest.mark.parametrize("mutation,failure", [
    ("write_behavior = 'false_after_write'", "write_failed"),
    ("write_behavior = 'number'", "write_failed"),
    ("after_integer_fault = 'nil'", "readback_read_failed"),
    ("after_integer_fault = 'error'", "readback_read_failed"),
    ("after_float_fault = 'error'", "readback_read_failed"),
    ("after_float_override = 13", "readback_mismatch"),
    ("after_float_override = 12.500000001", "readback_mismatch"),
    ("write_behavior = 'no_change'; after_float_override = 12.5", "readback_mismatch"),
])
def test_restore_main_logs_api_and_dual_readback_failures_without_retry(env, mutation, failure):
    prepare_restore(env)
    lua, _, _ = env
    api = restore_main_api(env)
    lua.execute(mutation)
    api.main()
    assert len(lua.globals().writes) == 1
    for text in lua.globals().saved.values():
        assert f"execution_failure_class = {failure}" in text
        assert "restore_attempted = true" in text
        assert "restore_readback_ok = false" in text
        assert "execution_success = false" in text
    assert lua.globals().collector_calls == 0


@pytest.mark.parametrize("field,value,failure", [
    ("old_value_float", "13", "restore_source_value_mismatch"),
    ("old_value_pattern", "0x41500000", "restore_source_value_mismatch"),
    ("rollback_value_pattern", "0x41500000", "restore_source_value_mismatch"),
    ("readback_float", "18", "restore_source_value_mismatch"),
    ("readback_pattern", "0x41900000", "restore_source_value_mismatch"),
    ("execution_addr", "0x12345004", "restore_source_address_mismatch"),
    ("execution_arm_seconds_remaining", "0", "restore_source_arm_invalid"),
    ("execution_write_request_id", "nil", "restore_source_arm_invalid"),
    ("restore_attempted", "true", "restore_source_write_not_successful"),
    ("failure_class", "source_failed", "restore_source_write_not_successful"),
    ("mode", "restore_only", "restore_source_evidence_malformed"),
])
def test_consistently_corrupted_source_evidence_is_rejected(env, field, value, failure):
    prepare_restore(env)
    files = env[0].globals().files
    for path, text in list(files.items()):
        if field == "mode" and path.endswith("summary.txt"):
            text = text.replace(" / stable_no_probe_intersection ---", " / restore_only ---")
        files[path] = re.sub(rf"(?m)^({field}\s*=\s*)[^\r\n]*", lambda m: m[1] + value, text)
    assert_rejected(env, evaluate(env), failure)


def test_unarmed_restore_preview_checks_values_without_consuming_request(env):
    prepare_restore(env)
    result = evaluate(env, """
        opts.config.execution_mode = 'dry_run'
        opts.config.execution_confirm = nil
        opts.config.execution_armed_at_utc = nil
        opts.config.execution_arm_expires_at_utc = nil
    """)
    assert result.execution_preconditions_ok is result.restore_current_value_match is True
    assert result.write_ready is result.restore_request_reserved is False
    assert result.write_readiness_failure_class == "missing_execution_confirm"
    assert len(env[0].globals().writes) == env[0].globals().file_writes == 0


def test_legacy_v3_successful_receipts_remain_supported(env):
    prepare_restore(env)
    files = env[0].globals().files
    for path, text in list(files.items()):
        files[path] = text.replace("guarded_write_v4_restore_only", "guarded_write_v3")
    assert evaluate(env).execution_success is True


def test_restore_main_loads_complete_config_once_and_never_loads_collector(env):
    prepare_restore(env)
    lua, _, opts = env
    lua.globals().synthetic_config = opts.config
    lua.execute("""
        config_loads = 0
        local open = io.open
        io.open = function(path, mode)
            if mode == 'r' then
                assert(path:match('run_case_config.local.lua$'))
                return {close = function() return true end}
            end
            return open(path, mode)
        end
        dofile = function(path)
            assert(path:match('run_case_config.local.lua$'))
            config_loads = config_loads + 1
            return synthetic_config
        end
    """)
    api = restore_main_api(env, load_config=True)
    assert api.cases[1].case_config_loaded is True
    api.main()
    g = lua.globals()
    assert g.config_loads == 1 and g.collector_calls == 0
    assert len(g.writes) == 1 and g.restore_results.execution_success is True
    assert g.restore_summaries[1].session_id == opts.config.session_id


def test_restore_mixed_with_other_cases_is_rejected_before_any_work(env):
    prepare_restore(env)
    lua, _, _ = env
    api = restore_main_api(env)
    api.cases[2] = lua.table_from({"validation_profile": "full", "execution_mode": "disabled"})
    with pytest.raises(Exception, match="restore_only requires exactly one case"):
        api.main()
    g = lua.globals()
    assert len(g.writes) == g.reads == g.evaluation_count == g.collector_calls == 0
    assert not list(g.saved.items())
