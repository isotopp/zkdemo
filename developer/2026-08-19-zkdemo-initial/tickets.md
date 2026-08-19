# Implementation tickets

These tickets implement [user-stories.md](user-stories.md) in dependency
order. Every ticket follows a vertical TDD loop: add one failing test through
the public `zktest` command, write the smallest implementation that makes it
pass, then repeat for the next listed behavior. Do not batch all tests before
implementation.

Tests exercise a real, isolated ZooKeeper instance wherever possible. A fake
is permitted only at the ZooKeeper or time/randomness boundary when a specific
connection state cannot be induced reliably. Tests must never mock zkdemo's own
modules.

## 1. Establish the CLI and ZooKeeper test foundation

Add the runtime dependencies `kazoo` and `rich`, and replace the placeholder
subcommand behavior with the command grammar required by the stories:
`lslr`, `lr`, `cat`, `server`, and `client`.

TDD slices:

1. RED: the public `zktest --help` output does not list the five commands.
   GREEN: expose their parsers and required arguments, while each unimplemented
   command fails clearly rather than pretending to succeed.
2. RED: an integration test cannot connect a command to an isolated local
   ZooKeeper server. GREEN: provide a pytest fixture that owns a server for a
   test run and exposes its connection address. It must leave no running server
   or persistent test znodes behind.
3. RED: formatting a table cannot produce stable plain text. GREEN: introduce
   a color-disabled `rich` console at the CLI boundary.

Done when `uv run pytest` can exercise `zktest` as a subprocess against the
fixture, and the normal default remains `127.0.0.1:2181` for users.

## 2. List one znode with `lr`

Implement `uv run zktest lr <znode-path> [--format text|json]`.

TDD slices:

1. RED: `zktest lr / --format json` cannot list direct root children. GREEN:
   connect, fetch the requested znode and its direct children, sort them, and
   emit one valid JSON document.
2. RED: `zktest lr / --format text` has no stable table. GREEN: render a
   color-free `rich` table with column headers.
3. RED: a missing or malformed absolute znode path has an unclear result.
   GREEN: reject it with a non-zero exit and a diagnostic on standard error.

Record the exact JSON object and text-table columns in the tests. Diagnostics
must never contaminate JSON standard output.

## 3. Read raw znode data with `cat`

Implement `uv run zktest cat <znode-path>`.

TDD slices:

1. RED: znode data cannot be retrieved through the CLI. GREEN: write its exact
   bytes to `stdout.buffer`, without a prefix or automatically added newline.
2. RED: an empty znode data value is ambiguous. GREEN: succeed with zero data
   bytes on standard output.
3. RED: a missing path or unavailable ZooKeeper server does not fail cleanly.
   GREEN: return non-zero with a clear standard-error diagnostic.

## 4. Recursively inspect the tree with `lslr`

Implement `uv run zktest lslr [--format text|json]`.

TDD slices:

1. RED: a nested test tree cannot be listed in deterministic depth-first path
   order. GREEN: walk from `/`, listing every reachable znode once.
2. RED: `Stat` information is absent or incomplete. GREEN: include every
   standard ZooKeeper `Stat` field in each JSON record and text-table row.
3. RED: text output is not a readable, stable table. GREEN: render the agreed
   `rich` table without terminal color.

Define and test the JSON document shape before extending it; it is a public
machine-readable interface.

## 5. Register one server ephemerally

Implement the foreground command:

```console
uv run zktest server --cluster bpdb --name bpdb17 --endpoint 10.1.1.1:3306
```

TDD slices:

1. RED: starting the command does not make `/bpdb/bpdb17` observable through
   `zktest cat`. GREEN: atomically create the persistent parent if absent, then
   create the child as an ephemeral znode containing the exact endpoint bytes.
2. RED: stopping the command leaves membership behind. GREEN: prove through
   public `lr`/`cat` commands that the member disappears when its process exits.
