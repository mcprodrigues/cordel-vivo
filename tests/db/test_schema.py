"""Rules enforced by the V001 schema, checked against a real Postgres.

Run with the database up and migrated (see AGENTS.md):
    CORDEL_DB_URL=postgresql://user:password@127.0.0.1:55450/cordel \
        uv run pytest -m db --force-enable-socket --allow-hosts=127.0.0.1

Each test runs inside a transaction that is rolled back, so the database is left as it was.
"""

import os
import re
from collections.abc import Iterator

import psycopg
import pytest
from psycopg import errors

pytestmark = pytest.mark.db

SHA_A = "a" * 64
SHA_B = "b" * 64


@pytest.fixture
def db() -> Iterator[psycopg.Connection[tuple[object, ...]]]:
    url = os.environ.get("CORDEL_DB_URL")
    if not url:
        pytest.fail("CORDEL_DB_URL is not set; database tests need a migrated Postgres")
    with psycopg.connect(url, connect_timeout=5) as conn:
        conn.execute("SET statement_timeout = '5s'")
        try:
            yield conn
        finally:
            conn.rollback()


def new_item(conn: psycopg.Connection[tuple[object, ...]], **columns: str | None) -> object:
    values = {"origin": "test origin", **columns}
    names = ", ".join(values)
    marks = ", ".join(["%s"] * len(values))
    row = conn.execute(
        f"INSERT INTO collection_item ({names}) VALUES ({marks}) RETURNING id",
        list(values.values()),
    ).fetchone()
    assert row is not None
    return row[0]


def new_booklet(conn: psycopg.Connection[tuple[object, ...]], sha256: str = SHA_A) -> object:
    item_id = new_item(conn)
    row = conn.execute(
        "INSERT INTO booklet (collection_item_id, sha256) VALUES (%s, %s) RETURNING id",
        [item_id, sha256],
    ).fetchone()
    assert row is not None
    return row[0]


def expect_violation(
    conn: psycopg.Connection[tuple[object, ...]],
    error: type[psycopg.Error],
    constraint: str,
    sql: str,
    params: list[object],
) -> None:
    with pytest.raises(error) as raised, conn.transaction():
        conn.execute(sql, params)
    assert raised.value.diag.constraint_name == constraint


def test_vector_and_unaccent_extensions_are_installed(
    db: psycopg.Connection[tuple[object, ...]],
) -> None:
    rows = db.execute("SELECT extname FROM pg_extension").fetchall()
    assert {"vector", "unaccent"} <= {row[0] for row in rows}


def test_license_vocabulary_is_empty_until_p1_is_resolved(
    db: psycopg.Connection[tuple[object, ...]],
) -> None:
    row = db.execute("SELECT count(*) FROM license").fetchone()
    assert row == (0,)


def test_duplicate_sha256_is_rejected(db: psycopg.Connection[tuple[object, ...]]) -> None:
    new_booklet(db, SHA_A)
    item_id = new_item(db)
    expect_violation(
        db,
        errors.UniqueViolation,
        "uq_booklet_sha256",
        "INSERT INTO booklet (collection_item_id, sha256) VALUES (%s, %s)",
        [item_id, SHA_A],
    )


def test_sha256_must_be_lowercase_hex(db: psycopg.Connection[tuple[object, ...]]) -> None:
    item_id = new_item(db)
    expect_violation(
        db,
        errors.CheckViolation,
        "ck_booklet_sha256_hex",
        "INSERT INTO booklet (collection_item_id, sha256) VALUES (%s, %s)",
        [item_id, "A" * 64],
    )


def test_booklet_requires_collection_item(db: psycopg.Connection[tuple[object, ...]]) -> None:
    expect_violation(
        db,
        errors.ForeignKeyViolation,
        "fk_booklet_collection_item_id",
        "INSERT INTO booklet (collection_item_id, sha256) VALUES (gen_random_uuid(), %s)",
        [SHA_A],
    )


def test_collection_item_may_have_several_booklets(
    db: psycopg.Connection[tuple[object, ...]],
) -> None:
    item_id = new_item(db)
    for sha in (SHA_A, SHA_B):
        db.execute(
            "INSERT INTO booklet (collection_item_id, sha256) VALUES (%s, %s)", [item_id, sha]
        )
    row = db.execute("SELECT count(*) FROM booklet WHERE collection_item_id = %s", [item_id])
    assert row.fetchone() == (2,)


def test_cover_license_is_independent_of_booklet_license(
    db: psycopg.Connection[tuple[object, ...]],
) -> None:
    # License codes here are test fixtures only; the real vocabulary is open item P-1.
    db.execute(
        "INSERT INTO license (code, description, allows_image) VALUES "
        "('test_text', 'test', true), ('test_cover', 'test', false)"
    )
    item_id = new_item(db, booklet_license="test_text", cover_license="test_cover")
    row = db.execute(
        "SELECT booklet_license, cover_license FROM collection_item WHERE id = %s", [item_id]
    ).fetchone()
    assert row == ("test_text", "test_cover")
    other = new_item(db, booklet_license="test_text")
    row = db.execute("SELECT cover_license FROM collection_item WHERE id = %s", [other]).fetchone()
    assert row == (None,)


