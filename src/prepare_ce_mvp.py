"""Offline preparation only: bind the CT template to this installation's Lua files."""
from pathlib import Path
import sys
import xml.etree.ElementTree as ET


MARKER = "local entrypoint=nil -- H3A7_LOCAL_ENTRYPOINT"
READONLY_MARKER = "local entrypoint=nil -- G1_READONLY_LOCAL_ENTRYPOINT"
CONTROLLED_MARKER = "local controlled=false -- G1_ALPHA_CONTROLLED"
MODULES = (
    "ce_mvp.lua", "ce_mvp_core.lua", "ce_mvp_adapter.lua",
    "mvp0_foundlist_collector.lua", "mvp0_candidate_report.lua",
    "ce_mvp_readonly.lua", "mvp0_offline_scoring.lua",
)
REQUIRED_FILES = (*MODULES, "examples/g1_alpha_population.example.lua")


def lua_path(path: str) -> str:
    # Fixed-width decimal UTF-8 bytes are valid Lua 5.3 string escapes. No path
    # character can close a Lua quote, XML element, CDATA section or AA block.
    if not path or any(ord(c) < 32 for c in path):
        raise ValueError("INVALID_ENTRYPOINT_PATH")
    return '"' + "".join(f"\\{byte:03d}" for byte in path.encode("utf-8")) + '"'


def prepare(source_dir: Path, *, alpha_controlled: bool = False) -> Path:
    source_dir = source_dir.resolve(strict=True)
    for name in REQUIRED_FILES:
        if not (source_dir / name).is_file():
            raise ValueError(f"MISSING_MODULE: {source_dir / name}")
    template = (source_dir / "ce_mvp.CT").read_text(encoding="utf-8")
    rendered = template
    if alpha_controlled:
        fixture = source_dir.parent / "tests/fixtures/ce_mvp_mock.lua"
        if not fixture.is_file():
            raise ValueError(f"MISSING_CONTROLLED_FIXTURE: {fixture}")
        if template.count(CONTROLLED_MARKER) != 1:
            raise ValueError("INVALID_CT_TEMPLATE: expected one controlled marker")
        rendered = rendered.replace(CONTROLLED_MARKER, "local controlled=true -- G1_ALPHA_CONTROLLED")
    for marker, name in ((MARKER, "ce_mvp.lua"), (READONLY_MARKER, "ce_mvp_readonly.lua")):
        if template.count(marker) != 1:
            raise ValueError("INVALID_CT_TEMPLATE: expected one marker for " + name)
        rendered = rendered.replace(marker, "local entrypoint=" + lua_path((source_dir / name).as_posix()))
    ET.fromstring(rendered)
    output = source_dir / "ce_mvp.local.CT"
    if output.is_symlink():
        raise ValueError("OUTPUT_IS_SYMLINK")
    output.write_bytes(rendered.encode("utf-8"))
    return output


def main() -> None:
    if sys.argv[1:] not in ([], ["--alpha-controlled"]):
        raise SystemExit("Usage: python src/prepare_ce_mvp.py [--alpha-controlled]")
    try:
        output = prepare(Path(__file__).resolve().parent, alpha_controlled=bool(sys.argv[1:]))
    except (OSError, ValueError, ET.ParseError) as exc:
        raise SystemExit(f"CE_MVP_PREPARE_FAILED: {exc}") from exc
    print(f"Prepared: {output}")
    print("Load this local CT in CE; the G1 READ ONLY example is an explicit, one-shot entry.")
    print("ID1 uses the owned table fixture; no native target calls." if sys.argv[1:]
          else "Native Start remains separate and explicit. Local config is unchanged.")


if __name__ == "__main__":
    main()
