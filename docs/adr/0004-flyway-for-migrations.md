# ADR 0004: Apply database migrations with Flyway

- **Status:** accepted
- **Date:** 2026-11-25
- **Issue:** #5

## Context

The schema lives in plain SQL files named `V###__description.sql` under `db/migrations/` (AGENTS.md). The database changes only through new migrations, and an applied migration is never edited (principle 11). We need a tool that applies the files in order, records what was applied, and refuses to continue when an applied file has changed.

The services are Python, but the migrations are SQL that any tool could run. The project forbids AGPL dependencies, and every Docker image is pinned by tag and digest (principle 12). CI must apply the migrations to a real Postgres before the database tests run.

## Decision

Use **Flyway Community** (Apache-2.0), run from its official Docker image, pinned by tag and digest:

- locally as the `migrations` service in `infra/docker-compose.yml`, under the `tools` profile, so `up` does not start it: `docker compose -f infra/docker-compose.yml --env-file .env run --rm migrations migrate`;
- in CI, in the `db` job, with `migrate` followed by `validate` against a pgvector service container, before `pytest -m db`.

Only the core commands are used: `migrate`, `info`, `validate` and, as a manual repair step, `repair`. Telemetry is disabled.

## Consequences

- The `V###__description.sql` naming already in AGENTS.md is Flyway's own convention, so no renaming is needed.
- Flyway stores a checksum per applied migration in `flyway_schema_history`. Editing an applied file makes `validate` and `migrate` fail with a checksum mismatch, which turns principle 11 into a check instead of a convention. This was verified locally.
- Nothing Java is installed on the host or in the Python environment; Docker is enough.
- Migrations stay plain SQL with no Flyway-specific syntax, so the tool can be replaced without rewriting them.
- Flyway is developed by Redgate, which also sells paid editions. If the Community edition drops a command we use or changes license, we revisit this decision.
- Rollbacks are forward-only: a mistake is fixed by a new migration.

## Alternatives

- **A runner written in Python** (psycopg plus a table of applied files and checksums). No extra image, but it is code to write, test and maintain for a solved problem.
- **Alembic.** The standard Python choice, but it is built around SQLAlchemy models and Python migration scripts. Our schema is SQL first and the services do not use SQLAlchemy.
- **dbmate or golang-migrate.** Small and SQL first, but they use different file naming (timestamps or up/down pairs), so the convention already in AGENTS.md would change.
- **yoyo-migrations.** SQL migrations in Python with a small footprint. It tracks applied migrations by id, without a checksum check equivalent to Flyway's `validate`, which is the property principle 11 needs most.
