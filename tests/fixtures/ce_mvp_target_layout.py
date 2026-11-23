"""Pure offset-only L09 plans: no ctypes, processes or native memory.

The manual target applies these plans only after an operator command. Synthetic
tests materialize them as bytearrays; they never import the native target.
"""

RESERVATION_SIZE = 0x10000
PAGE_SIZE = 0x1000
SEARCH_BITS = 0x42C80000
DRIFT_BITS = 0x42280000
STRUCTURE = {
    -0x20: 0x10011200, -0x10: 0x10013800, -8: 0x10042100,
    0x30: 0x10060000, 0x40: 0x10025600, 0x48: 0x10028400, 0x50: 0x10086300,
}
MODES = (
    "baseline_unique", "zero_match", "ambiguous", "over_limit",
    "incomplete_structure", "invalid_structure", "value_drift", "relocate",
)


def plan(mode, page=0):
    """Return fresh pages and aligned uint32 writes inside a 64 KiB reservation.

    over_limit is a separate dense layout, not 129 large structures. Actual CE
    must independently count its 129 search words. incomplete_structure has a
    readable value at +FD0 but required +30..+50 fields in an uncommitted next
    page. invalid_structure has readable fields with zero structural markers.
    """
    if mode not in MODES or not isinstance(page, int) or not 0 <= page < 16:
        raise ValueError("invalid fixture mode/page")
    if mode != "relocate" and page != 0:
        raise ValueError("only relocate selects another page")
    pages = (0, 2) if mode == "ambiguous" else (page,)
    positions = tuple(p * PAGE_SIZE + 0x128 for p in pages)
    if mode == "over_limit":
        positions = tuple(0x100 + i * 4 for i in range(129))
        words = {offset: SEARCH_BITS for offset in positions}
    else:
        if mode == "incomplete_structure":
            positions = (0xFD0,)
        words = {}
        for address in positions:
            for offset, bits in STRUCTURE.items():
                if (address + offset) // PAGE_SIZE in pages:
                    words[address + offset] = 0 if mode == "invalid_structure" else bits
            words[address] = DRIFT_BITS if mode in ("zero_match", "value_drift") else SEARCH_BITS
    assert all(0 <= p < RESERVATION_SIZE // PAGE_SIZE for p in pages)
    assert all(0 <= a <= RESERVATION_SIZE - 4 and a % 4 == 0
               and a // PAGE_SIZE in pages for a in words)
    return {"mode": mode, "pages": pages, "words": words, "positions": positions}


def transition(command, mode, page):
    """Bounded local command planning; no memory effect or automatic mode loop."""
    aliases = {"drift": "value_drift", "duplicate": "ambiguous", "reset": "baseline_unique"}
    command = aliases.get(command, command)
    if command == "relocate":
        if mode not in ("baseline_unique", "value_drift", "relocate") or page >= 15:
            raise ValueError("relocate requires one valid slot and an unused page")
        return plan(command, page + 1)
    if command == "value_drift":
        if mode not in ("baseline_unique", "value_drift", "relocate"):
            raise ValueError("value drift requires one valid slot")
        return {"mode": command, "pages": (page,), "positions": (page * PAGE_SIZE + 0x128,),
                "words": {page * PAGE_SIZE + 0x128: DRIFT_BITS}}
    return plan(command)
