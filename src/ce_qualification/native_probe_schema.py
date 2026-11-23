"""Small strict validator for the shipped JSON Schema subset; no dependencies.

Unsupported schema keywords fail closed. This is not a general JSON Schema
implementation. The versioned probe schema uses only the supported keywords.
"""
import re
from .native_probe_protocol import require

KEYWORDS = {"$schema", "$id", "title", "description", "type", "enum", "const", "required",
            "properties", "additionalProperties", "minimum", "maximum", "pattern",
            "minLength", "maxLength", "minItems", "maxItems", "items", "oneOf"}


def validate(value, schema):
    require(type(schema) is dict and set(schema) <= KEYWORDS, "SCHEMA_KEYWORD")
    if "oneOf" in schema:
        matches = 0
        for variant in schema["oneOf"]:
            try:
                validate(value, variant)
                matches += 1
            except ValueError:
                pass
        require(matches == 1, "SCHEMA_ONE_OF")
    if "type" in schema:
        types = {"object": dict, "array": list, "string": str, "integer": int, "boolean": bool, "null": type(None)}
        require(schema["type"] in types and type(value) is types[schema["type"]], "SCHEMA_TYPE")
    if "const" in schema:
        require(type(value) is type(schema["const"]) and value == schema["const"], "SCHEMA_CONST")
    if "enum" in schema:
        require(any(type(value) is type(v) and value == v for v in schema["enum"]), "SCHEMA_ENUM")
    if type(value) is dict:
        props = schema.get("properties", {})
        require(set(schema.get("required", [])) <= set(value), "SCHEMA_REQUIRED")
        if schema.get("additionalProperties") is False:
            require(set(value) <= set(props), "SCHEMA_UNKNOWN_FIELD")
        for key in set(value) & set(props):
            validate(value[key], props[key])
    if type(value) is str:
        require(schema.get("minLength", 0) <= len(value) <= schema.get("maxLength", len(value)), "SCHEMA_STRING_LENGTH")
        if "pattern" in schema:
            require(re.fullmatch(schema["pattern"], value) is not None, "SCHEMA_PATTERN")
    if type(value) is int:
        require(schema.get("minimum", value) <= value <= schema.get("maximum", value), "SCHEMA_INTEGER_RANGE")
    if type(value) is list:
        require(schema.get("minItems", 0) <= len(value) <= schema.get("maxItems", len(value)), "SCHEMA_ARRAY_LENGTH")
        for item in value:
            validate(item, schema.get("items", {}))


def validate_event(row, schema):
    validate(row, schema)
    data = row["data"]
    expected = {"CHECK": {"check_id", "observed"}, "TX": {"wire_hex"}, "RX": {"wire_hex"},
                "TX_CHUNK": {"wire_hex"}, "RX_CHUNK": {"wire_hex"},
                "WATCHDOG_ARM": {"deadline_ms", "cutoff_ms"},
                "DEADLINE": {"elapsed_ms"}, "HARD_CUTOFF_MODEL": {"elapsed_ms"},
                "CLEANUP_OBSERVED": {"io_completed", "resources_closed", "state"}}
    require(set(data) == expected.get(row["kind"], set()), "EVENT_PAYLOAD")
    if row["kind"] not in ("TX", "RX", "TX_CHUNK", "RX_CHUNK"):
        require(row["frame_length"] == 0 and row["frame_sha256"] == "", "NONFRAME_BYTES")
