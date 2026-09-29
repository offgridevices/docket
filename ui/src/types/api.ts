// Hand-written route types — the shapes that come back over the wire, as opposed to
// ui/src/types/objects.d.ts (generated from the committed JSON Schemas). These are kept
// separate on purpose: a route's envelope (an HTTP status, an error code, a resolved
// slot) is server plumbing this UI owns, not an object shape the kernel authors, so it
// does not belong in the generated file and should not be regenerated out from under a
// hand-edit.
//
// Written against the plan's own route contracts (Tasks 1, 2 and 4) ahead of those
// routes landing, so Task 5 has something to type against; re-verify each shape here
// the first time a screen actually calls the route (Tasks 6-8), since the plan text is
// the design, not a guarantee the implementation didn't have to adjust en route.

import type { AuthorType } from '../lib/provenance';
import type {
  DecisionEpisode,
  DecisionPackage,
  DecisionProgram,
  EpisodeDiff,
  Evidence,
  MandateScorecard,
  ReadinessReport,
  RefreshTrigger,
  StandardsAssessment,
} from './objects';

/** One entry of `GET /api/settings/models` (src/docket/api/routes/settings.py
 * `_normalize_models`) — also what `GET /api/health`'s own `backend.models` carries,
 * since both call `list_models` under the hood. `reason` (T8 fix round, ruling M1) is
 * present only on a `denylisted: true` entry — the name of the policy family the id
 * matched, e.g. `` `model id matches denylisted family 'qwen' (policy P8)` `` — and
 * never the override hint (`DOCKET_LLM_ALLOW_DENYLISTED`), which stays CLI-only. */
export interface ModelEntry {
  id: string;
  denylisted: boolean;
  reason?: string;
}

/** `GET /api/health` (src/docket/api/routes/health.py). `configRefused`/
 * `configRefusedMessage` (T2 fix round, ruling I4): a malformed `llm.json` degrades the
 * probe to a neutral recorded/no-backend guess rather than 500ing the one endpoint the
 * whole UI polls to decide whether anything works — honesty rule 8 ("refusals are
 * shown, not hidden") applies to the health check too. */
export interface HealthResponse {
  kernelVersion: string;
  provider: string;
  model: string;
  baseUrl: string;
  keyPresent: boolean;
  backend: {
    reachable: boolean;
    models: ModelEntry[];
    error: string | null;
  };
  denylistActive: boolean;
  denylistOverride: boolean;
  mode: 'live' | 'recorded';
  demoStores: Record<string, boolean>;
  actorId: string;
  sessions: number;
  configRefused: boolean;
  configRefusedMessage: string | null;
}

/** `GET /api/session/{s}/episode/{e}/authority` (src/docket/api/authority.py) — the
 * authority rail's numbers, computed server-side. `numerals.agent` is always 0; the
 * counter exists to show that, not to warn that it might not be. */
export interface AuthorityCounts {
  episode: string;
  objects: { human: number; agent: number; kernel: number };
  numerals: { human: number; agent: number; kernel: number };
  agentForbiddenWrites: number;
  kernelVersion: string;
  explanation: string;
}

/** One rung of `episode_view(g, eid).gateLadder` (src/docket/api/serialize.py). Built
 * from `kernel.lifecycle.CHECKS`/`EDGES` on the server so the UI never restates the
 * check list and cannot disagree with the gate it is drawing. */
export interface GateRung {
  to: string;
  state: 'passed' | 'available' | 'blocked';
  /** `whatWouldSatisfy` is the check's own first docstring line, served verbatim
   * (`kernel.queue.what_would_satisfy`) — the same sentence the Needs queue prints, so
   * a ladder and a queue can never describe the same predicate differently. */
  checks: { name: string; satisfied: boolean; whatWouldSatisfy: string }[];
  humanOnly: boolean;
}

/** The shape every route's error handler produces (plan Task 1 Step 7's exception
 * table). `error` is the machine-readable code (`"transition-refused"`,
 * `"authority-violation"`, …); the rest of the fields vary by code. */
export interface ApiErrorBody {
  error: string;
  message?: string;
  unsatisfied?: string[];
  errors?: unknown;
  sentence?: string;
  [extra: string]: unknown;
}

