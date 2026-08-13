#!/usr/bin/env bash
# Runs once, after the .sql init scripts, via docker-entrypoint-initdb.d.
# Sets the password for the hexa_app application role from the compose
# environment (POSTGRES_APP_PASSWORD) so it is never committed to the
# repo. If the variable is unset, the role keeps no password and
# scripts/migrate_db.sh must provision it later.
set -euo pipefail

if [ -n "${POSTGRES_APP_PASSWORD:-}" ]; then
  # Bind the password as a psql variable (`:'name'` quoting) instead of
  # interpolating it into the SQL string — a `'` in the password would
  # otherwise break the statement (X11).
  psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname hexa_assistant \
    -v app_password="$POSTGRES_APP_PASSWORD" \
    -c "ALTER ROLE hexa_app WITH LOGIN PASSWORD :'app_password';"
  echo "hexa_app password provisioned from environment."
else
  echo "POSTGRES_APP_PASSWORD not set — hexa_app has no password yet; run scripts/migrate_db.sh to provision it."
fi