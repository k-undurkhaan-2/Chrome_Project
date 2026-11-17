"""H3-A1 uses real Lua 5.4 and generated, in-memory Verify.run/render reports.

H1/H2 fixture generation and executor rejection checks have separate runtimes
with table-backed files/memory. The admission runtime poisons ALL external APIs.
These tests cannot qualify CE attachment, OS identity, atomic memory reads,
source authenticity, owner approval, live writing or independent recovery.
"""

import hashlib
from pathlib import Path
import re

import pytest
from lupa.lua54 import LuaRuntime

from test_handoff_candidate_verify import (
    NAMES, OUTPUT, evidence_sets, mutate, request, setup, sync_log_size,
)
from test_single_handoff import LOG_ROOT, files
from test_write_usability import SOURCE_BATCH, env, prepare_restore


ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "src/mvp0_handoff_write_admission.lua"
VERIFY = ROOT / "src/mvp0_single_handoff_verify.lua"
REVIEWABLE = "SOURCE_REVIEWABLE_NOT_AUTHORIZED"
CONTEXT_KEYS = (
    "review_record_id", "h2_report_sha256", "h1_companion_sha256", "h1_log_sha256",
    "h1_summary_sha256", "h1_diagnostic_sha256",
)
# Read the real producer's field inventory; no fabricated success schema.
H2_FIELDS = re.findall(
    r'"([a-z_]+)"', VERIFY.read_text(encoding="utf-8").split("local RESULT_FIELDS = {", 1)[1].split("}", 1)[0],
)


def fields(text):
    assert text.endswith("\r\n")
    lines = text[:-2].split("\r\n")
    result = dict(line.split("=", 1) for line in lines)
    assert len(result) == len(lines)
    return result


def replace(text, key, value):
    lines = text[:-2].split("\r\n")
    assert sum(line.startswith(key + "=") for line in lines) == 1
    return "\r\n".join(key + "=" + value if line.startswith(key + "=") else line for line in lines) + "\r\n"


def generated_report(evidence, *, level="basic", bits=None, address=None, times=None):
    """Let the unchanged H2 verifier produce success, including edge Float32s.

    Variant H1 fixtures keep every synthetic source declaration coherent. H2
    must reconcile them and perform its two mocked reads before rendering.
    """
    req = request()
    if times:
        confirmed, observed = times
        req["attestation"]["confirmed_at_utc"] = confirmed
        req["attestation"]["source_recorded_at_utc"] = confirmed
        for key in ("source", "current"):
            req["attestation"][key]["started_at_utc"] = confirmed
    lua, api, _ = setup(evidence, level, req=req)
    if times:
        lua.globals().synthetic_now = observed
    if bits is not None:
        assert level == "basic"
        lua.globals().test_bits = bits
        lua.execute("test_value = string.unpack('<f', string.pack('<I4', test_bits))")
        exact = lua.eval("string.format('%.17g', test_value)")
        legacy = lua.eval("tostring(test_value)")
        for artifact in NAMES:
            companion = artifact == "companion"
            prefix = "search_target_" if companion else "target_value_"
            mutate(lua, artifact, prefix + "float", exact if companion else legacy)
            mutate(lua, artifact, prefix + "pattern", f"0x{bits:08X}" if companion else f"0x{bits:X}")
        lua.execute("""
            readInteger = function(addr)
                assert(addr == synthetic_candidate)
                candidate_reads[#candidate_reads+1] = {'integer', addr}
                return test_bits >= 0x80000000 and test_bits - 0x100000000 or test_bits
            end
            readFloat = function(addr)
                assert(addr == synthetic_candidate)
                candidate_reads[#candidate_reads+1] = {'float', addr}
                return test_value
            end
        """)
    if address is not None:
        assert level == "basic"
        for artifact in NAMES:
            mutate(lua, artifact, "candidate_address" if artifact == "companion" else "best_candidate", address)
        lua.globals().synthetic_candidate = int(address, 16)
    if bits is not None or address is not None:
        sync_log_size(lua)
    result, publication_failure = api.main()
    assert publication_failure is None
    assert result.verification_status == "VALUE_CONSISTENT_NOT_AUTHORIZED", result.failure_class
    assert result.memory_read_attempts == len(lua.globals().candidate_reads) == 2
    assert result.memory_write_attempts == lua.globals().write_calls == 0
    text = lua.globals().verify_module.render(result)
    assert files(lua)[OUTPUT] == text
    assert list(fields(text)) == H2_FIELDS
    return text


