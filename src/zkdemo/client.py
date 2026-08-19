"""Initial endpoint-file rendering for a ZooKeeper cluster client."""

import os
from pathlib import Path
from threading import Event

from kazoo.client import KazooClient

from zkdemo.server import validate_component


def endpoint_snapshot(client: KazooClient, cluster: str) -> list[tuple[str, str]]:
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
    client: KazooClient,
    cluster: str,
    output_file: str | Path,
    *,
    stop_event: Event | None = None,
) -> None:
    """Render the initial snapshot and remain in the foreground."""
    endpoints = endpoint_snapshot(client, cluster)
    write_endpoint_file(output_file, endpoints)
    try:
        (stop_event or Event()).wait()
    except KeyboardInterrupt:
        return
