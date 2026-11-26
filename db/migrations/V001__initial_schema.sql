-- V001: initial schema for the collection, booklets, pages and the ingestion queue.
--
-- Naming convention: pk_<table>, fk_<table>_<column>, uq_<table>_<columns>,
-- ck_<table>_<rule>, ix_<table>_<columns or purpose>.
-- Never edit this file after it has been applied: add a new migration instead.

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS unaccent;

-- License vocabulary. Open item P-1: the values, and which of them allow storing or
-- indexing images, are not defined yet. The table is created empty on purpose and is
-- filled by a later migration once P-1 is resolved.
CREATE TABLE license (
    code         text    NOT NULL,
    description  text    NOT NULL,
    allows_image boolean NOT NULL,
    CONSTRAINT pk_license PRIMARY KEY (code),
    CONSTRAINT ck_license_code_format CHECK (code ~ '^[a-z0-9_]+$')
);

COMMENT ON TABLE license IS 'License vocabulary, empty until open item P-1 is resolved.';

-- One row of the collection manifest: where the item comes from, who is declared and
-- attributed as author (each with its source), and the licenses of the booklet text
-- and of the cover, which are independent. A null license means "not confirmed".
CREATE TABLE collection_item (
    id                           uuid        NOT NULL DEFAULT gen_random_uuid(),
    origin                       text        NOT NULL,
    origin_url                   text,
    declared_authorship          text,
    declared_authorship_source   text,
    attributed_authorship        text,
    attributed_authorship_source text,
    booklet_license              text,
    cover_license                text,
    created_at                   timestamptz NOT NULL DEFAULT now(),
    updated_at                   timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT pk_collection_item PRIMARY KEY (id),
    CONSTRAINT fk_collection_item_booklet_license
        FOREIGN KEY (booklet_license) REFERENCES license (code) ON DELETE RESTRICT,
    CONSTRAINT fk_collection_item_cover_license
        FOREIGN KEY (cover_license) REFERENCES license (code) ON DELETE RESTRICT,
    CONSTRAINT ck_collection_item_origin_not_blank CHECK (btrim(origin) <> ''),
    CONSTRAINT ck_collection_item_origin_url_is_http CHECK (origin_url ~ '^https?://'),
    CONSTRAINT ck_collection_item_declared_authorship_has_source
        CHECK (declared_authorship IS NULL OR declared_authorship_source IS NOT NULL),
    CONSTRAINT ck_collection_item_attributed_authorship_has_source
        CHECK (attributed_authorship IS NULL OR attributed_authorship_source IS NOT NULL)
);

CREATE INDEX ix_collection_item_booklet_license ON collection_item (booklet_license);
CREATE INDEX ix_collection_item_cover_license ON collection_item (cover_license);

-- A digitized file of a collection item. The SHA-256 of the file is the idempotency
-- key of the ingestion (AGENTS.md, principle 6). One item may have several files.
CREATE TABLE booklet (
    id                 uuid        NOT NULL DEFAULT gen_random_uuid(),
    collection_item_id uuid        NOT NULL,
    sha256             char(64)    NOT NULL,
    created_at         timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT pk_booklet PRIMARY KEY (id),
    CONSTRAINT fk_booklet_collection_item_id
        FOREIGN KEY (collection_item_id) REFERENCES collection_item (id) ON DELETE RESTRICT,
    CONSTRAINT uq_booklet_sha256 UNIQUE (sha256),
    CONSTRAINT ck_booklet_sha256_hex CHECK (sha256 ~ '^[0-9a-f]{64}$')
);

CREATE INDEX ix_booklet_collection_item_id ON booklet (collection_item_id);

-- A page of a booklet. object_key is null when the image is not stored, for example
-- because its license is not confirmed. dpi has no minimum yet: open item P-4.
CREATE TABLE page (
    id         uuid        NOT NULL DEFAULT gen_random_uuid(),
    booklet_id uuid        NOT NULL,
    number     integer     NOT NULL,
    kind       text,
    object_key text,
    width_px   integer,
    height_px  integer,
    dpi        integer,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT pk_page PRIMARY KEY (id),
    CONSTRAINT fk_page_booklet_id
        FOREIGN KEY (booklet_id) REFERENCES booklet (id) ON DELETE CASCADE,
    CONSTRAINT uq_page_booklet_id_number UNIQUE (booklet_id, number),
    CONSTRAINT ck_page_number_positive CHECK (number > 0),
    CONSTRAINT ck_page_kind CHECK (kind IN ('cover', 'body')),
    CONSTRAINT ck_page_width_px_positive CHECK (width_px > 0),
    CONSTRAINT ck_page_height_px_positive CHECK (height_px > 0),
    CONSTRAINT ck_page_dpi_positive CHECK (dpi > 0)
);

-- Ingestion queue, claimed with SELECT ... FOR UPDATE SKIP LOCKED (ADR 0002).
-- One job per booklet and stage makes enqueueing idempotent.
-- The status values are provisional: open item P-2. Retry limits: open item P-3.
CREATE TABLE job (
    id           bigint      GENERATED ALWAYS AS IDENTITY,
    booklet_id   uuid        NOT NULL,
    stage        text        NOT NULL,
    status       text        NOT NULL DEFAULT 'pending',
    attempts     integer     NOT NULL DEFAULT 0,
    available_at timestamptz NOT NULL DEFAULT now(),
    locked_at    timestamptz,
    locked_by    text,
    error        text,
    created_at   timestamptz NOT NULL DEFAULT now(),
    updated_at   timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT pk_job PRIMARY KEY (id),
    CONSTRAINT fk_job_booklet_id
        FOREIGN KEY (booklet_id) REFERENCES booklet (id) ON DELETE CASCADE,
    CONSTRAINT uq_job_booklet_id_stage UNIQUE (booklet_id, stage),
    CONSTRAINT ck_job_stage CHECK (stage IN ('reading', 'poetics', 'enrichment', 'indexing')),
    CONSTRAINT ck_job_status CHECK (status IN ('pending', 'running', 'done', 'failed')),
    CONSTRAINT ck_job_attempts_not_negative CHECK (attempts >= 0),
    CONSTRAINT ck_job_lock_is_complete CHECK ((locked_at IS NULL) = (locked_by IS NULL))
);

COMMENT ON COLUMN job.status IS 'Provisional values, open item P-2.';

CREATE INDEX ix_job_queue ON job (stage, available_at) WHERE status = 'pending';
