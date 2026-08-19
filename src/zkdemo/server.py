"""Foreground ephemeral server registration."""

from threading import Event

from kazoo.client import KazooClient
from kazoo.exceptions import NodeExistsError


def validate_component(value: str, label: str) -> None:
    """Validate one ZooKeeper path component and its output-safe characters."""
    if not value:
        raise ValueError(f"{label} must not be empty")
    if value in {".", ".."} or "/" in value or "\x00" in value:
        raise ValueError(f"{label} must be a single ZooKeeper path component")
    if "\r" in value or "\n" in value:
        raise ValueError(f"{label} must not contain carriage return or newline")


def register_member(client: KazooClient, cluster: str, name: str, endpoint: str) -> str:
    """Create the persistent cluster and this process's ephemeral member."""
    validate_component(cluster, "cluster")
    validate_component(name, "name")
    if "\r" in endpoint or "\n" in endpoint:
        raise ValueError("endpoint must not contain carriage return or newline")

    cluster_path = f"/{cluster}"
    try:
        client.create(cluster_path, b"", ephemeral=False)
    except NodeExistsError:
        stat = client.exists(cluster_path)
        if stat is None:
            client.create(cluster_path, b"", ephemeral=False)
        elif stat.ephemeralOwner != 0:
            raise ValueError(f"cluster parent {cluster_path} is not persistent")

    member_path = f"{cluster_path}/{name}"
    client.create(member_path, endpoint.encode("utf-8"), ephemeral=True)
    return member_path


def serve_member(client: KazooClient, cluster: str, name: str, endpoint: str) -> None:
    """Register a member and hold the process in the foreground."""
    register_member(client, cluster, name, endpoint)
    try:
        Event().wait()
    except KeyboardInterrupt:
        return
