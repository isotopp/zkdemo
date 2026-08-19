"""Read-only znode listing operations."""

from typing import Any

from kazoo.client import KazooClient


def validate_znode_path(path: str) -> None:
    """Reject paths that cannot identify an absolute znode."""
    if not path.startswith("/"):
        raise ValueError("znode path must be absolute")


def _stat_dict(stat: Any) -> dict[str, int]:
    return {
        "czxid": stat.czxid,
        "mzxid": stat.mzxid,
        "ctime": stat.ctime,
        "mtime": stat.mtime,
        "version": stat.version,
        "cversion": stat.cversion,
        "aversion": stat.aversion,
        "ephemeralOwner": stat.ephemeralOwner,
        "dataLength": stat.dataLength,
        "numChildren": stat.numChildren,
        "pzxid": stat.pzxid,
    }


def direct_children(client: KazooClient, path: str) -> dict[str, object]:
    """Return one znode and its sorted direct children."""
    data, stat = client.get(path)
    children: list[dict[str, object]] = []
    for name in sorted(client.get_children(path)):
        child_path = f"/{name}" if path == "/" else f"{path}/{name}"
        child_data, child_stat = client.get(child_path)
        children.append(
            {
                "name": name,
                "path": child_path,
                "data": child_data.decode("utf-8"),
                "stat": _stat_dict(child_stat),
            }
        )

    return {
        "path": path,
        "data": data.decode("utf-8"),
        "stat": _stat_dict(stat),
        "children": children,
    }


def read_data(client: KazooClient, path: str) -> bytes:
    """Return the exact data bytes stored at one znode."""
    validate_znode_path(path)
    data, _ = client.get(path)
    return data


def recursive_nodes(client: KazooClient, path: str = "/") -> list[dict[str, object]]:
    """Return every reachable znode in deterministic depth-first order."""
    validate_znode_path(path)
    nodes: list[dict[str, object]] = []

    def visit(current: str) -> None:
        data, stat = client.get(current)
        nodes.append(
            {
                "path": current,
                "data": data.decode("utf-8"),
                "stat": _stat_dict(stat),
            }
        )
        for name in sorted(client.get_children(current)):
            child_path = f"/{name}" if current == "/" else f"{current}/{name}"
            visit(child_path)

    visit(path)
    return nodes
