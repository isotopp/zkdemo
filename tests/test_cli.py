"""Tests for the command-line interface."""

import pytest

from zkdemo.cli import main


def test_help_lists_all_commands(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exception:
        main(["--help"])

    assert exception.value.code == 0
    output = capsys.readouterr().out
    assert "lslr" in output
    assert "lr" in output
    assert "cat" in output
    assert "server" in output
    assert "client" in output


def test_unimplemented_command_fails_clearly(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exception:
        main(
            [
                "server",
                "--cluster",
                "bpdb",
                "--name",
                "bpdb17",
                "--endpoint",
                "10.1.1.1:3306",
            ]
        )

    assert exception.value.code == 2
    assert "server is not implemented yet" in capsys.readouterr().err
