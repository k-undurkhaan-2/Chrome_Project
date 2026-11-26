# armedforces.io-v2

This branch delivers a standalone Cheat Engine table for the configured PID:
check ID1 to attach, scan the configured Float32 value, rank the complete initial
address pool with the original Single algorithm, write rank 1 after its hard
filter passes, and periodically restore values below the configured write value.
The first unreadable value (CE displays question marks) stops writing and clears
ID1. REVIEW is allowed; recommendation labels do not add another write gate.

Open **`src/ce_mvp.local.CT`** in Cheat Engine 7.6 x64 and keep the existing
**`ce_mvp_config.local.lua`** beside it. The prepared CT embeds the runner and both
original algorithm files. The runtime only needs these two files; it has no
fixed PID, synthetic-input requirement, external Python process, engineering
mode, qualification workflow or core/adapter dependency.

- ID1: start; uncheck to stop.
- ID2: print progress and the last observed state to the Lua console.
- ID3: display the selected address and its live Float value; its freeze control
  is disabled by the runner so all writes remain under ID1's control.

Changing PID requires only a config edit followed by a new ID1 Start. Build a
fresh table after editing runner or algorithm source:

```powershell
& .venv/Scripts/python.exe src/prepare_ce_mvp.py
```

The builder preserves the local config. The original count budgets do not
truncate the initial pool. The existing Single scorer, including its hard
filter, score, rank order and recommendation, is unchanged.

See [usage and configuration](docs/ce_mvp_quickstart.md), the
[product regressions](tests/test_ce_mvp_native.py), the
[real CE smoke driver](tests/ce_mvp_native_smoke.py), and the
[delivery evidence](reports/2026-11-27/ce-native-id1-delivery.md).
Historical engineering modules and reports are not dependencies of this product.
