"""Integration tests for the ``cat`` command."""

from uuid import uuid4

import pytest
from kazoo.client import KazooClient

from zkdemo.cli import main


def test_cat_writes_raw_znode_bytes(
    zookeeper_hosts: str, monkeypatch, capsysbinary
) -> None:
    client = KazooClient(hosts=zookeeper_hosts)
    client.start(timeout=10)
    path = f"/cat-{uuid4().hex}"
    data = b"cookie\x00value\nwithout-a-cli-newline"
    try:
        client.create(path, data)
        monkeypatch.setenv("ZKTEST_HOSTS", zookeeper_hosts)

        main(["cat", path])

        assert capsysbinary.readouterr().out == data
    finally:
        client.delete(path)
        client.stop()


def test_cat_empty_znode_succeeds(
    zookeeper_hosts: str, monkeypatch, capsysbinary
) -> None:
    client = KazooClient(hosts=zookeeper_hosts)
    client.start(timeout=10)
    path = f"/cat-{uuid4().hex}"
    try:
        client.create(path)
        monkeypatch.setenv("ZKTEST_HOSTS", zookeeper_hosts)

        main(["cat", path])

        assert capsysbinary.readouterr().out == b""
    finally:
        client.delete(path)
        client.stop()


def test_cat_missing_znode_fails_with_a_diagnostic(
    zookeeper_hosts: str, monkeypatch, capsysbinary
) -> None:
    monkeypatch.setenv("ZKTEST_HOSTS", zookeeper_hosts)

    with pytest.raises(SystemExit) as exception:
        main(["cat", "/does-not-exist"])

    captured = capsysbinary.readouterr()
    assert exception.value.code == 2
    assert captured.out == b""
    assert b"does-not-exist" in captured.err


def test_cat_unavailable_server_fails_clearly(monkeypatch, capsysbinary) -> None:
    monkeypatch.setenv("ZKTEST_HOSTS", "127.0.0.1:1")
    monkeypatch.setenv("ZKTEST_TIMEOUT", "0.1")

    with pytest.raises(SystemExit) as exception:
        main(["cat", "/"])

    captured = capsysbinary.readouterr()
    assert exception.value.code == 2
    assert captured.out == b""
    assert b"cannot read /" in captured.err
