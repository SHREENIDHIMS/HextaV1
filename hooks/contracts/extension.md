# Hook Contract — Extension mode

**Status:** Design-only. Not yet implemented by any code.

Hexta may later ship as a **browser extension** (e.g. a mortgage policy
lookup toolbar) or an add-on to another tool. This contract defines the
conceptual event surface such an extension would consume. It is NOT wired
into the backend today — nothing emits these events yet. Defining the shape
now keeps the standalone core unencumbered while making the future
migration mechanical.

## Design rule

The core remains a standalone REST API (see `app.md`). An "extension" is a
thin injected surface that talks to that same API and reacts to lifecycle
events. The core never loads or runs third-party code inside its process.

## Event surface (proposed, not emitted)

These are logical events the core *could* emit in a future build. Each maps
to the existing API action:

| Event | Fired when | Payload shape |
| ----- | ---------- | ------------- |
| `session.created` | `/auth/login` succeeds | `{ user_id, email }` |
| `search.completed` | `/search/` returns | `{ query, response_id, confidence, routing }` |
| `feedback.received` | `/feedback` recorded | `{ response_id, score }` |
| `document.staged` | `/documents` upload accepted | `{ filename, size, queued }` |
| `no_answer` | search routed to `no_answer` / confidence < 50 | `{ query, response_id }` |

## Extension manifest

An extension declares itself in `hooks/manifest.schema.json` with
`kind: "extension"` and maps hooks to local handlers:

```json
{
  "manifest_version": 1,
  "name": "VA Loan Helper",
  "kind": "extension",
  "entry": "src/listeners.js",
  "hooks": {
    "search.completed": "listeners.onSearchCompleted",
    "feedback.received": "listeners.onFeedback"
  },
  "permissions": ["search", "feedback"]
}
```

## Contract

- An extension acts as an **observer** by default. It may call the same
  REST endpoints an app does, using a bearer JWT it was granted by the host.
- It must not run its own LLM/AI summarizer over the returned excerpts.
- It must not mutate the knowledge base. `permissions` stay read-only until
  an explicit, reviewed capability is added.
- Injected UI must respect the department/`allowed_departments` scoping
  already enforced server-side.

## Current status

- [ ] None of the above events are emitted by backend code.
- [ ] No event bus or WebSocket channel exists.
- [ ] No extension host/loader exists.

This file is the forward-looking contract only. Do not build the event bus
until the standalone app is deployed and confirmed working (per the project
roadmap), and do not spread event-emission calls through `app/` prematurely.

## When this becomes real

Budget a tiny, well-typed bridge (registers in `app/hooks/`, not scattered
everywhere). Implement in this order:

1. Define typed event payloads in one module.
2. Emit at the single source of truth per action (the API handler), not in
   helper functions.
3. Add a subscriber registry with an explicit allow-list of extension ids
   from `manifest.schema.json`.
4. Add tests that assert events are emitted exactly once per action.