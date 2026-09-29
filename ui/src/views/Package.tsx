// The package (spec §16) — the whole record rendered by the kernel into one document,
// hashed; read it in full, then sign it, dissent, or send it back.
//
// This view assembles nothing. `POST .../package` asks the kernel to render and seal a
// `DecisionPackage`, and what is shown is exactly the text and the hashes the server
// produced; "Download the text" saves that text as it arrived; "Verify the bytes" asks the
// server to render again and compare. The document's own numerals are the kernel's, and the
// adjacent verify result proves the text is byte-identical to a fresh render — so the
// `<pre>` is a document viewer (`data-num="label"`), not chrome asserting a number.
//
// **What you sign is this text.** The signature binds to the hash of the full rendering,
// and the hash this view hands the sign sheet is the one of the full package rendered HERE,
// in this session (`latestFullHash`) — never a hash the record happens to hold that nobody
// on this screen has read. A person who has not rendered the full package is told to,
// rather than offered a signature over a document they have not seen. The kernel's own gate
// (`commitment-package-hash`) then checks that the hash the commitment carries is the
// latest full package's, so the two rules meet on the same value.
//
// **Where the decision's state comes from.** `PENDING_SIGNATURE` and `SIGNED` are the
// episode's own `lifecycleState`; whether the readiness report says ready is
// `GET .../readiness` (a 404 is "not scored", which is not ready); the charter names the
// signer's role; the commitment, once made, is read as an object. A pending send-back is
// the queue's own `sent-back` item (`kernel.queue.needs`, which lists a signer-return newer
// than the latest full package and not yet opened as a refresh) — the record still sits at
// `PENDING_SIGNATURE` after a send-back, so the queue, not the state, is what says the
// signature is not the next act. The trigger it names is read for its date and its reason,
// printed verbatim. The kernel holds the same rule (`commit.sign` refuses while a send-back
// stands, on the same predicate), so hiding `Sign` here states a fact rather than making one.
//
// **The one Ember** is `Sign`, and only while every condition holds at once: the state is
// `PENDING_SIGNATURE`, the readiness report says ready, a full package has been rendered
// here, and no send-back is pending. Otherwise this view carries no fill at all.
//
// **A refusal is a fact of the record.** A signature the gate refused is a `SIGNED`
// transition written with `refused: true` and the checks it failed; it is read back from
// the episode's transitions, the way Compute reads a refused dispatch, so it survives
// leaving the view.
import { useEffect, useState } from 'react';
import { Download } from 'lucide-react';
import { apiPost } from '../api/client';
import { useFetched } from '../api/useFetched';
import { useNeeds } from '../api/useNeeds';
import { useSession } from '../api/useSession';
import { useWorkspace } from '../api/useWorkspace';
import { EmptyState } from '../components/EmptyState';
import { ErrorState } from '../components/ErrorState';
import { Loading } from '../components/Loading';
import { SectionList } from '../components/SectionList';
import { Sev } from '../components/Sev';
import { VerifyButton } from '../components/VerifyButton';
import { ViewHead } from '../components/ViewHead';
import { ICON_PROPS } from '../lib/icons';
import type { ObjectView, PackageResponse, ReadinessView, SectionsResponse } from '../types/api';
import type { Charter, Commitment, RefreshTrigger } from '../types/objects';

type Rendering = 'full' | 'unclassified';

const btn = 'og-label inline-flex min-h-11 items-center border border-hairline-strong px-4 text-b3';

/** The six exports `docket.exports.EXPORTS` accepts, in the order the spec names them,
 * with the label each one is known by. The `format` values are the route's own — a
 * seventh name here would be a 400 from the server, not a silent nothing. */
const EXPORT_FORMATS: { format: string; label: string }[] = [
  { format: 'prov', label: 'PROV' },
  { format: 'gsn', label: 'GSN' },
  { format: 'dmn', label: 'DMN' },
  { format: 'milstd3022', label: 'MIL-STD-3022' },
  { format: 'madr', label: 'MADR' },
  { format: 'rtvm', label: 'RTVM (csv)' },
];

/** Split the rendered Markdown on `render.py`'s own `\n## {title}\n` heading lines and
 * pair each chunk positionally with `sections` (`GET /api/sections`, which already
 * matches document order 1:1). A pure string operation — locating a heading marker is
 * not "arithmetic on an API value" in the honesty rule's sense, it prints nothing this
 * view computed. Returns `null` on any mismatch so the caller falls back to the raw,
 * unsplit text rather than silently mis-attributing a chunk to the wrong section. */
