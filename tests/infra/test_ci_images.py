"""CI uses exactly the images pinned in infra/docker-compose.yml."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PINNED = re.compile(r"[a-z0-9./_-]+:[A-Za-z0-9._-]+@sha256:[0-9a-f]{64}")


def images_in(path: Path) -> set[str]:
    return set(PINNED.findall(path.read_text(encoding="utf-8")))


def test_ci_images_match_compose_images() -> None:
    ci = images_in(ROOT / ".github" / "workflows" / "ci.yml")
    compose = images_in(ROOT / "infra" / "docker-compose.yml")
    assert ci, "CI declares no pinned images"
    assert ci <= compose, f"images only in CI: {sorted(ci - compose)}"
