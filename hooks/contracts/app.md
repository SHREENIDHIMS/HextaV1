# Hook Contract — App mode

**Status:** Design-only. Not yet enforced by any code.

Hexta is currently a standalone web application. This contract defines what
it means for a future product to consume Hexta as an **app** — an independent
client process that talks to the Hexta REST API. It exists so that, when the
time comes to ship one, the API surface and auth flow are already pinned and
won't need redesign.

## Principle

Hexta's serving path is **extractive only** — it retrieves and returns
verbatim database content; it never synthesizes answers. Any app built on
top inherits this rule: it must not introduce an LLM or an AI summarizer
into the request path. An app may only render, search, and display what the
API returns.

## Verified API surface (v1)

Base URL: `http://host/api/v1` (or `NEXT_PUBLIC_API_URL` in dev).

Stable, non-destructible endpoints an app relies on:

| Endpoint | Method | Auth | Purpose |
| -------- | ------ | ---- | ------- |
| `/auth/login` | POST | none | Exchange email+password for a JWT. |
| `/auth/verify` | POST | Bearer | Validate a JWT; returns `valid`, `user_id`. |
| `/search/` | POST | Bearer | Query the knowledge base. **Note the trailing slash.** |
| `/feedback` | POST | Bearer | Record thumbs-up/down for a response. |
| `/documents` (upload) | POST | Bearer | Validate + stage a document for ingestion. |

## Auth flow for an app

1. `POST /auth/login` with `{ "email", "password" }`.
2. Store the returned `access_token` (a JWT).
3. Send it on every subsequent call as `Authorization: Bearer <token>`.
4. Before a long-lived session, call `/auth/verify` to confirm the token is
   still valid; on `valid: false`, prompt for re-login.

Search is **required** to be authenticated (anonymous requests return
`401 Unauthorized`). An app must obtain a token before its first search.

## Search payload / response

Request:
```json
{ "query": "what is the minimum credit score" }
```

Response is a *Response Package* (never a synthesized sentence):
```json
{
  "response_id": "...",
  "title": "...",
  "excerpts": [{ "text": "...", "source": { "title": "...", "section": null, "chunk_type": "paragraph" }, "confidence": 0.92 }],
  "confidence": 0.92,
  "routing": "answer | partial | no_answer",
  "related_questions": ["..."]
}
```

An app must render `excerpts` verbatim and cite their `source`. Fields must
not be rewritten or blended.

## Rules for app developers

- Never render a field that isn't a verbatim excerpt + its citation.
- Re-authenticate on `401` (call `/auth/login`, retry once).
- Respect RBAC: a user only sees content their `allowed_departments`
  grant. Do not attempt to bypass `authorization` scoping client-side.

## Migration checklist (when building the real app)

1. Confirm `manifest.schema.json` `kind: "app"` with an `entry` URL.
2. Confirm `/search/` trailing-slash behavior is documented and cached.
3. Pin the auth flow in a shared client library (see `frontend/lib/`).
4. Add this doc's `Base URL` resolution to a build-time config, not a
   hardcoded literal.

See `extension.md` for the alternate (in-process event) mode.