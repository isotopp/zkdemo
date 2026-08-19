"""Small boundary around the external ZooKeeper client."""

import os
from collections.abc import Iterator
from contextlib import contextmanager

from kazoo.client import KazooClient

DEFAULT_ZOOKEEPER_HOSTS = "127.0.0.1:2181"


@contextmanager
def connected_client() -> Iterator[KazooClient]:
    """Yield a connected client and close it when the command finishes."""
    client = KazooClient(hosts=os.environ.get("ZKTEST_HOSTS", DEFAULT_ZOOKEEPER_HOSTS))
    timeout = float(os.environ.get("ZKTEST_TIMEOUT", "10"))
    client.start(timeout=timeout)
    try:
        yield client
    finally:
        client.stop()
        client.close()
