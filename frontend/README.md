# ContextBridge workspace

Static Next.js UI served by the native Python loopback manager. End users install
prebuilt assets; Node 24 is a development/build dependency only.

```text
npm ci
```

From the repository root, run `uv run python scripts/generate_product_types.py`.
Then in this directory:

```text
npm run types
npm run typecheck
npm run build
```

The build copies static assets and CSP hashes into `src/contextbridge/product/web`.
Assets are generated and bundled in wheels/release archives; do not commit `.next`,
`out`, node_modules, traces or local state. Types derive from the actual shared API.

For Chromium/axe tests, first migrate a dedicated PostgreSQL database ending in
`_test`, set `CONTEXTBRIDGE_TEST_DATABASE_URL`, install Chromium with
`npx playwright install chromium`, then run `npm test`. Never point this at a real
memory database. Tests truncate that dedicated database. OS vault/Docker are
simulated in browser tests; native and Docker probes are separate.

`npm run dev` provides frontend development only. Use the bundled build with
`uv run contextbridge start` to verify the real local session/CSRF/CSP boundary.
No provider calls, remote fonts or analytics are required for frontend tests.
