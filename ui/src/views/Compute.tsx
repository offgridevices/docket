// Compute (spec §14) — what the kernel did, sealed, and the one act that asks it to do it.
//
// Everything on this view is kernel-computed. `POST .../plan/{p}/dispatch` hands the
// approved plan to the kernel, which seals one `EvaluationRun` per step, computes a
// `FlipAnalysis` per sweep-eligible parameter and a `flip_summary` per run, and drives the
// episode to `EVALUATED` itself. The interface asks; it never computes, and it never
// re-sorts: every order on this view is the server's own.
//
// **Reconstructing an already-computed episode.** A fresh dispatch's own response already
// carries the full `EvaluationRun`/`FlipAnalysis` objects and a `flipSummaries` entry per
// run, so it is read straight from there. Arriving without one (a reload, or coming back
// from Readiness) rebuilds the same shape from three routes instead: `GET .../run/{r}`
// (`read_back` — ranking, results, seed, kernel version and each flip's brief, already in
// *id* order per `read_back`'s own sort, not a flip-distance ranking), `GET .../object/{runId}`
// for the seal fields `read_back` does not carry, and `GET .../object/{flipId}` per flip for
// the full `FlipAnalysis`.
//
// **Flip order.** `flip_summary` ranks flip ids shortest flip distance first, for exactly
// one run per episode (the episode's last). A freshly dispatched run's inline entry is used
// first; failing that `GET .../episode/{e}/readiness` is tried once, and its 404
// (`no-readiness`) means "not scored yet", not an error. With neither, `read_back`'s own id
// order is shown and `FlipChart` says so rather than presenting it as a ranking.
//
// **One read at a time.** These are several objects per run, so this view cannot hand the
// job to `useFetched`; it keeps that hook's rules instead — every response is stamped with
// the generation that asked for it and a response from an older generation is dropped, so
// switching the decision in the header can never leave one episode's runs under another
// episode's heading, and an error clears the board rather than sitting beside stale runs.
//
// **The one Ember** is "Run the plan", and only while the state is `PLAN_APPROVED`: that is
// the one moment a person is being asked for something here. Once anything has run, nobody
// is being asked to decide and this view carries no fill at all — `RunSeal`, `ResultTable`,
// `FlipChart` and `Simplex` each paint none of their own, deliberately. The only dashed rule
// on the view is `Term`'s glossary underline; nothing here is a gap.
import { useCallback, useEffect, useRef, useState } from 'react';
import { apiGet, apiPost, ApiError } from '../api/client';
import { openStream } from '../api/stream';
import { useSession } from '../api/useSession';
import { useWorkspace } from '../api/useWorkspace';
import { ErrorState } from '../components/ErrorState';
import { FieldsControl } from '../components/FieldsControl';
import { FlipChart, type FlipAnalysisView } from '../components/FlipChart';
import { Loading } from '../components/Loading';
import { Num } from '../components/Num';
import { ResultTable, type ResultEntry } from '../components/ResultTable';
import { RunSeal } from '../components/RunSeal';
import { Sev } from '../components/Sev';
import { Simplex } from '../components/Simplex';
import { Term } from '../components/Term';
import { ViewHead } from '../components/ViewHead';
import { useFields, type FieldSpec } from '../lib/fields';
import type { EpisodeView, ObjectView } from '../types/api';
import type { EvaluationRun, FlipAnalysis } from '../types/objects';

export const COMPUTE_FIELDS: FieldSpec[] = [
  { key: 'hashes', label: 'record and input hashes', default: true },
  { key: 'parameters', label: 'parameter bindings', default: false },
  { key: 'every-result', label: 'every result, not only aggregates', default: false },
  { key: 'sweeps', label: 'sensitivity sweeps', default: true },
];

/** The pre-gate sentence, verbatim from the screen this view replaces (`EmptyState`'s own
 * `byGate` branch, which that screen passed for exactly this state). */
const byGate = 'No numbers exist yet. Nothing is computed before the model is approved.';
/** …and the sentence for the other empty case, also the old screen's own: past gate 2 (or
 * off its path, as a superseded revision is) with nothing to hand the kernel. Saying
 * "nothing is computed before the model is approved" there would be a lie — that gate is
 * behind this episode, and what it lacks is a plan. */
const noPlan = 'This episode has no plan to dispatch yet.';
/** The two states from which gate 2 is still AHEAD — `kernel.lifecycle.EDGES` makes them
 * the only states whose forward path still runs through `PLAN_APPROVED`. Every other state
 * has passed that gate or left the path (`SUSPECT`, `SUPERSEDED`, `VOID`). */
