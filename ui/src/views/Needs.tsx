// What needs you (spec §8) — the first view a visitor sees, and the only one that is
// still useful with nothing open.
//
// The queue is not a to-do list this UI keeps. Every card is an outstanding human act
// `kernel.queue.needs` derived from the record just now, and it disappears the moment
// the record no longer needs it. The big number is the server's `count`, printed, never
// the length of an array this file filtered.
import { useEffect, useState } from 'react';
import { apiGet, apiPost, ApiError } from '../api/client';
import { useClock } from '../api/useClock';
import { useHealth } from '../api/useHealth';
import { useNeeds } from '../api/useNeeds';
import { useSession, type DemoSource } from '../api/useSession';
import { useWorkspace } from '../api/useWorkspace';
import { ClockCard } from '../components/ClockCard';
import { ErrorState } from '../components/ErrorState';
import { FieldsControl } from '../components/FieldsControl';
import { Loading } from '../components/Loading';
import { Num } from '../components/Num';
import { QueueCard } from '../components/QueueCard';
import { ViewHead } from '../components/ViewHead';
import { DEMO_TITLE } from '../frame/DecisionSwitcher';
import { useFields, type FieldSpec } from '../lib/fields';
import { plainState } from '../lib/format';
import type { EpisodeView, SessionInfo } from '../types/api';
import { useNavigate } from 'react-router-dom';

export const QUEUE_FIELDS: FieldSpec[] = [
  { key: 'who', label: 'who it waits on', default: true },
  { key: 'count', label: 'how many are waiting', default: true },
  { key: 'where', label: 'which part of the record', default: false },
  { key: 'stage', label: 'stage', default: false },
];

const START: { source: DemoSource; kind: string; blurb: string; notBuilt?: string }[] = [
  { source: 'demo-a', kind: 'trade study', blurb: 'The 2013 Congressional Budget Office trade study of the Ground Combat Vehicle against four alternatives, rebuilt as a record and taken through the whole lifecycle to a signer-ready package.', notBuilt: "Demo A's store has not been built. Run `uv run python -m demos.a_cbo_gcv_2013.run`." },
  { source: 'demo-b', kind: 'decision programme', blurb: 'The Optionally Manned Fighting Vehicle requirements programme over four years: five episodes, four superseded, graded against GAO-23-106549.', notBuilt: "Demo B's store has not been built. Run `uv run python -m demos.b_omfv_2019_2023.run`." },
  { source: 'new', kind: 'empty', blurb: 'An empty session holding the demonstration policy and nothing else. File a request and the AI drafts a model from the source you name.' },
];

function StartCards() {
  const { sessionId, adoptSession } = useSession();
  const { data: health } = useHealth();
  const { bumpRecord } = useWorkspace();
  const [busy, setBusy] = useState<string | null>(null);
  const [err, setErr] = useState<{ source: string; message: string } | null>(null);
  async function open(source: DemoSource) {
    setBusy(source); setErr(null);
    try {
      // `POST /api/session` directly rather than through `openSession`, which keeps its
      // failure in the hook's shared error field: a 409 has to be printed verbatim on
      // the card that asked for it, and a shared field cannot say which card that was.
      const info = await apiPost<SessionInfo>('/session', { source });
      adoptSession(info.id); bumpRecord();
    } catch (e) {
      setErr({ source, message: e instanceof ApiError ? (e.body.message ?? e.message) : String(e) });
    } finally { setBusy(null); }
  }
  return (
    <div className="grid gap-3" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(min(300px, 100%), 1fr))' }}>
      {START.map((c) => {
        const built = c.source === 'new' || health?.demoStores?.[c.source] !== false;
        return (
          <section key={c.source} className="border border-hairline bg-raised p-4" data-start={c.source}>
            <h3 className="og-label text-b1" data-num="label">{DEMO_TITLE[c.source]}</h3>
            <p className="my-1.5"><span className="og-label inline-flex min-h-8 items-center border border-hairline px-2 text-b3">{c.kind}</span></p>
            <p className="text-b3 text-fg-secondary" data-num="label">{c.blurb}</p>
            {!built && c.notBuilt && <p className="mt-2 text-b3" data-num="label">{c.notBuilt}</p>}
            <p className="mt-3"><button type="button" disabled={busy !== null} onClick={() => open(c.source)} className="og-label inline-flex min-h-11 items-center border border-hairline-strong px-3 text-b3">
              {busy === c.source ? 'opening…' : !built ? 'Build now' : sessionId ? (c.source === 'new' ? 'Start another' : 'Open a fresh copy') : (c.source === 'new' ? 'Start it' : 'Open it')}</button></p>
            {err?.source === c.source && <ErrorState message={err.message} route="api/session" />}
          </section>
        );
      })}
    </div>
  );
}

/** The two things the app can say about its own configuration without naming a model:
 * that no backend answered, and that the configured one was refused. The reasons for
 * both stay in Settings, which is where a reader is entitled to the provider strings. */
function BackendNotices() {
  const { data, apiAbsent } = useHealth();
  if (apiAbsent || !data) return null;
  return (
    <>
      {!data.backend.reachable && <p className="border border-hairline bg-surface p-3 text-b3">No backend answered the health probe. Open Settings for the reason it gave.</p>}
      {data.configRefused && <p className="border border-hairline bg-surface p-3 text-b3">The configured model was refused by policy. Open Settings for the reason.</p>}
    </>
  );
}

