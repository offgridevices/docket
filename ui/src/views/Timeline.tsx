// The programme (spec §17) — every episode of one decision over the years, what changed
// between them, and how long it has been since the last one.
//
// **The browser computes nothing.** Every number on this view is served: the days each
// episode lived, the whole months between consecutive episodes, the months since the
// latest one and the re-accreditation clock all come from `timeline.timing`
// (`kernel.clock.programme_timing`, computed at request time against the server's own
// `now`). There is no date arithmetic here, and no counting — a browser that worked out
// "38 months since" for itself would be a second, unrecorded clock, and the two would
// disagree the first time a timestamp form changed.
//
// Reads go through `useFetched`: `Loading` on any read in flight (so switching the
// header's decision never leaves another programme's episodes on screen), `ErrorState`
// with retry, defensive `?? []` reads throughout.
//
// **The one Ember.** Opening a refresh is the human act this view exists around, and it
// is lit only while there is one to perform — a trigger filed on the programme that no
// episode has opened. §5 allows exactly one fill per view whatever the record holds, so
// when the record carries several unopened triggers the leading one is lit and the rest
// are bordered. With nothing filed, nothing on this view is lit at all.
//
// Everything the pre-rebuild screen did that the record still needs is here unchanged:
// the diff panel and its `DiffRow`s, the trigger markers, the 3×3 sub-episode verdict
// grid with its standing GAO caption, and the watch tray (the agent proposes, a person
// files, and only then may a person open a refresh).

import { useEffect, useMemo, useState } from 'react';
import { CalendarClock } from 'lucide-react';
import { apiGet, apiPost } from '../api/client';
import { useFetched } from '../api/useFetched';
import { useSession } from '../api/useSession';
import { useWorkspace } from '../api/useWorkspace';
import { DiffRow } from '../components/DiffRow';
import { EmptyState } from '../components/EmptyState';
import { ErrorState } from '../components/ErrorState';
import { FieldsControl } from '../components/FieldsControl';
import { Loading } from '../components/Loading';
import { Num } from '../components/Num';
import { Sev } from '../components/Sev';
import { ViewHead } from '../components/ViewHead';
import { GAO_23_106549_CAPTION } from '../lib/captions';
import { useFields, type FieldSpec } from '../lib/fields';
import { plainState } from '../lib/format';
import { ICON_PROPS } from '../lib/icons';
import type { EpisodeView, TimelineResponse, TimelineTiming, WatchResponse } from '../types/api';
import type { DecisionEpisode, EpisodeDiff, RefreshTrigger } from '../types/objects';

export const TIMELINE_FIELDS: FieldSpec[] = [
  { key: 'diff-ids', label: 'object ids on diff rows', default: false },
  { key: 'triggers', label: 'triggers filed on the programme', default: true },
  { key: 'verdict-grid', label: 'the verdict grid', default: true },
  { key: 'days', label: 'days each episode lived', default: true },
];

const btn = 'og-label text-b3 inline-flex min-h-11 min-w-11 items-center justify-center border border-hairline-strong px-3';

const DIMENSIONS = ['objectivity', 'validity', 'reliability'] as const;

interface SubEpisodeVerdicts {
  episodeId: string;
  verdicts: Record<string, { verdict?: string; qualifier?: string } | undefined>;
}

/** Best-effort discovery of the sub-episodes a main-chain episode was split into
 * (Demo B: `ep-omfv-2020-02-r4` → `-dc`/`-fs`/`-ce`). Nothing in the timeline route
 * names them — `DecisionProgram.episodes` is the main chain only, by the same rule that
 * keeps `_latest_episode` from mistaking a sub-episode for the next one in sequence
 * (`demos/b_omfv_2019_2023/README.md` §1). They are, however, real `DecisionEpisode`s
 * that reference the parent via `supersedes`, so `object_view(parent).referencedBy`
 * finds them without inventing a route: this is a read-only, additive discovery over
 * routes the view already has, not a new server contract. Failure anywhere here
 * (a session with no such episodes, a transport error) yields an empty result — this is
 * progressive enhancement over the required rail, never a blocker for it. */
