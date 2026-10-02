# Architecture and repository map

This file explains why the repository is laid out the way it is, what each piece does,
and where to look when something goes wrong. It is the one place for that; the README
stays high-level.

## The idea in three layers

docket keeps the reasoning behind an acquisition decision as a record that can be
checked, recomputed and graded. Three layers, and the boundaries between them are the
product:

1. **The record** (`src/docket/store.py`, `src/docket/objects.py`, `src/docket/schema/`).
   An append-only, hash-chained store of typed objects: charter, objectives, options,
   constraints, assumptions, risks, bias checks, evidence, claims, runs, results,
   packages. Every object says who wrote it (a human, the kernel, or a model acting as an
   agent) and when. A gap or an exclusion is itself an object, so silence is never blank.
2. **The kernel** (`src/docket/kernel/`). Deterministic code that validates the record,
   computes values, finds what would flip the decision, checks evidence against its scope
   of validity, scores the record against the 36-question research standard, decides
   readiness, handles refreshes over time, and renders the decision package. Given the
   same store, the same seed and the same clock it produces the same bytes; the CI gate
   proves it on every demo.
3. **The agent layer** (`src/docket/agent/`). A language model, chosen by the operator
   and swappable, that drafts the model from a request, proposes a plan with doctrine
   citations, dispatches computation, and writes a narrative whose every factual sentence
   must cite a record object. The agent never computes a number and can never author a
   run, a result or a commitment: the store refuses it at the write path, and a saved
   store can prove the refusal to a third party.

Between the layers sit four human gates. The first one, G1, sits on the *model*, after
elicitation and before any computation: a human confirms the gaps, accepts or rejects
each drafted object, completes the charter, and approves. Catching a wrong question is
cheap; catching a wrong answer is not.

## Repository map

```
README.md            what this is, what it runs on, how to run it
CONTRIBUTING.md      dev setup, checks, hooks and the contribution rules
LICENSING.md         which files are AGPL-3.0-only (LICENSE) and which Apache-2.0 (LICENSE-APACHE)
NOTICE.md            third-party rights in sources/, item by item
Makefile             make demo · make test · make figures · make ui-build

src/docket/          the Python package
  store.py, objects.py, errors.py     the record: store, object catalogue, error types
  schema/                             the object catalogue (objects.yaml) and generated JSON Schemas
  standard/                           the 36-question research standard, tailorings, crosswalk, rules
  kernel/                             validator, evaluator, flip analysis, scope, standards scorer,
                                      bias indicators, lifecycle gates, readiness, refresh, renderer
    clock.py                          when it is due, where the time went, who it has been waiting on
    queue.py                          what needs a person now, and what stops this decision moving on
    commit.py                         G3: the commitment bound by hash to the package that was read
  exports/                            the six exports written beside every package
  agent/                              backends, elicitation, G1 review, plan, dispatch, narrative, watch
    ask.py                            the read-only chat: nine intents answered from the record
  eval/                               agreement statistics and the ablation transforms (library code)
  api/                                the FastAPI demo server: sessions, routes, settings, event stream
    routes/workspace.py               the clock, the activity log, the queue, send back and sign
    routes/ask.py                     the suggested questions and the one ask endpoint
  cli.py                              the docket command: validate, evaluate, render, export, ui, demo …

ui/                  the demonstration frontend (Vite, React, TypeScript); ui/e2e holds the browser tests

demos/               one folder per demonstration or validation case, each with build.py,
                     run.py and a committed out/ (the record, the packages, the exports)
reports/             the generated Phase I validation report and its generator
tests/               pytest suites mirroring src/ (kernel, agent, api, exports, eval, demos)
scripts/             the pre-commit secrets audit, the CI range helper, the determinism check,
                     the citation checker, the copy lint, the source fetcher, the standard
                     deriver

sources/             INPUT DOCUMENTS: the public documents the record cites, each with a
                     .source.md sidecar giving URL, retrieval date and release status
library/             (gitignored) the local research inbox; nothing here is cited or committed
                     until it is promoted into sources/ with a sidecar

docs/                the documentation (see docs/README.md)
.github/workflows/   CI (PRs only): ruff, pytest, citations, DoW, secrets, determinism;
                     UI build + Playwright smoke in parallel
```

