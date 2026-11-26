"""One-shot, read-only AC6 launcher for explicitly supplied owned table data.

Run from a source checkout. No process adapter, action port or recovery loop.
"""
from __future__ import annotations

import argparse
from importlib import import_module
import json
from pathlib import Path
import re
import sys
import time
import traceback


SOURCE = Path(__file__).resolve().parent
MODULES = ("mvp0_foundlist_collector.lua", "mvp0_offline_scoring.lua",
           "mvp0_candidate_report.lua")
# Small local handoff path, not the historical large-population worker profile.
INPUT_BYTES = 8 * 1024 * 1024
LUA_BYTES = 256 * 1024 * 1024
OUTPUT_BYTES = 256 * 1024 * 1024
SECONDS = 240


class AlphaInputError(ValueError):
    pass


def _require(condition, reason):
    if not condition:
        raise AlphaInputError(reason)


def _object(pairs):
    result = {}
    for key, value in pairs:
        _require(key not in result, "ALPHA_DUPLICATE_JSON_KEY")
        result[key] = value
    return result


def _invalid_constant(value):
    raise AlphaInputError("ALPHA_NONFINITE_JSON: " + value)


def read_input(path):
    with Path(path).open("rb") as stream:
        data = stream.read(INPUT_BYTES + 1)
    _require(len(data) <= INPUT_BYTES, "ALPHA_INPUT_RESOURCE_LIMIT")
    return data


def decode_input(data):
    document = json.loads(data.decode("utf-8-sig"), object_pairs_hook=_object,
                          parse_constant=_invalid_constant)
    _require(type(document) is dict and set(document) == {
        "schema", "population_id", "complete", "supplied_count",
        "supplied_identities", "records", "options"}, "ALPHA_INPUT_SCHEMA")
    _require(type(document["schema"]) is int and document["schema"] == 1,
             "ALPHA_INPUT_SCHEMA")
    _require(isinstance(document["population_id"], str)
             and re.fullmatch(r"[A-Za-z0-9_.-]{1,80}", document["population_id"]),
             "ALPHA_POPULATION_ID_REQUIRED")
    _require(document["complete"] is True, "ALPHA_POPULATION_NOT_DECLARED_COMPLETE")
    rows, identities, options = (document[k] for k in ("records", "supplied_identities", "options"))
    _require(type(rows) is list and type(identities) is list and type(options) is dict,
             "ALPHA_INPUT_SCHEMA")
    _require(type(document["supplied_count"]) is int
             and document["supplied_count"] == len(rows), "ALPHA_SUPPLIED_COUNT_MISMATCH")
    _require(all(type(a) is int and 0 < a <= 2**53 - 1 for a in identities),
             "ALPHA_DECLARED_IDENTITIES_INVALID")
    _require(options.get("population_mode") in ("full", "bounded"), "ALPHA_EXPLICIT_MODE_REQUIRED")
    _require(all(type(v) in (str, int, float, bool) for v in options.values()),
             "ALPHA_OPTIONS_MUST_BE_SCALARS")
    for row in rows:
        _require(type(row) is dict and set(row) == {"addr", "mapped", "protect", "memory"},
                 "ALPHA_RECORD_SCHEMA")
        _require(type(row["memory"]) is dict, "ALPHA_MEMORY_SCHEMA")
        _require(all(re.fullmatch(r"[1-9][0-9]*", key) and int(key) <= 2**53 - 1
                     for key in row["memory"]), "ALPHA_MEMORY_IDENTITY_INVALID")
        _require(all(type(v) is int for v in row["memory"].values()), "ALPHA_WORD_MUST_BE_INTEGER")
        # AC5 performs the ordinary record, overlap, option and uint32 validation.
        row["memory"] = {int(key): value for key, value in row["memory"].items()}
    _require(identities == [row["addr"] for row in rows], "ALPHA_SUPPLIED_IDENTITIES_MISMATCH")
    return document


def _plain(value, lua_type, guard):
    guard()
    if lua_type(value) == "table":
        # Numeric Lua keys remain JSON object keys, including ranked/identity tables.
        return {str(key): _plain(child, lua_type, guard) for key, child in value.items()}
    return value


