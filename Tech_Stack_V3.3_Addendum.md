# Mortgage CRM Intelligent Knowledge Assistant — Tech Stack Addendum (V3.3)

Companion to `Final_Tech_Stack_V3.2.md`, `Final_Folder_Structure.md`, and
`Final_System_Design.md`. This addendum does not replace V3.2 — every
decision in V3.2 is affirmed and kept. This document adds the items that
were implicit, ambiguous, or missing, organized by the same layers, plus
an expanded risk register and a prioritized action list.

Convention used below: **[QUICK WIN]** = near-zero cost/effort, do before
launch. **[BEFORE PROD]** = required before real user data/traffic.
**[DEFER]** = valid to postpone, but must stay tracked, not forgotten.

---

## 1. Application Layer — Additions

| Item | Detail | Priority |
|---|---|---|
| JWT storage location | V3.2 specifies JWT auth but not where the token lives client-side. Given this handles financial PII, store it in an **httpOnly, `Secure`, `SameSite=Strict` cookie**, not `localStorage`/`sessionStorage`. `localStorage` is readable by any injected script (XSS), which is a materially worse blast radius for mortgage data. | BEFORE PROD |
| CSP headers | Since Nginx serves the static export directly, add a `Content-Security-Policy` header at the Nginx level (`default-src 'self'`, tightened as needed for any third-party fonts/scripts). Costs nothing, closes an easy XSS vector. | QUICK WIN |
| Socket-activation vs. warm ML models | **This is the single biggest internal contradiction in V3.2** and needs explicit resolution (see §6, Risk R1). Socket activation implies "cold process, starts on request." The ML layer implies "load once, keep warm." These two goals conflict unless scoped correctly — see the Infrastructure section below for the resolution. |
| Worker count rationale | V3.2 correctly pins `--workers 1`, but the *reason* isn't documented anywhere: each additional Uvicorn worker would load its own independent copy of spaCy + GLiNER + embedding model + reranker, multiplying ML RAM linearly. This should be written into the design doc as a hard constraint, not just a config value, so a future contributor doesn't "fix" it by scaling workers under load. | QUICK WIN (docs only) |
| Rate limiting | No rate limiting is specified anywhere on the FastAPI/Nginx boundary. On a 1 GiB box with a cold-start penalty, a handful of concurrent requests during the idle-to-warm transition could exhaust memory or CPU credits. Add `limit_req` at the Nginx layer per project. | BEFORE PROD |
| Request size limits | No max body size specified for document upload endpoints. Combined with local filesystem storage and 1 GiB RAM, an unbounded upload is a straightforward DoS vector. Set `client_max_body_size` in Nginx and a matching limit in FastAPI. | BEFORE PROD |

> **DONE (2026-08-13):** Rate limiting (`limit_req`, 10r/s burst 20 on `/api/`, 30r/s on `/health`) and `client_max_body_size 20m` added in `shared-host-infra-scaffold/infra/shared/nginx/conf.d/hexa-assistant.conf`; frontend static nginx (`frontend/nginx.conf`) gets 20r/s burst 40 and `client_max_body_size 1m`. FastAPI limit (`settings.max_upload_bytes`, 20MB) already existed and matches the Nginx cap.

> **DONE (2026-08-13):** Loguru is pinned in `requirements.txt` but unused — all backend logging goes to stdout (captured by systemd journald, which self-rotates). The actual unbounded-growth risk is Docker's json-file driver, so rotation `max-size: 10m / max-file: 3` was added to every container in both `docker-compose.yml` and `infra/shared/docker-compose.yml`.

---

## 2. Data Layer — Additions

### 2.1 Shared Postgres instance — noisy-neighbor controls

V3.2 consolidates all projects into one Postgres instance with per-project
databases. This is the right memory optimization but introduces a resource
*contention* risk that isn't mitigated anywhere in the current doc.

