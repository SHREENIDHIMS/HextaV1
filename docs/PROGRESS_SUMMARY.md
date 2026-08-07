# Hexta — Progress Summary

Last updated: Session verification pass (2026-08-06). All green locally.

## Where we are
**Phases 0–6 and 8 are CLOSED and verified green this session.** Phase 7
(on-demand systemd deployment) scaffold is complete on disk; its final
DoD step — live cold-start/idle-stop measurement on the EC2 host — is
host-bound and not runnable from this Windows dev box.

## Completed (committed + verified)
- **Phase 0–3** (pre-existing scaffold): shared Postgres+pgvector + Nginx
  containers; FastAPI backend (`--workers 1`, `python:3.11-slim`, Alembic,
  `document_chunks`+`vector(384)`); batch ingestion scaffold;
  `query_processing.process_query`.
- **Phase 4 — B1 / RBAC DoD:**
  - `backend/tests/unit/test_search_rbac.py` — asserts RBAC + active-version
    filtering live in the SQL `WHERE` (rule #1 primary enforcement) for a
    restricted user, that admin SQL omits the dept filter, and the validation
    safety-net rejects unauthorized/unapproved chunks.
  - `backend/tests/integration/test_rbac_end_to_end.py` — seeds two
    departments; asserts the denied chunk is excluded from candidates **and**
    never reaches the reranker (call-count spy); plus a two-user/two-department
    scoping test.
  - Reranker p50 ~110 ms / p95 ~175–184 ms **< 200 ms** (rule 6); verified
    live — 0 rule-6 violations on the cold-after-boot request.
  - Commits `319bbc2` (Phase-4 RBAC tests) + `ce06d73` (two-user DoD assertion)
    + `ca9984e` (reranker wire-up + warm-up) + `7325fcf` (20-query benchmark).
- **Phase 4 — B3 / 20-query benchmark:**
  - `evaluation/retrieval_benchmark.py`: 20 GOLD queries incl. 8 exact-phrase
    pairs; whitespace-normalized `_gold_chunk`.
  - Rerank ON: recall@1 80% / @5 95% / @10 100%; MRR@10 0.848 (vs 0.571
    baseline); AND-vs-OR 13/20 operator misses; **reranker p95 175.02 ms**.
  - Report: `evaluation/reports/retrieval_benchmark_20260806_032736.json`.
- **Phase 5:** response packaging (`package_builder`), 90/75/50 routing
  (`confidence_thresholds`), validation safety-net (`validation`), audit
  logger (`audit_logger`), gap detector. Covered by `test_response.py` (all four
  confidence bands) and `test_search_fallback.py` (no-answer + audit row).
  Live `/api/v1/search` path: `process_query → hybrid_search → rrf →
  package → validate → audit_log` (see `backend/app/api/v1/search.py`).
- **Phase 6 — Frontend + F1–F3 conversation kit:**
  - Next.js 15 (`output: 'export'`) app with `(auth)`/`(dashboard)` route
    groups, client-side JWT via `lib/auth.ts`, `lib/api-client.ts` calling
    FastAPI directly (no BFF).
  - `components/ui/{message,orb,conversation,response}.tsx` — full Framer
    Motion + Three.js (perlin-noise shader) conversation kit. The kit that was
    flagged "blocked / user-supplied" is in fact implemented and built.
  - `components/search/` (SearchBar, ResponsePackageCard, ConfidenceBadge,
    SourceCitation, RelatedQuestions) + `components/auth/LoginForm.tsx`.
- **Phase 8 — Evaluation framework:** `evaluation/run_benchmark.py`,
  `datasets/eval_questions.py` + `eval_20_questions.jsonl`,
  `metrics/{precision_recall,mrr,ndcg,hit_rate,latency_benchmark}.py`, and
  `reports/` (8 reports incl. the Phase-4 retrieval benchmarks).

## Verification this session (all green, no code changes)
- **Backend:** `pytest backend/tests -q` → **137 passed** (exit 0).
- **Frontend typecheck:** `npx tsc --noEmit` → **clean** (exit 0).
- **Frontend build gate (Phase 6 DoD):** `npm run build` → **succeeds** (exit 0);
  8 static pages prerendered, static export written to `frontend/out/`.
- **Phase 8 DoD #1 (determinism):** two consecutive `run_benchmark.py` runs
  with no code changes → identical accuracy (sub-question 100%, intent 58.3%,
  entity 91.7%); only ~3ms jitter on sub-2ms per-query latency.
- **Live retrieval benchmark (reranker ON):** `python -m evaluation.retrieval_benchmark`
  → recall@1 **86%**, recall@5/10 **100%**, MRR@10 **0.907**, end-to-end
  p95 **76ms**, **reranker p95 61ms** (< 200ms rule #6). Report:
  `evaluation/reports/retrieval_benchmark_20260806_202106.json`. (The real
  `c.embedding <=> %s` path works — it is exercised through the pooled
  connection that calls `register_vector`; a bare `SELECT (%s <=> %s)`
  without a vector-typed LHS is what fails to infer param types, and is not
  how the code queries.)
- **Live HTTP route smoke test** (`POST /api/v1/search/` with a real JWT,
  seeded in-scope + out-of-scope chunk): **PASS** —
  `routing=answer`, confidence 100, the in-scope (`lending`) chunk returned,
  the out-of-scope (`underwriting`) chunk **absent from the response and from
  the `audit_log.retrieved_ids`** (RBAC rule #1 verified in the serving path),
  and an `audit_log` row was written (rule #8). The backend was started
  socket-style (`--workers 1`, reranker + embeddings warm) on port 8009, then
  stopped; smoke seed data was deleted afterward (5 corpus docs + 39 corpus
  chunks left intact).

> Note: the Docker daemon on this Windows dev box flapped mid-session (npipe
> unreachable) and was recovered via `Start-Service com.docker.service`. The
> shared Postgres container was kept on the persistent `shared_pg_data` volume,
> so seeded corpus data survived.

## Test health
`pytest backend/tests -q` → **137 passed** (1 warning: Starlette httpx
deprecation — harmless, not a regression).

## Pending / Not started
- **Phase 7 — live EC2 verification:** the units are installed-ready and
  constraint-compliant
  (`shared-host-infra-scaffold/infra/systemd/hexa-backend.{socket,service}`
  listening 0.0.0.0:8001 via fd 3, `--workers 1`, `MemoryMax=200M`;
  `hexa-backend-idle.timer` → `idle_stop_watcher.sh` 10-min idle-stop) and
  the nginx server block (`nginx/conf.d/hexa-assistant.conf`) proxies `/api/`
  to the socket and serves `frontend/out/`. The remaining DoD items —
  `systemctl status` showing socket-listening/service-inactive-then-active,
  cold-start latency after a >10-min gap, and idle-stop confirming the service
  returns to inactive — require the shared EC2 host and are recorded as a
  baseline in `evaluation/reports/` only from there.
  **Action:** once on the host, follow `shared-host-infra-scaffold/infra/README.md`
  step 3, then run the verify `curl` sequence and append a cold-start baseline
  report to `evaluation/reports/`.

## Next step
Phase 7 live verification on the shared EC2 host (host-bound; can't be done
from this Windows dev workstation). Alternatively, the Phase 6 build gate is now
green and the static export at `frontend/out/` is ready to deploy to the path
referenced in `nginx/conf.d/hexa-assistant.conf` (`/opt/projects/hexa/frontend/out`).