def evaluate(document, *, lua_version="lua54", guard=lambda: None):
    """Evaluate a decoded snapshot once; preserve AC6 errors and its entire envelope."""
    module = import_module("lupa." + lua_version)
    lua = module.LuaRuntime(unpack_returned_tuples=True, max_memory=LUA_BYTES,
                            register_eval=False, register_builtins=False)
    sources = lua.table_from({name: (SOURCE / name).read_text(encoding="utf-8") for name in MODULES})
    runner = lua.eval("""function(sources)
      local env={assert=assert,error=error,ipairs=ipairs,pairs=pairs,next=next,pcall=pcall,
        select=select,tonumber=tonumber,tostring=tostring,type=type,getmetatable=getmetatable,
        math=math,string=string,table=table,debug={getinfo=debug.getinfo},os={clock=os.clock}}
      env._G=env
      local function load_module(name, scope)
        return assert(load(assert(sources[name], 'ALPHA_UNKNOWN_MODULE'), name, 't', scope))()
      end
      local collector=load_module('mvp0_foundlist_collector.lua',env)
      return function(records, options)
        return collector.run(options,{records=records,load_module=load_module})
      end
    end""")(sources)
    # A cooperative deadline/cancellation checkpoint, not a worker or liveness detector.
    set_guard = lua.eval("function(check) debug.sethook(function() check() end, '', 10000) end")
    clear_guard = lua.eval("function() debug.sethook() end")
    try:
        set_guard(guard)
        guard()
        completed = runner(lua.table_from(document["records"], recursive=True),
                           lua.table_from(document["options"]))
        result = _plain(completed, module.lua_type, guard)
        guard()
        return {
            "scope": "OWNED_TABLE_SNAPSHOT_READ_ONLY",
            "population_id": document["population_id"],
            "state": "COMPLETED_READ_ONLY",
            "action_permitted": False,
            "action_status": "UNSUPPORTED_NO_COOPERATIVE_OPERATION_INTERFACE",
            "lifecycle_status": "UNSUPPORTED_NO_APPLICATION_LIFECYCLE_INTERFACE",
            "automatic_recovery": False,
            "proposed_rank1": (result["result"]["ranked"]["1"]["candidate"]["value_addr"]
                               if result["population_mode"] == "full" and result["status"] == "COMPLETE"
                               else None),
            "evaluation": result,
        }
    finally:
        clear_guard()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path,
                        help="UTF-8 JSON export from an owned application; see src/examples")
    parser.add_argument("--lua", choices=("lua53", "lua54"), default="lua54")
    parser.add_argument("--json", action="store_true", help="Emit the complete AC6 envelope as JSON")
    args = parser.parse_args(argv)
    started = time.monotonic()

    def guard():
        if time.monotonic() - started >= SECONDS:
            raise TimeoutError("ALPHA_EVALUATION_DEADLINE")

    try:
        original = read_input(args.input)
        outcome = evaluate(decode_input(original), lua_version=args.lua, guard=guard)
        if args.json:
            rendered = json.dumps(outcome, ensure_ascii=True, allow_nan=False, indent=2)
        else:
            evaluation = outcome["evaluation"]
            summary = {key: value for key, value in outcome.items() if key != "evaluation"}
            summary.update({key: evaluation[key] for key in (
                "status", "completed", "population_mode", "population_complete", "counts", "identities")})
            rendered = json.dumps(summary, ensure_ascii=True, allow_nan=False, indent=2)
            rendered += "\n" + evaluation["result"]["report_text"]
        _require(len(rendered.encode("utf-8")) <= OUTPUT_BYTES, "ALPHA_OUTPUT_RESOURCE_LIMIT")
        _require(read_input(args.input) == original, "ALPHA_INPUT_CHANGED_DURING_EVALUATION")
        guard()
        print(rendered)
        return 0
    except KeyboardInterrupt:
        print("STOPPED: OPERATOR_CANCELLED; no automatic restart", file=sys.stderr)
        return 130
    except Exception:
        print("STOPPED: evaluation unsuccessful; no result or automatic restart", file=sys.stderr)
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
