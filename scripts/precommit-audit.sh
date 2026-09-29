#!/usr/bin/env bash
# Pre-commit security audit for docket. Scans staged files and the staged diff
# for secrets. Exit 1 on any hit. Required before every commit (CLAUDE.md).
#
# Additive `--range <base>..<head>` mode (ruling R6, plan 06 Task 2): with no argument
# this script is byte-for-byte the staged-index audit it always was. `--range` swaps the
# diff source from the index to a commit range (checks 1-3), and check 4 reads
# `.gitignore` at <head> instead of the index — so CI can run this without ever staging
# anything, over `origin/main...HEAD` with `fetch-depth: 0`.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"

RANGE=""
if [ "${1:-}" = "--range" ]; then
  RANGE="${2:?--range requires <base>..<head>}"
  shift 2
fi

# The diff selector and the name-only selector (ruling R6): staged mode's is
# `git diff --cached` / `git diff --cached --name-only --diff-filter=ACMR`, exactly as
# before; range mode's is the same two shapes over `$RANGE` instead of the index. Arrays,
# not strings, so a selector expands as its own argument list with no word-splitting risk.
if [ -n "$RANGE" ]; then
  diff_sel=(git diff "$RANGE")
  name_only_sel=(git diff "$RANGE" --name-only --diff-filter=ACMR)
else
  diff_sel=(git diff --cached)
  name_only_sel=(git diff --cached --name-only --diff-filter=ACMR)
fi

workdir=$(mktemp -d)
trap 'command rm -rf "$workdir"' EXIT
hits="$workdir/hits.txt"
entropy="$workdir/entropy.txt"
ignorefile="$workdir/gitignore"

fail=0
staged_files=$("${name_only_sel[@]}" || true)

if [ -n "$RANGE" ]; then
  echo "== range $RANGE files =="
else
  echo "== staged files =="
fi
echo "${staged_files:-<none>}"

# 0. Refuse to bless an empty index: checks 1-3 pass vacuously when nothing is
#    staged, and a vacuous pass is not a clean audit. Keyed on whether the index
#    differs from HEAD at all, not on the scanned set — the scanned set is ACMR,
#    so a deletion-only commit is legitimately empty of content to scan and must
#    still be allowed through to check 4. Staged mode only: a range has no "index"
#    to be empty, so an empty range is a legitimate no-op push, not a vacuous pass
#    to refuse (ruling R6).
if [ -z "$RANGE" ]; then
  if git diff --cached --quiet; then
    echo "NOTHING STAGED — audit did not inspect any content."
    exit 1
  fi
  if [ -z "$staged_files" ]; then
    echo "deletions only — nothing to scan"
  fi
else
  n=0
  if [ -n "$staged_files" ]; then
    n=$(printf '%s\n' "$staged_files" | command grep -c . || true)
  fi
  echo "range $RANGE: $n file(s)"
fi

