"""R3-B prelaunch contract, evaluated as data only. No native activation exists.

The injected verifier is test equipment, never a trusted approver installation.
Even a fully matching model result cannot create a runtime capability.
"""
from datetime import datetime
from pathlib import PureWindowsPath

from .native_probe_protocol import canonical, decode, digest_string, identifier, require, sha256, ProbeError

FREEZE_KEYS = frozenset({"manifest", "patch", "source", "probe", "ce_exe", "ce_dll"})
CASES = frozenset(f"N{i:02}" for i in range(1, 10))
CAPS = {"ce_processes": 1, "servers": 1, "outstanding": 1, "request_ms": 250,
        "watchdog_ms": 2000, "case_ms": 60000, "session_ms": 900000,
        "repetitions": 3, "cleanup_cycles": 20, "body_bytes": 65536,
        "log_bytes": 8388608, "memory_bytes": 16777216}
ZERO = frozenset({"target_launch", "target_attach", "target_scan", "target_read",
                  "target_write", "target_allocate", "production_ledger", "automatic_retries"})


def exact(value, keys, code):
    require(type(value) is dict and set(value) == set(keys), code)


def timestamp(value):
    require(type(value) is str, "APPROVAL_TIME")
    try:
        result = datetime.fromisoformat(value)
    except ValueError:
        raise ProbeError("APPROVAL_TIME") from None
    require(result.tzinfo is not None and result.utcoffset() is not None, "APPROVAL_TIMEZONE")
    return result


