// The universal review card (design spec §4; plan 07 Task 6, split out in Task 11). One
// component, five kinds, six regions in a fixed order every time — so an audience learns
// it once and a reviewer never has to work out where the consequence of a click is
// written on this particular surface.
//
// Task 11 gave the card three homes and this file is all three of them: the reading queue
// at `/review`, one object at `/review/:objectId`, and the dialog the model's own cards
// open (`ReviewDialog`, now a thin shell around this). Nothing about the regions changed
// in that move; only what wraps them did. `data-review-card` is the hook a spec uses
// wherever the card is standing, and `[data-review-dialog] [data-region]` still resolves
// because the card is inside the dialog.
//
// Two rules a reviewer of *this file* will check for, both from the plan:
//
//   1. `run()` makes ONE API call and returns what the server sent. This card does not
//      construct object revisions, and does not decide what `reject` means for a given
//      type — `agent.review.reject` decides that, and the card prints the consequence
//      it was told about in `effect`. The one exception, added for the Charter's three
//      gate fields (`charterFields`) and for the one field of an ordinary object a
//      reviewer may reword (`editableField`): the card carries the human's typed text
//      for the fields they touched and hands it to the same one `accept` call as
//      `edits` — it still does not merge anything into the stored object itself, or
//      decide what the server does with those edits; `agent.review.accept`'s own
//      `**edits` does exactly what it would for any other caller.
//   2. `effect` is a STRING WRITTEN NEXT TO THE ACTION, not generated. It is the sentence
//      a human reads before committing an irreversible act, and generated prose is
//      exactly the wrong thing there. (On the G1 board those strings come from
//      `review._record_effect`, which composes them per action against *this* object in
//      *this* graph — naming the episodes that actually lose the id. They are still
//      written prose from a fixed template, not assembled from data by the browser; see
//      the Task 6 report's note on this.)
//
// Region 4 renders its heading even when there is nothing under it, with the line "the
// record does not say" — an absent consequence is a fact about the record, and hiding
// the heading would hide it.
//
// Brand v3.0 (§5, §5a): the headings are sentence case (v3.0 has nothing uppercase;
// `data-region` keeps the spec's own ALL-CAPS field name as the stable hook a test and a
// reader both use), labels and buttons are `og-label` rather than mono, and mono is kept
// for what it is for: object ids, revs, changed key names, schema field names. Every
// button clears the 44px touch floor.
//
// The confirm step keeps Ember AS TEXT and as a hairline, never as a plane. The one Ember
// FILL a view is allowed (§5's precedence rule) is asked for by the view, through
// `ember` — a card standing on `/review` is the view's primary act and marks it; a card
// inside the dialog never does, because the act behind an overlay is not the act in
// front of one.

import { useEffect, useRef, useState, type ReactNode } from 'react';
import { CircleAlert } from 'lucide-react';
import { ApiError } from '../api/client';
import { confidenceLabel } from '../lib/format';
import { ICON_PROPS } from '../lib/icons';
import { Chip } from './Chip';
import { ErrorState } from './ErrorState';
import type { ObjectView } from '../types/api';

// [ruling M7, plan 07 T6 fix round] `limitation` and `finding` were implemented and
// never wired to any route this app calls: G1 exposes no structural-findings list (the
// `no-blocking-structural` check is a boolean, not an enumeration a dialog could open),
// and `limitations[]` live on Charter/Evidence objects, which the Evidence register
// renders on its own screen. Removed as untested scaffolding rather than left
// half-built — a kind no spec ever opens is a kind that can silently break.
export type ReviewKind = 'assumption' | 'gap' | 'exclusion';

/** One of the three AR 5-11 ¶4-5b fields `kernel.lifecycle.c_charter` reads
 * (`charter-three-fields`) — see `ReviewSubject.charterFields`. */
export interface CharterField {
  /** The schema field name (`question` / `decisionToBeMade` /
   * `consequencesOfErroneousOutput`), printed verbatim as the label — never reworded,
   * so a reviewer can match it to AR 5-11 ¶4-5b and to the check that reads it. */
  key: string;
  /** The draft's current content, or `''` when the field holds none (absent, or a
   * `$gap`/`$exclusion` marker) — empty when absent, never invented text. */
  value: string;
}

