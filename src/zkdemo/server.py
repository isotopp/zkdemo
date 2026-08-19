"""Foreground ephemeral server registration."""

from collections.abc import Callable
from threading import Event
from typing import Any, Protocol

from kazoo.exceptions import KazooException, NodeExistsError
from kazoo.handlers.threading import KazooTimeoutError
from kazoo.protocol.states import KazooState


class RegistrationClient(Protocol):
    """ZooKeeper client operations needed by the registration loop."""

    def add_listener(self, listener: Callable[[str], object]) -> None: ...

    def remove_listener(self, listener: Callable[[str], object]) -> None: ...

    def create(
        self,
        path: str,
        data: bytes,
        /,
        acl: Any = None,
        ephemeral: bool = False,
    ) -> Any: ...

    def exists(self, path: str) -> Any: ...


def validate_component(value: str, label: str) -> None:
    """Validate one ZooKeeper path component and its output-safe characters."""
    if not value:
        raise ValueError(f"{label} must not be empty")
    if value in {".", ".."} or "/" in value or "\x00" in value:
        raise ValueError(f"{label} must be a single ZooKeeper path component")
    if "\r" in value or "\n" in value:
        raise ValueError(f"{label} must not contain carriage return or newline")


def register_member(
    client: RegistrationClient, cluster: str, name: str, endpoint: str
) -> str:
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


def serve_member(
    client: RegistrationClient,
    cluster: str,
    name: str,
    endpoint: str,
    *,
    stop_event: Event | None = None,
) -> None:
    """Register a member and hold the process in the foreground."""
    shutdown = stop_event or Event()
    connected = Event()
    wake = Event()
    needs_registration = True

    def on_state(state: str) -> None:
        nonlocal needs_registration
        if state == KazooState.SUSPENDED:
            connected.clear()
        elif state == KazooState.LOST:
            needs_registration = True
            connected.clear()
        elif state == KazooState.CONNECTED:
            connected.set()
        wake.set()

    client.add_listener(on_state)
    connected.set()
    try:
        while not shutdown.is_set():
            if not needs_registration:
                wake.wait(0.1)
                wake.clear()
                continue
            if not connected.wait(0.1):
                continue
            try:
                register_member(client, cluster, name, endpoint)
            except NodeExistsError:
                raise
            except KazooException, KazooTimeoutError:
                wake.wait(0.1)
                wake.clear()
                continue
            needs_registration = False
    except KeyboardInterrupt:
        return
    finally:
        client.remove_listener(on_state)
