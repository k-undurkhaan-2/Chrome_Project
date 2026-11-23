"""Passive normalizer of already-copied R1 diagnostics. Default disabled.

No CE object/callback is accepted. Context bindings are transport claims, not
independent proof. Missing raw-address/attempt anchors remain inconclusive.
"""
from copy import deepcopy

from .evidence import EvidenceError, bits, canonical, identifier

COUNTERS = set("""adapter_read_calls adapter_readback_calls adapter_write_attempts
adapter_write_successes verified_writes adapter_scan_invocations scan_completions
scan_cancel_requests scan_disposals identity_checks mapping_queries valid_monitor_checks
invalid_monitor_checks retirements cleanup_attempts rejected_starts scan_count write_count
monitor_checks invalid_count rescan_attempts""".split())
FIELDS = set("""schema session_token source sequence event_type state_before state_after
configured_pid relative_ms time_source counters identity address_label reason stop_reason
identity_token raw_match_count count_source collection_complete completeness_reason hard_limit
configured_limit scan_complete progress_results total_addresses scanned_addresses raw_count
scanned_count filtered_count selected_count read_failure ranked_count qualified_count
recommendation manual_review best_score hard_pass confidence search_bits write_intent_bits
api_success readback_bits readback_float float_bits value_bits valid delay_ms cancel_requested
dispose_call_returned cleanup_ok cleanup_error call_ok accepted
raw_admission_budget ranking_budget native_count_limited raw_inspected_count unique_count
prescored_count coverage global_uniqueness_proven search_mode cycle_id
decision_scope write_admission_basis""".split())
ADMISSION_SCOPES = {"LEGACY_SCOPE_ACCEPT": "LEGACY_SINGLE_SCOPE",
                    "QSG_FULL_POPULATION_UNIQUE_ACCEPT": "QSG_FULL_POPULATION"}
GUARD_NAMES = ("openProcess", "createMemScan", "readInteger", "readFloat", "writeFloat",
               "createTimer", "executeCodeLocalEx", "createMemoryStream")


