-- Standard Alpha only. Copy ONCE to the sibling ce_mvp_config.local.lua if absent.
-- Never overwrite an existing private config. This trusted local data is not a
-- native target/writer authorization. The legacy engineering example is separate.
return {
  schema = 'g1.alpha.config.v1',
  mode = 'ALPHA_STANDARD',
  input_source = 'OWNED_SYNTHETIC',
}