function EpisodesTable({ episodes, sessionId }: { episodes: EpisodeView[]; sessionId: string }) {
  const [hashes, setHashes] = useState<Record<string, string>>({});
  useEffect(() => {
    let cancelled = false;
    Promise.all(episodes.map(async (ep) => {
      const last = ep.runs[ep.runs.length - 1];
      if (!last) return [ep.id, ''] as const;
      const view = await apiGet<{ object: { runRecordHash?: string } }>(`/session/${sessionId}/object/${last}`).catch(() => null);
      return [ep.id, view?.object.runRecordHash ?? ''] as const;
    })).then((pairs) => { if (!cancelled) setHashes(Object.fromEntries(pairs)); });
    return () => { cancelled = true; };
  }, [episodes, sessionId]);
  // A comparison, never a subtraction: `sequence` is the kernel's own integer and this
  // table only needs to know which episode came first.
  const ordered = [...episodes].sort((a, b) => (a.sequence === b.sequence ? 0 : a.sequence < b.sequence ? -1 : 1));
  return (
    <div className="overflow-x-auto"><table className="w-full text-b3"><thead><tr className="og-label text-m1 text-fg-muted"><th className="py-2 text-left">episode</th><th className="text-left">as of</th><th className="text-left">state</th><th className="text-left">last calculation hash</th></tr></thead>
      <tbody>{ordered.map((ep) => (
        <tr key={ep.id} className="border-t border-hairline" data-episode-row={ep.id}>
          <td className="og-mono py-2 text-m2" data-num="label">{ep.id}</td>
          <td className="og-mono text-m2" data-num="label">{ep.asOf}</td>
          <td>{plainState(ep.lifecycleState)}</td>
          <td className="og-mono break-all text-m2" data-num="label">{hashes[ep.id] || '—'}</td>
        </tr>))}</tbody></table></div>
  );
}

export function Needs() {
  const { sessionId, episodeId, episodes, episode } = useSession();
  const navigate = useNavigate();
  const needs = useNeeds(sessionId, episodeId);
  const clock = useClock(sessionId, episodeId);
  const fields = useFields('queue', QUEUE_FIELDS);
  const items = needs.data?.items ?? [];
  // A returned package is answered before it is signed, and the RECORD says so: `commit.sign`
  // refuses while a send-back stands, so `kernel.queue` lists the return first and marks the
  // signature `actionable: false` with what unlocks it. This view no longer pairs the two
  // itself — it splits the server's list on the server's own flag, like any other row.
  const actionable = items.filter((i) => i.actionable);
  const later = items.filter((i) => !i.actionable);
  const from = episodeId ?? 'needs';

  if (!sessionId) {
    return (
      <div>
        <ViewHead eyebrow="what needs you" title="What needs you" sentence="Nothing is open yet. Choose a decision above, or start one here; opening a demonstration copies its committed store into a private session and the record in the repository is never written to." />
        <BackendNotices />
        <h2 className="og-display mt-6 mb-3 text-e2">Start something new</h2>
        <StartCards />
      </div>
    );
  }
  return (
    <div>
      <ViewHead eyebrow="what needs you" title="What needs you"
        sentence="Everything below is read out of the record, not out of a to-do list, and it disappears when the record no longer needs it."
        right={<FieldsControl list="queue" spec={QUEUE_FIELDS} shownOverride={fields} />} />
      {needs.loading && !needs.data && <Loading />}
      {needs.error && <ErrorState message={needs.error.message} route={`session/${sessionId}/episode/${episodeId}/needs`} onRetry={needs.refresh} />}
      {needs.data && (
        <>
          <div className="mb-5 grid items-start gap-4" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(min(360px, 100%), 1fr))' }}>
            <div className="flex flex-wrap items-baseline gap-4">
              <span className="og-mono text-[clamp(40px,7vw,68px)] leading-none" data-num data-from={from}><span aria-hidden className="text-fg-muted">[ </span><span data-bignum>{needs.data.count}</span><span aria-hidden className="text-fg-muted"> ]</span></span>
              {/* "In any order" is true of everything counted here: an act the record holds
                  behind another one is not in this list at all — it is greyed below, under
                  its own heading, saying what unlocks it. */}
              <span className="text-b1 text-fg-secondary">{needs.data.count === 1 ? 'thing is' : 'things are'} waiting on a person.<br />You can do them in any order. Each checklist says what is still missing.</span>
            </div>
            {clock.data && <ClockCard clock={clock.data} />}
          </div>
          {actionable.length === 0 ? (
            <div className="border border-hairline bg-raised p-4"><p className="text-b1">Nothing is waiting on a person in this decision.</p>
              {episode?.lifecycleState === 'SIGNED' && <p className="mt-2"><button type="button" onClick={() => navigate('/package')} data-ember="" className="og-label inline-flex min-h-11 items-center border border-hairline-strong px-4 text-b3">Open the signed package</button></p>}</div>
          ) : (
            <div className="flex flex-col gap-3">{actionable.map((item, i) => <QueueCard key={item.id} item={item} ember={i === 0} fields={fields.shown} clock={clock.data} />)}</div>
          )}
          {later.length > 0 && (<><h2 className="og-display mt-8 mb-3 text-e2">Waiting for an earlier step</h2>
            <div className="flex flex-col gap-3">{later.map((item) => <QueueCard key={item.id} item={item} ember={false} fields={fields.shown} clock={clock.data} />)}</div></>)}
        </>
      )}
      <h2 className="og-display mt-8 mb-3 text-e2">Start something new</h2>
      <StartCards />
      <h2 className="og-display mt-8 mb-3 text-e2">If something is missing</h2>
      <div className="flex flex-col gap-2"><BackendNotices /></div>
      {episodes.length > 0 && (<><h2 className="og-display mt-8 mb-3 text-e2">Episodes in this decision</h2><EpisodesTable episodes={episodes} sessionId={sessionId} /></>)}
      <p className="mt-6 text-m1 text-fg-muted">Numbers on this page: <Num value={needs.data?.count ?? 0} from={from} /> is the count of items above.</p>
    </div>
  );
}
