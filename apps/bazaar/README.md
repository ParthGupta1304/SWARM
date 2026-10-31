# Bazaar API

Bazaar is the local, deliberately vulnerable marketplace target for Swarmtest.
Its API is the contract used by the swarm runtime and dashboard.

## Contract

- Live OpenAPI: `GET /openapi.json`
- Interactive API docs: `GET /docs`
- Offline export: run `make openapi`; it writes `apps/bazaar/openapi.json`.

## Feature flags

`BAZAAR_VERSION=v1` enables all eight frozen planted bugs. `BAZAAR_VERSION=v2`
fixes E1 (oversell race) and E2 (coupon stacking); all remaining bugs stay
enabled for the Phase 2 regression story. Use `BAZAAR_BUG_OVERRIDES` as a JSON
object only for a focused local demo, for example:

```sh
BAZAAR_BUG_OVERRIDES='{"oversell_race": false}'
```

The detailed bug mapping, deterministic reset protocol, and handoffs are in
[`docs/dev1-context.md`](../../docs/dev1-context.md).
