// The plan (spec §13) — the three acts of gate 2, in the order the record takes them:
// a person sets the weights, the AI proposes a plan from the model and the policy, a
// person approves that plan object, and only then may a person drive the episode across
// the gate. Three separate requests, on purpose: approving the plan and moving the
// decision are two different authorities even though the same person exercises both
// here, and the record keeps them apart.
//
// The one Ember moves. While the state is MODEL_APPROVED and nobody has approved the
// proposal, the recommended act is "Approve the plan" and that button carries the fill.
// The moment it is approved, that button is gone and `plan-approved-by-human` is met, so
// `GateChecklist` lights the gate button instead. The two can never coincide, because the
// very fact that lights the second is the fact that removes the first. `WeightsPanel`
// paints no Ember of its own (its own header says so), so nothing else on this view
// competes.
//
// No remedy buttons on this ladder. Every remedy `lib/checks.ts` knows for a gate-2 check
// routes to `/plan` — this view — and a button that navigates to the page you are already
// standing on reads as a chore and does nothing. `Model.tsx` established the rule for the
// charter's two checks (`REMEDIED_INLINE`); at gate 2 it happens to cover all four,
// because everything gate 2 wants is a control a few centimetres above the checklist.
// The two ids those remedies carry (`/plan#propose`, `/plan#approve`) are still on the
// sections below, because a ladder on ANOTHER view — the Needs queue, the Readiness
// ladder — does point at them, and that link must land on the right block.
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { apiPost, ApiError } from '../api/client';
import { useFetched } from '../api/useFetched';
import { useHealth } from '../api/useHealth';
import { useSession } from '../api/useSession';
import { useWorkspace } from '../api/useWorkspace';
import { ErrorState } from '../components/ErrorState';
import { FieldsControl } from '../components/FieldsControl';
import { GateChecklist, type Refusal } from '../components/GateChecklist';
import { Num } from '../components/Num';
import { Sev } from '../components/Sev';
import { Term } from '../components/Term';
import { ViewHead } from '../components/ViewHead';
import { WeightsPanel } from '../components/WeightsPanel';
import { useFields, type FieldSpec } from '../lib/fields';
import type { ObjectView } from '../types/api';
import type { Plan as PlanObject } from '../types/objects';

export const PLAN_FIELDS: FieldSpec[] = [
  { key: 'authority', label: 'the paragraph each step cites', default: true }, { key: 'measures', label: 'measures', default: false },
  { key: 'evaluator', label: 'evaluator model', default: false }, { key: 'sweeps', label: 'sensitivity sweeps', default: false },
];
const btn = 'og-label inline-flex min-h-11 items-center border border-hairline-strong px-3 text-b3';

