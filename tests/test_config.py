"""Tests for dotenv-backed command defaults."""

from pathlib import Path

import pytest

from zkdemo.cli import build_parser


def test_first_dotenv_file_and_precedence_rules(monkeypatch, tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("ZKTEST_CLUSTER", raising=False)
    monkeypatch.delenv("ZKTEST_DELAY", raising=False)
    monkeypatch.delenv("ZKTEST_FILE", raising=False)
    (tmp_path / ".env").write_text(
        "ZKTEST_CLUSTER=file-cluster\nZKTEST_DELAY=1.25\nZKTEST_FILE=file.endpoints\n",
        encoding="utf-8",
    )
    (home / ".zktest.ini").write_text(
        "ZKTEST_CLUSTER=home-cluster\nZKTEST_DELAY=2.5\n",
        encoding="utf-8",
    )

    parser = build_parser()
    args = parser.parse_args(["client"])
    assert args.cluster == "file-cluster"
    assert args.delay == 1.25
    assert args.output_file == "file.endpoints"

    monkeypatch.setenv("ZKTEST_CLUSTER", "environment-cluster")
    args = build_parser().parse_args(["client"])
    assert args.cluster == "environment-cluster"

    args = build_parser().parse_args(
        ["client", "--cluster", "cli-cluster", "--delay", "0.5"]
    )
    assert args.cluster == "cli-cluster"
    assert args.delay == 0.5


def test_invalid_dotenv_setting_names_file_and_setting(
    monkeypatch, tmp_path: Path, capsys
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text("ZKTEST_DELAY=nan\n", encoding="utf-8")

    with pytest.raises(SystemExit) as exception:
        build_parser()

    captured = capsys.readouterr()
    assert exception.value.code == 2
    assert str(tmp_path / ".env") in captured.err
    assert "ZKTEST_DELAY" in captured.err


def test_invalid_host_configuration_is_rejected(
    monkeypatch, tmp_path: Path, capsys
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text("ZKTEST_HOSTS=zk1.example:0\n", encoding="utf-8")

    with pytest.raises(SystemExit) as exception:
        build_parser()

    captured = capsys.readouterr()
    assert exception.value.code == 2
    assert "ZKTEST_HOSTS" in captured.err
    assert "port out of range" in captured.err
