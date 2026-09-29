# Contributing to Docket

## Licence first

There is no `LICENSE` file yet: all rights are reserved and no licence has been chosen.
Until one exists there is no basis on which an outside contribution can be accepted, so
treat this file as the rules the work already follows rather than an invitation to open a
pull request.

## Development setup

```bash
uv sync                        # Python 3.12+, the package and the dev tools
cd ui && npm ci                # Node 22+, the UI and Playwright
npx playwright install chromium   # once, for the browser tests
git config core.hooksPath .githooks   # once per clone: the pre-commit audit
```

`make demo` runs the app on the recorded transcript; `README.md` lists the other
commands and `docs/architecture.md` explains the layout.

## The checks

CI runs these on every pull request; run them locally before you push.

```bash
uv run ruff check src tests demos reports scripts
uv run pytest -q
uv run python scripts/check-citations.py     # every [src:]/[out:] tag resolves to a file
uv run python scripts/dow-lint.py            # present-day prose says DoW; DoD only in titles,
                                             #   citations, filenames, URLs and quotations
scripts/determinism-check.sh                 # two builds of every demo are byte-identical
cd ui && npm run typecheck && npm run build && npx playwright test --project=smoke
```

- **Determinism is a test, not a hope.** If you change the renderer, a rule or a message,
  regenerate with `uv run docket demo all` and commit the outputs with the change; the
  gate fails otherwise.
- **Recorded transcripts are keyed on the prompt.** Changing any text under
  `src/docket/agent/prompts/` changes the key, and the recorded fixtures in
  `tests/fixtures/recorded/` stop matching. A prompt change is a fixture change.
- **Tests assert behaviour.** A test that pins an implementation detail, or a disjunctive
  assertion that passes for the wrong reason, is a defect, not coverage.

## The pre-commit audit

`scripts/precommit-audit.sh` runs on every commit through `.githooks/pre-commit`. It scans
the staged files and the staged diff for API keys, tokens, private keys, credentials,
connection strings, `.env*` files and high-entropy strings; refuses any staged file under
the ignored local folders (`library/` and the other paths it names); and checks that
`.gitignore` still covers them. It exits non-zero on any hit. If it flags something, stop
and look; do not commit "just in case". It refuses key-shaped strings even in tests — build
a fake key at runtime rather than writing it as one literal.

## Rules of the road

1. **Public sources only.** Nothing controlled, CUI, export-restricted or unreleased enters
   this repository, ever. If a document's release status is unclear, do not commit it:
   write a stub in `sources/` with the URL and ask (see `sources/README.md`).
2. **Every factual claim cites a committed file.** If we cannot point at the document, we
   do not write the sentence. A promoted document arrives in `sources/` with a sibling
   `<name>.source.md` sidecar recording the URL, the date retrieved, the publisher and the
   release status; the sidecar is the authority on that document's rights, and
   `NOTICE.md` is a table built from the sidecars.
3. **The agent never sits in the numeric path.** No model output may become a number, a
   rating, an evaluation run or a commitment; the store enforces this and the tests prove
   it. No provider or model is a default, and some model families are refused by policy.
4. **A change of direction is a decision record.** Add a dated file under
   `docs/decisions/` saying what was chosen, over what, why, and what would reverse it.
5. **The local research library (`library/`) is never committed.** Documents are promoted
   from it into `sources/`, with a sidecar, only after their public status is checked.

## Branches, commits and pull requests

- Work in a git worktree on a branch; every change lands on `main` through a pull request
  (`docs/decisions/2026-09-08-worktrees-and-pull-requests.md`).
- Nothing merges to `main` without the maintainer's review. No automated process or agent
  rebases, merges or pushes to `main` on its own.
- Commit messages: a short imperative subject line, then a body that says what changed and
  why. Keep unrelated changes in separate commits.
- The pull request carries the description of what changed and why, and the results of the
  checks above.