3. RED: a duplicate member, invalid znode component, or carriage-return/newline
   in a member name or endpoint has an unsafe result. GREEN: fail clearly,
   without changing any existing member.

The parent-create “already exists” result is success only for the cluster
parent. The member create is a single atomic operation and is always fatal on
an existing znode.

## 6. Make ephemeral registration connection-safe

Extend `zktest server` for ZooKeeper connection states.

TDD slices:

1. RED: a temporary disconnect causes a second create or exits the registration
   process. GREEN: retain the process and let the original session recover
   without a duplicate create.
2. RED: a confirmed session expiration leaves the process alive but unlisted.
   GREEN: establish a new session and re-create only its own ephemeral member.
3. RED: a new-session registration finds another member of the same name.
   GREEN: emit the fatal duplicate diagnostic; never overwrite or delete that
   other registration.

Use a real-server restart/expiration scenario when reliable; otherwise fake only
the Kazoo state boundary while continuing to verify the observable CLI outcome.

## 7. Render the initial client endpoint file

Implement the foreground command:

```console
uv run zktest client --cluster bpdb --file /path/to/bpdb.endpoints
```

TDD slices:

1. RED: an existing cluster does not immediately produce a file. GREEN: create
   missing parent directories, take a complete member snapshot, and render the
   sorted `<endpoint> # <name>` lines.
2. RED: an empty existing cluster leaves a stale or missing file. GREEN: render
   a valid empty file.
3. RED: a pre-existing output file cannot be replaced safely. GREEN: write to
   `<outfile>.<pid>` in the same directory and atomically replace the target
   with `rename(2)`.
4. RED: a missing cluster proceeds or removes an old file. GREEN: exit with a
   diagnostic while preserving any existing target file.

Treat endpoint data as opaque except for rejecting carriage return and newline
at registration time. Each target file has exactly one client writer; leftover
PID-suffixed files after a crash are acceptable.

## 8. Converge the client file after membership and data changes

Add child and data-watch behavior to `zktest client`.

TDD slices:

1. RED: adding or removing an ephemeral member does not update the running
   client file. GREEN: install and re-install the cluster child watch, then
   render the current full snapshot.
2. RED: changing a current member's data does not update the file. GREEN:
   install and re-install data watches for every current member.
3. RED: bursts of changes cause one render per event. GREEN: coalesce them and
   delay output by a random value in `[0, --delay]`, with a default maximum of
   `3.0` seconds.
4. RED: a reader can observe a partially rendered file. GREEN: assert from a
   concurrent reader that every observed target is either the old complete
   snapshot or the new complete snapshot.

The public guarantee is eventual convergence to the latest complete cluster
state, not a record of each transient membership state. Re-arm watches before
waiting for jitter.

## 9. Recover or fail predictably in the running client

Complete the long-running client's exceptional paths.

TDD slices:

1. RED: a temporary ZooKeeper connection loss leaves stale watches after it
   recovers. GREEN: reconnect, rescan the full cluster, and install fresh
   watches before the next output render.
2. RED: deletion of the cluster after startup leaves an unreported running
   client. GREEN: exit non-zero with a clear diagnostic and retain the most
   recently rendered target file.
3. RED: malformed member data gives an unclear outcome. GREEN: terminate with
   a diagnostic while leaving the last complete output file in place.

## 10. Complete the acceptance regression suite

Run each user-story example against the local developer ZooKeeper, including
the `bpdb`/`bpdb17` registration and endpoint-file scenario.

TDD slices:

1. RED: the documented examples are not executable end to end. GREEN: add
   concise integration tests that execute them unchanged.
2. RED: quality checks do not cover the final command surface. GREEN: run
   `uv run ruff check --fix`, `uv run ruff format`, `uv run pytest`, and
   `uv run ty check` successfully.

Refactor only after each ticket's tests are green. Keep ZooKeeper connection,
watch-reconciliation, and output-file complexity behind small interfaces; test
only the public command behavior and output artifacts.
