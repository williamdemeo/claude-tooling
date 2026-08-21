---
name: driving-agda-mcp
description: Drive the agda-mcp server over its real JSON-RPC stdio transport and read back exactly what an MCP client would see — tool descriptions from tools/list, and the full response body of check_file / get_diagnostics / get_goal / fill_hole. Use whenever working on agda-mcp and you need to verify a response shape, a tool description, or an error payload rather than infer it from Haskell; also covers finding out what a nix devShell writes into the caller's directory.
---

# Driving agda-mcp end to end

Unit tests assert handler values; they do not show what an agent actually
receives.  Response fields are double-encoded (the tool result's `text` is
itself a JSON document), descriptions are assembled from concatenated Haskell
fragments, and failures arrive as `isError` content rather than as JSON-RPC
errors — so "read the code" is not a substitute for driving the binary.

Everything below runs inside `nix develop .#backend`, from the repo root.

## Build and resolve the binary

```sh
BIN=$(cd agda-mcp && cabal list-bin exe:agda-mcp)
```

`cabal list-bin` also builds nothing — run `cabal build exe:agda-mcp` in
`agda-mcp/` first (or `BACKEND_USE_NIX=0 make agda-mcp-build` from the repo
root, the `BACKEND_USE_NIX=0` being what avoids nesting a second Nix shell when
you are already in one).

## Call a tool and unwrap the response

Requests are newline-delimited JSON on stdin.  The server logs its banner to
stderr, so drop it; take the last line for the last response.  The payload is
JSON **inside** a JSON string, hence two `json.loads`:

```sh
printf '%s\n' \
 '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}' \
 '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"check_file","arguments":{"filePath":"agda-dojang/data/fixtures/Fixture01.agda"}}}' \
 | "$BIN" --agda-flags "-i agda-dojang/agda --library-file=agda/libraries -l agda-dojang -l standard-library" 2>/dev/null \
 | tail -1 \
 | python3 -c "import sys,json; r=json.load(sys.stdin); print(json.dumps(json.loads(r['result']['content'][0]['text']), indent=2))"
```

Notes that cost time to rediscover.

+  `initialize` first is optional for `tools/call` but matches what a client
   does; keep it so a transport regression surfaces here rather than later.
+  The `--agda-flags` string above is the one `make agda-mcp-serve` and the
   shipped `.mcp.json` use, so a result obtained this way is the result a client
   gets.  Paths in it are relative to the server's cwd, which is the repo root.
+  A failing call has `result.isError == true`; its `content[0].text` is either
   prose or a JSON object (timeouts and root mismatches serialize as objects).
   Branch on the leading character rather than assuming.
+  A first call against a cold library builds `.agdai` interfaces and can take
   minutes; raise `--timeout` before blaming the server.

## Reproduce a bug a client in ANOTHER project hits

The server's working directory is not its client's — `scripts/run-server.sh` `cd`s
to this repository before exec — so any  defect about path resolution only
reproduces when you drive it from somewhere else. Two ways, in increasing fidelity.

**Binary directly, from the server's cwd.**  Equivalent to the above, but
send the relative path a client in *its own* project would send:

```sh
'{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"check_file",
  "arguments":{"filePath":"src/Whatever/Module.agda"}}}'
```

**Through `run-server.sh`, from the client's project.**  The real thing: `cd`
into a scratch project (`git init`, a `*.agda-lib`, one module at a hierarchical
path) and pipe the request into `"$REPO/scripts/run-server.sh" --agda-flags …`.
The script's own fd juggling keeps stdout clean, so `| tail -1` is the response
and its stderr is the server log — grep that for `uncaught exception` to tell a
handled refusal from a crash.

Gotcha worth the five minutes it costs: **`nix develop … --command bash -c '…'`
prints the shellHook banner on the *outer* stdout**, so a pipeline that ends in
`| tail -1 | python3 -c …` parses banner text and dies on "Expecting value".
Have the inner script write its last line to a file and read the file after the
shell exits:

```sh
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
env -u LD_LIBRARY_PATH nix develop "$REPO#backend" --command bash -c \
  "OUTFILE='$TMP/out.json' ERRLOG='$TMP/err.txt' '$SCRATCH/drive.sh' …" >/dev/null 2>&1 &&
  python3 show.py < "$TMP/out.json"
```

