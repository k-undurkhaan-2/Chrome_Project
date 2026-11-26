# Retired intermediate native-ID1 implementation

This snapshot preserves the intermediate implementation that still used the
original core/adapter layers, engineering modes and qualification interfaces.
It was superseded by the independent product in `src/ce_mvp.lua` after the
delivery scope explicitly excluded those mechanisms.

These files are historical reference only, not a runnable standalone package.
They are neither embedded in the delivered CT nor imported by the product.
The current tests and native smoke are `tests/test_ce_mvp_native.py` and
`tests/ce_mvp_native_smoke.py` at the repository root.
