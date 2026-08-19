"""Command-line entry point for the ZooKeeper development harness."""

import argparse
import json
import sys
from collections.abc import Sequence
from typing import cast

from kazoo.exceptions import KazooException, NodeExistsError
from kazoo.handlers.threading import KazooTimeoutError
from rich.console import Console
from rich.table import Table

from zkdemo.listing import (
    direct_children,
    read_data,
    recursive_nodes,
    validate_znode_path,
)
from zkdemo.server import serve_member
from zkdemo.zookeeper import connected_client

console = Console(color_system=None, width=240)
_STAT_FIELDS = (
    "czxid",
    "mzxid",
    "ctime",
    "mtime",
    "version",
    "cversion",
    "aversion",
    "ephemeralOwner",
    "dataLength",
    "numChildren",
    "pzxid",
)


def _print_lr_text(listing: dict[str, object]) -> None:
    children = cast(list[dict[str, object]], listing["children"])
    table = Table("Name", "Path", "Data")
    for child in children:
        table.add_row(
            str(child["name"]),
            str(child["path"]),
            str(child["data"]),
        )
    console.print(table)


def _print_lslr_text(nodes: list[dict[str, object]]) -> None:
    table = Table("Path", "Data", *_STAT_FIELDS)
    for node in nodes:
        stat = cast(dict[str, int], node["stat"])
        table.add_row(
            str(node["path"]),
            str(node["data"]),
            *(str(stat[field]) for field in _STAT_FIELDS),
        )
    console.print(table)


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""
    parser = argparse.ArgumentParser(
        prog="zktest",
        description="Run and exercise a local single-instance ZooKeeper.",
    )
    subcommands = parser.add_subparsers(dest="command", required=True)

    lslr = subcommands.add_parser("lslr", help="Recursively list the ZooKeeper tree")
    lslr.add_argument(
        "--format", choices=("text", "json"), default="text", dest="output_format"
    )

    lr = subcommands.add_parser("lr", help="List one znode's children")
    lr.add_argument("znode_path")
    lr.add_argument(
        "--format", choices=("text", "json"), default="text", dest="output_format"
    )

    cat = subcommands.add_parser("cat", help="Read one znode's data")
    cat.add_argument("znode_path")

    server = subcommands.add_parser(
        "server", help="Register an ephemeral server endpoint"
    )
    server.add_argument("--cluster", required=True)
    server.add_argument("--name", required=True)
    server.add_argument("--endpoint", required=True)

    client = subcommands.add_parser(
        "client", help="Write a cluster's endpoint list and watch for changes"
    )
    client.add_argument("--cluster", required=True)
    client.add_argument("--file", required=True, dest="output_file")
    client.add_argument("--delay", default=3.0, type=float)
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    """Run the selected command."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "lr":
        try:
            validate_znode_path(args.znode_path)
            with connected_client() as client:
                listing = direct_children(client, args.znode_path)
        except (
            KazooException,
            KazooTimeoutError,
            UnicodeDecodeError,
            ValueError,
            OSError,
        ) as error:
            detail = str(error) or error.__class__.__name__
            parser.error(f"cannot read {args.znode_path}: {detail}")
        if args.output_format == "json":
            print(json.dumps(listing))
        else:
            _print_lr_text(listing)
        return

    if args.command == "cat":
        try:
            with connected_client() as client:
                data = read_data(client, args.znode_path)
        except (KazooException, KazooTimeoutError, ValueError, OSError) as error:
            detail = str(error) or error.__class__.__name__
            parser.error(f"cannot read {args.znode_path}: {detail}")
        sys.stdout.buffer.write(data)
        sys.stdout.buffer.flush()
        return

    if args.command == "lslr":
        try:
            with connected_client() as client:
                nodes = recursive_nodes(client)
        except (
            KazooException,
            KazooTimeoutError,
            UnicodeDecodeError,
            ValueError,
            OSError,
        ) as error:
            detail = str(error) or error.__class__.__name__
            parser.error(f"cannot read /: {detail}")
        if args.output_format == "json":
            print(json.dumps({"nodes": nodes}))
        else:
            _print_lslr_text(nodes)
        return

    if args.command == "server":
        try:
            with connected_client() as client:
                serve_member(client, args.cluster, args.name, args.endpoint)
        except NodeExistsError:
            parser.error(
                f"cannot register /{args.cluster}/{args.name}: member already exists"
            )
        except (
            KazooException,
            KazooTimeoutError,
            UnicodeError,
            ValueError,
            OSError,
        ) as error:
            detail = str(error) or error.__class__.__name__
            parser.error(f"cannot register /{args.cluster}/{args.name}: {detail}")
        return

    parser.error(f"{args.command} is not implemented yet")
