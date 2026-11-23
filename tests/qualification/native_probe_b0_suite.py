"""R3-A matrix replayed through B0 adapters plus sealed Win32 model traces."""
from pathlib import Path

from ce_qualification.native_probe_protocol import canonical, sha256
from native_probe_suite import build, PLAN
from native_probe_b0_fakes import equipment


def build_adapters(directory, candidate_sha256, authorization_sha256):
    sessions = {}
    def factory(binding, emit_host, emit_lua, clock, **kwargs):
        endpoint = "\\\\.\\pipe\\qsg-r3-" + sha256(binding["session_id"].encode())[:32]
        h, s, p, ce, _, _, events, _, watchdog_events = equipment(open_now=False, binding=binding,
            emit_host=emit_host, emit_lua=emit_lua, owner_clock=clock, endpoint=endpoint)
        s.expected.update(candidate_sha256=candidate_sha256, authorization_sha256=authorization_sha256)
        for key, value in kwargs.items(): setattr(ce, key, value)
        s.open(endpoint, deadline_ms=clock() + 250)
        sessions[binding["session_id"]] = {"events": events, "spec": p.spec, "peer": p.proof,
            "expected": s.expected, "watchdog_events": watchdog_events}
        return h, ce
    seal, observations = build(directory, candidate_sha256, authorization_sha256, transport_factory=factory)
    for session in sessions.values():
        session["watchdog_events"] = [list(event) for event in session["watchdog_events"]]
    raw = canonical({"schema": "qsg.native-probe.adapter-traces.v1", "origin": "SYNTHETIC",
        "candidate_sha256": candidate_sha256, "authorization_sha256": authorization_sha256, "sessions": sessions})
    with (Path(directory) / "adapter-traces.json").open("xb") as out: out.write(raw)
    return seal, sha256(raw), observations


def main():
    import argparse
    import json
    parser = argparse.ArgumentParser(description="B0 synthetic adapters only")
    for name in ("output", "candidate-sha256", "authorization-sha256"): parser.add_argument("--" + name, required=True)
    args = parser.parse_args()
    seal, trace, observations = build_adapters(args.output, args.candidate_sha256, args.authorization_sha256)
    print(json.dumps({"manifest_sha256": seal, "adapter_traces_sha256": trace, "observations": len(observations),
                      "origin": "SYNTHETIC", "native": "NOT_RUN"}))


if __name__ == "__main__": main()
