"""Independent offline QSG verifier. Imports no broker, gate or writer code.

Reconstructs consumption, claims, CE dispatch/readback and independent target
samples from sealed source records. Missing observations cannot produce PASS.
The live axis is always NOT_RUN, regardless of any controller status string.
"""
from collections import Counter, defaultdict
import re
import struct

from .evidence import canonical, decode, digest, validate_chain, EvidenceError
from .verifier import load_sidecars, l12_payload


def need(ok, code):
    if not ok:
        raise EvidenceError(code)


def chained(rows, schema, clock_key):
    previous, last = "0"*64, -1
    for i, row in enumerate(rows, 1):
        expected = ({"schema","origin","sequence","clock_ms","kind","data","previous","digest"} if schema == "qsg.store.v1"
                    else {"schema","origin","source","session_id","sequence","clock_origin","clock_ms","kind","body","previous","digest"})
        need(set(row) == expected, "SOURCE_SCHEMA")
        need(row["schema"] == schema and row["origin"] == "SYNTHETIC", "ORIGIN_OR_SCHEMA")
        need(type(row["sequence"]) is int and row["sequence"] == i and row["previous"] == previous, "SEQUENCE_OR_CHAIN")
        need(row["digest"] == digest({k:v for k,v in row.items() if k != "digest"}), "SOURCE_DIGEST")
        now = int(row[clock_key])
        need(now >= last, "CLOCK_REVERSED")
        previous, last = row["digest"], now


