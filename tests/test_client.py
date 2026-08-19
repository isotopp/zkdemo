"""Integration tests for the initial endpoint-file client render."""

import os
import signal
import subprocess
from pathlib import Path
from time import monotonic, sleep
from uuid import uuid4

import pytest
from kazoo.client import KazooClient

from zkdemo.cli import build_parser, main


def _wait_for_file(path: Path, timeout: float = 10.0) -> bool:
    deadline = monotonic() + timeout
    while monotonic() < deadline:
        if path.exists():
            return True
        sleep(0.05)
    return path.exists()


def _wait_for_content(path: Path, expected: str, timeout: float = 10.0) -> bool:
    deadline = monotonic() + timeout
    while monotonic() < deadline:
        if path.exists() and path.read_text(encoding="utf-8") == expected:
            return True
        sleep(0.05)
    return path.exists() and path.read_text(encoding="utf-8") == expected


def test_client_renders_sorted_initial_endpoint_file(
    zookeeper_hosts: str, tmp_path: Path
) -> None:
    client = KazooClient(hosts=zookeeper_hosts)
    client.start(timeout=10)
    cluster = f"client-{uuid4().hex}"
    target = tmp_path / "nested" / "bpdb.endpoints"
    environment = os.environ.copy()
    environment["ZKTEST_HOSTS"] = zookeeper_hosts
    try:
        client.create(f"/{cluster}")
        client.create(f"/{cluster}/bpdb17", b"10.1.1.1:3306")
        client.create(f"/{cluster}/bpdb03", b"10.1.1.3:3306")
        process = subprocess.Popen(
            [
                "uv",
                "run",
                "zktest",
                "client",
                "--cluster",
                cluster,
                "--file",
                str(target),
                "--delay",
                "0",
            ],
            cwd=Path(__file__).parents[1],
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            assert _wait_for_file(target)
            assert target.read_text(encoding="utf-8") == (
                "10.1.1.3:3306 # bpdb03\n10.1.1.1:3306 # bpdb17\n"
            )
            process.send_signal(signal.SIGINT)
            assert process.wait(timeout=10) == 0
        finally:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=10)
    finally:
        client.delete(f"/{cluster}", recursive=True)
        client.stop()


def test_client_replaces_existing_file_with_empty_cluster_snapshot(
    zookeeper_hosts: str, tmp_path: Path
) -> None:
    client = KazooClient(hosts=zookeeper_hosts)
    client.start(timeout=10)
    cluster = f"client-{uuid4().hex}"
    target = tmp_path / "nested" / "bpdb.endpoints"
    target.parent.mkdir(parents=True)
    target.write_text("stale\n", encoding="utf-8")
    environment = os.environ.copy()
    environment["ZKTEST_HOSTS"] = zookeeper_hosts
    try:
        client.create(f"/{cluster}")
        process = subprocess.Popen(
            [
                "uv",
                "run",
                "zktest",
                "client",
                "--cluster",
                cluster,
                "--file",
                str(target),
                "--delay",
                "0",
            ],
            cwd=Path(__file__).parents[1],
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            assert _wait_for_content(target, "")
            process.send_signal(signal.SIGINT)
            assert process.wait(timeout=10) == 0
        finally:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=10)
    finally:
        client.delete(f"/{cluster}", recursive=True)
        client.stop()


def test_client_missing_cluster_fails_and_preserves_existing_file(
    zookeeper_hosts: str, monkeypatch, tmp_path: Path, capsys
) -> None:
    target = tmp_path / "nested" / "bpdb.endpoints"
    target.parent.mkdir(parents=True)
    target.write_text("old\n", encoding="utf-8")
    monkeypatch.setenv("ZKTEST_HOSTS", zookeeper_hosts)

    with pytest.raises(SystemExit) as exception:
        main(
            [
                "client",
                "--cluster",
                f"missing-{uuid4().hex}",
                "--file",
                str(target),
            ]
        )

    captured = capsys.readouterr()
    assert exception.value.code == 2
    assert captured.out == ""
    assert "does not exist" in captured.err
    assert target.read_text(encoding="utf-8") == "old\n"


@pytest.mark.parametrize("delay", ["-1", "nan", "inf"])
def test_client_rejects_invalid_delay(delay: str) -> None:
    with pytest.raises(SystemExit) as exception:
        build_parser().parse_args(
            [
                "client",
                "--cluster",
                "bpdb",
                "--file",
                "/tmp/bpdb.endpoints",
                "--delay",
                delay,
            ]
        )

    assert exception.value.code == 2
