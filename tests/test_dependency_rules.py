"""Dependency rules between workspace members (AGENTS.md, "Repository layout").

import-linter covers imports between our own packages; these tests cover what it
cannot express: allowlists of third-party imports and the rule that services never
import each other, including services added in the future.
"""

import ast
import sys
import tomllib
from collections.abc import Iterable
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PACKAGES = ROOT / "packages"
SERVICES = ROOT / "services"
STDLIB = frozenset(sys.stdlib_module_names)


def top_level_imports(source_dir: Path) -> dict[str, set[Path]]:
    """Map each imported top-level module to the files that import it."""
    found: dict[str, set[Path]] = {}
    for path in sorted(source_dir.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            names: Iterable[str] = ()
            if isinstance(node, ast.Import):
                names = (alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                names = (node.module,)
            for name in names:
                found.setdefault(name.split(".")[0], set()).add(path)
    return found


def violations(source_dir: Path, own: str, allowed: frozenset[str]) -> list[str]:
    """Imports in source_dir that are neither the package itself nor allowed."""
    return sorted(
        f"{module} in {', '.join(str(p.relative_to(ROOT)) for p in sorted(files))}"
        for module, files in top_level_imports(source_dir).items()
        if module != own and module not in allowed
    )


def declared_dependencies(member_dir: Path) -> list[str]:
    data = tomllib.loads((member_dir / "pyproject.toml").read_text(encoding="utf-8"))
    deps: list[str] = data["project"]["dependencies"]
    return deps


def service_modules() -> dict[Path, str]:
    return {
        service: next((service / "src").iterdir()).name
        for service in sorted(SERVICES.iterdir())
        if (service / "pyproject.toml").exists()
    }


def test_poetics_imports_only_standard_library() -> None:
    src = PACKAGES / "poetics" / "src"
    assert violations(src, "cordel_poetics", STDLIB) == []


def test_poetics_declares_no_dependencies() -> None:
    assert declared_dependencies(PACKAGES / "poetics") == []


def test_contracts_imports_only_pydantic_and_standard_library() -> None:
    src = PACKAGES / "contracts" / "src"
    assert violations(src, "cordel_contracts", STDLIB | {"pydantic"}) == []


def test_contracts_declares_only_pydantic() -> None:
    names = [
        dep.split("=")[0].split("[")[0] for dep in declared_dependencies(PACKAGES / "contracts")
    ]
    assert names == ["pydantic"]


@pytest.mark.parametrize("service", sorted(service_modules()), ids=lambda p: p.name)
def test_services_never_import_other_services(service: Path) -> None:
    own = service_modules()[service]
    other_services = set(service_modules().values()) - {own}
    imported = set(top_level_imports(service / "src"))
    assert imported & other_services == set()


def test_rule_checker_detects_forbidden_import(tmp_path: Path) -> None:
    module = tmp_path / "cordel_fake" / "mod.py"
    module.parent.mkdir()
    module.write_text("import os\nfrom cordel_api import app\n", encoding="utf-8")

    found = top_level_imports(tmp_path)

    assert set(found) == {"os", "cordel_api"}


def test_rule_checker_ignores_relative_imports(tmp_path: Path) -> None:
    module = tmp_path / "mod.py"
    module.write_text("from . import sibling\nfrom .sub import thing\n", encoding="utf-8")

    assert top_level_imports(tmp_path) == {}
