# OKX Position Report Error Propagation Design

## Problem

The OKX execution adapter currently catches every exception raised while generating position
status reports, logs the failure, and returns the reports accumulated so far. During an account-wide
query, an early request failure therefore looks exactly like a successful empty venue response. The
live execution engine interprets that empty response as `venue_qty=0`; with missing-order generation
enabled, it can synthesize a closing fill and incorrectly close the cached position.

## Selected design

Keep successful empty responses unchanged, but propagate query exceptions after logging them. The
existing live execution engine already gathers client results with `return_exceptions=True`, records
the failed venue, and skips cached-position reconciliation for that venue. The patch therefore stays
at the only boundary that still knows whether the response was empty or failed: the OKX adapter.

The change is intentionally one behavioral line in
`nautilus_trader/adapters/okx/execution.py`: re-raise from the existing `PositionReports` exception
handler. The existing integration test which asserts failures return `[]` will be changed first to
assert that the original exception propagates. Existing live-engine tests prove that propagated
client exceptions become `failed_venues` rather than inferred flat positions.

## Alternatives rejected

- Disabling `generate_missing_orders` only masks this failure and weakens valid reconciliation.
- Treating every empty report list as an error would break the legitimate all-flat account case.
- Adding strategy-side guards in `nautilus_quants` is too late; the fake fill has already mutated the
  execution cache and emitted `PositionClosed`.

## Release and deployment

Publish this as fork patch `1.230.3`, update the existing GHCR wheel `latest` contract, build
`nautilus_quants` main with `Dockerfile.beta`, then deploy the same immutable fork image to the
Shanghai 1-hour breakout testnet and the three current AWS prod accounts. Runtime verification must
confirm `nautilus_trader=1.230.3`, container health, restart count, command/config identity, and no
new reconciliation errors. The existing BTC venue/cache mismatch is not silently altered by this
patch.