const BEFORE_GATE_2 = new Set(['DRAFT', 'MODEL_APPROVED']);

interface ReadBackFlip {
  id: string;
  flipThreshold: number | null;
  flipDistance: number | null;
}

interface ReadBack {
  run: string;
  ranking: string[];
  results: Record<string, ResultEntry>;
  flips: ReadBackFlip[];
  seed: number;
  kernelVersion: string;
}

interface FlipSummary {
  run: string;
  ranked: string[];
  simplexRobustness: Record<string, number>;
  /** `_readiness_view`'s `_flip_summary_view` — present only when this summary came from
   * `GET .../readiness`, never on a fresh dispatch's inline copy. */
  simplexRobustnessText?: Record<string, string>;
  nSimplex: number;
  seed: number;
}

interface DispatchResult {
  runs: EvaluationRun[];
  flips: FlipAnalysis[];
  flipSummaries: FlipSummary[];
  episode: EpisodeView;
}

interface RunDisplay {
  run: EvaluationRun;
  readBack: ReadBack;
  flips: FlipAnalysisView[];
  ranked: boolean;
  flipSummary: FlipSummary | null;
  /** The object `Simplex` cites for `flipSummary`'s fractions: the `ReadinessReport` id
   * when the summary came from `GET .../readiness` (every committed fixture's case, since
   * `simplexRobustness` lives on `ReadinessReport.flipSummary`, not on the run), or the run
   * id when it arrived inline on a fresh dispatch response. */
  flipSummarySource: string;
}

async function fetchObject<T>(sessionId: string, id: string): Promise<T> {
  const view = await apiGet<ObjectView>(`/session/${sessionId}/object/${id}`);
  return view.object as unknown as T;
}

/** Like `fetchObject`, but also carries `valueText` — `object_view`'s own `str()` form of
 * each numeric field, so `<Num>` never reparses-and-restrings a float at a different
 * precision than the rendered package. */
async function fetchFlipAnalysis(sessionId: string, id: string): Promise<FlipAnalysisView> {
  const view = await apiGet<ObjectView>(`/session/${sessionId}/object/${id}`);
  return {
    ...(view.object as unknown as FlipAnalysis),
    valueText: view.valueText as FlipAnalysisView['valueText'],
  };
}

