# docket — demo frontend design (plan 07)

> **Superseded on 2026-09-11.** The interface described here was rebuilt to the combined
> design; see [`frontend-design-v2.md`](frontend-design-v2.md). This document remains as
> the record of the first frontend and of the honesty rules it introduced, which v2 keeps.

**Status:** built and merged (PR #1, 2026-09-08). **Revised 2026-09-08** for brand v3.0:
§5 (visual language), §5a (layout, new), §8 (testing) and §10 (open decisions) describe
the rebuild and supersede what was built against v1.2. §§1–4, 6, 7 are unchanged and
still describe the shipped app.
**Written:** 2026-09-05. Inputs: `CLAUDE.md`, `README.md`,
`.superpowers/sdd/USER-BRIEF-2026-09-04-frontend-review-loop.md`, brand handoff
(`library/design/handoff/`, gitignored), design spec §5/§7/§8/§9.4–9.5/§10, plans
00 / 03b / 04 and the plan-04 rulings.
**Format:** each design question gets options in one line each, then a recommendation
with the reason. Tables over prose.

---

## 1. Purpose and audiences

| Audience | Where they meet it | What they must see in <10 s | How |
|---|---|---|---|
| Proposal reviewer | 4 static figures inside the 7-page Volume 2 | The model proposed; a human approved; the kernel computed. Scored against a published outside standard. | Every numeral in mono inside survey brackets with a run id; a human name on the gate stamp; the 21-question grid |
| Live event audience | A projected 7-minute run | A messy document becomes a typed record, a human catches a bad assumption, numbers appear only after approval | The authority rail counters; the refused-gate moment; the flip chart |
| Shreyash operating it | `uv run docket ui` on his laptop | It started, a backend is reachable, both demos are seeded | Health chip in the header, green/absent, one click to Demo A |

Non-goals for all three: not a product UI, not an admin console, not a document editor.

---

## 2. The story the UI tells

One line, told once, in lifecycle order. The screen you are on *is* the state the
episode is in.

| Lifecycle | Screen | On it | Who may act |
|---|---|---|---|
| — | Home | Programs, episodes, state chips | human |
| `DRAFT` | Intake | Objective in · source picked · DRAFT objects streaming with provenance | agent proposes |
| `DRAFT` | **Model (G1)** | The model as a board: objectives, alternatives, GRC&A, evidence, gaps, exclusions | **human decides** |
| `MODEL_APPROVED` | Plan (G2) | Proposed steps, each with a doctrine authority citation | agent proposes, human approves |
| `PLAN_APPROVED` → `EVALUATED` | Compute | Sealed runs, results, flip analyses, weight simplex | kernel only |
| `EVALUATED` | Readiness | Four-state grid, three dimension verdicts, blockers, gates | kernel computes |
| `PENDING_SIGNATURE` → `SIGNED` | Package | 16 sections, two renderings, hashes, export | human signs |
| `SUSPECT` / `SUPERSEDED` | Timeline | Episodes over time, triggers, diffs | kernel diffs, human accepts (G4) |

**Where the gate sits.** The Model screen is the only screen with a full-width Ember
action bar, and it is the last screen before any number exists anywhere in the app. Until
G1 passes, Compute and Readiness are present but empty, with the literal line *"No numbers
exist yet. Nothing is computed before the model is approved."*

**Three provenance marks, on every object, every screen** — the whole argument, rendered:

| Mark | Means | Rendering |
|---|---|---|
| Dashed hairline + hollow diamond | agent-proposed, DRAFT | `--og-hairline-color` dashed, mono `confidence` chip (`explicit` / `inferred` / `absent`), locator |
| Solid hairline + filled square + actor id | human-authored or human-accepted | `--og-hairline-strong`, actor id in mono |
| Survey-corner brackets + JetBrains Mono | kernel-computed | `[ 45.1 ]` with `run-id · seed · kernelVersion` beneath |

Rule the frontend enforces and states on screen: **a numeral may only be rendered
inside brackets.** Agent-authored prose is rendered in Instrument Sans and the renderer
already refuses uncited numerals; the UI makes the same rule visible. The header carries
a live counter: `NUMBERS AUTHORED BY MODEL: 0 · BY KERNEL: 37`.

---

## 3. Screen set

Options: (a) 4 screens, one long scroll — too compressed for the lifecycle story;
(b) 9 screens + a settings slide-over; (c) 13 screens, one per package section — nobody
will click through it live.

**Recommendation: (b). Nine screens, one slide-over, one universal dialog, one
persistent rail.** Nine is exactly the lifecycle plus the two registers, so the nav is
the story and nothing needs explaining.

| # | Screen | One line | Build in Phase I | Why |
|---|---|---|---|---|
| 1 | Home / Episodes | Demo A · Demo B · New, with lifecycle chips and last-run hash | **yes** | Entry point; the "two demos" claim made visible |
| 2 | Intake | Paste or pick a source, watch elicitation stream DRAFT objects with locators | **yes** | The "messy request in" half of the topic |
| 3 | Model (G1) | Board of chips by category; every chip opens the review dialog; one Ember approve bar | **yes — the screen** | The gate the proposal rests on |
| 4 | Plan (G2) | Steps with `authority.document` + paragraph; approve; agent cannot | **yes** | Cheapest strong figure: doctrine citations |
| 5 | Compute | Runs sealing, ranking, per-measure results, flip list ranked by flip distance, weight simplex | **yes** | "What flips the decision" is the topic's own phrase |
| 6 | Readiness | 21/36 four-state grid × three dimensions, verdicts, blockers, gate ladder | **yes** | The outside-referee claim |
| 7 | Evidence register | Classification / metadata level, scope of validity, reuse justification, reliability steps, assessability | **yes** | Carries F1 and F4; the CDRL A013/A103 story |
| 8 | Timeline (Demo B) | Five episodes, triggers, diffs, ratings changed | **yes, read-only** | The long-horizon half of the topic |
| 9 | Package | 16 sections rendered, unclassified/full toggle, hashes, download | **yes** | The deliverable |
| — | Settings (slide-over) | Provider · model · base URL · live model list · key state · denylist notice | **yes** | Explicit user requirement; slide-over so a model can be swapped mid-demo |
| — | Authority rail (persistent) | Counters + three-layer diagram on click | **yes** | Figure 1 of the volume |

**Cut:** authentication, multi-user, arbitrary graph editing, a JSON object browser
beyond a raw-object drawer, in-app PDF, any chart library beyond ~200 lines of hand-drawn
SVG. (Mobile layout was cut here originally and has since been reinstated — see §5a.
Dark/light transitions are moot: there is one mode.)

---

## 4. The review dialog

One component, five kinds. This is the "popups for every assumption / issue /
limitation" requirement, and it is the same dialog every time so the audience learns it
once.

| Kind | Source object | Human actions |
|---|---|---|
| Assumption | `Assumption` (linchpin flagged) | Accept · Edit · Reject |
| Gap | `InsufficientEvidence` | Confirm gap · Edit · Resolve with evidence |
| Exclusion | `Exclusion` | Accept (re-author authority) · Edit reason · Reject |
| Limitation | `Charter.limitations[]` / `Evidence.limitations[]` | Accept · Edit mitigation |
| Finding | kernel `Finding {rule, severity, objects, message}` | Jump to object · Acknowledge (no write) |

**Fixed field order, every kind:**

1. `WHAT` — the statement, verbatim, Instrument Sans.
2. `WHY THE MODEL PROPOSED IT` — `confidence` chip + `ingestionProvenance.extractor`, e.g. *inferred by openai-compatible:… from p. 9*.
3. `SOURCE` — `sourceArtifact` + `locator`, click to open the excerpt. Quoted source text is the **only** Newsreader italic in the app.
4. `IF IT IS WRONG` — `implicationsIfWrong` / `impact` / `severity`, plus `indicatorsThatWouldAlter`.
5. `WHAT YOU CAN DO` — the buttons.
6. `WHAT HAPPENS TO THE RECORD` — stated *before* the click, echoed after.

**Write-back — never silent:**

| Action | Kernel/agent call | Record effect shown |
|---|---|---|
| Accept / Edit | `agent.review.accept` | `rev n → n+1`, `createdBy.actorType: human`, your actor id |
| Confirm gap | `agent.review.confirm_gaps` | gap gains `confirmedBy {actorId, date}`; unblocks `gaps-confirmed` |
| Reject (Evidence) | `agent.review.reject` | `reviewStatus: rejected` |
| Reject (other) | `agent.review.reject` | new `Exclusion ex-reject-<id>`, `authority.role: reviewer`, id dropped from the episode list |
| Gate advance | `kernel.lifecycle.transition` | new episode rev with `checksSatisfied`; on refusal, `refused: true` is appended and shown |

After every action the dialog shows the returned object diff and the gate ladder
re-evaluates live. **Refusals are shown, not hidden** — the recorded refusal is the best
thirty seconds of the live demo.

---

## 5. Visual language

**Brand version: v3.0** (`offgridevices/offgrid-brand`,
`handoffs/2026-09-08-brand-v3.0/`). The build was originally written against v1.2; the
move is recorded in `docs/decisions/2026-09-08-demo-ui-rebuilt-on-brand-v3.md`.

Brand rules that bind: radius 0 everywhere, no shadows ever, **one Ember per surface**,
warm-paper ground (never `#FFFFFF`, never a gradient), elevation is surface tone plus a
1 px hairline, no photography. Authority comes from **size, never from weight or caps**.

**Ember is scarce, so spend it on "a human must act."** Options: (a) a conventional
red/amber/green severity palette — breaks the one-accent rule and looks like every other
dashboard; (b) Ember for blocking only, neutral tonal ramp for everything else; (c) Ember
for the four-state grid only. **Recommend (b).**

| State | Token | Shape (greyscale-safe) |
|---|---|---|
| Blocking finding / gate refused / needs you | `--og-accent` | solid square + `octagon-alert` |
| Warning | `--og-fg` on `--og-bg-sunken` | half-fill + `triangle-alert` |
| Info | `--og-fg-muted` | hairline + `info` |
| Gate passed | `--og-fg` + `shield-check`, actor id in mono | filled shield |
| Gate pending | `--og-fg-muted` dashed + `shield` | hollow shield |
| Rating 1 (no concerns) | hairline outline only | empty square |
| Rating 2 (some) | `--og-fg-muted` quarter fill | quarter square |
| Rating 3 (significant) | `--og-fg` solid | full square |
| Rating 4 (indeterminate) | `--og-fg` solid + `help-circle` | full square with glyph |
| Not applicable (tailored out) | `--og-hairline-color` slash + `tailoringReason` on hover | diagonal slash |

Shape carries the meaning as well as tone, because the technical volume may print
greyscale.

**Iconography.** Options: custom set (no time), Phosphor (rounded, fights radius 0),
Lucide. **Recommend Lucide**, 24 px, 1.5 px stroke, `stroke-linecap: butt`, monochrome
`currentColor`, never two colours. Set (~24): `file-input` intake · `scan-text`
elicitation · `circle-dashed` agent-proposed · `user-check` human-accepted · `cpu`
kernel-computed · `shield-check` / `shield` gate · `octagon-alert` blocking ·
`triangle-alert` warning · `info` info · `help-circle` gap · `square-minus` exclusion ·
`scale` standards rating · `sliders-horizontal` weights · `activity` flip curve · `lock`
sealed run · `hash` run hash · `rotate-ccw` re-run identical · `library` evidence
register · `stamp` classification · `eye-off` withheld · `calendar-clock` refresh trigger
· `history` timeline · `file-text` package section · `download` export · `server` backend
· `pen-tool` commitment.

**Typography roles (v3.0).** Two families do the talking, not four. **Instrument Sans
400, sentence case** — screen titles, the one big number per screen (`7 / 21`), the
explanatory sentences and the dialog body. Nothing in the interface is uppercase; the
`text-transform` that v1.2 baked into `.og-display` and `.og-mono` is gone. **Instrument
Sans 500** — eyebrows, labels, chips and buttons, which v1.2 set in mono. **Newsreader
italic** — verbatim quoted source or doctrine only, never our words. **JetBrains Mono** —
numerals, coordinates and code only: object ids, revs, hashes, seeds, counts, states, raw
JSON. If a string is neither a number nor an identifier nor code, it is not mono.

This is the most visible change from v1.2 and it is deliberate: the record's numbers now
read as numbers because they are the only monospaced thing on the screen.

**Density.** Max one sentence of prose per panel; everything else is a chip, a count, a
cell or a glyph. Eyebrow labels are `--og-b3` in Instrument Sans 500, not mono caps. Card
= `--og-bg-sunken` with a 1 px hairline. Grid gutter 24 px. No card is taller than the
viewport at the width it is read at.

**Spending the one Ember — the precedence rule.** The table above is a vocabulary, not a
licence: several of its states could each argue for the accent, and v1.2 let two of them
take it (blocking findings *and* rating-4 cells), which makes the one-accent rule
unsatisfiable on Readiness. Resolved by taking option (b) literally. Per rendered screen,
**exactly one element is Ember**, chosen by this precedence:

1. the screen's primary human action, where it has one — on Model that is the full-width
   gate bar (§2); elsewhere it is the single primary button, and there is never a second
   primary button on a screen; else
2. the single most severe blocking finding; else
3. nothing — a screen with no call on a human has no Ember at all, and that is correct.

Everything else, rating 4 included, falls back to its greyscale-safe shape from the table.
Shape was always carrying the meaning for print; this makes it carry the meaning on screen
too. Enforced by test, not by discipline (§8).

**Modes.** One. The UI is light only — no toggle, no `data-theme`, no dark tokens in the
stylesheet. This is a recorded deviation from the brand's dual-mode requirement;
see `docs/decisions/2026-09-08-demo-ui-is-light-only.md`. Every figure in Volume 2 is
therefore light by construction rather than by per-figure override, which is what prints.

---

## 5a. Layout: fluid to 360 px

The UI must be usable from a 360 px phone to a 4K projector. This reverses the Phase I
scope cut in §3 and §9 (see
`docs/decisions/2026-09-08-demo-ui-rebuilt-on-brand-v3.md`).

**No breakpoint soup.** v3.0 prescribes the technique in its reference page, which is
already fluid, and states the rule outright: *"Gutter is FLUID. `--og-gutter` is the
ceiling, never a fixed value — a shell that cannot narrow is the wrong thing to copy."*
So the default mechanism everywhere is:

| Concern | Mechanism |
|---|---|
| Page gutter | `padding-inline: clamp(20px, 6vw, var(--og-gutter))` |
| Section rhythm | `padding-block: clamp(64px, 10vw, var(--og-section-y))` |
| Display type | `font-size: clamp(<floor>, <n>vw, var(--og-dN))` |
| Any grid | `repeat(auto-fit, minmax(min(<N>px, 100%), 1fr))` |
| Any row of controls | `flex-wrap: wrap` |

Explicit media queries are for the four structural changes below and nothing else.

| Screen | Below 768 px | Why not something simpler |
|---|---|---|
| Shell (9-step nav) | Sidebar becomes a sticky horizontally-scrolling step strip along the top, current step scrolled into view | A hamburger hides *where you are in the lifecycle*, which is the one thing the nav exists to say (§2) |
| Readiness | Grid reflows 6 → 4 → 3 columns, cell floor 44 px | The grid **is** the claim on that screen; it must never become a list |
| Evidence, Package | Each table row becomes a stacked label-over-value card | The brand's own `.spec` table is already a two-column label/value shape — this follows it |
| Timeline | Episodes stack; the diff panel moves below rather than beside | Side-by-side diff is unreadable under ~600 px |

**Touch.** Every interactive target is at least 44 × 44 px at every width. This is the
one place the design gets *less* dense on small screens rather than merely narrower.

**Overflow is a bug.** No screen may scroll horizontally at any supported width, and
nothing may clip or overlap. Enforced by test (§8), because it is the failure mode that
returns silently the moment someone adds a wide table.

---

## 6. Architecture

Options: (a) static HTML over pre-computed JSON — fails "when I run it, it works";
(b) Next.js + a Python sidecar — two runtimes, more to break at an event; (c) FastAPI
importing the kernel and agent directly + a React/Vite/TS SPA. **Recommend (c):** one
process, no shelling out, so an `AuthorityViolation` surfaces as a real exception with a
real message rather than a parsed stderr line.

**Stack, one line:** FastAPI (uvicorn, 127.0.0.1 only) importing `docket.kernel.*` and
`docket.agent.*` · React 19 + Vite + TypeScript · Tailwind with
`library/design/handoff/tokens/tailwind.preset.js` and `tokens.css` · SSE for progress ·
hand-drawn SVG charts · Lucide icons · Playwright for smoke tests · TS types generated
from the committed `src/docket/schema/json/*.schema.json` so the 39 types cannot drift.

**Progress transport.** WebSocket (bidirectional, unneeded) vs polling (ugly) vs **SSE**.
Recommend SSE: one channel `GET /api/stream/{session}`, events `stage`, `object`,
`finding`, `done`, `error`.

| Route | M | Kernel / agent function | Notes |
|---|---|---|---|
| `/api/health` | GET | — | kernelVersion, backend reachability, models, `keyPresent`, denylist active, demo stores present |
| `/api/session` | POST | `Graph.load` | body `{source: "demo-a"｜"demo-b"｜"new"}`; **copies** the demo store into a session dir |
| `/api/session/{s}/episodes` | GET | `Graph.all` | id, sequence, lifecycleState, readiness id |
| `/api/session/{s}/object/{id}` | GET | `Graph.get` | raw object drawer |
| `/api/session/{s}/elicit` | POST | `agent.elicit.elicit_into` | SSE; returns DRAFT ids with provenance |
| `/api/session/{s}/episode/{e}/g1` | GET | `agent.review.g1_sheet` | structured, not the Markdown |
| `/api/session/{s}/object/{id}/accept｜reject` | POST | `agent.review.accept｜reject` | human actor enforced server-side |
| `/api/session/{s}/episode/{e}/confirm-gaps` | POST | `agent.review.confirm_gaps` | |
| `/api/session/{s}/episode/{e}/transition` | POST | `kernel.lifecycle.transition` | 409 + `unsatisfied[]` on `TransitionRefused` |
| `/api/session/{s}/episode/{e}/plan` | POST | `agent.plan.propose_plan` | `approvedBy` absent by construction |
| `/api/session/{s}/plan/{p}/approve` | POST | `agent.plan.approve_plan` | human only |
| `/api/session/{s}/plan/{p}/dispatch` | POST | `agent.dispatch.dispatch` | SSE; kernel evaluate + flip |
| `/api/session/{s}/run/{r}` | GET | `agent.dispatch.read_back` | ids + copied values only |
| `/api/session/{s}/episode/{e}/readiness` | POST/GET | `kernel.readiness.readiness_report` | |
| `/api/session/{s}/episode/{e}/narrate` | POST | `agent.narrate.narrate` | 422 with the offending sentence on `UncitedSentenceError` |
| `/api/session/{s}/episode/{e}/package` | POST | `kernel.render.build_package` | `?rendering=unclassified｜full` |
| `/api/session/{s}/program/{p}/timeline` | GET | program + episodes + `EpisodeDiff`s | Demo B |
| `/api/session/{s}/program/{p}/watch` | POST | `agent.refresh_watch.detect` | proposals, not filed |
| `/api/session/{s}/program/{p}/refresh` | POST | `kernel.refresh.open_refresh` | human actor |
| `/api/settings/model` | GET/PUT | config loader (ruling R6–R8) | provider/model/base-url only |
| `/api/settings/models` | GET | `GET {base_url}/models` | live Ollama / OpenRouter list |
| `/api/settings/key` | PUT | in-memory only | never written, never returned |
| `/api/session/{s}/verify` | POST | re-run at the same seed, compare hashes | determinism affordance |

**Stores.** The two `demos/*/out/graph` directories are templates, copied into
`~/.local/share/docket/sessions/<id>/` on open, so a demo survives ten re-runs at an event
and the fixtures never mutate. "New" starts an empty graph with the default Policy.

**Model settings safety.** Provider / model / base URL persist to
`~/.config/docket/llm.json` (0600); the loader rejects a file containing `apiKey`. The key
arrives from env or one PUT, lives in process memory only, is never logged, and GET
returns `{keyPresent: true}`, never the value. A denylisted model id is refused with 409
naming the model and the reason; **the UI offers no override toggle** — the override is
`DOCKET_LLM_ALLOW_DENYLISTED=1` at the shell, so no screenshot can show us enabling one.
No provider or model name appears in proposal-facing copy.

**Determinism, shown.** Every kernel panel footer: `kernelVersion · seed · hash` in mono.
The Package screen shows `graphSnapshotHash` and the package `hash`; a `rotate-ccw`
button re-renders and displays `identical bytes ✓` or a diff. The browser computes no
displayed value; bar geometry only.

---

## 7. Demo choreography

**Demo A — CBO 2013 GCV trade study, 7 minutes.**

| Time | Screen | Beat |
|---|---|---|
| 0:00 | Home | Authority rail: `MODEL: 0 · KERNEL: 0`. Open Demo A. |
| 0:30 | Intake | Paste the request, pick the CBO source, Elicit. DRAFT objects stream in dashed, each with a page locator. |
| 1:30 | Model (G1) | Open the nine-dismount assumption: linchpin, gap, implications. Confirm, edit, accept. |
| 2:45 | Model (G1) | Approve with one gap unconfirmed → **refused**, `gaps-confirmed` named, refusal recorded. Fix, approve. |
| 3:30 | Plan | Two steps, each citing its paragraph. Agent proposed; a human approves. |
| 4:15 | Compute | Runs seal. Ranking appears — the demo's first numerals, bracketed. Flip list; squad-assumption flip distance; weight simplex. |
| 5:30 | Readiness | 21-question grid, three verdicts, blockers, gate ladder. |
| 6:30 | Package | 16 sections, unclassified/full toggle, re-render → identical hash. Download. |

**Demo B — OMFV 2019–2023, 2 minutes.** Timeline of five episodes → scrub 2020-02 →
2020-12, the manning diff (assumption becomes three numeric constraints) → 2023-03 three
sub-episodes → 3×3 grid beside GAO's, F1–F9 matrix → toggle the counterfactual repair,
`NotAssessableAtLevel` → assessable, EXE-14 1 → done.

**Proposal figures** — 4, captured at 1600 × 1000 CSS px, DPR 2, **light mode**, recorded
backend, fixed seed, by the Playwright screenshot task so they regenerate byte-stable:
F1 Authority rail + three layers · F2 the review dialog on the linchpin assumption ·
F3 what flips the decision · F4 the readiness grid. Hold the timeline as the alternate.

---

## 8. Testing and "it just works"

| Requirement | Recommendation |
|---|---|
| One command | `uv run docket ui` (the console script already exists) opens 127.0.0.1:8765 and the browser; `make demo` is a two-line alias for people who type `make` |
| Seeded on first run | On boot, if `demos/*/out/graph` is missing, run the demo builders; report progress on a splash |
| Frontend build | Vite build committed to `src/docket/ui/static/` and served by FastAPI, so no Node is needed to run — only to develop |
| Smoke tests | Playwright: one spec per screen, light only; asserts key selectors, zero console errors, and that no un-bracketed numeral appears outside a mono span |
| Viewport matrix | Every screen spec runs at 360 / 768 / 1440 px: no horizontal overflow, no clipped or overlapping elements, every interactive target ≥ 44 px |
| Brand conformance | One spec, applied to every screen. The brand's own tagline is *"Built to be checked"* and most of its rules are machine-checkable: `border-radius` is 0 everywhere · no `box-shadow` anywhere · no colour literal outside `tokens.css` · no `text-transform: uppercase` · **exactly one Ember element per screen** · no font family outside the three the brand allows |
| Health | `/api/health` polled every 15 s; header chip green / grey; click opens Settings |
| Model down | Elicit disabled with *"no backend reachable"* + one-click switch to `RecordedBackend` |
| Key missing | Inline field in Settings, labelled *"held in memory for this session; never written to disk"* |
| Denylisted model | Refusal card naming the model and the policy reason; env-var override documented, not offered |
| Backend integration | pytest against the FastAPI app with `RecordedBackend` and the Demo A store; no network in CI |

---

## 9. Out of scope for Phase I, and risks

| Out of scope | Risk | Mitigation |
|---|---|---|
| Authentication, users, roles | A reviewer reads it as a production claim | Footer: *"Single-user demonstration. Not a production authorisation system."* |
| Real classification handling | Banners could be mistaken for real markings | Persistent footer: *"All data here is public. Classification values are schema fields, not markings."* |
| PDF export, i18n | — | Markdown out; convert offline |
| LLM latency at the event | Wifi dies mid-demo | `LIVE / RECORDED` switch in the header, labelled on screen; recorded is the default at the venue |
| Frontend drifting from the 39 types | Silent shape mismatch | TS types generated from the committed JSON Schemas at build |
| Per-question reading of GAO-23-106549 | Overclaim | Standing caption on the Readiness screen: *"GAO-23-106549 states nine section×dimension verdicts in prose, not as a grid and not as per-question labels. The 3×3 arrangement and the per-question layer here are ours. GAO did not assess or verify the Army's underlying analytical work."* |
| Naming | Slip back to DoD | Copy lint in CI: `DoW` outside document titles | <!-- dow-lint: allow -->

---

## 10. Open decisions for Shreyash

1. ~~**Ember hex conflict in the handoff.**~~ **Settled 2026-09-08: `#FF6A00`.** The conflict survives in v3.0 and is still unresolved upstream; docket picks the better-supported reading and writes it into both its own files. Flag it to the brand owner. See `docs/decisions/2026-09-08-ember-is-ff6a00.md`.
2. **Branding in proposal figures.** OffGrid wordmark visible in the screenshots, or unbranded product UI? Bears on the data-rights posture.
3. ~~**Light or dark for the four figures.**~~ **Settled 2026-09-08: light, and light is now the only mode the UI has.** See `docs/decisions/2026-09-08-demo-ui-is-light-only.md`.
4. **The event.** Date, projector resolution, and whether there is usable internet — decides whether `RECORDED` ships as the default.
5. **Does any figure show a model name?** A Settings screenshot would reveal e.g. a local model id. Recommend masking the field in proposal figures; confirm.