def evaluate_model(raw, expected, observations, verifier, *, now, case_id):
    """Validate a canonical synthetic approval against independent model inputs.

    No filesystem/OS queries are made here. A caller-provided observation cannot
    become native evidence. Unknown fields, units or isolation deny admission.
    """
    require(type(raw) is bytes and 0 < len(raw) <= 65536, "APPROVAL_SIZE")
    record = decode(raw)
    exact(record, {"schema", "origin", "purpose", "approval_id", "approver", "operator",
                   "host", "principal", "workspace", "freeze", "window", "evidence_dir",
                   "cases", "vectors", "caps", "zero", "isolation", "cleanup", "signature"}, "APPROVAL_FIELDS")
    require(record["schema"] == "qsg.r3-b.approval-model.v1" and record["origin"] == "SYNTHETIC",
            "MODEL_APPROVAL_ONLY")
    require(record["purpose"] == "R3-B transport test only, NOT G1 LIVE", "APPROVAL_SCOPE")
    for key in ("approval_id", "approver", "operator", "host"):
        identifier(record[key])
    exact(expected, {"freeze", "approver", "operator", "host", "principal", "workspace",
                     "evidence_dir", "isolation_digest"}, "EXPECTED_FIELDS")
    for key in ("approver", "operator", "host", "principal", "workspace", "evidence_dir"):
        require(type(record[key]) is str and record[key] == expected[key] and record[key], "APPROVAL_BINDING")
    for key in ("workspace", "evidence_dir"):
        path = PureWindowsPath(record[key])
        require(path.is_absolute() and not str(path).startswith("\\\\") and ".." not in path.parts,
                "APPROVAL_PATH")
    exact(record["freeze"], FREEZE_KEYS, "FREEZE_FIELDS")
    exact(expected["freeze"], FREEZE_KEYS, "FREEZE_FIELDS")
    for key in FREEZE_KEYS:
        digest_string(record["freeze"][key]); digest_string(expected["freeze"][key])
        require(record["freeze"][key] == expected["freeze"][key], "FREEZE_MISMATCH")
    exact(record["window"], {"start", "end"}, "APPROVAL_WINDOW")
    start, end, current = timestamp(record["window"]["start"]), timestamp(record["window"]["end"]), timestamp(now)
    require(start <= current < end and 0 < (end - start).total_seconds() <= 900, "APPROVAL_EXPIRED")
    cases = record["cases"]
    require(type(cases) is list and cases and all(type(c) is str and c in CASES for c in cases)
            and len(cases) == len(set(cases)) and case_id in cases, "CASE_NOT_APPROVED")
    exact(record["vectors"], cases, "VECTOR_SCOPE")
    for values in record["vectors"].values():
        require(type(values) is list and 1 <= len(values) <= 64, "VECTOR_SCOPE")
        for value in values: identifier(value)
        require(len(set(values)) == len(values), "VECTOR_SCOPE")
    exact(record["caps"], CAPS, "RESOURCE_CAPS")
    for key, ceiling in CAPS.items():
        value = record["caps"][key]
        require(type(value) is int and 1 <= value <= ceiling, "RESOURCE_CAPS")
    c = record["caps"]
    require(c["request_ms"] < c["watchdog_ms"] < c["case_ms"] <= c["session_ms"], "RESOURCE_ORDER")
    exact(record["zero"], ZERO, "ZERO_CAPABILITIES")
    require(all(type(v) is int and v == 0 for v in record["zero"].values()), "ZERO_CAPABILITIES")
    exact(record["isolation"], {"method", "proof_sha256", "reuse", "autorun", "restore", "autoattach"}, "STARTUP_ISOLATION")
    isolation = record["isolation"]
    require(isolation["method"] == "INDEPENDENT_SUPPORTED_STARTUP_PROOF", "STARTUP_ISOLATION")
    digest_string(isolation["proof_sha256"])
    require(isolation["proof_sha256"] == expected["isolation_digest"]
            and all(isolation[k] == "PROVEN_DISABLED" for k in ("reuse", "autorun", "restore", "autoattach")),
            "STARTUP_ISOLATION")
    exact(observations, {"origin", "evidence_fresh", "evidence_writable", "startup_proof_sha256",
                         "watchdog_independent", "target_absent"}, "OBSERVATION_FIELDS")
    require(observations["origin"] == "SYNTHETIC", "MODEL_OBSERVATIONS_ONLY")
    require(observations["evidence_fresh"] is True and observations["evidence_writable"] is True, "EVIDENCE_UNAVAILABLE")
    require(observations["startup_proof_sha256"] == isolation["proof_sha256"], "STARTUP_ISOLATION")
    require(observations["watchdog_independent"] is True, "WATCHDOG_UNPROVEN")
    require(observations["target_absent"] is True, "TARGET_NOT_ABSENT")
    exact(record["cleanup"], {"cancel_io", "terminate", "instance_policy", "helpers", "principal_negatives"}, "CLEANUP_SCOPE")
    cleanup = record["cleanup"]
    require(type(cleanup["cancel_io"]) is bool and type(cleanup["terminate"]) is bool
            and cleanup["instance_policy"] == "EXACT_INDEPENDENTLY_SPAWNED_HANDLE"
            and cleanup["helpers"] == [] and cleanup["principal_negatives"] == [], "CLEANUP_SCOPE")
    # Additional helper/principal-negative rights require a new reviewed contract.
    signature = record["signature"]
    exact(signature, {"key_id", "value"}, "APPROVAL_SIGNATURE")
    identifier(signature["key_id"])
    require(type(signature["value"]) is str and 1 <= len(signature["value"]) <= 4096, "APPROVAL_SIGNATURE")
    payload = canonical({k: v for k, v in record.items() if k != "signature"})
    require(callable(verifier), "APPROVAL_VERIFIER_UNAVAILABLE")
    verified = verifier(payload, signature, expected["approver"])
    require(verified == {"origin": "SYNTHETIC", "verified_payload_sha256": sha256(payload),
                         "approver": expected["approver"], "status": "MODEL_SIGNATURE_MATCH"}, "APPROVAL_SIGNATURE")
    return {"status": "SYNTHETIC_ADMISSION_ONLY", "authorization_sha256": sha256(raw),
            "native_activation": "BLOCKED_NATIVE_ACTIVATION_UNPROVEN", "case_id": case_id}


