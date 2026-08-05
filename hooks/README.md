# Hexta Hooks — Extension-Points Contract

**Status:** Design-only. Hexta is currently a **standalone application**.
Nothing in this directory is loaded, executed, or enforced by the running
system yet. Its purpose is to make the product **future-ready**: when Hexta
later ships as a standalone *app* and/or a browser/IDE *extension*, the
manifest shape and the split of responsibilities are already pinned, so the
migration is mechanical rather than a redesign.

This folder is separate from application code on purpose. It documents the
boundary the core must respect, and it gives future authors the exact
integration points (`/api/v1/...` endpoints, event names) to build against.

## What already works (application ground truth)

These endpoints exist and are verified against the live backend. Any future
app/extension must target them:

| Endpoint | Auth | Note |
| -------- | ---- | ---- |
| `POST /api/v1/auth/login` | none | returns a JWT (`access_token`) |
| `POST /api/v1/auth/verify` | Bearer | returns `{ valid, user_id, email }` |
| `POST /api/v1/search/` | Bearer | **trailing slash required** |
| `POST /api/v1/feedback` | Bearer | thumbs up/down |
| `POST /api/v1/documents` | Bearer | stage an upload |

## Directory layout

```
hooks/
├── README.md                     # this overview
├── manifest.schema.json          # JSON Schema for app + extension manifests
├── contracts/
│   ├── app.md                    # what "becomes an app" means (REST client)
│   └── extension.md              # what "becomes an extension" means (event surface)
└── examples/
    ├── app/manifest.json         # a valid "app" manifest (Loan Officer Toolkit)
    └── extension/manifest.json   # a valid "extension" manifest (VA Loan Helper)
```

## The two future modes

- **App** (`kind: "app"`) — an independent client process calling the Hexta
  REST API over HTTP, authenticating via JWT. See `contracts/app.md`.
- **Extension** (`kind: "extension"`) — an injected surface (browser/IDE)
  that reacts to lifecycle events and calls the same API. See
  `contracts/extension.md`.

Both are read-only observers by default and inherit the core's hard rule:
**extractive only, never synthesize answers.**

## The manifest schema

`hooks/manifest.schema.json` is a valid JSON Schema (draft 2020-12). Any
future consumer publishes a manifest matching it:

- `manifest_version: 1`
- `kind: "app" | "extension"`
- `entry` — start URL (app) or injected module / tool id (extension)
- `auth.flow: "password" | "bearer"`
- `hooks` — event subscriptions (extension only)
- `permissions` — declared capabilities (empty = read-only observer)

Validate a manifest today with:

```bash
# (schema is not yet wired into any build/test — best-effort manual check)
python -m json.tool hooks/examples/app/manifest.json
```

## What is deliberately NOT here

- No event bus, WebSocket channel, or loader code — none is emitted by the
  backend yet (see `contracts/extension.md` "Current status").
- No hooks are injected into the running API process. The core stays
  standalone; extensions must not run inside its process.
- No third-party code execution path.

## Migration trigger

When the standalone app is deployed and working (roadmap Phase 7), and a
decision is made to build an app and/or extension, follow `contracts/app.md`
and `contracts/extension.md` in that order, then wire `manifest.schema.json`
into a registry. Until then, treat this folder as authoritative documentation
only.