function splitSections(text: string, sections: SectionsResponse['sections']): Record<string, string> | null {
  const marker = /\n(?=## )/;
  const chunks = text.split(marker);
  if (chunks.length !== sections.length) return null;
  const out: Record<string, string> = {};
  sections.forEach((s, i) => {
    out[s.key] = chunks[i];
  });
  return out;
}

function downloadText(filename: string, text: string): void {
  const blob = new Blob([text], { type: 'text/markdown' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

export function Package() {
  const { sessionId, episodeId, episode } = useSession();
  const { openOverlay, bumpRecord, recordVersion } = useWorkspace();
  const [rendering, setRendering] = useState<Rendering>('full');
  const [pkg, setPkg] = useState<PackageResponse | null>(null);
  // The hash of the last FULL rendering this session made — what a signature binds to.
  const [latestFullHash, setLatestFullHash] = useState<string | null>(null);
  const [activeKey, setActiveKey] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  // Every read is the shared one: it drops the last episode's answer rather than leaving
  // it under this one's heading, and re-reads whenever a write bumps the record.
  const sections = useFetched<SectionsResponse>('/sections');
  const base = sessionId && episodeId ? `/session/${sessionId}/episode/${episodeId}` : null;
  const readiness = useFetched<ReadinessView>(base ? `${base}/readiness` : null, [recordVersion]);
  const charterView = useFetched<ObjectView>(sessionId && episode?.charter ? `/session/${sessionId}/object/${episode.charter}` : null);
  const commitmentView = useFetched<ObjectView>(sessionId && episode?.commitment ? `/session/${sessionId}/object/${episode.commitment}` : null, [recordVersion]);
  const needs = useNeeds(sessionId, episodeId);
  // The newest pending send-back, if the queue lists one; its trigger for the date and the
  // reason, verbatim.
  const returned = [...(needs.data?.items ?? [])].reverse().find((i) => i.kind === 'sent-back') ?? null;
  const returnView = useFetched<ObjectView>(sessionId && returned?.objectId ? `/session/${sessionId}/object/${returned.objectId}` : null, [recordVersion]);

  // Changing the decision empties the board at once: nothing of the last one's package —
  // nor the hash a signature would bind to — may be left under this one's heading.
  useEffect(() => {
    setPkg(null);
    setLatestFullHash(null);
    setActiveKey(null);
    setError(null);
  }, [sessionId, episodeId]);

  async function render() {
    if (!base) return;
    setLoading(true);
    setError(null);
    try {
      const res = await apiPost<PackageResponse>(`${base}/package?rendering=${rendering}`);
      setPkg(res);
      if (res.rendering === 'full') setLatestFullHash(res.hash);
      setActiveKey(sections.data?.sections[0]?.key ?? null);
      // A render is a write: a sealed `DecisionPackage` joins the record, and the queue's
      // own reading of a pending send-back is "newer than the latest full package".
      bumpRecord();
    } catch (err) {
      setError(err instanceof Error ? err : new Error(String(err)));
    } finally {
      setLoading(false);
    }
  }

  if (!sessionId || !episodeId || !episode) {
    return <ViewHead eyebrow="package" title="The package" sentence="Choose a decision in the header first." />;
  }

  const sectionList = sections.data?.sections ?? [];
  const bodyByKey = pkg ? splitSections(pkg.text, sectionList) : null;
  const pending = episode.lifecycleState === 'PENDING_SIGNATURE';
  const signed = episode.lifecycleState === 'SIGNED';
  const ready = readiness.data?.ready === true;
  const fullHash = rendering === 'full' && pkg ? pkg.hash : latestFullHash;
  const charter = charterView.data?.object as unknown as Charter | undefined;
  const signerRole = charter?.authority?.signer ?? '';
  const commitment = commitmentView.data?.object as unknown as Commitment | undefined;
  const trigger = returnView.data?.object as unknown as RefreshTrigger | undefined;
  // The last attempt at SIGNED on record, if it was refused — a fact of the episode, not
  // a variable this view keeps.
  const lastSigned = [...(episode.transitions ?? [])].reverse().find((t) => t.to === 'SIGNED');
  const refusal = lastSigned?.refused ? lastSigned : null;

  const renderAct = (
    <button type="button" onClick={() => void render()} disabled={loading} className={btn}>
      {loading ? 'rendering…' : pkg ? 'Render it again' : 'Render the package'}
    </button>
  );

  return (
    <div>
      <ViewHead
        eyebrow={`package · ${episodeId}`}
        title="The package"
        sentence="The whole record rendered by the kernel into one document, hashed. What you sign is this text, and the signature carries the hash."
        right={(
          <>
            <div className="flex border border-hairline-strong" role="group" aria-label="rendering">
              {(['full', 'unclassified'] as Rendering[]).map((r) => (
                <button
                  key={r}
                  type="button"
                  onClick={() => setRendering(r)}
                  aria-pressed={rendering === r}
                  className={`og-label text-b3 inline-flex min-h-11 min-w-11 items-center justify-center px-3 ${rendering === r ? 'text-fg bg-canvas' : 'text-fg-muted'}`}
                >
                  {r}
                </button>
              ))}
            </div>
            {renderAct}
          </>
        )}
      />

      {error && <ErrorState message={error.message} route={`session/${sessionId}/episode/${episodeId}/package`} onRetry={() => void render()} />}
      {loading && !pkg && <Loading label="rendering the package" />}

      {!pkg && !loading && !error && (
        <EmptyState
          eyebrow="Package"
          message="No package has been rendered for this decision yet. Press Render the package to build one; the kernel renders and seals it."
        />
      )}

      {pkg && (
        <div className="flex flex-col gap-4 md:flex-row md:gap-6">
          {/* Below 768px the rail is a full-width block above the document; at 768px and
              up it is the column it always was. Nothing is hidden at either width. */}
          <aside className="min-w-0 border-b border-hairline pb-4 md:w-56 md:shrink-0 md:border-b-0 md:border-r md:pb-0 md:pr-4">
            <SectionList sections={sectionList} activeKey={activeKey} onSelect={setActiveKey} />
          </aside>

          <div className="flex min-w-0 flex-1 flex-col gap-4">
            <div className="flex flex-wrap items-center gap-x-4 gap-y-2 border border-hairline p-3 text-b2">
              <span className="og-mono text-m2 break-all text-fg-muted">{pkg.id}</span>
              <span className="og-mono text-m2 text-fg-muted">
                {pkg.rendering} · {pkg.renderedAt}
              </span>
              {/* The determinism claim. A hash that wraps mid-string, or is cut off, is a
                  hash a reader cannot check against the one the package prints — so these
                  hold one mono line and scroll inside their own box on a narrow screen. The
                  word in front of each is a label, so it is not mono. */}
              <span className="og-label min-w-0 max-w-full overflow-x-auto whitespace-nowrap text-b3 text-fg-muted">
                hash <span className="og-mono text-m2" data-package-hash>{pkg.hash}</span>
              </span>
              <span className="og-label min-w-0 max-w-full overflow-x-auto whitespace-nowrap text-b3 text-fg-muted">
                graph <span className="og-mono text-m2">{pkg.graphSnapshotHash}</span>
              </span>
              <span className="og-label text-b3 text-fg-muted">
                kernel <span className="og-mono text-m2" data-num="label">{pkg.kernelVersion}</span>
              </span>
              {/* Not Ember: taking the text away is not the decision. The one fill on this
                  view is the signature, below. */}
              <button
                type="button"
                onClick={() => downloadText(`${pkg.id}-${pkg.rendering}.md`, pkg.text)}
                className="og-label inline-flex min-h-11 min-w-11 items-center justify-center gap-2 border border-hairline-strong px-3 text-b3"
              >
                <Download {...ICON_PROPS} size={16} aria-hidden /> Download the text
              </button>
            </div>

            <VerifyButton sessionId={sessionId} episodeId={episodeId} rendering={rendering} />

            <pre className="og-mono overflow-x-auto whitespace-pre-wrap border border-hairline p-4 text-b3" data-num="label">
              {bodyByKey && activeKey ? (bodyByKey[activeKey] ?? pkg.text) : pkg.text}
            </pre>
          </div>
        </div>
      )}

      {/* The six interchange formats, as plain download links straight at the kernel's own
          export route (`GET …/export?format=…&rendering=…`). Nothing is assembled here and
          nothing is fetched: the browser asks the server for the file, at whichever
          rendering the toggle above is set to. They are offered whether or not a package
          has been rendered in this session — an export is a reading of the record, not of
          the document on screen. */}
      <section className="mt-8" data-exports>
        <h2 className="og-display text-e2">Exports</h2>
        <p className="mt-1 text-b3 text-fg-secondary">The same record in the six interchange formats, written by the kernel at the rendering chosen above.</p>
        <ul className="mt-2 flex flex-wrap gap-2">
          {EXPORT_FORMATS.map(({ format, label }) => (
            <li key={format}>
              <a
                href={`/api/session/${sessionId}/episode/${episodeId}/export?format=${format}&rendering=${rendering}`}
                // Named, not left to the browser: without this every export lands in the
                // downloads folder as "export", and six of them are six files whose only
                // difference is a number the browser added. The extension is the server's
                // to choose (it sets the media type), so it is deliberately not guessed
                // here.
                download={`docket-${episodeId}-${format}-${rendering}`}
                data-export={format}
                className="og-label inline-flex min-h-11 min-w-11 items-center justify-center gap-2 border border-hairline-strong px-3 text-b3"
              >
                <Download {...ICON_PROPS} size={16} aria-hidden />
                {/* A standard's number is part of its name, not a measurement. */}
                <span data-num="label">{label}</span>
              </a>
            </li>
          ))}
        </ul>
      </section>

      {/* `id`: the coverage sheet's "the Commitment / sign block" row is addressed
          `/package#commit`, and the frame scrolls a hash into view. */}
      <section id="commit" className="mt-8 border border-hairline-strong bg-raised p-4" data-decision-block>
        <h2 className="og-display text-e2">The decision</h2>
        {signed && commitment && (<div data-commitment>
          <p><Sev kind="done">Signed. The signature binds to the package hash shown above.</Sev></p>
          <dl className="mt-2 grid gap-x-4 gap-y-1 text-b3 md:grid-cols-[minmax(110px,0.3fr)_1fr]">
            <dt className="og-label text-fg-muted">signed by</dt><dd className="og-mono text-m2 break-words" data-num="label">{commitment.signer.identity} · {commitment.signer.role} · {commitment.signedAt}</dd>
            <dt className="og-label text-fg-muted">the option</dt><dd className="og-mono text-m2 break-words" data-num="label">{commitment.selected}</dd>
            <dt className="og-label text-fg-muted">stop rules</dt><dd className="break-words" data-num="label">{commitment.stopRules.join(' · ')}</dd>
            <dt className="og-label text-fg-muted">bound to</dt><dd className="og-mono text-m2 break-all" data-num="label">{commitment.packageHash}</dd>
            {(commitment.dissent ?? []).length > 0 && <><dt className="og-label text-fg-muted">dissent</dt><dd className="break-words" data-num="label">{commitment.dissent!.map((d) => `${d.who}: ${d.text}`).join(' · ')}</dd></>}
          </dl>
          <p className="mt-2 text-b3 text-fg-muted">Conditions are not yet captured here.</p>
        </div>)}
        {signed && !commitment && !commitmentView.error && <Loading label="loading the commitment" />}
        {signed && commitmentView.error && <ErrorState message={commitmentView.error.message} route={`session/${sessionId}/object/${episode.commitment ?? ''}`} onRetry={commitmentView.refresh} />}
        {pending && returned && (<div data-sent-back>
          <p><Sev kind="wait">
            Sent back for rework on <span className="og-mono text-m2">{trigger?.createdAt ?? '_[unavailable]_'}</span>; reason: <span data-num="label">{trigger?.description ?? returned.text}</span>
          </Sev></p>
          <p className="mt-2 text-b3 text-fg-secondary">The signer-return trigger is on the record and nothing was deleted; the programme can open a new episode from it. A signature is not on offer while the send-back stands.</p>
          <p className="mt-3 flex flex-wrap gap-2">
            <button type="button" onClick={() => openOverlay({ kind: 'sendback' })} className={btn}>Send back for rework</button>
          </p>
        </div>)}
        {pending && !returned && (<>
          <p className="text-b3 text-fg-secondary">{ready ? 'Nothing stops sign-off. Read the package above, then sign, or send it back with a reason.' : 'Readiness still names blockers; the gate will refuse a signature until they are cleared.'}</p>
          <p className="mt-3 flex flex-wrap items-center gap-2">
            {fullHash && ready && <button type="button" onClick={() => openOverlay({ kind: 'sign', packageHash: fullHash, defaultRole: signerRole })} data-ember="" className={btn}>Sign</button>}
            {!fullHash && <span className="text-b3 text-fg-muted">Render the full package first; the signature binds to its hash.</span>}
            <button type="button" onClick={() => openOverlay({ kind: 'sendback' })} className={btn}>Send back for rework</button>
          </p>
        </>)}
        {refusal && !signed && (
          <div className="mt-3">
            <ErrorState kind="refused" message={`Asked at ${refusal.at} by ${refusal.actor.actorId}; the gate refused the signature and the state did not move.`} unsatisfied={refusal.checksUnsatisfied} />
          </div>
        )}
        {!pending && !signed && <p className="text-b3 text-fg-secondary">This decision is not yet awaiting a signature. It is at <span className="og-mono text-m2">{episode.lifecycleState}</span>; the package can still be rendered and read.</p>}
      </section>
    </div>
  );
}
