# zktest interactive demo

This walkthrough uses several long-running commands at once to demonstrate
ephemeral server registration, client rendering, membership changes, error
handling, reconnection, and shutdown behavior.

The endpoint values are opaque demonstration data. Nothing needs to listen on
the example ports.

## Prepare the project and terminal session

From the project root, install the environment and start the local ZooKeeper:

```console
uv sync
scripts/start-zookeeper.sh
```

### What the local start and stop scripts do

The scripts run one standalone development ZooKeeper on `127.0.0.1:2181`.
They are intentionally not production service-management scripts.

`scripts/start-zookeeper.sh` finds `zkServer` or `zkServer.sh` on `PATH`, or
uses `$ZOOKEEPER_HOME/bin/zkServer.sh`. On its first run it creates:

```text
.zookeeper/
├── conf/zoo.cfg
├── data/
└── logs/
```

Set `ZKDEMO_RUNTIME_DIR` before running both scripts to use a different runtime
directory. The start script generates `zoo.cfg` only when it is absent, so
local edits survive later restarts.

`scripts/stop-zookeeper.sh` asks that same ZooKeeper installation to stop the
server. It does not remove the configuration, transaction data, snapshots,
logs, persistent znodes, or rendered endpoint files. A subsequent start uses
the retained data. Run start and stop with the same `ZOOKEEPER_HOME` and
`ZKDEMO_RUNTIME_DIR` values.

If startup reports that ZooKeeper cannot be found, either install it on `PATH`
or point at an unpacked distribution:

```console
export ZOOKEEPER_HOME=/path/to/apache-zookeeper
scripts/start-zookeeper.sh
```

Open a `tmux` session:

```console
tmux new-session -s zktest-demo
```

Create five windows or panes with `Ctrl-b c` or `Ctrl-b %`. Screen users can
instead run `screen -S zktest-demo` and create windows with `Ctrl-a c`. Run all
commands from the project root.

Use the panes as follows:

1. observer and control commands
2. server `demo01`
3. server `demo02`
4. server `demo03`
5. endpoint-file client

## Register three server nodes

Run one command in each server pane. Each command stays in the foreground and
owns one ephemeral znode.

Pane 2:

```console
uv run zktest server --cluster demo --name demo01 --endpoint 10.20.0.11:5432
```

Pane 3:

```console
uv run zktest server --cluster demo --name demo02 --endpoint 10.20.0.12:5432
```

Pane 4:

```console
uv run zktest server --cluster demo --name demo03 --endpoint 10.20.0.13:5432
```

In the control pane, inspect the cluster:

```console
uv run zktest lr /demo
uv run zktest cat /demo/demo02
```

The cluster should contain `demo01`, `demo02`, and `demo03`. The `cat` command
prints `10.20.0.12:5432` without adding a newline.

## Render and observe the endpoint file

In pane 5, start the client with a short maximum debounce delay:

```console
uv run zktest client --cluster demo --file .zookeeper/demo.endpoints --delay 0.5
```

The client stays in the foreground. In the control pane, inspect its initial
snapshot:

```console
cat .zookeeper/demo.endpoints
```

The file is sorted by node name:

```text
10.20.0.11:5432 # demo01
10.20.0.12:5432 # demo02
10.20.0.13:5432 # demo03
```

For a continuously refreshed display, use this loop in the control pane. Do
not use `tail -f`: the client atomically replaces the file, so `tail` may keep
following its old inode.

```console
while :; do
  clear
  date
  uv run zktest lr /demo || true
  printf '\nRendered endpoints:\n'
  if test -f .zookeeper/demo.endpoints; then
    cat .zookeeper/demo.endpoints
  else
    printf '(file not created yet)\n'
  fi
  sleep 1
done
```

Stop the loop with `Ctrl-c` before running later control commands.

## Exercise expected errors

These failures must not alter the existing cluster or endpoint file.

While the original `demo01` command is still running, try to register the same
name from the control pane:

```console
uv run zktest server --cluster demo --name demo01 --endpoint 192.0.2.1:9999
```

The command exits non-zero with `member already exists`. Confirm that the
original endpoint was not overwritten:

```console
uv run zktest cat /demo/demo01
```

Exercise input validation:

```console
uv run zktest server --cluster demo --name bad/name --endpoint 192.0.2.1:9999
uv run zktest server --cluster demo --name badname --endpoint $'bad\nendpoint'
uv run zktest client --cluster demo --file .zookeeper/demo.endpoints --delay -1
```

Each command exits non-zero. The invalid server commands create no member, and
the invalid client delay does not start another writer.

A client cannot start for a missing cluster and must preserve an existing
target file:

```console
printf 'sentinel\n' >.zookeeper/missing.endpoints
uv run zktest client --cluster demo-missing --file .zookeeper/missing.endpoints
cat .zookeeper/missing.endpoints
```

The client exits non-zero and the last command still prints `sentinel`.

## Remove and restart a server node

In the `demo02` pane, press `Ctrl-c`. A clean server exit closes its ZooKeeper
session, so `/demo/demo02` disappears. Within the configured debounce delay,
the client rewrites the file with only `demo01` and `demo03`:

```text
10.20.0.11:5432 # demo01
10.20.0.13:5432 # demo03
```

Restart pane 3 with a changed endpoint:

```console
uv run zktest server --cluster demo --name demo02 --endpoint 10.20.0.22:5432
```

The registration now succeeds because the old ephemeral node is gone. The
client adds the restarted member and renders its new endpoint:

```text
10.20.0.11:5432 # demo01
10.20.0.22:5432 # demo02
10.20.0.13:5432 # demo03
```

## Stop and restart the client

