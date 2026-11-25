"""The cordel_poetics package is installed and typed."""

from importlib import resources


def test_poetics_package_ships_type_marker() -> None:
    assert resources.files("cordel_poetics").joinpath("py.typed").is_file()