export interface ReviewSubject {
  kind: ReviewKind;
  id: string;
  /** The revision on screen, so region 6 can print `rev n → n+1` after the write. */
  rev?: number;
  /** Region 1, verbatim from the object. Never reworded here. Unused when
   * `charterFields` is set — the three editable fields replace it. */
  what: string;
  confidence?: string | null;
  provenance?: {
    sourceArtifact: string | null;
    locator: string | null;
    /** Carried, never rendered — honesty rule 3 keeps every provider/model string off
     * the proposal-facing screens. It reaches a reader through the raw-object drawer. */
    extractor: string | null;
  } | null;
  /** `implicationsIfWrong` / `impact` / `severity` — region 4. */
  ifWrong: string[];
  /** `indicatorsThatWouldAlter` / `indicatorsThatWouldResolve` — region 4. */
  indicators: string[];
  /** A verbatim excerpt of the source. The only Newsreader italic in the app. No route
   * on the G1 board supplies one today (see the Task 6 report, "fields not sourced"), so
   * this is unset there rather than filled with the stored value, which is the model's
   * reading of the source and not a quotation from it. */
  quoted?: string;
  /** The object as stored *before* the action, so region 6 can name which keys changed.
   * Supplied by the caller (which fetched it to open the raw drawer anyway); the card
   * never fetches. */
  before?: ObjectView | null;
  /** Set ONLY when this subject is a Charter (`lib/reviewSubject.ts` is the only
   * producer) — the three AR 5-11 fields, editable, so a human can complete the model
   * at the gate instead of only accepting it as-is. Every other object kind leaves this
   * unset and keeps the ordinary, read-only region 1. */
  charterFields?: CharterField[];
  /** The one free-text field of an ordinary object a reviewer may reword (an
   * Assumption's `statement`, an Objective's `name`) — rendered under the verbatim
   * `what` in region 1. Accepting with it changed sends it as the same `edits` a
   * Charter's three fields go through: one call, one new revision, authored by the
   * person who typed it. Never set alongside `charterFields`. */
  editableField?: { key: string; value: string };
}

/** What an action's one API call gave back. Wider than the plan's literal
 * `Promise<ObjectView>` because two of the plan's own actions do not return one:
 * `confirm-gaps` answers with the list of gap ids a human just signed, and an action
 * that writes nothing to the record at all (the plan's own `Acknowledge`, not wired on
 * any board today — see `ReviewKind`'s note on `limitation`/`finding`) still needs a
 * state to report. Modelling that as a union rather than casting keeps "this action
 * changed nothing" a state the card can *say*. */
export type ReviewResult =
  | { kind: 'object'; view: ObjectView }
  | { kind: 'gaps'; confirmed: string[] }
  /** A server payload that is not an `object_view` — `reject` returns the new
   * `Exclusion` itself. `label` is what to call it on screen. */
  | { kind: 'record'; label: string; id: string }
  | { kind: 'none' };

export interface ReviewAction {
  label: string;
  /** Region 6, shown BEFORE the click. */
  effect: string;
  /** Exactly one API call. `edits` is populated only when the subject offers an
   * editable field (`charterFields`, or the one `editableField` of an ordinary
   * object) — the human's current text for every field that differs from the draft's
   * original content, keyed by the field's own schema name (`changedEdits`, below).
   * The card does not decide what `accept` does with them, and does not merge them
   * into anything itself; it hands them to the one call this action already makes,
   * exactly as `agent.review.accept`'s own `**edits` treats any other caller's edits.
   * An action on a subject with nothing editable ignores the argument. */
  run: (edits?: Record<string, string>) => Promise<ReviewResult>;
  /** An Ember confirm step first — for the one action a reviewer cannot undo by
   * clicking again. */
  destructive?: boolean;
}

export interface ReviewCardProps {
  subject: ReviewSubject;
  actions: ReviewAction[];
  onDone: (result: ReviewResult) => void;
  /** Opens the raw-object drawer — the one place this object's full JSON, and the
   * extractor that produced it, are allowed to appear. */
  onOpenRaw?: () => void;
  /** Move the keyboard into the card the moment it mounts. Set by the dialog (a modal
   * that leaves focus behind it announces nothing); left off by the two views, where the
   * card is page content and stealing focus from the frame would be wrong. */
  autoFocus?: boolean;
  /** Mark this card's primary act as the VIEW's one Ember fill (§5's precedence rule);
   * the frame paints anything carrying `data-ember` (`frame/frame.css`). Only a view asks
   * for this. The primary act is Accept where the record offers one, and otherwise the
   * first act that is not the destructive one — a Reject is never a screen's Ember. */
  ember?: boolean;
}

