"""Small boundary around the external ZooKeeper client."""

from collections.abc import Iterator
from contextlib import contextmanager

from kazoo.client import KazooClient

from zkdemo.configuration import configured

DEFAULT_ZOOKEEPER_HOSTS = "127.0.0.1:2181"


@contextmanager
def connected_client() -> Iterator[KazooClient]:
    """Yield a connected client and close it when the command finishes."""
    hosts = (
        configured("ZKTEST_HOSTS", DEFAULT_ZOOKEEPER_HOSTS) or DEFAULT_ZOOKEEPER_HOSTS
    )
    timeout = float(configured("ZKTEST_TIMEOUT", "10") or "10")
    client = KazooClient(hosts=hosts)
    client.start(timeout=timeout)
    try:
        yield client
    finally:
        client.stop()
        client.close()
