"""Tests for server registration across ZooKeeper session states."""

import threading
import time
from types import SimpleNamespace

from kazoo.exceptions import NodeExistsError
from kazoo.protocol.states import KazooState

from zkdemo.server import serve_member


class _FakeKazooClient:
    """Small external-client boundary for deterministic state transitions."""

    def __init__(self) -> None:
        self.listeners = []
        self.parent_exists = False
        self.member_exists = False
        self.creates: list[tuple[str, bytes, bool]] = []

    def add_listener(self, listener) -> None:
        self.listeners.append(listener)

    def remove_listener(self, listener) -> None:
        self.listeners.remove(listener)

    def create(
        self,
        path: str,
        data: bytes,
        acl=None,
        ephemeral: bool = False,
    ) -> None:
        if path == "/cluster" and self.parent_exists:
            raise NodeExistsError()
        if path == "/cluster/member" and self.member_exists:
            raise NodeExistsError()
        if path == "/cluster":
            self.parent_exists = True
        if path == "/cluster/member":
            self.member_exists = True
        self.creates.append((path, data, ephemeral))

    def exists(self, path: str):
        if path == "/cluster" and self.parent_exists:
            return SimpleNamespace(ephemeralOwner=0)
        if path == "/cluster/member" and self.member_exists:
            return SimpleNamespace(ephemeralOwner=1)
        return None

    def emit(self, state: str) -> None:
        for listener in list(self.listeners):
            listener(state)


def _wait_for(predicate, timeout: float = 2.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return predicate()


def test_temporary_disconnect_does_not_register_a_second_member() -> None:
    client = _FakeKazooClient()
    stop_event = threading.Event()
    thread = threading.Thread(
        target=serve_member,
        args=(client, "cluster", "member", "endpoint"),
        kwargs={"stop_event": stop_event},
    )
    thread.start()
    try:
        assert _wait_for(lambda: len(client.creates) == 2)

        client.emit(KazooState.SUSPENDED)
        client.emit(KazooState.CONNECTED)

        time.sleep(0.1)
        assert len(client.creates) == 2
    finally:
        stop_event.set()
        thread.join(timeout=2)
    assert not thread.is_alive()


def test_expired_session_recreates_only_this_ephemeral_member() -> None:
    client = _FakeKazooClient()
    stop_event = threading.Event()
    thread = threading.Thread(
        target=serve_member,
        args=(client, "cluster", "member", "endpoint"),
        kwargs={"stop_event": stop_event},
    )
    thread.start()
    try:
        assert _wait_for(lambda: len(client.creates) == 2)

        client.member_exists = False
        client.emit(KazooState.LOST)
        client.emit(KazooState.CONNECTED)

        assert _wait_for(lambda: len(client.creates) == 3)
        assert client.creates[-1] == ("/cluster/member", b"endpoint", True)
    finally:
        stop_event.set()
        thread.join(timeout=2)
    assert not thread.is_alive()


def test_expired_session_duplicate_is_fatal_without_overwrite() -> None:
    client = _FakeKazooClient()
    stop_event = threading.Event()
    errors = []

    def run() -> None:
        try:
            serve_member(
                client,
                "cluster",
                "member",
                "endpoint",
                stop_event=stop_event,
            )
        except BaseException as error:
            errors.append(error)

    thread = threading.Thread(target=run)
    thread.start()
    try:
        assert _wait_for(lambda: len(client.creates) == 2)

        client.member_exists = False
        client.emit(KazooState.LOST)
        client.member_exists = True
        client.emit(KazooState.CONNECTED)

        assert _wait_for(lambda: bool(errors))
        thread.join(timeout=2)
        assert isinstance(errors[0], NodeExistsError)
        assert len(client.creates) == 2
    finally:
        stop_event.set()
        thread.join(timeout=2)
    assert not thread.is_alive()