/** One SSE event, as emitted on `/api/stream/{session}` (plan Task 3). The event
 * names are fixed by the design spec §6: `stage`, `object`, `finding`, `done`, `error`. */
export type StreamEvent =
  | { event: 'stage'; data: { stage: string; status: 'started' | 'finished'; detail?: string } }
  | {
      event: 'object';
      data: {
        id: string;
        type: string;
        authorType: 'agent';
        confidence?: string;
        provenance?: Record<string, unknown>;
        summary?: string;
      };
    }
  | { event: 'finding'; data: { rule: string; severity: string; objects: string[]; message: string } }
  | { event: 'done'; data: { stage: string; ids: string[]; episode?: string } }
  | { event: 'error'; data: { error: string; message: string } };

// ---- session (src/docket/api/routes/session.py, sessions.py) -------------------------

/** `POST /api/session` and one entry of `GET /api/sessions`. */
export interface SessionInfo {
  id: string;
  source: string;
  created: string;
}

/** `episode_view(g, eid)` (src/docket/api/serialize.py) — the stored `DecisionEpisode`
 * plus the gate ladder, resolved reference counts and the readiness report id, spread
 * over the raw object so every catalogue field is still present. `DecisionEpisode`
 * itself (ui/src/types/objects.d.ts) already declares `readiness`/`transitions`; this
 * only adds the two fields `episode_view` computes that are not in the schema. */
export type EpisodeView = DecisionEpisode & {
  gateLadder: GateRung[];
  counts: Record<string, number>;
};

// ---- objects and slots (src/docket/api/serialize.py: slot_view, object_view) ---------

export type SlotKind = 'content' | 'gap' | 'exclusion';

/** One entry of `object_view(...).slots` — present **only** for a field whose current
 * value is a `$gap`/`$exclusion` marker (`slot_view` is applied after `iter_slots`
 * already filtered to markers). A slot field holding real content never appears here;
 * `resolveSlot` (ui/src/components/Slot.tsx) is what tells the two cases apart for a
 * given field path. `path` uses `/` to join nested segments and array indices exactly
 * as `docket.objects.iter_slots` builds them, e.g. `"limitations/0/impact"`. */
export interface SlotEntry {
  path: string;
  kind: 'gap' | 'exclusion';
  target: string | null;
  targetObject: unknown;
}

/** A JSON tree shaped like `object`, but every numeric leaf holding its own `str()`
 * text form instead of a number — `object_view`'s `_value_text` (plan 07 Task 7 fix
 * round, I2). Recursive rather than a flat map because a value can sit one level
 * inside a nested field (`FlipAnalysis.range.{lo,hi}`). */
export type ValueTextTree = { [key: string]: string | ValueTextTree };

/** `GET /api/session/{s}/object/{id}` (src/docket/api/serialize.py `object_view`). */
export interface ObjectView {
  id: string;
  rev: number;
  type: string;
  object: Record<string, unknown>;
  authorType: AuthorType;
  authorId: string | null;
  confidence: string | null;
  provenance: { extractedAt: string; extractor: string; locator: string; sourceArtifact: string } | null;
  slots: SlotEntry[];
  revisions: number[];
  referencedBy: string[];
  /** Additive, next to `object`, never inside it — `view.object` stays exactly what
   * the graph stored. */
  valueText: ValueTextTree;
}

// ---- evidence register (src/docket/api/routes/kernel.py get_evidence) ----------------

export interface ScopeFinding {
  rule: string;
  severity: 'blocking' | 'warning' | 'info';
  objects: string[];
  message: string;
}

/** `_claims_citing_evidence`'s per-item entry — `reuseJustification`/`assessableAt`
 * live on the *Claim* that cites the evidence (`supportedBy[]`), not on the Evidence
 * object itself, which is why the evidence register route resolves them separately. */
export interface EvidenceCitedBy {
  claim: string;
  reuseJustification: { authority: string; text: string } | null;
  /** `Claim.assessableAt` — "assessable at level L if supporting evidence metadata is
   * visible at L" (schema doc). `null` only if the citing claim itself is missing the
   * required field (a malformed store, per `serialize.py`'s tolerance rule). */
  assessableAt: { level: string } | null;
}