export function Plan() {
  const { sessionId, episodeId, episode, refetch } = useSession();
  const { data: health } = useHealth();
  const { toast, bumpRecord, openOverlay, recordVersion } = useWorkspace();
  const navigate = useNavigate();
  const fields = useFields('plan', PLAN_FIELDS);
  const [busy, setBusy] = useState(false);
  // This browser's own refused attempt, kept only for the server's own words: the red
  // card itself is derived from the record below, so it survives leaving the view.
  const [attempt, setAttempt] = useState<Refusal | null>(null);
  const planId = episode?.plan ?? null;
  // The shared read (`useFetched`), never a hand-rolled effect: it clears the error on a
  // success, drops the previous episode's plan rather than leaving it under a new
  // episode's heading, and cancels a response the reader has already navigated away
  // from. A `null` path — no decision open, or an episode with no plan — reads nothing
  // and empties the panel, which is what switching to an episode without a plan must do.
  const planPath = sessionId && planId ? `/session/${sessionId}/object/${planId}` : null;
  const fetched = useFetched<ObjectView>(planPath, [recordVersion]);
  const plan = fetched.data;
  if (!sessionId || !episodeId || !episode) return <ViewHead eyebrow="plan" title="The plan" sentence="Choose a decision in the header first." />;
  const state = episode.lifecycleState;
  const open = state === 'MODEL_APPROVED';
  const rung = episode.gateLadder.find((r) => r.to === 'PLAN_APPROVED');
  const checks = rung?.checks ?? [];
  const p = plan?.object as unknown as PlanObject | undefined;
  // ONE source of truth for "is the plan approved", and it is the ladder's own check —
  // the same fact that lights the gate button. Reading it off the separately fetched plan
  // object instead would leave a frame in which the ladder already says yes (so the gate
  // is lit) while this view still says no (so the approval button is still lit): two
  // Embers, for as long as the two reads take to agree. `approvedBy` below is still the
  // plan object's, because only the object carries who approved it and when.
  const approved = checks.some((c) => c.name === 'plan-approved-by-human' && c.satisfied);
  const done = () => { refetch(); bumpRecord(); };
  async function act(fn: () => Promise<unknown>, ok: string) {
    setBusy(true);
    try { await fn(); toast(ok, 'done'); done(); }
    catch (e) { toast(e instanceof ApiError ? (e.body.message ?? e.message) : String(e), 'stop'); }
    finally { setBusy(false); }
  }
  async function gate() {
    setBusy(true); setAttempt(null);
    try { await apiPost(`/session/${sessionId}/episode/${episodeId}/transition`, { to: 'PLAN_APPROVED' }); toast('Gate passed. This decision is now PLAN_APPROVED.', 'done'); done(); }
    catch (e) { setAttempt({ message: e instanceof ApiError ? (e.body.message ?? e.message) : String(e), unsatisfied: e instanceof ApiError ? (e.body.unsatisfied ?? []) : [] }); toast('Refused. The attempt is in the record.', 'stop'); done(); }
    finally { setBusy(false); }
  }
  // The refusal is a fact of the record — a transition with `refused: true` — not a
  // variable this view keeps, so following a link and coming back still shows the red
  // card. Only while the gate is still open: past it, a refused attempt belongs to the
  // ladder's history, not to a warning about what pressing the button will do.
  const recorded = [...(episode.transitions ?? [])].reverse().find((t) => t.refused && t.to === 'PLAN_APPROVED');
  const refusal: Refusal | null = !open ? null
    : attempt ?? (recorded ? { unsatisfied: recorded.checksUnsatisfied, at: recorded.at, actorId: recorded.actor.actorId } : null);
  return (
    <div>
      <ViewHead eyebrow={`plan · ${episodeId}`} title="The plan" sentence="What the AI proposes to compute, step by step, each step citing the doctrine paragraph that requires it." right={<FieldsControl list="plan" spec={PLAN_FIELDS} shownOverride={fields} />} />
      {fetched.error && <ErrorState message={fetched.error.message} route={`session/${sessionId}/object/${planId}`} onRetry={fetched.refresh} />}
      {!planId && open && episode.objectives.length === 0 && (
        <p className="border border-hairline bg-raised p-4 text-b3 text-fg-secondary" data-panel="no-objectives">There is nothing to weigh: this decision names no objective, and weights are how much each objective counts. Agree the objectives on the model first.{' '}
          <button type="button" onClick={() => navigate('/model')} className="inline-flex min-h-11 items-center underline underline-offset-4">Open the model</button></p>
      )}
      {!planId && open && episode.objectives.length > 0 && (
        <section className="border border-hairline bg-raised p-4" data-panel="weights">
          <h2 className="og-display text-e2">Weights</h2>
          <p className="mb-3 text-b3 text-fg-secondary">How much each objective counts. A person sets them; the AI never does. They are read when the plan is proposed, so set them first.</p>
          <WeightsPanel sessionId={sessionId} episodeId={episodeId} objectiveIds={episode.objectives} onWritten={done} />
        </section>
      )}
      <section id="propose" className="mt-6 border border-hairline bg-raised p-4" data-panel="proposal">
        <h2 className="og-display text-e2">The proposal</h2>
        {!p && <><p className="mb-3 text-b3 text-fg-secondary">No plan yet. The AI proposes one from the model and the policy; every step must cite its authority or the gate refuses.</p>
          <button type="button" disabled={busy || !open} onClick={() => void act(() => apiPost(`/session/${sessionId}/episode/${episodeId}/plan`, {}), 'Plan proposed. Read every step before you approve it.')} className={btn}>Ask the AI to propose a plan</button></>}
        {p && plan && (<>
          <p className="break-words text-b3 text-fg-secondary" data-num="label">Proposed as <span className="og-mono text-m2">{plan.id}</span>, rev <Num value={plan.rev} from={plan.id} />, under policy <span className="og-mono text-m2">{p.policyBasis}</span>.
            {p.approvedBy ? <> Approved by <span className="og-mono text-m2" data-model-id>{p.approvedBy.actorId}</span> on <span className="og-mono text-m2">{p.approvedBy.date}</span>.</> : <> Nobody has approved it yet.</>}</p>
          {/* The Ember, unconditionally: this button exists only in the one state that
              earns it — the gate open, the ladder's own approval check unmet — so the
              guard that renders it IS the rule, and a second flag saying the same thing
              could only ever drift from it. The gate button lights off exactly the same
              check, so the moment it lights, this one is already gone. */}
          {!approved && open && <button type="button" disabled={busy} onClick={() => void act(() => apiPost(`/session/${sessionId}/plan/${plan.id}/approve`, {}), 'Plan approved, in your name. The gate can now be passed.')} className={`${btn} mt-3`} data-ember="">Approve the plan</button>}
          <button type="button" onClick={() => openOverlay({ kind: 'raw', id: plan.id })} className="og-label ml-2 mt-3 inline-flex min-h-11 items-center px-3 text-b3 underline underline-offset-4">Open the stored plan</button>
        </>)}
      </section>
      {p && plan && (<section className="mt-6" data-panel="steps">
        <h2 className="og-display mb-3 text-e2">Steps</h2>
        {p.steps.map((s) => (
          // `break-words`: a citation is free text ("Appendix, 'Overall Improvement'
          // (pp. 33–34) and Table A-3 (p. 35)") and a step's alternatives are a run of
          // hyphenated ids — both must wrap at 360 px, never clip and never widen the
          // column.
          <div key={s.id} className="break-words border-t border-hairline py-3 text-b3" data-plan-step={s.id}>
            <p className="og-label" data-num="label">Step <span className="og-mono text-m2 text-fg-muted">{s.id}</span> · <span className="og-mono text-m2">{s.method}</span>{fields.shown.evaluator && <span className="og-mono text-m2 text-fg-muted"> · {s.evaluator}</span>}</p>
            <p data-num="label">Compares <span className="og-mono text-m2">{s.alternatives.join(', ')}</span>{fields.shown.measures && <> on <span className="og-mono text-m2">{s.measures.join(', ')}</span></>} with weights <span className="og-mono text-m2">{s.weightSet}</span>.</p>
            {fields.shown.authority && <p className="text-fg-secondary" data-authority data-num="label"><span className="og-label">Required by</span> <span className="og-mono text-m2">{s.authority.document}</span> paragraph <span className="og-mono text-m2">{s.authority.paragraph}</span></p>}
            {fields.shown.sweeps && (s.sensitivitySweeps ?? []).length > 0 && <p className="og-mono text-m2 text-fg-muted" data-num="label">{(s.sensitivitySweeps ?? []).map((w) => `${w.kind} ${w.target}`).join(' · ')}</p>}
          </div>))}
        {state === 'PLAN_APPROVED' && <p className="mt-3"><Sev kind="wait">Every step is planned; none has run. The next act is on the Compute view.</Sev></p>}
      </section>)}
      <h2 className="og-display mt-8 mb-3 text-e2" id="approve" data-num="label"><Term k="g2" plain="Pass gate 2" /></h2>
      <GateChecklist gate="G2" to="PLAN_APPROVED" verb="Pass gate 2" checks={checks} open={open} onApprove={gate} refusal={refusal} busy={busy} remedies={{}} actor={health?.actorId ?? ''} />
    </div>
  );
}
