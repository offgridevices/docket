# Docket — guide for coding agents

Docket turns a decision study into an auditable record: an AI agent drafts the
structure of a decision (alternatives, criteria, assumptions, evidence), people review
and agree it, and a deterministic kernel scores and packages it. The agent never
produces a number, rating or verdict; the kernel does. `README.md` is the product
overview and `docs/architecture.md` the full layout.

## Where things are

| Path | What it is |
|---|---|
| `src/docket/` | The Python package: `kernel/` (graph, scoring, rendering), `agent/` (elicitation, prompts, review), `api/` (FastAPI app behind the UI), `schema/`, `standard/` (the 36-question research standard), `exports/`, `eval/`, `cli.py` |
| `ui/` | The demo UI (Vite, React, TypeScript) and its Playwright suites in `ui/e2e/` |
| `demos/` | Six reproducible demonstrations; each `out/` is committed and must match a fresh build byte for byte |
| `tests/` | pytest suite; `tests/fixtures/recorded/` holds recorded model transcripts |
| `reports/` | The validation report, generated from the demo outputs |
| `scripts/` | Commit audit, citation and wording checks, determinism gate, source fetcher |
| `sources/` | One `*.source.md` provenance note per public document cited; the documents themselves are downloaded, never committed |
| `docs/` | Architecture, design, demo script, and `decisions/` (one dated record per settled choice) |

## Commands

```bash
uv sync && (cd ui && npm ci)                  # setup
git config core.hooksPath .githooks            # once per clone: turns on the commit audit
uv run pytest -q
uv run ruff check src tests demos reports scripts
uv run python scripts/check-citations.py
uv run python scripts/dow-lint.py
scripts/determinism-check.sh
cd ui && npm run typecheck && npm run build && npx playwright test --project=smoke
make demo                                      # run the app on the recorded transcript
```

## Never commit

`.gitignore` excludes these and `scripts/precommit-audit.sh` refuses them if staged (CI
runs the same audit on every pull request). Never bypass either: no `git add -f`, no
`--no-verify`.

- **`proposal/`** — a private working folder that may exist on the maintainer's machine.
  It is not part of this project. Do not copy its content into tracked files, and do not
  reference it from code, docs, tests or commit messages.
- **`library/`** — the local research library.
- **Downloaded documents in `sources/`** — only the `*.source.md` notes and
  `sources/README.md` are committed. Fetch a document from the URL in its note and save
  it beside the note under the file name the note gives.
- **Secrets** — keys, tokens, credentials, `.env*` files.

## Working rules

- Work in a git worktree on a branch; every change lands on `main` through a pull request
  that the maintainer merges. Never push to `main`.
- A worktree contains only tracked files. The ignored folders above, and any downloaded
  documents, exist only in the main checkout.
- A change to the renderer, a rule or a message changes demo output: regenerate with
  `uv run docket demo all` and commit the outputs with the change.
- A change to anything under `src/docket/agent/prompts/` invalidates the recorded
  transcripts in `tests/fixtures/recorded/`.
- A change of direction gets a dated decision record in `docs/decisions/`.
- Every factual claim in docs and demos cites a committed file (`check-citations.py`).
- `CONTRIBUTING.md` has the rest.
