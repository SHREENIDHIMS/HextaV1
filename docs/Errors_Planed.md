# Hexta — Errors Planned (full audit findings + fix phases)

Source audit: `docs/AUDIT_2026-08-10.md` · Created: 2026-08-10 · Status legend:
`[x]` done · `[ ]` pending · `[~]` in progress

---

## Phase 1 — Fix broken features (user-visible, no architecture change)

| # | Finding | Files | Status |
|---|---------|-------|--------|
| A1 | No login gate on the home page; logged-out users get an inert chat UI. `LoginForm` imported but unused (ESLint warnings). | `frontend/app/page.tsx` | [x] |
| A2 | JWT payload has no `email` claim → `/auth/verify` email always null, sidebar shows "user@hexa.local", Settings shows "—", `getSession()` email empty. | `backend/app/auth/jwt_handler.py`, `backend/app/api/v1/auth.py` | [x] |
| B1 | `gap_detector.detect_and_log` has zero callers → `knowledge_gaps` never written → Analytics "Knowledge Gaps" always empty. | `backend/app/api/v1/search.py` | [x] |
| B2 | Upload contract mismatch: FE allows `.doc` + 50 MB, BE allows `{pdf,txt,docx,html,md}` + 20 MB → `.doc` and 20–50 MB files fail at the API. | `frontend/app/uploads/page.tsx` | [x] |
| D3 | Dead UI controls: paperclip (attach) and mic (voice) buttons have no handlers. | `frontend/components/search/SearchBar.tsx` | [x] |

## Phase 2 — Security hardening (before any real deployment)

| # | Finding | Files | Status |
|---|---------|-------|--------|
| A3 | No logout endpoint / token revocation; stolen JWT valid 8h. | `backend/app/api/v1/auth.py` (+ new `token_blacklist` table) | [x] |
| A4 | No rate limiting / lockout on login; failed logins not tracked. | `backend/app/api/v1/auth.py` (+ `auth_events` table) | [x] |
| A5 | `/auth/verify` ignores `users.is_active` — deactivated users' tokens still verify. | `backend/app/api/v1/auth.py` | [x] |
| S1 | CORS `*` with credentials + no production guard. | `backend/app/config.py`, `backend/app/main.py` | [x] |
| S2 | No security headers / CSP on static frontend (XSS → token theft). | `frontend/nginx.conf`, `shared-host-infra-scaffold/infra/shared/nginx/conf.d/hexa-assistant.conf` | [x] |
| S3 | Backend bound to `0.0.0.0:18001`; no TLS; port 443 published with nothing listening. | `shared-host-infra-scaffold/infra/systemd/hexa-backend.socket`, `docker-compose.yml` | [x] |
| X1 | Shared nginx serves `/opt/projects/hexa/frontend/out` never mounted into the container → frontend 404s behind prod proxy. | `shared-host-infra-scaffold/infra/shared/nginx/conf.d/hexa-assistant.conf`, `.../shared/docker-compose.yml` | [x] |
| X2 | Deploy workflow runs `systemctl restart nginx` (system nginx not installed → aborts); never installs systemd units or reloads backend. | `.github/workflows/deploy.yml` | [x] |
| X3 | Ingestion/migrate scripts resolve backend to `/opt/projects/backend` (wrong) at documented install location. | `shared-host-infra-scaffold/infra/scripts/run_ingestion.sh`, `migrate_db.sh` | [x] |
| X4 | `migrate_db.sh` can't authenticate as superuser (sources only `backend/.env`). | `shared-host-infra-scaffold/infra/scripts/migrate_db.sh` | [x] |
| X6 | systemd unit requires `.env` the deploy never provisions → first start fails. | `shared-host-infra-scaffold/infra/systemd/hexa-backend.service`, `deploy.yml` | [x] |
| S4 | Weak bundled dev credentials (`adminpass`, default JWT) — rotate before real deployment. | `shared-host-infra-scaffold/infra/shared/.env`, `backend/.env` | [x] |
| S5 | Raw audit-logged queries unredacted (PII). | `backend/app/audit/audit_logger.py` | [x] |

## Phase 3 — Ingestion reliability

| # | Finding | Files | Status |
|---|---------|-------|--------|
| I1 | `process_file` has no per-file error isolation — one DB error kills the whole batch. | `backend/app/documents/ingest_batch.py` | [x] |
| I2 | PDF tables never preserved (table detection requires ≥2 lines but PDF paragraphs are single-line). | `backend/app/documents/chunking/structural_chunker.py` | [x] |
| I3 | OCR orphaned — scanned PDFs silently fail forever; no dead-letter quarantine. | `backend/app/documents/ocr.py`, `text_extraction.py`, `ingest_batch.py` | [x] |
| I4 | Ingestion entity extraction uses naive substring matching → false positives. | `backend/app/documents/entity_extraction.py` | [x] |
| I5 | Embedding failure silently swallowed → chunks indexed with `embedding = NULL`, no retry/alert. | `backend/app/documents/ingest_batch.py` | [x] |
| I6 | Chunk size derives from response-display setting (`max_excerpt_chars // 2`) instead of a dedicated setting. | `backend/app/documents/ingest_batch.py`, `backend/app/config.py` | [x] |
| I7 | `_move_to_processed` crashes on Windows `FileExistsError`. | `backend/app/documents/ingest_batch.py` | [x] |
| C1/X8 | `embedding_cache_dir` not anchored (unlike `rerank_model_dir`) → model path mismatch under systemd. | `backend/app/config.py` | [x] |
| I8 | Dead NER/chunker/audit modules with stale APIs (`gliner.load`, etc.). | `backend/app/query_processing/ner/*`, `chunking/*`, `audit/models.py` | [x] |
| I9 | Orphan `documents` rows when every chunk is a duplicate re-ingest. | `backend/app/documents/indexing.py` | [x] |
| I10 | `import sys` unused; `min_tokens` dead field. | `backend/app/documents/ingest_batch.py`, `structural_chunker.py` | [x] |