export function Compute() {
  const { sessionId, episodeId, episode, refetch } = useSession();
  const { toast, bumpRecord, recordVersion } = useWorkspace();
  const fields = useFields('compute', COMPUTE_FIELDS);
  const [runs, setRuns] = useState<RunDisplay[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [stageLabel, setStageLabel] = useState<string | null>(null);
  // This browser's own attempt at the act, kept for the server's own words — a gate
  // refusal itself is derived from the record below, so the card survives leaving the
  // view; only the wording is here. Stamped with the episode it was made against, so a
  // refusal can never appear under a decision it does not belong to.
  const [attempt, setAttempt] =
    useState<{ episode: string; message: string; unsatisfied: string[]; refused: boolean } | null>(null);
  // The READ's own error, owned by the effect below and cleared by it. Kept apart from the
  // act's: a write bumps `recordVersion`, which re-runs the read, and one slot would mean
  // every act erased its own answer the moment it finished.
  const [readError, setReadError] = useState<{ message: string } | null>(null);
  // The act is not over when the response lands: the header's own episode has not caught
  // up yet, so for those few frames the record still says "nothing has run". The button
  // stays out of reach until the refetched episode arrives, which is what makes a second
  // dispatch of the same plan impossible — cleared by the effect below, which fires when
  // `useSession` replaces the episode list.
  const [settling, setSettling] = useState(false);
  const generation = useRef(0);
  const closeStream = useRef<(() => void) | null>(null);

  const load = useCallback(
    async (ep: EpisodeView, fresh?: DispatchResult) => {
      if (!sessionId) return;
      const mine = ++generation.current;
      const current = () => generation.current === mine;
      setLoading(true);
      setReadError(null);
      try {
        let readinessFlipSummary: FlipSummary | null = null;
        let readinessReportId: string | null = null;
        try {
          const rr = await apiGet<{ id: string; flipSummary?: FlipSummary }>(
            `/session/${sessionId}/episode/${ep.id}/readiness`,
          );
          if (rr.flipSummary && rr.flipSummary.run) {
            readinessFlipSummary = rr.flipSummary;
            readinessReportId = rr.id;
          }
        } catch (err) {
          // "not scored yet" (404 no-readiness) is expected pre-Readiness; anything else
          // is a real failure and must surface, not be swallowed alongside it.
          if (!(err instanceof ApiError && err.status === 404)) throw err;
        }

        const freshRunObjs = new Map((fresh?.runs ?? []).map((r) => [r.id, r]));
        const freshFlipObjs = fresh?.flips ?? [];
        const freshSummaryByRun = new Map((fresh?.flipSummaries ?? []).map((s) => [s.run, s]));

        const out: RunDisplay[] = [];
        for (const runId of ep.runs) {
          const readBack = await apiGet<ReadBack>(`/session/${sessionId}/run/${runId}`);
          const runObj = freshRunObjs.get(runId) ?? (await fetchObject<EvaluationRun>(sessionId, runId));
          const flipIds = readBack.flips.map((f) => f.id);
          const freshForRun = freshFlipObjs.filter((f) => f.run === runId);
          const flips: FlipAnalysisView[] =
            freshForRun.length === flipIds.length && flipIds.length > 0
              ? freshForRun
              : await Promise.all(flipIds.map((id) => fetchFlipAnalysis(sessionId, id)));

          const usedFresh = freshSummaryByRun.has(runId);
          const summary = freshSummaryByRun.get(runId) ??
            (readinessFlipSummary?.run === runId ? readinessFlipSummary : null);
          // Cite the `ReadinessReport` the summary actually came from, not the run —
          // `simplexRobustness` lives on `ReadinessReport.flipSummary`. A fresh dispatch's
          // inline summary has no separate stored object yet, so the run id is the best
          // available reference for that one case.
          const flipSummarySource =
            summary === null ? runId : usedFresh ? runId : (readinessReportId ?? runId);

          let orderedFlips = flips;
          let ranked = false;
          if (summary) {
            const byId = new Map(flips.map((f) => [f.id, f]));
            const inOrder = summary.ranked
              .map((id) => byId.get(id))
              .filter((f): f is FlipAnalysisView => f !== undefined);
            if (inOrder.length === flips.length) {
              orderedFlips = inOrder;
              ranked = true;
            }
          }
          out.push({ run: runObj, readBack, flips: orderedFlips, ranked, flipSummary: summary, flipSummarySource });
        }
        if (current()) setRuns(out);
      } catch (err) {
        // The board is emptied with the error, never left standing beside it.
        if (current()) {
          setRuns(null);
          setReadError({ message: err instanceof Error ? err.message : String(err) });
        }
      } finally {
        if (current()) setLoading(false);
      }
    },
    [sessionId],
  );

  // Changing the DECISION empties the board at once: nothing of the last one may be left
  // under this one's heading, not even for the length of a read. Re-reading the SAME
  // decision (a write bumped the record, or its run list grew) deliberately does not — the
  // rows on screen belong to this episode either way, and blanking them would throw away a
  // fresh dispatch's own runs before the refetched episode had named them.
  useEffect(() => {
    setRuns(null);
    setReadError(null);
  }, [sessionId, episode?.id]);

  useEffect(() => {
    // Bumping the generation here is what drops a read already in flight — including in the
    // "this episode has no runs" case, which starts no read of its own that could notice,
    // and which must also put the loading panel away.
    generation.current++;
    if (!episode || episode.runs.length === 0) {
      setLoading(false);
      return;
    }
    void load(episode);
    // Only the episode's identity, its own run list and a write to the record re-trigger
    // this — `load` is stable across renders for a fixed `sessionId`.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId, episode?.id, episode?.runs.join(','), recordVersion]);

  // The act is settled the moment `useSession` hands back a new episode list — the record
  // this view is reading has caught up with the record it just wrote.
  useEffect(() => { setSettling(false); }, [episode]);

  // A dispatch left mid-flight by someone navigating away must not leave its EventSource
  // open; `finally` only covers the case where this view is still mounted to run it.
  useEffect(() => () => { closeStream.current?.(); closeStream.current = null; }, []);

  async function dispatch() {
    if (!sessionId || !episodeId || !episode?.plan) return;
    const asked = episodeId;
    setBusy(true);
    setAttempt(null);
    setStageLabel('stage: dispatch');
    // `wrote` decides whether the record moved and therefore whether anything needs
    // re-reading: a sealed run does, and so does the refused transition
    // `kernel.lifecycle.transition` writes on a 409. A 403 refuses before any write and a
    // 422 is the kernel declining to compute at all — neither leaves anything to re-read,
    // and bumping for them would only wipe the answer off the screen.
    let wrote = false;
    closeStream.current = openStream(sessionId, (evt) => {
      if (evt.event === 'stage') setStageLabel(`stage: ${evt.data.stage}`);
      if (evt.event === 'error') setAttempt({ episode: asked, message: evt.data.message, unsatisfied: [], refused: false });
    });
    try {
      const res = await apiPost<DispatchResult>(`/session/${sessionId}/plan/${episode.plan}/dispatch`, { seed: 0 });
      wrote = true;
      setSettling(true);
      await load(res.episode, res);
      // Whatever the stream said along the way, the act itself succeeded: the card it
      // raised is about an attempt that is now over.
      setAttempt(null);
      toast('Every step ran and was sealed. The decision is now EVALUATED.', 'done');
    } catch (err) {
      // A 403 (`AuthorityViolation`, dispatch itself refused) and a 409
      // (`TransitionRefused`, the `EVALUATED` transition dispatch drives after a successful
      // evaluation) are refusals BY NAME, and the record keeps them; `unsatisfied` only
      // exists on the 409 shape. Anything else — a 422 from the kernel's own validation,
      // an unreachable server — is an error, printed with the route that produced it,
      // because nothing was written and there is no refusal in the record to point at.
      const message = err instanceof ApiError ? (err.body.message ?? err.message)
        : err instanceof Error ? err.message : String(err);
      wrote = err instanceof ApiError && err.status === 409;
      setAttempt({
        episode: asked,
        message,
        unsatisfied: err instanceof ApiError ? (err.body.unsatisfied ?? []) : [],
        refused: err instanceof ApiError && (err.status === 403 || err.status === 409),
      });
      if (wrote) setSettling(true);
      toast(message, 'stop');
    } finally {
      setBusy(false);
      setStageLabel(null);
      closeStream.current?.();
      closeStream.current = null;
      if (wrote) {
        refetch();
        bumpRecord();
      }
    }
  }

  if (!sessionId || !episodeId || !episode) {
    return <ViewHead eyebrow="compute" title="Compute" sentence="Choose a decision in the header first." />;
  }
  const state = episode.lifecycleState;
  const canRun = state === 'PLAN_APPROVED' && !!episode.plan;
  const hasRuns = (episode.runs?.length ?? 0) > 0;
  // Exactly one sentence, chosen once: a run on record is a fact and outranks everything,
  // then the act that is open, then — depending on which side of gate 2 this decision
  // stands on — why there is nothing here at all.
  const line = hasRuns ? 'done' : canRun ? 'wait' : BEFORE_GATE_2.has(state) ? 'pre-gate' : 'no-plan';
  // The refusal is a fact of the record — a transition to `EVALUATED` written with
  // `refused: true` and the checks that were unmet — not a variable this view keeps, so
  // following a link and coming back still shows it. The LAST attempt on record is the one
  // that counts: an episode refused once and then run carries both, and only the later of
  // the two says where it stands. The live attempt wins over either, because only the
  // server's own answer carries the wording.
  const lastOnRecord = [...(episode.transitions ?? [])].reverse().find((t) => t.to === 'EVALUATED');
  const recorded = lastOnRecord?.refused ? lastOnRecord : null;
  const live = attempt?.episode === episodeId ? attempt : null;
  const refusal = (live?.refused ? live : null) ??
    (recorded
      ? { message: `Asked at ${recorded.at} by ${recorded.actor.actorId}; no run was sealed.`, unsatisfied: recorded.checksUnsatisfied }
      : null);

  return (
    <div>
      <ViewHead
        eyebrow={`compute · ${episodeId}`}
        title="Compute"
        sentence="Every run is sealed by the kernel: inputs hashed, outputs hashed, seed recorded. The AI never touches a number here."
        right={<FieldsControl list="compute" spec={COMPUTE_FIELDS} shownOverride={fields} />}
      />
      {line === 'wait' && <p className="mb-4"><Sev kind="wait">The plan is approved and nothing has run. Press Run the plan; the kernel computes every step and seals each run.</Sev></p>}
      {line === 'done' && <p className="mb-4"><Sev kind="done">Every planned step has a sealed run.</Sev></p>}
      {line === 'pre-gate' && <p className="mb-4 text-b3 text-fg-secondary">{byGate}</p>}
      {line === 'no-plan' && <p className="mb-4 text-b3 text-fg-secondary">{noPlan}</p>}
      {canRun && (
        <button type="button" onClick={() => void dispatch()} disabled={busy || settling} data-ember=""
          className="og-label mb-6 inline-flex min-h-11 items-center border border-hairline-strong px-4 text-b3">
          {busy || settling ? 'computing…' : 'Run the plan'}
        </button>
      )}

      {(busy || (loading && !runs)) && <Loading label={stageLabel ?? 'loading'} />}
      {refusal && <ErrorState kind="refused" message={refusal.message} unsatisfied={refusal.unsatisfied} />}
      {live && !live.refused && <ErrorState message={live.message} route={`session/${sessionId}/plan/${episode.plan}/dispatch`} />}
      {readError && <ErrorState message={readError.message} />}

      {runs && runs.length > 0 && (
        <div className="flex flex-col gap-8">
          <section className="flex flex-col gap-3">
            <h2 className="og-display text-e2"><Term k="run" plain="Runs sealed" /></h2>
            <div className="flex flex-col gap-3">
              {runs.map((r) => (fields.shown.hashes
                ? <RunSeal key={r.run.id} run={r.run} />
                // With the hashes off, the run is still named: a seal nobody is reading the
                // hashes of is one line, not a card of eight.
                : <p key={r.run.id} className="og-label text-m2 tracking-normal break-words text-fg-secondary">sealed run <span className="og-mono">· {r.run.id}</span></p>
              ))}
            </div>
          </section>

          {runs.map((r) => (
            <section key={r.run.id} data-testid="run-section" data-run-section data-run-id={r.run.id}
              className="flex min-w-0 flex-col gap-6 border-t border-hairline pt-6">
              {/* A run id is an identifier — mono, and one of the few things on this view
                  that stays that way. */}
              <p className="og-mono text-m2 break-words text-fg-secondary">{r.run.id}</p>

              <div className="flex min-w-0 flex-col gap-2">
                <h2 className="og-display text-e2">Ranking and results</h2>
                <ResultTable results={r.readBack.results} ranking={r.readBack.ranking} />
                {fields.shown['every-result'] && (
                  <table className="mt-2 w-full min-w-0 table-fixed text-left text-b3" data-testid="every-result">
                    <tbody>
                      {Object.entries(r.readBack.results).map(([resultId, res]) => (
                        <tr key={resultId} className="border-b border-hairline last:border-b-0">
                          <td className="og-mono text-m2 break-words">{res.measure ?? 'aggregate'}</td>
                          <td className="og-mono text-m2 break-words">{res.alternative}</td>
                          <td className="break-words"><Num value={res.value} units={res.units} valueText={res.valueText} from={resultId} /></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>

              {fields.shown.parameters && (
                <pre className="og-mono text-m2 min-w-0 whitespace-pre-wrap break-all text-fg-secondary" data-num="label">
                  {JSON.stringify(r.run.parameterBindings, null, 2)}
                </pre>
              )}

              {fields.shown.sweeps && (
                <>
                  <div className="flex flex-col gap-2">
                    <h2 className="og-display text-e2"><Term k="flip" plain="What flips the decision" /></h2>
                    <FlipChart flips={r.flips} ranked={r.ranked} />
                  </div>
                  {r.flipSummary && (
                    <Simplex
                      simplexRobustness={r.flipSummary.simplexRobustness}
                      simplexRobustnessText={r.flipSummary.simplexRobustnessText}
                      nSimplex={r.flipSummary.nSimplex}
                      seed={r.flipSummary.seed}
                      from={r.flipSummarySource}
                    />
                  )}
                </>
              )}

              {/* One panel footer line (`kernelVersion · seed · hash`) instead of repeating
                  the run's own stamp under every numeral above. "kernel", "seed" and
                  "record" are labels naming what follows them; a kernel version, a seed and
                  a record hash are exactly the numerals mono is reserved for. */}
              <p className="og-label text-b3 break-words text-fg-secondary" data-testid="run-footer">
                kernel <span className="og-mono text-m2" data-num="label">{r.run.kernelVersion}</span> · seed{' '}
                <span className="og-mono text-m2" data-num="label">{r.run.seed}</span> · record{' '}
                <span className="og-mono text-m2" title={r.run.runRecordHash} data-full-hash={r.run.runRecordHash} data-num="label">
                  {r.run.runRecordHash.slice(0, 12)}…
                </span>
              </p>
            </section>
          ))}
        </div>
      )}
    </div>
  );
}
