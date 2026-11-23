"""Connection and cryptographic binding failures without OS observations."""
from copy import deepcopy
import pytest

from ce_qualification.native_probe_peer import validate_connection_model, response, verify_mutual_model
from ce_qualification.native_probe_protocol import ProbeError
from native_probe_b0_fakes import peer_fixture, SECRET, CHALLENGES


def test_N03_two_way_proof_and_challenge_are_only_synthetic():
    e, p = peer_fixture()
    proof = validate_connection_model(p, e, handle_ref="model-handle-server")
    replies = {r: response(SECRET, e, proof["proof_sha256"], *CHALLENGES.values(), r) for r in ("CLIENT", "SERVER")}
    assert verify_mutual_model(SECRET, e, proof["proof_sha256"], CHALLENGES, replies) == "SYNTHETIC_MUTUAL_ONLY"


@pytest.mark.parametrize("mutation", ["pid", "pid_bool", "reuse", "image", "component", "sid", "handle", "connection",
    "observer", "query_pid", "query_api", "creation_source", "token_source", "image_source", "component_source",
    "dacl_missing", "null_dacl", "dacl_digest", "dacl_owner", "broad_ace", "generic_write", "inherit", "remote",
    "client_handle", "origin", "authenticated", "same_principal", "security_handle", "query_unknown"])
def test_N03_N08_connection_provenance_and_access_negatives(mutation):
    e, p = peer_fixture(); q = p["queries"]["client"]; s = p["security"]
    if mutation == "pid": p["client"]["pid"] = 999
    elif mutation == "pid_bool": p["client"]["pid"] = True
    elif mutation == "reuse": p["client"]["creation"] = "0000000000000099"
    elif mutation == "image": p["client"]["image_sha256"] = "0" * 64
    elif mutation == "component": p["client"]["component_sha256"] = "0" * 64
    elif mutation == "sid": p["client"]["sid"] = "S-1-5-21-1-9999"
    elif mutation == "handle": q["handle_ref"] = "unrelated-handle"
    elif mutation == "connection": q["connection_id"] = "old-connection"
    elif mutation == "observer": q["observer"] = p["client"]
    elif mutation == "query_pid": q["peer_pid"] = 999
    elif mutation == "query_api": q["api"] = "JSON_PID"
    elif mutation == "creation_source": q["creation_api"] = "CLIENT_CLAIM"
    elif mutation == "token_source": q["token_api"] = "JSON_SID"
    elif mutation == "image_source": q["image_api"] = "FILE_ONLY_NO_PROCESS"
    elif mutation == "component_source": q["component_source"] = "UNVERIFIED"
    elif mutation == "dacl_missing": s["dacl_present"] = False
    elif mutation == "null_dacl": s["null_dacl"] = True
    elif mutation == "dacl_digest": s["descriptor_sha256"] = "0" * 64
    elif mutation == "dacl_owner": s["owner_sid"] = p["client"]["sid"]
    elif mutation == "broad_ace": s["aces"].append({"sid": "S-1-1-0", "mask": 1, "type": "ALLOW", "inherited": False})
    elif mutation == "generic_write": s["client_requested_access"] |= 4
    elif mutation == "inherit": p["inheritable"] = True
    elif mutation == "remote": p["local_only"] = False
    elif mutation == "client_handle": p["client_handle"] = "UNKNOWN"
    elif mutation == "origin": p["origin"] = "NATIVE"
    elif mutation == "authenticated": p["authenticated"] = True
    elif mutation == "same_principal": e["client"]["sid"] = e["server"]["sid"]
    elif mutation == "security_handle": s["handle_ref"] = "unrelated-handle"
    elif mutation == "query_unknown": q["memory_scraped"] = True
    with pytest.raises(ProbeError): validate_connection_model(p, e, handle_ref="model-handle-server")


@pytest.mark.parametrize("field", ["session_id", "channel_id", "epoch", "connection_id", "candidate_sha256",
    "authorization_sha256", "client", "server", "proof", "role", "nonce", "secret"])
def test_N03_challenge_binds_both_endpoints_freeze_authority_and_role(field):
    e, p = peer_fixture(); proof = validate_connection_model(p, e, handle_ref="model-handle-server")["proof_sha256"]
    replies = {r: response(SECRET, e, proof, *CHALLENGES.values(), r) for r in ("CLIENT", "SERVER")}
    secret, challenges = SECRET, deepcopy(CHALLENGES)
    if field in ("client", "server"): e[field]["creation"] = "0000000000000099"
    elif field == "proof": proof = "0" * 64
    elif field == "role": replies["CLIENT"] = replies["SERVER"]
    elif field == "nonce": challenges["client"] = "3" * 64
    elif field == "secret": secret = b"different-public-model-key-xxxxxxxx"
    elif field == "epoch": e[field] += 1
    else: e[field] = "8" * 64 if field.endswith("sha256") else "changed"
    with pytest.raises(ProbeError, match="MUTUAL_CHALLENGE_MISMATCH"):
        verify_mutual_model(secret, e, proof, challenges, replies)
