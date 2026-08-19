"""Initial endpoint-file rendering for a ZooKeeper cluster client."""

import os
import random
from collections.abc import Callable
from pathlib import Path
from threading import Event
from typing import Any, Protocol

from kazoo.exceptions import ConnectionLoss, SessionExpiredError
from kazoo.handlers.threading import KazooTimeoutError
from kazoo.protocol.states import KazooState

from zkdemo.server import validate_component
from zkdemo.zookeeper import EnsembleMonitor


class ClientConnection(Protocol):
    """ZooKeeper client operations needed by the endpoint client."""

    def add_listener(self, listener: Callable[[str], object]) -> None: ...

    def remove_listener(self, listener: Callable[[str], object]) -> None: ...

    def exists(self, path: str) -> Any: ...

    def get_children(
        self, path: str, watch: Callable[[object], object] | None = None
    ) -> list[str]: ...

    def get(
        self, path: str, watch: Callable[[object], object] | None = None
    ) -> tuple[bytes, Any]: ...


def endpoint_snapshot(client: ClientConnection, cluster: str) -> list[tuple[str, str]]:
    """Read and sort the current endpoint data for one cluster."""
    validate_component(cluster, "cluster")
    cluster_path = f"/{cluster}"
    if client.exists(cluster_path) is None:
        raise ValueError(f"cluster {cluster_path} does not exist")

    endpoints: list[tuple[str, str]] = []
    for name in sorted(client.get_children(cluster_path)):
        member_path = f"{cluster_path}/{name}"
        data, _ = client.get(member_path)
        endpoint = data.decode("utf-8")
        if "\r" in endpoint or "\n" in endpoint:
            raise ValueError(
                f"member {member_path} contains carriage return or newline"
            )
        endpoints.append((name, endpoint))
    return endpoints


def write_endpoint_file(
    output_file: str | Path, endpoints: list[tuple[str, str]]
) -> None:
    """Atomically replace an endpoint file using this process's PID suffix."""
    target = Path(output_file)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f"{target.name}.{os.getpid()}")
    content = "".join(f"{endpoint} # {name}\n" for name, endpoint in endpoints)
    temporary.write_text(content, encoding="utf-8", newline="")
    os.replace(temporary, target)


def run_client(
    client: ClientConnection,
    cluster: str,
    output_file: str | Path,
    *,
    delay: float = 3.0,
    monitor: EnsembleMonitor | None = None,
    stop_event: Event | None = None,
) -> None:
    """Render the snapshot and converge after watched cluster changes."""
    endpoints = endpoint_snapshot(client, cluster)
    write_endpoint_file(output_file, endpoints)
    shutdown = stop_event or Event()
    changes = Event()
    connection_ready = Event()
    connection_ready.set()

    def changed(_event: object) -> None:
        changes.set()

    def state_changed(state: str) -> None:
        if state in (KazooState.SUSPENDED, KazooState.LOST):
            connection_ready.clear()
        elif state == KazooState.CONNECTED:
            connection_ready.set()
        changes.set()

    def install_watches() -> None:
        cluster_path = f"/{cluster}"
        names = client.get_children(cluster_path, watch=changed)
        for name in names:
            client.get(f"{cluster_path}/{name}", watch=changed)

    def install_when_connected() -> bool:
        while not shutdown.is_set():
            if not connection_ready.wait(0.1):
                continue
            try:
                install_watches()
            except ConnectionLoss, SessionExpiredError, KazooTimeoutError:
                connection_ready.clear()
                continue
            return True
        return False

    client.add_listener(state_changed)
    try:
        if monitor is not None:
            monitor.start()
        if not install_when_connected():
            return
        while not shutdown.is_set():
            if monitor is not None:
                monitor.process()
            if not changes.wait(0.1):
                continue
            changes.clear()
            while True:
                if not install_when_connected():
                    return
                jitter = random.uniform(0, delay)
                if shutdown.wait(jitter):
                    return
                if not changes.is_set():
                    break
                changes.clear()
            try:
                endpoints = endpoint_snapshot(client, cluster)
            except ConnectionLoss, SessionExpiredError, KazooTimeoutError:
                connection_ready.clear()
                changes.set()
                continue
            write_endpoint_file(output_file, endpoints)
    except KeyboardInterrupt:
        return
    finally:
        if monitor is not None:
            monitor.stop()
        client.remove_listener(state_changed)
