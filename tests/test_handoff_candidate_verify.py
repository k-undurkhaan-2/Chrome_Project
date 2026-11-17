"""H2 integration with real Lua 5.4 and synthetic H1 evidence/memory only.

H1 creates fixtures in a virtual filesystem. H2 starts in a separate runtime;
its collector, executor, process discovery and all writes are counted/trapped.
No local config, real log, CE process or target memory is opened by these tests.
"""

import copy
import re
import subprocess

import pytest
from lupa.lua54 import LuaRuntime

from test_single_handoff import (
    BATCH, BATCH_ID, COMPANION, LOG_ROOT, STEM, collection_evidence,
    fields, files, handoff_runtime,
)
from test_screening_single_mode import array, assert_no_execution
from test_screening_truth_isolation import freeze
from test_write_usability import env, prepare_restore, SOURCE_BATCH


VERIFY = BATCH.with_name("mvp0_single_handoff_verify.lua")
NOW = "2026-06-01T12:00:30Z"
VERIFY_CASE = "verify-synthetic-01"
VERIFY_BATCH = "h2-20260601-120030"
OUTPUT = LOG_ROOT + "\\" + VERIFY_BATCH + "__" + VERIFY_CASE + "__handoff_verification.txt"
NAMES = {
    "log": STEM + "__no_probe_A.log",
    "summary": BATCH_ID + "__summary.txt",
    "diagnostic": BATCH_ID + "__diagnostic_diff.txt",
    "companion": COMPANION,
}


@pytest.fixture(scope="module")
def evidence_sets():
    evidence = {}
    for level in ("basic", "debug", "trace"):
        lua, api, cfg = handoff_runtime()
        cfg.diagnostic_level = level
        api.main()
        evidence[level] = files(lua)
        assert len(evidence[level]) == 4
        assert_no_execution(lua)
    return evidence


def request():
    identity = {
        "process_name": "synthetic.exe", "executable": r"C:\Disposable\synthetic.exe",
        "pid": 1234, "started_at_utc": "2026-06-01T10:00:00Z", "scene": "synthetic-scene",
    }
    source = {"batch_id": BATCH_ID, "case_id": "synthetic", "session_id": "synthetic"}
    return {
        "case_id": VERIFY_CASE, "source": source,
        "attestation": {
            "identity_basis": "operator_reconfirmed", "permitted_disposable_environment": True,
            "h1_did_not_measure_identity": True, "source_identity_status": "operator_recorded_at_h1",
            "continuity_confirmed": True, "continuity_basis": "Synthetic external record checked against current context",
            "confirmed_at_utc": "2026-06-01T12:00:00Z", "source_recorded_at_utc": "2026-06-01T11:00:00Z",
            "verification_case_id": VERIFY_CASE,
            "source_batch_id": BATCH_ID, "source_case_id": "synthetic", "source_session_id": "synthetic",
            "requested_process_name": "synthetic.exe", "source": identity, "current": copy.deepcopy(identity),
        },
    }


def setup(evidence_sets, level="basic", *, req=None):
    lua, api, cfg = handoff_runtime(enabled=False)
    cfg.handoff_verify_only = True
    cfg.handoff_verify_request = lua.table_from(request() if req is None else req, recursive=True)
    lua.globals().verify_module = lua.execute(VERIFY.read_text(encoding="utf-8"))
    for path, text in evidence_sets[level].items():
        lua.globals().written_logs[path] = text
    # The expected candidate comes only from the H1 artifact, not an answer key.
    candidate = fields(evidence_sets[level][LOG_ROOT + "\\" + COMPANION])["candidate_address"]
    lua.globals().synthetic_candidate = int(candidate, 16)
    lua.globals().synthetic_now = NOW
    lua.execute(r'''
        candidate_reads = {}; identity_calls = 0; h2_loads = 0
        os.date = function(format)
            if format == '!%Y%m%d-%H%M%S' then return '20260601-120030' end
            assert(format == '!%Y-%m-%dT%H:%M:%SZ')
            return synthetic_now
        end
        dofile = function(path)
            assert(path:match('mvp0_single_handoff_verify%.lua$'), 'unexpected module load')
            h2_loads = h2_loads + 1
            if module_failure then error('synthetic module unavailable') end
            return verify_module
        end
        readInteger = function(addr)
            candidate_reads[#candidate_reads+1] = {'integer', addr}
            assert(addr == synthetic_candidate, 'wrong address')
            return 0x42C80000
        end
        readFloat = function(addr)
            candidate_reads[#candidate_reads+1] = {'float', addr}
            assert(addr == synthetic_candidate, 'wrong address')
            return 100.0
        end
        local function forbidden_identity()
            identity_calls = identity_calls + 1
            error('OS process discovery is forbidden')
        end
        getOpenedProcessID = forbidden_identity; getProcessIDFromProcessName = forbidden_identity
        openProcess = forbidden_identity; getProcesslist = forbidden_identity
        createMemScan = forbidden_identity; createFoundList = forbidden_identity
    ''')
    return lua, api, cfg


