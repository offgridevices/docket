# Playwright end-to-end specs

Every user-facing part of the combined design has a spec here. `../playwright.config.ts`
defines two projects, and `smoke` is the one a normal run uses: it runs every file in this
directory except `figures.spec.ts`, which belongs to the `figures` project and is never
part of a smoke run. One test inside the smoke set skips unless it is opted into — the
live-Ollama run in `live.spec.ts` — so a green run reports a skip and that skip is
expected. This file says what each spec is for, what the shared helpers assert, and how to
install and run the suite.

## The specs

The frame and the session:

| file | what it holds the app to |
| --- | --- |
| `shell.spec.ts` | the application frame at every width: header, progress map, view column, chat, footer — what collapses, what becomes a strip, what is never dropped. |
| `session.spec.ts` | how a decision gets opened, and what the app says when it cannot be — a missing store, an unreachable API, nothing chosen yet. |
| `chat.spec.ts` | Ask about this decision: the chips the server names, answers whose citations open the stored object and whose actions navigate, one thread per decision, and the `/ask` address. The chat reads the record and never writes to it. |
| `coverage.spec.ts` | nothing the old interface offered is unreachable: every control the coverage sheet names has a home that resolves, Browse lists every view, Explain says something on each, and the exports are real links. |

The eleven views, one spec each:

| file | what it holds the app to |
| --- | --- |
| `needs.spec.ts` | the queue is the record's own list of outstanding human acts, the one Ember sits on the first of them, and the ways into a decision are on the same page. |
| `clock.spec.ts` | the clock card prints only what `kernel.clock` computed — when it is due, where the time went, who it has been waiting on. |
| `request.spec.ts` | the three-step wizard elicits the committed request, and every card it draws is marked as the AI's proposal in the order the server wrote them. |
| `model.spec.ts` | the gate-one board: every object with its provenance, the checklist that refuses, and the review dialog a card opens. |
| `review.spec.ts` | the review card at its two addresses — the reading queue and one object — with its regions in one fixed order. |
| `plan.spec.ts` | every planned step cites its doctrine paragraph, the proposal names who approved it, and gate two is the same kind of gate as gate one. |
| `compute.spec.ts` | the sealed runs, the ranking, what flips the decision, and the one act that hands an approved plan to the kernel. |
| `readiness.spec.ts` | the record scored against the standard: the tinted grid, the blockers naming their own rule, the gate ladder, and the honesty captions the server writes. |
| `package.spec.ts` | the package read in full, signed, dissented from or sent back — each act proved against the record through the API, never against the screen alone. |
| `evidence.spec.ts` | the evidence register, its classification marks, and what a withheld value looks like at a rendering that withholds it. |
| `timeline.spec.ts` | the programme: every number on it comes from the timeline route's own timing block, never from arithmetic in the browser. |
| `activity.spec.ts` | the append-only log, newest first, one plain sentence per entry — each sentence the server's own, refusals marked. |

Across the whole interface:

| file | what it holds the app to |
| --- | --- |
| `colour.spec.ts` | the colour and overflow matrix: every view, at three widths, on both demonstration decisions. Red is never a fill; at most one Ember fill per view; the header counters carry state colour only while they are counting something; every severity glyph draws from the five state colours in their text-safe form; and nothing pushes the page sideways or makes it taller than the window. Every colour it compares against is read out of the token files at run time, so nothing here names one. |
| `brand.spec.ts` | the brand rules that are about the source rather than a rendered page — no colour literal outside the token files, the shout detector's own unit tests, the glossary — plus one walk of every view of one decision, asserting brand conformance on each. |
| `brand-tokens.spec.ts` | the token layer itself: warm paper, Ember, the three faces, right angles, the semantic tokens on the root, and no theme machinery. If this fails, everything visual is failing for the same reason — start here. |
| `settings.spec.ts` | the settings panel: the key field is a password input and never pre-filled, no control offers the denylist override, and a denylisted model id renders disabled with its reason. |
| `choreography.spec.ts` | the demonstration's opening minutes end to end — elicit, the checklist refuses, confirm the absence, agree the linchpin, write the field, approve — with the queue draining as you act. |
| `fallback.spec.ts` | what happens when a live backend goes dark mid-demonstration: health notices, the request view reacts, and the one-click switch to the recording works. Spawns its own server on its own port. |
| `live.spec.ts` | the opt-in run against a real local Ollama. Skipped unless `DOCKET_LIVE_OLLAMA=1`; it spawns its own server too, and CI never sets that variable. |
| `figures.spec.ts` | the documentation figures. Belongs to the `figures` project and is never part of a smoke run — see below. |

