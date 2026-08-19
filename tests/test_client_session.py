"""Tests for client convergence across ZooKeeper connection states."""

import threading
import time
from pathlib import Path
from types import SimpleNamespace

from kazoo.protocol.states import KazooState

from zkdemo.client import run_client


class _FakeClient:
    """External ZooKeeper boundary with controllable state transitions."""

    def __init__(self) -> None:
        self.endpoint = "old-endpoint"
        self.state_listeners = []
        self.watches = []

    def add_listener(self, listener) -> None:
        self.state_listeners.append(listener)

    def remove_listener(self, listener) -> None:
        self.state_listeners.remove(listener)

    def exists(self, path: str):
        return SimpleNamespace() if path == "/cluster" else None

    def get_children(self, path: str, watch=None):
        if watch is not None:
            self.watches.append(watch)
        return ["member"]

    def get(self, path: str, watch=None):
        if watch is not None:
            self.watches.append(watch)
        return self.endpoint.encode(), SimpleNamespace()

    def emit(self, state: str) -> None:
        for listener in list(self.state_listeners):
            listener(state)


def _wait_for_content(path: Path, expected: str, timeout: float = 2.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if path.exists() and path.read_text(encoding="utf-8") == expected:
            return True
        time.sleep(0.01)
    return path.exists() and path.read_text(encoding="utf-8") == expected


def test_client_reinstalls_watches_after_temporary_connection_loss(
    tmp_path: Path,
) -> None:
    client = _FakeClient()
    target = tmp_path / "endpoints"
    stop_event = threading.Event()
    thread = threading.Thread(
        target=run_client,
        args=(client, "cluster", target),
        kwargs={"delay": 0, "stop_event": stop_event},
    )
    thread.start()
    try:
        assert _wait_for_content(target, "old-endpoint # member\n")
        client.endpoint = "new-endpoint"
        client.emit(KazooState.SUSPENDED)
        client.emit(KazooState.CONNECTED)
        assert _wait_for_content(target, "new-endpoint # member\n")
        assert len(client.watches) >= 4
    finally:
        stop_event.set()
        thread.join(timeout=2)
    assert not thread.is_alive()