class CERecorder:
    def __init__(self, stream, *, enabled=False):
        self.stream, self.enabled = stream, enabled
        self.seen = {}

    def capture(self, snapshot, *, run_id, scenario, bindings=None, model_lua="NOT_RUN"):
        if not self.enabled:
            return {"enabled": False, "live": "NOT_RUN"}
        # Round-trip rejects objects/callables and detaches caller's mutable tables.
        canonical(snapshot)
        snapshot = deepcopy(snapshot)
        if snapshot.get("source") != "synthetic":
            raise EvidenceError("LIVE_CAPTURE_NOT_IMPLEMENTED")
        if snapshot.get("enabled") is not True or snapshot.get("schema") != 1:
            raise EvidenceError("DIAGNOSTICS_NOT_ENABLED")
        if snapshot.get("dropped_events") != 0 or snapshot.get("telemetry_error"):
            raise EvidenceError("DIAGNOSTIC_GAP")
        identifier(run_id); identifier(scenario)
        token = identifier(snapshot["session_token"])
        prior = self.seen.get(run_id, {"token": token, "events": {}})
        if prior["token"] != token:
            raise EvidenceError("RUN_TOKEN_CHANGED")
        events = snapshot.get("events", [])
        if isinstance(events, dict) and not events:
            events = []  # empty Lua table
        if [e.get("sequence") for e in events] != list(range(1, snapshot["last_sequence"] + 1)):
            raise EvidenceError("DIAGNOSTIC_SEQUENCE_GAP")
        if len(events) < len(prior["events"]):
            raise EvidenceError("DIAGNOSTIC_ROLLBACK")
        prepared = []
        for event in events:
            if set(event) - FIELDS or set(event.get("counters", {})) - COUNTERS:
                raise EvidenceError("UNREVIEWED_DIAGNOSTIC_FIELD")
            if event.get("event_type") == "candidate_admitted":
                basis = event.get("write_admission_basis")
                coverage, unique = event.get("coverage"), event.get("global_uniqueness_proven")
                if (not isinstance(basis, str) or basis not in ADMISSION_SCOPES
                        or event.get("decision_scope") != ADMISSION_SCOPES[basis]
                        or coverage not in ("full_population", "sampled_or_reduced")
                        or type(unique) is not bool or (unique and coverage != "full_population")
                        or (basis == "QSG_FULL_POPULATION_UNIQUE_ACCEPT" and not unique)):
                    raise EvidenceError("INVALID_ADMISSION_EVIDENCE")
            elif "write_admission_basis" in event or "decision_scope" in event:
                raise EvidenceError("INVALID_ADMISSION_EVIDENCE")
            event = deepcopy(event)
            for key in list(event):
                if key.endswith("_bits"):
                    event[key] = bits(event[key])
            if event.get("source") != "synthetic" or event.get("session_token") != token:
                raise EvidenceError("DIAGNOSTIC_ORIGIN_OR_TOKEN")
            for value in event.get("counters", {}).values():
                if type(value) is not int or value < 0:
                    raise EvidenceError("COUNTER_TYPE")
            sequence = event["sequence"]
            if sequence in prior["events"]:
                if prior["events"][sequence] != event:
                    raise EvidenceError("DIAGNOSTIC_HISTORY_CHANGED")
            else:
                prepared.append(event)
        for event in prepared:
            self.stream.emit("ce_event", {"diagnostic": event, "bindings": deepcopy(bindings or {})},
                             run_id=run_id, scenario=scenario)
            prior["events"][event["sequence"]] = event
        self.seen[run_id] = prior
        return self.stream.emit("ce_snapshot", {"state": snapshot["state"],
            "running": snapshot["running"], "counters": snapshot["counters"],
            "identity": snapshot["identity"], "cleanup_ok": snapshot["cleanup_ok"],
            "stop_reason": snapshot.get("stop_reason"), "last_sequence": snapshot["last_sequence"],
            "ce_embedded_lua": "NOT_RUN", "synthetic_lua": model_lua,
            "counter_semantics": "ADAPTER_CALLS_NOT_OS_SYSCALLS"}, run_id=run_id, scenario=scenario)

    def rejection(self, *, run_id, scenario, accepted, diagnostic, guard_before,
                  guard_after, restored, retained_before, retained_after,
                  sidecars=None, diagnostic_observation=None):
        if not self.enabled:
            raise EvidenceError("RECORDER_DISABLED")
        if scenario not in {"L12-MISSING", "L12-DISABLED", "L12-INVALID"}:
            raise EvidenceError("REJECTION_SCENARIO")
        if set(guard_before) != set(GUARD_NAMES) or set(guard_after) != set(GUARD_NAMES):
            raise EvidenceError("GUARD_COUNTERS_REQUIRED")
        if sidecars is not None:
            # Bytes preserve Lua's byte-oriented :sub(1,240), including a split
            # UTF-8 codepoint. The complete error is a distinct observation.
            if (not isinstance(diagnostic, bytes) or len(diagnostic) > 240
                    or not isinstance(diagnostic_observation, dict)
                    or diagnostic_observation.get("returned_error_hex") != diagnostic.hex()):
                raise EvidenceError("INVALID_REJECTION_DIAGNOSTIC_V2")
            return self.stream.emit("config_rejected", {
                "evidence_schema_version": 2, "bundle_id": sidecars.bundle_id,
                "accepted": accepted, "guard_before": guard_before, "guard_after": guard_after,
                "guard_restored": restored, "retained_origin": "PRIOR_RUN_OR_NO_RUN",
                "retained_before": sidecars.put(retained_before, "retained_snapshot"),
                "retained_after": sidecars.put(retained_after, "retained_snapshot"),
                "diagnostic": sidecars.put(diagnostic_observation, "loader_diagnostic")},
                run_id=run_id, scenario=scenario)
        if diagnostic_observation is not None:
            raise EvidenceError("SIDECAR_REQUIRED")
        # Keep only a bounded missing-file diagnostic or fixed validation token.
        if (not isinstance(diagnostic, str) or len(diagnostic) > 240
                or (scenario == "L12-MISSING" and "ce_mvp_config.local.lua" not in diagnostic)):
            raise EvidenceError("INVALID_REJECTION_DIAGNOSTIC")
        return self.stream.emit("config_rejected", {"accepted": accepted,
            "diagnostic": diagnostic, "guard_before": guard_before, "guard_after": guard_after,
            "guard_restored": restored, "retained_before": retained_before,
            "retained_after": retained_after, "retained_origin": "PRIOR_RUN_OR_NO_RUN"},
            run_id=run_id, scenario=scenario)
