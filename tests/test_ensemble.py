"""Tests for ZooKeeper ensemble bootstrap discovery."""

from types import SimpleNamespace

import pytest

from zkdemo.zookeeper import discover_ensemble


class _FakeConfigClient:
    def __init__(self, value: bytes) -> None:
        self.value = value
        self.synced = []
        self.hosts = None
        self.watchers = []
        self.state_listeners = []

    def add_listener(self, listener) -> None:
        self.state_listeners.append(listener)

    def remove_listener(self, listener) -> None:
        self.state_listeners.remove(listener)

    def sync(self, path: str) -> None:
        self.synced.append(path)

    def get(self, path: str, watch=None):
        assert path == "/zookeeper/config"
        if watch is not None:
            self.watchers.append(watch)
        return self.value, SimpleNamespace()

    def set_hosts(self, hosts: str) -> None:
        self.hosts = hosts

    def emit_config_change(self) -> None:
        watcher = self.watchers.pop(0)
        watcher(SimpleNamespace())


def test_discover_ensemble_uses_all_client_endpoints() -> None:
    client = _FakeConfigClient(
        b"server.1=zk1.example:2888:3888:participant;zk1.example:2181\n"
        b"server.2=zk2.example:2888:3888:observer;[::1]:2182\n"
        b"version=0x100000001\n"
    )

    endpoints = discover_ensemble(client)

    assert endpoints == ["zk1.example:2181", "[::1]:2182"]
    assert client.synced == ["/zookeeper/config"]
    assert client.hosts == "zk1.example:2181,[::1]:2182"


def test_discover_ensemble_rejects_empty_configuration() -> None:
    client = _FakeConfigClient(b"version=0x100000001\n")

    try:
        discover_ensemble(client)
    except ValueError as error:
        assert "no client endpoints" in str(error)
    else:
        raise AssertionError("empty ensemble configuration unexpectedly succeeded")


def test_discover_ensemble_rejects_malformed_configuration() -> None:
    client = _FakeConfigClient(b"server.1=zk1.example:2888:3888:participant\n")

    try:
        discover_ensemble(client)
    except ValueError as error:
        assert "missing client endpoint" in str(error)
    else:
        raise AssertionError("malformed ensemble configuration unexpectedly succeeded")


def test_local_fixture_advertises_a_single_dynamic_participant(
    zookeeper_hosts: str,
) -> None:
    from kazoo.client import KazooClient

    client = KazooClient(hosts=zookeeper_hosts)
    client.start(timeout=10)
    try:
        data, _ = client.get("/zookeeper/config")
        assert b"server.1=" in data
        assert b"participant" in data
    finally:
        client.stop()


def test_config_monitor_rearms_before_applying_new_configuration() -> None:
    from zkdemo.zookeeper import EnsembleMonitor

    client = _FakeConfigClient(
        b"server.1=zk1.example:2888:3888:participant;zk1.example:2181\n"
    )
    monitor = EnsembleMonitor(client)
    monitor.start()
    client.value = b"server.1=zk2.example:2888:3888:participant;zk2.example:2182\n"

    client.emit_config_change()
    monitor.process()

    assert client.hosts == "zk2.example:2182"
    assert len(client.watchers) == 1


def test_config_monitor_fails_on_malformed_update_after_rearming() -> None:
    from zkdemo.zookeeper import EnsembleMonitor

    client = _FakeConfigClient(
        b"server.1=zk1.example:2888:3888:participant;zk1.example:2181\n"
    )
    monitor = EnsembleMonitor(client)
    monitor.start()
    client.value = b"server.1=zk1.example:2888:3888:participant\n"
    client.emit_config_change()

    with pytest.raises(ValueError, match="missing client endpoint"):
        monitor.process()
    assert len(client.watchers) == 1
