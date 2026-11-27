"""Data-only manual-export loading for the existing caller-owned Lua runtime.

No target APIs, evaluation, executable dataset loading, or label reads.
SPDX-License-Identifier: GPL-3.0-only
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _json(text):
    def invalid_constant(value):
        raise ValueError(f"nonfinite JSON number: {value}")
    return json.loads(text, object_pairs_hook=_unique_object, parse_constant=invalid_constant)


def _word_map(value):
    if not isinstance(value, dict):
        raise ValueError("word map must be an object")
    result = {}
    for key, word in value.items():
        address = int(key)
        if str(address) != key or not 1 <= address <= 2**53 - 1:
            raise ValueError("invalid word-map identity")
        result[address] = word
    return result


def _integer(value, low, high):
    return type(value) is int and low <= value <= high


def _check_replay_records(records, counts):
    """Reconcile actual observations, not only the manifest's disposition."""
    seen, words = {}, {}
    duplicates = unavailable = 0
    offsets = (-0x20, -0x10, -8, 0, 0x30, 0x40, 0x48, 0x50)
    relevant = set()
    for record in records:
        address = record.get("addr")
        if (not _integer(address, 1, 2**53 - 1) or type(record.get("mapped")) is not bool
                or not _integer(record.get("protect"), 0, 2**32 - 1)
                or not isinstance(record.get("memory"), dict)):
            raise ValueError("missing or invalid replay record schema")
        relevant.update(address + offset for offset in offsets)
        memory = record["memory"]
        for key, value in memory.items():
            if not _integer(value, 0, 2**32 - 1):
                raise ValueError("invalid observation word")
            if record["mapped"]:
                if key in words and words[key] != value:
                    raise ValueError("conflicting observation word")
                words[key] = value
        for key, value in record.get("unavailable", {}).items():
            if value is not True or key in memory:
                raise ValueError("invalid unavailable observation")
            unavailable += 1
        if address in seen:
            previous = seen[address]
            duplicates += 1
            if any(previous[key] != record[key] for key in ("mapped", "protect", "memory")):
                raise ValueError("conflicting duplicate")
        else:
            seen[address] = record
    for record in records:
        missing = record.get("unavailable", {})
        if not set(record["memory"]).union(missing).issubset(relevant):
            raise ValueError("observation outside supplied contract")
        if record["mapped"]:
            if set(missing).intersection(words):
                raise ValueError("unavailable observation conflicts with supplied word")
            if any(record["addr"] + offset not in words and record["addr"] + offset not in missing
                   for offset in offsets):
                raise ValueError("undeclared missing observation")
    if counts["duplicate_occurrences"] != duplicates or counts["unavailable_words"] != unavailable:
        raise ValueError("observation accounting mismatch")


def load_inventory(manifest_path):
    """Verify bytes and counts; preserve every occurrence, including incomplete ones."""
    path = Path(manifest_path)
    if not path.name.endswith(".manifest.json"):
        raise ValueError("a published manifest is required")
    manifest = _json(path.read_bytes())
    if manifest.get("format") != "MVP0_MANUAL_EXPORT" or manifest.get("version") != 1:
        raise ValueError("unsupported export format")
    if manifest.get("outcome") not in {"REPLAY_READY", "ADDRESS_ONLY", "INCOMPLETE"}:
        raise ValueError("unsuccessful export")
    identity = manifest["dataset_id"]
    prefix = f"manual-export-{identity}"
    if path.name != prefix + ".manifest.json":
        raise ValueError("manifest identity mismatch")
    info = manifest["records"]
    if info["file"] != prefix + ".records.jsonl" or Path(info["file"]).name != info["file"]:
        raise ValueError("records file identity mismatch")
    data = (path.parent / info["file"]).read_bytes()
    if info["hash_algorithm"] != "MD5" or hashlib.md5(data).hexdigest() != info["hash"]:
        raise ValueError("records checksum mismatch")
    if len(data) != info["bytes"] or (data and not data.endswith(b"\n")):
        raise ValueError("records size/framing mismatch")
    records = [_json(line) for line in data.splitlines()]
    counts = manifest["counts"]
    if not (len(records) == info["count"] == counts["source_count"] == counts["exported_count"]):
        raise ValueError("population count mismatch")
    for record in records:
        if not isinstance(record, dict) or set(record) - {"addr", "mapped", "protect", "memory", "unavailable"}:
            raise ValueError("invalid record fields")
        for key in ("memory", "unavailable"):
            if key in record:
                record[key] = _word_map(record[key])
    return manifest, records


def load_replay(manifest_path, lua):
    """Return (records, options, manifest); AC5/AC6 still owns scoring validation.

    This function deliberately has no labels argument and never opens labels_file.
    The caller explicitly chooses bounded/full options and retains resource limits.
    """
    manifest, records = load_inventory(manifest_path)
    expected = manifest["expected_source_count"]
    if (manifest["outcome"] != "REPLAY_READY"
            or manifest["inventory_complete"] is not True
            or manifest["replay_observations_complete"] is not True
            or manifest["supplied_population_exported"] is not True
            or manifest["population_basis"] != "INITIAL_SNAPSHOT"
            or manifest["source_snapshot_status"] != "OPERATOR_FROZEN_COPY"
            or manifest["source_unchanged_at_checks"] is not True
            or manifest["permission_disposition"] != "EXPRESSLY_APPROVED"
            or manifest["authorized_owned"] is not True
            or manifest["source_category"] not in {"AUTHORIZED_REAL_PRODUCTION",
                                                    "AUTHORIZED_REPRESENTATIVE_REAL", "ARTIFICIAL_FIXTURE"}
            or manifest["issues"] != {}
            or manifest["acquisition_completeness"] == "INCOMPLETE"
            or (expected != "UNKNOWN" and expected != len(records))):
        raise ValueError("export is not replay-ready")
    counts = manifest["counts"]
    if any(counts[key] != 0 for key in ("unavailable_identities", "records_without_replay_schema",
                                      "undeclared_missing_words", "conflicting_observations")):
        raise ValueError("incomplete replay observations")
    _check_replay_records(records, counts)
    options = manifest["evaluation_options"]
    allowed = {"target_value_pattern", "target_value_float", "session_id", "population_mode",
               "scan_budget", "max_candidates", "filter_target_match", "use_prescore_selection"}
    if not isinstance(options, dict) or set(options) - allowed or "target_value_pattern" not in options:
        raise ValueError("invalid evaluation options")
    # Match the ordinary fixtures: only the four AC5 input fields enter scoring.
    converted = []
    for record in records:
        converted.append(lua.table_from({key: lua.table_from(record[key]) if key == "memory"
                                        else record[key] for key in ("addr", "mapped", "protect", "memory")}))
    return lua.table_from(converted), lua.table_from(options), manifest
