"""Integration tests for the ``lslr`` command."""

import json
from uuid import uuid4

import pytest
from kazoo.client import KazooClient

from zkdemo.cli import main


def test_lslr_json_lists_every_node_depth_first(
    zookeeper_hosts: str, monkeypatch, capsys
) -> None:
    client = KazooClient(hosts=zookeeper_hosts)
    client.start(timeout=10)
    root = f"/lslr-{uuid4().hex}"
    try:
        client.create(root, b"root")
        client.create(f"{root}/branch", b"branch")
        client.create(f"{root}/branch/leaf", b"leaf")
        client.create(f"{root}/sibling", b"sibling")
        monkeypatch.setenv("ZKTEST_HOSTS", zookeeper_hosts)

        main(["lslr", "--format", "json"])

        document = json.loads(capsys.readouterr().out)
        paths = [node["path"] for node in document["nodes"]]
        assert paths[:5] == [
            "/",
            root,
            f"{root}/branch",
            f"{root}/branch/leaf",
            f"{root}/sibling",
        ]
        assert len(paths) == len(set(paths))
        assert document["nodes"][2]["data"] == "branch"
        assert set(document["nodes"][2]["stat"]) == {
            "czxid",
            "mzxid",
            "ctime",
            "mtime",
            "version",
            "cversion",
            "aversion",
            "ephemeralOwner",
            "dataLength",
            "numChildren",
            "pzxid",
        }
    finally:
        client.delete(root, recursive=True)
        client.stop()


def test_lslr_text_renders_path_data_and_stat_headers(
    zookeeper_hosts: str, monkeypatch, capsys
) -> None:
    client = KazooClient(hosts=zookeeper_hosts)
    client.start(timeout=10)
    path = f"/lslr-{uuid4().hex}"
    try:
        client.create(path, b"cookie")
        monkeypatch.setenv("ZKTEST_HOSTS", zookeeper_hosts)

        main(["lslr", "--format", "text"])

        output = capsys.readouterr().out
        for heading in (
            "Path",
            "Data",
            "czxid",
            "mzxid",
            "ctime",
            "mtime",
            "version",
            "cversion",
            "aversion",
            "ephemeralOwner",
            "dataLength",
            "numChildren",
            "pzxid",
        ):
            assert heading in output
        assert path in output
        assert "cookie" in output
    finally:
        client.delete(path)
        client.stop()


def test_lslr_unavailable_server_fails_with_a_diagnostic(monkeypatch, capsys) -> None:
    monkeypatch.setenv("ZKTEST_HOSTS", "127.0.0.1:1")
    monkeypatch.setenv("ZKTEST_TIMEOUT", "0.1")

    with pytest.raises(SystemExit) as exception:
        main(["lslr", "--format", "json"])

    captured = capsys.readouterr()
    assert exception.value.code == 2
    assert captured.out == ""
    assert "cannot read /" in captured.err
