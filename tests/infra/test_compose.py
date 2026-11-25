"""Static checks of infra/docker-compose.yml (AGENTS.md, principles 8 and 12).

They parse the file only: no Docker daemon and no network.
"""

import re
from pathlib import Path
from typing import Any

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
COMPOSE_FILE = ROOT / "infra" / "docker-compose.yml"
ENV_EXAMPLE = ROOT / ".env.example"
# "$${VAR}" is a compose escape expanded inside the container, not an env reference.
ENV_REFERENCE = re.compile(r"(?<!\$)\$\{([A-Z0-9_]+)(?::?[-?][^}]*)?\}")


def load_compose() -> dict[str, Any]:
    data: dict[str, Any] = yaml.safe_load(COMPOSE_FILE.read_text(encoding="utf-8"))
    return data


COMPOSE = load_compose()
SERVICES: dict[str, dict[str, Any]] = COMPOSE["services"]


def test_compose_project_is_named() -> None:
    assert COMPOSE["name"] == "cordel-vivo"


@pytest.mark.parametrize("service", sorted(SERVICES))
def test_every_image_is_pinned_by_tag_and_digest(service: str) -> None:
    image = SERVICES[service]["image"]
    assert re.fullmatch(r"[a-z0-9./_-]+:[A-Za-z0-9._-]+@sha256:[0-9a-f]{64}", image), image
    assert ":latest@" not in image


@pytest.mark.parametrize("service", sorted(SERVICES))
def test_every_service_has_healthcheck(service: str) -> None:
    healthcheck = SERVICES[service].get("healthcheck", {})
    assert healthcheck.get("test")
    assert not healthcheck.get("disable", False)


@pytest.mark.parametrize("service", sorted(SERVICES))
def test_volumes_are_named(service: str) -> None:
    declared = set(COMPOSE.get("volumes") or {})
    for mount in SERVICES[service].get("volumes", []):
        source = mount.split(":")[0]
        assert source in declared, f"{service} mounts {source!r}, which is not a named volume"


@pytest.mark.parametrize("service", sorted(SERVICES))
def test_no_hardcoded_host_ports(service: str) -> None:
    for mapping in SERVICES[service].get("ports", []):
        # host_ip:host_port:container_port, where host_port must come from the env
        parts = str(mapping).split(":", 1)
        assert len(parts) == 2, f"{service}: {mapping!r} has no explicit host binding"
        host_ip, rest = parts
        assert host_ip == "127.0.0.1", f"{service}: {mapping!r} is not bound to localhost"
        assert ENV_REFERENCE.match(rest), f"{service}: host port in {mapping!r} is hardcoded"


def test_every_compose_variable_is_in_env_example() -> None:
    used = set(ENV_REFERENCE.findall(COMPOSE_FILE.read_text(encoding="utf-8")))
    documented = {
        line.split("=", 1)[0]
        for line in ENV_EXAMPLE.read_text(encoding="utf-8").splitlines()
        if line and not line.startswith("#")
    }
    assert used - documented == set()


def test_credentials_come_only_from_environment() -> None:
    for name, service in SERVICES.items():
        for key, value in (service.get("environment") or {}).items():
            if re.search(r"PASSWORD|SECRET|ACCESS_KEY", key):
                assert ENV_REFERENCE.fullmatch(str(value)), f"{name}.{key} is not from the env"