def require_native_activation(*_args, **_kwargs):
    """Hard stop BEFORE provider construction/loading. No flag or verifier override.

    Future replacement requires independent R3-B approval, trusted verification,
    supported prelaunch isolation and a newly frozen/reapproved implementation.
    """
    raise ProbeError("BLOCKED_NATIVE_ACTIVATION_UNPROVEN")


# P0 is a separate contract. B0 approval fixtures and their semantics stay intact.
ACTIVATION_SCHEMA = "qsg.native-probe.activation.v1"
LP_MANIFEST = "9c8a3b8dd5c7a8278b138f78598af9c70a3fa12c6c70dd7db98aa21bcd4d7ae6"
CE_EXE = "49cc24f682ff330631672dc89f2e4d7d277598d0d61541a3fee4dd3cd941583d"
CE_DLL = "436f6bf9ac414e7e7259bef4f6e287702a41e1fddbdd9af7d43350d47539a3c9"
ACTIVATION_FILES = frozenset({
    "src/qualification/native_ipc_probe.lua", "src/ce_qualification/native_ipc_probe.py",
    "src/ce_qualification/native_probe_admission.py", "src/ce_qualification/native_probe_winpipe.py",
    "src/ce_qualification/native_probe_activation.py", "tests/qualification/test_native_probe_activation.py",
    "docs/qualification/h3_a7_q1_qsg_r3_b_p0_activation_contract.md",
    "src/ce_qualification/native_probe_protocol.py"})
P0_CAPS = {"ce_processes": 1, "servers": 1, "outstanding": 1, "request_ms": 250,
           "watchdog_ms": 2000, "case_ms": 60000, "suite_ms": 900000,
           "trials": 3, "cleanup_iterations": 20, "messages": 64, "cases": 12,
           "body_bytes": 65536, "evidence_bytes": 16777216,
           "ce_memory_bytes": 536870912, "server_memory_bytes": 268435456,
           "helper_memory_bytes": 268435456}
P0_ZERO = ZERO | {"real_pipe", "native_provider", "process_termination", "handle_duplication"}
TECHNICAL_FIELDS = frozenset({"dedicated_instance", "startup_isolation", "dacl",
    "peer_principal", "client_handle", "process_creation", "loaded_runtime",
    "watchdog_independent", "cleanup_completion", "secret_bootstrap", "target_absent",
    "evidence_fresh", "evidence_writable"})


def activation_utc(value):
    import re
    require(type(value) is str and re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", value),
            "P0_UTC_REQUIRED")
    return timestamp(value)


def activation_path(value):
    """Lexical approval binding, NOT filesystem/reparse-point verification."""
    import re
    require(type(value) is str and 3 <= len(value) <= 4096, "P0_PATH")
    p = PureWindowsPath(value)
    require(p.is_absolute() and len(p.drive) == 2 and p.drive[1] == ":"
            and value == str(p) and ".." not in p.parts, "P0_PATH")
    for part in p.parts[1:]:
        require(part and part[-1] not in ". " and not re.search(r'[<>:"/|?*\x00-\x1f]', part)
                and not re.fullmatch(r"(?i)(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?", part), "P0_PATH")


