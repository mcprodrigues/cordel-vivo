# ADR 0002: Run the ingestion queue in Postgres with SKIP LOCKED

- **Status:** accepted
- **Date:** 2026-11-25
- **Issue:** #3

## Context

Each booklet goes through four asynchronous stages: reading, poetics, enrichment and indexing. Each stage is a job that must be idempotent and re-runnable, and the SHA-256 of the uploaded file is the idempotency key (AGENTS.md, principle 6). Services are autonomous and integrate only over HTTP or through the queue (principle 5).

The upload route answers `202` with a job id, and the job route reports progress per stage (`docs/plano.md`, "Busca e API"), so job state has to be queryable together with the booklet it belongs to.

ADR 0001 already puts all project data in Postgres. Expected job throughput is not known yet. It is to be measured when the pilot collection exists. Some stages call slow external models (OCR, LLM), so jobs are long compared with the time to claim one.

## Decision

Keep the queue in a **Postgres table** and let workers claim jobs with `SELECT ... FOR UPDATE SKIP LOCKED`, in a transaction that marks the job as taken.

- A job is identified by booklet and stage. A unique constraint on that pair makes enqueueing idempotent: re-submitting the same file (same SHA-256, therefore same booklet) does not create duplicate jobs.
- Each job records its stage, status, attempts, the time it becomes available, and who locked it and when, so that a crashed worker's job can be picked up again.
- A partial index over pending jobs keeps the claim query cheap.
- The maximum number of attempts and the backoff between them are open item **P-3**. They will come from environment variables, with no default in code, when the first worker exists (F1).
- The job statuses are open item **P-2**. The values in the first migration are provisional.

## Consequences

- Enqueueing a job and writing the booklet happen in the same transaction, so there is no window where one exists without the other.
- Job progress is a plain query, which serves the job route directly.
- No extra service to run, monitor or back up.
- Workers poll. The polling interval becomes a configuration value, and a status of pending in a manual test may only mean the worker has not polled yet. `LISTEN/NOTIFY` can be added later to wake workers without changing the table.
- The database carries the queue load. If measured throughput or lock contention becomes a problem, we revisit this decision.

## Alternatives

- **Redis with RQ.** Mature, simple workers and low latency. It is not chosen because it adds a second stateful service, and job state would live apart from the booklets, so idempotency and progress reporting would need to be kept consistent across two stores.
- **A broker such as RabbitMQ (or Celery on top of one).** Built for higher throughput and routing than this project needs, with the same split-state problem and more operational weight.
- **A Postgres queue library (for example procrastinate or pgqueuer).** Same storage model as this decision. Not chosen for now because the queue logic is small, and writing it keeps the schema under our migrations. It stays an option for F1 if the worker code grows.