def test_unknown_license_is_rejected(db: psycopg.Connection[tuple[object, ...]]) -> None:
    expect_violation(
        db,
        errors.ForeignKeyViolation,
        "fk_collection_item_cover_license",
        "INSERT INTO collection_item (origin, cover_license) VALUES ('x', %s)",
        ["not_a_license"],
    )


@pytest.mark.parametrize("kind", ["declared", "attributed"])
def test_authorship_requires_its_source(
    db: psycopg.Connection[tuple[object, ...]], kind: str
) -> None:
    expect_violation(
        db,
        errors.CheckViolation,
        f"ck_collection_item_{kind}_authorship_has_source",
        f"INSERT INTO collection_item (origin, {kind}_authorship) VALUES ('x', %s)",
        ["Leandro Gomes de Barros"],
    )


def test_origin_url_must_be_http(db: psycopg.Connection[tuple[object, ...]]) -> None:
    expect_violation(
        db,
        errors.CheckViolation,
        "ck_collection_item_origin_url_is_http",
        "INSERT INTO collection_item (origin, origin_url) VALUES ('x', %s)",
        ["javascript:alert(1)"],
    )


def test_page_number_is_unique_per_booklet(db: psycopg.Connection[tuple[object, ...]]) -> None:
    booklet_id = new_booklet(db)
    db.execute("INSERT INTO page (booklet_id, number) VALUES (%s, 1)", [booklet_id])
    expect_violation(
        db,
        errors.UniqueViolation,
        "uq_page_booklet_id_number",
        "INSERT INTO page (booklet_id, number) VALUES (%s, 1)",
        [booklet_id],
    )


def test_page_kind_is_cover_or_body(db: psycopg.Connection[tuple[object, ...]]) -> None:
    booklet_id = new_booklet(db)
    expect_violation(
        db,
        errors.CheckViolation,
        "ck_page_kind",
        "INSERT INTO page (booklet_id, number, kind) VALUES (%s, 1, 'miolo')",
        [booklet_id],
    )


def test_pages_are_removed_with_their_booklet(db: psycopg.Connection[tuple[object, ...]]) -> None:
    booklet_id = new_booklet(db)
    db.execute("INSERT INTO page (booklet_id, number) VALUES (%s, 1), (%s, 2)", [booklet_id] * 2)
    db.execute("DELETE FROM booklet WHERE id = %s", [booklet_id])
    row = db.execute("SELECT count(*) FROM page WHERE booklet_id = %s", [booklet_id]).fetchone()
    assert row == (0,)


def test_invalid_stage_is_rejected(db: psycopg.Connection[tuple[object, ...]]) -> None:
    booklet_id = new_booklet(db)
    expect_violation(
        db,
        errors.CheckViolation,
        "ck_job_stage",
        "INSERT INTO job (booklet_id, stage) VALUES (%s, 'ocr')",
        [booklet_id],
    )


def test_job_is_unique_per_booklet_and_stage(db: psycopg.Connection[tuple[object, ...]]) -> None:
    booklet_id = new_booklet(db)
    db.execute("INSERT INTO job (booklet_id, stage) VALUES (%s, 'reading')", [booklet_id])
    expect_violation(
        db,
        errors.UniqueViolation,
        "uq_job_booklet_id_stage",
        "INSERT INTO job (booklet_id, stage) VALUES (%s, 'reading')",
        [booklet_id],
    )


def test_new_job_starts_pending_with_no_attempts(
    db: psycopg.Connection[tuple[object, ...]],
) -> None:
    booklet_id = new_booklet(db)
    row = db.execute(
        "INSERT INTO job (booklet_id, stage) VALUES (%s, 'reading') "
        "RETURNING status, attempts, locked_at",
        [booklet_id],
    ).fetchone()
    assert row == ("pending", 0, None)


def test_job_lock_records_both_time_and_owner(db: psycopg.Connection[tuple[object, ...]]) -> None:
    booklet_id = new_booklet(db)
    expect_violation(
        db,
        errors.CheckViolation,
        "ck_job_lock_is_complete",
        "INSERT INTO job (booklet_id, stage, locked_at) VALUES (%s, 'reading', now())",
        [booklet_id],
    )


def test_all_constraints_and_indexes_follow_naming_convention(
    db: psycopg.Connection[tuple[object, ...]],
) -> None:
    # Catches auto-generated names (e.g. booklet_pkey) that the static check could miss.
    # Flyway's own history table is not ours and is excluded.
    rows = db.execute(
        """
        SELECT conname FROM pg_constraint c
        JOIN pg_namespace n ON n.oid = c.connamespace
        WHERE n.nspname = 'public' AND c.conrelid <> 'flyway_schema_history'::regclass
        UNION ALL
        SELECT indexname FROM pg_indexes
        WHERE schemaname = 'public' AND tablename <> 'flyway_schema_history'
        """
    ).fetchall()
    names = {str(row[0]) for row in rows}
    assert names
    assert sorted(n for n in names if not re.match(r"^(pk|fk|uq|ck|ix)_", n)) == []
