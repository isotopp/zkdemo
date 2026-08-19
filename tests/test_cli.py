"""Tests for the command-line interface."""

import pytest

from zkdemo.cli import main


@pytest.mark.parametrize(
    ("command", "expected"),
    [
        ("client", "ZooKeeper client stub"),
        ("server", "ZooKeeper server stub"),
    ],
)
def test_command_stub(
    command: str, expected: str, capsys: pytest.CaptureFixture[str]
) -> None:
    main([command])

    assert capsys.readouterr().out.strip() == expected
