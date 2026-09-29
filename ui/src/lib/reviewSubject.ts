// One object of the G1 sheet, as the review dialog's subject and its actions.
//
// Moved here verbatim from the old `screens/Model.tsx` (`openObjectDialog`,
// `openGapDialog`, `subjectFor`, `charterFieldsFor`, the three fallback sentences,
// `REJECT_REASON`, `reifyRejectEffect`), so the overlay that opens over ANY view — the
// queue's cards, the model's cards, a `/review/:objectId` link — builds the same subject
// the G1 board used to build for itself.
//
// Two rules the old file carried and this one keeps:
//   1. `review._actions` decides what is offered; the browser never invents an action.
//   2. `review._record_effect` wrote the sentence a reviewer reads before clicking. The
//      three fallbacks below exist only for the case where the server offered an action
//      without a sentence for it — a reviewer must never see a blank where the
//      consequence belongs.

import { apiGet, apiPost } from '../api/client';
import type { CharterField, ReviewAction, ReviewSubject } from '../components/ReviewDialog';
import type { ConfirmGapsResponse, G1Gap, G1Object, G1Review, ObjectView } from '../types/api';

/** `kernel.lifecycle.AR_5_11_FIELDS` — the three AR 5-11 ¶4-5b fields
 * `charter-three-fields` reads. Spelled here once rather than derived from a route (no
 * route returns a schema field list) — a name copied from the server module it belongs
 * to, not invented here. */
const AR_5_11_FIELDS = ['question', 'decisionToBeMade', 'consequencesOfErroneousOutput'] as const;

/** A Charter field's pre-fill text: the stored string, or `''` for anything else (absent,
 * a `$gap`/`$exclusion` marker, or a shape the schema does not allow here) — "empty when
 * absent", never invented text. */
function charterFieldText(v: unknown): string {
  return typeof v === 'string' ? v : '';
}

// ---- the sentences this file owns ------------------------------------------------------

const ACCEPT_FALLBACK =
  'A new revision, authored by you. The confidence annotation is dropped — a human did not infer it — and the ingestion provenance is kept, because where the text came from is still true.';
const CONFIRM_FALLBACK =
  'Every gap this episode reaches gains confirmedBy {actorId, date}, and the gaps-confirmed check flips on the ladder.';
const REJECT_FALLBACK =
  'An Exclusion is written recording the omission, and the id is dropped from the episode. Clicking again does not undo it.';

/** [ruling M5, plan 07 T6 fix round] `review._record_effect` composes the reject sentence
 * across EVERY episode that holds the object; with more than one it says "either A or B …
 * you must pass episode_id=… to say which" rather than naming the one this click will
 * actually send. The reject action below always POSTs `episodeId` — the current episode,
 * never a choice the reviewer makes — so the ambiguity is never true of what clicking
 * Reject here does. */
function reifyRejectEffect(effect: string | undefined, episodeId: string): string | undefined {
  if (!effect || !effect.includes('you must pass episode_id=')) return effect;
  return effect.replace(
    /either .+? — this object is shared; you must pass episode_id=\.\.\. to say which, and only that one loses the id/,
    `${episodeId} — the episode open on this board. Another episode also holds this object and keeps it`,
  );
}

/** The reason recorded on an Exclusion written from a review card. Fixed and honest: a
 * reviewer rejecting here has not typed a reason, and inventing a specific one would put
 * words in their mouth in a record a signer reads. */
const REJECT_REASON = 'rejected by the reviewer at G1';

function subjectFor(obj: G1Object, before: ObjectView | null): ReviewSubject {
  return {
    kind: obj.type === 'InsufficientEvidence' ? 'gap' : obj.type === 'Exclusion' ? 'exclusion' : 'assumption',
    id: obj.id,
    rev: obj.rev,
    what: obj.summary,
    confidence: obj.confidence,
    provenance: {
      sourceArtifact: obj.sourceArtifact,
      locator: obj.locator,
      extractor: obj.extractor,
    },
    // `explanation` is folded in for an `InsufficientEvidence` only: for a gap the
    // explanation IS the object's content (sought · looked in · not found because ·
    // would be resolved by), and it never names an extractor. For every other object
    // `_explanation` composes an authorship line that names the extractor — the
    // provider/model string honesty rule 3 keeps off every proposal-facing surface.
    ifWrong: [
      obj.type === 'InsufficientEvidence' ? obj.explanation : null,
      obj.ifWrong.statement,
    ].filter((s): s is string => Boolean(s)),
    indicators: obj.ifWrong.indicators,
    before,
    charterFields: charterFieldsFor(obj.type, before),
  };
}

