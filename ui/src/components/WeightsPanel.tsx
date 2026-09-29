// The Weights panel (Plan screen, pre-G2): a human's value judgement, typed directly —
// `POST /api/session/{s}/episode/{e}/weights` (`docket.agent.plan.author_weight_set`).
// No route existed for this before this task (`task-9b-report.md`'s "WeightSet gap"):
// `propose_plan` needs at least one `WeightSet` in the episode before it can build a
// plan step, and nothing ever wrote one for a live elicitation. The ledger's ruling
// (`.superpowers/sdd/2026-09-05-docket-07-frontend/progress.md`, last entry): weights
// are a human value judgement, never the agent's to propose.
//
// This panel does no arithmetic of its own. It does not sum the inputs, does not warn
// locally about a bad total, and does not pre-empt the server's own validation — the
// server's 422 message (`kernel.evaluate.check_weights`'s own wording, reused, never
// re-implemented here) is shown verbatim through the same `ErrorState` every other
// screen's error path already uses.
//
// One `WeightSet` per episode, at the deterministic id `ws-{episodeId}-human`
// (`docket.agent.plan._weight_set_id` — the id convention is documented there; this
// component computes the exact same string to read the set back on mount, before a
// human has revised anything in the current page load. If that convention ever
// changes, `_weight_set_id`'s own docstring says so, and this must change with it). A
// second submit supersedes the same id as a new revision, never a second set.
//
// Brand v3.0 (§5, §5a): the three field labels are sentence case in `og-label` — v1.2
// shouted them in mono caps, and v3.0 takes authority from size, never from caps. An
// objective's NAME is extracted prose, so it is body text; only the weights themselves,
// the set's id and its rev stay mono. Every input and the submit button clear the 44px
// touch floor. Nothing here is Ember: this panel is one control among several on the
// Plan screen, and the screen's one primary action is the G2 approval, not this save.

import { useEffect, useState } from 'react';
import { apiGet, apiPost, ApiError } from '../api/client';
import type { ObjectView } from '../types/api';
import type { Objective, WeightSet } from '../types/objects';
import { ErrorState } from './ErrorState';
import { Num } from './Num';
import { Provenance } from './Provenance';

export interface WeightsPanelProps {
  sessionId: string;
  episodeId: string;
  objectiveIds: string[];
  onWritten: () => void;
}

function humanWeightSetId(episodeId: string): string {
  return `ws-${episodeId}-human`;
}