| Control | Recommended setting | Why |
|---|---|---|
| `statement_timeout` | Set per-role (e.g., 5–10s for the app role) | Prevents one slow/runaway query in one project from starving CPU/IO for all others sharing the instance |
| `max_connections` | Cap conservatively (e.g., 20–40 total across all projects) and use a small connection pool (or none, given single Uvicorn worker) per project | Each connection reserves backend memory (~5–10MB); on 1 GiB this adds up fast |
| `work_mem` | Keep low (4MB default is usually fine); raise only per-query with `SET LOCAL` if a specific vector/FTS query needs it | Prevents a single complex query (e.g., hybrid BM25+vector) from ballooning memory |
| `shared_buffers` | Explicitly size (don't leave at Postgres default, which assumes a dedicated host) — typically 15–25% of *available* RAM on a shared box | Postgres defaults assume it owns the machine; on a shared 1 GiB host this needs manual tuning |
| Per-database resource groups | If contention becomes real, consider `pg_cgroup`-style OS-level cgroup limits per project's connection pool, not just Postgres-level settings | Optional, only needed once actual traffic exists |

> **DONE (2026-08-13):** `statement_timeout` set per-role: `ALTER ROLE hexa_app SET statement_timeout = '10s'` in `01_hexa_assistant.sql` and idempotently in `infra/scripts/migrate_db.sh`; a 30s floor for every other role added to `postgresql.conf`. `max_connections=15`, `work_mem=2MB`, `shared_buffers=32MB` were already set.

### 2.2 pgvector index strategy — decision, not "or"

V3.2 lists "pgvector IVFFlat **or** HNSW" as if either is a fine default.
This needs to be an explicit decision:

- **HNSW**: better query latency and recall, but higher build-time RAM and
  slower index builds. Reasonable default *if* corpus size is meaningfully
  large (tens of thousands of chunks+).
- **IVFFlat**: cheaper to build, needs `lists` tuned proportional to row
  count (`rows / 1000` is a common starting heuristic) and periodic
  `ANALYZE` to stay accurate as data grows.
- **No index at all**: for a single mortgage brokerage's document corpus,
  the actual chunk count may be small enough (low tens of thousands or
  fewer) that a sequential scan with cosine distance is fast enough and
  costs zero extra RAM/build time. **Recommendation: start with no vector
  index, add IVFFlat only if p95 latency data says you need it.** This is
  consistent with V3.2's own "reintroduce Redis only when traffic
  justifies it" philosophy — apply the same logic here.

### 2.3 Lightweight caching without reintroducing Redis

V3.2 removes Redis for MVP, which is correct. A near-zero-cost partial
substitute: an **in-process LRU cache** (e.g., Python's `functools.lru_cache`
or a small bounded dict) for repeated identical queries within a single
warm process lifetime. This costs a few KB–MB, requires no new
infrastructure, and disappears cleanly on idle-stop — fully consistent
with the socket-activation model. | QUICK WIN

### 2.4 Durability — filesystem and database backups

**This is the most significant gap in V3.2.** Local filesystem storage
(`storage/pending/`, `storage/processed/`) and a single Postgres instance
on one EBS volume means: if that volume is lost, corrupted, or the
instance is terminated, **mortgage documents and all data are permanently
gone** — not just temporarily unavailable (which is what the existing
"Single point of failure" risk in V3.2 describes). These are two different
failure modes and both need coverage:

| Data | Recommended mitigation | Priority |
|---|---|---|
| Postgres (all project DBs) | Nightly `pg_dump` per database (or `pg_dumpall` for the instance) to S3, with a retention policy (e.g., 30 daily + 12 monthly) | BEFORE PROD |
| Local filesystem documents | Periodic sync (e.g., `aws s3 sync`) of `storage/processed/` to an S3 bucket; `storage/pending/` is more transient but should still be covered if ingestion runs are long | BEFORE PROD |
| EBS volume itself | Enable automated EBS snapshots (AWS Backup or a simple cron + `aws ec2 create-snapshot`) as a coarse-grained safety net underneath the above | BEFORE PROD |
| Restore testing | A backup that's never been restored is not a backup — do at least one documented test restore before go-live | BEFORE PROD |

### 2.5 Encryption at rest

Not addressed anywhere in V3.2. Given mortgage documents are regulated,
sensitive financial data:

- Confirm the **EBS volume has encryption enabled** (a one-time setting at
  volume creation, effectively free on modern EC2 instance types).
- Confirm the **S3 backup bucket** (once added per §2.4) has default
  encryption (SSE-S3 or SSE-KMS) enabled.

Priority: BEFORE PROD.

---

## 3. NLP / ML Layer — Additions

| Item | Detail | Priority |
|---|---|---|
| spaCy pipeline weight | `disable=["ner"]` is a good first cut, but if the only remaining need is sentence boundary detection for chunking, a full statistical pipeline is still heavier than necessary. Consider `spacy.blank("en")` + a rule-based `sentencizer`, or the lightweight `en_core_web_sm` with *every* unneeded component disabled (`tagger`, `parser`, `lemmatizer`, `attribute_ruler` if not used downstream), keeping only what chunking actually consumes. | QUICK WIN |
| GLiNER load timing — must be explicit | V3.2 says GLiNER is "loaded query-time (search) and batch-time (ingestion)" — this is ambiguous between "loaded once when the process starts, reused for the process's lifetime" (correct, cheap) and "loaded fresh on every request" (expensive, adds real latency and CPU-credit cost on every single search). **This needs to be pinned down explicitly in the design doc as: model loaded once at process startup (after socket activation wakes the process), held in memory for the life of the process, released on idle-stop.** This directly interacts with the socket-activation cold-start tradeoff — see Risk R1 below. | BEFORE PROD (docs + code review) |
| Reranker size: base vs. small | V3.2 defaults to `bge-reranker-base` (quantized). Given the stack's own stated philosophy — quantize and shrink everything to protect a 1 GiB shared budget — `base` is still roughly 2x the parameters of `bge-reranker-small`. **Recommendation: start with `small`, and only move to `base` if the Evaluation Framework's retrieval-quality metrics show a real, measured gap.** This is the same "don't pay for capacity you haven't proven you need" logic V3.2 already applies to Redis and Qdrant — apply it here too. | QUICK WIN (config change) |
| Domain-specific tuning — synonym dictionary | The synonym dictionary and query expansion layer are listed as generic infrastructure with no mortgage-specific content specified. Populate it with actual domain jargon and expansions: DTI ↔ debt-to-income, LTV ↔ loan-to-value, APR ↔ annual percentage rate, PMI ↔ private mortgage insurance, escrow, underwriting, amortization, points ↔ discount points, etc. This is low engineering effort and directly improves retrieval quality on the domain this product exists for. | QUICK WIN |
| Domain-specific tuning — entity labels | GLiNER is flexible-label by design; V3.2 doesn't specify what labels it's configured to extract. Generic NER labels (PERSON, ORG, DATE) are a weak fit for a mortgage CRM. Configure a **custom label set**: loan officer name, loan number, property address, loan type (Conventional / FHA / VA / USDA), borrower name, lender name, closing date, interest rate. This materially improves both search filtering and downstream CRM linkage. | QUICK WIN |
| Model artifact versioning | Not specified: where are the quantized ONNX model files stored/pinned (a specific version/commit), so a redeploy doesn't silently pull a different model with a different memory footprint or different eval scores? Pin exact model file hashes/versions in the repo or a manifest. | DEFER (but track) |

---

## 4. Search & Ranking — Additions

| Item | Detail | Priority |
|---|---|---|
| FTS index maintenance | BM25 via Postgres full-text search needs a **GIN index on the `tsvector` column** (not just a plain column) to stay performant, plus a routine `VACUUM`/`ANALYZE` schedule (autovacuum defaults are usually fine, but should be explicitly confirmed enabled and not tuned down anywhere in the shared-instance config). Without this, FTS performance degrades silently and gradually as document volume grows — the kind of regression that's easy to miss until it's already bad. | BEFORE PROD |
| RRF weight tuning visibility | Reciprocal Rank Fusion combines BM25 + cosine similarity, but the relative weighting between the two isn't surfaced anywhere as a tunable, tracked value. Recommend exposing it as a named config value (not a magic number in code) so the Evaluation Framework mentioned in the Confidence/Weighted Scoring row can actually tune it against real eval data. | DEFER (but track) |

---

## 5. Infrastructure Layer — Additions

| Item | Detail | Priority |
|---|---|---|
| Monitoring stack footprint conflict | **This is the second major internal contradiction in V3.2.** Self-hosting Prometheus + Grafana on the same 1 GiB box you're trying to protect is expensive — Prometheus alone commonly runs 100–200MB+ resident, before Grafana's own footprint. That's 10–20%+ of total system RAM spent monitoring an environment whose entire design philosophy is minimizing footprint. **Recommendation: use a hosted free tier instead** — Grafana Cloud's free tier, or plain CloudWatch metrics + alarms for CPU credit balance and memory, with no local monitoring process running on the instance at all. | BEFORE PROD |
| Secrets management | Not specified anywhere: where do JWT signing secrets and DB credentials live? Options in order of preference for this scale: AWS SSM Parameter Store (free, no new infra) > a systemd `EnvironmentFile` with locked-down permissions (`600`, owned by the service user) > a `.env` file (acceptable only if excluded from version control and permissions-locked). **Explicitly avoid** committing secrets to the repo or baking them into container images. | BEFORE PROD |
| CI/CD memory-budget gate | V3.2's `eval_on_pr.yml` gates merges on retrieval-quality regression — genuinely strong practice, ahead of most MVPs. Add a **companion CI check that measures peak RSS** during a simulated full model-loading run (spaCy + GLiNER + embedding model + reranker all warm at once), and fails the build if it exceeds a set threshold (e.g., 700MB, leaving headroom for Postgres + Nginx + OS). Without this, a single new dependency or a "small" model upgrade can silently blow the 1 GiB ceiling in production with zero warning until an OOM kill happens live. | BEFORE PROD |
| Audit log immutability | The audit log is correctly kept as a separate append-only Postgres table — good instinct for a compliance artifact. But it still lives on the same instance that can fail or (in a worst case) be tampered with by anyone with DB access. Recommend a **periodic export of the audit table to immutable storage** — S3 with Object Lock (WORM mode) — so audit history survives both instance loss and any attempt to alter historical records after the fact. | BEFORE PROD (regulated data) |
| Log rotation | Loguru is specified for synchronous file-based logging, but no rotation/retention policy is mentioned. Unbounded log files on a small EBS volume will eventually fill the disk. Configure Loguru's built-in rotation (size- or time-based) and a retention cap. | QUICK WIN |
| Dependency update / patching cadence | Not specified: how OS packages, Python dependencies, and the base Docker images get security-patched over time. At minimum, enable `unattended-upgrades` for OS-level security patches and add a scheduled (e.g., monthly) Dependabot/`pip-audit` pass for the Python layer. | DEFER (but track) |

---

## 6. Expanded Risk Register

The three risks already tracked in V3.2 (CPU credit contention, cold-start
latency, single point of failure) are accurate and kept as-is. The
following are new risks that fall directly out of the decisions in V3.2
but weren't written down anywhere in that document.

### R1 — Socket activation vs. warm ML models (internal contradiction)

**The core tension:** systemd socket activation is designed around the
assumption that a cold process is cheap to start. That's true for a
typical web backend. It is **not** true here — starting this backend means
loading spaCy, GLiNER, the embedding model, and the reranker into memory,
which is a real, measurable cost (likely low-single-digit seconds, not
milliseconds). Every idle-stop → next-request cycle pays this cost again.

This needs one of two explicit resolutions, and V3.2 doesn't currently
pick one:

- **(a) Accept the cold-start cost as a known tradeoff** for low-traffic
  demo use (this is consistent with the existing "Cold-start latency" risk
  already listed in V3.2) — in which case, make sure the idle-timeout
  (currently 10 min) is tuned so this doesn't fire on every single
  request during normal usage patterns, only genuine idle periods.
- **(b) Lengthen the idle-timeout or move to always-warm** for any project
  where a user might reasonably issue two searches five minutes apart and
  experience a multi-second stall on the second one just because the
  first one triggered a stop.

Either is defensible — but the choice and its latency impact needs to be
**measured and documented**, not left implicit.

### R2 — Concurrent peak-memory ceiling isn't empirically verified

Every individual ML component's memory footprint is documented in
isolation (embedding model ~35MB, reranker quantized, GLiNER "smallest
variant," etc.), but there's no evidence anywhere in V3.2 that the **sum**
— all components warm simultaneously, plus Postgres, plus Nginx, plus OS
overhead, plus swap pressure — has actually been load-tested on the real
1 GiB target instance. Advertised per-component footprints and real
concurrent RSS under load often diverge meaningfully. **Recommend a load
test on an actual t3.micro before go-live**, not just a paper budget.

### R3 — No backup/disaster-recovery strategy (data-loss risk, distinct from downtime risk)

Covered in detail in §2.4. Flagged here explicitly as its own risk-register
line because it's a different failure category than the existing "SPOF"
risk: SPOF describes *downtime*; this describes **permanent loss of
regulated financial documents** with no recovery path. For a mortgage
product specifically, this likely intersects with real retention/compliance
obligations, which raises the severity further.

### R4 — No secrets management strategy

Covered in §5. Flagged as a risk-register item because credential handling
on a shared multi-project host is exactly the kind of thing that gets
solved "temporarily" with a plaintext `.env` file and never revisited.

### R5 — No encryption-at-rest confirmation

Covered in §2.5. Low effort to close, but currently unconfirmed either way
in the source documents, which for financial data is itself the issue —
it needs to be a stated, verified fact, not an assumption.

### R6 — Noisy-neighbor contention on shared Postgres

Covered in §2.1. Distinct from the CPU-credit-contention risk already in
V3.2 (which is host-level/CPU) — this is Postgres-level (connections,
locks, query load) and needs its own mitigation even if CPU credits are
healthy.

### R7 — Monitoring stack works against its own footprint goal

Covered in §5. Self-hosted Prometheus + Grafana is a meaningful,
avoidable chunk of the exact resource budget the rest of this stack was
redesigned to protect.

---

## 7. Summary — What Changed From V3.2

| Change type | Count | Examples |
|---|---|---|
| **Resolved contradiction** | 2 | Socket activation vs. warm ML models (R1); self-hosted monitoring vs. RAM budget (R7) |
| **New risk identified** | 5 | R2 (untested peak memory), R3 (no backup/DR), R4 (no secrets mgmt), R5 (no encryption-at-rest confirmation), R6 (noisy-neighbor Postgres) |
| **Ambiguity resolved into explicit decision** | 2 | pgvector index choice (§2.2), GLiNER load timing (§3) |
| **Quick, low-cost additions** | ~10 | CSP headers, LRU cache, mortgage-specific synonyms/entities, reranker size default, log rotation, GIN index for FTS |
| **New "before prod" requirements** | ~12 | Backups, encryption-at-rest, secrets management, rate limiting, CI memory-budget gate, audit log export to immutable storage |

**Nothing in V3.2 is reversed.** Every technology choice, removal, and
justification in the original document remains correct for this scale and
use case — this addendum closes gaps and resolves ambiguities, it doesn't
change direction.
