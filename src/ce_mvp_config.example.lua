-- Copy only when ce_mvp_config.local.lua does not already exist.
-- ID1 reads the config beside the opened CT on each Start.
return {
  target_pid = 0, -- replace with the target process's current numeric PID
  screening_profile = 'single',
  value_type = 'float32',
  write_enabled = true,
  write_value = 125.0,
  scan = {
    target_value_float = 100.0,
    target_value_pattern = 0x42C80000, -- optional; must match the Float32 bits
    -- All initial scan results enter the unchanged Single collector/ranker.
    -- Optional paired bounds; omitted means the process's user address space.
    -- start_address = '0x10000', stop_address = '0x7FFFFFFFFFFF',
    -- collection_batch_size = 256, collection_slice_ms = 10,
  },
  monitor_interval_ms = 1000,
  scan_timeout_ms = 120000, -- scan plus full collection and ranking
}
