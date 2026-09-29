// Every object in the model (spec §10) — the gate the whole proposal rests on. The
// human approval sits on the MODEL, not on the answer: catching a wrong question is
// cheap, catching a wrong answer is not, and nothing is computed until this gate opens.
//
// Everything here is `agent.review.g1_review(g, episode_id)`, rendered. The view does not
// restate the checklist (the checks are the gate's own predicates, called), does not
// decide what an action means for a type (`review._actions` decides), and does not write
// the sentence a reviewer reads before clicking (`review._record_effect` does).
//
// The one Ember is the gate button, and only when every check is met. The charter is
// inline and editable because the field the source never states is the commonest reason
// this gate refuses, and a reviewer should not have to go looking for the box to fix it.
import { useCallback, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { apiPost, ApiError } from '../api/client';
import { useEpisode, useG1 } from '../api/useG1';
import { useHealth } from '../api/useHealth';
import { useNeeds } from '../api/useNeeds';
import { useSession } from '../api/useSession';
import { useWorkspace } from '../api/useWorkspace';
import { CharterFields } from '../components/CharterFields';
import { ErrorState } from '../components/ErrorState';
import { FieldsControl } from '../components/FieldsControl';
import { GateChecklist, type Refusal } from '../components/GateChecklist';
import { Loading } from '../components/Loading';
import { Num } from '../components/Num';
import { ObjectCard } from '../components/ObjectCard';
import { Sev } from '../components/Sev';
import { Term } from '../components/Term';
import { ViewHead } from '../components/ViewHead';
import { remedyFor } from '../lib/checks';
import { useFields, type FieldSpec } from '../lib/fields';
import type { G1Object } from '../types/api';

export const MODEL_FIELDS: FieldSpec[] = [
  { key: 'page', label: 'source page', default: false }, { key: 'id', label: 'object id', default: false },
  { key: 'confidence', label: 'how sure the draft was', default: false }, { key: 'agreed', label: 'who agreed', default: false },
  { key: 'rev', label: 'revision', default: false },
];
const SECTIONS: [string, string[]][] = [['Objectives', ['Objective']], ['Options', ['Alternative']], ['Ground rules, constraints and assumptions', ['GroundRule', 'Constraint', 'Assumption']], ['Evidence', ['Evidence']]];
/** The types that have a place of their own above; everything else the gate reaches is
 * listed at the foot, so the emphasis is a choice and never a silence. The episode
 * itself is in that list: the gate reads it, and it is not part of the model a person
 * approves here. */
const HANDLED = new Set(['Charter', 'Objective', 'Alternative', 'GroundRule', 'Constraint', 'Assumption', 'Evidence', 'InsufficientEvidence', 'Exclusion']);
/** The two checks whose remedy is the charter block on this very view — the three
 * fields are editable there and "Save the charter" writes them under your name. A
 * button on the ladder that only scrolled the page would be noise. */
const REMEDIED_INLINE = new Set(['charter-three-fields', 'charter-human-accepted']);

function NoDecision() {
  return <ViewHead eyebrow="model" title="Every object in the model" sentence="Choose a decision in the header first." />;
}

export function Model() {
  const { sessionId, episodeId, episode, refetch } = useSession();
  const g1 = useG1(sessionId, episodeId);
  const ep = useEpisode(sessionId, episodeId);
  const needs = useNeeds(sessionId, episodeId);
  const { data: health } = useHealth();
  const { openOverlay, toast, bumpRecord } = useWorkspace();
  const navigate = useNavigate();
  const fields = useFields('model', MODEL_FIELDS);
  // This browser's own refused attempt, kept only for the server's own words: the red
  // card itself is derived from the record below, so it survives leaving the view.
  const [attempt, setAttempt] = useState<Refusal | null>(null);
  const [charterUnavailable, setCharterUnavailable] = useState(false);
  const [busy, setBusy] = useState(false);
  // Every write bumps the record; `useG1`/`useEpisode` re-read on that bump, so the
  // cards, the checklist, the header counters and the map all move together.
  const refreshAll = useCallback(() => { refetch(); bumpRecord(); }, [refetch, bumpRecord]);

  const review = g1.data;
  const linchpinIds = useMemo(
    () => new Set((needs.data?.items ?? []).filter((i) => i.kind === 'linchpin-unreviewed').map((i) => i.objectId)),
    [needs.data],
  );
  if (!sessionId || !episodeId) return <NoDecision />;
  const charter = review?.objects.find((o) => o.type === 'Charter') ?? null;
  const open = review?.lifecycleState === 'DRAFT';
  const firstGap = review?.gaps.find((g) => !g.confirmed)?.id ?? null;
  const firstLinchpin = (review?.objects ?? []).find((o) => linchpinIds.has(o.id))?.id ?? null;
  const ctx = { charterId: charter?.id ?? null, firstGap, firstLinchpin };
  // The charter's two checks are remedied inline — unless the inline block could not be
  // read, in which case the ladder puts its own remedy back rather than pointing at a
  // box that is not on the page.
  const remedies = Object.fromEntries((review?.checks ?? []).map(
    (c) => [c.name, REMEDIED_INLINE.has(c.name) && !charterUnavailable ? null : remedyFor(c.name, ctx)]));
  const unreadLinchpin = (review?.objects ?? []).some((o) => linchpinIds.has(o.id));
  // The refusal is a fact of the record — a transition with `refused: true` — not a
  // variable this view keeps: following a remedy and coming back re-mounts the view, and
  // the red card has to still be there. Only while the gate is still open: once the
  // decision is past it, the attempt belongs to the gate ladder's history, not to a
  // warning about what pressing the button will do.
  const recorded = [...(ep.data?.transitions ?? [])].reverse().find((t) => t.refused && t.to === 'MODEL_APPROVED');
  const refusal: Refusal | null = !open ? null
    : attempt ?? (recorded ? { unsatisfied: recorded.checksUnsatisfied, at: recorded.at, actorId: recorded.actor.actorId } : null);

  async function approve() {
    setBusy(true); setAttempt(null);
    try {
      await apiPost(`/session/${sessionId}/episode/${episodeId}/transition`, { to: 'MODEL_APPROVED' });
      toast('Gate passed. This decision is now MODEL_APPROVED.', 'done'); refreshAll();
    } catch (e) {
      const message = e instanceof ApiError ? (e.body.message ?? e.message) : String(e);
      setAttempt({ message, unsatisfied: e instanceof ApiError ? (e.body.unsatisfied ?? []) : [] });
      toast('Refused. The attempt is in the record, and the checklist names what is missing.', 'stop'); refreshAll();
    } finally { setBusy(false); }
  }
  // A card on this view opens the review over the board, which is what a card promises.
  // The ADDRESS `/review/:objectId` — where the ladder's remedies and the queue's cards
  // point — is the Review view's own (Task 11), not an overlay this view opens over itself.
  const card = (o: G1Object, act: string) => (
    <ObjectCard key={o.id} id={o.id} type={o.type} title={o.summary} authorType={o.authorType} confidence={o.confidence} locator={o.locator} rev={o.rev}
      linchpin={linchpinIds.has(o.id)} fields={fields.shown} act={act}
      onOpen={() => openOverlay({ kind: 'review', id: o.id })} onRaw={() => openOverlay({ kind: 'raw', id: o.id })} />
  );
  const grid = 'grid gap-3 [grid-template-columns:repeat(auto-fit,minmax(min(300px,100%),1fr))]';
  return (
    <div>
      <ViewHead eyebrow={`model · ${episodeId}`} title="Every object in the model" sentence="Everything the AI drafted and everything a person has agreed, in the order the gate reads them." right={<FieldsControl list="model" spec={MODEL_FIELDS} shownOverride={fields} />} />
      {g1.loading && !review && <Loading label="the model" />}
      {g1.error && <ErrorState message={g1.error.message} route={`session/${sessionId}/episode/${episodeId}/g1`} onRetry={g1.refresh} />}
      {review && review.objects.length === 0 && <ErrorState message="Nothing to review yet. File a request first." />}
      {review && review.objects.length > 0 && !charter && (
        <div className="border border-hairline bg-raised p-4">
          <p className="text-b2">This decision holds no charter, so there is nothing for the gate to read: the charter is the question, the stakes and the scope, and every check at this gate starts from it.</p>
          <p className="mt-3"><button type="button" onClick={() => navigate('/request')} className="og-label inline-flex min-h-11 items-center border border-hairline-strong px-4 text-b3">File the request</button></p>
        </div>
      )}
      {review && charter && (
        <>
          <h2 className="og-display mt-2 mb-3 text-e2">The charter <span className="og-mono break-words text-m2 text-fg-muted" data-num="label">{charter.id} · rev <Num value={charter.rev} from={charter.id} /></span></h2>
          <CharterFields sessionId={sessionId} charterId={charter.id} editable={!!open} onWritten={refreshAll} onUnavailable={setCharterUnavailable} />
          <p className="mt-2 text-b3 text-fg-secondary">The <Term k="charter" /> holds three mandated fields; an empty one is typed here, and saving puts your name on the charter.</p>
          {SECTIONS.map(([title, types]) => {
            const items = review.objects.filter((o) => types.includes(o.type));
            return (<section key={title}><h2 className="og-display mt-8 mb-3 text-e2">{title}</h2>
              {title.startsWith('Ground') && unreadLinchpin && <p className="mb-2"><Sev kind="blocking">Some of these are assumptions the answer depends on, and no person has read them.</Sev></p>}
              {items.length === 0 ? <p className="text-b3 text-fg-muted">nothing of this kind in the record</p> : <div className={grid}>{items.map((o) => card(o, o.authorType === 'agent' ? (o.type === 'Assumption' ? 'Read it' : 'Agree or change it') : 'Open it'))}</div>}</section>);
          })}
          <h2 className="og-display mt-8 mb-3 text-e2">What the source never says</h2>
          <div className={grid}>{review.gaps.map((g) => (
            <div key={g.id} className={`flex min-w-0 flex-col gap-2 border bg-raised p-3 ${g.confirmed ? 'border-hairline-strong' : 'border-dashed border-ai-line'}`} data-object-id={g.id} data-object-type="InsufficientEvidence">
              <span className={`og-label inline-flex min-h-8 w-fit items-center border px-2 text-b3 ${g.confirmed ? 'border-done-line bg-done-tint text-done' : 'border-wait-line bg-wait-tint text-wait'}`}>{g.confirmed ? 'confirmed by a person' : 'unconfirmed'}</span>
              <p className="text-b3" data-num="label"><Term k="gap" />: {g.sought}</p>
              {g.confirmedBy?.actorId && <p className="og-mono break-words text-m2 text-fg-secondary" data-num="label" data-model-id>{`${g.confirmedBy.actorId} · ${g.confirmedBy.date ?? ''}`}</p>}
              <button type="button" onClick={() => openOverlay({ kind: 'review', id: g.id })} className="og-label inline-flex min-h-11 w-fit items-center border border-hairline-strong px-3 text-b3">{g.confirmed ? 'Open it' : 'Confirm the absence'}</button>
            </div>))}{review.gaps.length === 0 && <p className="text-b3 text-fg-muted">no absence is recorded on this episode</p>}</div>
          <h2 className="og-display mt-8 mb-3 text-e2">Left out on purpose</h2>
          <div className={grid}>{review.exclusions.map((x) => (
            <div key={x.id} className="flex min-w-0 flex-col gap-1 border border-hairline-strong bg-raised p-3 text-b3" data-object-id={x.id} data-object-type="Exclusion">
              <span className="og-label"><Term k="exclusion" /> <span className="og-mono text-m2 text-fg-muted">{x.reasonType}</span></span>
              <p data-num="label">{`${x.targetKind ?? '—'} · ${x.targetLabel}`}</p><p className="text-fg-secondary" data-num="label">{x.reason}</p>
              <p className="og-mono break-words text-m2 text-fg-muted" data-num="label" data-model-id>{`${x.authorityWho ?? '—'} (${x.authorityRole ?? '—'})`}</p>
            </div>))}{review.exclusions.length === 0 && <p className="text-b3 text-fg-muted">no omission is recorded on this episode</p>}</div>
          <h2 className="og-display mt-8 mb-3 text-e2">Other objects this decision reaches</h2>
          <ul className="og-mono text-m2 text-fg-secondary">{review.objects.filter((o) => !HANDLED.has(o.type)).map((o) => <li key={o.id} data-object-id={o.id} data-num="label"><button type="button" onClick={() => openOverlay({ kind: 'raw', id: o.id })} className="inline-flex min-h-11 max-w-full items-center break-words text-left underline underline-offset-4">{o.type} · {o.id}</button></li>)}</ul>
          <section className="mt-8 border border-hairline p-4" data-panel="scoring">
            <h2 className="og-display text-e2">{review.ratingRelevantHeading}</h2>
            <p className="text-b2">{review.ratingRelevantLine}</p><p className="text-b3 text-fg-secondary">{review.ratingRelevantBoundary}</p>
            <ul className="mt-2 flex flex-col gap-2">{review.ratingRelevant.map((r) => (
              <li key={`${r.objectId}:${r.field}`} className="border-t border-hairline pt-2 text-b3" data-object-id={r.objectId}>
                <span className="og-mono break-words text-m2 text-fg-muted" data-num="label">{r.objectId} · {r.field}</span> — <span data-num="label">{r.summary}</span>{' '}
                {typeof r.value === 'number' ? <Num value={r.value} from={r.objectId} /> : <span className="og-mono" data-num="label">{typeof r.value === 'string' ? r.value : JSON.stringify(r.value)}</span>}
                <p className="text-fg-secondary" data-num="label">{r.why}</p></li>))}</ul>
            {review.ratingRelevant.length === 0 && <p className="text-b3 text-fg-muted">no model-authored value on this episode reaches a rating</p>}
          </section>
          <h2 className="og-display mt-8 mb-3 text-e2" data-num="label"><Term k="g1" plain="Approve the model (gate 1)" /></h2>
          <GateChecklist gate="G1" to="MODEL_APPROVED" verb="Approve the model" checks={review.checks} open={!!open} onApprove={approve} refusal={refusal} busy={busy} remedies={remedies} actor={health?.actorId ?? ''} />
          {!open && episode && <p className="mt-2 text-b3 text-fg-secondary">This episode is at <span className="og-mono text-m2">{episode.lifecycleState}</span>. The board is the record of what was approved.</p>}
          {ep.data && <p className="mt-2 text-m1 text-fg-muted">The gate ladder, with every transition and check, is on the Readiness view. <button type="button" onClick={() => navigate('/readiness')} className="inline-flex min-h-11 items-center underline underline-offset-4">Open it</button></p>}
        </>
      )}
    </div>
  );
}
