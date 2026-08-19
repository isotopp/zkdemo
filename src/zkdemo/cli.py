"""Command-line entry point for the ZooKeeper development harness."""

import argparse
from collections.abc import Sequence


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""
    parser = argparse.ArgumentParser(
        prog="zktest",
        description="Run and exercise a local single-instance ZooKeeper.",
    )
    subcommands = parser.add_subparsers(dest="command", required=True)
    subcommands.add_parser("client", help="Talk to the development ZooKeeper")
    subcommands.add_parser("server", help="Run the development ZooKeeper")
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    """Run the selected command."""
    args = build_parser().parse_args(argv)

    if args.command == "client":
        print("ZooKeeper client stub")
    else:
        print("ZooKeeper server stub")
