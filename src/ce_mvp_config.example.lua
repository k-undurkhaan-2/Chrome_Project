-- Copy to ce_mvp_config.local.lua in this directory, then edit ONCE.
-- This sample cannot start: replace PID=0 and deliberately enable writes only
-- for an operator-approved target. The local copy is ignored by Git.
return {
  target_pid = 0, -- exact positive PID; never a process-name fallback
  screening_profile = 'single',
  value_type = 'float32',
  write_value = 125.0, -- example only; rounded by string.pack('<f') to binary32
  write_enabled = false,
  scan = {
    -- Default: process scope, OS-verified user-mode bounds; no addresses needed.
    -- Only 4-byte aligned matches in CE-supported private writable/non-executable
    -- mappings are searched. Candidate context must be committed PAGE_READWRITE.
    -- Optional diagnostics: mode='bounded', start_address='0x100000',
    -- stop_address='0x10FFFF'. Legacy paired bounds also mean bounded mode.
    target_value_float = 100.0, -- new/relocated objects must start with this value
    target_value_pattern = 0x42C80000, -- exact bits must agree with rounded value
    -- Full-population Single, no truth label, no first-match or top-N shortcut.
    -- Legacy bounded-mode budgets only; process mode never samples this quota.
    scan_budget = 128,
    max_candidates = 128, -- must equal scan_budget
    filter_target_match = true,
    use_prescore_selection = true,
    -- Process defaults (omit in bounded mode): complete pool or zero writes.
    -- process_candidate_limit = 8192, -- compact snapshots; hard ceiling 8192
    -- process_chunk_candidates = 8, -- 1..32, yield after this many candidates
    -- process_slice_ms = 10, -- 1..25, checked between guarded read/score steps
  },
  monitor_interval_ms = 1000,
  invalid_confirmations = 2,
  min_rescan_spacing_ms = 2000,
  rescan_backoff_ms = 1000,
  max_backoff_ms = 30000,
  max_rescan_attempts = 5, -- total retries/relocations per Start, not reset on success
  scan_timeout_ms = 120000, -- includes cooperative collection/ranking time
  log_limit = 200, -- bounded status history + console/file lines per Start
  -- Optional, read-only bounded evidence in Lua tables; no native operations.
  -- Enable only for a separately approved session, with a fresh per-Start token.
  diagnostics = {enabled=false},
  -- diagnostics = {enabled=true, session_token='FRESH_TOKEN', event_limit=512,
  --   cleanup_start_probe=false}, -- true ONLY for the controlled L10 Stop
  -- Optional: existing directory; append at most log_limit lines per Start.
  -- log_path = [[D:\armedforces.io-v2\log\ce_mvp.log]],
  engineering_extensions = {
    h3_a3_store = false,
    h3_a4_approval = false,
    strict_attachment = false, -- any enabled extension explicitly rejects
  },
}