def outcome(api):
    result, publication_failure = api.main()
    return result, publication_failure


def assert_readonly(lua, before):
    assert_no_execution(lua)
    g = lua.globals()
    assert len(g.captured_runs) == g.module_loads == len(g.snapshots) == g.rank_calls == 0
    assert g.directory_calls == g.ui_calls == g.identity_calls == 0
    assert {p: files(lua)[p] for p in before} == before
    assert not list(g.directories.items())


def assert_invariants(result):
    assert result.authorization_status == "NOT_AUTHORIZED"
    assert result.handoff_write_ready is result.write_ready is result.write_attempted is False
    assert result.baseline_eligible is result.source_cryptographic_authentication is False
    assert result.process_identity_os_measured is result.semantic_correctness_established is False
    assert result.ownership_established is False
    assert result.memory_write_attempts == 0 and result.independent_review_required is True


def replace_field(text, key, value):
    pattern = rf"(?m)^({re.escape(key)}[ \t]*=[ \t]*)[^\r\n]*"
    replaced, count = re.subn(pattern, lambda m: m[1] + value, text)
    assert count > 0, key
    return replaced


def mutate(lua, artifact, key, value):
    path = LOG_ROOT + "\\" + NAMES[artifact]
    lua.globals().written_logs[path] = replace_field(files(lua)[path], key, value)


def sync_log_size(lua):
    size = len(files(lua)[LOG_ROOT + "\\" + NAMES["log"]].encode())
    for artifact, key in (("companion", "source_log_size_bytes"), ("summary", "log_size_bytes"), ("diagnostic", "log_size_bytes")):
        mutate(lua, artifact, key, str(size))


@pytest.mark.parametrize("level", ["basic", "debug", "trace"])
def test_real_h1_artifact_set_has_exact_source_binding_and_two_readonly_observations(evidence_sets, level):
    lua, api, _ = setup(evidence_sets, level)
    before = files(lua)
    result, failure = outcome(api)
    assert result.verification_status == "VALUE_CONSISTENT_NOT_AUTHORIZED", result.failure_class
    assert failure is None and result.candidate_value_consistent is True
    assert result.operator_attestation_status == result.process_identity_basis == "operator_reconfirmed"
    assert result.source_process_identity_status == "operator_recorded_at_h1_not_measured"
    assert result.source_consistency_status == "consistent_local_evidence_only"
    assert result.expected_search_pattern == result.observed_integer_pattern == result.observed_float_pattern == "0x42C80000"
    assert result.expected_search_float == result.observed_float == 100
    assert result.candidate_address == fields(before[LOG_ROOT + "\\" + COMPANION])["candidate_address"]
    reads = array(lua.globals().candidate_reads)
    assert [array(row) for row in reads] == [["integer", int(result.candidate_address, 16)], ["float", int(result.candidate_address, 16)]]
    assert result.memory_read_attempts == 2
    opens = [array(row) for row in array(lua.globals().file_operations) if row[1] == "open"]
    assert {row[1] for row in opens if row[1] in before} == set(before)
    assert all(row[2] == "rb" for row in opens if row[1] in before)
    assert len([row for row in opens if row[1] in before]) == 4
    report = fields(files(lua)[OUTPUT])
    assert report["verification_kind"] == "readonly_candidate_verification"
    assert "WRITE/RESTORE receipt" in report["warning"]
    assert not re.search(r"synthetic\.exe|Disposable|1234|execution_confirm|write_request_id|known_true", files(lua)[OUTPUT])
    assert_invariants(result)
    assert_readonly(lua, before)


@pytest.mark.parametrize("artifact", list(NAMES))
@pytest.mark.parametrize("fault", ["missing", "check", "read", "close", "exception", "empty", "oversized"])
def test_missing_unreadable_or_oversized_evidence_fails_before_memory(evidence_sets, artifact, fault):
    lua, api, _ = setup(evidence_sets)
    path = LOG_ROOT + "\\" + NAMES[artifact]
    if fault == "missing": lua.globals().written_logs[path] = None
    elif fault == "empty": lua.globals().written_logs[path] = ""
    elif fault == "oversized": lua.globals().written_logs[path] = "X" * (2 * 1024 * 1024 + 1)
    else: lua.globals().file_fault, lua.globals().fault_suffix = fault, NAMES[artifact]
    before = files(lua)
    result, failure = outcome(api)
    assert result.verification_status == "REJECTED" and result.failure_class.startswith("source_")
    assert result.candidate_value_consistent == "not_evaluated"
    assert result.memory_read_attempts == len(lua.globals().candidate_reads) == 0
    assert failure is None
    assert_invariants(result)
    assert_readonly(lua, before)


