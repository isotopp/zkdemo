# zkdemo

A Python project for running and exercising a local, single-instance development
ZooKeeper. The ZooKeeper implementation will be added in follow-up changes.

## Setup

Install the project and its development tools:

```console
uv sync
```

The command-line surface is already stubbed out:

```console
uv run zktest client
uv run zktest server
```

## Local ZooKeeper

Install ZooKeeper with Homebrew, point `ZOOKEEPER_HOME` at an unpacked ZooKeeper
distribution, or put `zkServer`/`zkServer.sh` on `PATH`. Start and stop the
standalone development instance with:

```console
scripts/start-zookeeper.sh
scripts/stop-zookeeper.sh
```

The scripts create `.zookeeper/` in the project root. This ignored runtime
directory contains the generated configuration, logs, PID state, and the local
`data/` directory. The instance listens on the standard client port, `2181`, and
does not configure a quorum.

## Development checks

```console
uv run ruff check --fix
uv run ruff format
uv run pytest
uv run ty check
```