def verify(bundle, expected_digest, *, requested=("L04",), sidecar_directory=None):
    result = {"schema": "qsg.verification.v1", "origin": "DERIVED", "status": "SYNTHETIC_INCONCLUSIVE",
        "synthetic": {k: "NOT_RUN" for k in requested}, "live": {f"L{i:02}": "NOT_RUN" for i in range(1,13)},
        "g1_live": "NOT_APPROVED", "consumed_attempts": 0, "dispatch_boundaries": 0,
        "errors": [], "missing": [], "limitations": ["ATTACHMENT_HANDLE_UNVERIFIED", "NOT_PRODUCTION_AUTHORIZED",
        "Native IPC/peer binding and physical power loss NOT_RUN", "Independent retained seal required",
        "Target snapshots do not identify the writer or exclude transient writes"]}
    try:
        need(digest(bundle) == expected_digest, "EXTERNAL_SEAL_MISMATCH")
        v2 = "schema" in bundle
        need(set(bundle) == {"policy", "broker", "qsg", "ce", "target", "raw_spy"}
             | ({"schema", "sidecars"} if v2 else set()), "BUNDLE_SCHEMA")
        need(not v2 or bundle["schema"] == "qsg.bundle.v2", "BUNDLE_VERSION")
        policy = bundle["policy"]
        need(policy["origin"] == "SYNTHETIC" and 0 < int(policy["end_ms"])-int(policy["start_ms"]) <= 3600000, "POLICY")
        broker, qsg, ce, target = (bundle[k] for k in ("broker", "qsg", "ce", "target"))
        chained(broker, "qsg.store.v1", "clock_ms"); chained(qsg, "qsg.event.v1", "clock_ms")
        validate_chain(ce, source="ce", session_id=policy["session_id"])
        resolved_l12 = load_sidecars(ce, bundle.get("sidecars"), sidecar_directory)
        for source in {r["source"] for r in target}:
            need(source in {"target-A","target-B"}, "TARGET_SOURCE")
            validate_chain([r for r in target if r["source"]==source], source=source, session_id=policy["session_id"])
        need(all(r["origin"] == "SYNTHETIC" for r in ce+target), "LIVE_PROMOTION")
        targets = {t["allocation_id"]:t for t in policy["targets"]}
        need(1 <= len(targets) <= 9, "INSTANCE_CAP")
        for t in targets.values():
            need(t["size"] == "65536" and t["fresh"] is True and t["owned"] is True, "ALLOCATION_SCOPE")
            need(re.fullmatch(r"[0-9A-F]{16}", t["identity"]["creation"]) and int(t["identity"]["creation"],16)>0, "IDENTITY")
            need(set(t["provenance"]) == {"image_sha256", "script_sha256", "layout_sha256", "provider_sha256"}
                and all(re.fullmatch(r"[0-9a-f]{64}", v) for v in t["provenance"].values()), "PROVENANCE")
        target_index = {r["content_digest"]:r for r in target}
        allocations = {r["data"]["allocation_id"]:r for r in target if r["kind"] == "allocation"}
        for r in target:
            t = targets[r["data"]["allocation_id"]]
            need(r["data"]["identity"] == t["identity"] and r["source"]=='target-'+t['identity']['designation'], "TARGET_IDENTITY")
        starts, stopped, phases, reserves, claims, outcomes, verifications, retires = {},set(),{},{},{},{},{},[]
        totals, operations, checkpoints = Counter(),set(),set()
        last_operation = 0
        for row in broker:
            kind, d = row["kind"], row["data"]
            need(kind in {"start", "phase", "reserve", "claim", "outcome", "verified", "retire", "monitor", "stop", "failed"}, "BROKER_KIND")
            if kind == "start":
                run = d["run_id"]
                need(run not in starts and not set(starts)-stopped and len(starts)<9, "RUN_OVERLAP_OR_CAP")
                need(d["lease"]["generation"] == len(starts)+1, "RUN_GENERATION")
                starts[run] = row
            elif kind == "phase":
                run = d["lease"]["run_id"]
                need(run in starts and run not in stopped and d["lease"] == starts[run]["data"]["lease"], "PHASE_RUN")
                need(d["phase_sequence"] == (phases[run]["data"]["phase_sequence"]+1 if run in phases else 1), "PHASE_SEQUENCE")
                if run in phases:
                    order = ["L02", "L03", "L04", "L05", "L06", "L07", "L08"]
                    old = phases[run]["data"]["phase"]
                    need(old in order[:-1] and d["phase"] == order[order.index(old)+1], "PHASE_TRANSITION")
                phases[run] = row
            elif kind == "reserve":
                run = d["lease"]["run_id"]; phase = d["phase"]
                need(run in starts and run not in stopped and d["lease"] == starts[run]["data"]["lease"], "RESERVATION_RUN")
                need(phase in {"L04", "L07", "L10"} and d["phase_sequence"] == phases[run]["data"]["phase_sequence"]
                    and phase == phases[run]["data"]["phase"], "ZERO_PHASE_OR_SEQUENCE")
                need(d["session_id"] == policy["session_id"] and d["authorization_id"] == policy["authorization_id"], "SESSION_BINDING")
                scope = policy["targets"][d["lease"]["target"]]
                need(d["scope"] == scope and scope["identity"]["designation"] == "A", "SCOPE_CHANGED")
                identity = scope["identity"]
                need(d["ce_token"] == f"{identity['pid']}:{identity['creation']}", "CE_IDENTITY")
                address, base = int(d["address"]),int(scope["base"])
                need(address%4 == 0 and 32 <= address-base <= 65452 and int(d["offset"]) == address-base, "ADDRESS_SCOPE")
                need(d["bits"] == "0x42FA0000", "WRITE_BITS")
                need(int(policy["start_ms"]) <= row["clock_ms"] < int(policy["end_ms"])
                    and 0 <= row["clock_ms"]-phases[run]["clock_ms"] < 300000 and row["clock_ms"] < int(d["deadline_ms"]), "RESERVATION_TIME")
                op = int(d["operation_id"])
                need(op > last_operation and d["nonce"] not in operations, "OPERATION_REPLAY")
                operations.add(d["nonce"]); last_operation = op
                cp = decode(d["checkpoint"])
                need(cp["content_digest"] not in checkpoints, "CHECKPOINT_REPLAY")
                checkpoints.add(cp["content_digest"])
                if cp["content_digest"] not in target_index: result["missing"].append("TARGET_PRE_MISSING")
                else: need(cp == target_index[cp["content_digest"]], "TARGET_PRE_CHANGED")
                need(cp["run_id"] == run and cp["scenario"] == phase and cp["data"]["address"] == address
                    and cp["data"]["identity"] == identity and cp["data"]["allocation_id"] == scope["allocation_id"]
                    and cp["data"]["bits"] == "0x42C80000" and cp["data"]["anchor_id"] == d["nonce"], "CHECKPOINT_BINDING")
                need(scope["allocation_id"] in allocations, "ALLOCATION_MISSING")
                allocation = allocations[scope["allocation_id"]]["data"]
                need(allocation["base"] == base and allocation["size"] == 65536 and allocation["owner"] == d["ce_token"], "ALLOCATION_CHANGED")
                need(not any(r["allocation_id"] == scope["allocation_id"] and r["address"] == d["address"] for r in retires), "RETIRED_DISPATCH")
                if phase == "L07":
                    old = [r for r in reserves.values() if r["data"]["lease"] == d["lease"] and r["data"]["phase"] == "L04"]
                    need(len(old) == 1 and old[0]["data"]["address"] != d["address"] and any(r["address"] == old[0]["data"]["address"] and r["lease"] == d["lease"] for r in retires), "RECOVERY_RETIREMENT")
                reserves[row["digest"]] = row; totals[phase] += 1
                need(len(reserves)<=3 and totals["L04"]+totals["L07"]<=2 and all(totals[k]<=1 for k in totals), "BUDGET_CAP")
            elif kind == "claim":
                aid = d["attempt"]
                need(aid in reserves and aid not in claims and d["request_digest"] == digest(reserves[aid]["data"]), "CLAIM_WITHOUT_UNIQUE_RESERVATION")
                need(d["lease"] == reserves[aid]["data"]["lease"] and d["lease"]["run_id"] not in stopped
                    and row["clock_ms"] < int(d["expires_ms"]) <= int(reserves[aid]["data"]["deadline_ms"]), "CLAIM_BINDING_OR_TIME")
                claims[aid] = row
            elif kind == "outcome":
                need(d["attempt"] in claims and d["attempt"] not in outcomes, "UNCLAIMED_OR_DUPLICATE_OUTCOME")
                outcomes[d["attempt"]] = row
            elif kind == "verified":
                need(d["attempt"] in outcomes and outcomes[d["attempt"]]["data"]["result"] == "TRUE" and d["attempt"] not in verifications, "UNRETURNED_VERIFICATION")
                verifications[d["attempt"]] = row
            elif kind == "retire":
                need(d["target_digest"] in target_index and target_index[d["target_digest"]]["kind"] == "retire"
                    and target_index[d["target_digest"]]["data"]["address"] == int(d["address"]), "RETIRE_TARGET")
                retires.append(d)
            elif kind == "stop":
                need(d["run_id"] in starts and d["run_id"] not in stopped, "STOP_SEQUENCE")
                stopped.add(d["run_id"])
            elif kind == "failed": result["missing"].append("SESSION_FAILED_CLOSED")
        result["consumed_attempts"] = len(reserves)
        diagnostics, snapshots = defaultdict(dict), {}
        guard_names={'openProcess','createMemScan','readInteger','readFloat','writeFloat','createTimer','executeCodeLocalEx','createMemoryStream'}
        for row in ce:
            if row["kind"] == "ce_event":
                e = row["data"]["diagnostic"]; run = row["run_id"]
                need(e["sequence"] == len(diagnostics[run])+1 and e["source"] == "synthetic", "CORE_SEQUENCE")
                diagnostics[run][e["sequence"]] = row
            elif row["kind"] == "ce_snapshot":
                d = row["data"]; run = row["run_id"]
                need(all(type(v) is int and v>=0 for v in d['counters'].values()), 'SNAPSHOT_COUNTER_TYPES')
                need(d["ce_embedded_lua"] == "NOT_RUN" and d["last_sequence"] == len(diagnostics[run]), "SNAPSHOT_SEQUENCE")
                if run in snapshots:
                    old = snapshots[run]
                    need(all(d["counters"][k]>=v for k,v in old["counters"].items() if k != "invalid_count"), "SNAPSHOT_COUNTER_ROLLBACK")
                snapshots[run] = d
            else: need(row["kind"] in {"config_rejected", "load_observation", "phase_boundary", "target_switch"}, "CE_EVENT_KIND")
        dispatched, returned, verified, bound_candidates = {},{},{},{}
        qsg_keys = {"READY":{"policy_digest"}, "CANDIDATE":{"address","mapping","fields","rank_sequence","population_sequence","alias","qualified_count","hard_pass","recommendation","raw_count","scanned_count","filtered_count","selected_count"},
            "PERMIT_REQUEST":{"request_digest","operation_id"}, "RESERVATION":{"attempt","request_digest","receipt_kind"},
            "RAW_DISPATCH":{"attempt","receipt","address","bits"}, "RAW_RETURN":{"attempt","result"},
            "VERIFIED":{"attempt","address","bits","core_sequence","target","readback"}, "FAILED_CLOSED":{"code"}}
        for row in qsg:
            body,kind = row["body"],row["kind"]; d = body["data"]
            need(set(body) == {"lease","phase","data"}, "QSG_BODY_SCHEMA")
            need(row["session_id"] == policy["session_id"] and row["source"] == "ce-qsg" and row["clock_origin"] == "synthetic-ce-ms", "QSG_IDENTITY")
            need(kind in qsg_keys and set(d) == qsg_keys[kind], "QSG_PAYLOAD_SCHEMA")
            run=body['lease']['run_id']
            need(run in starts and body['lease']==starts[run]['data']['lease'], 'QSG_RUN_BINDING')
            if kind=='READY': need(d['policy_digest']==digest(policy), 'QSG_POLICY_BINDING')
            if kind=='CANDIDATE':
                key=(run,d['rank_sequence'])
                need(key not in bound_candidates, 'DUPLICATE_CANDIDATE_BINDING')
                bound_candidates[key]=d
            if kind == "RAW_DISPATCH":
                aid = d["attempt"]
                need(aid in claims and aid not in dispatched, "UNRESERVED_OR_DUPLICATE_RAW")
                req = reserves[aid]["data"]
                need(body["lease"] == req["lease"] and body["phase"] == req["phase"] and d["receipt"] == claims[aid]["digest"]
                    and d["address"] == req["address"] and d["bits"] == req["bits"], "RAW_BINDING")
                dispatched[aid] = row
            elif kind == "RAW_RETURN":
                aid = d["attempt"]
                need(aid in dispatched and aid not in returned, "RETURN_ORDER")
                if aid not in outcomes: result["missing"].append("BROKER_OUTCOME_MISSING")
                else: need(outcomes[aid]["data"]["event_digest"] == row["digest"] and outcomes[aid]["data"]["result"] == d["result"], "OUTCOME_CONTRADICTION")
                returned[aid] = row
            elif kind == "VERIFIED":
                aid = d["attempt"]
                need(aid in returned and returned[aid]["body"]["data"]["result"] == "TRUE" and aid not in verified, "VERIFIED_ORDER")
                req = reserves[aid]["data"]; run = req["lease"]["run_id"]
                cp = decode(d["target"]); pre = decode(req["checkpoint"])
                if cp["content_digest"] not in target_index: result["missing"].append("TARGET_POST_MISSING")
                else: need(cp == target_index[cp["content_digest"]], "TARGET_POST_CHANGED")
                need(cp["sequence"] > pre["sequence"] and cp["data"]["attempt_id"] == aid
                    and cp['run_id']==run and cp['scenario']==req['phase'] and cp['kind']=='checkpoint'
                    and cp["data"]["bits"] == d["bits"] == req["bits"] and str(cp["data"]["address"]) == d["address"] == req["address"]
                    and cp["data"]["identity"] == req["scope"]["identity"] and cp["data"]["allocation_id"] == req["scope"]["allocation_id"], "TWO_SIDED_DISAGREEMENT")
                e = diagnostics[run].get(d["core_sequence"])
                if e is None: result["missing"].append("CORE_VERIFIED_MISSING")
                else:
                    e = e["data"]["diagnostic"]
                    need(e["event_type"] == "readback_verified" and e["readback_bits"] == e["float_bits"] == e["write_intent_bits"] == req["bits"], "CORE_BITS")
                rb = d["readback"]
                need(rb["bits"] == int(req["bits"],16) and rb["address"] == int(req["address"])
                    and struct.unpack("<I",struct.pack("<f",rb["value"]))[0] == rb["bits"], "ADAPTER_READBACK_BITS")
                if aid not in verifications: result["missing"].append("BROKER_VERIFIED_MISSING")
                else: need(verifications[aid]["data"]["evidence_digest"] == row["digest"], "VERIFIED_ANCHOR")
                verified[aid] = row
        for aid, r in reserves.items():
            d = r["data"]; c = d["candidate"]; es = diagnostics[d["lease"]["run_id"]]
            need(bound_candidates.get((d['lease']['run_id'],c['rank_sequence']))=={k:v for k,v in c.items() if k!='intent_sequence'}, 'CANDIDATE_SIDECAR_BINDING')
            for field,kind in (("rank_sequence","ranking_summary"),("population_sequence","candidate_population"),("intent_sequence","write_intent")):
                need(c[field] in es and es[c[field]]["data"]["diagnostic"]["event_type"] == kind, "CANDIDATE_CORE_ANCHOR")
            rank,pop,intent = (es[c[k]]["data"]["diagnostic"] for k in ("rank_sequence","population_sequence","intent_sequence"))
            need(rank["qualified_count"] == c["qualified_count"] == 1 and rank["hard_pass"] is True and rank["recommendation"] == "ACCEPT"
                and rank["address_label"] == intent["address_label"] == c["alias"] and intent["write_intent_bits"] == d["bits"], "CANDIDATE_RANK")
            need(pop["collection_complete"] is True and pop["read_failure"] is False
                and all(pop[k] == c[k] for k in ("raw_count","scanned_count","filtered_count","selected_count")), "CANDIDATE_POPULATION")
        for run, es in diagnostics.items():
            intents = [e for e in es.values() if e["data"]["diagnostic"]["event_type"] == "write_intent"]
            if es:
                final = es[max(es)]["data"]["diagnostic"]
                need(final["counters"]["adapter_write_attempts"] == len(intents), "INTENT_COUNTER_DISAGREEMENT")
            if len(intents) != sum(r["data"]["lease"]["run_id"] == run for r in reserves.values()):
                result["missing"].append("DENIED_OR_UNRESOLVED_PORT_ENTRY")
        result["dispatch_boundaries"] = len(dispatched)
        need(len(bundle["raw_spy"]) <= len(dispatched), "RAW_SPY_BYPASS")
        if len(bundle["raw_spy"]) != len(dispatched): result["missing"].append("PRECALL_WITHOUT_OBSERVED_RAW")
        for spy,row in zip(bundle["raw_spy"],dispatched.values()):
            need(str(spy["address"]) == row["body"]["data"]["address"] and spy["value"] == 125.0
                and spy["reserves"] >= 1 and spy["claims"] >= 1, "RAW_SPY_DISAGREEMENT")
        if set(reserves) != set(verified): result["missing"].append("CONSUMED_ATTEMPT_WITHOUT_COMPLETE_VERIFICATION")
        if set(starts) != stopped: result["missing"].append("CLEANUP_NOT_OBSERVED")
        def case_events(case, kind=None):
            return [r['data']['diagnostic'] for r in ce if r['kind']=='ce_event' and r['scenario']==case
                    and (kind is None or r['data']['diagnostic']['event_type']==kind)]
        def prove(case, condition):
            if condition: result['synthetic'][case]='SYNTHETIC_PASS'
        for case in requested:
            if case in {"L04","L07","L10"}:
                if sum(reserves[a]["data"]["phase"] == case for a in verified) == 1: result["synthetic"][case] = "SYNTHETIC_PASS"
            elif case in {"L05","L06"}:
                records = [r for r in ce if r["kind"] == "ce_event" and r["scenario"] == case]
                monitors = [r for r in records if r["data"]["diagnostic"]["event_type"] == "monitor_result"]
                if len(monitors) < (20 if case == "L05" else 3): continue
                need(len({r["run_id"] for r in monitors}) == 1, "MONITORS_SPAN_RESTART")
                counts = [r["data"]["diagnostic"]["counters"]["monitor_checks"] for r in monitors]
                need(counts == list(range(counts[0],counts[0]+len(counts))) and all(r["data"]["diagnostic"]["valid"] is True for r in monitors), "MONITOR_GAP")
                for key in ("scan_count","write_count","verified_writes"):
                    need(len({r["data"]["diagnostic"]["counters"][key] for r in records}) == 1, "MONITOR_REWRITE")
                if case == "L06":
                    values = [r["data"]["diagnostic"]["value_bits"] for r in records if r["data"]["diagnostic"]["event_type"] == "valid_value_observed"]
                    need(len(values)>=3 and set(values)=={"0x42280000"}, "DRIFT_BITS")
                result["synthetic"][case] = "SYNTHETIC_PASS"
            elif case=='L01':
                loads=[r['data'] for r in ce if r['kind']=='load_observation']
                prove(case,len(loads)==1 and loads[0]['state']=='STOPPED' and loads[0]['ct_lua_syntax_blocks']==4
                    and loads[0]['guard_restored'] is True and loads[0]['config_loaded'] is False
                    and loads[0]['ce_embedded_lua']=='NOT_RUN' and set(loads[0]['attempted_calls'])==guard_names
                    and all(type(v) is int and v==0 for v in loads[0]['attempted_calls'].values()))
            elif case=='L02':
                bound=case_events(case,'identity_bound')
                prove(case,bool(bound) and any(bound[0]['identity_token']==a['data']['owner'] for a in allocations.values()))
            elif case=='L03':
                prove(case,any(e.get('raw_match_count')==1 and e.get('scan_complete') is True for e in case_events(case,'scan_population_complete'))
                    and any(e.get('qualified_count')==1 and e.get('recommendation')=='ACCEPT' and e.get('hard_pass') is True for e in case_events(case,'ranking_summary'))
                    and any(e.get('collection_complete') is True for e in case_events(case,'candidate_population')))
            elif case=='L08':
                es=case_events(case)
                prove(case,bool(es) and any(e.get('cleanup_ok') is True and e.get('reason') in {'PID_EXITED','PID_EXITED_OR_UNCERTAIN','IDENTITY_UNCERTAIN'} for e in case_events(case,'cleanup_complete'))
                    and len({e['counters']['adapter_write_attempts'] for e in es})==1 and not case_events(case,'write_intent'))
            elif case=='L09':
                complete=True
                for mode,count in [('zero',0),('ambiguous',2),('129_plus',129),('incomplete',1),('invalid',1)]:
                    sub='L09-'+mode; es=case_events(sub); pops=case_events(sub,'scan_population')
                    modes=[r for r in target if r['kind']=='mode' and r['scenario']==sub and r['data']['mode']==mode]
                    if not es or not pops or not modes:
                        complete=False; continue
                    need(pops[0]['raw_match_count']==count and pops[0]['hard_limit']==pops[0]['configured_limit']==128
                        and modes[0]['data']['synthetic_match_count']==count, 'L09_POPULATION')
                    need(all(e['counters']['adapter_write_attempts']==0 for e in es), 'L09_WRITE')
                    if mode=='ambiguous': need(any(e.get('qualified_count')==2 for e in case_events(sub,'ranking_summary')), 'L09_AMBIGUITY')
                    if mode=='129_plus': need(bool(case_events(sub,'scan_population_blocked')), 'L09_OVERFLOW')
                    if mode=='incomplete': need(any(e.get('read_failure') is True for e in case_events(sub,'candidate_population')), 'L09_INCOMPLETE')
                    if mode=='invalid': need(any(e.get('qualified_count')==0 for e in case_events(sub,'ranking_summary')), 'L09_INVALID')
                prove(case,complete)
            elif case=='L11':
                switches=[r for r in ce if r['kind']=='target_switch']
                if len(switches)!=1: continue
                sw=switches[0]['data']
                need(sw['from']!=sw['to'] and sw['to']['designation']=='B', 'L11_TARGETS')
                need(any(t['identity']==sw['from'] for t in targets.values()) and any(t['identity']==sw['to'] and t['phases']==['L11'] for t in targets.values()), 'L11_UNAPPROVED_TARGET')
                need(all(sw['before'][k]==sw['after'][k] for k in ('adapter_read_calls','adapter_write_attempts','adapter_scan_invocations')), 'L11_POSTSWITCH_ACCESS')
                prove(case,any(e.get('reason')=='CE_TARGET_CHANGED' and e.get('cleanup_ok') is True for e in case_events(case,'cleanup_complete'))
                    and any(r['kind']=='checkpoint' and r['scenario']==case and r['data']['identity']==sw['to'] and r['data']['bits']=='0x42C80000' for r in target))
            elif case=='L12':
                records=[r for r in ce if r['kind']=='config_rejected']
                names={'L12-MISSING','L12-DISABLED','L12-INVALID'}
                if len(records)!=3 or {r['scenario'] for r in records}!=names or len({r['run_id'] for r in records})!=3: continue
                for r in records:
                    d=resolved_l12[r['event_id']] if 'evidence_schema_version' in r['data'] else l12_payload(r)
                    need(d['accepted'] is False and d['guard_restored'] is True and d['retained_before']==d['retained_after']
                        and d['retained_origin']=='PRIOR_RUN_OR_NO_RUN', 'L12_ACTIVITY')
                    need(all(set(d[k])==guard_names and all(type(v) is int and v==0 for v in d[k].values()) for k in ('guard_before','guard_after')), 'L12_GUARD_ACTIVITY')
                    if r['scenario']=='L12-MISSING': need('ce_mvp_config.local.lua' in d['diagnostic'] and 'MISSING_CONFIG' not in d['diagnostic'], 'L12_MISSING_DIAGNOSTIC')
                    else: need(d['diagnostic']==('WRITE_DISABLED' if r['scenario']=='L12-DISABLED' else 'INVALID_SCAN_SETTINGS'), 'L12_DIAGNOSTIC')
                prove(case,True)
        # L10's write alone is insufficient when a full session is requested.
        if 'L10' in requested and len(requested)>5:
            rejects={e.get('reason') for e in case_events('L10','start_rejected')}
            boundaries=[r['data'] for r in ce if r['kind']=='phase_boundary' and r['scenario']=='L10']
            ok={'ALREADY_RUNNING','CLEANUP_IN_PROGRESS'}<=rejects and len(boundaries)==2
            ok=ok and all(d['before']==d['after'] and d['completed_wait_intervals']>=3 for d in boundaries)
            ok=ok and len(case_events('L10','cleanup_complete'))==2 and any(e.get('raw_match_count')==0 for e in case_events('L10','scan_population'))
            if not ok: result['synthetic']['L10']='NOT_RUN'
        if len(requested)==12:
            cleaned={r['data']['allocation_id'] for r in target if r['kind']=='cleanup' and r['data']['released'] is True}
            if cleaned != set(allocations): result['missing'].append('TARGET_CLEANUP_NOT_OBSERVED')
        if result["missing"]:
            result["synthetic"] = {k:"NOT_RUN" for k in requested}
        elif all(v == "SYNTHETIC_PASS" for v in result["synthetic"].values()): result["status"] = "SYNTHETIC_PASS"
        return result
    except (OSError,ValueError,TypeError,KeyError,IndexError,OverflowError,struct.error) as exc:
        result["status"] = "SYNTHETIC_FAIL"; result["errors"].append(str(exc))
        result["synthetic"] = {k:"SYNTHETIC_FAIL" for k in requested}
        return result


def main(argv=None):
    """Read-only CLI: explicitly pinned synthetic input, no live/backend switch."""
    import argparse
    import json
    from pathlib import Path
    parser = argparse.ArgumentParser(description="Independently verify sealed QSG synthetic evidence")
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--canonical-sha256", required=True)
    parser.add_argument("--case", action="append", choices=[f"L{i:02}" for i in range(1,13)])
    parser.add_argument("--sidecar-directory", type=Path, help="Designated bounded v2 sidecar root")
    args = parser.parse_args(argv)
    result = verify(decode(args.bundle.read_bytes()), args.canonical_sha256,
        requested=args.case or ["L04"], sidecar_directory=args.sidecar_directory)
    print(json.dumps(result, indent=2, sort_keys=True))
    return {"SYNTHETIC_PASS":0,"SYNTHETIC_FAIL":1,"SYNTHETIC_INCONCLUSIVE":2}[result["status"]]


if __name__ == "__main__":
    raise SystemExit(main())