@pytest.mark.parametrize("artifact,key,value", [
    ("companion", "source_batch_id", "other"), ("companion", "source_case_id", "other"),
    ("companion", "source_session_id", "other"), ("companion", "source_log_filename", "outside.log"),
    ("companion", "source_log_size_bytes", "1"), ("companion", "best_score", "40"),
    ("companion", "second_score", "26"), ("companion", "score_gap", "13"),
    ("companion", "candidate_count", "99"), ("companion", "candidate_rank", "2"),
    ("companion", "candidate_address", "0x10000230"), ("companion", "candidate_address", "0x010000228"),
    ("companion", "candidate_address", "0X10000228"), ("companion", "candidate_address", "0xabcdef"),
    ("companion", "candidate_address", "0x0"), ("companion", "candidate_address", "0x20000000000000"),
    ("companion", "confidence", "CERTAIN"), ("companion", "recommendation", "WRITE"),
    ("companion", "best_score", "nan"), ("companion", "best_score", "1e999"),
    ("companion", "score_gap", "inf"), ("companion", "search_target_float", "nan"),
    ("companion", "search_target_float", "1e+100"), ("companion", "search_target_float", "99"),
    ("companion", "search_target_pattern", "0x7FC00000"), ("companion", "search_target_pattern", "0x7F800000"),
    ("companion", "search_target_pattern", "0x42c80000"), ("companion", "search_target_pattern", "0x42C80001"),
    ("companion", "handoff_schema_version", "2"), ("companion", "handoff_kind", "restore_receipt"),
    ("companion", "authorization_status", "AUTHORIZED"), ("companion", "handoff_write_ready", "true"),
    ("companion", "write_attempted", "true"), ("companion", "baseline_eligible", "true"),
    ("companion", "operator_process_identity_verified", "true"), ("companion", "independent_review_required", "false"),
    ("companion", "authentication_note", "signed"), ("companion", "warning", "safe to write"),
    ("summary", "batch_id", "other"), ("diagnostic", "batch_id", "other"),
    ("summary", "case_id", "other"), ("log", "session_id", "other"),
    ("summary", "log_path", r"C:\elsewhere.log"), ("diagnostic", "output_dir", r"C:\elsewhere"),
    ("summary", "best_score", "42"), ("log", "score_gap", "nan"),
    ("summary", "confidence", "LOW"), ("diagnostic", "best_candidate", "0x10000230"),
    ("log", "best_candidate", "0x10000230"), ("summary", "log_size_bytes", "1"),
    ("diagnostic", "log_size_bytes", "1"), ("summary", "run_valid", "false"),
    ("log", "failure_class", "collector_error"), ("diagnostic", "error", "truncated"),
    ("summary", "write_ready", "true"), ("diagnostic", "write_attempted", "true"),
    ("log", "execution_mode", "write"), ("summary", "execution_arm_valid", "true"),
    ("summary", "target_value_float", "99"), ("diagnostic", "target_value_pattern", "0x00000000"),
    ("log", "selected_count", "99"), ("diagnostic", "raw_count", "1"),
    ("log", "recommendation", "ACCEPT"), ("summary", "recommendation", "ACCEPT"),
    ("summary", "execution_write_request_id", "forged-arm"), ("diagnostic", "write_method", "bytes"),
    ("summary", "single_handoff_status", "PUBLISHED_NOT_AUTHORIZED"),
    ("diagnostic", "single_handoff_status", "REJECTED"),
    ("summary", "single_source_log_filename", "other.log"), ("log", "diagnostic_level", "invalid"),
])
def test_tampered_companion_or_original_reports_are_rejected(evidence_sets, artifact, key, value):
    lua, api, _ = setup(evidence_sets)
    mutate(lua, artifact, key, value)
    if artifact == "log": sync_log_size(lua)
    before = files(lua)
    result, _ = outcome(api)
    assert result.verification_status == "REJECTED", (artifact, key, value)
    assert result.candidate_value_consistent == "not_evaluated"
    assert len(lua.globals().candidate_reads) == 0
    assert_invariants(result)
    assert_readonly(lua, before)


