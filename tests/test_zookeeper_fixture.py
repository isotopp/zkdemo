"""Integration coverage for the local ZooKeeper test fixture."""

from kazoo.client import KazooClient


def test_zookeeper_fixture_exposes_a_live_server(zookeeper_hosts: str) -> None:
    client = KazooClient(hosts=zookeeper_hosts)
    client.start(timeout=10)
    try:
        assert client.exists("/") is not None
    finally:
        client.stop()
