# zkdemo

`zkdemo` is a small Python command-line tool for exercising ZooKeeper-backed
service discovery. The `zktest` command runs server and client examples against
either the local development ZooKeeper or a configured production ensemble. It
also provides simple commands for inspecting znodes without opening an
interactive ZooKeeper shell.

This repository is a development and demonstration harness. The local
ZooKeeper scripts intentionally start one standalone participant, not a
production quorum.

## Why this is useful

The pattern demonstrated here is useful when a service needs to publish its
own readiness and endpoint without a separate registry client or DNS-based
polling loop:

- A server checks that it is ready, then registers its endpoint below its
  cluster's ZooKeeper path. The registration is ephemeral, so it disappears
  when the server exits or its ZooKeeper session expires.
- A client watches the cluster and its members. On a change it waits for a
  random delay, which coalesces bursts and avoids a thundering herd of clients
  rebuilding at once.
- The client writes a complete endpoint list to a same-directory temporary
  file and atomically renames it into place. Readers see either the previous
  complete file or the new complete file, never a partial render.
- If ZooKeeper is unavailable, the client retains the last complete file. When
  the session and cluster return, it notices the current membership, refreshes
  its watches, and converges to a new file. Servers likewise recreate their
  ephemeral registration after session recovery.
- Ensemble configuration is discovered from ZooKeeper and followed when client
  addresses change. Membership updates are watch-driven rather than DNS- or
  polling-driven, so changes become visible promptly while the client keeps
  operating through reconnects.

To turn this into a production service, imagine extending `zktest` into a
server-readiness script that runs alongside MySQL. When the script finds that
the server is ready to serve—its port is open, replication is running, and
replication delay is within the accepted limit—it registers the endpoint. When
the server becomes unfit to serve, because replication is no longer keeping up
or the port is closed, it deregisters.

Clients notice changes to the available server pool as quickly as they choose,
with at most the configured `--delay` jitter while ZooKeeper is reachable.
There are no DNS propagation delays. A client library can then randomly select
an endpoint from the rendered file and connect to a viable server in the pool.

## Download and install

Install Python 3.14 or newer, [uv](https://docs.astral.sh/uv/), and Apache
ZooKeeper. On macOS, the dependencies can be installed with Homebrew:

```console
brew install uv zookeeper
```

Download the repository and enter its directory:

```console
git clone https://github.com/isotopp/zkdemo.git
cd zkdemo
```

Install the project and its development dependencies:

```console
uv sync
```

`uv sync` creates the project environment and installs the `zktest` command,
including its `rich` output dependency and the development tools used by the
test suite.

## Initial setup

Start the local single-instance ZooKeeper:

```console
scripts/start-zookeeper.sh
```

The script finds `zkServer` or `zkServer.sh` on `PATH`, or uses
`$ZOOKEEPER_HOME/bin/zkServer.sh`. It creates the ignored `.zookeeper/`
directory with generated configuration, logs, PID state, and local data. The
server listens on `127.0.0.1:2181` and does not form a quorum.

Verify that the server is reachable:

```console
uv run zktest lr /
```

For repeated commands, copy [`sample.env`](sample.env) to `.env` and uncomment
the defaults you want. The process environment and explicit command-line
options take precedence over values from that file. To stop the local server:

```console
scripts/stop-zookeeper.sh
```

Try a minimal registration and endpoint render:

```console
uv run zktest server --cluster demo --name demo01 --endpoint 10.20.0.11:5432
uv run zktest client --cluster demo --file .zookeeper/demo.endpoints
```

The server command stays in the foreground while its ephemeral registration is
alive. Run it and the client in separate terminals; then inspect the rendered
file with:

```console
cat .zookeeper/demo.endpoints
```

## Interactive walkthrough

[`DEMO.md`](DEMO.md) contains a complete multi-terminal walkthrough covering
registration, endpoint rendering, duplicate and invalid input, atomic file
replacement, ZooKeeper shutdown and recovery, and the distinction between the
standalone development instance and a production ensemble.

## Development checks

```console
uv run ruff check --fix
uv run ruff format
uv run pytest
uv run ty check
```
