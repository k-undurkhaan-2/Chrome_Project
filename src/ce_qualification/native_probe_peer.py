"""Connection-specific OS proof contract and bilateral challenge model, no OS calls."""
import hmac
import re

from .native_probe_admission import exact
from .native_probe_protocol import canonical, digest_string, identifier, require, sha256

FILE_READ_DATA = 0x1
FILE_WRITE_DATA = 0x2
FILE_CREATE_PIPE_INSTANCE = 0x4
READ_CONTROL = 0x20000
SYNCHRONIZE = 0x100000
CLIENT_ACCESS = FILE_READ_DATA | FILE_WRITE_DATA | READ_CONTROL | SYNCHRONIZE
SERVER_ACCESS = 0x12019F  # FILE_GENERIC_READ | FILE_GENERIC_WRITE, for server only.
PROCESS_FIELDS = {"pid", "creation", "image_sha256", "component_sha256", "sid"}


def process_identity(value):
    exact(value, PROCESS_FIELDS, "PROCESS_FIELDS")
    require(type(value["pid"]) is int and 0 < value["pid"] <= 0xFFFFFFFF, "PROCESS_PID")
    require(type(value["creation"]) is str and re.fullmatch(r"[0-9A-F]{16}", value["creation"])
            and int(value["creation"], 16) > 0, "PROCESS_CREATION")
    for key in ("image_sha256", "component_sha256"): digest_string(value[key])
    require(type(value["sid"]) is str and re.fullmatch(r"S-1-5-(?:[0-9]+-)*[0-9]+", value["sid"]), "PROCESS_SID")
    require(value["sid"] not in ("S-1-5-7", "S-1-5-11", "S-1-5-18"), "PRINCIPAL_TOO_BROAD")


