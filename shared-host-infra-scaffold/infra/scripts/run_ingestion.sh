#!/usr/bin/env bash
#
# Runs the document ingestion pipeline (OCR, chunking, entity
# extraction, embedding generation, indexing) as a one-shot batch job.
#
# This deliberately does NOT run inside the FastAPI process. The
# embedding model is the heaviest component in the stack —
# loading it into the always-on API process means paying that RAM
# cost 24/7 even when nobody is uploading documents. Running it
# here means the memory is only held for the duration of the job.
#
# Trigger this manually, via cron, or via a lightweight upload-queue
# consumer — never call it from inside app.main directly.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="${HEXA_BACKEND_DIR:-$(cd "${SCRIPT_DIR}/../../.." && pwd)/backend}"
VENV_DIR="${HEXA_VENV_DIR:-${BACKEND_DIR}/.venv}"
PYTHON="${VENV_DIR}/bin/python"
[ -x "${PYTHON}" ] || PYTHON="${VENV_DIR}/Scripts/python"

cd "${BACKEND_DIR}"

# Storage dirs are resolved from backend/.env settings; the queue must
# match settings.storage_pending_dir ('storage/pending' by default).
# Resolve to an absolute path anchored at the backend so the upload
# endpoint and the ingestion job always agree on the same directory.
QUEUE_DIR="${HEXA_QUEUE_DIR:-${BACKEND_DIR}/storage/pending}"
mkdir -p "${QUEUE_DIR}"

echo "[$(date -Iseconds)] Starting ingestion batch (queue=${QUEUE_DIR})"
"${PYTHON}" -m app.documents.ingest_batch --queue-dir "${QUEUE_DIR}"
echo "[$(date -Iseconds)] Ingestion batch complete"

# Process exits here — the embedding model RAM is
# released back to the OS, not held resident.