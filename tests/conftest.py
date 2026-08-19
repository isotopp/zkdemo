"""Shared integration-test fixtures."""

import os
import shutil
import socket
import subprocess
from collections.abc import Iterator
from pathlib import Path

import pytest
from kazoo.client import KazooClient


def _zookeeper_server() -> str | None:
    if os.environ.get("ZOOKEEPER_HOME"):
        server = Path(os.environ["ZOOKEEPER_HOME"]) / "bin" / "zkServer.sh"
        if server.is_file() and os.access(server, os.X_OK):
            return str(server)

    return shutil.which("zkServer") or shutil.which("zkServer.sh")


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@pytest.fixture(scope="session")
def zookeeper_hosts(tmp_path_factory: pytest.TempPathFactory) -> Iterator[str]:
    """Start an isolated ZooKeeper daemon and yield its client address."""
    server = _zookeeper_server()
    if server is None:
        pytest.skip("zkServer is not installed")

    runtime_dir = tmp_path_factory.mktemp("zookeeper")
    config_dir = runtime_dir / "conf"
    data_dir = runtime_dir / "data"
    log_dir = runtime_dir / "logs"
    config_dir.mkdir()
    data_dir.mkdir()
    log_dir.mkdir()

    port = _free_port()
    config_file = config_dir / "zoo.cfg"
    config_file.write_text(
        "\n".join(
            [
                "tickTime=2000",
                "initLimit=10",
                "syncLimit=5",
                f"dataDir={data_dir}",
                f"clientPort={port}",
                "admin.enableServer=false",
                "standaloneEnabled=true",
                "",
            ]
        ),
        encoding="utf-8",
    )

    environment = os.environ.copy()
    environment["ZOOCFGDIR"] = str(config_dir)
    environment["ZOO_LOG_DIR"] = str(log_dir)
    hosts = f"127.0.0.1:{port}"

    started = subprocess.run(
        [server, "start"],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )
    if started.returncode != 0:
        detail = (started.stdout + started.stderr).strip()
        raise RuntimeError(f"could not start test ZooKeeper: {detail}")

    probe = KazooClient(hosts=hosts)
    try:
        probe.start(timeout=10)
        yield hosts
    finally:
        probe.stop()
        subprocess.run(
            [server, "stop"],
            check=False,
            capture_output=True,
            text=True,
            env=environment,
        )
