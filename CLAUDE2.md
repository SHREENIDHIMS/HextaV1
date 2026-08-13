# CLAUDE2.md — Hexta (Mortgage Knowledge Assistant) runbook & reference

> A plain-English companion to the repo-root `CLAUDE.md` (which holds the
> hard architecture rules). This doc answers **"what does each thing do?"**,
> **"how do I run/operate it?"**, and **"what's next?"**. Give this to any agent
> or teammate to get them up to speed fast.

## 1. What is Hexta?

An **extractive-only** internal knowledge assistant for mortgage / property-
management questions. It never generates text from scratch: every answer is a
verbatim or near-verbatim excerpt pulled from indexed company documents
(SOPs, policies, contracts), stitched together from retrieved chunks and
always shown with a **source citation**. If nothing relevant is found it
returns a clearly-labelled "no answer" — it never makes one up.

**Core rules (from `CLAUDE.md`, do not break):**
- No LLM, no embeddings-as-generation, no vector DB in the serving path beyond
  pgvector. Retrieval = Postgres full-text search (`ts_rank` BM25) + pgvector
  similarity + RRF re-rank → reranker (ONNX int8). Answers come verbatim.
- RBAC + "active version" filters happen **in the SQL `WHERE`**, not after.
- Backend runs **single-worker, socket-activated**, and idle-stops (not a
  long-lived container in production).
- Document ingestion (OCR/chunk/embed/index) runs only in a **batch job**, never
  in a request handler.

## 2. Stack

| Layer | Tech |
|---|---|
| API | Python 3.11 + FastAPI, async SQLAlchemy 2 / asyncpg / psycopg, Alembic |
| Retrieval | Postgres `ts_rank` (BM25) + pgvector + RRF lexical reranker, ONNX int8 cross-encoder reranker |
| Auth | JWT (HS256) + RBAC (`role`/`department` filters in SQL) |
| Frontend | Next.js 15 (`output: 'export'`) + React 19, ElevenLabs Conversation/Message/Orb/Response kit, Tailwind, shadcn/ui |
| Search frontend | `use-stick-to-bottom`, `streamdown` (kit Response); direct-to-FastAPI `api-client.ts` (no BFF) |
| DB | PostgreSQL + pgvector (one shared instance, one DB per project) |
| Infra (prod) | systemd socket-activated backend, shared Nginx+Postgres Docker Compose on a single host |

## 3. Repo layout

```
Hexta-main/
├── backend/                 # FastAPI app
│   ├── app/                 # API (api.v1 router: auth, search, documents, feedback, analytics, admin)
│   │   ├── api/v1/          # route handlers
│   │   ├── search/          # hybrid_orchestrator, metadata_filters, pgvector_search, reranker wiring
│   │   ├── ranking/         # BM25+vector+RRF + ONNX reranker (p95 < 200ms)
│   │   ├── documents/       # upload validation + ingest_batch (batch only)
│   │   ├── db/postgres/     # schema + seed (admin@hexa.local / adminpass)
│   │   ├── auth/            # JWT + bcrypt + permissions
│   │   ├── response/        # response packaging + confidence thresholds (config, not constants)
│   │   └── config.py        # settings (env prefix HEXA_), repo-root path anchoring
│   ├── requirements.txt
│   ├── Dockerfile           # standalone single-worker image (--workers 1)
│   └── .env                 # LOCAL ONLY (gitignored): DB url, JWT secret, HEXA_RERANK_ENABLED
├── frontend/                # Next.js app
│   ├── app/                 # pages: / (chat), /uploads, /settings, /analytics, /admin
│   ├── components/
│   │   ├── ui/              # kit: conversation, message, orb, response + shadcn primitives + sidebar
│   │   ├── search/          # SearchBar, ResponsePackageCard (citations), RelatedQuestions, ConfidenceBadge
│   │   └── auth/LoginForm, feedback/ThumbsFeedback
│   ├── lib/api-client.ts    # direct FastAPI client (JWT bearer)
│   ├── lib/auth.ts          # client JWT storage
│   ├── Dockerfile           # multi-stage: node builder → nginx static export
│   └── next.config.js       # output:'export'
├── docker-compose.yml       # one-hood local stack: frontend + backend (Postgres stays shared on host)
├── evaluation/              # benchmark + latency tooling + reports/
├── shared-host-infra-scaffold/infra/   # systemd units, nginx conf, shared docker-compose, scripts
│   ├── systemd/              # hexa-backend.{socket,service}, hexa-backend-idle.{timer,service}
│   ├── shared/               # docker-compose.yml (Postgres+Nginx), postgres init, nginx conf
│   └── scripts/              # migrate_db.sh, run_ingestion.sh, idle_stop_watcher.sh
├── .github/workflows/        # CI: lint/typecheck/build/test + deploy gate
└── CLAUDE.md                 # authoritative architecture rules
```

