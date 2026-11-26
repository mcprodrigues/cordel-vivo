"""Layer rules inside the app package (AGENTS.md, "Repository layout").

Rules are checked on the import statements of each layer, so they also hold for layers
and modules added later. Folders that do not exist yet have no imports and pass.
"""

import ast
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app"
STDLIB = frozenset(sys.stdlib_module_names)

# Standard library modules that reach files, processes or the network.
IO_MODULES = frozenset(
    {"os", "pathlib", "shutil", "socket", "subprocess", "urllib", "http", "ssl", "sqlite3"}
)


def imported_names(path: Path) -> Iterator[str]:
    """Every module a file imports, with `from a import b` reported as both a and a.b."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            yield from (alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            yield node.module
            yield from (f"{node.module}.{alias.name}" for alias in node.names)


def display(path: Path) -> str:
    return str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)


def imports_of(layer: Path) -> dict[str, set[str]]:
    """Map each module imported anywhere in the layer to the files that import it."""
    found: dict[str, set[str]] = {}
    for path in sorted(layer.rglob("*.py")):
        for name in imported_names(path):
            found.setdefault(name, set()).add(display(path))
    return found


def matches(name: str, prefix: str) -> bool:
    return name == prefix or name.startswith(prefix + ".")


def offending(layer: Path, forbidden: tuple[str, ...], allowed: tuple[str, ...] = ()) -> list[str]:
    """Imports of the layer under a forbidden prefix, except the allowed ones."""
    return sorted(
        f"{name} in {', '.join(sorted(files))}"
        for name, files in imports_of(layer).items()
        if any(matches(name, prefix) for prefix in forbidden)
        and not any(matches(name, prefix) for prefix in allowed)
    )


def outside_allowlist(layer: Path, allowed: frozenset[str], own: tuple[str, ...]) -> list[str]:
    return sorted(
        f"{name} in {', '.join(sorted(files))}"
        for name, files in imports_of(layer).items()
        if name.split(".")[0] not in allowed and not any(matches(name, p) for p in own)
    )


def opens_files(layer: Path) -> list[str]:
    return sorted(
        display(path)
        for path in layer.rglob("*.py")
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "open"
    )


def test_poetics_imports_only_standard_library() -> None:
    assert outside_allowlist(APP / "poetics", STDLIB, own=("app.poetics",)) == []


def test_collection_imports_only_pydantic_standard_library_and_errors() -> None:
    allowed = STDLIB | {"pydantic"}
    own = ("app.collection", "app.errors")
    assert outside_allowlist(APP / "collection", allowed, own) == []


@pytest.mark.parametrize("layer", ["poetics", "collection"])
def test_pure_layers_do_no_io(layer: str) -> None:
    assert offending(APP / layer, tuple(IO_MODULES)) == []
    assert opens_files(APP / layer) == []


def test_routers_never_reach_providers_or_workers() -> None:
    assert offending(APP / "routers", ("app.providers", "app.workers")) == []


def test_services_depend_only_on_provider_interfaces() -> None:
    # `from app.providers import interfaces` also reports the bare package name.
    allowed = ("app.providers.interfaces",)
    concrete = offending(APP / "services", ("app.providers",), allowed)
    assert [entry for entry in concrete if not entry.startswith("app.providers in ")] == []


def test_workers_never_import_routers() -> None:
    assert offending(APP / "workers", ("app.routers",)) == []


def test_app_uses_only_absolute_imports() -> None:
    relative = sorted(
        str(path.relative_to(ROOT))
        for path in APP.rglob("*.py")
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
        if isinstance(node, ast.ImportFrom) and node.level > 0
    )
    assert relative == []


def test_rule_checker_detects_forbidden_import(tmp_path: Path) -> None:
    layer = tmp_path / "routers"
    layer.mkdir()
    (layer / "mod.py").write_text("from app import providers\n", encoding="utf-8")

    assert offending(layer, ("app.providers",)) != []


def test_rule_checker_detects_io_in_pure_layer(tmp_path: Path) -> None:
    (tmp_path / "mod.py").write_text("import pathlib\nopen('x')\n", encoding="utf-8")

    assert offending(tmp_path, tuple(IO_MODULES)) != []
    assert opens_files(tmp_path) != []
