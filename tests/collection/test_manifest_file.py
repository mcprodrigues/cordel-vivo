"""The real collection/manifest.csv is valid, and collection files never enter git."""

import subprocess
from pathlib import Path

from app.collection.manifest import MANIFEST_COLUMNS, parse_manifest

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "collection" / "manifest.csv"
DB_MIGRATIONS = ROOT / "db" / "migrations"


def test_collection_manifest_is_valid() -> None:
    parse_manifest(MANIFEST.read_text(encoding="utf-8"))


def test_manifest_columns_mirror_collection_item_table() -> None:
    sql = (DB_MIGRATIONS / "V001__initial_schema.sql").read_text(encoding="utf-8")
    table = sql.split("CREATE TABLE collection_item (", 1)[1].split(");", 1)[0]
    for column in MANIFEST_COLUMNS:
        assert f"\n    {column} " in table, f"{column} is not a column of collection_item"


def test_collection_files_are_ignored_by_git() -> None:
    for path in ("collection/files/booklet.pdf", "collection/files/sub/cover.png"):
        result = subprocess.run(
            ["git", "check-ignore", "--quiet", "--no-index", path],
            cwd=ROOT,
            check=False,
        )
        assert result.returncode == 0, f"{path} would be committed"