async function discoverSubEpisodeGrid(sessionId: string, parentId: string): Promise<SubEpisodeVerdicts[]> {
  const parent = await apiGet<{ referencedBy: string[] }>(`/session/${sessionId}/object/${parentId}`);
  const out: SubEpisodeVerdicts[] = [];
  for (const candidateId of parent.referencedBy) {
    let candidate: { type: string; object: { supersedes?: string } };
    try {
      candidate = await apiGet<{ type: string; object: { supersedes?: string } }>(
        `/session/${sessionId}/object/${candidateId}`,
      );
    } catch {
      continue;
    }
    if (candidate.type !== 'DecisionEpisode' || candidate.object.supersedes !== parentId) continue;
    try {
      const readiness = await apiGet<{ standardsAssessment: { dimensionVerdicts?: Record<string, { verdict?: string; qualifier?: string }> } | null }>(
        `/session/${sessionId}/episode/${candidateId}/readiness`,
      );
      out.push({ episodeId: candidateId, verdicts: readiness.standardsAssessment?.dimensionVerdicts ?? {} });
    } catch {
      // No readiness report for this sub-episode yet — it is still a real
      // sub-episode, it just has nothing to put in the grid.
      out.push({ episodeId: candidateId, verdicts: {} });
    }
  }
  return out.sort((a, b) => a.episodeId.localeCompare(b.episodeId));
}

function TriggerMarker({ trigger, onClick, selected }: { trigger: RefreshTrigger; onClick?: () => void; selected?: boolean }) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={!onClick}
      className={`flex min-h-11 min-w-11 flex-col items-center justify-center gap-1 og-mono text-m2 ${selected ? 'text-fg' : 'text-fg-muted'}`}
      title={trigger.description}
    >
      {/* Smaller than the spec default: an inline rail glyph. */}
      <CalendarClock {...ICON_PROPS} size={18} aria-hidden />
      {/* A detection date is a coordinate, so it stays mono. */}
      <span className="og-mono tracking-normal">{trigger.detectedAt}</span>
    </button>
  );
}

function DiffPanel({ diff, showIds }: { diff: EpisodeDiff; showIds: boolean }) {
  return (
    <div className="border border-hairline p-4 flex flex-col gap-3" data-state="diff" data-testid="diff-panel">
      <p className="og-mono text-m1 break-words">
        {diff.from} → {diff.to}
      </p>
      {/* `because` is a trigger's own free-text description (a GAO report's own
          statutory citation, "Section 234", or similar) — quoted source content, not
          a value; the same exemption every other extracted-prose field in this app
          already gets. */}
      <p className="text-b2" data-num="label">{diff.because}</p>
      {diff.pairing === 'unknown' && (
        <p className="text-b2 text-fg-secondary">field-level pairing unavailable for this diff</p>
      )}
      <ul className="flex flex-col">
        {/* `showId` is the one thing Fields changes about a diff row, and only on a
            CHANGED row: there the field path and its before/after carry the meaning
            without the object's id. An added, removed or consistent row is nothing but
            an id, so hiding it would leave the word "added" and no subject. */}
        {diff.changed.map((c, i) => (
          <DiffRow key={`c${i}`} kind="changed" id={c.object} field={c.field} before={c.before} after={c.after} showId={showIds} />
        ))}
        {diff.added.map((id) => (
          <DiffRow key={`a${id}`} kind="added" id={id} />
        ))}
        {diff.removed.map((id) => (
          <DiffRow key={`r${id}`} kind="removed" id={id} />
        ))}
        {diff.judgmentsConsistent.map((id) => (
          <DiffRow key={`j${id}`} kind="consistent" id={id} />
        ))}
      </ul>
      {diff.judgmentsChanged.length > 0 && (
        <div className="flex flex-col gap-1">
          <p className="og-label text-b3 text-fg-muted">judgments changed</p>
          {/* `kernel.refresh`'s `judgments_changed` entries are `{claim, before,
              after}`, where `before`/`after` are a Claim's own free-text `text` (or
              `null`) — quoted record content, not a value; `data-num="label"` on the
              whole dump, the same reasoning every other extracted-prose field here
              gets. */}
          <ul className="og-mono text-m2 text-fg-muted flex min-w-0 flex-col gap-0.5 break-all" data-num="label">
            {diff.judgmentsChanged.map((entry, i) => (
              <li key={i}>{JSON.stringify(entry)}</li>
            ))}
          </ul>
        </div>
      )}
      {diff.ratingsChanged.length > 0 && (
        <div className="flex flex-col gap-1">
          <p className="og-label text-b3 text-fg-muted">ratings changed</p>
          {/* Unlike `judgmentsChanged` above, `kernel.refresh`'s `ratings_changed`
              entries (`{questionId, before, after}`) carry a genuine kernel-computed
              integer rating on the GAO scale — a real value, not free text, so it goes
              through `<Num>` like any other kernel numeral, not a raw `JSON.stringify`
              dump. */}
          <ul className="og-mono text-m2 text-fg-muted flex min-w-0 flex-col gap-0.5 break-words">
            {diff.ratingsChanged.map((entry, i) => {
              const questionId = typeof entry.questionId === 'string' && entry.questionId
                ? entry.questionId
                : '_[unknown question]_';
              const before = entry.before;
              const after = entry.after;
              return (
                <li key={i}>
                  {questionId}:{' '}
                  {typeof before === 'number' ? (
                    <Num value={before} from={`ratingsChanged[${i}].before`} />
                  ) : (
                    <span>_[unavailable]_</span>
                  )}
                  {' → '}
                  {typeof after === 'number' ? (
                    <Num value={after} from={`ratingsChanged[${i}].after`} />
                  ) : (
                    <span>_[unavailable]_</span>
                  )}
                </li>
              );
            })}
          </ul>
        </div>
      )}
      {(diff.rankingBefore.length > 0 || (diff.rankingAfter?.length ?? 0) > 0) && (
        <div className="flex flex-col gap-1 text-b2">
          <p className="og-label text-b3 text-fg-muted">ranking before</p>
          <p className="og-mono break-words">{diff.rankingBefore.join(' > ') || '_[none]_'}</p>
          <p className="og-label text-b3 text-fg-muted">ranking after</p>
          <p className="og-mono break-words">{diff.rankingAfter?.join(' > ') || '_[none]_'}</p>
        </div>
      )}
    </div>
  );
}