Two folders are deliberately kept apart. `sources/` is committed and public by rule:
every file carries a sidecar stating its release status, and the citation checker holds
every tagged claim to it. `library/` is the inbox for anything gathered during research and is
never committed; a document moves from one to the other only after its public status is
checked.

Local working notes from the build (task ledgers, review reports) sit in `.superpowers/`,
which is gitignored; the rulings that matter are recorded under `docs/decisions/`.

## Conventions worth knowing before you change anything

- **Determinism is a test, not a hope.** `scripts/determinism-check.sh` builds every demo
  twice and diffs the trees, then diffs against the committed `demos/*/out`. If you
  change the renderer, a rule or a message, regenerate with `uv run docket demo all` and
  commit the outputs with the change; the gate fails otherwise.
- **Numbers on screen come from the server.** The UI does no arithmetic; every numeral
  renders through one component with its provenance mark, and a browser test walks each
  screen for bare numerals.
- **Actors are classified by their id.** An id beginning `agent:` is an agent whatever
  the dict declares; a mismatch is refused at the store.
- **Every tagged claim cites a file.** A source tag names a file under `sources/` and
  an output tag names an artefact under `demos/*/out` or `reports/`;
  `scripts/check-citations.py` verifies the paths exist and the deliverable files carry
  no untagged numeral.
- **The secrets audit runs before every commit** through `.githooks/pre-commit` (enable
  once per clone with `git config core.hooksPath .githooks`). It refuses key-shaped
  strings even in tests; use a spaced phrase for a fake key.

## Where to look when something misbehaves

| Symptom | Start here |
|---|---|
| A gate refuses and you disagree | `src/docket/kernel/lifecycle.py` (the checks per transition) and the readiness report's blockers |
| A rating or verdict looks wrong | `src/docket/standard/rules.yaml` (the predicates), `src/docket/kernel/standards.py` (the scorer), the tailoring under `src/docket/standard/tailorings/` |
| A finding fires that should not | `src/docket/kernel/policy_rules.py` and `validate.py`; run `uv run docket validate <graph>` |
| Numbers differ between runs | `scripts/determinism-check.sh`; then `src/docket/kernel/evaluate.py` and the seed/clock arguments |
| The package text is wrong | `src/docket/kernel/render.py`; every sentence must cite an object or the renderer refuses |
| An export disagrees with the package | `src/docket/exports/`; the shared helpers live in `render.py` |
| The model writes something it should not | `src/docket/store.py` (`_check_agent_authority`) and `tests/agent/test_authority_e2e.py` |
| The UI shows nothing or a blank | `ui/src/components/Slot.tsx` (never-blank rule) and the raw-object drawer on any screen |
| Live mode does not engage | `src/docket/api/routes/health.py` (the probe), `settings.py` (the denylist), the Settings slide-over |
| A browser test fails | `ui/e2e/_fixtures.ts` (the shared walk and the numeral walk), then the screen's spec |

## How a decision moves through the system

Request → **elicit** (agent drafts the model with gaps) → **G1** (human confirms gaps,
accepts or rejects objects, completes the charter, approves the model) → human authors
the weights → **plan** (agent proposes steps with doctrine citations; human approves, G2)
→ **dispatch** (kernel computes sealed runs; flip analysis) → **readiness** (validator,
scope, standard, bias indicators; one verdict, every blocker named) → **package** (two
renderings; six exports; the AI-assistance block) → **sign** (G3/G4) → **refresh** when
a trigger fires, with a diff between episodes.

One Phase I edge: a freshly elicited episode has no evaluation model and the kernel will
not choose one for the human, so the live loop stops at the plan step; plan, compute and
package are demonstrated on Demo A's own record.