`run-server.sh` does not have this problem — it saves real stdout on fd 3
before the hook runs, which is exactly what the fd juggling in its header is for.

## Read the tool descriptions a client sees

Descriptions are what an agent picks tools by, and they are built by
concatenating fragments in `AgdaMCP.Server`, so proofreading the Haskell is not
the same as proofreading the result:

```sh
printf '%s\n' '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}' \
 | "$BIN" 2>/dev/null \
 | python3 -c "
import sys,json,textwrap
for t in json.load(sys.stdin)['result']['tools']:
    print('===', t['name']); print(textwrap.fill(t['description'], 96)); print()
"
```

No `--agda-flags` are needed for `tools/list`.  Add `--corpus
agda-mcp/test/resources/corpus-fixture.jsonl` to see the three search tools,
which are registered only when a corpus is loaded.

## The Makefile lanes

```sh
BACKEND_USE_NIX=0 make agda-mcp-test    # cabal test: unit + corpus + Agda integration
BACKEND_USE_NIX=0 make agda-mcp-smoke   # build + a JSON-RPC round-trip through the real binary
```

Run both before pushing.  `agda-mcp-smoke` greps `tools/list` output for tool
*names*, so it passes through a description rewrite — it is a transport check,
not a contract check.

## What a devShell writes into the caller's directory

`nix develop` runs the shellHook in the **caller's** working directory, so a
hook that derives paths from `git rev-parse --show-toplevel` answers about
whatever checkout you were standing in.  To find out what a shell leaves behind
somewhere it should not, use an empty git repository as the canary:

```sh
mkdir /tmp/canary && cd /tmp/canary && git init -q
nix develop /path/to/agda-native-air#backend --command bash -c 'echo "$AGDA_DIR"'
ls -a /tmp/canary          # anything beyond .git was written by the hook
```

`docs/agda-mcp-environment.md` records the inventory this technique produced and
the anchoring fix (`AGDA_NATIVE_AIR_ROOT`); re-run the canary after any
shellHook change.

## Driving against a client project (the fls pattern)

The binary needs no wrapper for this — give it the client anchors directly and
drive the same pipeline as above:

```sh
"$BIN" --cwd /home/williamdemeo/git/IO/fls/master \
       --agda-bin /home/williamdemeo/.cache/fls/agda-root/bin/agda \
       --agda-flags "-i $PWD/agda-dojang/agda" --timeout 900
```

+  `--cwd` is what makes the client's modules resolve: Agda finds a project's
   `.agda-lib` by walking up from the **process cwd**, not from the checked
   file, and it is also what routes `.agdai` interfaces into the client's own
   `_build/`.
+  To exercise `get_goal` without writing into the client tree, put a probe
   module with one hole in any scratch directory, importing the client's
   modules (e.g. `open import Ledger.Prelude`); with `--cwd` set they resolve,
   and the probe's `.agdai` lands beside the probe.
+  `~/.cache/fls/agda-root` is a gc-rooted symlink to fls's wrapped agda;
   refresh it after fls's `flake.lock` moves with
   `nix build ~/git/IO/fls/master#fls-agdaWithPackages -o ~/.cache/fls/agda-root`.

## Gotcha: a flag-less server cannot check anything under the flake

Driving the binary with no `--agda-flags` does not give you a bare Agda: the
checking `agda` is the flake's wrapper, whose defaults ask for `agda-dojang`
while its own nix-store registry knows only `standard-library`, so EVERY
check answers a `LibraryError` — even for a file importing only builtins
(verified while building the #119 harness).  Always pass the committed flag
set (`-i agda-dojang/agda --library-file=agda/libraries -l agda-dojang -l
standard-library`); it is correct for builtin-only files too.

## A reference client lives in the repo

`struxdriver.search.McpClient` (+ `Wire`, `Oracle`) is a working Scala client
for this transport — spawn, initialize, newline framing, double-decode,
`isError` branching, per-call timing — with its decoders pinned against
responses captured verbatim from the live server
(`strux-driver/src/test/resources/search/wire-*.json`).  The fastest live
round-trip through it: `make proof-search-it` (BACKEND_USE_NIX=0 inside the
shell), which runs the two-obligation regression end to end.

## Gotcha: `nix` from inside a session shell

A local session inherits an `LD_LIBRARY_PATH` that breaks the `nix` binary.
Prefix nested invocations with `env -u LD_LIBRARY_PATH`.