def parse_activation_record(raw):
    require(type(raw) is bytes and 1 <= len(raw) <= 65536, "P0_APPROVAL_SIZE")
    r = decode(raw)
    exact(r, {"schema", "protocol", "origin", "purpose", "authorization_sha256",
        "candidate_sha256", "assets", "identities", "window", "workspace", "evidence_dir",
        "session", "cases", "caps", "zero", "watchdog"}, "P0_APPROVAL_FIELDS")
    require(r["schema"] == ACTIVATION_SCHEMA and r["protocol"] == "qsg.native-probe.v1"
            and r["origin"] == "SYNTHETIC" and r["purpose"] == "P0_OFFLINE_ONLY", "P0_SCOPE")
    for k in ("authorization_sha256", "candidate_sha256"): digest_string(r[k])
    exact(r["assets"], ACTIVATION_FILES | {"ce_exe", "ce_dll"}, "P0_ASSETS")
    for v in r["assets"].values(): digest_string(v)
    exact(r["identities"], {"host", "operator", "approver"}, "P0_IDENTITIES")
    for role in ("host", "operator", "approver"):
        exact(r["identities"][role], {"id", "identity_sha256"}, "P0_IDENTITY")
        identifier(r["identities"][role]["id"])
        digest_string(r["identities"][role]["identity_sha256"])
    require(r["identities"]["operator"]["id"] != r["identities"]["approver"]["id"]
            and r["identities"]["operator"]["identity_sha256"] != r["identities"]["approver"]["identity_sha256"],
            "P0_AMBIGUOUS_APPROVER")
    exact(r["window"], {"start", "end"}, "P0_WINDOW")
    start, end = activation_utc(r["window"]["start"]), activation_utc(r["window"]["end"])
    require(0 < (end-start).total_seconds() <= 900, "P0_WINDOW")
    for k in ("workspace", "evidence_dir"): activation_path(r[k])
    workspace, evidence = PureWindowsPath(r["workspace"]), PureWindowsPath(r["evidence_dir"])
    require(evidence.is_relative_to(workspace/"reports") and evidence != workspace/"reports", "P0_EVIDENCE_PATH")
    exact(r["session"], {"session_id", "channel_id", "epoch", "nonce", "case_id", "trial"}, "P0_SESSION")
    for k in ("session_id", "channel_id"): identifier(r["session"][k])
    digest_string(r["session"]["nonce"])
    require(type(r["session"]["epoch"]) is int and 1 <= r["session"]["epoch"] <= 2147483647, "P0_EPOCH")
    require(type(r["session"]["trial"]) is int and 1 <= r["session"]["trial"] <= 3, "P0_TRIAL")
    cases = r["cases"]
    require(type(cases) is list and 1 <= len(cases) <= 12
            and all(type(c) is str and c in {f"P0-{i:02}" for i in range(1, 13)} for c in cases)
            and len(set(cases)) == len(cases) and r["session"]["case_id"] in cases, "P0_CASE")
    exact(r["caps"], P0_CAPS, "P0_CAPS")
    for k, ceiling in P0_CAPS.items():
        require(type(r["caps"][k]) is int and 1 <= r["caps"][k] <= ceiling, "P0_CAPS")
    # Existing byte worker/watchdog have these fixed deadlines. Never claim to
    # enforce a different value merely because a record requested it.
    for k in ("request_ms", "watchdog_ms", "body_bytes"):
        require(r["caps"][k] == P0_CAPS[k], "P0_FIXED_LIMIT")
    c = r["caps"]
    require(c["request_ms"] < c["watchdog_ms"] < c["case_ms"] <= c["suite_ms"]
            and len(cases) <= c["cases"] and r["session"]["trial"] <= c["trials"], "P0_BUDGET_BINDING")
    exact(r["zero"], P0_ZERO, "P0_ZERO")
    require(all(type(v) is int and v == 0 for v in r["zero"].values()), "P0_ZERO")
    exact(r["watchdog"], {"mode", "clock_domain", "cancel", "terminate"}, "P0_WATCHDOG")
    require(r["watchdog"] == {"mode":"INDEPENDENT_MODEL", "clock_domain":"watchdog",
                             "cancel":"MODEL_ONLY", "terminate":False}
            and r["watchdog"]["terminate"] is False, "P0_WATCHDOG")
    return r