Key endpoints: `POST /api/v1/auth/login`, `POST /api/v1/search/`,
`POST /api/v1/feedback/`, `POST /api/v1/documents/upload`, `GET /api/v1/documents/`,
`GET /api/v1/health`.

## 4. How to run it locally

### Option A — Docker Compose (recommended, one hood)
```bash
cd Hexta-main/Hexta-main      # the mortgage-assistant repo (note: doubled name)
docker compose up --build -d   # builds backend+frontend, mounts nlp_models, rerank ON
docker compose logs -f         # watch
```
- Frontend: `http://localhost:13000`
- Backend API/docs: `http://localhost:18001/api/v1/docs`
- DB: `localhost:15432` (shared Postgres already running)
- Admin login: `admin@hexa.local` / `adminpass`

Compose mounts `./nlp_models:/nlp_models:ro` and sets `HEXA_RERANK_ENABLED=True`,
so the container parity matches the host run (reranker + embeddings).

### Option B — native dev (no containers)
```bash
# terminal 1 — backend (single worker, dev reload)
cd backend && .venv\Scripts\python.exe -m uvicorn app.main:app --workers 1 --reload
# terminal 2 — frontend (hot reload)
cd frontend && npm run dev
```
Backend default DB url = `postgresql://hexa_app:devpass@127.0.0.1:15432/hexa_assistant`.

### Option C — production-ish on this host (systemd)
Use the socket-activated units in `shared-host-infra-scaffold/infra/`
(install units + scripts to `/opt/projects/hexa/...` per `infra/README.md`).

## 5. What each recent change does

- **ElevenLabs kit** (`components/ui/{conversation,message,orb,response}`); the 3D
  `Orb` uses `three`/`@react-three/fiber`/`@react-three/drei` with a local
  `public/perlin-noise.png` texture and a client-only render guard so static
  prerender never runs WebGL.
- **Search bar UX fix**: `SearchBar` now clears its input after dispatch
  (`setQuery("")`), and the chat area is a proper flex column so `StickToBottom`
  auto-scrolls to the latest message.
- **Sidebar**: persistent left rail (Chat/Uploads/Settings/Analytics/Admin +
  sign-out) shown to authenticated users; sign-out moved out of the header.
- **Uploads page**: file picker → `POST /api/v1/documents/upload` (validated,
  written to `storage/pending/`); lists existing documents. Ingestion runs
  separately via `run_ingestion.sh`.
- **Docker**: `frontend/Dockerfile` (multi-stage static export) + root
  `docker-compose.yml` for the one-hood stack; `backend/.dockerignore` keeps
  images slim.

## 6. Verification done so far
- `npm run lint` and `npx tsc --noEmit` → clean on `frontend/`.
- `next build` (in-container) → 8 routes prerendered, no errors.
- Container stack live: `/` 200, `/uploads/` 200, kit chunk 200, `perlin-noise.png` 200.
- `/api/v1/health` → `database: connected`; login → JWT; search →
  `routing=answer`, confidence 98.4–100, verbatim excerpts with citations.

## 7. Next steps (when you're ready)
- Browser-based visual check of the 3D Orb + auto-scroll + sidebar on `localhost:13000`.
- Wire `/admin` to real admin endpoints + a `/settings` form for JWT secret/
  CORS (currently informational).
- Add a real Analytics dashboard (audit log → charts).

- For AWS EC2: use `infra/shared` compose for Postgres+Nginx, socket-activate
  the backend, set a billing alarm — see `infra/README.md`.

## 8. Ops cheat-sheet
```bash
# rebuild + restart after code changes
docker compose up --build -d
docker compose stop          # or: down  (removes containers; keeps postgres on host)

# backend shell in container
docker compose run --rm backend sh     # or: bash
# rebuild frontend only
docker compose build frontend

# run ingestion (host venv, against host db)
cd backend && .venv/bin/python -m app.documents.ingest_batch --queue-dir storage/pending
# (or via infra/scripts/run_ingestion.sh)

# eval
python evaluation/run_benchmark.py
```