/** The three AR 5-11 fields, editable — set ONLY for a Charter, and only once its raw
 * stored content has been read. A fetch failure leaves this `undefined` rather than
 * rendering three fields pre-filled with a guess. */
function charterFieldsFor(objType: string, before: ObjectView | null): CharterField[] | undefined {
  if (objType !== 'Charter' || !before) return undefined;
  const raw = before.object as Record<string, unknown>;
  return AR_5_11_FIELDS.map((key) => ({ key, value: charterFieldText(raw[key]) }));
}

export interface ReviewBundle { subject: ReviewSubject; actions: ReviewAction[]; before: ObjectView | null }

/** The one free-text field a reviewer may reword, per object type — the field whose
 * content IS the object's statement on the sheet. Anything else (a rank, a pointer, an
 * authority line) is not wording, and `accept`'s own reserved keys refuse most of it. */
const EDITABLE: Record<string, string> = { Assumption: 'statement', GroundRule: 'statement', Constraint: 'statement', Objective: 'name', Alternative: 'name', Evidence: 'title', Exclusion: 'reason' };

function editableFieldFor(obj: G1Object, before: ObjectView | null): { key: string; value: string } | undefined {
  const key = EDITABLE[obj.type];
  if (!key || !before) return undefined;
  const value = (before.object as Record<string, unknown>)[key];
  return typeof value === 'string' ? { key, value } : undefined;
}

/** The subject and the actions for one object, from the G1 sheet (`review._actions`
 * decides what is offered; `review._record_effect` wrote the sentences). Null when
 * the id is neither on the sheet nor among its gaps. */
export async function buildReview(sessionId: string, episodeId: string, objectId: string, review: G1Review): Promise<ReviewBundle | null> {
  const gap = review.gaps.find((g) => g.id === objectId);
  const obj = review.objects.find((o) => o.id === objectId);
  if (!obj && !gap) return null;
  const before = await apiGet<ObjectView>(`/session/${sessionId}/object/${objectId}`).catch(() => null);
  const actions: ReviewAction[] = [];
  const confirm = (effect: string): ReviewAction => ({
    label: 'Confirm gap', effect,
    run: async () => ({ kind: 'gaps', confirmed: (await apiPost<ConfirmGapsResponse>(`/session/${sessionId}/episode/${episodeId}/confirm-gaps`, {})).confirmed }),
  });
  if (obj) {
    if (obj.actions.includes('accept')) actions.push({
      label: 'Accept', effect: obj.recordEffect.accept ?? ACCEPT_FALLBACK,
      run: async (edits) => ({ kind: 'object', view: await apiPost<ObjectView>(`/session/${sessionId}/object/${obj.id}/accept`, edits && Object.keys(edits).length > 0 ? { edits } : {}) }),
    });
    if (obj.actions.includes('confirm')) actions.push(confirm(obj.recordEffect.confirm ?? CONFIRM_FALLBACK));
    if (obj.actions.includes('reject')) actions.push({
      label: 'Reject', destructive: true, effect: reifyRejectEffect(obj.recordEffect.reject, episodeId) ?? REJECT_FALLBACK,
      run: async () => ({ kind: 'record', label: 'Exclusion written', id: (await apiPost<{ id: string }>(`/session/${sessionId}/object/${obj.id}/reject`, { reason: REJECT_REASON, reasonType: 'out-of-scope', episodeId })).id }),
    });
    const subject = { ...subjectFor(obj, before), editableField: editableFieldFor(obj, before) };
    return { subject, actions, before };
  }
  const g = gap as G1Gap;
  const gapObject = review.objects.find((o) => o.id === g.id);
  if (!g.confirmed && g.confirmableHere) actions.push(confirm(gapObject?.recordEffect.confirm ?? CONFIRM_FALLBACK));
  return {
    before,
    actions,
    subject: { kind: 'gap', id: g.id, what: g.sought, ifWrong: [g.impact].filter(Boolean), indicators: g.indicatorsThatWouldResolve,
      provenance: { sourceArtifact: g.whereLookedFor.join('; ') || null, locator: null, extractor: null }, before },
  };
}
