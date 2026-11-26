# Standalone CE table: ID1 scan and value maintenance

The prepared table runs in Cheat Engine 7.6 x64 / Lua 5.3 on Windows. It embeds
`ce_mvp.lua`, `mvp0_candidate_report.lua` and `mvp0_foundlist_collector.lua`.
The latter two files are the original algorithm sources, without scoring or
ranking changes. No external runtime modules or Python process are required.

## Run the delivered table

1. Keep `ce_mvp.local.CT` and the existing `ce_mvp_config.local.lua` in one folder.
2. Open the CT in CE. Loading the table does not attach, scan or write.
3. Check **ID1**. It rereads the config, attaches its numeric PID, performs the
   exact scan, passes the entire initial pool to the original algorithm, and
   writes the configured value to rank 1 if its hard filter passes.
4. **ID3** shows that address and its current Float value. The runner disables
   the row's freeze checkbox so it cannot continue writing independently.
5. **ID2** prints cached progress/status. Toggle it again to refresh the output.
6. Uncheck **ID1** to stop. A new deliberate Start rereads the config and rescans.

To use a different PID, stop, edit `target_pid` and check ID1 again. Neither code
changes nor table regeneration are needed. The PID must exist and be accessible
to CE; the original Single algorithm still evaluates its memory candidates.
There is no process-name or PID allowlist and no fixed test-input requirement.

The CT uses the config beside the currently opened table. Its prepared absolute
config path is a fallback for hosts that do not expose the opened filename.
When the table filename is known, a missing sibling config is an error; the
runner does not silently use a config from another installation.

## Configuration

The existing local config is retained byte for byte. `ce_mvp_config.example.lua`
is a smaller template for a new installation; do not overwrite an existing
private config with it.

| Setting | Behavior |
| --- | --- |
| `target_pid` | Positive numeric PID passed directly to CE `openProcess`, then checked against CE's opened PID. |
| `screening_profile`, `value_type` | If present, must be `single` and `float32`. |
| `write_enabled` | Must be `true` for this writing product. |
| `write_value` | Finite Float32 target, written and immediately verified by Float32 bit equality. |
| `scan.target_value_float` | Finite Float32 exact search value. CE scans its exact 4-byte representation using a hexadecimal Dword scan. |
| `scan.target_value_pattern` | Optional; if supplied, must equal the search value's Float32 bits. |
| `scan.start_address`, `scan.stop_address` | Optional paired numeric/hex bounds; absent means user address space `0x10000..0x7FFFFFFFFFFF`. |
| `monitor_interval_ms` | Positive interval between checks, subject to CE timer scheduling. The current config uses 1000 ms. |
| `scan_timeout_ms` | Optional timeout for scanning plus full collection/ranking; default 120000 ms. No partial result is written on timeout. |
| `scan.collection_batch_size`, `scan.collection_slice_ms` | Optional cooperative processing checkpoints; defaults 256 operations / 10 ms. These do not cap the population. |

Other fields in the current config are unused by this independent runner.
In particular, `scan_budget=2000` and `max_candidates=20` cannot truncate the
initial address pool. There are no rescan/backoff, diagnosis, qualification or
mode-selection branches in the product runtime.

CE scans four-byte-aligned writable memory, including private, image and mapped
memory. Every initialized FoundList address is supplied to the original
collector. The collector's existing deduplication and target-match filtering
remain in force. All surviving candidates receive its original scoring and
ranking. Full consumption and complete scoring are checked before any write.

The original algorithm's rank 1 and `hard_pass` determine the first write.
`ACCEPT`, `REVIEW` and `REJECT` labels remain visible algorithm output and are not
an additional execution gate. This implements the requested rule: write the
highest-ranked candidate once the hard filter passes; REVIEW is allowed.
If rank 1 is absent or fails the hard filter, no write occurs.

## Monitoring and stopping

After the first verified write, the runner checks the same selected address at
the configured interval. A finite value below `write_value` triggers a rewrite.
Equal or higher values are left alone. The current value is checked again just
before a rewrite, so a recovered value is not overwritten. Every write has
immediate readback verification.

The first failed/nonfinite read stops the timer and clears ID1. CE 7.6 displays
an unreadable Float as `??`; this is the question-mark state described as `???`
in the request. The runner does not wait for `invalid_confirmations`, retry,
automatically reattach or rescan. Target switches, write failures and readback
mismatches also stop. Stop never restores the old value. If resource cleanup
fails, the table requires a fresh CE session before another Start.

ID2 prints the state, PID, raw/inspected/filtered/scored counts, selected address,
score, recommendation, last observed value, write/rewrite counts and stop reason.
Status printing does not trigger another memory read or scan.

## Rebuild and verify

Only developers changing source need Python:

```powershell
& .venv/Scripts/python.exe src/prepare_ce_mvp.py
& .venv/Scripts/python.exe -m pytest tests/test_ce_mvp_native.py -q
```

For a manual real-CE smoke on Windows with CE installed at its default location:

```powershell
& .venv/Scripts/python.exe tests/ce_mvp_native_smoke.py 2101
```

The driver launches its own disposable target and CE session, substitutes only
the PID in an isolated config copy, and exercises the generated table's actual
ID1 script. It checks native attach, full-pool ranking, write, decrease/rewrite,
unreadable display, automatic ID1 disable and continued absence of writes.
Neither this test driver nor its controlled input is shipped or referenced by
the product. The product's only runtime files are the CT and local config.
