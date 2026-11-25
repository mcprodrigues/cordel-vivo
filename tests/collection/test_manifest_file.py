"""The real collection/manifest.csv is valid, and collection files never enter git."""

import re
import subprocess
from pathlib import Path

from app.collection.manifest import MANIFEST_COLUMNS, parse_manifest

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "collection" / "manifest.csv"
DB_MIGRATIONS = ROOT / "db" / "migrations"


def test_collection_manifest_is_valid() -> None:
    parse_manifest(MANIFEST.read_text(encoding="utf-8"))


def collection_item_columns() -> set[str]:
    """Columns of collection_item after every migration: created in V001, added later."""
    columns: set[str] = set()
    for path in sorted(DB_MIGRATIONS.glob("V*.sql")):
        sql = path.read_text(encoding="utf-8")
        if "CREATE TABLE collection_item (" in sql:
            table = sql.split("CREATE TABLE collection_item (", 1)[1].split(");", 1)[0]
            columns |= set(re.findall(r"^    ([a-z_]+) ", table, flags=re.MULTILINE))
        for statement in re.findall(r"ALTER TABLE collection_item\b(.*?);", sql, flags=re.DOTALL):
            columns |= set(re.findall(r"ADD COLUMN (?:IF NOT EXISTS )?([a-z_]+)", statement))
    return columns


def test_manifest_columns_mirror_collection_item_table() -> None:
    missing = set(MANIFEST_COLUMNS) - collection_item_columns()

    assert missing == set(), f"not columns of collection_item: {sorted(missing)}"


def test_mirror_check_sees_columns_added_by_later_migrations() -> None:
    assert {"title", "engraver", "engraver_source"} <= collection_item_columns()


def test_collection_files_are_ignored_by_git() -> None:
    for path in ("collection/files/booklet.pdf", "collection/files/sub/cover.png"):
        result = subprocess.run(
            ["git", "check-ignore", "--quiet", "--no-index", path],
            cwd=ROOT,
            check=False,
        )
        assert result.returncode == 0, f"{path} would be committed"
