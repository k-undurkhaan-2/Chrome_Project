-- Original product contract. Copy ONCE to the sibling ce_mvp_config.local.lua
-- only if absent; never overwrite an existing private configuration.
-- Safe placeholders are structurally valid but cannot Start. Configuration is
-- neither runtime capability nor execution authorization. Standard Alpha uses
-- the existing full adapter admission, but native qualification is unavailable.
-- See docs/ce_mvp_quickstart.md for the current English product contract.
-- Optional standard-only input_source='OWNED_SYNTHETIC' explicitly selects the
-- existing fixed table test environment (identity 101), never a native target.
-- Engineering/qualification selection and execution validation remain separate.
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
    -- Original Single collector defaults, independent of CE's raw hit count.
    -- Raw admission 1..65536; final ranking 1..128, at most scan_budget.
    -- These two count budgets apply ONLY to engineering/qualification intake.
    -- Standard Alpha full supplied evaluation does not truncate by these budgets.
    -- Bounded address scope conflicts with the standard Alpha profile.
    scan_budget = 2000,
    max_candidates = 20,
    filter_target_match = true,
    use_prescore_selection = true,
    -- Cooperative collection in either scope; no native raw-result count cap.
    -- collection_batch_size = 256, -- 16..2048 address/read/score checkpoints
    -- collection_slice_ms = 10, -- 1..25, checked between those operations
  },
  monitor_interval_ms = 1000,
  invalid_confirmations = 2, -- engineering only; Alpha stops at first observed invalidity
  min_rescan_spacing_ms = 2000,
  rescan_backoff_ms = 1000,
  max_backoff_ms = 30000,
  max_rescan_attempts = 5, -- engineering recovery only; all four recovery fields are dormant in Alpha
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
