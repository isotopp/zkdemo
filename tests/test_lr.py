"""Integration tests for the ``lr`` command."""

import json
from uuid import uuid4

import pytest
from kazoo.client import KazooClient

from zkdemo.cli import main


def test_lr_json_lists_direct_children(
    zookeeper_hosts: str, monkeypatch, capsys
) -> None:
    client = KazooClient(hosts=zookeeper_hosts)
    client.start(timeout=10)
    path = f"/lr-{uuid4().hex}"
    try:
        client.create(path)
        client.create(f"{path}/bpdb17", b"10.1.1.1:3306")
        client.create(f"{path}/bpdb03", b"10.1.1.3:3306")
        monkeypatch.setenv("ZKTEST_HOSTS", zookeeper_hosts)

        main(["lr", path, "--format", "json"])

        listing = json.loads(capsys.readouterr().out)
        assert listing["path"] == path
        assert [child["name"] for child in listing["children"]] == [
            "bpdb03",
            "bpdb17",
        ]
        assert listing["children"][0]["data"] == "10.1.1.3:3306"
    finally:
        client.delete(path, recursive=True)
        client.stop()


def test_lr_text_renders_a_headered_table(
    zookeeper_hosts: str, monkeypatch, capsys
) -> None:
    client = KazooClient(hosts=zookeeper_hosts)
    client.start(timeout=10)
    path = f"/lr-{uuid4().hex}"
    try:
        client.create(path)
        client.create(f"{path}/bpdb17", b"10.1.1.1:3306")
        monkeypatch.setenv("ZKTEST_HOSTS", zookeeper_hosts)

        main(["lr", path, "--format", "text"])

        output = capsys.readouterr().out
        assert "Name" in output
        assert "Path" in output
        assert "Data" in output
        assert "bpdb17" in output
        assert "10.1.1.1:3306" in output
    finally:
        client.delete(path, recursive=True)
        client.stop()


def test_lr_missing_znode_fails_with_a_diagnostic(
    zookeeper_hosts: str, monkeypatch, capsys
) -> None:
    monkeypatch.setenv("ZKTEST_HOSTS", zookeeper_hosts)

    with pytest.raises(SystemExit) as exception:
        main(["lr", "/does-not-exist", "--format", "json"])

    captured = capsys.readouterr()
    assert exception.value.code == 2
    assert captured.out == ""
    assert "does-not-exist" in captured.err


def test_lr_rejects_a_relative_path(zookeeper_hosts: str, monkeypatch, capsys) -> None:
    monkeypatch.setenv("ZKTEST_HOSTS", zookeeper_hosts)

    with pytest.raises(SystemExit) as exception:
        main(["lr", "relative", "--format", "json"])

    assert exception.value.code == 2
    assert "absolute" in capsys.readouterr().err