def validate_connection_model(proof, expected, *, handle_ref):
    """No PID in a wire message is consumed. All identities are provider samples.

    Each query names the observing process, connection and actual modeled handle.
    Samples in this function are SYNTHETIC; runtime query availability NOT_RUN.
    """
    exact(expected, {"session_id", "channel_id", "epoch", "connection_id", "client", "server",
                     "dacl_sha256", "candidate_sha256", "authorization_sha256"}, "PEER_EXPECTED")
    for name in ("session_id", "channel_id", "connection_id"): identifier(expected[name])
    require(type(expected["epoch"]) is int and 1 <= expected["epoch"] <= 2147483647, "PEER_EPOCH")
    for name in ("dacl_sha256", "candidate_sha256", "authorization_sha256"): digest_string(expected[name])
    for role in ("client", "server"): process_identity(expected[role])
    require(expected["client"]["pid"] != expected["server"]["pid"], "PEER_INSTANCE")
    # This least-privilege proposal needs distinguishable principals. Same-token
    # server/client cannot claim separation of create-instance rights.
    require(expected["client"]["sid"] != expected["server"]["sid"], "PRINCIPAL_SEPARATION_UNPROVEN")
    exact(proof, {"origin", "os_evidence", "binding", "client", "server", "queries", "security",
                  "client_handle", "local_only", "inheritable"}, "PEER_FIELDS")
    require(proof["origin"] == "SYNTHETIC" and proof["os_evidence"] == "NOT_RUN", "MOCK_IS_NOT_OS_PROOF")
    binding = {k: expected[k] for k in ("session_id", "channel_id", "epoch", "connection_id")}
    exact(proof["binding"], binding, "CONNECTION_BINDING")
    require(type(proof["binding"]["epoch"]) is int and proof["binding"] == binding, "CONNECTION_BINDING")
    for role in ("client", "server"):
        process_identity(proof[role])
        require(proof[role] == expected[role], "PEER_IDENTITY_MISMATCH")
    require(proof["local_only"] is True and proof["inheritable"] is False, "PIPE_ISOLATION")
    require(proof["client_handle"] == "PROCESS_OWNED_VERIFIED_MODEL", "CLIENT_HANDLE_UNVERIFIED")
    identifier(handle_ref)
    exact(proof["queries"], {"client", "server"}, "QUERY_FIELDS")
    for peer, observer, api in (("client", "server", "GetNamedPipeClientProcessId"),
                                ("server", "client", "GetNamedPipeServerProcessId")):
        query = proof["queries"][peer]
        exact(query, {"api", "handle_ref", "connection_id", "observer", "peer_pid", "process_handle_ref",
                      "creation_api", "token_api", "image_api", "component_source"}, "QUERY_PROVENANCE")
        require(query["api"] == api and query["connection_id"] == expected["connection_id"]
                and query["observer"] == expected[observer] and type(query["peer_pid"]) is int
                and query["peer_pid"] == expected[peer]["pid"], "QUERY_PROVENANCE")
        identifier(query["handle_ref"]); identifier(query["process_handle_ref"])
        if peer == "client": require(query["handle_ref"] == handle_ref, "HANDLE_BINDING")
        require(query["creation_api"] == "GetProcessTimes(held-process-handle)"
                and query["token_api"] == "GetTokenInformation(TokenUser,held-process-token)"
                and query["image_api"] == "QueryFullProcessImageName+file-sha256"
                and query["component_source"] == "PINNED_LOADED_COMPONENT_MODEL", "QUERY_PROVENANCE")
    security = proof["security"]
    exact(security, {"api", "handle_ref", "connection_id", "owner_sid", "dacl_present", "null_dacl",
                     "protected", "descriptor_sha256", "aces", "client_requested_access"}, "DACL_FIELDS")
    require(security["api"] == "GetSecurityInfo(SE_KERNEL_OBJECT)" and security["handle_ref"] == handle_ref
            and security["connection_id"] == expected["connection_id"], "DACL_PROVENANCE")
    require(security["dacl_present"] is True and security["null_dacl"] is False
            and security["protected"] is True and security["owner_sid"] == expected["server"]["sid"], "DACL_UNPROVEN")
    require(security["descriptor_sha256"] == expected["dacl_sha256"], "DACL_DIGEST")
    aces = [{"sid": expected["server"]["sid"], "mask": SERVER_ACCESS, "type": "ALLOW", "inherited": False},
            {"sid": expected["client"]["sid"], "mask": CLIENT_ACCESS, "type": "ALLOW", "inherited": False}]
    require(type(security["aces"]) is list and len(security["aces"]) == 2, "DACL_ACCESS")
    for ace in security["aces"]:
        exact(ace, {"sid", "mask", "type", "inherited"}, "DACL_ACCESS")
        require(type(ace["mask"]) is int and ace["inherited"] is False, "DACL_ACCESS")
    require(security["aces"] == aces, "DACL_ACCESS")
    require(type(security["client_requested_access"]) is int
            and security["client_requested_access"] == CLIENT_ACCESS, "CLIENT_ACCESS_UNPROVEN")
    return {"status": "SYNTHETIC_PEER_ONLY", "proof_sha256": sha256(canonical(proof)),
            "binding_sha256": sha256(canonical(expected))}


def response(secret, expected, proof_sha256, client_challenge, server_challenge, role):
    """Both endpoint identities, freeze and authority digests enter both MACs."""
    require(type(secret) is bytes and len(secret) >= 32, "SECRET")
    require(role in ("CLIENT", "SERVER"), "ROLE")
    for value in (proof_sha256, client_challenge, server_challenge): digest_string(value)
    require(client_challenge != server_challenge, "CHALLENGE_REUSE")
    return hmac.new(secret, canonical({"schema": "qsg.native-probe.binding.v1", "binding": expected,
        "proof_sha256": proof_sha256, "client_challenge": client_challenge,
        "server_challenge": server_challenge, "role": role}), "sha256").hexdigest()


def verify_mutual_model(secret, expected, proof_sha256, challenges, replies):
    exact(challenges, {"client", "server"}, "CHALLENGES")
    exact(replies, {"CLIENT", "SERVER"}, "CHALLENGE_REPLIES")
    for role in ("CLIENT", "SERVER"):
        digest_string(replies[role])
        require(hmac.compare_digest(replies[role], response(secret, expected, proof_sha256,
            challenges["client"], challenges["server"], role)), "MUTUAL_CHALLENGE_MISMATCH")
    return "SYNTHETIC_MUTUAL_ONLY"