@pytest.fixture(scope="module")
def reports(evidence_sets):
    return {level: generated_report(evidence_sets, level=level) for level in ("basic", "debug", "trace")}


@pytest.fixture
def admission():
    lua = LuaRuntime(register_eval=False, register_builtins=False)
    assert lua.eval("_VERSION") == "Lua 5.4"
    load_module = lua.eval("load")
    lua.execute("""
        python = nil; forbidden_calls = 0
        function forbidden()
            forbidden_calls = forbidden_calls + 1
            error('private external exception must never escape')
        end
        for _, key in ipairs({'readInteger', 'readFloat', 'readBytes', 'readDouble',
            'writeInteger', 'writeFloat', 'writeBytes', 'writeDouble', 'dofile', 'loadfile',
            'load', 'require', 'print', 'getCurrentMemscan', 'createMemScan', 'createFoundList',
            'getProcessIDFromProcessName', 'getOpenedProcessID', 'getProcesslist', 'openProcess',
            'getAddress', 'getLuaEngine', 'read_source', 'now_utc', 'execute', 'restore'}) do
            _G[key] = forbidden
        end
        for _, key in ipairs({'io', 'os', 'package', 'MVP0FoundList', 'MVP0',
            'MVP0ValueExecutor', 'Handoff', 'Verify', 'MVP0SingleHandoff', 'MVP0SingleHandoffVerify'}) do
            _G[key] = setmetatable({}, {__index=forbidden, __newindex=forbidden, __call=forbidden})
        end
    """)
    # Lupa looks up host debug.traceback before lua_pcall; a throwing __index
    # there panics outside its protected call. Keep host traceback intact and
    # poison debug only in the module's environment, including its _G alias.
    module_env = lua.execute("""
        local env = {}
        for key, value in pairs(_G) do env[key] = value end
        env._G = env
        env.debug = setmetatable({}, {__index=forbidden, __newindex=forbidden, __call=forbidden})
        return env
    """)
    api = load_module(MODULE.read_text(encoding="utf-8"), "@" + str(MODULE), "t", module_env)()
    yield lua, api
    assert lua.globals().forbidden_calls == 0


def assert_safe(record):
    assert record["authorization_status"] == "NOT_AUTHORIZED"
    for key in ("write_ready", "handoff_write_ready", "write_attempted", "process_identity_os_measured",
                "source_cryptographic_authentication", "semantic_correctness_established", "ownership_established",
                "baseline_eligible", "review_context_binding_verified"):
        assert record[key] == "false", key
    assert record["independent_review_required"] == "true"
    assert record["memory_write_attempts"] == record["memory_read_attempts"] == "0"
    assert record["current_target_freshness"] == "not_evaluated"
    assert record["source_temporal_scope"] == "historical_observation_only"
    assert record["next_action"] == "separate_owner_review_required"
    assert not any(key.startswith(("execution_", "restore_", "known_true", "rank_")) for key in record)
    assert not {"write_enabled", "write_value_float", "write_value_pattern", "rollback_available"} & record.keys()


def rejected(admission, text, failure=None, context=None):
    _, api = admission
    result = api.evaluate(text, context)
    rendered = api.render(result)
    record = fields(rendered)
    assert_safe(record)
    assert result.review_status == record["review_status"] == "REJECTED"
    assert result.failure_class and record["failure_class"] != "nil"
    if failure:
        assert result.failure_class == failure
    for key in ("source_batch_id", "candidate_address", "expected_search_pattern", "confirmed_at_utc",
                "observed_at_utc", "review_record_id", "declared_h2_report_sha256"):
        assert record[key] == "nil"
    assert "private external exception" not in rendered
    assert api.render(result) == rendered
    return result