## The helpers

- `_session.ts` — opening a decision through the header's switcher (`openDecision`), and
  getting to a view: `goTo` clicks a row of the progress map, `browseTo` clicks an item of
  the Browse menu, and `openView` does the latter and then waits until the view has
  actually finished arriving. That wait is not decoration: a view prints its heading in its
  empty state as well as its loaded one, so a spec that only waits for the heading asserts
  against a screen that has no data on it yet and passes.
- `_brand.ts` — brand v3.0 as assertions: right angles, no shadows, sentence case, the
  three faces, at most one Ember fill, red never a fill, forty-four-pixel targets, no
  horizontal overflow, and no colour named anywhere but the two token files.
  `assertBrandConformance` runs the lot. It also owns the list of views (`ALL_SCREENS`) and
  `semanticColours`, which reads the token names off the token files and resolves their
  values in the running page so no spec has to write a colour down. That returns two
  collections, and the distinction matters: everything the token files define, for checks
  where a tint or a hairline is the right answer, and the narrower set a coloured glyph or
  a coloured numeral may draw from — the five state colours in their text-safe form, plus
  the ink ramp, and no tint.
- `_fixtures.ts` — the checks every screen shares: console errors and uncaught exceptions,
  the numeral walk (no numeral on screen that the record did not author), the two footer
  disclosures, no provider or model string on a proposal-facing screen, no denylist
  override control. It also owns `forEachViewport`, which runs a spec's body once per
  width, and `openDemoASeeded`.
- `_elicit.ts` — one real elicitation against the committed recording, shared by the specs
  that need a draft episode in front of gate one. Neither demonstration store ships one, so
  it has to be elicited, which is what the demonstration itself does.

## Installing

    cd ui && npm ci && npx playwright install chromium

Chromium is cached under `~/Library/Caches/ms-playwright` on macOS; `npx playwright install
chromium` is a no-op once a matching build is there. `Makefile`'s `figures` and `test`
targets check for `ui/node_modules/@playwright` before invoking `npx --no-install
playwright`, so a worktree that skipped the install is told to run it rather than failing
obscurely.

## Running

    cd ui && npx playwright test --project=smoke              # the whole suite
    cd ui && npx playwright test --project=smoke colour.spec.ts   # one file
    cd ui && npx playwright test --project=smoke --headed     # watch it happen
    cd ui && DOCKET_LIVE_OLLAMA=1 npx playwright test --project=smoke -g "live Ollama"

`playwright.config.ts`'s `webServer` starts `docket ui --no-open` itself, in recorded mode,
against a throwaway state directory and a throwaway model config — so a run never touches a
developer's real sessions or `~/.config/docket`, and never reaches a network. No server
needs to be running by hand, locally or on CI. `fallback.spec.ts` and `live.spec.ts` are the
two exceptions: each spawns its own server on its own port, because both need process-wide
state that the suite's parallel workers would otherwise race.

The server is started against the BUILT bundle, not the dev server. Run `make ui-build`
before a suite run if the client has changed, or the run will assert against the last build.

## Widths

Every width-sensitive spec runs at three viewport widths — 360, 768 and 1440 CSS pixels —
through `forEachViewport` in `_fixtures.ts`. Those three are a property of this test
matrix, not of the application; `_fixtures.ts` is where they are defined and the only place
to change them. `colour.spec.ts` walks the same three across every view, on both
demonstration decisions, which is the one place the whole matrix is covered rather than one
screen of it.

## The figures project

The `figures` project is retargeted to the new views but is not run by CI or by `make test`;
regenerating the documentation figures is an explicit, separate step. It renders at its own
larger viewport at device pixel ratio two, and the two projects are kept disjoint by file so
a smoke run can never overwrite a committed PNG with a smaller one.

    cd ui && npx playwright test --project=figures    # only when asked to
