// Appendix C of the spec, as data: every control the nine screens of the old interface
// carried, and where it lives in this design. `CoverageSheet.tsx` renders it; the
// coverage spec counts it and checks that every home it names resolves.
//
// Plain data on purpose — no React, no router — so a Playwright spec can import it
// directly and hold the sheet to the same list the sheet renders from.

export interface CoverageItem { item: string; where: string; route: string | null; overlay?: 'settings' | 'coverage' | 'blockers' | 'authority' }

/** The eleven view paths — the same eleven `routes.tsx`'s `VIEWS` carries; kept here as
 * plain data so a spec can import it without importing React. Nothing links the two
 * lists at compile time, so `coverage.spec.ts` counts the Browse menu against this list
 * (and against `ALL_SCREENS`) to catch a view added to one and not the other. */
export const VIEW_PATHS = ['/', '/request', '/model', '/review', '/plan', '/compute', '/readiness', '/package', '/evidence', '/timeline', '/activity'] as const;

const v = (item: string, where: string, route: string | null, overlay?: CoverageItem['overlay']): CoverageItem => ({ item, where, route, overlay });

/** Appendix C of the spec, line by line: every control that existed before this rebuild
 * and where it lives now. The coverage spec counts these rows against the sheet. */
export const COVERAGE: { group: string; items: CoverageItem[] }[] = [
  { group: 'Shell', items: [
    v('brand mark + Docket', 'header, left; the OffGrid mark is in the footer', '/'),
    v('current episode id · lifecycle state (mono)', 'header episode chip; the mono state shows under Explain', '/'),
    v('health chip LIVE / RECORDED / API absent (opens Settings)', 'the mode chip on the status row', null, 'settings'),
    v('settings gear', 'header, right', null, 'settings'),
    v('lifecycle navigation with unreached stages muted but clickable', 'the progress map (left column; a strip below 768 px)', '/'),
    v('the empty state "No numbers exist yet…"', 'Compute view before gate 2', '/compute'),
    v('authority rail counters numbers authored by model · by kernel', 'the chat panel header', null, 'authority'),
    v('objects h/a/k and the three-layer diagram', 'the authority overlay, opened from the counters', null, 'authority'),
    v('footer with the two disclosures and the OffGrid wordmark', 'the footer on every view', '/'),
  ] },
  { group: 'Home / sessions', items: [
    v('Open Demo A · Open Demo B · New session', 'the decision switcher in the header; start cards on Needs when nothing is open', '/'),
    v('demo cards with blurb', 'start cards on Needs', '/'),
    v('"Build now" with the build command when a store is missing', 'start cards on Needs', '/'),
    v('episode list with lifecycle chips and last-run hash', 'the episodes table at the foot of Needs', '/'),
    v('the two backend notices', 'Needs, above the queue', '/'),
  ] },
  { group: 'Request (was Intake)', items: [
    v('request textarea', 'Request step 1', '/request?step=1'),
    v('requested by', 'Request step 1', '/request?step=1'),
    v('source artefact (select from session sources)', 'Request step 2', '/request?step=2'),
    v('policy id', 'Request step 2', '/request?step=2'),
    v('needed by (the deadline)', 'Request step 2', '/request?step=2'),
    v('Load the recorded request', 'Request step 1', '/request?step=1'),
    v('ELICIT as the one primary action', 'Request step 3, the Ember button', '/request?step=3'),
    v('streaming stage progress', 'Request step 3 while the AI reads', '/request?step=3'),
    v('the elicited DRAFT objects as dashed chips', 'Request step 3 after elicitation, then the Model view', '/request?step=3'),
    v('"Every object above is a proposal…"', 'Request step 3', '/request?step=3'),
    v('"No backend reachable" with Switch to recorded', 'Request step 3', '/request?step=3'),
    v('a way to the Model board', 'Go to the model checklist', '/model'),
  ] },
  { group: 'Model (gate 1)', items: [
    v('episode selector', 'header episode chip', '/model'),
    v('Charter with its three fields, one typed at the gate', 'The charter, inline fields', '/model#charter'),
    v('Objectives with priority rank', 'Objectives cards; rank under Fields', '/model'),
    v('Alternatives', 'Options cards', '/model'),
    v('Ground rules · Constraints · Assumptions with linchpin flags', 'the third section; linchpin chip', '/model'),
    v('Evidence', 'Evidence cards on Model; the register on Evidence', '/model'),
    v('Recorded gaps with confirmedBy and a confirm action', 'What the source never says', '/model'),
    v('Recorded omissions (Exclusions)', 'Left out on purpose', '/model'),
    v('other objects the episode reaches', 'Other objects this decision reaches', '/model'),
    v('every chip opens the Review dialog', 'every card\'s act button', '/model'),
    v('the Approve bar with each check and its sentence', 'the gate-1 checklist', '/model'),
    v('the single Ember "Approve the model"', 'the checklist button', '/model'),
    v('the refusal as a persistent card', 'the red card in the checklist', '/model'),
    v('the read-only "already past G1" state', 'the checklist on any later state', '/model'),
    v('the rating-relevant panel', 'the scoring panel', '/model'),
  ] },
  { group: 'Review dialog', items: [
    v('fixed region order WHAT · WHY · SOURCE · IF WRONG · WHAT YOU CAN DO · WHAT HAPPENS', 'the review card: dialog, /review queue, /review/:id', '/review'),
    v('editable charter fields "the record does not say — type it here"', 'the charter on Model and in the card', '/model#charter'),
    v('confidence chip + extractor', 'region 2', '/review'),
    v('artefact + locator + verbatim excerpt in Newsreader italic', 'region 3', '/review'),
    v('Accept / Edit / Reject / Confirm gap', 'region 5', '/review'),
    v('what happens to the record, before and after', 'region 6', '/review'),
    v('open the stored object → raw JSON', 'the raw overlay', '/review'),
  ] },
  { group: 'Plan (gate 2)', items: [
    v('episode selector', 'header episode chip', '/plan'),
    v('Weights panel, human-only', 'Weights on Plan', '/plan'),
    v('Propose plan (agent) and its refusal state', 'The proposal', '/plan#propose'),
    v('plan steps as cards with authority document + paragraph', 'Steps', '/plan'),
    v('"approved by" and Approve plan (human)', 'The proposal', '/plan#propose'),
    v('Transition to PLAN_APPROVED', 'the gate-2 checklist', '/plan#approve'),
    v('"No plan proposed. The agent proposes; you approve."', 'The proposal, empty state', '/plan#propose'),
  ] },
  { group: 'Compute', items: [
    v('Dispatch with streaming stages', 'Run the plan', '/compute'),
    v('Runs sealed', 'one seal per run', '/compute'),
    v('Ranking and results per run', 'the result table per run', '/compute'),
    v('What flips the decision', 'the flip list per run', '/compute'),
    v('the weight simplex', 'under the flip list', '/compute'),
    v('the pre-G1 empty state', 'the sentence before gate 2', '/compute'),
  ] },
  { group: 'Readiness', items: [
    v('Compute readiness', 'Score the record against the standard', '/readiness'),
    v('the one big number', 'the applicable count on the grid caption', '/readiness'),
    v('the four-state grid, tailored-out questions with the reason', 'the grid, cells tinted by state', '/readiness'),
    v('the rating-scale caption printed', 'beside the grid', '/readiness'),
    v('the three dimension verdicts with the aggregation rule', 'the verdict cards', '/readiness'),
    v('Blockers (rule, severity, objects, message)', 'What blocks sign-off', '/readiness'),
    v('Open gaps and exclusions', 'under the blockers', '/readiness'),
    v('Mandate scorecard', 'under Fields → mandate', '/readiness'),
    v('the gate ladder', 'Where this decision stands', '/readiness'),
    v('the tailoring honesty caption', 'beside the grid when the tailoring has one', '/readiness'),
    v('the ready / not-ready sentence', 'the state line at the top', '/readiness'),
  ] },
  { group: 'Evidence register', items: [
    v('rendering toggle unclassified / full', 'the Package view toggle (the register shows what the record holds)', '/package'),
    v('per item: every field, classification chip, scope of validity, VV&A, reliability, limitations, custodian…', 'each evidence row', '/evidence'),
    v('scope findings on an item', 'each row, by severity', '/evidence'),
    v('open the stored object', 'each row', '/evidence'),
  ] },
  { group: 'Timeline (programme)', items: [
    v('episodes over time with as-of date and end state', 'the rail', '/timeline'),
    v('the trigger on the line between episodes', 'the connectors', '/timeline'),
    v('the diff panel', 'click an episode', '/timeline'),
    v('"field-level pairing unavailable for this diff"', 'the diff panel', '/timeline'),
    v('the 3×3 verdict grid with its caption', 'under the diff panel', '/timeline'),
    v('sub-episodes', 'the rail', '/timeline'),
    v('refresh watch (agent proposes) and open refresh (human, G4)', 'Ask the AI what changed · Open refresh', '/timeline'),
  ] },
  { group: 'Package', items: [
    v('episode selector', 'header episode chip', '/package'),
    v('rendering toggle unclassified / full', 'the toggle', '/package'),
    v('the 16 sections with jump navigation', 'the section list', '/package'),
    v('graphSnapshotHash · package hash · kernelVersion in full', 'the hash strip', '/package'),
    v('re-render · verify · download', 'the buttons under the hash strip', '/package'),
    v('the six exports (PROV, GSN, DMN, MIL-STD-3022, RTVM csv, MADR)', 'Exports', '/package'),
    v('the Commitment / sign block', 'The decision: Sign, Send back for rework', '/package#commit'),
  ] },
  { group: 'Settings', items: [
    v('Connection: provider · base URL · model (denylisted ids disabled)', 'the settings overlay', null, 'settings'),
    v('key (password field, held in memory)', 'the settings overlay', null, 'settings'),
    v('Mode auto / live / recorded', 'the settings overlay', null, 'settings'),
    v('Actor id', 'the settings overlay', null, 'settings'),
    v('Status: kernelVersion, backend, demo stores, denylist, refused reason', 'the settings overlay', null, 'settings'),
    v('the environment-variable override documented, not offered', 'the settings overlay text', null, 'settings'),
  ] },
  { group: 'New in this design', items: [
    v('What needs you — the queue', 'Needs', '/'),
    v('the clock card and the header time chip', 'Needs', '/#clock'),
    v('Ask about this decision', 'the chat panel', '/'),
    v('Activity — the log in sentences', 'Activity', '/activity'),
    v('Blockers sheet', 'the blocking counter', null, 'blockers'),
    v('Fields control', 'every view head', '/'),
  ] },
];
