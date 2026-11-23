"""Manual qualification fixture ONLY; never imported/launched by R1 tests.

Separate G1 approval is required. Only this process's own 64 KiB reservation is
modified. Commands are local stdin, finite and deterministic; no network or CE
control. Mode changes other than value_drift/relocate require MVP fully stopped.
"""
import ctypes
from ctypes import wintypes
from datetime import datetime, timezone
import json
import os
import re
import struct
import sys
import time

from fixtures.ce_mvp_target_layout import PAGE_SIZE, RESERVATION_SIZE, MODES, plan, transition


def main():
    if len(sys.argv) != 2 or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", sys.argv[1]):
        raise RuntimeError("Supply one fresh approved session token (1..64 letters/digits/_/-)")
    if os.name != "nt" or ctypes.sizeof(ctypes.c_void_p) != 8:
        raise RuntimeError("Use Windows x64 Python for this manual fixture")
    k = ctypes.WinDLL("kernel32", use_last_error=True)
    k.VirtualAlloc.argtypes = [ctypes.c_void_p, ctypes.c_size_t, wintypes.DWORD, wintypes.DWORD]
    k.VirtualAlloc.restype = ctypes.c_void_p
    k.VirtualFree.argtypes = [ctypes.c_void_p, ctypes.c_size_t, wintypes.DWORD]
    k.VirtualFree.restype = wintypes.BOOL
    k.GetCurrentProcess.argtypes = []
    k.GetCurrentProcess.restype = wintypes.HANDLE
    k.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4
    k.GetProcessTimes.restype = wintypes.BOOL
    times = [wintypes.FILETIME() for _ in range(4)]
    if not k.GetProcessTimes(k.GetCurrentProcess(), *(ctypes.byref(t) for t in times)):
        raise ctypes.WinError(ctypes.get_last_error())
    creation = (times[0].dwHighDateTime << 32) | times[0].dwLowDateTime
    base = k.VirtualAlloc(None, RESERVATION_SIZE, 0x2000, 4)
    if not base:
        raise ctypes.WinError(ctypes.get_last_error())
    committed, current, mode, page = set(), None, "baseline_unique", 0
    started, sequence = time.monotonic_ns(), 0
    fixture_word_writes = 0

    def release_page(index):
        if not k.VirtualFree(base + index * PAGE_SIZE, PAGE_SIZE, 0x4000):
            raise ctypes.WinError(ctypes.get_last_error())
        committed.remove(index)

    def apply(layout, *, value_only=False, relocation=False):
        nonlocal current, mode, page, fixture_word_writes
        old_pages = set(committed)
        if not value_only and not relocation:
            for index in sorted(old_pages):
                release_page(index)
        if not value_only:
            for index in layout["pages"]:
                address = base + index * PAGE_SIZE
                if k.VirtualAlloc(address, PAGE_SIZE, 0x1000, 4) != address:
                    raise ctypes.WinError(ctypes.get_last_error())
                committed.add(index)  # fresh committed pages are zero initialized
        for offset, bits in layout["words"].items():
            assert offset // PAGE_SIZE in committed and 0 <= offset < RESERVATION_SIZE
            ctypes.c_uint32.from_address(base + offset).value = bits
            fixture_word_writes += 1
        if relocation:
            for index in sorted(old_pages):
                release_page(index)  # same process, old page genuinely decommitted
        current = base + layout["positions"][0]
        mode, page = layout["mode"], layout["pages"][0]

    def show(event, **detail):
        nonlocal sequence
        sequence += 1
        bits = ctypes.c_uint32.from_address(current).value if current else None
        print(json.dumps({"schema": 1, "source": "target", "session_token": sys.argv[1],
            "sequence": sequence, "event_type": event, "mode": mode, "pid": os.getpid(),
            "target_creation_filetime_hex": f"{creation:016X}",
            "identity_source": "target:GetProcessTimes(GetCurrentProcess); corroboration only",
            "utc_observed": datetime.now(timezone.utc).isoformat(),
            "relative_ms": (time.monotonic_ns() - started) // 1_000_000,
            "scan_start": hex(base), "scan_stop": hex(base + RESERVATION_SIZE - 1),
            "reservation_bytes": RESERVATION_SIZE, "committed_pages": sorted(committed),
            "value_address": hex(current) if current else None,
            "float32": struct.unpack("<f", struct.pack("<I", bits))[0] if bits is not None else None,
            "bits": f"0x{bits:08X}" if bits is not None else None,
            "fixture_word_writes": fixture_word_writes,
            "ce_write_count": "unobserved; use CE adapter counters", **detail}), flush=True)

    try:
        apply(plan("baseline_unique"))
        show("ready")
        print("Commands: status, " + ", ".join(MODES) + ", exit. No automatic CE actions.", flush=True)
        for line in sys.stdin:
            command = line.strip()
            if command == "exit":
                break
            if command == "status":
                show("status")
                continue
            try:
                layout = transition(command, mode, page)
            except ValueError as exc:
                show("command_rejected", reason=str(exc))
                continue
            previous = current
            is_drift = command in ("value_drift", "drift")
            apply(layout, value_only=is_drift, relocation=command == "relocate")
            show(command, previous_address=hex(previous), previous_decommitted=command == "relocate")
    finally:
        if not k.VirtualFree(base, 0, 0x8000):
            raise ctypes.WinError(ctypes.get_last_error())
        current = None
        committed.clear()
        show("released")


if __name__ == "__main__":
    main()
