# Extension example — VA Loan Helper (`kind: "extension"`)

An injected browser/IDE surface that reacts to Hexta lifecycle events. See
`hooks/contracts/extension.md` for the full contract.

## What this manifest declares

- `id`: `hexa.va-helper`
- `entry`: `src/listeners.js` — the module that registers event handlers.
- `auth.flow`: `bearer` — the host hands the extension an already-valid JWT
  rather than asking it to log in.
- `hooks`: subscribes to `search.completed`, `feedback.received`, and
  `no_answer` (confidence < 50 routing).
- `permissions`: `["search", "feedback"]` — read-only observer.

## Not yet wired

No event bus exists in the backend (see `contracts/extension.md` →
"Current status"). This manifest is purely illustrative of the target shape.

Validate it against the schema:

```bash
python -m json.tool hooks/examples/extension/manifest.json
```