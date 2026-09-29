// Shared assertion helpers for every screen spec (plan 07 Task 9). `@playwright/test` was
// not installed in this worktree when Part A wrote this file's first half (no network
// access at the time — see `README.md` for the install line); Part B (this addition) runs
// against the real, installed package.
//
// Scope: this file owns (1) the cross-cutting checks plan 07 Task 9 Step 4 lists as
// common to every screen (console errors, the numeral walk, the two footer sentences,
// the provider/model-string ban, the denylist-override ban); (2) the theme parameter
// (`forEachViewport`), so every screen spec runs at 360, 768 and 1440 px without
// hand-duplicating its test bodies; and (3) `openDemoASeeded` (moved up
// from Task 10 — Task 9 Part B is what actually builds it, since it needs the live G1
// round trip Task 9 Part B proves out). The screen specs already in `ui/e2e/`
// (`evidence.spec.ts`, `timeline.spec.ts`, `package.spec.ts`, `settings.spec.ts`) each
// bootstrap their own session through the visible `SessionPicker` instead of using
// `openDemoASeeded`, on purpose (see their header comments) — nothing here assumes they
// were rewritten to use it.

import { readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { expect, test, type APIResponse, type Page } from '@playwright/test';
import { elicitRecorded } from './_elicit';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const FOOTER_SOURCE = path.join(HERE, '..', 'src', 'components', 'Footer.tsx');

// ---- console errors --------------------------------------------------------------------

/**
 * Start collecting console errors and uncaught page exceptions for `page`. Returns the
 * live array — call this once per test, before navigating, then assert it is empty
 * after the interactions under test have run (plan Step 4.2: "zero console errors
 * (`page.on('console')` collected and asserted empty)").
 *
 * `pageerror` (an uncaught exception) is collected alongside `console` `error` messages,
 * not just the latter: a component that throws during render is a more serious failure
 * than a logged error and must not pass this check by virtue of never having called
 * `console.error` itself.
 */
export function collectConsoleErrors(page: Page): string[] {
  const errors: string[] = [];
  page.on('console', (msg) => {
    if (msg.type() === 'error') errors.push(msg.text());
  });
  page.on('pageerror', (err) => {
    errors.push(err.message);
  });
  return errors;
}

// ---- the numeral walk -------------------------------------------------------------------

// `YYYY-MM-DD`, optionally followed by a full timestamp — the shape the kernel itself
// stores (`createdAt`, `asOf`, ...; see `docket.canon`/every object's `createdAt`
// field) — OR the bare `YYYY-MM` a citation's own `published` field carries when a
// source states only a month and year (`schema/objects.yaml`'s `Evidence.published` is
// an unconstrained string — whatever precision the source gives; plan 07 Task 9 Part B
// found "2013-04" unmarked on the Evidence screen). The day-and-time suffix is
// optional for exactly this reason; the hyphen is what keeps this from also matching a
// bare four-digit number that has nothing to do with a date. Not a numeral the UI is
// asserting, so it is stripped before the digit check.
const ISO_DATE_RE = /\b\d{4}-\d{2}(?:-\d{2}(?:T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z?)?)?\b/g;

// Kernel/graph object ids: a lowercase word, then one or more hyphen-joined alnum
// segments — `ep-cbo-2013`, `pl-cbo`, `mdl-1`, `alt-x`, `ws-1`, `gap-v`,
// `ep-omfv-2020-02-r5`, `s-4f9c2a1b3d7e` (a session id). These are identifiers, not
// numbers the UI computed, so they are stripped alongside ISO dates. Deliberately
// case-insensitive and deliberately not exhaustive — see the module docstring above and
// the task report for what this does not yet cover (e.g. a bare truncated hex hash with
// no hyphen, such as a package hash's first 12 characters).
const OBJECT_ID_RE = /\b[a-z]+(?:-[a-z0-9]+)+\b/gi;

// The gap this module's own header flagged: "a bare truncated hex hash with no hyphen,
// such as a package hash's first 12 characters" (`Package.tsx`'s `pkg.hash`/
// `pkg.graphSnapshotHash` — no spec had exercised this helper against a screen that
// prints one until plan 07 Task 7's `compute.spec.ts`). A hash is an identifier for a
// run or a build, not a value a reviewer would do arithmetic on — the same category
// `OBJECT_ID_RE` already exempts, just without a hyphen to key on.
//
// Requires at least one `a`-`f` letter alongside the digits (not just `\d{8,}`):
// `docket`'s own seeds are plain decimal (Demo A's is `20130430`, an 8-digit run
// seed with zero hex letters) and must still trip this check if ever printed bare —
// `RunSeal.tsx`/`Simplex.tsx` mark those spans `data-num="label"` instead of relying on
// this regex, precisely so a real un-bracketed decimal number is never accidentally
// swallowed by a fix aimed at hex hashes.
//
// Trailing boundary `(?![0-9a-z])` (fix round 1, M1): without it, an 8+ digit decimal
// immediately followed by lowercase letters in `a`-`f` — "12345678billion" — let the
// greedy `[0-9a-f]{8,}` swallow the leading `b` of "billion" too (a genuine hex-class
// character), matching "12345678b" and leaving only "illion" behind, hiding a real
// numeral. The lookahead forces the match to end where the hex-class run actually
// ends, at a boundary the next character cannot extend, so a decimal glued to `a`-`f`
// letters is no longer swallowed with them; the true residual case ("n 12345678f" — a
// decimal immediately followed by exactly one hex letter and then a non-hex character)
// is inherent to the exemption (that token is genuinely indistinguishable from a short
// hash) and is documented here rather than chased further.
const HEX_HASH_RE = /\b(?=[0-9a-f]*[a-f])[0-9a-f]{8,}…?(?![0-9a-z])/gi;

/**
 * Plan Step 4.3: "no un-bracketed numeral outside a mono span." Walks
 * `document.body.innerText`, excludes every `[data-num]` element's text (the one
 * component allowed to print a digit that came from the API — `ui/src/components/
 * Num.tsx`'s own header comment; the attribute-presence selector `[data-num]` already
 * matches an explicitly labelled `data-num="label"` exception the same way, since a CSS
 * attribute selector with no `=value` matches any value), strips ISO dates, object ids
 * and bare hex hashes from what remains, and fails if a digit is still present anywhere
 * in the result.
 *
 * **Not** `document.body.cloneNode(true)` then `.innerText` on the clone (an earlier
 * version of this function, plan 07 Task 9 Part A) — `innerText` is a *rendered*
 * property: it depends on layout to know where a block boundary puts a line break, and
 * a cloned node that was never attached to the document has no layout at all. Confirmed
 * live (Chromium, a detached clone of a real page): two adjacent `<dt>`/`<dd>` pairs
 * that the live, attached page renders as `"DATE\n2013-04\nPUBLISHER\n..."` came back
 * from the detached clone's `.innerText` as `"date2013-04publisher..."` — concatenated
 * with no separator at all, which also silently defeated the very `\b` word-boundary
 * anchor every regex below depends on (`\b` cannot find a boundary between two `\w`
 * characters, and a digit is one). Every screen this walk has ever run against was
 * exposed to this, not just the one that happened to surface it (plan 07 Task 9 Part
 * B, extending this walk to `evidence.spec.ts`, which is where two block-level `[data-
 * num]`-free values ended up adjacent with nothing else between them for the first
 * time).
 *
 * Fixed by reading `innerText` off the LIVE body instead, with `[data-num]` elements
 * actually REMOVED (not `display: none` — tried that first; Chromium's `innerText`
 * does not honour `display: none` on an `<option>` at all, confirmed live: hiding
 * Intake's `data-num="label"`-marked `<option>`s left their text in `innerText`
 * completely unchanged, because a closed `<select>`'s options are not part of normal
 * layout to begin with) and reinserted at their exact original position immediately
 * after — non-destructive to the live page (any subsequent assertion in the same test
 * still sees the real DOM), and correct for every element kind, not only the ones CSS
 * `display` actually hides.
 */
export async function assertNoUnbracketedNumerals(page: Page): Promise<void> {
  const raw = await page.evaluate(() => {
    const marked = Array.from(document.querySelectorAll<HTMLElement>('[data-num]'));
    const anchors = marked.map((el) => ({ parent: el.parentNode, next: el.nextSibling }));
    marked.forEach((el) => el.remove());
    const text = document.body.innerText;
    // Reinsert in REVERSE document order, not forward: two `[data-num]` elements can
    // be adjacent siblings, in which case the first one's recorded `next` IS the
    // second one — which is itself still detached at that point in a forward loop,
    // and `insertBefore` throws ("not a child of this node"). Walking backward means
    // the second one is already back in the tree by the time the first one needs it
    // as a reference.
    for (let i = marked.length - 1; i >= 0; i--) {
      anchors[i].parent?.insertBefore(marked[i], anchors[i].next);
    }
    return text;
  });
  // Object ids FIRST, not `ISO_DATE_RE` first (fix round, plan 07 Task 9 Part B):
  // `OBJECT_ID_RE`'s own extended-with-`YYYY-MM` form now matches a bare `\d{4}-\d{2}`
  // substring — and an episode id like `ep-omfv-2020-02-r5` CONTAINS exactly that shape
  // in its middle. Stripping dates first removed only "2020-02" out of the id, leaving
  // "ep-omfv--r5" behind (a double hyphen `OBJECT_ID_RE` no longer matches as one
  // token), with a real digit surviving in the residue. Stripping whole object ids
  // first removes the id in one piece before the date regex ever sees a chance to
  // carve a hole in the middle of one.
  const stripped = raw.replace(OBJECT_ID_RE, '').replace(ISO_DATE_RE, '').replace(HEX_HASH_RE, '');
  const match = stripped.match(/\d/);
  if (match) {
    const idx = stripped.indexOf(match[0]);
    const context = stripped.slice(Math.max(0, idx - 40), idx + 40).replace(/\s+/g, ' ');
    throw new Error(
      `un-bracketed numeral found outside [data-num] (and not an ISO date or object id): ` +
        `"…${context}…"`,
    );
  }
}

// ---- the footer -----------------------------------------------------------------------

/**
 * Read the two mandated sentences straight out of `ui/src/components/Footer.tsx` rather
 * than retyping them here — a screen's spec must fail if the footer's actual, rendered
 * text ever drifts from that file, not merely if it drifts from a second, hand-copied
 * string a future edit could update in one place and forget in the other.
 */
function footerSentences(): [string, string] {
  const src = readFileSync(FOOTER_SOURCE, 'utf-8');
  const matches = [...src.matchAll(/<p[^>]*>([^<]+)<\/p>/g)].map((m) =>
    m[1].replace(/\s+/g, ' ').trim(),
  );
  if (matches.length < 2) {
    throw new Error(
      `expected two <p> sentences in ${FOOTER_SOURCE}, found ${matches.length}; ` +
        `Footer.tsx's shape changed and this helper needs updating`,
    );
  }
  return [matches[0], matches[1]];
}

/** Plan Step 4.4: "the two footer sentences are present." Persistent on every screen —
 * see `Footer.tsx`'s own header comment ("Honesty and safety in the UI #4"). */
export async function assertFooterSentences(page: Page): Promise<void> {
  const [first, second] = footerSentences();
  await expect(page.getByText(first, { exact: false })).toBeVisible();
  await expect(page.getByText(second, { exact: false })).toBeVisible();
}

// ---- no provider/model string on proposal-facing screens ------------------------------

// Deliberately conservative substrings for known LLM providers and model families —
// this list, not `docket.agent.backend.DENYLIST_FAMILIES`, because the rule here is
// broader than the PRC-origin policy: NO concrete provider or model name belongs in
// proposal-facing copy at all (ledger ruling, `progress.md`: "no concrete model name
// anywhere in proposal-facing copy"), allowed or not.
const PROVIDER_MODEL_RE =
  /\b(openai|anthropic|claude|ollama|openrouter|openai-compatible|gpt-?\d|llama-?\d|mistral|gemini|gemma\d|qwen|deepseek)\b/i;

/**
 * Plan Step 4.5: "no provider or model string is present on the seven proposal-facing
 * screens." Callers apply this only to those seven screens (Home, Intake, Model, Plan,
 * Compute, Readiness, Package) — Settings is the one screen where a provider/model
 * string is the whole point (picking one), so it must never be run there.
 */
export async function assertNoProviderStrings(page: Page): Promise<void> {
  const text = await page.evaluate(() => document.body.innerText);
  const match = text.match(PROVIDER_MODEL_RE);
  if (match) {
    throw new Error(`provider/model string "${match[0]}" found in visible page text`);
  }
}

// ---- no denylist-override control -------------------------------------------------------

const OVERRIDE_CONTROL_RE = /allow.?denylist/i;

/**
 * Plan Step 4.6: "no control matching `/allow.?denylist/i` exists anywhere." Checked
 * against the whole rendered DOM (not just interactive elements), matching "anywhere"
 * literally — `DOCKET_LLM_ALLOW_DENYLISTED` is an environment variable for local
 * testing only (`agent.backend.check_model_policy`'s own docstring) and must never be
 * exposed as a UI affordance, in any form, on any screen.
 */
export async function assertNoOverrideControl(page: Page): Promise<void> {
  const html = await page.content();
  if (OVERRIDE_CONTROL_RE.test(html)) {
    throw new Error('a control matching /allow.?denylist/i was found in the page');
  }
}

// ---- theme parameter (plan Step 4: "in BOTH themes") -------------------------------------

// ---- viewport parameter (design §5a: fluid to 360px) --------------------------------

/** The three widths every screen spec runs at. 360 is the narrow-phone floor §5a commits
 * to; 768 is where the shell swaps its sidebar for a step strip; 1440 is the `smoke`
 * project's own default and what the demo is actually shown at. */
export const VIEWPORTS = [
  {name: 'phone', width: 360, height: 780},
  {name: 'tablet', width: 768, height: 1024},
  {name: 'laptop', width: 1440, height: 900},
] as const;

export type Viewport = (typeof VIEWPORTS)[number];
export type ViewportName = Viewport['name'];

/**
 * Wraps `body` (a screen spec's `test(...)` calls) in one `test.describe` per viewport,
 * sizing the page in `beforeEach` so the size is set before the test body's own
 * `page.goto`.
 *
 * Replaces `forEachTheme`. The UI is light-only
 * (`docs/decisions/2026-09-08-demo-ui-is-light-only.md`), so theme is no longer an axis;
 * width is, and it is the axis that can actually regress silently. Same wrapper shape as
 * `forEachTheme` had, so a spec opts in by wrapping exactly as before.
 */
export function forEachViewport(body: (viewport: Viewport) => void): void {
  for (const viewport of VIEWPORTS) {
    test.describe(viewport.name, () => {
      test.beforeEach(async ({page}) => {
        await page.setViewportSize({width: viewport.width, height: viewport.height});
      });
      body(viewport);
    });
  }
}

// ---- the seeded walk (plan 07 Task 9 Part B / Task 10) ------------------------------------

/** One human-authored sentence for the one AR 5-11 field the committed source document
 * never states (`Charter.consequencesOfErroneousOutput` — see `openDemoASeeded`'s own
 * header comment on why accepting the charter must supply it). Content, not a
 * decoration: `tests/agent/test_review.py` establishes the identical pattern
 * (`accept(g, charter_id, H, now=NOW, consequencesOfErroneousOutput=...)`) as the way
 * this repository already reaches `MODEL_APPROVED` on this exact fixture — a human
 * filling a gap the source is silent on, with their own judgement, is what "accept"
 * being human-authored is *for*, not a shortcut around it. */
const CONSEQUENCE_A_HUMAN_SUPPLIES = (
  'Industry designs to characteristics the Army does not actually need, or a '
  + 'solicitation the Army must revise after industry comment, delaying the OMFV program.'
);

interface G1Object {
  id: string;
  type: string;
}

interface G1Sheet {
  objects: G1Object[];
  gaps: { id: string }[];
}

/** The one field this file reads off `GET /session/{s}/episode/{e}` that `ElicitBody`
 * (`_elicit.ts`) does not carry — `episode_view`'s full `DecisionEpisode` has plenty
 * more, but `objectives: string[]` (`DecisionEpisode.objectives: {ref: Objective}[]`)
 * is the only one the Weights step below needs. */
interface EpisodeObjectives {
  objectives: string[];
}

/** Equal weight per objective, remainder folded into the first id so the total is
 * exactly `1` — `check_weights`'s own tolerance is `1e-6`, tighter than naive floating
 * division across an odd count (nine objectives on the OMFV request text) would land
 * on its own. Computed here, in the test's own fixture code, not in the product: this
 * is "the fixture's numbers", typed into the request the same way a human would type
 * nine numbers that happen to be equal, not the browser doing arithmetic on a human's
 * behalf (the Weights panel itself does none — see `WeightsPanel.tsx`'s own header). */
function equalWeights(objectiveIds: string[]): Record<string, number> {
  const share = 1 / objectiveIds.length;
  const weights = Object.fromEntries(objectiveIds.map((oid) => [oid, share]));
  const total = Object.values(weights).reduce((a, b) => a + b, 0);
  weights[objectiveIds[0]] += 1 - total;
  return weights;
}

export interface DemoASeededResult {
  sessionId: string;
  /** The freshly-elicited episode this walk drove — never `ep-cbo-2013` (Demo A's own
   * seeded episode, also present in this session, at `PENDING_SIGNATURE`, and the only
   * place an id like `as-nine-squad` exists — see the header comment below). */
  episodeId: string;
  /** The lifecycle state this walk actually reached on `episodeId`. */
  reachedState: 'DRAFT' | 'MODEL_APPROVED';
  /** The id of the `WeightSet` this walk authored through the new route
   * (`ws-{episodeId}-human` — `docket.agent.plan._weight_set_id`'s convention),
   * `null` only if that step itself failed (it should not; a refusal there throws
   * rather than degrading to a `stoppedAt`, the same posture step 6 already takes for
   * the G1 transition). */
  weightSetId: string | null;
  /** `null` once every step below completes; otherwise the name of the first step that
   * could not, so a caller can decide what to do rather than guess from a thrown error. */
  stoppedAt: 'plan-propose' | null;
  /** The server's own words for why, verbatim, when `stoppedAt` is not `null`. */
  stopReason: string | null;
}

async function expectOk(response: APIResponse, what: string): Promise<APIResponse> {
  if (!response.ok()) {
    throw new Error(`${what}: HTTP ${response.status()} — ${await response.text()}`);
  }
  return response;
}

/**
 * The seeded walk plan 07 Task 10 needs, built here (Task 9 Part B) because getting it
 * past G1 needed two fixes only this task's investigation surfaced — see
 * `task-9b-report.md` for the reproduction of both:
 *
 * 1. **A session opened from Demo A, then a live elicitation against the committed
 *    recording, mints a SECOND episode** alongside Demo A's own seeded one
 *    (`ep-cbo-2013`, already at `PENDING_SIGNATURE`). `Intake.tsx`'s `elicit()` always
 *    posts a fresh episode regardless of what the session already holds. This is
 *    deliberate, not a limitation: Demo A's own seeded episode is where
 *    `chip-as-nine-squad` and every other figure that needs Demo A's *actual* GCV
 *    content lives (`demos/a_cbo_gcv_2013/build.py`, never elicited — built directly);
 *    the fresh episode this function drives is where a *live* G1→G2 round trip can be
 *    demonstrated end to end. One session, both episodes, selectable by id.
 * 2. **G1 approval needs one server-side fix this task made** (`src/docket/api/
 *    routes/agent.py`'s `post_elicit`, `src/docket/api/sessions.py`'s
 *    `default_policy_json`, `src/docket/api/config.py`'s `RECORDED_REQUEST_POLICY`):
 *    the committed recording's response is hashed under policy id `"pol-1"` — no
 *    session (new or demo-sourced) ever seeds a Policy at that id — so eliciting
 *    against it always wrote a Charter whose `decisionClassPolicy` pointed nowhere,
 *    which `kernel.validate`'s `ref-integrity` rule reports as a BLOCKING structural
 *    finding, which refuses G1 approval on `no-blocking-structural` forever, on every
 *    session, regardless of what a human does at the gate. Confirmed live (`curl`
 *    against a throwaway server) before touching any code, and confirmed again after:
 *    `no-blocking-structural` was the *only* unsatisfied check once gaps were
 *    confirmed and the charter/assumption were accepted.
 *
 * With both fixed, this function reaches **`MODEL_APPROVED`** — every G1 check
 * satisfied by a real human action, read back from the server's own transition record,
 * not asserted from the client.
 *
 * **The WeightSet gap this file's own comment used to document here is closed**
 * (plan 07 "weights" task): `POST /session/{s}/episode/{e}/weights`
 * (`docket.agent.plan.author_weight_set`) now exists, and this function calls it —
 * equal weight per objective (`equalWeights`, above), typed as the fixture's own
 * numbers, with a `name` and a `rationale` — exactly the route's happy path
 * `tests/api/test_agent_routes.py` already covers. This step succeeds and
 * `weightSetId` is always populated; a refusal here throws rather than degrading to a
 * `stoppedAt`, the same posture step 6 already takes for the G1 transition.
 *
 * **Where the walk stops now is a DIFFERENT, deeper finding, confirmed live** (a
 * throwaway `docket ui` process, this exact sequence, before writing this comment —
 * not predicted): with a `WeightSet` on record, `propose_plan` gets past the check
 * this task closed and into `_skeleton_steps`, which must then resolve an `evaluator`
 * for the one step it builds (`_select_evaluator`) — from `episode["models"]`, which
 * is **empty**, because `agent.elicit` never writes a `Model` object either (the same
 * module-header sentence this comment used to quote continues: elicitation "produces
 * no Observation, WeightSet, ..." — Model is a third thing on that list, not
 * previously load-bearing for this function until the WeightSet gap was the only
 * thing in front of it). `_select_evaluator` refuses by name
 * ("cannot choose an evaluator for step ...: episode models [], models whose inputs
 * cover [...]: []. A human must name the evaluator; the agent will not pick between
 * models.") — a `ValidationError`, 422, raised before `propose_plan` ever calls a
 * backend, so this is NOT a `RecordingMissing`/recorded-fixture problem: it fires
 * whether or not `tests/fixtures/recorded/plan.json`'s key would have matched this
 * episode's own authority-citation prompt (it would not have — that fixture is keyed
 * to Demo A's own `pl-cbo` step ids and measures — but the evaluator refusal happens
 * first regardless, so the recording question is moot here). No route anywhere in
 * `src/docket/api/` lets a human name an evaluator or author a `Model` object either
 * (`ProposePlanRequest` takes only `planId`/`now`) — closing that gap is a Model-
 * authoring route's job, not this task's, so this function stops here, honestly,
 * rather than fabricate a `Model` object outside the API surface to push past it.
 *
 * `stoppedAt: 'plan-propose'` (the same call as before — the reason underneath it
 * changed, not which step this is), `stopReason` carrying the server's own 422 message
 * verbatim. `propose`/`approve` the plan, `dispatch` at seed 0, `readiness`, and
 * `render the package` — the rest of Task 10's aspirational sequence — remain
 * UNREACHABLE on a live-elicited episode until a Model/evaluator-naming route exists,
 * on this fixture or any other; a figure that needs those states must still draw them
 * from Demo A's own seeded episode (`ep-cbo-2013`, already `PENDING_SIGNATURE` with
 * sealed runs and a `ReadinessReport` on record — see `plan.spec.ts`/
 * `compute.spec.ts`/`readiness.spec.ts`'s own header comments, which independently
 * reach the same conclusion about that episode).
 *
 * Recorded mode only (`DOCKET_UI_MODE=recorded`, as the shared `webServer` always runs)
 * — the "seeded" in the name is the dispatch seed this function would use if it ever
 * got that far (`0`, per the plan), not a claim about determinism reached today.
 */
export async function openDemoASeeded(page: Page): Promise<DemoASeededResult> {
  // 1–2. A session from Demo A; elicit against the committed recording.
  const body = await elicitRecorded(page, 'demo-a');
  const sessionId = await page.evaluate(() => sessionStorage.getItem('docket-session-id'));
  if (!sessionId) throw new Error('openDemoASeeded: no session id after eliciting');
  const episodeId = body.episode.id;

  const g1Res = await expectOk(
    await page.request.get(`/api/session/${sessionId}/episode/${episodeId}/g1`),
    'openDemoASeeded: reading the G1 sheet',
  );
  const g1 = (await g1Res.json()) as G1Sheet;

  const charter = g1.objects.find((o) => o.type === 'Charter');
  if (!charter) throw new Error('openDemoASeeded: the elicited episode has no Charter');
  const assumptions = g1.objects.filter((o) => o.type === 'Assumption');

  // 3. Confirm every gap this episode reaches — one call, matching what the Model
  //    screen's "Confirm gap" button does per gap (`review.confirm_gaps` signs every
  //    unconfirmed gap in scope at once; there is no partial form of this action).
  await expectOk(
    await page.request.post(`/api/session/${sessionId}/episode/${episodeId}/confirm-gaps`, {
      data: {},
    }),
    'openDemoASeeded: confirming gaps',
  );

  // 4. Accept the charter — WITH the one field the source never states supplied as a
  //    human edit (see `CONSEQUENCE_A_HUMAN_SUPPLIES`'s own comment). The Model screen's
  //    review dialog now offers a box to type this field into (the charter-editing gap
  //    plan 07 Task 10 found — `model.spec.ts`/`choreography.spec.ts` drive it by
  //    clicking, through `ReviewDialog`'s `charterFields`), so this is no longer the
  //    only path to it. This helper still calls the accept route directly rather than
  //    clicking through the form: it is a fast, deterministic fixture for figures and
  //    other specs, not a proof that a human can do this in a browser — the same
  //    reason the surrounding steps (confirming gaps, authoring the weight set) also
  //    call their routes directly rather than driving the DOM. `tests/agent/
  //    test_review.py` establishes the identical `accept(..., **edits)` pattern
  //    server-side.
  await expectOk(
    await page.request.post(`/api/session/${sessionId}/object/${charter.id}/accept`, {
      data: { edits: { consequencesOfErroneousOutput: CONSEQUENCE_A_HUMAN_SUPPLIES } },
    }),
    'openDemoASeeded: accepting the charter',
  );

  // 5. Accept every Assumption (this fixture's one Assumption is the linchpin
  //    `linchpins-human` reads; accepting a non-linchpin would be equally harmless, so
  //    this does not special-case which one it is).
  for (const assumption of assumptions) {
    await expectOk(
      await page.request.post(`/api/session/${sessionId}/object/${assumption.id}/accept`, {
        data: {},
      }),
      `openDemoASeeded: accepting assumption ${assumption.id}`,
    );
  }

  // 6. Approve G1. Every check above should now be satisfied; a refusal here is NOT the
  //    documented, expected stop — it means one of the five G1 checks regressed, so
  //    this throws rather than degrading to a `stoppedAt`.
  const approveRes = await expectOk(
    await page.request.post(`/api/session/${sessionId}/episode/${episodeId}/transition`, {
      data: { to: 'MODEL_APPROVED' },
    }),
    'openDemoASeeded: approving G1 (transition to MODEL_APPROVED)',
  );
  const approved = (await approveRes.json()) as { lifecycleState: string };
  if (approved.lifecycleState !== 'MODEL_APPROVED') {
    throw new Error(
      `openDemoASeeded: expected MODEL_APPROVED after transition, got ${approved.lifecycleState}`,
    );
  }

  // 7. Author the WeightSet propose_plan needs — the gap this task closed. A human
  //    value judgement, typed here as equal weight per objective (`equalWeights`,
  //    above); the panel a real operator would type these into is `WeightsPanel.tsx`
  //    on the Plan screen — this call is the same route it posts to, driven directly
  //    for the same reason step 4 drives `accept` directly (no screen control needed
  //    to prove the walk; the panel's own choreography is `plan.spec.ts`'s concern).
  const epRes = await expectOk(
    await page.request.get(`/api/session/${sessionId}/episode/${episodeId}`),
    'openDemoASeeded: reading the episode for its objectives',
  );
  const { objectives } = (await epRes.json()) as EpisodeObjectives;
  if (objectives.length === 0) {
    throw new Error('openDemoASeeded: the elicited episode has no Objectives to weigh');
  }
  const weightsRes = await expectOk(
    await page.request.post(`/api/session/${sessionId}/episode/${episodeId}/weights`, {
      data: {
        name: 'equal weights',
        weights: equalWeights(objectives),
        rationale: 'no source document weighs these objectives; equal weight until one does',
      },
    }),
    'openDemoASeeded: authoring the WeightSet',
  );
  const weightSet = (await weightsRes.json()) as { id: string };

  // 8. Propose the plan — the documented stop, one step later than before this task's
  //    WeightSet route landed. See this function's own header comment for exactly why.
  const planRes = await page.request.post(`/api/session/${sessionId}/episode/${episodeId}/plan`, {
    data: {},
  });
  if (planRes.ok()) {
    // Not reachable today (no route lets a human name an evaluator, or author a
    // Model, for a freshly elicited episode) — left in, not dead code, so a future
    // Model/evaluator route makes this walk complete automatically instead of
    // silently stopping one step early forever.
    throw new Error(
      'openDemoASeeded: propose_plan unexpectedly SUCCEEDED — a Model/evaluator route ' +
        'now exists; extend this function past MODEL_APPROVED (approve the plan, ' +
        'dispatch at seed 0, compute readiness, render the package) instead of ' +
        'stopping here',
    );
  }
  const planBody = (await planRes.json().catch(() => ({}))) as { message?: string };
  return {
    sessionId,
    episodeId,
    reachedState: 'MODEL_APPROVED',
    weightSetId: weightSet.id,
    stoppedAt: 'plan-propose',
    stopReason: planBody.message ?? `HTTP ${planRes.status()}`,
  };
}