# 1. Forbidden filenames / extensions. Matched on the basename so nested paths
#    (infra/credentials.json, config/.env) are caught, not just the repo root.
#    The research-library and private-proposal checks stay on the full path.
while IFS= read -r f; do
  [ -z "$f" ] && continue
  case "$(basename "$f")" in
    .env.example|.env.sample)
      ;;
    .env|.env.*|*.pem|*.key|*.p12|*.pfx|id_rsa*|credentials.json|service-account*.json|secrets.*|.netrc)
      echo "FORBIDDEN FILE STAGED: $f"; fail=1;;
  esac
  case "$f" in
    library/*|*/library/*)
      echo "RESEARCH LIBRARY FILE STAGED (must stay local): $f"; fail=1;;
    proposal/*|*/proposal/*)
      echo "PRIVATE PROPOSAL FILE STAGED (must stay local): $f"; fail=1;;
  esac
done <<< "$staged_files"

# 2. Secret patterns in the staged diff (added lines only)
patterns='(AKIA[0-9A-Z]{16}|ASIA[0-9A-Z]{16}|(^|[^A-Za-z0-9])sk-[A-Za-z0-9_-]{20,}|(^|[^A-Za-z0-9])sk-ant-[A-Za-z0-9_-]{20,}|ghp_[A-Za-z0-9]{36}|github_pat_[A-Za-z0-9_]{22,}|xox[baprs]-[A-Za-z0-9-]{10,}|AIza[0-9A-Za-z_-]{35}|-----BEGIN (RSA |EC |OPENSSH |PGP |DSA )?PRIVATE KEY-----|eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{10,}|(password|passwd|pwd|secret|token|api[_-]?key|access[_-]?key|bearer)[\"'"'"' ]*[:=][\"'"'"' ]*[A-Za-z0-9/+=_-]{12,}|(postgres|mysql|mongodb(\+srv)?|redis|amqp)://[^:/[:space:]]+:[^@/[:space:]]+@)'
diff_added=$("${diff_sel[@]}" -U0 | command grep -E '^\+' | command grep -Ev '^\+\+\+' || true)
printf '%s\n' "$diff_added" | command grep -Ein "$patterns" > "$hits" || true
if [ -s "$hits" ]; then
  echo "POSSIBLE SECRET IN STAGED DIFF:"; cat "$hits"; fail=1
fi

# 3. High-entropy strings in added lines. Exemptions: hex digests, hash-prefixed
#    tokens (sha256/digest/hash), hyphen-separated slugs, separator-joined
#    identifiers, lockfiles, and committed HTML pages. Lockfiles (uv.lock,
#    poetry.lock, package-lock.json, pnpm-lock.yaml, yarn.lock, Cargo.lock) are
#    excluded from this check's diff entirely, at any depth (ui/package-lock.json
#    too) — they are machine-generated
#    manifests of package URLs and hashes, never hand-typed secrets, and their
#    wheel/package filenames routinely contain long mixed alnum runs (e.g.
#    platform tags like `cp314-cp314-pyemscripten_2026_0_wasm32`) that read as
#    high-entropy but aren't. Committed public HTML pages under sources/ (e.g.
#    a saved report page) are excluded too — they carry version ids and SRI hashes
#    baked in by the publisher, not secrets. Checks 1 and 2 still scan
#    lockfiles and sources/*.html in full, so a literal secret pasted into one
#    (an AKIA key, a bearer token, a credentialed connection string) is still
#    caught by check 2. Candidates exclude '/' so ordinary paths and URLs break
#    into short pieces. A candidate is reported only if it mixes letters and
#    digits, is not a hex digest (either case), is not a hyphen-separated slug,
#    and is not an allowlisted digest-like string. The allowlist is applied to
#    the matched candidate, never to the whole line. The leading '+' diff
#    marker is stripped first: '+' is a candidate character, so a line whose
#    content starts at column 0 would otherwise fold the marker into the
#    candidate and defeat the hex and slug exclusions.
diff_added_no_locks=$("${diff_sel[@]}" -U0 -- . ':(exclude,glob)**/uv.lock' ':(exclude,glob)**/poetry.lock' ':(exclude,glob)**/package-lock.json' ':(exclude,glob)**/pnpm-lock.yaml' ':(exclude,glob)**/yarn.lock' ':(exclude,glob)**/Cargo.lock' ':(exclude)sources/*.html' | command grep -E '^\+' | command grep -Ev '^\+\+\+' || true)
printf '%s\n' "$diff_added_no_locks" \
  | command sed 's/^+//' \
  | command grep -Eon '[A-Za-z0-9+=_-]{40,}' \
  | awk -F: '
      function is_slug(t,   parts, i, n) {
        if (t !~ /^[a-z0-9-]+$/) return 0
        n = split(t, parts, "-")
        if (n < 2) return 0
        for (i = 1; i <= n; i++) if (length(parts[i]) > 20) return 0
        return 1
      }
      # Identifier shapes: words joined by _ or -, leading letter, no segment
      # longer than 20, and every segment shaped letters-then-digits (never a
      # random mix of the two within one segment). Catches snake_case test
      # names and ids carrying digits, while rejecting separator-segmented
      # high-entropy tokens (e.g. base64url chunks joined by '-') that would
      # otherwise satisfy the length-only rule. A separator is required, so a
      # contiguous token blob never qualifies.
      function is_identifier(t,   parts, i, n) {
        if (t !~ /^[A-Za-z][A-Za-z0-9]*([_-][A-Za-z0-9]+)+$/) return 0
        n = split(t, parts, "[_-]")
        for (i = 1; i <= n; i++) {
          if (length(parts[i]) > 20) return 0
          if (parts[i] !~ /^[A-Za-z]*[0-9]*$/) return 0
        }
        return 1
      }
      {
        cand = $2
        if (cand ~ /sha256/ || cand ~ /digest/ || cand ~ /[Hh]ash/) next
        if (cand !~ /[0-9]/ || cand !~ /[A-Za-z]/) next
        if (cand ~ /^[0-9a-fA-F]+$/) next
        if (is_slug(cand)) next
        if (is_identifier(cand)) next
        print $1 ":" cand
      }' > "$entropy" || true
if [ -s "$entropy" ]; then
  echo "HIGH-ENTROPY STRINGS (review by hand; fail-safe):"; cat "$entropy"; fail=1
fi

# 4. .gitignore still covers the sensitive classes. Decide the source from the
#    INDEX, not from the staged_files (ACMR) list above: an index that removes
#    .gitignore is filter-D, so it never appears in ACMR and check 4 would
#    otherwise silently fall back to the working-tree copy and bless the one
#    commit that disarms every later commit's ignore rules. Range mode has no index
#    at all, so it reads `.gitignore` as committed at <head> instead (ruling R6) —
#    never the working tree, which can hold uncommitted edits the range never covers.
if [ -n "$RANGE" ]; then
  head_rev="${RANGE##*..}"
  if git show "$head_rev":.gitignore > "$ignorefile" 2>/dev/null; then
    echo "== .gitignore source: $head_rev =="
  else
    echo ".gitignore MISSING ENTIRELY"; fail=1; : > "$ignorefile"
  fi
elif git cat-file -e :.gitignore 2>/dev/null; then
  echo "== .gitignore source: staged blob =="
  git show :.gitignore > "$ignorefile"
elif git rev-parse -q --verify HEAD:.gitignore >/dev/null; then
  echo ".gitignore REMOVED FROM THE INDEX"; fail=1; : > "$ignorefile"
elif [ -f .gitignore ]; then
  echo "== .gitignore source: working tree =="
  cat .gitignore > "$ignorefile"
else
  echo ".gitignore MISSING ENTIRELY"; fail=1; : > "$ignorefile"
fi
for pat in '.env' '*.pem' '*.key' 'credentials.json' 'service-account*.json' 'library/' 'proposal/'; do
  command grep -qxF "$pat" "$ignorefile" || { echo ".gitignore MISSING: $pat"; fail=1; }
done

if [ "$fail" -ne 0 ]; then echo "AUDIT FAILED — do not commit."; exit 1; fi
echo "AUDIT CLEAN."