function GaoGrid({ rows }: { rows: SubEpisodeVerdicts[] }) {
  if (rows.length === 0) return null;
  return (
    <div className="border border-hairline p-4 flex flex-col gap-3">
      {/* The grid's own name, which is a written label rather than an identifier.
          "3×3" is the published assessment's own shape — the same category as a
          document id, not a value this view computed — hence `data-num="label"`. */}
      <p className="og-label text-b2" data-num="label">3×3 verdict grid</p>
      {/* §5a: one stacked label-over-value card per sub-episode, not a four-column
          `<table>` of sentences. `auto-fit` keeps the three dimensions side by side
          wherever there is room for them. */}
      <ul className="flex flex-col gap-3">
        {rows.map((row) => (
          <li
            key={row.episodeId}
            className="flex min-w-0 flex-col gap-2 border-b border-hairline pb-3 last:border-b-0 last:pb-0"
          >
            <p className="og-mono text-m1 break-all">{row.episodeId}</p>
            <dl
              className="grid gap-x-6 gap-y-2 text-b2"
              style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(min(14rem, 100%), 1fr))' }}
            >
              {DIMENSIONS.map((d) => (
                <div key={d} className="flex min-w-0 flex-col gap-0.5">
                  <dt className="og-label text-b3 text-fg-muted">{d}</dt>
                  <dd className="min-w-0 break-words">
                    {/* A verdict is a closed kernel token (`generally_objective`, …), so
                        mono; the qualifier beside it is a sentence, so it is not. */}
                    <span className="og-mono text-m2">{row.verdicts[d]?.verdict ?? '_[unavailable]_'}</span>
                    {row.verdicts[d]?.qualifier ? <span> — {row.verdicts[d]?.qualifier}</span> : null}
                  </dd>
                </div>
              ))}
            </dl>
          </li>
        ))}
      </ul>
      {/* The standing anti-overclaim caption, verbatim and in ordinary body type — it
          is the sentence that keeps this grid from reading as GAO's own per-question
          assessment, so it is never a tooltip, never shortened and never demoted to a
          muted footnote. `data-num="label"`: the sentence states the published grid's
          shape ("a 3×3 verdict grid") and the report's own id, neither of which is a
          value this view computed. */}
      <p className="text-b2 text-fg-secondary" data-num="label">{GAO_23_106549_CAPTION}</p>
    </div>
  );
}

