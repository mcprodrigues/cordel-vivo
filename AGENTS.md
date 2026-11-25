# AGENTS.md

## Mission

Cordel Vivo is a searchable archive of Brazilian cordel booklets for students, teachers, researchers and cordel poets. Computer vision reads the booklet, deterministic code recognizes the poetic form, an LLM enriches it with mandatory citations, and search combines text, vectors and cover images. The roadmap is in `docs/plano.md` (Portuguese, the original planning document), decisions in `docs/adr/` and the public contract in `docs/api-contract-v1.md`.

## Current phase

**F0 · Foundation.** Do not start work from later phases. A phase ends only when its gate has been measured.

| Phase | Gate |
|---|---|
| F0 Foundation | license of every item confirmed and recorded in the manifest |
| F1 Reading | CER measured and OCR engine chosen |
| F2 Poetics | form accuracy measured on the stanza golden set |
| F3 Search | recall@10 and nDCG@10 published (hybrid vs lexical vs dense) |
| F4 Graph and agent | judge calibrated against human annotation (kappa) |
| F5 Showcase | deploy, demo and README with results |

## Business rules

- **License before data.** No item enters the collection without a row in the manifest (`collection/manifest.csv`). An image without a confirmed license is never downloaded or indexed: only its metadata and a link to the source are stored.
- **The cover has its own license.** The woodcut (xilogravura) has its own author, the engraver, and its public domain term is computed per piece, separately from the booklet.
- **Public domain** (Brazilian Law 9.610/98, art. 41): 70 years counted from January 1st of the year after the author's death.
- **Declared and attributed authorship** are both stored, each with its source. Authorship is never "corrected" without a reference.
- **Stylometry only produces hypotheses**, always shown with a confidence level, never as a verdict.
- **Contemporary works** enter only with the poet's written authorization.
- **The manifest is edited by hand** and reviewed like a golden set. Each row has a stable UUID; an empty cell means unknown or not confirmed. Its columns mirror the collection item table, and a test keeps both in sync.
- **One decision point for images.** Whether an image may be downloaded, stored or indexed is decided only by `app.collection.manifest`; services and workers call it and never reimplement the rule. An empty license never allows an image.

### Open items

- **P-1** License vocabulary (booklet and cover) and which values allow downloading or indexing the image. Until it is defined, any confirmed license raises `UnresolvedPendingError`, and the database `license` table stays empty.
- **P-2** Job statuses. Current values are provisional.
- **P-3** Maximum attempts and backoff for the queue.
- **P-4** Minimum input DPI.
- **P-5** Rhyme scheme and meter of each poetic form, to be confirmed against the literature before becoming tests.

While an item is open, code uses a `TODO(P-N)` that fails with a clear error. Never invent a value for it.

## Language

- **English:** code, file and folder names, identifiers, tables, columns, comments, commit messages, docs (this file, README, ADRs, API contract), PRs and issues.
- **Portuguese:** `docs/plano.md` (the original plan), Portuguese domain data, and the names of poetic forms (`sextilha`, `decima`, `martelo_agalopado`…), which have no English equivalent.
- **Never** use the em dash in any text.

| Portuguese (domain) | English (code) |
|---|---|
| folheto | booklet |
| página / capa / miolo | page / cover / body |
| item do acervo / acervo / manifesto | collection_item / collection / manifest |
| autoria declarada / atribuída | declared_authorship / attributed_authorship |
| licença do folheto / da capa | booklet_license / cover_license |
| leitura / poética / enriquecimento / indexação | reading / poetics / enrichment / indexing |
| estrofe / verso | stanza / line |
| xilogravura / gravurista | woodcut / engraver |

## Stack and commands

- Python 3.13, one application package (`app/`) managed by `uv`; versions pinned in `pyproject.toml` and `uv.lock`.
- FastAPI + Uvicorn, Pydantic v2, `pydantic-settings`.
- Postgres 16 with `pgvector`, `unaccent` and Portuguese full-text search. Text, vectors, graph and queue all live in Postgres. Migrations are applied by Flyway (Community).
- S3-compatible object storage (SeaweedFS locally), accessed only through the S3 protocol.
- OpenCV and PDFium (`pypdfium2`) for reading.
- ruff (lint and format), mypy (strict), pytest (including the layer rules).
- Docker Compose in `infra/`; GitHub Actions for CI.

```bash
uv sync                                                       # install
uv run ruff check --fix && uv run ruff format                 # lint and format
uv run mypy                                                   # types
uv run pytest                                                 # tests, no network
set -a && . ./.env && set +a && uv run python -m app           # API on CORDEL_API_PORT
docker compose -f infra/docker-compose.yml --env-file .env up -d
docker compose -f infra/docker-compose.yml --env-file .env run --rm migrations migrate
# tests against local Postgres (CORDEL_DB_URL from .env)
uv run pytest -m db --force-enable-socket --allow-hosts=127.0.0.1
```

## Testing and evaluation