/** One item of `GET /api/session/{s}/episode/{e}/evidence`. When the register lists an
 * id the graph does not resolve, every `ObjectView` field but `id`/`object` is absent —
 * modelled here as all-optional rather than a union so a caller can check `object` for
 * `null` once and read on. */
export interface EvidenceItem extends Partial<Omit<ObjectView, 'id' | 'object'>> {
  id: string;
  object: Evidence | null;
  scopeFindings: ScopeFinding[];
  citedBy: EvidenceCitedBy[];
}

export interface EvidenceRegisterResponse {
  episode: string;
  items: EvidenceItem[];
  findings: ScopeFinding[];
}

// ---- timeline and refresh-watch (src/docket/api/routes/program.py) -------------------

/** `GET /api/session/{s}/program/{p}/timeline`. `program: null` (with empty arrays)
 * means the id named no `DecisionProgram` at all — a missing/not-yet-built Demo B store,
 * or a session (e.g. Demo A, "new") that has no programme, not an error. */
export interface TimelineResponse {
  program: DecisionProgram | null;
  episodes: EpisodeView[];
  diffs: EpisodeDiff[];
  refreshTriggers: RefreshTrigger[];
  /** `null` exactly when `program` is — an id that named no `DecisionProgram` has no
   * clock to report. */
  timing: TimelineTiming | null;
}

/** `kernel.clock.programme_timing`, computed at request time against the server's own
 * `now` and never stored or rendered into a package. Every number the programme view
 * prints is here: no browser derives a day count, a month count or a staleness verdict
 * of its own. `days` and `months` are `null` for a stamp the record cannot parse — the
 * same "unknown, not zero" convention `days_between` has always used. */
export interface TimelineTiming {
  program: string;
  episodes: {
    id: string;
    openedAt: string | null;
    /** The `createdAt` of the revision at which the episode reached a state the
     * programme treats as closed (`SIGNED`/`SUPERSEDED`/`VOID`/`SUSPECT`), or `null`
     * while it is still the live answer — in which case `days` runs to `now`. */
    closedAt: string | null;
    days: number | null;
    endState: string | null;
  }[];
  /** Whole calendar months between the `openedAt` of consecutive episodes. */
  between: { from: string; to: string; months: number | null }[];
  /** From the latest episode's `openedAt` to `now`; `null` for a programme with no
   * episodes at all. */
  sinceLast: { from: string; months: number | null } | null;
  /** AR 5-11 ¶4-2i(3)'s three-year staleness rule, in months. */
  accreditationMonths: number;
  overdue: boolean;
}

/** One entry of `POST .../watch`'s `proposals` — `agent.refresh_watch.detect`'s own
 * output, deliberately carrying no envelope (no `id`, `rev`, `createdBy`): it has not
 * been filed. Shape matches `RefreshTrigger`'s content fields minus the envelope. */
export interface WatchProposal {
  kind: string;
  source: string;
  description: string;
  detectedAt: string;
  affected: string[];
}

/** `POST .../watch`. Per the plan 07 ledger's ruling on the T4 follow-up (landed:
 * `file_all(g, program_id, proposals, actor=..., now=now)`, the fixed signature), `filed`
 * is always a list of filed trigger ids, empty when `?file=` is omitted — confirmed live
 * against Demo B (review-t8-report.md M4): `file=false` and `file=true` both return
 * `"filed": []`. The wider `string[] | boolean` type this task originally carried was
 * stale relative to the fix; kept narrow here so a caller no longer needs to normalize a
 * shape the server never actually sends. */
export interface WatchResponse {
  proposals: WatchProposal[];
  filed: string[];
}

// ---- readiness (src/docket/api/routes/kernel.py `_readiness_view`) -------------------

/** `GET`/`POST /api/session/{s}/episode/{e}/readiness` — the stored `ReadinessReport`
 * with its `StandardsAssessment` and `MandateScorecard` resolved to the objects they
 * name, plus the fields `_readiness_view` computes so no browser has to: the renderer's
 * own captions and ready sentence (never a second copy hand-typed in a component), the
 * applicable/total question counts, and the scored tailoring's own name and `k`.
 *
 * Moved here from the old Readiness screen (Task 14): a route's shape belongs beside
 * every other route's shape, not inside the one view that happens to read it. */
