// Readiness (spec §15) — the record scored against the standard, by the kernel.
//
// Nothing on this view is a judgement this interface made. `POST .../readiness` asks the
// kernel to score the episode against its policy's tailoring of the 36-question research
// standard; `GET` reads back whatever is already stored and never recomputes (the route's
// own contract). Every sentence beside a number here is the server's: the rating-scale
// caption, the scored tailoring's honesty note and the ready line are strings
// `kernel.render` writes for the rendered package, served through `_readiness_view`, so
// this view and the package can never say different things about the same report.
//
// The dimension verdicts print objectivity → validity → reliability, then any other key
// sorted — the order `kernel.render._readiness_body` uses, for the reason its own comment
// gives: the store sorts a dict's keys on save, so iterating `dimensionVerdicts` in
// whatever order `Object.keys` returns would disagree with the package over something
// that carries no meaning of its own.
//
// **No Ember.** §5 spends a view's one fill on the primary human act, and readiness is
// not one: the kernel scores the record and a person only asks it to. So "Score the
// record against the standard" is a bordered control, and the severity of what the
// report found is carried by the tints on the grid and the red left rule on each blocker
// — colour on a plane, a hairline and a glyph, never a lit button.
//
// **Where the states are.** A cell's tint and its glyph are both `StateGrid`'s
// (`data-cell-state`), the findings are `BlockerList`'s, and the gate ladder is built
// entirely from `episode.gateLadder`. This file holds no state table of its own, so
// there is nothing here that can drift from the kernel.
import { useState } from 'react';
import { apiPost, ApiError } from '../api/client';
import { useFetched } from '../api/useFetched';
import { useSession } from '../api/useSession';
import { useWorkspace } from '../api/useWorkspace';
import { BlockerList, type Finding } from '../components/BlockerList';
import { ErrorState } from '../components/ErrorState';
import { FieldsControl } from '../components/FieldsControl';
import { GateLadder } from '../components/GateLadder';
import { IdChip } from '../components/IdChip';
import { Loading } from '../components/Loading';
import { Num } from '../components/Num';
import { Sev, type SevKind } from '../components/Sev';
import { Simplex } from '../components/Simplex';
import { StateGrid } from '../components/StateGrid';
import { Term } from '../components/Term';
import { VerdictCard } from '../components/VerdictCard';
import { ViewHead } from '../components/ViewHead';
import { useFields, type FieldSpec } from '../lib/fields';
import type { ReadinessView } from '../types/api';

export const READINESS_FIELDS: FieldSpec[] = [
  { key: 'justification', label: 'what each rating was drawn from', default: false },
  { key: 'rule', label: 'the scoring rule behind each rating', default: false },
  { key: 'mandate', label: 'the mandate scorecard', default: true },
  { key: 'bias', label: 'bias checks', default: true },
];

const btn = 'og-label inline-flex min-h-11 items-center border border-hairline-strong px-3 text-b3';

const DIMENSION_ORDER = ['objectivity', 'validity', 'reliability'];

function orderedDimensions(verdicts: Record<string, unknown>): string[] {
  const known = DIMENSION_ORDER.filter((d) => d in verdicts);
  const rest = Object.keys(verdicts).filter((d) => !known.includes(d)).sort();
  return [...known, ...rest];
}

/** `ReadinessReport.flipSummary` — a bare dict on the schema (`additionalProperties`),
 * so it is read defensively and the figure is drawn only when the run it summarises
 * actually carried one. */
interface FlipSummaryView {
  simplexRobustness?: Record<string, number>;
  simplexRobustnessText?: Record<string, string>;
  nSimplex?: number;
  seed?: number;
}

