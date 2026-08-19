"""Integration tests for the foreground ``server`` command."""

import os
import signal
import subprocess
import time
from pathlib import Path
from uuid import uuid4

import pytest
from kazoo.client import KazooClient

from zkdemo.cli import main


def _wait_for(predicate, timeout: float = 10.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.05)
    return predicate()


def test_server_registers_an_ephemeral_member_and_exits_cleanly(
    zookeeper_hosts: str,
) -> None:
    cluster = f"server-{uuid4().hex}"
    name = "bpdb17"
    member_path = f"/{cluster}/{name}"
    environment = os.environ.copy()
    environment["ZKTEST_HOSTS"] = zookeeper_hosts
    process = subprocess.Popen(
        [
            "uv",
            "run",
            "zktest",
            "server",
            "--cluster",
            cluster,
            "--name",
            name,
            "--endpoint",
            "10.1.1.1:3306",
        ],
        cwd=Path(__file__).parents[1],
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    client = KazooClient(hosts=zookeeper_hosts)
    client.start(timeout=10)
    try:
        assert _wait_for(lambda: client.exists(member_path) is not None)
        assert client.get(member_path)[0] == b"10.1.1.1:3306"

        process.send_signal(signal.SIGINT)
        assert process.wait(timeout=10) == 0
        assert _wait_for(lambda: client.exists(member_path) is None)
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=10)
        client.delete(f"/{cluster}", recursive=True)
        client.stop()


def test_server_duplicate_member_fails_without_overwriting(
    zookeeper_hosts: str, monkeypatch, capsys
) -> None:
    client = KazooClient(hosts=zookeeper_hosts)
    client.start(timeout=10)
    cluster = f"server-{uuid4().hex}"
    member_path = f"/{cluster}/bpdb17"
    try:
        client.create(f"/{cluster}")
        client.create(member_path, b"old-endpoint")
        monkeypatch.setenv("ZKTEST_HOSTS", zookeeper_hosts)

        with pytest.raises(SystemExit) as exception:
            main(
                [
                    "server",
                    "--cluster",
                    cluster,
                    "--name",
                    "bpdb17",
                    "--endpoint",
                    "new-endpoint",
                ]
            )

        captured = capsys.readouterr()
        assert exception.value.code == 2
        assert captured.out == ""
        assert "already exists" in captured.err
        assert client.get(member_path)[0] == b"old-endpoint"
    finally:
        client.delete(f"/{cluster}", recursive=True)
        client.stop()


@pytest.mark.parametrize(
    ("name", "endpoint", "diagnostic"),
    [
        ("bad/name", "endpoint", "single ZooKeeper path component"),
        ("bpdb17", "line\nendpoint", "newline"),
    ],
)
def test_server_rejects_unsafe_registration_values(
    zookeeper_hosts: str,
    monkeypatch,
    capsys,
    name: str,
    endpoint: str,
    diagnostic: str,
) -> None:
    monkeypatch.setenv("ZKTEST_HOSTS", zookeeper_hosts)

    with pytest.raises(SystemExit) as exception:
        main(
            [
                "server",
                "--cluster",
                f"server-{uuid4().hex}",
                "--name",
                name,
                "--endpoint",
                endpoint,
            ]
        )

    captured = capsys.readouterr()
    assert exception.value.code == 2
    assert captured.out == ""
    assert diagnostic in captured.err
