#!/usr/bin/env bash
set -euo pipefail

# Seed the database with initial schema + users.
# Run this against the shared Postgres instance, from the repo root
# (e.g. ./shared-host-infra-scaffold/infra/scripts/migrate_db.sh or
# via `make migrate`). The script locates the backend venv by walking
# up from its own location, so it works from any cwd.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Backend location precedence: explicit env override > documented install
# location (/opt/projects/hexa/backend) > repo checkout (up 3 dirs).
# The "up 3 dirs" fallback is only correct for a repo checkout; at the
# documented install path the script lives in
# /opt/projects/hexa/infra/scripts, so "up 3" wrongly resolves to
# /opt/projects/backend (X3).
if [ -n "${HEXA_BACKEND_DIR:-}" ] && [ -d "${HEXA_BACKEND_DIR}" ]; then
  BACKEND_DIR="${HEXA_BACKEND_DIR}"
elif [ -d "/opt/projects/hexa/backend" ]; then
  BACKEND_DIR="/opt/projects/hexa/backend"
else
  BACKEND_DIR="$(cd "${SCRIPT_DIR}/../../.." && pwd)/backend"
fi
VENV_DIR="${HEXA_VENV_DIR:-${BACKEND_DIR}/.venv}"
PYTHON="python3"

if [ -x "${VENV_DIR}/bin/python" ]; then
  PYTHON="${VENV_DIR}/bin/python"
elif [ -x "${VENV_DIR}/Scripts/python" ]; then
  PYTHON="${VENV_DIR}/Scripts/python"
fi

cd "${BACKEND_DIR}"

# Load backend/.env so HEXA_DATABASE_URL is available.
if [ -f "${BACKEND_DIR}/.env" ]; then
  set -a
  # shellcheck disable=SC1091
  source "${BACKEND_DIR}/.env"
  set +a
fi

# Load the shared infra .env so POSTGRES_SUPERUSER_PASSWORD is available
# (it lives with the docker-compose, NOT backend/.env — X4).
SHARED_DIR="${HEXA_SHARED_DIR:-$(cd "${SCRIPT_DIR}/../shared" && pwd)}"
if [ -f "${SHARED_DIR}/.env" ]; then
  set -a
  # shellcheck disable=SC1091
  source "${SHARED_DIR}/.env"
  set +a
fi

echo "Provisioning hexa_app role password (idempotent)..."
"${PYTHON}" - <<'PY'
import os
import psycopg
from urllib.parse import urlparse

url = os.getenv("HEXA_DATABASE_URL", "")
if not url:
    raise SystemExit("HEXA_DATABASE_URL not set in backend/.env")
parsed = urlparse(url)
admin_url = f"postgresql://{parsed.hostname}:{parsed.port or 5432}/hexa_assistant"
conn = psycopg.connect(admin_url, user=os.getenv("POSTGRES_SUPERUSER", "admin"),
                       password=os.getenv("POSTGRES_SUPERUSER_PASSWORD", ""))
conn.autocommit = True
with conn.cursor() as cur:
    cur.execute(f"ALTER ROLE hexa_app WITH LOGIN PASSWORD {psycopg.sql.Literal(parsed.password)}")
conn.close()
print("hexa_app password provisioned.")
PY

echo "Creating schema..."
"${PYTHON}" -m app.db.postgres.schema

echo "Seeding users..."
"${PYTHON}" -m app.db.postgres.seed_db

echo "Done."