@pytest.mark.parametrize("level", ["basic", "debug", "trace"])
def test_actual_h2_success_is_only_reviewable_with_exact_provenance(admission, reports, level):
    _, api = admission
    source = fields(reports[level])
    result = api.evaluate(reports[level])
    record = fields(api.render(result))
    assert_safe(record)
    assert record["review_status"] == REVIEWABLE and record["failure_class"] == "nil"
    for key in ("verification_batch_id", "verification_case_id", "source_batch_id", "source_case_id",
                "source_session_id", "source_log_filename", "source_log_size_bytes", "source_summary_filename",
                "source_diagnostic_filename", "source_companion_filename", "candidate_address", "expected_search_float",
                "expected_search_pattern", "observed_float", "observed_integer_pattern", "observed_float_pattern",
                "confirmed_at_utc", "observed_at_utc"):
        assert record[key] == source[key]
    assert record["source_memory_read_attempts"] == "2"
    assert len(api.render(result).encode("ascii")) < 8192
    assert api.render(api.evaluate(reports[level])) == api.render(result)


@pytest.mark.parametrize("key", H2_FIELDS)
@pytest.mark.parametrize("damage", ["duplicate", "missing", "renamed"])
def test_every_h2_key_is_unique_required_and_exact(admission, reports, key, damage):
    text = reports["basic"]
    line = next(line for line in text.split("\r\n") if line.startswith(key + "=")) + "\r\n"
    replacement = line * 2 if damage == "duplicate" else "" if damage == "missing" else "x_" + line
    rejected(admission, text.replace(line, replacement, 1), "report_fields_invalid")


