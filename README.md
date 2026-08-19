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

## Development checks

```console
uv run ruff check --fix
uv run ruff format
uv run pytest
uv run ty check
```
