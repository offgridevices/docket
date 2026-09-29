# Docket

Docket keeps the reasoning behind an engineering or acquisition decision as a record that
can be checked, recomputed and graded. A docket is the official running record of a matter
awaiting a decision: every filing logged, nothing entering unrecorded. That is what this
software produces — a signer-ready Decision Package whose objectives, options,
constraints, assumptions, risks, evidence and exclusions are all first-class, checkable
objects, computed by code that gives the same answer every time, with a language model
helping to draft the questions but never allowed to touch the numbers.

## What it does

Decision analyses (which vehicle to buy, which requirement to keep) are graded after the
fact by outside referees, and they fail on the same things: evidence nobody can locate,
assumptions nobody varied, exclusions nobody wrote down. Docket makes those things
impossible to leave out.

- **The record.** An append-only, hash-chained store of typed objects. Every object says
  who wrote it — a human, the kernel, or a model acting as an agent — and when. A gap or
  an exclusion is itself an object, so silence is never blank.
- **The kernel.** Deterministic code that validates the record, computes values, finds
  what would flip the decision, checks each piece of evidence against the purpose it was
  built for, scores the record against GAO's published 36-question research standard,
  decides readiness, and renders the Decision Package. Same store, same seed, same clock:
  same bytes.
- **The agent layer.** A model chosen by the operator drafts the decision model from a
  request, proposes a plan with doctrine citations, and writes a narrative whose every
  factual sentence must cite a record object. The store refuses any agent write of a
  number, a rating, an evaluation run or a commitment.
- **Human gates.** A person approves the *model* of the decision before anything is
  computed, approves the plan, and signs the package. Catching a wrong question is cheap;
  catching a wrong answer is not.

## The demonstrations

Everything runs on public documents. Each has a note under `sources/` stating where it
came from, its release status and what is quoted from it; the documents themselves are
downloaded, not committed (see `sources/README.md`).

| Folder | What it is |
|---|---|
| `demos/a_cbo_gcv_2013` | **Demo A** — a point-in-time trade study reconstructed from the Congressional Budget Office's 2013 Ground Combat Vehicle alternatives analysis: computed, flip-analysed, scored and packaged. |
| `demos/b_omfv_2019_2023` | **Demo B** — a long-horizon decision program reconstructed from the public Optionally Manned Fighting Vehicle record, 2020–2023, with refresh episodes as the evidence moved, scored against GAO-23-106549. |
| `demos/validation_gao_21_460` | Validation: the scorer against GAO's own published per-question ratings (GAO-21-460, Figure 6). |
| `demos/control_gao_15_548` | Positive control: a study GAO rated as meeting the standard (GAO-15-548). |
| `demos/budget_books` | The seven Army budget-book extracts, checked for conflicts. |
| `demos/ablation` | What a readiness reading loses when each mechanism is switched off. |

Measured results are in `reports/phase1-validation.md`: on GAO-21-460 the scorer agrees
with GAO on 18 of 21 shared questions; on GAO-23-106549 it reproduces all nine of GAO's
stated verdicts. Every demonstration's output is committed under `demos/*/out`, and CI
proves a rebuild is byte-identical.

## Running it

Requirements: Python 3.12+ with [`uv`](https://docs.astral.sh/uv/), and Node 22+ for the UI.

```
make demo
```

One command. It builds the browser bundle if it is missing or stale, starts the local
server on `127.0.0.1:8765`, and opens a browser straight into a Demo A session — already
computed, scored and packaged. It runs against a committed recorded transcript by
default, so it needs no network and no model; the status row under the header carries a
chip reading `recorded` whenever that is what is happening.

Sessions are copies: opening a demo copies its store into a session directory under
`~/.local/share/docket/sessions` (set `DOCKET_STATE_DIR` to move it), so nobody edits the
shipped record.

To run against a model on your own machine, open **Settings** (the gear, top right), fill
in the provider, the base URL of your local endpoint and the model identifier, and switch
the mode to live. No key is needed for a loopback address; a key typed there is held in
memory for the session and never written to disk. If the endpoint stops answering, the
app falls back to the recorded transcript and says so. Some model families are refused by
policy whatever the configuration.

**The UI computes nothing. Every number it shows was written by the kernel and is
reproducible from the store.**

### Backend, UI and tests

```
uv sync                                   # install the Python package and dev tools
uv run docket --help                      # the CLI: validate, evaluate, flip, readiness,
                                          #   render, export, verify, refresh, diff, ui, demo
uv run docket demo all                    # rebuild every demonstration into demos/*/out
uv run docket validate <graph>            # check a saved record
uv run docket ui --no-open                # the API and UI server without a browser

cd ui && npm ci                           # UI dependencies
make ui-dev                               # Vite dev server
make ui-build                             # build the bundle the server serves
make types                                # regenerate the UI's API types

make test                                 # pytest, then the Playwright smoke suite
uv run ruff check src tests demos reports scripts
bash scripts/determinism-check.sh         # prove two builds are byte-identical
cd ui && npx playwright test --project=smoke
make figures                              # documentation screenshots -> ui/test-results/figures/
```

## Built with

- **Python** (`src/docket/`), managed with `uv`; **FastAPI** serves the API and the UI.
- **A JSON object catalogue** for the record and **YAML** for the research standard and
  its scoring rules, so the rules are data you can read.
- **Any OpenAI-compatible or Anthropic-style endpoint**, chosen at run time; a recorded
  transcript stands in when there is no network.
- **Vite, React and TypeScript** for the UI; **Playwright** for its browser tests.

## Repository layout

```
src/docket/    the package: record, kernel, agent layer, API, exports, CLI
ui/            the demonstration frontend and its browser tests (ui/e2e)
demos/         the demonstrations and validation cases, with their committed outputs
reports/       the generated validation report and its generator
tests/         the Python test suites
scripts/       the secrets audit, the citation checker, the copy lint, the determinism gate
sources/       the public input documents the record cites, each with a .source.md sidecar
docs/          architecture, design, decision records, research notes, demo script
```

`docs/architecture.md` explains why it is laid out this way, what every module does, and
where to look when something misbehaves. `CONTRIBUTING.md` has the development rules.

## Licence

All rights reserved; licence not yet chosen. There is no `LICENSE` file, and nothing here
may be redistributed until there is. `NOTICE.md` records the rights in each third-party
document under `sources/`, item by item.