export type ReadinessView = ReadinessReport & {
  standardsAssessment: StandardsAssessment | null;
  mandateScorecard: MandateScorecard | null;
  /** `standardsCaptions.tailoringNote` is `null` for a tailoring that has none
   * (`full-36`, `published-21`, …) and a sentence for one that does (`gao-23-106549`'s
   * caveat that GAO stated its verdicts in prose, not per-question labels). */
  standardsCaptions: { ratingScale: string; tailoringNote: string | null };
  applicableQuestions: number;
  totalQuestions: number;
  /** `kernel.render.ready_text` — `"True"`/`"False"`, or the staleness substitution when
   * the record has moved since the report was computed. The screen prints it verbatim so
   * it can never disagree with the rendered package's own Readiness section. */
  readyText: string;
  tailoring: string | null;
  k: number | null;
  createdAt: string;
};

// ---- package, sections, verify (src/docket/api/routes/{kernel,session}.py) -----------

export interface SectionSummary {
  key: string;
  title: string;
}

export interface SectionsResponse {
  sections: SectionSummary[];
}

/** `POST /api/session/{s}/episode/{e}/package` — the stored `DecisionPackage` plus the
 * rendered Markdown text in the same response body. */
export type PackageResponse = DecisionPackage & { text: string };

/** `POST /api/session/{s}/episode/{e}/verify` (src/docket/api/verify.py
 * `verify_determinism`). `scope` is printed verbatim next to the result — it is the
 * sentence that keeps a green "identical" from reading as a claim about the model. */
export interface VerifyResponse {
  identical: boolean;
  recordUnchanged: boolean;
  reason: string;
  hash: string;
  priorHash: string;
  graphSnapshotHash: string;
  priorGraphSnapshotHash: string;
  kernelVersion: string;
  scope: string;
}

/** `POST /api/session/{s}/episode/{e}/sign` (src/docket/api/routes/workspace.py) — the
 * person's own words: the option, the role, the stop rules (one per line on the sheet,
 * a list here) and an optional dissent recorded with the signature. */
export interface SignRequest {
  selected: string;
  role: string;
  stopRules: string[];
  dissent: { who: string; text: string }[] | null;
}

/** The commitment as `object_view` and the episode as `episode_view`, read while the
 * session lock is still held — the state the record is in the moment after the act. */
export interface SignResponse {
  commitment: ObjectView;
  episode: EpisodeView;
}

// ---- settings (src/docket/api/routes/settings.py) -------------------------------------

export interface SettingsModelResponse {
  provider: string;
  model: string;
  baseUrl: string;
  source: { provider: string; model: string; baseUrl: string };
  timeout: number;
}

export interface SettingsModelsResponse {
  models: ModelEntry[];
}

export interface SettingsKeyResponse {
  keyPresent: boolean;
}

export interface SettingsModeResponse {
  mode: 'live' | 'recorded' | 'auto';
}

export interface SettingsActorResponse {
  actorId: string;
}

// ---- the G1 review sheet (src/docket/agent/review.py `g1_review`) ---------------------

/** One `$gap`/`$exclusion` marker on a G1 object. Note this is **not** `SlotEntry`:
 * `g1_review` walks the raw object generically (`review._markers`, so a marker in a
 * field the catalogue does not declare a slot is still reported — `declaredSlot` says
 * which) and carries no resolved `targetObject`. The gap behind a `gap` marker is in the
 * same payload under `gaps[]`; the exclusion behind an `exclusion` marker is under
 * `exclusions[]`. */
export interface G1Slot {
  path: string;
  kind: 'gap' | 'exclusion';
  target: string;
  declaredSlot: boolean;
}

/** What `review._actions` says *this module* will do to this object — never
 * aspirational: `reject` is listed only where it would actually change something. The UI
 * offers exactly these and nothing else. */
export type G1Action = 'accept' | 'reject' | 'confirm';

export interface G1Object {
  id: string;
  type: string;
  rev: number;
  authorType: AuthorType;
  confidence: string | null;
  summary: string;
  sourceArtifact: string | null;
  locator: string | null;
  /** `ingestionProvenance.extractor` — the backend that produced the object. Carried in
   * the payload but **never rendered on this screen**: honesty rule 3 confines every
   * provider and model string to the Settings slide-over and the raw-object drawer. */
  extractor: string | null;
  explanation: string;
  ifWrong: { statement: string | null; indicators: string[] };
  actions: G1Action[];
  /** Per-action, the sentence the reviewer reads *before* clicking — written in
   * `review._record_effect` against this object in this graph (which episodes lose the
   * id, whether anything is dropped at all), not composed here. */
  recordEffect: Partial<Record<G1Action, string>>;
  slots: G1Slot[];
}

