# ADR 0001: Use Postgres with pgvector instead of Weaviate

- **Status:** accepted
- **Date:** 2026-11-25
- **Issue:** #3

## Context

Cordel Vivo needs to store and query several kinds of data about the same booklets:

- structured metadata and licenses per collection item, with constraints (AGENTS.md, "License before data");
- transcriptions in two layers (diplomatic and normalized), searched with Portuguese full-text search and `unaccent`;
- dense vectors for stanzas and for cover images (F3);
- a knowledge graph of booklets, declared and attributed authors, engravers, characters, places, themes and forms (F4);
- the ingestion job queue (see ADR 0002).

Search fuses lexical and dense results with RRF and filters by form, theme, author and decade, all of which come from earlier pipeline stages. Those filters and the lexical ranking need to see the same rows as the vector index.

The project is a portfolio piece maintained by one person. The sibling project Astros already uses Weaviate as its document store, and the plan (`docs/plano.md`) recommends a different stack here.

Collection size and query load for v1 are not known yet. They are to be measured once the pilot collection is defined in F0.

## Decision

Use **Postgres 16 with the `pgvector` extension** as the single store for metadata, transcriptions, full-text indexes, vectors, the graph (node and edge tables with recursive queries) and the queue. Add `unaccent` and a Portuguese text search configuration for the lexical side.

The local environment uses the official `pgvector/pgvector` image for Postgres 16, pinned by tag and digest.

## Consequences

- Lexical search, vector search, structured filters and license checks run in one query engine, in one transaction, with foreign keys between them. RRF fusion can be done in SQL or in the service over two result lists from the same database.
- One service to run, back up and migrate. Schema changes go through Flyway migrations (ADR 0004, #5).
- Changing the embedding model means adding or rebuilding vector columns and indexes, done only by the indexing stage, as the plan requires.
- Vector index tuning (HNSW or IVFFlat parameters) becomes our responsibility. Recall and latency are to be measured in F3 against the golden set, and those numbers decide the index parameters.
- If the graph needs traversals that recursive SQL cannot serve with acceptable latency, we revisit this for the graph only (see Neo4j below). If vector search does not meet the F3 gate after tuning, we revisit this for vectors only.

## Alternatives

- **Weaviate.** A dedicated vector database with hybrid search built in. It is not chosen because it would keep metadata, licenses and the queue in a second system, splitting constraints and transactions across two stores, and because it repeats the Astros stack instead of showing a different one.
- **Neo4j for the graph.** Better at deep traversals and graph algorithms. The plan defers it: the graph starts as Postgres tables and moves only if measured queries require it.
- **A separate search engine (Elasticsearch or OpenSearch).** Strong lexical search, but it adds another service to keep in sync with the source of truth, for a collection whose size does not yet justify it.
