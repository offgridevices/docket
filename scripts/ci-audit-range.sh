#!/usr/bin/env bash
# Resolve the commit range CI's secrets/DoW audit (`scripts/precommit-audit.sh --range`)
# should scan, from GitHub Actions' own event context — never a hardcoded
# `origin/main...HEAD`.
#
# Why this exists (review C1, plan 06 Task 2 Part 1, fix round 1): with `fetch-depth: 0`,
# `origin/main`'s remote-tracking ref already points at the commit that was just pushed
# by the time this job runs on an ordinary `push` to `main`, so a hardcoded
# `origin/main...HEAD` diffs a branch against itself — an empty diff, on every real
# commit this project makes. The range must instead come from the *event*, not from a
# fixed ref name.
#
# Inputs (env vars; the workflow step below maps these from the GitHub Actions context —
# see .github/workflows/ci.yml's "Determine audit range" step):
#
#   CI_EVENT_NAME          push | pull_request              (github.event_name)
#   CI_HEAD_SHA            the tip to audit up to            (github.sha for push;
#                                                              github.event.pull_request
#                                                              .head.sha for pull_request)
#   CI_BASE_SHA            the tip to audit from             (github.event.before for
#                                                              push; github.event
#                                                              .pull_request.base.sha for
#                                                              pull_request)
#   CI_DEFAULT_BRANCH_REF  fallback ref for a brand-new branch's first push, whose
#                          `before` is the all-zeros sha (default: origin/main)
#
# Rule: push's range is `before..sha`; pull_request's is `base.sha..head.sha` — both
# two-dot, both taken directly from the event, never rewritten to a fixed branch name.
# On a new branch's first push, `before` is 40 zeros (there is no prior commit on this
# ref to diff from), so the range starts at the merge-base with the default branch
# instead: `git merge-base "$CI_DEFAULT_BRANCH_REF" "$CI_HEAD_SHA"` — "everything this
# branch has added since it forked".
#
# Prints the resolved `base..head` range to stdout on success. Fails loudly (exit 1,
# reason on stderr) rather than ever letting a bad range through silently:
#   - either sha does not resolve to a real commit in this checkout;
#   - the resolved range is empty (`git rev-list --count` is 0) UNLESS base and head are
#     the literal same commit — a genuine no-op (e.g. a workflow re-run against an event
#     that added nothing new, or a brand-new branch whose tip equals the default
#     branch's merge-base). Any other empty range — distinct endpoints that still
#     produce zero commits between them, such as a force-push to an ancestor or a
#     misresolved sha — is treated as suspicious, not routine, and fails the job rather
#     than being waved through as an ordinary no-op.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"

ZERO_SHA="0000000000000000000000000000000000000000"
event="${CI_EVENT_NAME:?CI_EVENT_NAME is required (push|pull_request)}"
head="${CI_HEAD_SHA:?CI_HEAD_SHA is required}"
base="${CI_BASE_SHA:-}"
default_ref="${CI_DEFAULT_BRANCH_REF:-origin/main}"

case "$event" in
  pull_request)
    if [ -z "$base" ]; then
      echo "ci-audit-range: pull_request event but CI_BASE_SHA is empty" >&2
      exit 1
    fi
    ;;
  push)
    if [ -z "$base" ] || [ "$base" = "$ZERO_SHA" ]; then
      if ! base=$(git merge-base "$default_ref" "$head" 2>/dev/null); then
        echo "ci-audit-range: new-branch push (before=$ZERO_SHA) but no merge-base with $default_ref" >&2
        exit 1
      fi
    fi
    ;;
  *)
    echo "ci-audit-range: unrecognised CI_EVENT_NAME '$event' (want push|pull_request)" >&2
    exit 1
    ;;
esac

if ! git rev-parse --verify -q "${base}^{commit}" >/dev/null; then
  echo "ci-audit-range: base sha '$base' does not resolve to a commit" >&2
  exit 1
fi
if ! git rev-parse --verify -q "${head}^{commit}" >/dev/null; then
  echo "ci-audit-range: head sha '$head' does not resolve to a commit" >&2
  exit 1
fi

range="$base..$head"
count=$(git rev-list --count "$range")

if [ "$count" -eq 0 ] && [ "$base" != "$head" ]; then
  echo "ci-audit-range: empty range $range with distinct endpoints — refusing to pass silently" >&2
  exit 1
fi

echo "$range"
