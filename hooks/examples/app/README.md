# App example — Loan Officer Toolkit (`kind: "app"`)

An independent client that talks to the Hexta REST API. See
`hooks/contracts/app.md` for the full contract.

## What this manifest declares

- `id`: `com.hexa.loan-toolkit`
- `entry`: a start URL the future registry could deep-link to.
- `auth.flow`: `password` — it logs in via `/api/v1/auth/login`, stores the
  JWT, and sends `Authorization: Bearer <token>` on every request.
- `permissions`: `["search", "feedback"]` — read/search + record feedback.

## Not yet wired

This is a forward-looking example. No code consumes this manifest, and no
registry exists. It documents the intended shape for a future app build.

Validate it against the schema:

```bash
python -m json.tool hooks/examples/app/manifest.json
```