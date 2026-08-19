"""Small boundary around the external ZooKeeper client."""

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any, Protocol

from kazoo.client import KazooClient

from zkdemo.configuration import configured, parse_host_list

DEFAULT_ZOOKEEPER_HOSTS = "127.0.0.1:2181"


class DiscoveryClient(Protocol):
    """ZooKeeper operations required for ensemble discovery."""

    def sync(self, path: str) -> Any: ...

    def get(self, path: str) -> tuple[bytes, Any]: ...

    def set_hosts(self, hosts: str) -> Any: ...


def _server_host(server: str) -> str:
    if server.startswith("["):
        closing = server.find("]")
        if closing <= 1:
            raise ValueError(f"invalid server address {server!r}")
        return server[: closing + 1]
    return server.split(":", 1)[0]


def discover_ensemble(client: DiscoveryClient) -> list[str]:
    """Synchronize and apply all participant/observer client endpoints."""
    config_path = "/zookeeper/config"
    client.sync(config_path)
    data, _ = client.get(config_path)
    endpoints: list[str] = []
    for line in data.decode("utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("version="):
            continue
        if not line.startswith("server.") or "=" not in line:
            raise ValueError(f"malformed ensemble configuration line: {line!r}")
        server_spec = line.split("=", 1)[1]
        if ";" not in server_spec:
            raise ValueError(f"missing client endpoint in ensemble line: {line!r}")
        quorum_spec, client_spec = server_spec.rsplit(";", 1)
        quorum_parts = quorum_spec.split(":")
        if len(quorum_parts) < 4:
            raise ValueError(f"malformed server endpoint in ensemble line: {line!r}")
        role = quorum_parts[-1]
        if role not in {"participant", "observer"}:
            raise ValueError(f"unknown ensemble server role: {role!r}")
        client_endpoint = client_spec
        if ":" not in client_spec:
            client_endpoint = f"{_server_host(quorum_spec)}:{client_spec}"
        try:
            endpoints.extend(parse_host_list(client_endpoint))
        except ValueError as error:
            raise ValueError(
                f"invalid client endpoint in ensemble line: {line!r}: {error}"
            ) from error
    if not endpoints:
        raise ValueError("ensemble configuration has no client endpoints")
    unique_endpoints = list(dict.fromkeys(endpoints))
    client.set_hosts(",".join(unique_endpoints))
    return unique_endpoints


@contextmanager
def connected_client() -> Iterator[KazooClient]:
    """Yield a connected client and close it when the command finishes."""
    hosts = (
        configured("ZKTEST_HOSTS", DEFAULT_ZOOKEEPER_HOSTS) or DEFAULT_ZOOKEEPER_HOSTS
    )
    parse_host_list(hosts)
    timeout = float(configured("ZKTEST_TIMEOUT", "10") or "10")
    client = KazooClient(hosts=hosts)
    client.start(timeout=timeout)
    try:
        discover_ensemble(client)
        yield client
    finally:
        client.stop()
        client.close()