export interface G1Gap {
  id: string;
  sought: string;
  whereLookedFor: string[];
  whyNotFound: string;
  indicatorsThatWouldResolve: string[];
  impact: string;
  confirmed: boolean;
  confirmedBy: { actorId?: string; date?: string } | null;
  /** `"<objectId>/<fieldPath>"` for every slot this gap fills. Empty for an orphan gap —
   * the model looked for something and could not name the field it belonged to. */
  attachedTo: string[];
  attached: boolean;
  /** Whether *this* episode's reviewer may sign it (attached, or minted by this
   * episode's own elicitation). */
  confirmableHere: boolean;
}

export interface G1Exclusion {
  id: string;
  targetKind: string | null;
  targetId: string | null;
  targetLabel: string;
  reasonType: string;
  reason: string;
  authorityRole: string | null;
  authorityWho: string | null;
  retainedInStructure: boolean | null;
}

/** One row of the scoring panel — a model-authored value that reaches a rating, or a
 * model-written citation. `value` is whatever the object holds (a `priorityRank`
 * integer, a `baselineFlag` boolean, a `{uri, custodian}` pointer). */
export interface G1RatingRelevant {
  objectId: string;
  objectType: string;
  field: string;
  value: unknown;
  kind: 'rating' | 'citation';
  derivedField: string | null;
  derivedValue: string | null;
  convention: string | null;
  why: string;
  readBy: string[];
  summary: string;
}

export interface G1Check {
  name: string;
  satisfied: boolean;
  /** The check predicate's own docstring line, taken from the gate itself — so even the
   * remedy text cannot drift from what will actually be evaluated. */
  whatWouldSatisfy: string;
}

/** `GET /api/session/{s}/episode/{e}/g1` — `agent.review.g1_review(g, episode_id)`
 * verbatim. Three of its fields are fixed sentences the module owns
 * (`ratingRelevantHeading`, `ratingRelevantLine`, `ratingRelevantBoundary`); the UI
 * prints them and never retypes them. */
export interface G1Review {
  episode: string;
  lifecycleState: string;
  objects: G1Object[];
  gaps: G1Gap[];
  exclusions: G1Exclusion[];
  ratingRelevant: G1RatingRelevant[];
  ratingRelevantHeading: string;
  ratingRelevantLine: string;
  ratingRelevantBoundary: string;
  checks: G1Check[];
  ready: boolean;
}

/** `POST /api/session/{s}/elicit` — the new episode, every DRAFT object it wrote in
 * write order, and the ids of the gaps among them. */
export interface ElicitResponse {
  episode: EpisodeView;
  objects: ObjectView[];
  gaps: string[];
}

/** `POST /api/session/{s}/episode/{e}/confirm-gaps` — the gap ids a human just signed. */
export interface ConfirmGapsResponse {
  confirmed: string[];
}

// ---- sources and the committed request (src/docket/api/routes/session.py) -------------

/** One entry of `GET /api/sources` — keyed on `sources/*.source.md`, the provenance stub
 * that always exists, with `hasLocalCopy: false` when the document it documents is cited
 * but not redistributable. */
export interface SourceEntry {
  name: string;
  /** The `sourceArtifact` string to pass to `/elicit`, e.g. `"sources/cbo-2013-…pdf"`. */
  artifact: string;
  title: string | null;
  hasLocalCopy: boolean;
}

/** The one request text this repository has a committed model response for, and the two
 * arguments it was recorded under. `answerRecorded` is the server's own lookup against
 * the *currently configured* recording — false means pressing ELICIT in recorded mode
 * would 503, and the screen says so instead of finding out the hard way. */
export interface RecordedRequest {
  path: string;
  text: string;
  sourceArtifact: string;
  policyId: string;
  recording: string | null;
  answerRecorded: boolean;
}

export interface SourcesResponse {
  sources: SourceEntry[];
  recordedRequest: RecordedRequest | null;
}