/** The "open refresh" action — human-only, calls `POST .../refresh`. No route here
 * accepts an actor from the client; the human stamp is the server's own
 * `config.human_actor()` (`routes/program.py`), which is the whole reason detecting a
 * trigger and opening a refresh are two different verbs.
 *
 * `ember` is passed by the caller, never decided here: only one control on a view may
 * be lit, and only the caller knows whether this is the one. The button paints no fill
 * of its own — the frame paints whatever carries `data-ember` (`frame/frame.css`). */
function OpenRefreshButton({
  sessionId,
  programId,
  triggerId,
  ember,
  onOpened,
}: {
  sessionId: string;
  programId: string;
  triggerId: string;
  ember?: boolean;
  onOpened: (newEpisode: DecisionEpisode) => void;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function open() {
    setBusy(true);
    setError(null);
    try {
      const ep = await apiPost<EpisodeView>(`/session/${sessionId}/program/${programId}/refresh`, {
        triggerId,
      });
      onOpened(ep);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <span className="inline-flex items-center gap-2">
      <button type="button" onClick={open} disabled={busy} data-ember={ember ? '' : undefined} className={btn}>
        Open refresh
      </button>
      {error && <span className="og-mono text-m2 text-accent-text">{error}</span>}
    </span>
  );
}

function WatchTray({
  sessionId,
  programId,
  onFiled,
  onOpened,
}: {
  sessionId: string;
  programId: string;
  /** Filing writes `RefreshTrigger`s to the record, so the whole workspace has to
   * re-read: this view's own pending list (which is what lights the one Ember and
   * offers to open a refresh), the header counters and the map. Without it a
   * programme that had nothing pending ends the act with a trigger pending, nothing
   * lit, and no way to act on what was just filed short of a reload. */
  onFiled: () => void;
  onOpened: (newEpisode: DecisionEpisode) => void;
}) {
  const [response, setResponse] = useState<WatchResponse | null>(null);
  const [filedIds, setFiledIds] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  async function detect() {
    setLoading(true);
    setError(null);
    try {
      const res = await apiPost<WatchResponse>(`/session/${sessionId}/program/${programId}/watch`, {});
      setResponse(res);
    } catch (err) {
      setError(err instanceof Error ? err : new Error(String(err)));
    } finally {
      setLoading(false);
    }
  }

  async function fileAll() {
    setLoading(true);
    setError(null);
    try {
      const res = await apiPost<WatchResponse>(`/session/${sessionId}/program/${programId}/watch?file=true`, {});
      setResponse(res);
      setFiledIds(Array.isArray(res.filed) ? res.filed : []);
      onFiled();
    } catch (err) {
      setError(err instanceof Error ? err : new Error(String(err)));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="border border-dashed border-hairline p-4 flex flex-col gap-3">
      <p className="og-label text-b2">What may have moved since</p>
      <button type="button" onClick={detect} disabled={loading} className={`${btn} self-start`}>
        Ask the AI what changed
      </button>
      {error && <ErrorState message={error.message} route={`session/${sessionId}/program/${programId}/watch`} onRetry={detect} />}
      {response && (
        <div className="flex flex-col gap-2">
          <p className="text-b2">Detected, not recorded. Recording a trigger is a write; opening a refresh is a human act.</p>
          <ul className="flex flex-col gap-2">
            {(response.proposals ?? []).map((p, i) => (
              // Drafted by the AI and not yet part of the record: the dashed blue card
              // every unagreed draft in this app wears (§10's `ai` plane), never a
              // solid one — a filled card would read as something the record holds.
              <li key={i} className="border border-dashed border-ai-line bg-ai-tint p-2 text-b2 flex flex-col gap-1" data-state="proposed" data-watch-proposal>
                <Sev kind="ai">drafted by the AI</Sev>
                <span className="og-mono text-m2 text-fg-muted">{p.kind}</span>
                {/* A proposal's description is the finding's own message, quoted. */}
                <span data-num="label">{p.description}</span>
                <span className="og-mono text-m2 text-fg-muted break-all">
                  {p.source} · {p.detectedAt}
                </span>
              </li>
            ))}
            {(response.proposals ?? []).length === 0 && <p className="text-b2 text-fg-muted">no new triggers detected</p>}
          </ul>
          {(response.proposals ?? []).length > 0 && (
            <button type="button" onClick={fileAll} disabled={loading} className={`${btn} self-start`}>
              File this trigger
            </button>
          )}
          {filedIds.length > 0 && (
            <div className="flex flex-col gap-2">
              {/* "filed" is a written label; the ids after it are ids. */}
              <p className="og-label text-b3 text-fg-muted">
                filed: <span className="og-mono text-m2 break-all">{filedIds.join(', ')}</span>
              </p>
              {/* Never lit: the leading unopened trigger above already carries this
                  view's one Ember, and a trigger just filed here is one of them. */}
              {filedIds.map((triggerId) => (
                <OpenRefreshButton
                  key={triggerId}
                  sessionId={sessionId}
                  programId={programId}
                  triggerId={triggerId}
                  onOpened={onOpened}
                />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export function Timeline() {
  const { sessionId, episode, settled: episodeSettled, setEpisodeId, refetch: refetchSession } = useSession();
  const { recordVersion, bumpRecord } = useWorkspace();
  const fields = useFields('timeline', TIMELINE_FIELDS);
  const [selectedDiffKey, setSelectedDiffKey] = useState<string | null>(null);
  const [grid, setGrid] = useState<SubEpisodeVerdicts[]>([]);
  // `settled`, not `loading`: the sentence below ("not part of a programme") is a claim
  // about a decision, and this view may only make it about a decision that has actually
  // been read. `loading` is false both before the episode read starts — it begins in an
  // effect, a frame after the first render — and after it ends, so on a hard load or a
  // deep link to /timeline it would let the claim through about a decision nothing had
  // read yet. `useSession().settled` distinguishes the two (see its own doc).

  const programId = episode?.program ?? null;
  const path = sessionId && programId ? `/session/${sessionId}/program/${programId}/timeline` : null;
  const fetched = useFetched<TimelineResponse>(path, [recordVersion]);
  const timeline = fetched.data;

  // Progressive enhancement, best-effort: the 3×3 grid beside the 2023-03 sub-episodes.
  // Runs once the main chain is known; failures leave `grid` empty rather than surfacing
  // a second error state for a bonus panel.
  useEffect(() => {
    if (!sessionId || !timeline?.episodes?.length) {
      setGrid([]);
      return;
    }
    let cancelled = false;
    (async () => {
      const found: SubEpisodeVerdicts[] = [];
      for (const ep of timeline.episodes) {
        try {
          const rows = await discoverSubEpisodeGrid(sessionId, ep.id);
          found.push(...rows);
        } catch {
          // best-effort — see function doc
        }
      }
      if (!cancelled) setGrid(found);
    })();
    return () => {
      cancelled = true;
    };
  }, [sessionId, timeline]);

  const triggerByEpisode = useMemo(() => {
    const map = new Map<string, RefreshTrigger>();
    for (const t of timeline?.refreshTriggers ?? []) map.set(t.id, t);
    return map;
  }, [timeline]);

  const openedTriggerIds = useMemo(
    () => new Set((timeline?.episodes ?? []).map((ep) => ep.refreshedBecause).filter((id): id is string => !!id)),
    [timeline],
  );
  // Filed and opened nothing, longest-waiting first. The order is the server's own
  // `detectedAt` stamps compared as strings — ISO timestamps sort lexically, so this is
  // a sort, not date arithmetic — and a trigger with no readable stamp sorts last
  // rather than jumping the queue. The one that has waited longest is the one this view
  // lights: with several pending, "the first in `refreshTriggers`" would light whichever
  // the store happened to list first, which is not a fact about waiting.
  const unopenedTriggers = (timeline?.refreshTriggers ?? [])
    .filter((t) => !openedTriggerIds.has(t.id))
    .slice()
    .sort((a, b) => String(a.detectedAt ?? '￿').localeCompare(String(b.detectedAt ?? '￿')));

  /** `POST .../refresh` (a human act) creates a new episode in this programme's chain;
   * nothing here recomputes anything, it just tells the session-wide episode list and
   * this view's own read to catch up, and moves the current episode onto the one the
   * refresh just opened, as a person would navigate to it next. */
  function handleRefreshOpened(newEpisode: DecisionEpisode) {
    refetchSession();
    setEpisodeId(newEpisode.id);
    bumpRecord();
  }

  const head = (
    <ViewHead
      eyebrow={`programme · ${programId ?? '—'}`}
      title="The programme"
      sentence="Every episode of this decision over the years, what changed between them, and how long it has been since the last one."
      right={<FieldsControl list="timeline" spec={TIMELINE_FIELDS} shownOverride={fields} />}
    />
  );

  if (!sessionId) {
    return <ViewHead eyebrow="programme" title="The programme" sentence="Choose a decision in the header first." />;
  }

  // Until the decision itself has been read, this view knows nothing about it — not
  // even whether it belongs to a programme — and says nothing about it.
  if (!episodeSettled) {
    return (
      <div>
        {head}
        <Loading label="loading the decision" />
      </div>
    );
  }

  if (!programId) {
    return (
      <div>
        {head}
        <p className="text-b2">This decision is not part of a programme; there is no timeline to show.</p>
      </div>
    );
  }

  // Every number below, from the server (`kernel.clock.programme_timing`).
  const timing: TimelineTiming | null = timeline?.timing ?? null;
  const daysOf = (id: string) => timing?.episodes?.find((e) => e.id === id) ?? null;
  const monthsAfter = (i: number) => timing?.between?.[i - 1] ?? null;

  const episodes = timeline?.episodes ?? [];
  const diffs = timeline?.diffs ?? [];
  const diffKey = (from: string, to: string) => `${from}->${to}`;
  const diffBefore = (i: number) => (i > 0 ? diffs.find((d) => d.from === episodes[i - 1].id && d.to === episodes[i].id) : undefined);
  const selectedDiff = diffs.find((d) => diffKey(d.from, d.to) === selectedDiffKey) ?? null;

  return (
    <div>
      {head}

      {/* On ANY read in flight, not only the first: switching the decision in the header
          must never leave another programme's episodes on screen under this heading. */}
      {fetched.loading && <Loading label="loading the programme" />}
      {fetched.error && (
        <ErrorState
          message={fetched.error.message}
          route={`session/${sessionId}/program/${programId}/timeline`}
          onRetry={fetched.refresh}
        />
      )}

      {!fetched.loading && !fetched.error && timeline && episodes.length === 0 && (
        <EmptyState eyebrow="The programme" message="This programme has no episodes yet." />
      )}

      {!fetched.loading && !fetched.error && timeline && episodes.length > 0 && (
        <div className="flex flex-col gap-4">
          {/* A programme's `name` is free text, not an id or a numeral, so under v3.0's
              "mono is numerals, coordinates and code only" rule it is body type. It can
              also legitimately state a year range ("OMFV requirements decision,
              2019-2023") — source-descriptive, not a value; `data-num="label"`. */}
          <p className="text-b2 text-fg-secondary" data-num="label">{timeline.program?.name}</p>

          {/* §5a: the episodes stack below 768 px. Above it the rail reads left to right
              and scrolls INSIDE ITS OWN BOX if the programme is long — never the page.
              Below it a horizontal rail would be four fifths off-screen, so the same
              list runs down the page instead; the diff panel is below the rail at every
              width, never beside it. */}
          <div className="border border-hairline p-4 md:overflow-x-auto" data-testid="timeline-rail">
            <ol className="flex flex-col items-stretch gap-4 md:flex-row md:items-center md:gap-6">
              {episodes.map((ep: EpisodeView, i: number) => {
                const timed = daysOf(ep.id);
                const gap = monthsAfter(i);
                return (
                  <li key={ep.id} className="flex flex-col items-stretch gap-4 md:flex-row md:items-center md:gap-6">
                    {/* The connector between the previous node and this one: the whole
                        calendar months the server counted, never a number this browser
                        derived from two dates. */}
                    {i > 0 && gap && typeof gap.months === 'number' && (
                      <span className="og-mono text-m2 text-fg-muted" data-connector-months>
                        <Num value={gap.months} from={programId} /> months later
                      </span>
                    )}
                    {fields.shown.triggers && i > 0 && ep.refreshedBecause && triggerByEpisode.has(ep.refreshedBecause) && (
                      <TriggerMarker
                        trigger={triggerByEpisode.get(ep.refreshedBecause)!}
                        selected={selectedDiffKey === diffKey(episodes[i - 1].id, ep.id)}
                        onClick={diffBefore(i) ? () => setSelectedDiffKey(diffKey(episodes[i - 1].id, ep.id)) : undefined}
                      />
                    )}
                    <button
                      type="button"
                      data-testid="timeline-episode"
                      onClick={diffBefore(i) ? () => setSelectedDiffKey(diffKey(episodes[i - 1].id, ep.id)) : undefined}
                      className="flex min-h-11 w-full flex-col items-center justify-center gap-1 border border-hairline-strong px-3 py-2 md:w-auto"
                    >
                      <span className="og-mono text-m1">{ep.id}</span>
                      <span className="og-mono text-m2 text-fg-muted">{ep.lifecycleState}</span>
                      <span className="og-mono text-m2 text-fg-muted">{ep.asOf}</span>
                      {/* How long this episode was the live answer: served, in days,
                          and beside it the state it ended in, in plain words. */}
                      {fields.shown.days && timed && typeof timed.days === 'number' && (
                        <span className="block text-m2 text-fg-secondary" data-episode-days={ep.id}>
                          lived <Num value={timed.days} from={ep.id} /> days · {plainState(String(timed.endState ?? ep.lifecycleState))}
                        </span>
                      )}
                    </button>
                  </li>
                );
              })}
            </ol>
          </div>

          {/* After the last node: how long the record has stood, against the
              re-accreditation clock the same server keeps (AR 5-11 ¶4-2i(3)). Blocking
              when the server says it is overdue — the glyph carries the severity, the
              sentence stays ink. */}
          {timing?.sinceLast && typeof timing.sinceLast.months === 'number' && (
            <p className="text-b3" data-since-last>
              {timing.overdue ? (
                <Sev kind="blocking">
                  <Num value={timing.sinceLast.months} from={programId} /> months since · re-accreditation expected every{' '}
                  <Num value={timing.accreditationMonths} from={programId} />
                </Sev>
              ) : (
                <span className="text-fg-secondary">
                  <Num value={timing.sinceLast.months} from={programId} /> months since · re-accreditation expected every{' '}
                  <Num value={timing.accreditationMonths} from={programId} />
                </span>
              )}
            </p>
          )}

          {fields.shown.triggers && unopenedTriggers.length > 0 && (
            <div className="border border-hairline p-3 flex flex-col gap-2">
              <p className="og-label text-b3 text-fg-muted">filed, opened nothing</p>
              {unopenedTriggers.map((t, i) => (
                <div key={t.id} className="flex flex-wrap items-center gap-3 text-b2" data-pending-trigger={t.id}>
                  <span>
                    <span className="og-mono">{t.id}</span>{' '}
                    {/* A trigger's own free-text description (a GAO report's statutory
                        citation, "Section 234", etc.) — quoted source content. */}
                    <span data-num="label">— {t.description}</span>
                  </span>
                  {/* Why this one is lit and the others are not, said in words rather
                      than left to the reader to infer from a colour. */}
                  {i === 0 && unopenedTriggers.length > 1 && (
                    <span className="text-b3 text-fg-secondary" data-ember-reason>detected first, so it has waited longest</span>
                  )}
                  <OpenRefreshButton
                    sessionId={sessionId}
                    programId={programId}
                    triggerId={t.id}
                    ember={i === 0}
                    onOpened={handleRefreshOpened}
                  />
                </div>
              ))}
            </div>
          )}

          {selectedDiff ? (
            <DiffPanel diff={selectedDiff} showIds={!!fields.shown['diff-ids']} />
          ) : (
            <p className="text-b2 text-fg-muted">click an episode to see what changed</p>
          )}

          {fields.shown['verdict-grid'] && <GaoGrid rows={grid} />}

          <WatchTray sessionId={sessionId} programId={programId} onFiled={bumpRecord} onOpened={handleRefreshOpened} />
        </div>
      )}
    </div>
  );
}