@pytest.mark.parametrize("artifact", list(NAMES))
@pytest.mark.parametrize("damage", ["duplicate", "lf", "bare_cr", "nul", "truncated", "missing_field", "collision"])
def test_ambiguous_and_malformed_evidence_is_rejected(evidence_sets, artifact, damage):
    lua, api, _ = setup(evidence_sets)
    path = LOG_ROOT + "\\" + NAMES[artifact]
    text = files(lua)[path]
    if damage == "duplicate":
        line = next(line for line in text.split("\r\n") if "=" in line and not line.startswith("==="))
        text = text.replace(line + "\r\n", line + "\r\n" + line + "\r\n", 1)
    elif damage == "lf": text = text.replace("\r\n", "\n")
    elif damage == "bare_cr": text = text.replace("\r\n", "\r", 1)
    elif damage == "nul": text += "\0"
    elif damage == "truncated": text = text[:len(text)//2]
    elif damage == "missing_field":
        key = {"companion":"source_log_size_bytes", "log":"run_valid", "summary":"best_score", "diagnostic":"log_size_bytes"}[artifact]
        text = re.sub(rf"(?m)^{key}[^\r\n]*\r\n", "", text)
    else: text += "\r\n--- collision / no_probe_A ---\r\ncase_id = other\r\n"
    lua.globals().written_logs[path] = text
    if artifact == "log": sync_log_size(lua)
    before = files(lua)
    result, _ = outcome(api)
    assert result.verification_status == "REJECTED"
    assert result.memory_read_attempts == 0
    assert_readonly(lua, before)


@pytest.mark.parametrize("key", ["batch_id", "case_id", "session_id"])
@pytest.mark.parametrize("value", ["../outside", "a/b", "a\\b", "a__b", "a_", "nil", "", "x"*81, "中文", "D:root"])
def test_source_tokens_never_become_paths_or_fallback_to_collection(evidence_sets, key, value):
    req = request(); req["source"][key] = value
    lua, api, _ = setup(evidence_sets, req=req)
    before = files(lua)
    result, failure = outcome(api)
    assert result.failure_class == "source_token_invalid"
    assert failure == "verification_output_identity_invalid"
    assert len(lua.globals().file_operations) == len(lua.globals().candidate_reads) == 0
    assert files(lua) == before
    assert_readonly(lua, before)


@pytest.mark.parametrize("mutation", [
    "r.attestation = nil", "r.attestation.identity_basis = 'os_measured'",
    "r.attestation.h1_did_not_measure_identity = false", "r.attestation.os_measured = true",
    "r.attestation.source_identity_status = 'unknown'", "r.attestation.source = nil",
    "r.attestation.permitted_disposable_environment = false", "r.attestation.continuity_confirmed = false",
    "r.attestation.continuity_basis = ''", "r.attestation.confirmed_at_utc = '2026-06-01T11:58:29Z'",
    "r.attestation.confirmed_at_utc = '2026-06-01T12:00:31Z'", "r.attestation.confirmed_at_utc = '2026-02-30T12:00:00Z'",
    "r.attestation.confirmed_at_utc = '2026-06-01T12:60:00Z'", "r.attestation.confirmed_at_utc = '2026-06-01T12:00:00+00:00'",
    "r.attestation.confirmed_at_utc = nil", "r.attestation.source_recorded_at_utc = nil",
    "r.attestation.source_recorded_at_utc = '2026-06-01T09:00:00Z'",
    "r.attestation.source_recorded_at_utc = '2026-06-01T13:00:00Z'",
    "r.attestation.source_batch_id = 'other'", "r.attestation.source_case_id = 'other'",
    "r.attestation.source_session_id = 'other'", "r.attestation.verification_case_id = 'other'",
    "r.attestation.requested_process_name = 'other.exe'", "r.attestation.current.pid = 1235",
    "r.attestation.current.started_at_utc = '2026-06-01T10:01:00Z'",
    "r.attestation.current.executable = [[C:\\Elsewhere\\synthetic.exe]]",
    "r.attestation.current.scene = 'different-scene'", "r.attestation.current.process_name = 'other.exe'",
    "r.attestation.current.pid = nil", "r.attestation.current.pid = 1.5",
    "r.attestation.current.pid = -1", "r.attestation.current.executable = 'relative.exe'",
    "r.attestation.current.executable = [[C:\\Disposable\\..\\synthetic.exe]]",
    "r.attestation.current.started_at_utc = 'invalid'", "r.attestation.current.scene = nil",
])
def test_operator_reconfirmation_is_complete_fresh_bound_and_explicitly_non_measured(evidence_sets, mutation):
    lua, api, cfg = setup(evidence_sets)
    lua.globals().r = cfg.handoff_verify_request
    lua.execute(mutation)
    before = files(lua)
    result, _ = outcome(api)
    assert result.verification_status == "REJECTED", mutation
    assert result.operator_attestation_status == "rejected"
    assert result.candidate_value_consistent == "not_evaluated"
    assert len(lua.globals().candidate_reads) == 0
    if "source_identity_status" in mutation or "source = nil" in mutation:
        assert result.failure_class == "source_process_identity_unavailable"
        assert result.source_process_identity_status == "unavailable"
    assert_invariants(result)
    assert_readonly(lua, before)


@pytest.mark.parametrize("mutation,failure,reads", [
    ("readInteger = nil", "candidate_read_api_unavailable", 0),
    ("readFloat = nil", "candidate_read_api_unavailable", 0),
    ("readInteger = function() return nil end", "candidate_integer_read_failed", 1),
    ("readInteger = function() error('private failure detail') end", "candidate_integer_read_failed", 1),
    ("readInteger = function() return 1.5 end", "candidate_integer_read_failed", 1),
    ("readInteger = function() return '1120403456' end", "candidate_integer_read_failed", 1),
    ("readInteger = function() return 0x100000000 end", "candidate_integer_read_failed", 1),
    ("readInteger = function() return -0x80000001 end", "candidate_integer_read_failed", 1),
    ("readInteger = function() return 0/0 end", "candidate_integer_read_failed", 1),
    ("readFloat = function() return nil end", "candidate_float_read_failed", 2),
    ("readFloat = function() error('private failure detail') end", "candidate_float_read_failed", 2),
    ("readFloat = function() return 0/0 end", "candidate_float_read_failed", 2),
    ("readFloat = function() return 1/0 end", "candidate_float_read_failed", 2),
    ("readFloat = function() return -1/0 end", "candidate_float_read_failed", 2),
    ("readFloat = function() return 1e100 end", "candidate_float_read_failed", 2),
    ("readFloat = function() return 99 end", "candidate_observation_inconsistent", 2),
    ("readFloat = function() return 100.000000001 end", "candidate_observation_inconsistent", 2),
    ("readInteger = function() return 0x42C60000 end; readFloat = function() return 99 end", "candidate_value_mismatch", 2),
    ("synthetic_candidate = synthetic_candidate + 8", "candidate_integer_read_failed", 1),
])
def test_fresh_read_failures_never_retry_scan_or_write(evidence_sets, mutation, failure, reads):
    lua, api, _ = setup(evidence_sets)
    lua.execute(mutation)
    before = files(lua)
    result, _ = outcome(api)
    assert result.failure_class == failure
    assert result.memory_read_attempts == reads
    assert result.candidate_value_consistent == ("not_evaluated" if reads == 0 else False)
    assert "private failure detail" not in files(lua)[OUTPUT]
    assert_invariants(result)
    assert_readonly(lua, before)


def test_signed_pattern_is_normalized_and_compared_exactly(evidence_sets):
    lua, api, _ = setup(evidence_sets)
    for artifact in NAMES:
        mutate(lua, artifact, "search_target_float" if artifact == "companion" else "target_value_float", "-100")
        mutate(lua, artifact, "search_target_pattern" if artifact == "companion" else "target_value_pattern", "0xC2C80000")
    sync_log_size(lua)
    lua.execute("readInteger = function() return -1027080192 end; readFloat = function() return -100.0 end")
    result, _ = outcome(api)
    assert result.candidate_value_consistent is True, result.failure_class
    assert result.observed_integer_pattern == "0xC2C80000"
    assert_invariants(result)


@pytest.mark.parametrize("missing", ["float", "pattern", "both"])
def test_expected_search_input_may_use_one_coherent_representation(evidence_sets, missing):
    lua, api, _ = setup(evidence_sets)
    for suffix in (("float", "pattern") if missing == "both" else (missing,)):
        for artifact in NAMES:
            mutate(lua, artifact, ("search_target_" if artifact == "companion" else "target_value_") + suffix, "nil")
    sync_log_size(lua)
    result, _ = outcome(api)
    if missing == "both":
        assert result.failure_class == "source_search_value_missing"
        assert result.memory_read_attempts == 0
    else:
        assert result.candidate_value_consistent is True, result.failure_class


@pytest.mark.parametrize("truth", [None, 1, 0x10000228, 0x7FFFFFFF])
def test_high_rank_accept_and_truth_injection_never_supply_authorization(evidence_sets, truth):
    lua, api, cfg = setup(evidence_sets)
    cfg.known_true_addr = truth
    cfg.target_value_addr = truth
    cfg.target_value_float = 999
    cfg.target_value_pattern = 0x4479C000
    mutate(lua, "companion", "recommendation", "ACCEPT")
    before = files(lua)
    result, _ = outcome(api)
    assert result.candidate_value_consistent is True, result.failure_class
    assert result.expected_search_pattern == "0x42C80000"
    assert_invariants(result)
    assert_readonly(lua, before)


@pytest.mark.parametrize("mutation", [
    "cfg.validation_profile = 'full'", "cfg.validation_profile = 'quick'",
    "cfg.execution_mode = 'dry_run'", "cfg.execution_mode = 'write'",
    "cfg.write_enabled = true", "cfg.write_enabled = 'false'", "cfg.single_handoff_enabled = true",
    "cfg.execution_addr_source = 'restore_source_batch_execution_addr'",
    "cfg.restore_execution_addr = 0x1234", "cfg.restore_source_batch_id = 'other'",
    "cfg.execution_confirm = 'WRITE_ONCE'", "cfg.execution_write_request_id = 'some-arm'",
    "cfg.execution_armed_at_utc = '2026-06-01T12:00:00Z'", "cfg.write_value_float = 999",
])
def test_mixed_modes_or_arm_fields_are_rejected_before_evidence_and_memory(evidence_sets, mutation):
    lua, api, cfg = setup(evidence_sets)
    lua.globals().cfg = cfg
    lua.execute(mutation)
    before = files(lua)
    result, _ = outcome(api)
    assert result.failure_class in ("verification_requires_single_readonly", "verification_mixed_operation")
    assert result.memory_read_attempts == 0 and result.candidate_value_consistent == "not_evaluated"
    assert not any(row[1] == "open" and row[2] in before for row in array(lua.globals().file_operations))
    assert_readonly(lua, before)


def test_multiple_cases_cannot_enter_h2_or_collect(evidence_sets):
    lua, api, cfg = setup(evidence_sets)
    api.cases[2] = cfg
    before = files(lua)
    with pytest.raises(Exception, match="exactly_one_case"):
        api.main()
    assert len(lua.globals().candidate_reads) == len(lua.globals().file_operations) == 0
    assert_readonly(lua, before)


@pytest.mark.parametrize("mutation", [
    "r.root = [[C:\\other]]", "r.source.root = [[C:\\other]]", "r.candidate_address = '0x1234'",
    "r.known_true_addr = 0x1234", "r.source.case_id = nil", "r.case_id = 'synthetic'", "r.case_id = 'SYNTHETIC'",
    "r.case_id = '../out'", "r.case_id = 'a__b'", "r[2] = {}",
])
def test_request_cannot_supply_address_path_or_multiple_cases(evidence_sets, mutation):
    lua, api, cfg = setup(evidence_sets)
    lua.globals().r = cfg.handoff_verify_request
    lua.execute(mutation)
    before = files(lua)
    result, _ = outcome(api)
    assert result.verification_status == "REJECTED"
    assert len(lua.globals().candidate_reads) == len(lua.globals().file_operations) == 0
    assert_readonly(lua, before)


@pytest.mark.parametrize("value", [None, False, True, "true", "false", 0, 1, {}])
def test_opt_in_is_a_literal_boolean_in_the_single_existing_config_load(value):
    lua = LuaRuntime(register_eval=False, register_builtins=False)
    lua.globals().synthetic_config = lua.table_from({
        "validation_profile": "single", "execution_mode": "disabled", "write_enabled": False,
        "handoff_verify_only": value,
    }, recursive=True)
    lua.execute(r'''
        python = nil; loadfile = nil; package = nil; require = nil; config_loads = 0
        io = {open = function(path, mode)
            assert(mode == 'r' and path:match('run_case_config%.local%.lua$'))
            return {close = function() return true end}
        end}
        dofile = function(path)
            assert(path:match('run_case_config%.local%.lua$'))
            config_loads = config_loads + 1; return synthetic_config
        end
    ''')
    source, tail = BATCH.read_text(encoding="utf-8").rsplit("\nmain()", 1)
    assert not tail.strip()
    if value is not None and type(value) is not bool:
        with pytest.raises(Exception, match="handoff_verify_only must be a boolean"):
            lua.execute(source + "\nreturn RUN_CASES[1]")
    else:
        cfg = lua.execute(source + "\nreturn RUN_CASES[1]")
        assert cfg.handoff_verify_only is (value is True)
    assert lua.globals().config_loads == 1


@pytest.mark.parametrize("profile", ["single", "full", "quick"])
@pytest.mark.parametrize("h1", [False, True])
def test_disabled_h2_preserves_exact_head_outputs_reads_and_collection(evidence_sets, profile, h1):
    published = subprocess.check_output(
        ["git", "show", "140043918ed302b573b4c40b7334ebc630ab399f:src/execute_module-v5.2.0_batch.lua"],
        cwd=BATCH.parent.parent, text=True, encoding="utf-8",
    )
    states = []
    for source in (published, BATCH.read_text(encoding="utf-8")):
        lua, api, cfg = handoff_runtime(enabled=h1, profile=profile, batch_source=source)
        if source != published: assert cfg.handoff_verify_only is False
        api.main()
        g = lua.globals()
        states.append(freeze(collection_evidence({
            "files":g.written_logs, "reads":g.collection_reads, "runs":g.captured_runs,
            "summaries":g.captured_summaries, "console":g.console_lines, "file_operations":g.file_operations,
        })))
    assert states[0] == states[1]


@pytest.mark.parametrize("fault", ["check", "reserve", "open", "write", "close", "read", "corrupt", "rename", "exception", "race", "exists"])
def test_h2_publication_errors_are_explicit_and_preserve_source_and_other_outputs(evidence_sets, fault):
    lua, api, _ = setup(evidence_sets)
    if fault == "exists": lua.globals().written_logs[OUTPUT] = "earlier verification"
    else: lua.globals().file_fault, lua.globals().fault_suffix = fault, "__handoff_verification.txt"
    before = files(lua)
    result, failure = outcome(api)
    assert failure is not None
    assert_invariants(result)
    if fault == "race": assert files(lua)[OUTPUT] == "existing concurrent evidence"
    elif fault == "exists": assert files(lua)[OUTPUT] == "earlier verification"
    else: assert OUTPUT not in files(lua)
    assert_readonly(lua, before)


def test_published_report_cannot_be_consumed_as_restore_evidence(evidence_sets, env):
    source_lua, api, _ = setup(evidence_sets)
    outcome(api)
    artifact = files(source_lua)[OUTPUT]
    prepare_restore(env)
    lua, executor, opts = env
    lua.globals().files[LOG_ROOT + "\\" + SOURCE_BATCH + "__summary.txt"] = artifact
    result = executor.evaluate(opts)
    assert result.execution_failure_class == "restore_source_evidence_malformed"
    assert lua.globals().reads == len(lua.globals().writes) == 0


def test_module_unavailable_never_falls_back(evidence_sets):
    lua, api, _ = setup(evidence_sets)
    lua.globals().module_failure = True
    before = files(lua)
    with pytest.raises(Exception, match="handoff_verify_module_unavailable"):
        api.main()
    assert len(lua.globals().candidate_reads) == len(lua.globals().file_operations) == 0
    assert_readonly(lua, before)


@pytest.mark.parametrize("original,replacement", [
    ("Best candidate: 0x10000228", "Best candidate: 0x10000230"),
    ("Best score: 39", "Best score: 40"),
    ("Target value pattern: 0x42C80000", "Target value pattern: 0x42C60000"),
    ("Target value float: 100.0", "Target value float: 99.0"),
    ("Confidence: HIGH", "Confidence: LOW"),
    ("Recommendation: REVIEW", "Recommendation: ACCEPT"),
    ("Recommended score     : 39", "Recommended score     : 40"),
    ("--- Candidate #2 ---", "--- Candidate #1 ---"),
    ("rank_position = 1\n", "rank_position = 2\n"),
    ("value_addr = 0x10000228\n", "value_addr = 0x10000228\nvalue_addr = 0x10000228\n"),
])
def test_trace_candidate_observations_cannot_conflict_with_companion(evidence_sets, original, replacement):
    lua, api, _ = setup(evidence_sets, "trace")
    path = LOG_ROOT + "\\" + NAMES["log"]
    content = files(lua)[path]
    assert original in content
    lua.globals().written_logs[path] = content.replace(original, replacement, 1)
    sync_log_size(lua)
    before = files(lua)
    result, _ = outcome(api)
    assert result.failure_class == "source_trace_conflict"
    assert result.memory_read_attempts == 0
    assert_readonly(lua, before)


def test_pending_summary_and_reservation_never_substitute_for_published_companion(evidence_sets):
    lua, api, _ = setup(evidence_sets)
    path = LOG_ROOT + "\\" + COMPANION
    lua.globals().written_logs[path + ".pending\\content.tmp"] = files(lua)[path]
    lua.globals().written_logs[path] = None
    before = files(lua)
    result, _ = outcome(api)
    assert result.failure_class == "source_missing"
    assert result.candidate_value_consistent == "not_evaluated"
    assert result.memory_read_attempts == 0
    assert_readonly(lua, before)


@pytest.mark.parametrize("value", ["true", "false", 0, 1])
def test_runtime_boolean_guard_prevents_implicit_collection(evidence_sets, value):
    lua, api, cfg = setup(evidence_sets)
    cfg.handoff_verify_only = value
    before = files(lua)
    with pytest.raises(Exception, match="handoff_verify_only must be a boolean"):
        api.main()
    assert len(lua.globals().file_operations) == len(lua.globals().candidate_reads) == 0
    assert_readonly(lua, before)


@pytest.mark.parametrize("mutation", [
    {"modes": ["no_probe_A"]}, {"write_enabled": "false"}, {"validation_profile": "SINGLE"},
    {"execution_mode": None}, {"restore_process_attestation": {}}, {"execution_confirm": ""},
])
def test_raw_config_cannot_hide_mixed_or_nonliteral_settings(evidence_sets, mutation):
    lua, _, cfg = setup(evidence_sets)
    raw = {"validation_profile": "single", "execution_mode": "disabled", "write_enabled": False} | mutation
    result = lua.globals().verify_module.run(cfg, lua.table_from(raw, recursive=True), lua.table_from({"batch_id": VERIFY_BATCH}))
    assert result.failure_class == "verification_mixed_operation"
    assert result.memory_read_attempts == len(lua.globals().candidate_reads) == 0


def test_pure_verifier_uses_only_injected_sources_clock_and_two_read_apis(evidence_sets):
    lua, _, cfg = setup(evidence_sets)
    deps = lua.eval(r'''{
        batch_id = 'h2-20260601-120030', now_utc = function() return synthetic_now end,
        read_source = function(name, limit)
            local text = assert(written_logs[ [[D:\armedforces.io-v2\log\auto_output\]] .. name])
            assert(#text <= limit); return text
        end,
        readInteger = readInteger, readFloat = readFloat,
    }''')
    before = files(lua)
    lua.execute("io = nil; os = nil; dofile = nil; package = nil; require = nil")
    result = lua.globals().verify_module.run(cfg, None, deps)
    assert result.candidate_value_consistent is True, result.failure_class
    assert_invariants(result)
    assert files(lua) == before
    assert_readonly(lua, before)


@pytest.mark.parametrize("timestamp,success", [
    ("2026-06-01T11:58:30Z", True), ("2026-06-01T11:58:29Z", False),
    ("2026-06-01T12:00:30Z", True), ("2026-06-01T12:00:31Z", False),
    ("2026-06-01T12:00:60Z", False),
])
def test_confirmation_window_has_exact_utc_boundaries(evidence_sets, timestamp, success):
    req = request(); req["attestation"]["confirmed_at_utc"] = timestamp
    lua, api, _ = setup(evidence_sets, req=req)
    result, _ = outcome(api)
    assert (result.candidate_value_consistent is True) is success
    assert result.memory_read_attempts == (2 if success else 0)


def test_candidate_address_can_change_only_with_complete_consistent_source_evidence(evidence_sets):
    lua, api, cfg = setup(evidence_sets)
    alternate = "0x10002028"
    for artifact, key in (("companion", "candidate_address"), ("log", "best_candidate"),
                          ("summary", "best_candidate"), ("diagnostic", "best_candidate")):
        mutate(lua, artifact, key, alternate)
    sync_log_size(lua)
    cfg.known_true_addr = 0x123456
    lua.globals().synthetic_candidate = int(alternate, 16)
    result, _ = outcome(api)
    assert result.candidate_value_consistent is True, result.failure_class
    assert result.candidate_address == alternate
    assert all(row[2] == int(alternate, 16) for row in array(lua.globals().candidate_reads))
    assert_invariants(result)


def test_truncated_trace_tail_is_rejected_even_if_declared_byte_sizes_are_changed(evidence_sets):
    lua, api, _ = setup(evidence_sets, "trace")
    path = LOG_ROOT + "\\" + NAMES["log"]
    content = files(lua)[path]
    start = content.rindex("negative = ")
    end = content.index("\r\n=== single_detect_only ===", start)
    lua.globals().written_logs[path] = content[:start] + content[end:]
    sync_log_size(lua)
    before = files(lua)
    result, _ = outcome(api)
    assert result.failure_class == "source_trace_conflict"
    assert result.memory_read_attempts == 0
    assert_readonly(lua, before)
