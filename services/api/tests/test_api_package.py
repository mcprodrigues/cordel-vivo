"""The cordel_api package is installed and typed."""

from importlib import resources


def test_api_package_ships_type_marker() -> None:
    assert resources.files("cordel_api").joinpath("py.typed").is_file()