export function Readiness() {
  const { sessionId, episodeId, episode, refetch } = useSession();
  const { toast, bumpRecord, openOverlay, recordVersion } = useWorkspace();
  const fields = useFields('readiness', READINESS_FIELDS);
  const [busy, setBusy] = useState(false);
  // The shared read, never a hand-rolled effect: it clears the error on a success, drops
  // the last episode's report rather than leaving it under this one's heading, cancels a
  // response nobody is waiting for any more, and re-reads whenever a write bumps the
  // record — which is what makes the button below show its own result.
  const path = sessionId && episodeId ? `/session/${sessionId}/episode/${episodeId}/readiness` : null;
  const fetched = useFetched<ReadinessView>(path, [recordVersion]);

  async function score() {
    if (!path) return;
    setBusy(true);
    try {
      await apiPost<ReadinessView>(path, { seed: 0 });
      toast('Scored. The report is a kernel object on the record.', 'done');
      // Both: `refetch` for the episode (it now names the report, so the ladder's
      // `readiness-present` rung changes), `bumpRecord` for this view's own read and for
      // the header counters and the map.
      refetch();
      bumpRecord();
    } catch (e) {
      toast(e instanceof ApiError ? (e.body.message ?? e.message) : String(e), 'stop');
    } finally {
      setBusy(false);
    }
  }

  if (!sessionId || !episodeId || !episode) {
    return <ViewHead eyebrow="readiness" title="Readiness" sentence="Choose a decision in the header first." />;
  }

  const report = fetched.data;
  // A 404 `no-readiness` is "nobody has scored this yet" — a state of the record, not a
  // failure of the read. Everything else is an error and is shown as one.
  const notScored =
    fetched.error instanceof ApiError &&
    fetched.error.status === 404 &&
    fetched.error.body.error === 'no-readiness';
  const readError = fetched.error && !notScored ? fetched.error : null;
  const sa = report?.standardsAssessment ?? null;
  const ms = report?.mandateScorecard ?? null;
  const dimensionVerdicts = (sa?.dimensionVerdicts ?? {}) as Record<string, { verdict: string; qualifier?: string }>;
  const flip = (report?.flipSummary ?? {}) as FlipSummaryView;
  // WHICH GLYPH THE STATE LINE TAKES, and why it is not simply `report.ready`.
  // `ready` is frozen at the moment the report was computed; `readyText` is not —
  // `kernel.render.ready_text` replaces it with "unavailable — record changed since the
  // readiness report" exactly when a live blocking finding exists that the report never
  // saw, which is to say exactly when `ready` can no longer be trusted. Reading the
  // boolean for the glyph and the string for the sentence would put a green tick beside
  // a sentence withdrawing it. So: the tick only when the kernel is still stating the
  // boolean it stored (`str(True)`/`str(False)`, Python's own casing), and the waiting
  // glyph whenever it has substituted anything else. The sentence stays verbatim either
  // way — this chooses a glyph, never a word. [review fix round 1, Important 1]
  const stated = report ? report.readyText === (report.ready ? 'True' : 'False') : false;
  const readyKind: SevKind = !stated ? 'wait' : report?.ready ? 'done' : 'blocking';
  const scoreAct = (
    <button type="button" onClick={() => void score()} disabled={busy} className={btn}>
      {busy ? 'scoring…' : report ? 'Score it again' : 'Score the record against the standard'}
    </button>
  );

  return (
    <div>
      <ViewHead
        eyebrow={`readiness · ${episodeId}`}
        title="Readiness"
        sentence="The record scored against the standard by the kernel — never by the AI, never by a person. What is lit is what the tailoring made applicable."
        right={<FieldsControl list="readiness" spec={READINESS_FIELDS} shownOverride={fields} />}
      />

      {/* On ANY read in flight, not only the first: switching the decision in the header
          leaves the last one's report on screen for as long as the new read takes, and a
          report under someone else's id with no sign that it is being replaced is how a
          reader ends up reading the wrong record. [review fix round 1, Minor 6] */}
      {fetched.loading && <Loading label="loading readiness" />}
      {readError && (
        <ErrorState
          message={readError.message}
          route={`session/${sessionId}/episode/${episodeId}/readiness`}
          onRetry={fetched.refresh}
        />
      )}

      {notScored && (
        <section className="mb-8 flex flex-col gap-3" data-panel="not-scored">
          <p className="text-b2">No readiness report has been produced for this decision.</p>
          <p className="text-b3 text-fg-secondary">Scoring reads the record as it stands and writes a report the kernel signs. It decides nothing and changes nothing else.</p>
          {/* Bordered, never Ember (§5): the kernel does the scoring, and asking it to is
              not the human decision this view exists around — there is no such decision
              here at all. */}
          <div>{scoreAct}</div>
        </section>
      )}

      {report && (
        <div className="flex flex-col gap-8">
          {/* The state line. `readyText` is `kernel.render.ready_text` verbatim, carrying
              its own staleness substitution — so this line cannot say the record is ready
              when the record has moved under the report, and `readyKind` above keeps the
              glyph from saying it either. The label around it is the one the rendered
              package prints above the same value. */}
          <p data-ready-line>
            <Sev kind={readyKind}>
              Ready (no blocking findings): <span className="og-mono text-m2" data-num="label">{report.readyText}</span>
              {' · '}tailoring <span className="og-mono text-m2" data-num="label">{report.tailoring ?? '_[unavailable]_'}</span>
              {' · '}k <span className="og-mono text-m2" data-num="label">{report.k ?? '_[unavailable]_'}</span>
            </Sev>
          </p>

          {sa && (
            <section className="flex flex-col gap-8" data-testid="standards-assessment">
              <section className="grid gap-3" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(min(16rem, 100%), 1fr))' }}>
                {orderedDimensions(dimensionVerdicts).map((dim) => (
                  <VerdictCard
                    key={dim}
                    dimension={dim}
                    verdict={dimensionVerdicts[dim]?.verdict ?? '_[unavailable]_'}
                    qualifier={dimensionVerdicts[dim]?.qualifier}
                  />
                ))}
              </section>

              <StateGrid
                ratings={sa.ratings ?? []}
                aggregationRule={sa.aggregationRule}
                ratingScaleCaption={report.standardsCaptions.ratingScale}
                tailoringNote={report.standardsCaptions.tailoringNote}
                assessmentId={sa.id}
                showJustification={fields.shown.justification}
                showRule={fields.shown.rule}
              />

              {/* Counted by the server (`_readiness_view`), never by the browser. */}
              <p className="og-label text-b3 text-fg-secondary">
                <Num value={report.applicableQuestions} from={sa.id} /> of{' '}
                <span className="og-mono" data-num="label">{report.totalQuestions}</span> questions applicable
              </p>
            </section>
          )}

          <section className="flex flex-col gap-2">
            <h2 className="og-display text-e2">What blocks sign-off</h2>
            <BlockerList findings={(report.blockers ?? []) as unknown as Finding[]} kind="blocker" />
          </section>

          <section className="flex flex-col gap-2">
            <h2 className="og-display text-e2">Worth knowing</h2>
            <BlockerList findings={(report.warnings ?? []) as unknown as Finding[]} kind="warning" />
          </section>

          {fields.shown.mandate && ms && (
            <section className="flex min-w-0 flex-col gap-2" data-panel="mandate">
              <h2 className="og-display text-e2">What the mandate asked for</h2>
              {(ms.rows ?? []).length === 0 ? (
                <p className="text-b3 text-fg-muted">no rows on this scorecard</p>
              ) : (
                <table className="w-full min-w-0 table-fixed text-left text-b3" data-testid="mandate-scorecard">
                  <tbody>
                    {(ms.rows ?? []).map((row, i) => (
                      <tr key={`${row.element}:${i}`} className="border-b border-hairline last:border-b-0">
                        <td className="break-words py-2">{row.element}</td>
                        <td className="og-mono break-words py-2 text-m2">{row.status}</td>
                        <td className="og-mono break-words py-2 text-m2 text-fg-muted" data-num="label">
                          {(row.satisfiedBy ?? []).join(', ')}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </section>
          )}

          {fields.shown.bias && (
            <section className="flex flex-col gap-2" data-panel="bias">
              <h2 className="og-display text-e2">Bias checks</h2>
              {(report.biasChecksStatus ?? []).length === 0 ? (
                <p className="text-b3 text-fg-muted">no bias check is recorded on this report</p>
              ) : (
                <ul className="flex flex-col gap-1 text-b3">
                  {(report.biasChecksStatus ?? []).map((row, i) => (
                    <li key={i} className="flex flex-wrap items-center gap-2" data-bias-row>
                      <span className="og-mono text-m2" data-num="label">{String(row.check ?? '')}</span>
                      <span aria-hidden className="text-fg-muted">→</span>
                      <span className="og-mono text-m2">{String(row.status ?? '')}</span>
                    </li>
                  ))}
                </ul>
              )}
              {(report.computedBiasRisks ?? []).length > 0 && (
                <p className="flex flex-wrap items-center gap-2 text-b3">
                  <span className="text-fg-secondary">risks the kernel computed:</span>
                  {(report.computedBiasRisks ?? []).map((id) => (
                    <IdChip key={id} id={id} onOpen={() => openOverlay({ kind: 'raw', id })} />
                  ))}
                </p>
              )}
            </section>
          )}

          {flip.simplexRobustness && flip.nSimplex !== undefined && flip.seed !== undefined && (
            <section className="flex flex-col gap-2">
              <h2 className="og-display text-e2"><Term k="simplex" plain="How often each option wins across all weightings" /></h2>
              <Simplex
                simplexRobustness={flip.simplexRobustness}
                simplexRobustnessText={flip.simplexRobustnessText}
                nSimplex={flip.nSimplex}
                seed={flip.seed}
                from={report.id}
              />
            </section>
          )}

          {((report.openGaps ?? []).length > 0 || (report.openExclusions ?? []).length > 0) && (
            <section className="flex flex-col gap-2">
              <h2 className="og-display text-e2">Still open</h2>
              {(report.openGaps ?? []).length > 0 && (
                <p className="flex flex-wrap items-center gap-2 text-b3">
                  <span className="text-fg-secondary">recorded absences:</span>
                  {(report.openGaps ?? []).map((id) => (
                    <IdChip key={id} id={id} onOpen={() => openOverlay({ kind: 'raw', id })} />
                  ))}
                </p>
              )}
              {(report.openExclusions ?? []).length > 0 && (
                <p className="flex flex-wrap items-center gap-2 text-b3">
                  <span className="text-fg-secondary">left out on purpose:</span>
                  {(report.openExclusions ?? []).map((id) => (
                    <IdChip key={id} id={id} onOpen={() => openOverlay({ kind: 'raw', id })} />
                  ))}
                </p>
              )}
            </section>
          )}
        </div>
      )}

      <section className="mt-8 flex flex-col gap-2">
        <h2 className="og-display text-e2">Where this decision stands</h2>
        <p className="text-b3 text-fg-secondary">Each rung lists the checks the kernel ran when the gate was tried. A person passes the gate; the kernel only refuses.</p>
        <GateLadder rungs={episode.gateLadder} />
      </section>

      {report && (
        // The panel footer: the report's own identity, and the one act this view offers
        // once a report exists. Identity metadata, not an analytical value — narrow
        // marked spans, the same treatment `RunSeal` gives a seal line.
        <div className="mt-8 flex flex-wrap items-center justify-between gap-3 border-t border-hairline pt-4">
          <p className="og-label break-words text-b3 text-fg-secondary">
            policy <span className="og-mono text-m2" data-num="label">{report.policyVersion}</span> · kernel{' '}
            <span className="og-mono text-m2" data-num="label">{report.kernelVersion}</span> · seed{' '}
            <span className="og-mono text-m2" data-num="label">{report.seed}</span> · scored{' '}
            <span className="og-mono text-m2" data-num="label">{report.createdAt}</span>
          </p>
          {scoreAct}
        </div>
      )}
    </div>
  );
}
