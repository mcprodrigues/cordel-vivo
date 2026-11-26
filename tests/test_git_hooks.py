"""The commit-msg hook enforces the commit format from AGENTS.md."""

import os
import subprocess
from pathlib import Path

import pytest

HOOKS = Path(__file__).resolve().parent.parent / ".githooks"


def run_commit_msg(message: str, tmp_path: Path) -> subprocess.CompletedProcess[str]:
    message_file = tmp_path / "COMMIT_EDITMSG"
    message_file.write_text(message, encoding="utf-8")
    return subprocess.run(
        [str(HOOKS / "commit-msg"), str(message_file)],
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.mark.parametrize(
    "message",
    [
        "feat(#3 - api): add authentication to all routes",
        "chore(#0 - repo): add repository base",
        "db(#5 - db): add initial schema\n\nLonger body explaining why.",
        "refact(#12 - poetics): split scansion into syllable rules",
        "Merge pull request #4 from mcprodrigues/chore/1-uv-workspace",
    ],
)
def test_commit_message_in_agreed_format_is_accepted(message: str, tmp_path: Path) -> None:
    assert run_commit_msg(message, tmp_path).returncode == 0


@pytest.mark.parametrize(
    "message",
    [
        "add authentication",
        "feat: add authentication",
        "feature(#3 - api): add authentication",
        "feat(3 - api): add authentication",
        "feat(#3-api): add authentication",
        "feat(#3 - API): add authentication",
        "feat(#3 - api):add authentication",
        "feat(#3 - api): ",
    ],
)
def test_commit_message_outside_format_is_rejected(message: str, tmp_path: Path) -> None:
    result = run_commit_msg(message, tmp_path)

    assert result.returncode == 1
    assert "expected 'type(#N - module): description'" in result.stderr


@pytest.mark.parametrize("hook", ["commit-msg", "pre-commit", "pre-push"])
def test_hooks_are_executable(hook: str) -> None:
    assert os.access(HOOKS / hook, os.X_OK)