- `pytest` never calls an LLM or an external network: the network is blocked in the suite, and LLM and storage are mocked. Only dependency installation uses the network.
- Tests that spend tokens live in `*_live.py` and run only when Clara asks.
- Tests that need the database are marked `@pytest.mark.db` and run against local Postgres or the CI service container.
- Each test is named after the rule it checks (`test_cover_license_is_independent_of_booklet_license`), never after a value.
- Property tests cover determinism, ordering and idempotency.
- Every behavior change ships with a test.
- **Measure before changing:** a change of prompt, model, OCR or embedding lands only after running the `evaluation/` harness with `--compare-with <reference>`, which fails if any metric gets worse.
- Golden sets are annotated by hand and never rewritten automatically.

## Repository layout

```
app/main.py           create_app: the FastAPI application factory
app/settings.py       the only place configuration is read
app/dependencies.py   composition root: the only place concrete classes are built
app/security.py       authentication
app/api.py            mounts the routers
app/routers/          HTTP layer: validate input, call a service, serialize
app/services/         business logic; depends only on provider interfaces
app/providers/        Postgres, S3, OCR and LLM access
app/schemas/          Pydantic request and response models
app/errors.py         application errors
app/collection/       manifest and image license rule: pure, no I/O
app/poetics/          scansion, rhyme and form: pure, standard library only
app/workers/          one entry point per stage (reading, enrichment, indexing)
app/scripts/          offline jobs, run by hand
tests/                mirrors app/ (tests/routers/, tests/collection/...)
db/migrations/        V###__description.sql (Flyway)
evaluation/           golden sets and harness
collection/           manifest.csv (files live in collection/files/, outside git)
infra/                docker-compose
docs/                 plan, ADRs, API contract
```

There is no generic domain layer: a pure rule lives in a folder named after its subject, like `app/collection/` and `app/poetics/`.

Layer rules (enforced by `tests/test_dependency_rules.py`):
- `poetics` imports only the standard library and does no I/O;
- `collection` imports only the standard library, pydantic and `app.errors`, and does no I/O;
- routers never import providers or workers; they call services;
- services depend only on `app.providers.interfaces`, never on a concrete provider;
- workers never import routers;
- collaborators are passed through constructors and wired only in `app/dependencies.py`;
- imports inside `app` are absolute.

Database objects: every constraint and index is named explicitly with a prefix (`pk_`, `fk_`, `uq_`, `ck_`, `ix_`) followed by the table and the columns or rule. Enforced by tests on the SQL files and on the database catalog.

## Git workflow

- `main` (release) and `develop` (integration). Work happens on `type/N-slug` branches off `develop`, with PRs into `develop`. Only `develop` merges into `main`.
- Commits in English, imperative mood: `type(#N - module): description` (e.g. `feat(#3 - api): add authentication to all routes`). Types: `feat`, `fix`, `refact`, `chore`, `docs`, `db`, `test`. Without an issue, use `#0`. No attribution trailers.
- One PR per issue, with "What was done?", "How to test?" and `Issue: #N`. Clara reviews and merges.
- CI (`.github/workflows/ci.yml`) runs the same checks as the hooks (job `check`) and the migrations plus `pytest -m db` against Postgres (job `db`) on every PR and on pushes to `main` and `develop`; a PR merges only with CI green.
- Hooks live in `.githooks/` (`git config core.hooksPath .githooks`): `commit-msg` checks the format, `pre-commit` runs ruff, `pre-push` runs mypy and pytest.
- A change to the public contract updates `docs/api-contract-v1.md` in the same PR.
- Every architecture decision gets an ADR in `docs/adr/` (Context, Decision, Consequences, Alternatives).
- A new rule or a resolved open item is added to this file in the same PR.

## Inviolable principles

1. **The LLM decides, code executes.** Every LLM output is validated with Pydantic; side effects are performed by deterministic code.
2. **Mandatory citation.** Every LLM extraction points to line ids of the transcription; code checks that the passage exists and discards whatever does not.
3. **Poetics never uses an LLM.** `app/poetics` is pure and fully testable.
4. **License before data.** A test enforces the manifest rule and the image license rule.
5. **Separate processes.** The API and each worker run as their own process from the same codebase, and they integrate only over HTTP or through the queue, never by calling each other's code.
6. **Idempotent jobs.** Each ingestion stage is a re-runnable job; the file's SHA-256 is the idempotency key.
7. **Explicit, configurable timeout** on every external call (LLM, storage, HTTP).
8. **Configuration only through environment variables.** Every new variable goes into `.env.example` in the same PR.
9. **LLM model and provider come from configuration**, with roles (`ocr_reader`, `extractor_a`, `extractor_b`, `adjudicator`, `judge`) and a fallback chain. Extractors A and B come from different model families.
10. **Auth everywhere**, including `/docs` and `/openapi.json`. Only `/health` is public.
11. **The database changes only through new migrations.** An applied migration is never edited (Flyway's checksum blocks it).
12. **Pinned images.** Every Docker image uses a tag plus digest.

## Never

- Commit `.env`, credentials, or collection images and PDFs.
- Use PyMuPDF, MinIO or any AGPL dependency.
- Push directly or force-push to `main` or `develop`.
- Use `--no-verify`.
- Run `*_live.py` or deploy without being asked.
- Invent a business rule, value or threshold not stated in this file: ask, or open a `P-N` item.
- Weaken or delete a failing test to make the suite pass.
- Copy code, prompts or data from Exitus.
