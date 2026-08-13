-- Runs once, on first container start, via docker-entrypoint-initdb.d.
-- Add one file like this per project — each project gets its own
-- database inside the ONE shared Postgres instance, not its own
-- Postgres process.
--
-- The application role password is set in 02_set_app_password.sh
-- (from the POSTGRES_APP_PASSWORD compose env var) so it never lands
-- in this repo.

CREATE DATABASE hexa_assistant;

\connect hexa_assistant

CREATE EXTENSION IF NOT EXISTS vector;   -- pgvector, replaces Qdrant

CREATE ROLE hexa_app LOGIN;
GRANT ALL PRIVILEGES ON DATABASE hexa_assistant TO hexa_app;
GRANT ALL PRIVILEGES ON SCHEMA public TO hexa_app;

-- Noisy-neighbor control (V3.3 §2.1): cap per-query runtime so one
-- runaway hybrid retrieval can't starve CPU/IO for every other project
-- sharing this Postgres instance. The same value is the container default
-- in postgresql.conf.
ALTER ROLE hexa_app SET statement_timeout = '10s';