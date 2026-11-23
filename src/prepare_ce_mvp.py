"""Offline preparation only: bind the CT template to this installation's Lua files."""
from pathlib import Path
import sys
import xml.etree.ElementTree as ET


MARKER = "local entrypoint=nil -- H3A7_LOCAL_ENTRYPOINT"
MODULES = (
    "ce_mvp.lua", "ce_mvp_core.lua", "ce_mvp_adapter.lua",
    "mvp0_foundlist_collector.lua", "mvp0_candidate_report.lua",
)


def lua_path(path: str) -> str:
    # Fixed-width decimal UTF-8 bytes are valid Lua 5.3 string escapes. No path
    # character can close a Lua quote, XML element, CDATA section or AA block.
    if not path or any(ord(c) < 32 for c in path):
        raise ValueError("INVALID_ENTRYPOINT_PATH")
    return '"' + "".join(f"\\{byte:03d}" for byte in path.encode("utf-8")) + '"'


def prepare(source_dir: Path) -> Path:
    source_dir = source_dir.resolve(strict=True)
    for name in MODULES:
        if not (source_dir / name).is_file():
            raise ValueError(f"MISSING_MODULE: {source_dir / name}")
    template = (source_dir / "ce_mvp.CT").read_text(encoding="utf-8")
    if template.count(MARKER) != 1:
        raise ValueError("INVALID_CT_TEMPLATE: expected one entrypoint marker")
    entrypoint = (source_dir / "ce_mvp.lua").as_posix()
    rendered = template.replace(MARKER, "local entrypoint=" + lua_path(entrypoint))
    ET.fromstring(rendered)
    output = source_dir / "ce_mvp.local.CT"
    if output.is_symlink():
        raise ValueError("OUTPUT_IS_SYMLINK")
    output.write_bytes(rendered.encode("utf-8"))
    return output


def main() -> None:
    if len(sys.argv) != 1:
        raise SystemExit("Usage: python src/prepare_ce_mvp.py (no arguments)")
    try:
        output = prepare(Path(__file__).resolve().parent)
    except (OSError, ValueError, ET.ParseError) as exc:
        raise SystemExit(f"CE_MVP_PREPARE_FAILED: {exc}") from exc
    print(f"Prepared: {output}")
    print("Load this local CT in CE; Start remains explicit. Local config is unchanged.")


if __name__ == "__main__":
    main()
