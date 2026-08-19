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


def test_missing_required_option_fails_clearly(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exception:
        main(
            [
                "client",
                "--cluster",
                "bpdb",
            ]
        )

    assert exception.value.code == 2
    assert "required: --file" in capsys.readouterr().err