const KIND_LABEL: Record<ReviewKind, string> = {
  assumption: 'Model proposal',
  gap: 'Recorded gap',
  exclusion: 'Recorded omission',
};

/** [ruling M7] The `{kind: 'none'}` result stays in `ReviewResult`'s union even though
 * no action wired on any board returns it today — "this action writes nothing to the
 * record" is a state a future action (an Acknowledge, if one is ever wired) can still
 * say honestly, and the card does not need a kind of its own to say it. Written here,
 * not generated — see the file header's rule 2. */
const NOTHING_WRITTEN = 'This action writes nothing to the record.';

/** The six regions, in the order §4 fixes them. `key` is the spec's own name for the
 * field — ALL CAPS because that is how the design document writes it, and it is what
 * `data-region` exposes so a spec can assert the ORDER without depending on the wording
 * on screen. `title` is what a human actually reads: sentence case, because nothing in
 * v3.0's interface is uppercase (§5). The two are deliberately separate — renaming a
 * heading must not silently change the contract a test asserts against, and neither may
 * shouting be reintroduced by way of the attribute. */
const REGIONS = [
  { key: 'WHAT', title: 'What' },
  { key: 'WHY THE MODEL PROPOSED IT', title: 'Why the model proposed it' },
  { key: 'SOURCE', title: 'Source' },
  { key: 'IF IT IS WRONG', title: 'If it is wrong' },
  { key: 'WHAT YOU CAN DO', title: 'What you can do' },
  { key: 'WHAT HAPPENS TO THE RECORD', title: 'What happens to the record' },
] as const;

function Region({ n, children }: { n: 0 | 1 | 2 | 3 | 4 | 5; children: ReactNode }) {
  return (
    <section className="flex flex-col gap-1 border-t border-hairline pt-3 first:border-t-0 first:pt-0">
      <h3 className="og-label text-b3 text-fg-muted" data-region={REGIONS[n].key}>
        {REGIONS[n].title}
      </h3>
      {children}
    </section>
  );
}

/** The line every region falls back to. "Nothing here" is a fact about the record, so it
 * is stated, not implied by an absent heading. */
function NotSaid() {
  return <p className="text-b2 text-fg-secondary">the record does not say</p>;
}

/** Keys whose stored value differs between two revisions of the same object. Key names
 * only — the plan asks for "changed keys in mono", and printing the values would put
 * arbitrary record prose (and its numerals) into a summary line nobody cited. The
 * envelope fields every write touches are excluded: they would be listed on every single
 * action and say nothing about what the human actually changed. */
const _ENVELOPE_KEYS = new Set(['rev', 'createdAt', 'createdBy', 'supersedes']);

/** [ruling I2, plan 07 T6 fix round] Every element a keyboard user could tab to, inside
 * the panel. Used to pick "the first control" to focus on mount, and — by the dialog —
 * to trap Tab at the panel's own edges. The same selector for both, so the element
 * focused on open is always one the trap will actually cycle through. */
export const FOCUSABLE_SELECTOR =
  'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), ' +
  'textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

function changedKeys(before: Record<string, unknown>, after: Record<string, unknown>): string[] {
  const keys = new Set([...Object.keys(before), ...Object.keys(after)]);
  const out: string[] = [];
  for (const key of [...keys].sort()) {
    if (_ENVELOPE_KEYS.has(key)) continue;
    if (JSON.stringify(before[key]) !== JSON.stringify(after[key])) out.push(key);
  }
  return out;
}

/** Every editable field this subject offers: a Charter's three, or the one field of an
 * ordinary object a reviewer may reword. Never both. */
function editableFields(subject: ReviewSubject): CharterField[] {
  if (subject.charterFields) return subject.charterFields;
  return subject.editableField ? [subject.editableField] : [];
}

/** The initial value for each editable field, keyed by field name — the seed for the
 * card's own edit state, so a field the human never touches stays exactly the draft's
 * own value rather than an empty control. */
function initialEdits(subject: ReviewSubject): Record<string, string> {
  return Object.fromEntries(editableFields(subject).map((f) => [f.key, f.value]));
}

/** Only the fields whose text now differs from the draft's original content —
 * "changed or filled", never every field, so `accept`'s `edits` carries exactly what
 * the human actually decided and nothing a field the human left alone. `undefined` when
 * nothing changed, so an untouched Accept posts the same empty `edits` it always did. */
