"""The test suite never reaches the network (AGENTS.md, "Testing and evaluation")."""

import socket

import pytest
from pytest_socket import SocketBlockedError


@pytest.mark.filterwarnings("ignore:A test tried to use socket.socket")
def test_external_network_is_blocked() -> None:
    # Creating the socket is enough: pytest-socket refuses it before any DNS lookup
    # or connection, so this test itself never touches the network.
    with pytest.raises(SocketBlockedError):
        socket.socket(socket.AF_INET, socket.SOCK_STREAM)


def test_live_tests_are_not_collected(pytestconfig: pytest.Config) -> None:
    assert "*_live.py" in pytestconfig.getoption("ignore_glob")
