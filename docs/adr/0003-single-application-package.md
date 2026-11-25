# ADR 0005: One application package organized by layer

- **Status:** accepted
- **Date:** 2026-11-25
- **Issue:** #15

## Context

The first layout was a uv workspace with three members (`packages/contracts`, `packages/poetics` and `services/api`), each with its own `pyproject.toml`, plus import-linter contracts between them. The plan calls for an API and three workers that talk only over HTTP or the queue, which led to one member per service.

For a project of this size, the workspace added cost without benefit: every member needed its own build configuration, version bounds were repeated, and moving code between members meant changing package names.

## Decision

- One package, `app/`, with one `pyproject.toml`, on Python 3.13.
- Layers: routers, services, providers, schemas, settings, a composition root in `app/dependencies.py` and interfaces next to each layer.
- No generic domain layer. Pure rules live in a folder named after their subject (`app/collection/`, `app/poetics/`).
- The API and each worker are separate processes started from the same codebase (`python -m app`, `python -m app.workers.<stage>`). They integrate only over HTTP or through the queue.
- Layer rules are checked by a test on import statements; import-linter is removed.

## Consequences

- One place for dependencies and tool configuration, and plain `app.*` imports.
- All processes share one dependency set, so the API image also carries the libraries of the workers. If an image grows too large, a worker can get its own optional dependency group without changing the layout.
- The isolation between the API and the workers is now a rule checked by tests instead of a package boundary.

## Alternatives

- **Keep the uv workspace.** Stronger boundaries, but more configuration than the project needs today.
- **Add a `domain/` layer.** It would hold only the manifest rules and errors for now; a folder per subject says more and avoids an empty generic layer.
- **One repository per service.** Far more overhead, and the services share models and rules.
