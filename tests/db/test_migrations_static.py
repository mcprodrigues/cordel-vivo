"""Static checks of db/migrations: file names and object names. No database needed."""

import re
from pathlib import Path

MIGRATIONS = Path(__file__).resolve().parents[2] / "db" / "migrations"
FILES = sorted(MIGRATIONS.glob("*.sql"))
NAME_PREFIX = re.compile(r"^(pk|fk|uq|ck|ix)_[a-z0-9_]+$")


def test_migration_file_names_follow_flyway_convention() -> None:
    assert FILES, "no migrations found"
    for path in FILES:
        assert re.fullmatch(r"V\d{3}__[a-z0-9_]+\.sql", path.name), path.name


def test_migration_versions_are_sequential_from_one() -> None:
    versions = [int(path.name[1:4]) for path in FILES]
    assert versions == list(range(1, len(versions) + 1))


def test_every_constraint_and_index_is_named_by_convention() -> None:
    for path in FILES:
        sql = path.read_text(encoding="utf-8")
        names = re.findall(r"\bCONSTRAINT\s+(\w+)", sql) + re.findall(
            r"\bCREATE\s+(?:UNIQUE\s+)?INDEX\s+(?:CONCURRENTLY\s+)?(?:IF NOT EXISTS\s+)?(\w+)",
            sql,
        )
        assert names, f"{path.name} declares no named objects"
        bad = [name for name in names if not NAME_PREFIX.match(name)]
        assert bad == [], f"{path.name}: {bad}"


def test_tables_do_not_declare_unnamed_constraints() -> None:
    # Inline "PRIMARY KEY", "UNIQUE" or "REFERENCES" in a column would get an
    # auto-generated name; every constraint must be declared with CONSTRAINT <name>.
    for path in FILES:
        for line in path.read_text(encoding="utf-8").splitlines():
            code = line.split("--", 1)[0]
            if re.search(r"\b(PRIMARY KEY|UNIQUE|REFERENCES|CHECK)\b", code):
                assert re.search(r"\bCONSTRAINT\b|^\s+(FOREIGN KEY|CHECK)\b", code), (
                    f"{path.name}: unnamed constraint in {line.strip()!r}"
                )
