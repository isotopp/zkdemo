# ZooKeeper inspection CLI user stories

## Load command defaults from a dotenv file

As a developer, I want `uv run zktest` to load shared connection and command
defaults from a dotenv file, so that I do not have to repeat the same
ZooKeeper and cluster options on every invocation.

Acceptance criteria:

- Before parsing command defaults, `zktest` looks for configuration files in
  this exact order and loads only the first one that exists:
  1. `.env` in the current working directory
  2. `$HOME/.zktest.ini`
  3. `/etc/zktest.ini`
- All three files use dotenv syntax (`NAME=VALUE`, optional quoting, blank
  lines, and lines beginning with `#` as comments); the `.ini` suffix does not
  imply INI sections.
- The supported settings are `ZKTEST_HOSTS`, `ZKTEST_CLUSTER`, `ZKTEST_DELAY`,
  `ZKTEST_NODE_NAME`, and `ZKTEST_FILE`. `ZKTEST_TIMEOUT`, which controls the
  ZooKeeper connection timeout, may also be supplied by the file.
- Values already present in the process environment are not overwritten by
  values from a file. An explicit command-line option takes precedence over
  the process environment or loaded file, which in turn takes precedence over
  a built-in default.
- `ZKTEST_HOSTS` is a comma-separated list of ZooKeeper client endpoints,
  such as `zk1.example:2181,zk2.example:2181,zk3.example:2181`. These endpoints
  are bootstrap hints: the client tries them until it establishes a session,
  then replaces them with the ensemble's current advertised client endpoint
  set from `/zookeeper/config`.
- After the initial discovery, `zktest` watches `/zookeeper/config`. When the
  ensemble configuration changes, it synchronizes and reads the configuration
  again, validates a non-empty client endpoint set, and updates the addresses
  Kazoo will use for subsequent reconnects. A discovered set is scoped to the
  running process and is not written back to a dotenv file.
- Ensemble discovery requires ZooKeeper 3.5 or newer and a configuration that
  advertises a usable client endpoint for every participant and observer. If a
  hint accepts the connection but the current ensemble endpoint set cannot be
  read or is malformed or incomplete, the command exits non-zero with a clear
  diagnostic instead of silently continuing with stale hints.
- The built-in ZooKeeper bootstrap hint remains `127.0.0.1:2181`; the built-in
  delay remains `3.0` seconds. Cluster, node name, and output file have no
  built-in defaults.
- ZooKeeper hosts apply to every subcommand. Cluster applies to `server` and
  `client`, node name applies to `server`, and delay and output file apply to
  `client`. The server endpoint has no configured or built-in default and must
  always be supplied as `--endpoint`. When any other required value has neither
  a command-line value nor a configured default, argument parsing fails with a
  clear diagnostic.
- Configured values receive the same validation as their command-line
  equivalents. Every host entry must contain a valid hostname or bracketed IP
  address and an integer port from 1 through 65535; empty entries are rejected.
  Delay and timeout must be finite non-negative numbers, and configured cluster
  and node names must be valid single ZooKeeper path components.
- Finding no configuration file is not an error. If the selected file exists
  but cannot be read, contains invalid dotenv syntax, or contains an invalid
  value used by the command, `zktest` exits non-zero with a diagnostic that
  names the file and setting.
- The repository contains a fully commented `sample.env` documenting every
  supported setting, the lookup order, and the precedence rules. Users can
  copy it to one of the lookup locations and uncomment the settings they need.

## Browse the complete znode tree

As a developer, I want to run `uv run zktest lslr` to see the complete znode
structure of the running local ZooKeeper instance, so that I can understand its
current state without opening an interactive ZooKeeper shell.

Acceptance criteria:

- The command connects to the local server at `127.0.0.1:2181` by default.
- It starts at `/` and prints every reachable znode path in a deterministic,
  depth-first order.
- It displays every standard ZooKeeper `Stat` metadata field for each znode,
  including transaction IDs, timestamps, versions, data length, child count,
  and ephemeral owner.
- It accepts `--format text|json`, defaulting to `text`. Text output is a
  color-free, headered table rendered by `rich`; JSON output is a single valid
  JSON document with no table or diagnostic text on standard output.
- It exits with a clear non-zero error when the server is unavailable.

## List one znode's children

As a developer, I want to run `uv run zktest lr <znode-path>` to list one
znode and its immediate children, so that I can inspect a focused part of the
ZooKeeper tree.