// ---- the workspace routes (src/docket/api/routes/workspace.py, ask.py) ---------------
//
// Written against the serializers, not against the plan text: `kernel/queue.py::needs`
// and `kernel/clock.py::clock` are the two functions these four shapes come from, and
// where the plan's draft shape and the implementation disagreed the implementation won.

/** The three tones the clock and the queue speak in. Not a colour: the view maps a tone
 * onto a semantic token (`src/brand/semantic.css`), and the server never names one. */
export type Tone = 'ok' | 'wait' | 'stop';

/** One row of `needs.items` (`kernel.queue._item`). `actionable: false` marks a "waiting
 * for an earlier step" row, which carries `unlocksAfter` and nothing else useful.
 * `objectId` is null on a row that stands for a set of objects rather than one — a
 * grouped blocking finding — and `count` is how many findings that row stands for. */
export interface NeedsItem {
  id: string;
  kind: string;
  text: string;
  waitingOn: string;
  route: string;
  objectId: string | null;
  ageDays: number | null;
  actionable: boolean;
  count: number | null;
  unlocksAfter: string | null;
}

/** One row of `needs.blocking.items` (`kernel.queue.blocking`): either an unmet check of
 * the gate the episode sits at (`severity: 'gate'`, `count` 1, no objects) or the stored
 * readiness findings of one rule (`severity: 'blocking'`, `count` the number of findings
 * under it, `objects` the union of theirs). `blocking.count` is the sum of every row's
 * `count`, so grouping the rows never changes the number the header shows. */
export interface BlockingItem {
  rule: string;
  severity: string;
  count: number;
  objects: string[];
  message: string;
  route: string;
}

export interface NeedsResponse {
  episode: string;
  count: number;
  items: NeedsItem[];
  /** How many actionable items sit on each row of the map, computed by the server
   * (`kernel.queue.MAP_ROUTES`/`_by_route`) so no browser filters `items` to draw a
   * number. Keyed by the view's own path, present at zero, with `/review/{id}` items
   * folded into `/model`; `sum(byRoute) === count`. The `/` entry is always zero — the
   * home row counts the whole queue, which is `count`. */
  byRoute: Record<string, number>;
  blocking: { count: number; items: BlockingItem[] };
}

export interface ClockStage {
  state: string;
  plain: string;
  enteredAt: string;
  days: number;
  expected: number;
  running: boolean;
  tone: Tone;
}

export interface ClockFlag {
  kind: string;
  text: string;
  severity: Tone;
  route: string;
}

/** `GET …/clock` (`kernel.clock.clock`). `dueIn`, `spanDays` and `remainingDays` are
 * null together when the charter names no `neededBy`: with no deadline there is no
 * honest number for how much time is left, and nothing the server returns is an
 * estimate. A view draws that case as a strip running to today, never to a guess. */
export interface ClockResponse {
  episode: string;
  now: string;
  openedAt: string;
  deadline: string | null;
  expectedSource: 'policy' | 'default';
  stages: ClockStage[];
  current: { state: string; plain: string; days: number; expected: number };
  lastHumanAct: { at: string; actorId: string; what: string; daysAgo: number } | null;
  dueIn: number | null;
  spanDays: number | null;
  remainingDays: number | null;
  tone: Tone;
  flags: ClockFlag[];
}

/** One entry of `GET /api/session/{s}/activity` (`kernel.clock.describe_log_entry`),
 * newest first. `at` is the named revision's own `createdAt`, and is null when the
 * revision the log names is no longer readable. */
export interface ActivityEntry {
  seq: number;
  id: string;
  type: string;
  rev: number;
  at: string | null;
  layer: 'human' | 'agent' | 'kernel';
  actorId: string;
  what: string;
  refused: boolean;
}

export interface ActivityResponse {
  entries: ActivityEntry[];
}

export interface AskAction {
  label: string;
  route: string;
}

/** `POST …/ask` (`agent.ask`): answered from the record, else from the model, else the
 * fallback sentence. `intent` is null when no rule matched the question. */
export interface AskResponse {
  answer: { paragraphs: string[]; cites: string[]; actions: AskAction[] };
  source: 'record' | 'model' | 'fallback';
  intent: string | null;
}

export interface AskQuestionsResponse {
  questions: string[];
}