Press `Ctrl-c` in the client pane. The client never owns or removes the target,
so `.zookeeper/demo.endpoints` remains with its last complete snapshot.

While the client is stopped, press `Ctrl-c` in the `demo03` pane. The rendered
file is now deliberately stale because no client is running. Confirm that it
still exists and still mentions `demo03`:

```console
cat .zookeeper/demo.endpoints
```

Restart the client in pane 5:

```console
uv run zktest client --cluster demo --file .zookeeper/demo.endpoints --delay 0.5
```

At startup it performs a complete snapshot immediately. The refreshed file now
contains only `demo01` and `demo02`.

## Exercise ZooKeeper shutdown and recovery

Leave the `demo01`, restarted `demo02`, and client commands running. In the
control pane, stop ZooKeeper:

```console
scripts/stop-zookeeper.sh
```

The long-running commands should wait for ZooKeeper rather than deleting the
last rendered endpoint file. Confirm that the file remains readable:

```console
cat .zookeeper/demo.endpoints
```

Wait at least 12 seconds so the default 10-second ZooKeeper sessions can expire,
then restart ZooKeeper:

```console
scripts/start-zookeeper.sh
```

The server commands establish new sessions and recreate their own ephemeral
nodes. The client reconnects, performs a complete rescan, reinstalls its
watches, and converges the endpoint file. Verify both views:

```console
uv run zktest lr /demo
cat .zookeeper/demo.endpoints
```

This outage is intentionally different from restarting one server process: it
exercises session expiration and recovery for every long-running command.

## Clean shutdown

For an orderly final shutdown:

1. Press `Ctrl-c` in the client pane. Its rendered file remains in place.
2. Press `Ctrl-c` in the `demo01` and `demo02` panes. Their ephemeral nodes are
   removed; the persistent `/demo` cluster parent remains.
3. Optionally inspect the empty cluster and retained file:

   ```console
   uv run zktest lr /demo
   cat .zookeeper/demo.endpoints
   ```

   The file is the client's last snapshot and is not emptied after its writer
   has stopped.
4. Stop the local ZooKeeper:

   ```console
   scripts/stop-zookeeper.sh
   ```

5. Leave the multiplexer with `exit` in each pane, `tmux kill-session -t
   zktest-demo`, or the corresponding Screen commands.

The shutdown script stops ZooKeeper but intentionally preserves its local data
under `.zookeeper/`. A later start therefore retains persistent znodes such as
the empty `/demo` parent. The rendered endpoint file is also deliberately left
for its consumer or operator to remove when no longer needed.

## From the demo to a three-node production ensemble

Do not deploy `scripts/start-zookeeper.sh` independently on three machines. It
creates three unrelated standalone databases, not one ensemble. A production
ensemble needs a shared membership definition and a unique server ID on each
host. Three voting members tolerate the loss of one member; two available
members are required for a quorum.

For example, install the same ZooKeeper release on `zk1.example`,
`zk2.example`, and `zk3.example`. Give every host the same `zoo.cfg`:

```properties
tickTime=2000
dataDir=/var/lib/zookeeper
initLimit=10
syncLimit=5
standaloneEnabled=false
server.1=zk1.example:2888:3888:participant;zk1.example:2181
server.2=zk2.example:2888:3888:participant;zk2.example:2181
server.3=zk3.example:2888:3888:participant;zk3.example:2181
```

The ports in each `server.N` entry are, respectively, the quorum port, leader
election port, and client endpoint. Ensure the hosts can reach one another on
`2888` and `3888`, and allow approved clients to reach `2181`.

Create `/var/lib/zookeeper/myid` on each host with only its numeric ID:

```text
# zk1.example
1

# zk2.example
2

# zk3.example
3
```

Those comments identify the separate files; the actual `myid` file contains
only `1`, `2`, or `3`. Give the ZooKeeper service account ownership of its data
and log directories, then start ZooKeeper on all three hosts through the
operating system's service manager. Use systemd, an orchestrator, or another
supervisor that provides restart policy, resource limits, logging, and health
monitoring rather than backgrounding `zkServer.sh` from an interactive shell.

Point `zktest` at all three client endpoints as bootstrap hints:

```dotenv
ZKTEST_HOSTS=zk1.example:2181,zk2.example:2181,zk3.example:2181
```

The ensemble must advertise usable client addresses for discovery; wildcard
addresses such as `0.0.0.0` are not useful to remote clients. Use stable DNS
names that resolve from every client network.

Before treating the ensemble as production-ready, also define:

- TLS and client authentication, plus ACLs for application znodes.
- Separate durable data and transaction-log storage, capacity limits, JVM heap
  sizing that avoids swapping, and automated snapshot/log cleanup.
- Metrics, health checks, alerting, backups, restore tests, and clock sync.
- A tested upgrade and membership-change procedure. Dynamic reconfiguration is
  disabled by default in modern ZooKeeper and should be enabled only with
  appropriate authentication and ACL controls.

For maintenance, stop and restart only one ZooKeeper member at a time and wait
until it has rejoined and synchronized before touching the next. The remaining
two members keep the service available. A full ensemble shutdown necessarily
loses availability after the second member stops: quiesce writers, stop clients
or tolerate their reconnect loops, stop followers before the leader when
practical, and use the service manager's graceful stop action. Start all three
again and verify quorum health before resuming application traffic.

See the Apache ZooKeeper
[Administrator's Guide](https://zookeeper.apache.org/doc/current/zookeeperAdmin.html)
and [Dynamic Reconfiguration guide](https://zookeeper.apache.org/doc/current/zookeeperReconfig.html)
for the production parameters and operational constraints of the exact
ZooKeeper release being deployed.
