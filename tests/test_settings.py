"""API settings (AGENTS.md, principle 8): documented in .env.example and validated."""

import tomllib
from pathlib import Path

import pytest
from pydantic_settings import BaseSettings

from app.main import API_VERSION
from app.settings import ServerSettings, Settings

ROOT = Path(__file__).resolve().parents[1]


def env_names(settings_class: type[BaseSettings]) -> set[str]:
    prefix = str(settings_class.model_config.get("env_prefix", ""))
    return {f"{prefix}{name}".upper() for name in settings_class.model_fields}


def documented(env_example: Path) -> set[str]:
    return {
        line.split("=", 1)[0]
        for line in env_example.read_text(encoding="utf-8").splitlines()
        if line and not line.startswith("#")
    }


def test_every_api_setting_is_in_env_example() -> None:
    expected = env_names(Settings) | env_names(ServerSettings)

    assert expected - documented(ROOT / ".env.example") == set()


def test_server_port_must_be_valid(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORDEL_API_HOST", "127.0.0.1")
    monkeypatch.setenv("CORDEL_API_PORT", "70000")

    with pytest.raises(ValueError, match="port"):
        ServerSettings()


def test_api_version_matches_project_version() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]

    assert project["version"] == API_VERSION
