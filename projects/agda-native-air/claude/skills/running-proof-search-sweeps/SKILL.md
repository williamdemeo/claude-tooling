---
name: running-proof-search-sweeps
description: Run agda-native-air's proof-search loop sweeps (proof-search-loop over the M1-5 suite or a stratum) when they take longer than a few minutes — from a snapshot of strux-driver's compiled classes with plain `java -cp`, launched detached with setsid so a harness kill or an sbt recompile cannot take them down, watched through a log monitor, and verified against a published run's report field for field.  Use for any knob experiment, scorer sweep, or baseline reproduction of the loop; the offline recall instrument (`make proof-search-recall`) does not need it.
---

# Running proof-search sweeps that outlive a turn

A 43-obligation sweep is 40 to 60 minutes of serial `agda`; a wholesale-stratum
knob sweep is about 35.  Two things killed sweeps in 2026-09: the harness stopped
a `run_in_background` driver "because the system is running low on memory" with
46 GB free, and recompiling `strux-driver` would have rewritten
`target/scala-2.13/classes` under a running JVM.  Everything below runs inside
`nix develop .#backend` from the worktree root, with the server built once
(`cd agda-mcp && cabal build -v0 exe:agda-mcp && cabal list-bin exe:agda-mcp`).
`$S` is the session scratchpad.

## 1.  Freeze the classes and the classpath

```sh
cd strux-driver && sbt -Dsbt.supershell=false "Test/compile" "export Runtime/fullClasspath" \
  | grep -E '^[^\[].*\.jar' | tail -1 > "$S/classpath.txt" && cd ..
rm -rf "$S/classes-snap" && cp -r strux-driver/target/scala-2.13/classes "$S/classes-snap"
sed "s|^[^:]*/strux-driver/target/scala-2.13/classes|$S/classes-snap|" "$S/classpath.txt" > "$S/classpath-snap.txt"
```

Re-snapshot after the last code change and before launching; the sweep then
never sees a recompile.

## 2.  A serial driver, one line per run

Write `$S/sweeps.sh` (a bash file, `set -u`) that defines one function and calls
it once per run; the body of the function is the exact `ProofSearchLoop`
invocation the Make target `proof-search-loop` would issue:

```sh
ROOT=/path/to/worktree
CP=$(cat "$S/classpath-snap.txt")
BIN=$ROOT/agda-mcp/dist-newstyle/build/x86_64-linux/ghc-9.10.3/agda-mcp-0.2.0/x/agda-mcp/build/agda-mcp/agda-mcp
run() {  # run-id retrieve-k budget exclude scorer ids
  echo ">>> $(date -u +%FT%TZ) start $1"
  java -Xmx3g -cp "$CP" struxdriver.search.ProofSearchLoop --index $ROOT/data/benchmarks/benchmark-index.jsonl $6 \
    --out-dir $ROOT/data/benchmarks/reports/proof-search --run-id $1 --server-bin "$BIN" --project-root $ROOT \
    --server-timeout 600 --beam 4 --max-depth 6 --probe-budget $3 --dedup script --peek on --proposer retrieval \
    --corpus $ROOT/data/corpora/agda-algebras/v0.1/corpus.jsonl --retrieve-k $2 --exclude-target $4 --expand-deps off \
    --scorer $5 > "$S/$1.log" 2>&1
  echo ">>> $(date -u +%FT%TZ) end   $1 exit=$?"
}
run k19-idf-unfold-a-exclude-on  8 60 on  idf-unfold --all
run k19-idf-unfold-b-exclude-off 8 60 off idf-unfold --all
echo ">>> all sweeps done"
```

For a stratum, pass `--ids "$(jq -r 'select(.tags|index("stratum:wholesale")) |
.id' data/benchmarks/benchmark-index.jsonl | paste -sd,)"` in place of `--all`.
The knobs shown are the published ones; change one per run and name the run
after it (`k19-wholesale-k16`).  A scorer that unfolds definitions loads the
224 MB corpus once at start; 3 GB of heap is plenty.

## 3.  Launch detached, watch the log

```sh
setsid nohup bash "$S/sweeps.sh" >> "$S/sweeps.log" 2>&1 < /dev/null & disown
```

Never `run_in_background` the driver itself.  Watch it with a Monitor whose
command exits on the final line, so each run's end is one notification:

```sh
tail -n +1 -f "$S/sweeps.log" | grep --line-buffered -E '>>> .* (end|done)' \
  | while IFS= read -r line; do echo "$line"; case "$line" in *"all sweeps done"*) exit 0;; esac; done
```

Keep the machine quiet while a headline sweep runs; probe counts and solves are
deterministic, wall clocks are not, and every published table says which
column is comparable.

## 4.  Verify against a published run before quoting anything

Compare the frozen stdlib rows field for field with the reference report (a
`p2s2-*` report in the `p2s2-sweeps` worktree), then read solves and the
exclusion ledger:

```sh
R=data/benchmarks/reports/proof-search/RUN_ID/report.json; P=/path/to/reference/report.json
jq -r '.outcomes[] | select(.benchmarkId|startswith("stdlib-")) | [.benchmarkId, .searchStatus, .probes, (.script|join(" ; "))] | @tsv' "$R" | sort > /tmp/new.tsv
jq -r '.outcomes[] | select(.benchmarkId|startswith("stdlib-")) | [.benchmarkId, .searchStatus, .probes, (.script|join(" ; "))] | @tsv' "$P" | sort > /tmp/ref.tsv
diff /tmp/new.tsv /tmp/ref.tsv && echo "stdlib rows identical"
jq '[.outcomes[] | select(.searchStatus=="anomaly")] | length' "$R"          # must be 0
jq -r '.outcomes[] | select(.solved) | "\(.benchmarkId): \(.script|join(" ; "))  (\(.probes) probes)"' "$R"
jq -r '.outcomes[] | select((.retrieval.excluded|length) > 0) | "\(.benchmarkId): \(.retrieval.excluded|join(", "))"' "$R"
```

An exclusion firing on a `target:` lemma means the row was gamed, not ranked;
read the ledger before quoting a number.  The ledger's `hits` and `inScope` are
sums over every goal a search visited, not the root pool's size; the offline
instrument reports the root pool.