def bind_activation_candidate(raw, pinned_sha256):
    digest_string(pinned_sha256)
    require(type(raw) is bytes and 1 <= len(raw) <= 16384 and sha256(raw) == pinned_sha256, "P0_CANDIDATE_DIGEST")
    m = decode(raw)
    exact(m, {"schema", "protocol", "baseline_manifest_sha256", "files", "ce_exe", "ce_dll"}, "P0_CANDIDATE_FIELDS")
    require(m["schema"] == "qsg.p0.source.v1" and m["protocol"] == "qsg.native-probe.v1"
            and m["baseline_manifest_sha256"] == LP_MANIFEST and m["ce_exe"] == CE_EXE
            and m["ce_dll"] == CE_DLL, "P0_FROZEN_ANCHOR")
    exact(m["files"], ACTIVATION_FILES, "P0_CANDIDATE_FILES")
    for h in m["files"].values(): digest_string(h)
    require(m["files"]["src/ce_qualification/native_probe_protocol.py"] ==
            "a7d1001e7d60d23f3dc839454839d627dca8b775d5be3b6c582370d41366b5be", "P0_PROTOCOL_DRIFT")
    return {**m["files"], "ce_exe":m["ce_exe"], "ce_dll":m["ce_dll"]}


def bind_activation_authority(record, raw, policy_raw, *, candidate_sha256, assets, now):
    require(type(policy_raw) is bytes and 1 <= len(policy_raw) <= 65536, "P0_POLICY")
    p = decode(policy_raw)
    # A fixed, separately supplied synthetic byte pin is not a signature verifier.
    exact(p, {"record_sha256", "authorization_sha256", "identities", "window", "workspace",
              "evidence_dir", "session", "cases", "caps", "zero", "watchdog"}, "P0_POLICY")
    require(record["candidate_sha256"] == candidate_sha256 and record["assets"] == assets, "P0_ASSET_DRIFT")
    for k in set(p)-{"record_sha256"}:
        require(record[k] == p[k], "P0_AUTH_BINDING")
    require(sha256(raw) == p["record_sha256"], "P0_APPROVAL_PIN")
    require(activation_utc(record["window"]["start"]) <= activation_utc(now)
            < activation_utc(record["window"]["end"]), "P0_APPROVAL_EXPIRED")
    return p


def check_activation_technical(raw, record):
    require(type(raw) is bytes and 1 <= len(raw) <= 65536, "P0_TECHNICAL_SIZE")
    o = decode(raw)
    exact(o, {"origin", "os_evidence", "session", "assets", "identities", "checks",
              "peer_expected", "peer_proof", "handle_ref"}, "P0_TECHNICAL_FIELDS")
    require(o["origin"] == "SYNTHETIC" and o["os_evidence"] == "NOT_PROVEN", "P0_MOCK_IS_NOT_OS_PROOF")
    for k in ("session", "assets", "identities"):
        require(o[k] == record[k] and canonical(o[k]) == canonical(record[k]), "P0_OBSERVATION_DRIFT")
    exact(o["checks"], TECHNICAL_FIELDS, "P0_TECHNICAL_CHECKS")
    for k in sorted(TECHNICAL_FIELDS):
        require(o["checks"][k] == "SYNTHETIC_MATCH", "P0_TECHNICAL_"+k.upper())
    from .native_probe_peer import validate_connection_model
    p = o["peer_expected"]
    require(type(p) is dict, "P0_PEER_BINDING")
    for k in ("session_id", "channel_id", "epoch"):
        require(p.get(k) == record["session"][k], "P0_PEER_BINDING")
    require(p.get("candidate_sha256") == record["candidate_sha256"]
            and p.get("authorization_sha256") == record["authorization_sha256"]
            and p.get("connection_id") == record["session"]["nonce"][:32], "P0_PEER_BINDING")
    validate_connection_model(o["peer_proof"], p, handle_ref=o["handle_ref"])
    require(p["client"]["image_sha256"] == CE_EXE and p["client"]["component_sha256"] == CE_DLL,
            "P0_LOADED_IDENTITY")
    return "SYNTHETIC_TECHNICAL_ONLY"