export function WeightsPanel({ sessionId, episodeId, objectiveIds, onWritten }: WeightsPanelProps) {
  const [objectives, setObjectives] = useState<Record<string, Objective>>({});
  const [written, setWritten] = useState<ObjectView | null>(null);
  const [values, setValues] = useState<Record<string, string>>({});
  const [name, setName] = useState('');
  const [rationale, setRationale] = useState('');
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<{ message: string; route?: string } | null>(null);

  const objectiveKey = objectiveIds.join(',');

  // `episode.objectives` is a list of ids (`DecisionEpisode.objectives: {ref:
  // Objective}[]`), not resolved objects — one fetch per id to label each input with
  // the objective's own name rather than its bare id.
  useEffect(() => {
    let cancelled = false;
    Promise.all(
      objectiveIds.map((oid) =>
        apiGet<ObjectView>(`/session/${sessionId}/object/${oid}`)
          .then((v) => [oid, v.object as unknown as Objective] as const)
          .catch(() => [oid, null] as const),
      ),
    ).then((pairs) => {
      if (cancelled) return;
      setObjectives(
        Object.fromEntries(pairs.filter((p): p is [string, Objective] => p[1] !== null)),
      );
    });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId, objectiveKey]);

  // The existing WeightSet, if this episode already has one — read back and pre-filled
  // so a resubmit revises it rather than starting blank.
  useEffect(() => {
    setWritten(null);
    setValues({});
    setName('');
    setRationale('');
    setError(null);
    let cancelled = false;
    setLoading(true);
    apiGet<ObjectView>(`/session/${sessionId}/object/${humanWeightSetId(episodeId)}`)
      .then((view) => {
        if (cancelled) return;
        setWritten(view);
        const ws = view.object as unknown as WeightSet;
        setName(ws.name);
        setValues(
          Object.fromEntries(Object.entries(ws.weights).map(([k, v]) => [k, String(v)])),
        );
      })
      .catch(() => {
        // No WeightSet written yet for this episode — a 404, the expected first-visit
        // state, not an error to show.
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [sessionId, episodeId]);

  async function submit() {
    setSubmitting(true);
    setError(null);
    try {
      const weights = Object.fromEntries(
        objectiveIds.map((oid) => [oid, Number(values[oid] || '0')]),
      );
      const view = await apiPost<ObjectView>(`/session/${sessionId}/episode/${episodeId}/weights`, {
        name,
        weights,
        rationale: rationale.trim() ? rationale.trim() : null,
      });
      setWritten(view);
      onWritten();
    } catch (err) {
      setError({
        message: err instanceof ApiError ? err.message : err instanceof Error ? err.message : String(err),
        route: `session/${sessionId}/episode/${episodeId}/weights`,
      });
    } finally {
      setSubmitting(false);
    }
  }

  const writtenSet = written ? (written.object as unknown as WeightSet) : null;

  return (
    <div className="border border-hairline p-4 flex flex-col gap-3" data-testid="weights-panel">
      <p className="og-label text-b3 text-fg-muted">Weights</p>

      {loading && <p className="text-b3 text-fg-muted">loading…</p>}

      <div className="flex flex-col gap-2">
        {objectiveIds.map((oid) => (
          <label key={oid} className="flex flex-wrap items-center justify-between gap-3 text-b2">
            {/* An objective's own name is extracted prose, not a value anything
                computed — body text, and `data-num="label"` for the numeral walk. */}
            <span data-num="label">{objectives[oid]?.name ?? oid}</span>
            <input
              type="number"
              step="any"
              value={values[oid] ?? ''}
              onChange={(e) => setValues((v) => ({ ...v, [oid]: e.target.value }))}
              className="og-mono text-m1 min-h-11 w-28 border border-hairline bg-transparent px-2 text-right"
              data-testid={`weight-input-${oid}`}
            />
          </label>
        ))}
      </div>

      <label className="flex flex-col gap-1 text-b2">
        <span className="og-label text-b3 text-fg-muted">Name</span>
        <input
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
          className="text-b2 min-h-11 border border-hairline bg-transparent px-2"
          data-testid="weight-name"
        />
      </label>

      <label className="flex flex-col gap-1 text-b2">
        <span className="og-label text-b3 text-fg-muted">Rationale</span>
        {/* The human's own sentence about why these weights — prose they type and prose
            we show back, so body text, never mono. */}
        <textarea
          value={rationale}
          onChange={(e) => setRationale(e.target.value)}
          rows={2}
          className="text-b2 min-h-11 border border-hairline bg-transparent px-2 py-1"
          data-testid="weight-rationale"
        />
      </label>

      <button
        type="button"
        onClick={submit}
        disabled={submitting}
        className="og-label text-b3 inline-flex min-h-11 min-w-11 items-center justify-center self-start border border-hairline-strong px-4"
        data-testid="weight-submit"
      >
        {submitting ? 'saving…' : written ? 'Revise weights' : 'Save weights'}
      </button>

      {error && <ErrorState message={error.message} route={error.route} />}

      {writtenSet && written && (
        <Provenance authorType={written.authorType} actorId={written.authorId}>
          <div className="flex flex-col gap-1">
            {/* The object id (which embeds a random hex suffix on a live episode) and
                the revision number are both verbatim identifiers, not values anything
                computed — one `data-num="label"` span for the whole line, rather than
                relying on the numeral walk's generic object-id strip to cover the id
                half on its own. */}
            <p className="og-label text-m2 tracking-normal text-fg-muted" data-num="label">
              <span className="og-mono">{written.id}</span> · rev{' '}
              <span className="og-mono">{written.rev}</span>
            </p>
            {Object.entries(writtenSet.weights).map(([oid, w]) => (
              <p key={oid} className="text-b3 flex flex-wrap items-center gap-2">
                {/* An objective's own name is extracted prose, not a value anything
                    computed — the same label carve-out the input list above uses. */}
                <span data-num="label">{objectives[oid]?.name ?? oid}</span>
                <Num
                  value={w as number}
                  from={written.id}
                  valueText={
                    typeof written.valueText.weights === 'object' &&
                    written.valueText.weights !== null &&
                    !Array.isArray(written.valueText.weights)
                      ? (written.valueText.weights as Record<string, string>)[oid]
                      : undefined
                  }
                />
              </p>
            ))}
          </div>
        </Provenance>
      )}
    </div>
  );
}
