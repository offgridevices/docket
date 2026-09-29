# Frontend design v2 — the combined design as built (2026-09-11)

**Status:** built on branch `t3code/five-ui-mockup-variants`, 2026-09-11 to 2026-09-13.
**Source:** the combined-design spec of 2026-09-11, with the two mockup briefs reproduced
as its appendices. The spec and its build plan are working papers kept outside the
repository (they are not committed); this document is the record of the design as built.
**Written from the code**, after the last build task: every label, route, token and term
in this document was read out of `ui/src/`, `src/docket/` or `ui/e2e/` while writing it.

---

## Why a second design document

The first design document gave the demonstration one screen per lifecycle stage, so the
screen a reader was on *was* the state the episode was in. This one is task-first
instead: What needs you is the home view, a progress map carries the lifecycle at the
side of every view, and a read-only chat answers from the record beside whatever is on
screen. `frontend-design.md` stays as the record of what those first screens were and of
the honesty rules it introduced — provenance marks, the numeral rule, the never-blank
rule, the footer disclosures — all of which this design keeps.

---

## The frame

`ui/src/frame/` and `ui/src/frame/frame.css`. The document itself never scrolls: the
viewport is a column of header, canvas and footer, and the three canvas columns scroll
inside themselves.

| Region | What it holds | Behaviour below 1024 / 768 / 520 |
|---|---|---|
| Header | The mark and the word `Docket`; the decision switcher (`Which decision`, offering `Demo A · CBO GCV 2013`, `Demo B · OMFV 2019–2023`, `New session` and every session already open); the episode chip (its id and its plain state, with the record's state name under Explain); then `Explain`, `Browse the record`, `Ask about this decision` and `open settings`. | The words beside the `Explain` and `Browse the record` icons come off first, below 1280, while each button keeps its name for a screen reader; below 768 the episode chip is hidden; below 520 the word `Docket` and the `Explain` button go, and Explain stays reachable inside `Browse the record`. |
| Status row | `needs you` and `blocking` as counters, each coloured only while it is counting something and each opening what it counts; the time chip; the mode chip (`recorded`, `live` or `API absent`), which opens Settings. | Below 1024 the row stops wrapping and scrolls sideways instead, with the mode chip ordered ahead of the time chip so the honesty indicator is never the thing you have to scroll to. Below 520 the counters keep their glyph and their number on screen and move their words into the accessible name only. |
| Progress map | `Where this decision stands`: What needs you, then Request, Model, Plan, Compute, Readiness, Package; then `Registers`: Evidence, Timeline, Activity. Each row has a state glyph (done, needs you, in progress, not yet), the view's own icon, its label, the record's term under Explain, and the count of actionable items routed there. Below the rows, the colour key. | Unchanged below 1024. Below 768 it becomes a horizontal strip above the view column: the group headings and the colour key are dropped, each row is as wide as its own label, and the strip scrolls sideways rather than squeezing every label into ellipses. |
| View | One eyebrow, one heading, one sentence, and the view's own controls against the right edge; the Explain panel above the body when Explain is on; the body below. Scrolls inside itself. | Unchanged; it is the column that grows as the others fold away. |
| Chat | `Ask about this decision`: the sentence "Reads this decision. Never writes to it.", the two authority counters (which open `Who may write what`), the suggested questions, the thread, and the composer. | Below 1024 it becomes a bottom sheet opened from the header; the collapsed desktop tab is not shown at that width. At and above 1024 it can be collapsed to a tab and reopened from the header. |
| Footer | The two disclosures separated by an interpunct; the Coverage control, which opens the inventory sheet; the mark and `OffGrid`. Always visible. | Below 520 the Coverage control shortens its own label to `Coverage`. |
| Overlays | Settings, the raw-object drawer, the review card as a dialog, the blockers list, the Coverage sheet, `Who may write what`, the sign sheet and the send-back sheet. | Unchanged; while any of them is open the frame takes the Ember fill off the page behind it, header and footer included, because the act behind a sheet is not the act in front of one. |

---

## The views

The table in `ui/src/routes.tsx` is the single list: the map, `Browse the record` and the
router all read it. "The one act" is the element carrying the view's single Ember fill,
which the frame paints.

| Route | View | The one act | What Fields can show | Spec reference |
|---|---|---|---|---|
| `/` | What needs you | the first actionable queue card's own button; `Open the signed package` once the decision is signed | who it waits on · how many are waiting · which part of the record · stage | §5 `/` |
| `/request` | Request | `Next` through the three steps, then `Elicit`, then `Go to the model checklist` | — | §5 `/request` |
| `/model` | Model | `Approve the model`, filled only while the gate is open and every check is met | source page · object id · how sure the draft was · who agreed · revision | §5 `/model` |
| `/plan` | Plan | `Approve the plan`, then `Pass gate 2` | the paragraph each step cites · measures · evaluator model · sensitivity sweeps | §5 `/plan` |
| `/compute` | Compute | `Run the plan` | record and input hashes · parameter bindings · every result, not only aggregates · sensitivity sweeps | §5 `/compute` |
| `/readiness` | Readiness | none — `Score the record against the standard` is outlined, and the severity on this view belongs to the blockers | what each rating was drawn from · the scoring rule behind each rating · the mandate scorecard · bias checks | §5 `/readiness` |
| `/package` | Package | `Sign`, offered only once a full package is rendered and the gate's checks pass | — | §5 `/package` |
| `/evidence` | Evidence | none | classification · reliability steps · cited by · scope findings · id | §5 `/evidence` |
| `/timeline` | Timeline | `Open refresh`, filled when opening a refresh is the act | object ids on diff rows · triggers filed on the programme · the verdict grid · days each episode lived | §5 `/timeline` |
| `/activity` | Activity | none | log position · revision | §5 `/activity` |
| `/review`, `/review/:objectId` | Review, one thing at a time | the review card's first non-destructive action — `Accept` wherever the record offers one | — | §5 `/review` |

`/ask` is not a view: it is the address a chat answer's chip carries. It asks the
question and leaves the reader on What needs you.

Six views carry a heading different from their map label, because the map has a column
to fit and the view has a line: `Request` is headed `File the request`, `Model` is headed
`Every object in the model`, `Plan` is headed `The plan`, `Package` is headed `The
package`, `Timeline` is headed `The programme`, and `Review, one thing at a time` is
headed `Read and agree`. The rest are headed by their label.

---

## The API added

Every route below follows the existing session and episode pattern and the shared error
table. Everything is computed at request time from the session's own copy of the record
and is never rendered into a package.

| Route | Module | Read/Write | Test |
|---|---|---|---|
| `GET /api/session/{s}/episode/{e}/clock` | `api/routes/workspace.py` over `kernel/clock.py` | read | `tests/kernel/test_clock.py`, `tests/api/test_clock.py`, `ui/e2e/clock.spec.ts` |
| `GET /api/session/{s}/activity` | `api/routes/workspace.py` over `clock.describe_log_entry` | read | `tests/api/test_clock.py`, `ui/e2e/activity.spec.ts` |
| `GET /api/session/{s}/episode/{e}/needs` | `api/routes/workspace.py` over `kernel/queue.py` | read | `tests/kernel/test_queue.py`, `tests/api/test_needs.py`, `ui/e2e/needs.spec.ts` |
| `POST /api/session/{s}/episode/{e}/send-back` | `api/routes/workspace.py` over `kernel/refresh.py` | write, by a person | `tests/kernel/test_refresh.py`, `tests/api/test_send_back.py`, `ui/e2e/package.spec.ts` |
| `POST /api/session/{s}/episode/{e}/sign` | `api/routes/workspace.py` over `kernel/commit.py`; the commitment it writes is `cm-<episode>-<n>` | write, by a person | `tests/kernel/test_commit.py`, `tests/api/test_sign.py`, `ui/e2e/package.spec.ts` |
| `GET /api/ask/questions` | `api/routes/ask.py` | read | `tests/api/test_ask.py`, `ui/e2e/chat.spec.ts` |
| `POST /api/session/{s}/episode/{e}/ask` | `api/routes/ask.py` over `agent/ask.py` | read — the exchange is appended to the session's own `chat.jsonl`, never to the record | `tests/agent/test_ask.py`, `tests/api/test_ask.py`, `ui/e2e/chat.spec.ts` |
| `whatWouldSatisfy` on every rung of the gate ladder | `api/serialize.py` over `kernel/queue.py` | read | `tests/api/test_sessions.py`, `ui/e2e/model.spec.ts` |
| `timing` on `GET /api/session/{s}/program/{p}/timeline` | `api/routes/program.py` over `clock.programme_timing` | read | `tests/kernel/test_clock.py`, `tests/api/test_program_routes.py`, `ui/e2e/timeline.spec.ts` |

Three things about these routes are worth stating in one place, because a reader of the
screens cannot see them.

**The clock derives, and never estimates.** How long is left and how wide the strip is
are both absent when the charter names no deadline: with nothing to count towards, there
is no honest number, so the client draws a strip that runs to today rather than to a
guess. A decision that is signed, superseded or void is never late and never stuck. The
wording a reader sees on an overdue flag is the clock's own flag text, not a sentence the
browser assembled. The charter's deadline field is optional and is unset in every
demonstration record.

**The queue counts acts, and the blocking counter counts obstructions.** The count beside
`needs you` is actionable items only; items waiting on an earlier step are listed and
greyed but never counted. The count beside `blocking` is the stored blocking findings
plus the unmet checks of the gate the episode is actually sitting at — except a check
whose satisfaction is the very act the queue is already asking for, which is not an
obstruction to itself: a package awaiting a signature does not count `commitment-present`
and `commitment-package-hash` against the signature. So a ready package with nothing
outstanding but the signature reads `blocking [ 0 ]`, and the blockers sheet says nothing
is blocking it. The gate ladder still shows both checks as unmet, because they are: not
counted is not hidden. Blocking findings are grouped one row per rule with a count on the
row, so grouping never changes the number a reader is shown. After a send-back the queue
lists the return as the act and the signature as waiting on it — the record's own reading,
since signing is refused while the return stands — so the signature is greyed and out of
the count until the return is answered.

**Every count on the map is the server's.** The queue reports, beside its items, how many
actionable items sit on each view of the map, with the review cards counted against Model;
the map prints those numbers and filters nothing itself.

**Signing and sending back are both writes by a person, and both are recorded.** Sending
back requires a package awaiting a signature and a reason that is not blank; it files a
human-authored trigger of kind `signer-return` whose affected object is the episode, and
appends it to the programme when the episode belongs to one. Nothing is deleted and no
history is rewritten; the programme's own refresh path is how the rework becomes a new
episode. Signing writes a commitment, `cm-<episode>-<n>`, bound by hash to the full package read, and
then drives the signed state through the same gate as every other transition; if the gate
refuses, the episode's pointer to the commitment is put back where it was and the refusal
stays on the record. Conditions are written as an empty list in this version, because the
schema requires each condition to name an action object to verify it by and no route
authors one yet; the view says so. A signature's timestamp may be supplied by the client
as the moment of signing.

---

## Colour

Five semantic state tokens, defined in `ui/src/brand/semantic.css` and exposed through
the Tailwind preset. Why the brand's one-accent rule was deviated from, where colour may
and may not sit, and what would reverse the decision are all in
[`../decisions/2026-09-11-ui-colour-system.md`](../decisions/2026-09-11-ui-colour-system.md);
they are not restated here.

| Token | Means | Tailwind names |
|---|---|---|
| `--c-act` | the act to do next — the one fill per view | `text-act`, `text-act-text`, `bg-act-tint`, `border-act-line` |
| `--c-stop` | stops progress · refused · overdue | `text-stop`, `bg-stop-tint`, `border-stop-line` |
| `--c-wait` | in progress · waiting · warning · time running low | `text-wait`, `bg-wait-tint`, `border-wait-line` |
| `--c-done` | done · passed · agreed by a person · verified | `text-done`, `bg-done-tint`, `border-done-line` |
| `--c-ai` | drafted by the AI, not yet agreed | `text-ai`, `bg-ai-tint`, `border-ai-line` |

The five-line key is printed on the product itself: at the foot of the progress map, in
the Explain panel and in the Coverage sheet.

---

## Plain language

`ui/src/lib/glossary.ts` is the single source. A label rendered through `Term` shows the
plain phrase, carries the record's term and its one-line explanation as its title, and
prints the record's term in mono beside it while Explain is on. Ids, hashes, revisions,
seeds and state names stay mono and verbatim wherever they are data.

| Term | Plain phrase | Where Explain shows the record's term |
|---|---|---|
| `draft` | drafted by the AI, not yet agreed | on every object card |
| `accepted` | agreed by a person | on every object card |
| `computed` | computed (same inputs, same answer) | glossary only — the provenance mark carries it on screen |
| `linchpin` | an assumption the answer depends on | on every object card |
| `gap` | something the source never says | Model, and the charter fields block |
| `exclusion` | left out on purpose, with a reason | Model |
| `charter` | the question, the stakes, the scope | Model, Request |
| `consequences` | what happens if this is wrong | glossary only — the field is named in full on the charter block |
| `g1` | approve the model (gate 1) | Model |
| `g2` | approve the plan (gate 2) | Plan |
| `g3` | sign the package (gate 3) | glossary only — the Explain line for Package names the gate's checks |
| `g4` | accept a refresh (gate 4) | glossary only — the Explain line for Timeline names the refresh path |
| `run` | a sealed calculation | Compute |
| `flip` | what would change the answer | Compute |
| `simplex` | how often each option wins across all weightings | Readiness |
| `readiness` | ready to sign? | glossary only — the view is headed with the plain phrase |
| `verdicts` | objectivity · validity · reliability | glossary only — the verdict cards name the three in full |
| `blocking` | something that stops sign-off | glossary only — the header counter and the blockers sheet name it in plain words |
| `scope` | what this evidence was built to answer | glossary only — Evidence prints the scope fields themselves |
| `vva` | whether the model behind it was checked | glossary only — Evidence prints the fields themselves |
| `withheld` | the value exists but is not shown at this level | glossary only — the withheld chip carries the phrase |
| `superseded` | replaced by a later episode (kept, never deleted) | glossary only — Timeline prints the state itself |
| `trigger` | a reason to look again | glossary only — Timeline and the Explain line name it |
| `pkg` | the decision package (the receipt) | glossary only — the view is headed with the plain phrase |
| `locator` | where this came from (page) | on every object card |
| `actor` | who did it | glossary only — actor ids are printed verbatim in mono |

Beside the glossary, Explain prints one or two lines per view naming the objects that
view draws and the gate checks by their kernel names
(`ui/src/frame/ExplainPanel.tsx`), and the colour key.

---

## Fields

`ui/src/lib/fields.ts`. Each card list declares its own fields with a default, and a
popover on the view's heading row toggles them. A choice is stored in `localStorage`
under `docket.fields.<list>`, and the write happens on the toggle and nowhere else — so a
stored entry always means a person chose something, and merely opening a view never
records today's defaults as a preference. An unreadable or absent entry is the default
set, not an error; storage being full or disabled costs the choice its persistence, not
the session.

Eight lists exist: `queue`, `model`, `plan`, `compute`, `readiness`, `evidence`,
`timeline`, `activity`. The Request, Review and Package views carry no Fields control,
because none of them is a card list. Defaults are minimal in the sense the spec asks for
— every list opens with the fields a reader needs to act, and the identifying and
provenance detail is opt-in — and the exact default per field is in each view's own
field list.

---

## What the UI never does

- **It never computes a number.** Every numeral on screen is a value the server sent,
  rendered with its provenance mark; the browser formats and never calculates. A
  numeral walk over every view enforces it.
- **It never writes as the agent.** The only writes the interface makes are the ones a
  person presses, attributed to the configured human actor. The chat has no write path
  at all.
- **It never colours a zero.** The two header counters carry state colour only while
  they are counting something.
- **It never shows a second Ember.** One filled element per view: the act to do next,
  else the most severe blocking finding, else none. An open overlay takes the fill off
  the page behind it.
- **It never scrolls the page.** The document is exactly the height of the window at
  every width; the three columns scroll inside themselves and the footer stays in view.

---

## Tests

`ui/e2e/README.md` is the spec list and says what each file holds the interface to. In
outline:

- **The frame and the session:** `shell.spec.ts`, `session.spec.ts`, `chat.spec.ts`,
  `coverage.spec.ts`.
- **One spec per view:** `needs`, `clock`, `request`, `model`, `review`, `plan`,
  `compute`, `readiness`, `package`, `evidence`, `timeline`, `activity`.
- **Across the whole interface:** `colour.spec.ts` (the colour and overflow matrix over
  every view, at three widths, on both demonstration decisions), `brand.spec.ts`,
  `brand-tokens.spec.ts`, `settings.spec.ts`, `choreography.spec.ts`, `fallback.spec.ts`,
  and `live.spec.ts`, whose run against a real local model is one test that skips unless
  it is opted into — so a green smoke run reports that skip, and the skip is expected.
- **The figures:** `figures.spec.ts` belongs to its own project and is never part of a
  smoke run.

Width-sensitive specs run at 360, 768 and 1440 CSS pixels, defined once in
`ui/e2e/_fixtures.ts`. On the server side the new work is covered by `tests/kernel/`
(`test_clock.py`, `test_queue.py`, `test_commit.py`, `test_refresh.py`), `tests/api/`
(`test_clock.py`, `test_needs.py`, `test_ask.py`, `test_send_back.py`, `test_sign.py`)
and the schema tests for the two optional fields, alongside the determinism, citation and
copy checks that already ran in CI.

---

## Known limits

Stated because a reader would otherwise assume the opposite.

- **Two paths are proved by construction, not by a walk-through.** No fixture can stage a
  computation that seals a run, and no fixture can stage a plan approval that goes
  through: every plan in the second demonstration is refused for a missing observation,
  and no route authors an evaluation model. Those two paths are held by the kernel's own
  refusals and by unit tests, not by a browser test that completes them.
- **The figures project is retargeted but has not been run.** Regenerating the proposal
  images is a separate, deliberate step, because the proposal is in preparation.
- **CI runs the smoke project, not the figures project.** On every pull request the `ui`
  job builds the bundle and runs the Playwright smoke project alongside the `check` job
  (the Python suites, the citation check, the copy lint, the determinism check and the
  secrets audit). `make test` runs the same two halves locally. The `figures` project is
  the one browser suite that never runs in CI.