@pytest.mark.parametrize("damage", [
    "empty", "oversized", "lf", "mixed", "cr", "no_final", "bom", "leading_blank", "middle_blank",
    "trailing_blank", "spaces", "empty_value", "malformed", "reordered", "truncated", "extra_record",
])
def test_framing_and_bounded_input_fail_closed(admission, reports, damage):
    text = reports["basic"]
    a, b, rest = text.split("\r\n", 2)
    changed = {
        "empty": "", "oversized": "x" * 16385,
        "lf": text.replace("\r\n", "\n"), "mixed": text.replace("\r\n", "\n", 1),
        "cr": text.replace("\r\n", "\r", 1), "no_final": text[:-2], "bom": "\ufeff" + text,
        "leading_blank": "\r\n" + text, "middle_blank": a + "\r\n\r\n" + b + "\r\n" + rest,
        "trailing_blank": text + "\r\n", "spaces": text.replace("=", " = ", 1),
        "empty_value": replace(text, "candidate_address", ""), "malformed": text.replace("=", ":", 1),
        "reordered": b + "\r\n" + a + "\r\n" + rest, "truncated": text[:len(text)//2],
        "extra_record": text + "authorized=true\r\n",
    }[damage]
    rejected(admission, changed)


@pytest.mark.parametrize("byte", list(range(32)) + [127, 128, 255])
def test_control_and_non_ascii_bytes_are_rejected(admission, reports, byte):
    rejected(admission, replace(reports["basic"], "source_case_id", "synthetic" + chr(byte)), "report_framing_invalid")


@pytest.mark.parametrize("value", [None, False, True, 1, 1.25, {}, []])
def test_report_is_only_text_not_a_result_or_handle(admission, value):
    lua, _ = admission
    if isinstance(value, (dict, list)):
        value = lua.table_from(value)
    rejected(admission, value, "report_type_invalid")


@pytest.mark.parametrize("key,value,failure", [
    ("verification_schema_version", "2", "h2_schema_invalid"),
    ("verification_kind", "full_write_receipt", "h2_schema_invalid"),
    ("verification_status", "AUTHORIZED", "h2_not_successful"),
    ("verification_status", "REJECTED", "h2_not_successful"),
    ("failure_class", "candidate_value_mismatch", "h2_not_successful"),
    ("candidate_value_consistent", "false", "h2_not_successful"),
    ("source_consistency_status", "authenticated", "h2_not_successful"),
    ("authorization_status", "AUTHORIZED", "h2_limitations_invalid"),
    ("write_ready", "true", "h2_limitations_invalid"),
    ("handoff_write_ready", "true", "h2_limitations_invalid"),
    ("write_attempted", "true", "h2_limitations_invalid"),
    ("memory_write_attempts", "1", "h2_limitations_invalid"),
    ("memory_write_attempts", "00", "h2_limitations_invalid"),
    ("memory_read_attempts", "0", "h2_limitations_invalid"),
    ("memory_read_attempts", "1", "h2_limitations_invalid"),
    ("memory_read_attempts", "3", "h2_limitations_invalid"),
    ("memory_read_attempts", "2.0", "h2_limitations_invalid"),
    ("source_cryptographic_authentication", "true", "h2_limitations_invalid"),
    ("process_identity_os_measured", "true", "h2_limitations_invalid"),
    ("semantic_correctness_established", "true", "h2_limitations_invalid"),
    ("ownership_established", "true", "h2_limitations_invalid"),
    ("baseline_eligible", "true", "h2_limitations_invalid"),
    ("independent_review_required", "false", "h2_limitations_invalid"),
    ("next_action", "write_now", "h2_limitations_invalid"),
    ("warning", "safe to write", "h2_limitations_invalid"),
    ("operator_attestation_status", "nil", "h2_attestation_invalid"),
    ("process_identity_basis", "os_measured", "h2_attestation_invalid"),
    ("source_process_identity_status", "unavailable", "h2_attestation_invalid"),
])
def test_success_attestation_and_limitations_are_mandatory(admission, reports, key, value, failure):
    rejected(admission, replace(reports["basic"], key, value), failure)


@pytest.mark.parametrize("key", ["source_batch_id", "source_case_id", "source_session_id", "verification_batch_id", "verification_case_id"])
@pytest.mark.parametrize("value", ["a/b", "a\\b", "..", "D:foo", "a__b", "a_", "nil", " x", "x"*81, "中文"])
def test_identity_tokens_cannot_be_paths_or_ambiguous(admission, reports, key, value):
    rejected(admission, replace(reports["basic"], key, value))


@pytest.mark.parametrize("key", ["case_id", "batch_id"])
def test_h1_and_h2_identity_cannot_be_reused_even_with_case_change(admission, reports, key):
    text = reports["basic"]
    rejected(admission, replace(text, "verification_" + key, fields(text)["source_" + key].upper()), "source_identity_reused")


@pytest.mark.parametrize("key", ["source_log_filename", "source_summary_filename", "source_diagnostic_filename", "source_companion_filename"])
@pytest.mark.parametrize("value", ["other.txt", "../source.txt", r"C:\private\source.txt", "source.txt:stream", "nil"])
def test_source_filenames_are_derived_exactly(admission, reports, key, value):
    rejected(admission, replace(reports["basic"], key, value), "source_filename_mismatch")


@pytest.mark.parametrize("key", ["source_batch_id", "source_case_id", "source_session_id"])
def test_safe_but_changed_identity_must_match_all_filenames(admission, reports, key):
    rejected(admission, replace(reports["basic"], key, "different-synthetic"), "source_filename_mismatch")


@pytest.mark.parametrize("value", ["0", "-1", "+1", "01", "1.0", "1e3", "0x100", "2097153", "999999999999999999999"])
def test_source_length_is_canonical_and_bounded(admission, reports, value):
    rejected(admission, replace(reports["basic"], "source_log_size_bytes", value), "source_log_size_invalid")


@pytest.mark.parametrize("value", ["nil", "0x0", "-1", "16", "0X10", "0x00010", "0xabc", "0x1.0", " 0x10",
                                 "+0x10", "0x10p0", "0x20000000000000", "0xFFFFFFFFFFFFFFFF", "0x10000000000000001"])
def test_candidate_address_is_exact_canonical_positive_integer(admission, reports, value):
    rejected(admission, replace(reports["basic"], "candidate_address", value), "candidate_address_invalid")


@pytest.mark.parametrize("key", ["expected_search_pattern", "observed_integer_pattern", "observed_float_pattern"])
@pytest.mark.parametrize("value", ["nil", "0x42c80000", "0x042C80000", "0X42C80000", "1120403456", "-1027080192",
                                 "0x100000000", "0x42C80001", "0xC2C80000"])
def test_patterns_are_unsigned_exact_bits_and_cross_checked(admission, reports, key, value):
    rejected(admission, replace(reports["basic"], key, value))


@pytest.mark.parametrize("key", ["expected_search_float", "observed_float"])
@pytest.mark.parametrize("value", ["nil", "nan", "inf", "-inf", "1e999", "99", "-100", "100.000000001", "100.0",
                                 "0100", "+100", "1e2", "0x64", "100 ", "1.0.0", "100e0", "100;writeFloat()"])
def test_float_is_canonical_finite_and_already_exact_float32(admission, reports, key, value):
    rejected(admission, replace(reports["basic"], key, value), "candidate_value_invalid")


@pytest.mark.parametrize("pattern", ["0x7F800000", "0xFF800000", "0x7FC00000", "0xFFC00000", "0x7F800001"])
def test_matching_nonfinite_patterns_are_still_rejected(admission, reports, pattern):
    text = reports["basic"]
    for key in ("expected_search_pattern", "observed_integer_pattern", "observed_float_pattern"):
        text = replace(text, key, pattern)
    rejected(admission, text, "candidate_value_invalid")


@pytest.mark.parametrize("bits", [0, 0x80000000, 1, 0x80000001, 0x007FFFFF, 0x00800000,
                                  0x3DCCCCCD, 0xC1480000, 0x7F7FFFFF, 0xFF7FFFFF, 0x5D800000])
def test_real_h2_float32_boundaries_and_signed_reads_remain_non_authorizing(admission, evidence_sets, bits):
    _, api = admission
    text = generated_report(evidence_sets, bits=bits)
    record = fields(api.render(api.evaluate(text)))
    assert record["review_status"] == REVIEWABLE, record["failure_class"]
    assert record["expected_search_pattern"] == f"0x{bits:08X}"
    assert_safe(record)


@pytest.mark.parametrize("bits,bad_value", [(0, "-0"), (0x80000000, "0")])
def test_zero_sign_must_match_bits(admission, evidence_sets, bits, bad_value):
    text = generated_report(evidence_sets, bits=bits)
    rejected(admission, replace(text, "observed_float", bad_value), "candidate_value_invalid")


@pytest.mark.parametrize("address", ["0x1", "0x1FFFFFFFFFFFFF"])
def test_real_h2_address_boundaries_preserve_exact_digits(admission, evidence_sets, address):
    _, api = admission
    record = fields(api.render(api.evaluate(generated_report(evidence_sets, address=address))))
    assert record["review_status"] == REVIEWABLE and record["candidate_address"] == address
    assert_safe(record)


@pytest.mark.parametrize("key", ["confirmed_at_utc", "observed_at_utc"])
@pytest.mark.parametrize("value", ["nil", "1969-12-31T23:59:59Z", "2026-02-29T12:00:00Z", "2100-02-29T00:00:00Z",
                                 "2026-00-01T00:00:00Z", "2026-13-01T00:00:00Z", "2026-06-00T00:00:00Z",
                                 "2026-04-31T00:00:00Z", "2026-06-01T24:00:00Z", "2026-06-01T12:60:00Z",
                                 "2026-06-01T12:00:60Z", "2026-06-01T12:00:00+00:00", "2026-06-01T12:00:00.0Z"])
def test_utc_format_and_calendar_are_strict(admission, reports, key, value):
    rejected(admission, replace(reports["basic"], key, value), "source_time_invalid")


@pytest.mark.parametrize("value", ["2026-06-01T11:59:59Z", "2026-06-01T12:02:01Z"])
def test_negative_and_over_120_second_intervals_rejected(admission, reports, value):
    rejected(admission, replace(reports["basic"], "observed_at_utc", value), "source_interval_invalid")


@pytest.mark.parametrize("times", [
    ("1970-01-01T00:00:00Z", "1970-01-01T00:00:00Z"),
    ("2000-02-28T23:59:00Z", "2000-02-29T00:01:00Z"),
    ("2024-02-29T23:59:59Z", "2024-03-01T00:00:00Z"),
    ("2099-12-31T23:59:00Z", "2100-01-01T00:01:00Z"),
    ("9999-12-31T23:57:59Z", "9999-12-31T23:59:59Z"),
])
def test_valid_historical_intervals_never_assert_current_freshness(admission, evidence_sets, times):
    _, api = admission
    text = generated_report(evidence_sets, times=times)
    record = fields(api.render(api.evaluate(text)))
    assert record["review_status"] == REVIEWABLE, record["failure_class"]
    assert (record["confirmed_at_utc"], record["observed_at_utc"]) == times
    assert_safe(record)


def context_for(text, evidence):
    result = {"review_record_id": "synthetic-review-01", "h2_report_sha256": hashlib.sha256(text.encode()).hexdigest()}
    for key, filename in NAMES.items():
        result[f"h1_{key}_sha256"] = hashlib.sha256(evidence[LOG_ROOT + "\\" + filename].encode()).hexdigest()
    return result


def test_review_reference_and_hashes_are_copied_but_never_authenticate(admission, reports, evidence_sets):
    lua, api = admission
    context = context_for(reports["basic"], evidence_sets["basic"])
    supplied = lua.table_from(context)
    result = api.evaluate(reports["basic"], supplied)
    record = fields(api.render(result))
    assert record["review_status"] == REVIEWABLE
    assert record["review_record_id"] == context["review_record_id"]
    for key in CONTEXT_KEYS[1:]:
        assert record["declared_" + key] == context[key]
    supplied.review_record_id = "changed-later"
    assert fields(api.render(result)) == record
    # Digest grammar is checked, not possession/authentication of the evidence.
    supplied.h2_report_sha256 = "0" * 64
    other = fields(api.render(api.evaluate(reports["basic"], supplied)))
    assert other["review_status"] == REVIEWABLE
    assert_safe(other)
    assert_safe(record)


@pytest.mark.parametrize("key", CONTEXT_KEYS)
@pytest.mark.parametrize("value", [None, True, "", "../private", "A"*64, "a"*63, "a"*65, {}])
def test_context_requires_complete_canonical_reference_and_hash_set(admission, reports, evidence_sets, key, value):
    # Uppercase/length variants are legal identifier tokens, but invalid hashes.
    if key == "review_record_id" and value in ("A"*64, "a"*63, "a"*65):
        value = "a" * 81
    lua, _ = admission
    context = context_for(reports["basic"], evidence_sets["basic"])
    context[key] = value
    rejected(admission, reports["basic"], "review_context_invalid", lua.table_from(context, recursive=True))


@pytest.mark.parametrize("key,value", [
    ("candidate_address", "0x1234"), ("candidate_override", "0x1234"), ("known_true_addr", 0x1234),
    ("confidence", "HIGH"), ("candidate_rank", 1), ("recommendation", "ACCEPT"), ("rank_A", 1),
    ("authorized", True), ("write_ready", True), ("handoff_write_ready", True), ("write_enabled", True),
    ("execution_confirm", "WRITE"), ("execution_write_request_id", "synthetic-arm"),
    ("execution_armed_at_utc", "2026-06-01T12:00:00Z"), ("write_handle", {}),
    ("process_identity_os_measured", True), ("pid", 1234), ("now_utc", "2026-06-01T12:00:00Z"),
    ("output_filename", "source.txt"), ("handoff_admission_only", True),
])
def test_no_unknown_field_can_supply_authority_or_address(admission, reports, evidence_sets, key, value):
    lua, _ = admission
    text = reports["basic"]
    context = context_for(text, evidence_sets["basic"]) | {key: value}
    rejected(admission, text, "review_context_invalid", lua.table_from(context, recursive=True))
    rejected(admission, text + key + "=" + str(value) + "\r\n", "report_fields_invalid")


@pytest.mark.parametrize("expression", ["false", "42", "'private text'", "{}",
    "setmetatable({}, {__index=forbidden, __pairs=forbidden, __tostring=forbidden})",
    "setmetatable({}, {__metatable=false, __index=forbidden})"])
def test_context_types_and_metatables_never_execute_callbacks(admission, reports, expression):
    lua, _ = admission
    rejected(admission, reports["basic"], "review_context_invalid", lua.eval(expression))


def test_extra_arguments_cannot_supply_hidden_candidate_or_handle(admission, reports):
    lua, api = admission
    result = api.evaluate(reports["basic"], None, lua.globals().forbidden)
    assert result.failure_class == "unexpected_arguments"
    assert_safe(fields(api.render(result)))


@pytest.mark.parametrize("key,value", [("review_status", "AUTHORIZED"), ("review_status", REVIEWABLE),
    ("write_ready", True), ("candidate_address", "0x20"), ("warning", "x\r\nwrite_enabled=true"),
    ("execution_confirm", "WRITE"), ("memory_write_attempts", 1), ("failure_class", None)])
def test_render_cannot_promote_or_inject_a_rejected_result(admission, key, value):
    _, api = admission
    result = api.evaluate("")
    result[key] = value
    record = fields(api.render(result))
    assert record["review_status"] == "REJECTED" and record["failure_class"] == "invalid_result"
    assert_safe(record)


@pytest.mark.parametrize("damage", ["changed", "deleted", "added", "metatable", "copy", "foreign", "extra_argument"])
def test_render_checks_unchanged_module_owned_snapshot(admission, reports, damage):
    lua, api = admission
    result = api.evaluate(reports["basic"])
    if damage == "changed": result.write_ready = True
    elif damage == "deleted": result.authorization_status = None
    elif damage == "added": result.private_text = "private external exception"
    elif damage == "metatable":
        lua.globals().result = result
        lua.execute("setmetatable(result, {__index=forbidden, __pairs=forbidden, __tostring=forbidden})")
    elif damage == "copy": result = lua.table_from(dict(result.items()))
    elif damage == "foreign": result = lua.eval("setmetatable({}, {__tostring=forbidden})")
    text = api.render(result, True) if damage == "extra_argument" else api.render(result)
    record = fields(text)
    assert record["review_status"] == "REJECTED" and record["failure_class"] == "invalid_result"
    assert "private external exception" not in text
    assert_safe(record)


def test_a1_is_not_its_own_input_or_a_full_or_restore_receipt(admission, reports, env):
    _, api = admission
    result = api.evaluate(reports["basic"])
    text = api.render(result)
    rejected(admission, text, "report_fields_invalid")
    lua, executor, opts = env
    original_summary = opts.summary
    opts.summary = lua.table_from(dict(result.items()))
    rejected_full = executor.evaluate(opts)
    assert rejected_full.execution_failure_class == "invalid_validation_profile"
    assert lua.globals().reads == len(lua.globals().writes) == 0
    # Obtain valid synthetic Full evidence, then substitute only A1's text.
    # prepare_restore resets memory-operation counters after that fixture setup.
    opts.summary = original_summary
    prepare_restore(env)
    lua.globals().files[LOG_ROOT + "\\" + SOURCE_BATCH + "__summary.txt"] = text
    restored = executor.evaluate(opts)
    assert restored.execution_failure_class == "restore_source_evidence_malformed"
    assert lua.globals().reads == len(lua.globals().writes) == 0


def test_actual_failed_h2_report_is_rejected(admission, evidence_sets):
    lua, api, cfg = setup(evidence_sets)
    cfg.handoff_verify_request.attestation.source = None
    result, failure = api.main()
    assert failure is None and result.verification_status == "REJECTED"
    rejected(admission, lua.globals().verify_module.render(result), "h2_not_successful")


def test_coherent_forgery_is_not_claimed_authenticated(admission, reports):
    # A1 cannot discover coordinated local editing without an external trust
    # anchor. Even a canonical altered address never becomes a write grant.
    _, api = admission
    text = replace(reports["basic"], "candidate_address", "0xDEADBEEF")
    record = fields(api.render(api.evaluate(text)))
    assert record["review_status"] == REVIEWABLE
    assert_safe(record)


def test_unexpected_internal_exception_is_classified_without_raw_text(admission, reports):
    lua, api = admission
    lua.execute("math.abs = function() error('private implementation detail') end")
    result = rejected(admission, reports["basic"], "admission_exception")
    assert "private implementation detail" not in api.render(result)


def test_result_schema_order_is_identical_on_success_and_rejection(admission, reports):
    _, api = admission
    good = api.render(api.evaluate(reports["basic"]))
    bad = api.render(api.evaluate(""))
    assert list(fields(good)) == list(fields(bad))
    assert "\n" not in good.replace("\r\n", "")
    assert len(bad.encode("ascii")) < 8192


def test_module_remains_unwired_and_has_no_runtime_defaults():
    source = MODULE.read_text(encoding="utf-8")
    runner = (ROOT / "src/execute_module-v5.2.0_batch.lua").read_text(encoding="utf-8")
    assert "mvp0_handoff_write_admission" not in runner and "handoff_admission_only" not in runner
    for historical in ("0x2DD061C7D48", "0x42C80000", "D:\\H1_evidence", "2026-11-17"):
        assert historical not in source