function changedEdits(
  subject: ReviewSubject,
  current: Record<string, string>,
): Record<string, string> | undefined {
  const changed: Record<string, string> = {};
  for (const field of editableFields(subject)) {
    const value = current[field.key] ?? '';
    if (value !== field.value) changed[field.key] = value;
  }
  return Object.keys(changed).length > 0 ? changed : undefined;
}

export function ReviewCard({ subject, actions, onDone, onOpenRaw, autoFocus = false, ember = false }: ReviewCardProps) {
  const [pending, setPending] = useState<ReviewAction | null>(null);
  const [confirming, setConfirming] = useState<ReviewAction | null>(null);
  const [result, setResult] = useState<ReviewResult | null>(null);
  const [refusal, setRefusal] = useState<{ message: string; unsatisfied: string[] } | null>(null);
  const [error, setError] = useState<string | null>(null);
  // Seeded once, from whatever this subject offers as editable — a Charter's three
  // fields, or the one field of an ordinary object a reviewer may reword. A new subject
  // means a new card instance (every caller keys this component on the subject's id), so
  // a lazy initializer is enough; `{}` for a subject that offers neither, where nothing
  // reads this state at all.
  const [edits, setEdits] = useState<Record<string, string>>(() => initialEdits(subject));

  const cardRef = useRef<HTMLElement>(null);

  // [ruling I2, plan 07 T6 fix round] Focus the card's first control the moment it
  // mounts inside a modal — before that fix, focus stayed on the chip behind the dialog
  // and `aria-modal="true"` announced nothing. Restoring focus to the opener on unmount
  // belongs to the dialog, which is the thing that was opened.
  useEffect(() => {
    if (!autoFocus) return;
    const card = cardRef.current;
    (card?.querySelector<HTMLElement>(FOCUSABLE_SELECTOR) ?? card)?.focus();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- mount only
  }, []);

  async function perform(action: ReviewAction) {
    setPending(action);
    setConfirming(null);
    setRefusal(null);
    setError(null);
    try {
      const res = await action.run(changedEdits(subject, edits));
      setResult(res);
      onDone(res);
    } catch (err) {
      // Honesty rule 8: a refusal is shown, by name, as a state of this card — never a
      // toast, and never swallowed into a generic "something went wrong".
      if (err instanceof ApiError && (err.status === 403 || err.status === 409)) {
        setRefusal({
          message: err.body.message ?? err.message,
          unsatisfied: err.body.unsatisfied ?? [],
        });
      } else {
        setError(err instanceof Error ? err.message : String(err));
      }
    } finally {
      setPending(null);
    }
  }

  const afterObject = result?.kind === 'object' ? result.view : null;
  // Accepting an object whose wording a reviewer has changed is not the same act as
  // accepting it as-is, so the button says which one it is about to do.
  const reworded =
    !!subject.editableField &&
    (edits[subject.editableField.key] ?? '') !== subject.editableField.value;
  // The view's one Ember, when a view asked for one: Accept where it is offered, else the
  // first act that is not the destructive one (a gap's Confirm gap). Never a Reject.
  const primary = ember ? actions.find((a) => !a.destructive) ?? null : null;

  return (
    <article
      ref={cardRef}
      tabIndex={autoFocus ? -1 : undefined}
      className="flex flex-col gap-4 border border-hairline-strong bg-raised p-4"
      data-review-card
      data-object-id={subject.id}
      data-kind={subject.kind}
    >
      <p className="og-label text-b3 text-fg-muted">
        {KIND_LABEL[subject.kind]} · <span className="og-mono break-words text-m2">{subject.id}</span>
      </p>

      {/* 1 — WHAT: the statement verbatim, UNLESS this is a Charter — G1's whole
          point is that a human can complete the model at the gate, and a Charter's
          "WHAT" is exactly the three fields `charter-three-fields` reads, so they are
          editable here instead of read-only prose. Record prose carries page numbers,
          section marks and quantities the model read out of a source; it is not a
          computed value, so it is never a `<Num>`. The narrowest span holding it is
          marked `data-num="label"`, the same carve-out T7's fix round applied to
          verbatim standard prose, dates and citations. */}
      <Region n={0}>
        {subject.charterFields ? (
          <div className="flex flex-col gap-3" data-charter-fields>
            {subject.charterFields.map((field) => (
              <label key={field.key} className="flex flex-col gap-1" data-charter-field={field.key}>
                {/* The schema's own field name, verbatim and in mono so a reviewer can
                    match it to AR 5-11 ¶4-5b; "human input" is our word for it, so it
                    is not mono. */}
                <span className="og-label text-b3 text-fg-muted">
                  <span className="og-mono text-m2">{field.key}</span>
                  {' · human input'}
                </span>
                {/* What a human types here is prose the record will carry — body text,
                    never mono. */}
                <textarea
                  value={edits[field.key] ?? ''}
                  onChange={(e) =>
                    setEdits((prev) => ({ ...prev, [field.key]: e.target.value }))
                  }
                  rows={3}
                  placeholder="the record does not say — type it here"
                  className="text-b2 border border-hairline-strong bg-transparent p-2"
                />
              </label>
            ))}
          </div>
        ) : (
          <>
            <p className="text-b1" data-num="label" title="Verbatim from the record. A number here is text the model read out of the source, not a value anything computed.">
              {subject.what}
            </p>
            {/* The one field of this object a reviewer may reword. Under the verbatim
                statement, never instead of it: what the record says now and what a
                person would rather it said are two different facts, and the second
                becomes a revision only when Accept is pressed. */}
            {subject.editableField && (
              <label className="mt-2 flex flex-col gap-1" data-editable-field={subject.editableField.key}>
                <span className="og-label text-b3 text-fg-muted">
                  <span className="og-mono text-m2">{subject.editableField.key}</span>
                  {' · your wording becomes the new revision'}
                </span>
                <textarea
                  value={edits[subject.editableField.key] ?? ''}
                  onChange={(e) => {
                    const key = subject.editableField?.key;
                    if (key) setEdits((prev) => ({ ...prev, [key]: e.target.value }));
                  }}
                  rows={3}
                  className="text-b2 border border-hairline-strong bg-transparent p-2"
                />
              </label>
            )}
          </>
        )}
      </Region>

      {/* 2 — WHY THE MODEL PROPOSED IT. The extractor is deliberately absent: honesty
          rule 3 confines every provider and model string to the Settings slide-over and
          the raw-object drawer, and this card stands on a proposal-facing screen. The
          drawer link below is how a reader gets to it. */}
      <Region n={1}>
        {subject.confidence || subject.provenance?.locator ? (
          <p className="text-b2 flex flex-wrap items-center gap-2">
            <Chip>{confidenceLabel(subject.confidence)}</Chip>
            {subject.provenance?.locator && (
              <span className="og-mono text-m2 text-fg-secondary" data-num="label">
                {subject.provenance.locator}
              </span>
            )}
            {onOpenRaw && (
              <button
                type="button"
                onClick={onOpenRaw}
                className="og-label text-b3 inline-flex min-h-11 items-center underline underline-offset-4"
              >
                open the stored object
              </button>
            )}
          </p>
        ) : (
          <NotSaid />
        )}
      </Region>

      {/* 3 — SOURCE. `quoted` is the only Newsreader italic in the app. */}
      <Region n={2}>
        {subject.provenance?.sourceArtifact ? (
          <p className="og-mono break-words text-m2 text-fg-secondary" data-num="label">
            {subject.provenance.sourceArtifact}
            {subject.provenance.locator ? ` · ${subject.provenance.locator}` : ''}
          </p>
        ) : (
          <NotSaid />
        )}
        {subject.quoted && (
          <blockquote className="font-editorial italic text-b2 border-l border-hairline-strong pl-3" data-num="label">
            {subject.quoted}
          </blockquote>
        )}
      </Region>

      {/* 4 — IF IT IS WRONG. Heading always rendered, even empty. */}
      <Region n={3}>
        {subject.ifWrong.length === 0 && subject.indicators.length === 0 ? (
          <NotSaid />
        ) : (
          <>
            {subject.ifWrong.map((line) => (
              <p key={line} className="text-b2" data-num="label">
                {line}
              </p>
            ))}
            {subject.indicators.length > 0 && (
              <ul className="text-b2 text-fg-secondary list-none flex flex-col gap-0.5">
                {subject.indicators.map((line) => (
                  <li key={line} data-num="label">
                    · {line}
                  </li>
                ))}
              </ul>
            )}
          </>
        )}
      </Region>

      {/* 5 — WHAT YOU CAN DO. */}
      <Region n={4}>
        {actions.length === 0 ? (
          <NotSaid />
        ) : (
          <div className="flex flex-wrap gap-3">
            {actions.map((action) => (
              <button
                key={action.label}
                type="button"
                disabled={pending !== null}
                onClick={() => (action.destructive ? setConfirming(action) : perform(action))}
                data-ember={action === primary ? '' : undefined}
                className={`og-label text-b3 inline-flex min-h-11 min-w-11 items-center justify-center border px-4 ${
                  action.destructive ? 'border-accent text-accent-text' : 'border-hairline-strong'
                }`}
              >
                {pending === action ? 'working…' : reworded && action.label === 'Accept' ? 'Change the wording' : action.label}
              </button>
            ))}
          </div>
        )}
      </Region>

      {/* 6 — WHAT HAPPENS TO THE RECORD: stated before the click, echoed after. */}
      <Region n={5}>
        <dl className="flex flex-col gap-2">
          {actions.map((action) => (
            <div key={action.label}>
              <dt className="og-label text-b3 text-fg-muted">{action.label}</dt>
              <dd className="text-b2" data-num="label">
                {action.effect}
              </dd>
            </div>
          ))}
          {actions.length === 0 && <NotSaid />}
        </dl>

        {confirming && (
          <div className="border border-accent p-3 flex flex-col gap-2" data-state="confirm">
            <p className="text-b2 inline-flex items-start gap-2">
              {/* Smaller than the spec default: an inline status glyph. */}
              <CircleAlert {...ICON_PROPS} size={18} className="text-accent-text shrink-0" aria-hidden />
              <span data-num="label">{confirming.effect}</span>
            </p>
            <div className="flex gap-3">
              <button
                type="button"
                onClick={() => perform(confirming)}
                className="og-label text-b3 inline-flex min-h-11 min-w-11 items-center justify-center border border-accent px-4 text-accent-text"
              >
                Confirm {confirming.label}
              </button>
              <button
                type="button"
                onClick={() => setConfirming(null)}
                className="og-label text-b3 inline-flex min-h-11 min-w-11 items-center justify-center border border-hairline px-4"
              >
                Cancel
              </button>
            </div>
          </div>
        )}

        {result && (
          <div className="border border-hairline p-3 flex flex-col gap-1" data-state="recorded">
            <p className="og-label text-b3 text-fg-muted">Recorded</p>
            {afterObject && (
              <>
                <p className="og-label text-b3">
                  rev{' '}
                  <span className="og-mono text-m2" data-num="label">
                    {subject.rev ?? '?'} → {afterObject.rev}
                  </span>{' '}
                  · <span className="og-mono text-m2">createdBy.actorType</span>:{' '}
                  <span className="og-mono text-m2">{afterObject.authorType}</span> ·{' '}
                  {/* `data-model-id`: the one string in this card that can carry a
                      model name (an agent-authored revision's actor id is built from
                      the configured model id). Masked in the documentation figures. */}
                  <span className="og-mono break-words text-m2" data-model-id>
                    {afterObject.authorId}
                  </span>
                </p>
                {subject.before && (
                  <p className="og-label text-b3 text-fg-secondary">
                    changed:{' '}
                    {changedKeys(subject.before.object, afterObject.object).length > 0 ? (
                      <span className="og-mono break-words text-m2">
                        {changedKeys(subject.before.object, afterObject.object).join(', ')}
                      </span>
                    ) : (
                      '(no field value changed; the authorship did)'
                    )}
                  </p>
                )}
                {/* The plan asks for both of these to be said, one line each. Read off
                    the returned object, never assumed. */}
                <p className="text-b2 text-fg-secondary">
                  {afterObject.confidence === null
                    ? 'The confidence annotation is gone — a human did not infer this.'
                    : `The confidence annotation is still ${afterObject.confidence}.`}
                </p>
                <p className="text-b2 text-fg-secondary">
                  {afterObject.provenance
                    ? 'Ingestion provenance is kept — where the text came from is still true.'
                    : 'This revision carries no ingestion provenance.'}
                </p>
              </>
            )}
            {result.kind === 'gaps' && (
              <p className="og-label text-b3">
                <span className="og-mono text-m2">
                  confirmedBy {'{'}actorId, date{'}'}
                </span>{' '}
                on: <span className="og-mono break-words text-m2">{result.confirmed.join(', ')}</span>
              </p>
            )}
            {result.kind === 'record' && (
              <p className="og-label text-b3">
                {result.label}: <span className="og-mono break-words text-m2">{result.id}</span>
              </p>
            )}
            {result.kind === 'none' && (
              <p className="text-b2 text-fg-secondary">{NOTHING_WRITTEN}</p>
            )}
          </div>
        )}

        {refusal && <ErrorState kind="refused" message={refusal.message} unsatisfied={refusal.unsatisfied} />}
        {error && <ErrorState message={error} />}
      </Region>
    </article>
  );
}
