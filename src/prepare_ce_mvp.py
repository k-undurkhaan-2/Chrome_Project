"""Embed the native runner and unchanged ranker in a standalone Cheat Table."""
from pathlib import Path
import sys
import xml.etree.ElementTree as ET


MODULES = ("ce_mvp.lua", "mvp0_candidate_report.lua", "mvp0_foundlist_collector.lua")
CONFIG_MARKER = "local config_path=nil -- CE_MVP_CONFIG_PATH"
SOURCES_MARKER = "local sources={} -- CE_MVP_SOURCES"


def lua_path(path: str) -> str:
    if not path or any(ord(c) < 32 for c in path):
        raise ValueError("INVALID_CONFIG_PATH")
    return '"' + "".join(f"\\{byte:03d}" for byte in path.encode("utf-8")) + '"'


def lua_source(source: str) -> str:
    equals = "===="
    while "]" + equals + "]" in source:
        equals += "="
    # Lua skips the first newline in a long string, preserving source contents.
    return "[" + equals + "[\n" + source + "]" + equals + "]"


def prepare(source_dir: Path, output: Path | None = None) -> Path:
    source_dir = source_dir.resolve(strict=True)
    sources = {name: (source_dir / name).read_text(encoding="utf-8") for name in MODULES}
    template = (source_dir / "ce_mvp.CT").read_text(encoding="utf-8")
    for marker in (CONFIG_MARKER, SOURCES_MARKER):
        if template.count(marker) != 1:
            raise ValueError("INVALID_CT_TEMPLATE: " + marker)
    config = source_dir / "ce_mvp_config.local.lua"
    embedded = "local sources={\n" + ",\n".join(
        "  ['" + name + "']=" + lua_source(source) for name, source in sources.items()
    ) + "\n}"
    # Close/reopen XML CDATA if a module itself contains its terminator.
    embedded = embedded.replace("]]>", "]]]]><![CDATA[>")
    rendered = template.replace(CONFIG_MARKER, "local config_path=" + lua_path(config.as_posix()))
    rendered = rendered.replace(SOURCES_MARKER, embedded)
    ET.fromstring(rendered)
    output = output or source_dir / "ce_mvp.local.CT"
    if output.is_symlink():
        raise ValueError("OUTPUT_IS_SYMLINK")
    output.write_bytes(rendered.encode("utf-8"))
    return output


def main() -> None:
    if sys.argv[1:]:
        raise SystemExit("Usage: python src/prepare_ce_mvp.py")
    try:
        output = prepare(Path(__file__).resolve().parent)
    except (OSError, ValueError, ET.ParseError) as exc:
        raise SystemExit(f"CE_MVP_PREPARE_FAILED: {exc}") from exc
    print(f"Prepared: {output}")
    print("Open this CT in CE and check ID1. Keep ce_mvp_config.local.lua beside it.")
    print("All runtime Lua is embedded; Python and repository modules are not needed in CE.")


if __name__ == "__main__":
    main()
