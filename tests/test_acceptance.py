"""End-to-end acceptance flow from the documented user story."""

import os
import signal
import subprocess
from pathlib import Path
from time import monotonic, sleep

from kazoo.client import KazooClient


def _wait_for(predicate, timeout: float = 10.0) -> bool:
    deadline = monotonic() + timeout
    while monotonic() < deadline:
        if predicate():
            return True
        sleep(0.05)
    return predicate()


def test_documented_bpdb_server_and_client_flow(
    zookeeper_hosts: str, tmp_path: Path
) -> None:
    environment = os.environ.copy()
    environment["ZKTEST_HOSTS"] = zookeeper_hosts
    server = subprocess.Popen(
        [
            "uv",
            "run",
            "zktest",
            "server",
            "--cluster",
            "bpdb",
            "--name",
            "bpdb17",
            "--endpoint",
            "10.1.1.1:3306",
        ],
        cwd=Path(__file__).parents[1],
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    probe = KazooClient(hosts=zookeeper_hosts)
    probe.start(timeout=10)
    client_process = None
    try:
        assert _wait_for(lambda: probe.exists("/bpdb/bpdb17") is not None)

        cat = subprocess.run(
            ["uv", "run", "zktest", "cat", "/bpdb/bpdb17"],
            cwd=Path(__file__).parents[1],
            env=environment,
            capture_output=True,
            check=True,
        )
        assert cat.stdout == b"10.1.1.1:3306"

        target = tmp_path / "bpdb.endpoints"
        client_process = subprocess.Popen(
            [
                "uv",
                "run",
                "zktest",
                "client",
                "--cluster",
                "bpdb",
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
        assert _wait_for(lambda: target.exists())
        assert target.read_text(encoding="utf-8") == "10.1.1.1:3306 # bpdb17\n"
    finally:
        if client_process is not None and client_process.poll() is None:
            client_process.send_signal(signal.SIGINT)
            client_process.wait(timeout=10)
        if server.poll() is None:
            server.send_signal(signal.SIGINT)
            server.wait(timeout=10)
        probe.delete("/bpdb", recursive=True)
        probe.stop()
