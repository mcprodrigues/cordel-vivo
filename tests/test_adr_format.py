"""ADRs follow the format in AGENTS.md: Context, Decision, Consequences, Alternatives."""

import re
from pathlib import Path

import pytest

ADR_DIR = Path(__file__).resolve().parent.parent / "docs" / "adr"
SECTIONS = ["## Context", "## Decision", "## Consequences", "## Alternatives"]
ADRS = sorted(ADR_DIR.glob("[0-9][0-9][0-9][0-9]-*.md"))


def test_adr_numbers_are_sequential_from_zero() -> None:
    numbers = [int(path.name[:4]) for path in ADRS]
    assert numbers == list(range(len(numbers)))


@pytest.mark.parametrize("adr", ADRS, ids=lambda p: p.stem)
def test_adr_has_required_sections_in_order(adr: Path) -> None:
    text = adr.read_text(encoding="utf-8")
    positions = [text.find(section) for section in SECTIONS]
    assert -1 not in positions
    assert positions == sorted(positions)


@pytest.mark.parametrize("adr", [p for p in ADRS if p.name[:4] != "0000"], ids=lambda p: p.stem)
def test_adr_declares_status_and_date(adr: Path) -> None:
    text = adr.read_text(encoding="utf-8")
    assert re.search(r"^- \*\*Status:\*\* (proposed|accepted|superseded by ADR \d{4})$", text, re.M)
    assert re.search(r"^- \*\*Date:\*\* \d{4}-\d{2}-\d{2}$", text, re.M)
