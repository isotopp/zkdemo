"""Command-line entry point for the ZooKeeper development harness."""

import argparse
from collections.abc import Sequence

from rich.console import Console

console = Console(color_system=None)


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
    parser.error(f"{args.command} is not implemented yet")
