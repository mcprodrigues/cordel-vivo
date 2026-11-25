"""The cordel_contracts package is installed and typed."""

from importlib import resources


def test_contracts_package_ships_type_marker() -> None:
    assert resources.files("cordel_contracts").joinpath("py.typed").is_file()
