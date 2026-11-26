-- Standard Alpha only. Copy ONCE to the sibling ce_mvp_config.local.lua if absent.
-- Never overwrite an existing private config. This trusted local data is not a
-- native target/writer authorization. This is the historical synthetic selector
-- only: it uses fixture defaults and is NOT the product configuration contract.
-- Use ce_mvp_config.example.lua for the original complete product contract.
return {
  schema = 'g1.alpha.config.v1',
  mode = 'ALPHA_STANDARD',
  input_source = 'OWNED_SYNTHETIC',
}
