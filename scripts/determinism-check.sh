#!/usr/bin/env bash
# Byte-identical determinism gate (design §9.6; §11 M2 row — "determinism tests in CI").
#
# Two checks, two builds (not three). Build the whole demo tree twice in two independent
# `uv run` processes (so a fresh, potentially different, hash seed lands on each build)
# and diff every byte on disk. Then reuse one of those trees against the *committed*
# `demos/*/out` — a stale committed output (someone changed the kernel or an export and
# forgot to re-run the demos) fails here by name, not as an unexplained line inside a
# `diff -r`. A third `run_all` would only re-prove what the first tree already is.
#
# Every timestamp in every demo is a fixed constant (`NOW`), and `kernel.render.
# build_package` stores a package's output path as a basename only (ruling R5), so
# there is nothing legitimate to exclude from either diff. If a real difference shows up
# that is not non-determinism — an absolute path inside an object, a temp directory name
# baked into a report — that is a kernel defect (see ruling R5), not a case for
# `--exclude`. Do not add one.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"

a=$(mktemp -d)
b=$(mktemp -d)
trap 'command rm -rf "$a" "$b"' EXIT

echo "== building two independent trees =="
uv run python -m demos.run_all --out "$a"
uv run python -m demos.run_all --out "$b"

echo "== diffing the two independent builds =="
independent_diff=$(diff -r "$a" "$b" || true)
if [ -n "$independent_diff" ]; then
  echo "DETERMINISM FAILED — two independent builds differ (first differences below):"
  echo "$independent_diff" | head -n 20
  exit 1
fi
echo "DETERMINISM OK — two independent builds are byte-identical."

echo "== checking the committed demos/*/out is not stale =="
# Reuse tree `$a`: it already matched `$b` across processes, so it is a valid fresh
# baseline for the committed-output comparison without a third full rebuild.
fail=0
for dir in demos/*/; do
  name=$(basename "$dir")
  fresh="$a/demos/$name/out"
  stale="demos/$name/out"
  if [ ! -d "$stale" ]; then
    continue    # nothing committed for this demo yet — nothing to compare
  fi
  if [ ! -d "$fresh" ]; then
    echo "STALE — $name: demos/$name/out is committed, but run_all skipped this demo" \
         "(its module is absent — see the printed reason above)"
    fail=1
    continue
  fi
  stale_diff=$(diff -r "$fresh" "$stale" || true)
  if [ -n "$stale_diff" ]; then
    echo "STALE — $name: committed demos/$name/out does not match a fresh run. Re-run:"
    echo "  uv run python -m demos.$name.run"
    echo "$stale_diff" | head -n 20
    fail=1
  fi
done

if [ "$fail" -ne 0 ]; then
  echo "DETERMINISM FAILED — committed output is stale for at least one demo."
  exit 1
fi
echo "COMMITTED OUTPUT OK — matches a fresh run for every demo with committed output."