Acceptance criteria:

- `<znode-path>` is an absolute ZooKeeper path, such as `/brokers/ids`.
- The output identifies the requested znode and lists only its direct children
  in a deterministic order.
- It accepts `--format text|json`, defaulting to `text`. Text output is a
  color-free, headered table rendered by `rich`; JSON output is a single valid
  JSON document with no table or diagnostic text on standard output.
- The command reports a missing znode clearly and exits non-zero.

## Read znode data

As a developer, I want to run `uv run zktest cat <znode-path>` to print the
data stored in one znode, so that I can inspect configuration and state values
without using the interactive ZooKeeper client.

Acceptance criteria:

- `<znode-path>` is an absolute ZooKeeper path.
- The znode's raw data bytes are written to standard output without extra
  formatting or content protection.
- Empty znode data succeeds and produces no data output.
- A missing znode or unavailable server produces a clear non-zero error.

## Register an available server ephemerally

As a server process, I want to run
`uv run zktest server --cluster <cluster> --name <name> --endpoint <endpoint>`
when I come online, so that clients can discover my endpoint through ZooKeeper
while my process is running.

For example:

```console
uv run zktest server --cluster bpdb --name bpdb17 --endpoint 10.1.1.1:3306
```

Acceptance criteria:

- The command creates the cluster znode, `/bpdb` in the example, when it does
  not already exist. It uses an atomic create and treats an “already exists”
  result as success only for this persistent parent znode.
- It creates `/bpdb/bpdb17` as an ephemeral znode, with `10.1.1.1:3306` as
  its UTF-8 data.
- The command remains in the foreground while its ZooKeeper session is live.
  On process exit, ZooKeeper automatically removes the ephemeral member znode.
- After a confirmed ZooKeeper session expiration, the command establishes a new
  session and re-creates its own ephemeral member znode. A temporary
  connection interruption must not cause a duplicate registration attempt
  while the original session can still recover.
- It fails clearly if the member znode already exists; it must not silently
  overwrite an endpoint or terminate the existing server registration.
- Cluster and member names must be valid single ZooKeeper path components and
  must not contain carriage-return or newline characters.
- The endpoint is opaque application data. The command stores it exactly as
  supplied and performs no endpoint syntax validation, except that it rejects
  carriage-return and newline characters to preserve one output line per
  member.
- A missing ZooKeeper server or a ZooKeeper connection failure produces a clear
  non-zero error.

## Render a cluster endpoint file after changes

As a client process, I want to run
`uv run zktest client --cluster <cluster> --file <outfile> [--delay <float-secs>]`
so that a local file is updated with every endpoint currently registered in a
cluster after the membership changes settle.

For a cluster containing `bpdb17` at `10.1.1.1:3306`, the output file contains:

```text
10.1.1.1:3306 # bpdb17
```

Acceptance criteria:

- The command validates that `--delay` is a finite float greater than or equal
  to zero. Default is 3.0.
- A missing cluster is a fatal error with a clear diagnostic; the command does
  not wait for that cluster to be created.
- It creates the full parent path for `--file`, then immediately renders the
  current cluster membership before waiting for ZooKeeper events.
- It watches the cluster znode for child additions and removals, and watches
  each current member for data changes, re-registering all ZooKeeper watches
  after every notification.
- On a change, it waits for a randomly chosen interval from zero through the
  configured maximum delay. Multiple changes during that period are coalesced
  into one render after the final change (debouncing).
- It guarantees eventual convergence to the current cluster state, not an
  output record of every transient change. It re-arms its watches before each
  jitter delay and performs a complete rescan after reconnecting.
- The render reads every current direct child of the cluster, fetches its data,
  sorts output by member name, and writes one `<endpoint> # <name>` line per
  member.
- Each render writes to `<outfile>.<pid>` in the same directory and atomically
  replaces `<outfile>` with `rename(2)`, so readers never observe a partial
  list. An existing output file is a valid replacement target.
- An empty cluster produces an empty output file.
- The command never deletes the output file or otherwise cleans it up.
- A target file has one client writer. The PID suffix avoids temporary-file
  collisions, but concurrent writers would still race to replace the target.
- The command remains running and reconnects/re-registers watches after a
  transient ZooKeeper connection loss.
- If the cluster is deleted after startup, the command exits with a clear
  diagnostic and leaves its most recently rendered output file in place.
- Malformed member data is reported clearly.