## Phase 4 — Quality gate that actually gates

| # | Finding | Files | Status |
|---|---------|-------|--------|
| T1 | `run_benchmark.py` imports retrieval metrics but never calls them → rule-7 gate measures nothing about ranking. | `evaluation/run_benchmark.py` | [x] |
| T2 | Intent accuracy requires every sub-query intent to match → multi-intent queries can never pass (stuck ~0.583). | `evaluation/run_benchmark.py` | [x] |
| T3 | `httpx` (and `requests`) missing from requirements → fresh CI install fails TestClient suite. | `backend/requirements-dev.txt` | [x] |
| T4 | Search 200 success path untested (`"Bearer test"` always 401). | `backend/tests/unit/test_backend_skeleton.py` | [x] |
| T5 | `test_rbac_prefilter` mislabeled; `test_no_user_denies_all` empty body. | `backend/tests/unit/test_search_rbac.py`, `test_rbac_prefilter.py` | [x] |
| T6 | Eval dataset dead/misnamed (`eval_20_questions.jsonl` unreferenced; hardcoded 12-item set). | `evaluation/datasets/` | [x] |
| T7 | Retrieval benchmark silently shrinks denominator (6/20 gold phrases absent from KB). | `evaluation/retrieval_benchmark.py` | [x] |
| B4 | `bm25_limit`/`vector_limit` config dead — never used in SQL. | `backend/app/search/hybrid_orchestrator.py` | [x] |
| B5 | Unbounded `limit` params on documents/analytics endpoints. | `backend/app/api/v1/documents.py`, `analytics.py` | [x] |
| B6 | Search query length unbounded server-side. | `backend/app/api/v1/search.py` | [x] |
| B7 | Feedback accepts arbitrary `response_id`. | `backend/app/api/v1/feedback.py` | [x] |
| B8 | Search returns 500 on RBAC/approval validation failure instead of 403/empty. | `backend/app/api/v1/search.py` | [x] |
| B9 | Admin actions not audit-logged; minimal admin surface. | `backend/app/api/v1/admin.py` | [x] |
| D2 | Sidebar shows admin-only pages to every role. | `frontend/components/ui/sidebar.tsx` | [x] |
| D3b | Inert chat-history search input in sidebar. | `frontend/components/ui/sidebar.tsx` | [x] |
| T8 | Inconsistent p95 definitions across eval tools. | `evaluation/metrics/latency_benchmark.py`, `evaluation/retrieval_benchmark.py` | [x] |
| T9 | Retrieval benchmark duplicates hybrid SQL (drift risk); `" || "`→`" && "` string hack. | `evaluation/retrieval_benchmark.py` | [x] |
| T10 | No pytest config; tests rely on CWD/sys.path hacks. | repo root | [x] |

## Phase 5 — Housekeeping

| # | Finding | Files | Status |
|---|---------|-------|--------|
| D5 | Settings page is a placeholder; email always "—". | `frontend/app/settings/page.tsx` | [x] |
| D6 | Chat transcript persisted unencrypted in localStorage. | `frontend/app/page.tsx` | [x] |
| C2 | Duplicated RBAC helper `get_user_departments` unused. | `backend/app/dependencies.py` | [x] |
| X5 | Idle-stop measures idle from service start, not last activity → false idle stops. | `shared-host-infra-scaffold/infra/scripts/idle_stop_watcher.sh` | [x] |
| X7 | Root compose has no memory caps (rule 10). | `docker-compose.yml` | [x] |
| X9 | Port 18001 collision between root compose and systemd socket. | `docker-compose.yml`, `hexa-backend.socket` | [x] |
| X10 | Read-only model volume breaks first-time model download. | `docker-compose.yml` | [x] |
| X11 | Raw SQL interpolation of app password. | `shared-host-infra-scaffold/infra/shared/postgres/init/02_set_app_password.sh` | [x] |
| X12 | Unpinned action `easingthemes/ssh-deploy@main`. | `.github/workflows/deploy.yml` | [x] |
| X13 | `HEXA_RERANK_ENABLED` true in `.env` vs false in `.env.example`; verify model staged. | `backend/.env`, `backend/.env.example` | [x] |
| E1 | `.env`/`.env.example` drift for rerank toggle (same as X13). | `backend/.env*` | [x] |
| A6 | Fixed 8h JWT expiry, no sliding sessions (documented decision). | `backend/app/config.py` | [x] |
| L1-L11 | Minor dead code / duplicates (unused imports, `COMMON_WORDS` dup, empty-regex fragility, etc.). | backend/app | [x] |

---

## Definition of done

- Every HIGH and MEDIUM above resolved or explicitly deferred with a tracked ticket.
- `pytest` green from a clean `pip install -r requirements-dev.txt`.
- `npm run lint` and `npm run build` clean.
- `python -m evaluation.run_benchmark` reports real retrieval metrics with a new baseline under `evaluation/reports/`.
- Deploy workflow runs end-to-end on a fresh EC2 box (socket activation + shared nginx serving the frontend).
