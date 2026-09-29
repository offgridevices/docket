// Explain: the record's own terms, for the view in front of you.
//
// The lines are copy, not values. They name the objects the view is drawing, the gate
// checks by their kernel names, and the one field that is policy rather than a rule —
// so a reader can go from a plain-language screen to the schema and back. No provider
// or model name ever appears here, and nothing on this panel is read from the API, so
// the numerals in it (a gate number, the count of questions in the standard, a clause
// citation) are parts of names and are marked as labels.
import { useLocation } from 'react-router-dom';
import { useWorkspace } from '../api/useWorkspace';
import { ColourKey } from '../components/ColourKey';
import { VIEWS, type ViewKey } from '../routes';

export const EXPECTED_TIME_NOTE = 'Expected time per stage is a policy setting, not a rule: overrunning it flags the stage; it never blocks anything.';

export const EXPLAIN_LINES: Record<ViewKey, string[]> = {
  // Deliberately without `EXPECTED_TIME_NOTE`: the clock card on this very view already
  // prints it under Explain, right beside the stage timings it is about (`ClockCard.tsx`,
  // and `clock.spec.ts` holds it there), and one screen must not say the same sentence
  // twice.
  needs: ['The queue is computed by the server from the gate checks (CHECKS), stored blocking findings, unconfirmed InsufficientEvidence and unopened RefreshTriggers.'],
  request: ['Making a request creates a Charter and a DecisionEpisode in DRAFT; ELICIT drafts objects with createdBy.actorType = agent.', 'neededBy is a policy field on the Charter; it flags, it never blocks.'],
  model: ['Gate 1 (MODEL_APPROVED): charter-three-fields, charter-human-accepted, no-blocking-structural, gaps-confirmed, linchpins-human.', 'A linchpin is an Assumption a FlipAnalysis binds to.'],
  review: ['Accept writes a new revision with createdBy.actorType = human; reject writes an Exclusion; confirm sets confirmedBy on the InsufficientEvidence.'],
  plan: ['Gate 2 (PLAN_APPROVED): plan-present, plan-approved-by-human, plan-steps-have-authority, policy-method-matches.', 'Each step\'s authority is a DMN AuthorityRequirement: document + paragraph.'],
  compute: ['dispatch runs every Plan step under the kernel actor; each EvaluationRun is sealed with runRecordHash and inputsHash; every-step-has-run is the EVALUATED check.'],
  readiness: ['ReadinessReport: StandardsAssessment (36 questions, tailoring), MandateScorecard, blockers, warnings, flipSummary. readiness-present is the PENDING_SIGNATURE check; readiness-ready is a SIGNED check.'],
  package: ['DecisionPackage: rendering, hash, graphSnapshotHash, kernelVersion. Gate 3 (SIGNED): commitment-present, readiness-ready, commitment-package-hash.', 'Send back files a RefreshTrigger of kind signer-return.'],
  evidence: ['Evidence fields with slot: true render as content, an InsufficientEvidence card or an Exclusion card; scope findings come from kernel.findings.'],
  timeline: ['DecisionProgram: episodes, refreshTriggers, diffs (EpisodeDiff with pairing). Months and days come from clock.programme_timing; the 36-month rule is AR 5-11 ¶4-2i(3).'],
  activity: ['Each row is one append-only log entry (seq, id, rev, actor); the sentence is clock.describe_log_entry. A refused transition is a revision of the DecisionEpisode with refused: true.'],
};

/** Which view's lines to print. `/review/:objectId` is the Review view reading one id off
 * the address, so it takes Review's lines; anything the table does not name (`/ask`,
 * which redirects home) falls back to the home view's. */
export function viewKeyFor(pathname: string): ViewKey {
  const hit = VIEWS.find((v) => v.path !== '/' && (pathname === v.path || pathname.startsWith(`${v.path}/`)));
  return hit?.key ?? 'needs';
}

export function ExplainPanel() {
  const { explain } = useWorkspace();
  const { pathname } = useLocation();
  if (!explain) return null;
  return (
    <div className="mb-4 border-l-2 border-hairline-strong bg-surface px-3 py-2 text-b3 text-fg-secondary" data-explain-panel>
      <p><strong className="og-label">What the colours mean.</strong> Colour is state, learned once. It sits on glyphs, marks, borders, chips and buttons, never on the sentence beside them; numbers never carry colour. One Ember-filled button per view is the act to do next.</p>
      <div className="mt-1.5"><ColourKey /></div>
      {EXPLAIN_LINES[viewKeyFor(pathname)].map((line) => (
        <p key={line} className="mt-1.5" data-num="label">{line}</p>
      ))}
    </div>
  );
}
