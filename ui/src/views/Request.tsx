// File the request (spec §9) — the "messy request in" half of the topic, asked as three
// questions instead of one wall of fields. Step one is what is being decided, step two
// is who asked, under what policy and when it is needed by, step three is which source
// the AI should read. `?step=1|2|3` is honoured on load so a link can point at one.
//
// Every card the elicitation draws is agent-proposed: dashed frame, `circle-dashed`
// glyph, confidence, locator. That is the whole point of the view — the model has spoken
// and NOTHING has been decided yet. The gate that decides is the Model view.
//
// No numeral in a card is a `<Num>`. If the model proposed a numeric constraint it
// renders as text inside the object summary, because it is not a value anything
// computed; the distinction is written into every card's `title`
// (`ObjectChip.NUMERAL_TITLE`).
//
// `requestedBy` has no default and cannot be blank. It becomes `Charter.authority.signer`
// — a claim about who asked for this trade study — and the operator opening a demo
// session is not that person. The server refuses a blank one (422); this view refuses to
// send one.
//
// THE DEADLINE. Step two's date is written to `Charter.neededBy` through
// `POST …/object/{charter}/accept {edits: {neededBy}}` — the same human-authored
// revision every other acceptance is, because there is no lighter write that leaves the
// model's name on the object. Two consequences, both deliberate and both recorded in the
// plan rather than hidden: setting a deadline satisfies `charter-human-accepted`, and it
// does not satisfy `charter-three-fields`, which gates on content — the reviewer still
// fills the empty field on the Model view. The date input's value is sent verbatim; this
// file does no date arithmetic, and the clock's own numbers are the server's.
//
// There is exactly ONE deadline field on the page at a time. Step two carries it while
// nothing is filed yet, where the write has to wait for a charter to exist; once a
// decision is open the field at the foot of the view carries it instead, and writes the
// open charter immediately.

import { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { apiGet, apiPost, apiPut, ApiError } from '../api/client';
import { openStream } from '../api/stream';
import { useHealth } from '../api/useHealth';
import { useSession } from '../api/useSession';
import { useWorkspace } from '../api/useWorkspace';
import { ErrorState } from '../components/ErrorState';
import { ObjectChip } from '../components/ObjectChip';
import { Term } from '../components/Term';
import { ViewHead } from '../components/ViewHead';
import type { AuthorType } from '../lib/provenance';
import type { ElicitResponse, ObjectView, SourcesResponse, StreamEvent } from '../types/api';

interface Streamed { id: string; type: string; authorType: AuthorType; confidence: string | null; locator: string | null; summary: string }
const STEPS = ['What is being decided', 'Who asked, under what policy, and when it is needed', 'Which source'];
// [ruling M1, plan 07 T6 fix round] Printed for both the SSE `error` payload and a caught
// `fetch` failure. Neither source's own words reach this view: both routinely carry the
// backend base URL, which is a provider string on a proposal-facing view (honesty rule 3)
// whether or not the provider it names is denylisted.
const ERROR_SENTENCE = 'The backend could not complete the elicitation. Open Settings for what it said.';
// One outline button, written once. The Ember fill is never a class here — a view marks
// its one primary act with `data-ember` and the frame paints it (`frame/frame.css`).
const BTN = 'og-label inline-flex min-h-11 items-center justify-center border border-hairline-strong px-4 text-b3';

/** `provenance` arrives on the SSE `object` event as the object's raw
 * `ingestionProvenance` — read defensively (it is unparsed JSON off a socket), never
 * reshaped. */
function locatorOf(p: unknown): string | null {
  const v = p && typeof p === 'object' ? (p as Record<string, unknown>).locator : null;
  return typeof v === 'string' ? v : null;
}

/** The deadline on a charter that already exists — the decision was filed before anyone
 * knew when it was wanted, which is the ordinary case. Seeded from the charter's own
 * stored value so the field says what the record says. */
function DeadlineForm({ sessionId, charterId }: { sessionId: string; charterId: string }) {
  const [value, setValue] = useState('');
  const [busy, setBusy] = useState(false);
  const { toast, bumpRecord } = useWorkspace();
  useEffect(() => {
    apiGet<ObjectView>(`/session/${sessionId}/object/${charterId}`).then((v) => {
      const n = (v.object as { neededBy?: string }).neededBy;
      if (typeof n === 'string') setValue(n);
    }).catch(() => undefined);
  }, [sessionId, charterId]);
  async function save() {
    setBusy(true);
    try {
      await apiPost(`/session/${sessionId}/object/${charterId}/accept`, { edits: { neededBy: value } });
      bumpRecord();
      toast(value ? `Deadline set to ${value}. The clock now counts to it.` : 'Deadline cleared. The clock says no deadline is set.', 'done');
    } catch (e) {
      toast(e instanceof ApiError ? (e.body.message ?? e.message) : String(e), 'stop');
    } finally { setBusy(false); }
  }
  return (
    <div className="border border-hairline bg-raised p-4" data-deadline-form>
      <label className="block"><span className="og-label block text-b3">When is this decision needed by? <Term k="charter" plain="a charter field" /></span>
        <input name="needed-by" type="date" value={value} onChange={(e) => setValue(e.target.value)} className="og-mono mt-1 min-h-11 max-w-[260px] border border-hairline bg-transparent px-2 text-m1" />
        <small className="mt-1 block text-m1 text-fg-muted">Saving writes a human revision of the charter with the date; the header chip and the clock count to it.</small></label>
      <p className="mt-3"><button type="button" onClick={save} disabled={busy} className={BTN}>Save the deadline</button></p>
    </div>
  );
}

/** Which of the three steps `?step=` names, clamped to one of them. Anything absent,
 * out of range or not a number is step one — an address is not a reason to show a blank
 * screen. Not arithmetic on a record value: this is a query parameter. */
function stepFromParams(raw: string | null): number {
  return Math.min(3, Math.max(1, Math.trunc(Number(raw ?? '1')) || 1));
}

export function Request() {
  const { sessionId, episode, refetch, setEpisodeId } = useSession();
  const health = useHealth();
  const { toast, bumpRecord } = useWorkspace();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const [step, setStep] = useState(() => stepFromParams(params.get('step')));
  const [text, setText] = useState('');
  const [by, setBy] = useState('');
  const [policyId, setPolicyId] = useState('');
  const [neededBy, setNeededBy] = useState('');
  const [source, setSource] = useState('');
  const [sources, setSources] = useState<SourcesResponse | null>(null);
  const [objects, setObjects] = useState<Streamed[]>([]);
  const [stages, setStages] = useState<string[]>([]);
  const [working, setWorking] = useState(false);
  const [done, setDone] = useState<ElicitResponse | null>(null);
  const [error, setError] = useState<{ message: string; route?: string } | null>(null);
  const [refusal, setRefusal] = useState<{ message: string; unsatisfied: string[] } | null>(null);
  const [switching, setSwitching] = useState(false);
  const closeRef = useRef<(() => void) | null>(null);

  // `?step=` is an address, not a seed. Read only in the initializer above, it worked for
  // a fresh load and did nothing at all for a link followed while this view was already
  // on screen — which is exactly what the coverage sheet's Go buttons do. Synced here so
  // the step follows the address either way; `stepFromParams` returns the same 1 for an
  // absent or unparseable value, so a plain `/request` still means step one.
  useEffect(() => { setStep(stepFromParams(params.get('step'))); }, [params]);
  useEffect(() => { apiGet<SourcesResponse>('/sources').then(setSources).catch(() => setSources(null)); }, []);
  useEffect(() => () => closeRef.current?.(), []);
  const recorded = sources?.recordedRequest ?? null;
  // The committed recording answers this request only under the source artefact and the
  // policy id the server advertised with it, so the button fills all three together.
  const loadRecorded = useCallback(() => {
    if (!recorded) return;
    setText(recorded.text); setSource(recorded.sourceArtifact); setPolicyId(recorded.policyId);
  }, [recorded]);
  // "No backend reachable": the backend does not answer AND the server is in live mode.
  // In recorded mode there is nothing to reach — the recorded fixture is the answer — so
  // the one act stays available.
  const unreachable = health.data ? !health.data.backend.reachable && health.data.mode === 'live' : false;

  async function switchToRecorded() {
    setSwitching(true);
    // The mode is what picks the backend (`routes/agent._settings_for`), so re-read
    // whether the committed recording can answer the request now loaded.
    try { await apiPut('/settings/mode', { mode: 'recorded' }); health.refetch(); apiGet<SourcesResponse>('/sources').then(setSources).catch(() => undefined); }
    finally { setSwitching(false); }
  }

  async function elicit() {
    if (!sessionId) return;
    setObjects([]); setStages([]); setError(null); setRefusal(null); setDone(null); setWorking(true);
    closeRef.current?.();
    const handle = (evt: StreamEvent) => {
      if (evt.event === 'stage') setStages((s) => [...s, `${evt.data.stage} · ${evt.data.status}`]);
      if (evt.event === 'object') setObjects((prev) => [...prev, { id: evt.data.id, type: evt.data.type, authorType: (evt.data.authorType ?? 'agent') as AuthorType, confidence: evt.data.confidence ?? null, locator: locatorOf(evt.data.provenance), summary: evt.data.summary ?? '' }]);
      if (evt.event === 'error') setError({ message: ERROR_SENTENCE });
    };
    // `/elicit` publishes its whole burst of `object` events while the POST is still in
    // flight, and a plain subscription replays nothing that happened before it opened —
    // so the POST waits for the socket. The timeout is a floor, not a race: if the
    // browser never fires `open`, the elicitation still runs and the cards simply do not
    // stream, which is better than a button that hangs.
    await new Promise<void>((resolve) => { let settled = false; const once = () => { if (!settled) { settled = true; resolve(); } }; closeRef.current = openStream(sessionId, handle, { onOpen: once }); window.setTimeout(once, 2000); });
    try {
      const res = await apiPost<ElicitResponse>(`/session/${sessionId}/elicit`, { requestText: text, sourceArtifact: source, requestedBy: by, ...(policyId ? { policyId } : {}) });
      setDone(res); refetch(); setEpisodeId(res.episode.id); bumpRecord();
      toast('The AI drafted the model. Nothing it drafted has been agreed.', 'done');
      // [review fix, Important 2] The deadline is a SECOND write, and it fails on its
      // own terms. Inside the elicitation's `catch` a refused accept would have printed
      // "the backend could not complete the elicitation" over a model that was in fact
      // drafted and filed, and the cards below would never have rendered. Its own
      // try/catch, after the cards are on screen, and its own sentence — which names
      // the form directly below that can still save it.
      if (neededBy) {
        try {
          await apiPost(`/session/${sessionId}/object/${res.episode.charter}/accept`, { edits: { neededBy } });
          bumpRecord();
        } catch {
          toast('The request was filed, but the deadline was not saved. Set it below.', 'stop');
        }
      }
    } catch (err) {
      if (err instanceof ApiError && (err.status === 403 || err.status === 409)) setRefusal({ message: err.body.message ?? err.message, unsatisfied: err.body.unsatisfied ?? [] });
      else setError({ message: ERROR_SENTENCE, route: `session/${sessionId}/elicit` });
    } finally { setWorking(false); closeRef.current?.(); closeRef.current = null; }
  }

  const canElicit = !working && !unreachable && text.trim() !== '' && source.trim() !== '' && by.trim() !== '';
  const stepBar = (
    <div className="mb-4 flex flex-wrap gap-3">{STEPS.map((s, i) => (
      <span key={s} className={`flex-1 basis-36 border-t-2 pt-1.5 text-b3 ${step === i + 1 ? 'border-fg text-fg' : 'border-hairline text-fg-muted'}`} data-num="label">step {i + 1} · {s}</span>))}</div>
  );

  return (
    <div>
      <ViewHead eyebrow={episode ? 'request · already filed' : 'request · nothing filed yet'} title="File the request"
        sentence="Three questions, then the AI drafts a model from your source; it proposes and decides nothing." />
      {!sessionId && <p className="mb-4 border border-hairline bg-surface p-3 text-b3">Choose a decision in the header first — a request is filed into a session.</p>}
      {stepBar}
      <div className="border border-hairline bg-raised p-4" data-wizard>
        {step === 1 && (
          <>
            {/* The pasted source document itself. Its digits belong to whoever wrote the
                tasking — a paragraph number, a percentage, a date — and none of them is a
                value this application rendered, so the control carries the numeral walk's
                label carve-out. */}
            <label className="block"><span className="og-label block text-b3">Write the request the way it reached you — a memo, a tasking, a paragraph off a slide.</span>
              <textarea name="request-text" data-num="label" rows={8} value={text} onChange={(e) => setText(e.target.value)} placeholder="Compare…" className="mt-1 w-full border border-hairline bg-transparent p-3 text-b2" /></label>
            {recorded && <p className="mt-2 flex flex-wrap items-center gap-3"><button type="button" onClick={loadRecorded} className={BTN}>Load the recorded request</button>
              <span className="og-label text-b3 text-fg-muted">{recorded.answerRecorded ? 'answer recorded' : 'no recorded answer configured'}</span></p>}
            <div className="mt-4 flex flex-wrap items-center justify-between gap-2"><span className="text-b3 text-fg-muted">Nothing is written to the record until the AI is asked to read the source.</span>
              <button type="button" onClick={() => setStep(2)} data-ember="" className={BTN}>Next</button></div>
          </>
        )}
        {step === 2 && (
          <>
            <label className="block"><span className="og-label block text-b3">Who asked for this?</span>
              <input name="requested-by" value={by} onChange={(e) => setBy(e.target.value)} placeholder="NGCV CFT" className="mt-1 min-h-11 w-full border border-hairline bg-transparent px-2 text-b2" />
              <small className="block text-m1 text-fg-muted">Becomes the charter's signing authority. There is no default, deliberately.</small></label>
            {/* A policy id IS an identifier (`pol-default`), so this one field keeps mono. */}
            <label className="mt-3 block"><span className="og-label block text-b3">Under what policy?</span>
              <input name="policy-id" value={policyId} onChange={(e) => setPolicyId(e.target.value)} placeholder="pol-default" className="og-mono mt-1 min-h-11 w-full border border-hairline bg-transparent px-2 text-m2" />
              <small className="block text-m1 text-fg-muted">The policy decides which questions apply and which gates only a person may pass.</small></label>
            {/* [review fix, Important 3] Only while nothing is filed yet. With a
                decision already open there is a charter to write to NOW, and the form at
                the foot of the view does exactly that — two identically labelled date
                fields on one page, one of which silently waited for an elicitation that
                may never come, is a worse answer than one field that works. */}
            {!episode && <label className="mt-3 block"><span className="og-label block text-b3">When is this decision needed by?</span>
              <input name="needed-by" type="date" value={neededBy} onChange={(e) => setNeededBy(e.target.value)} className="og-mono mt-1 min-h-11 max-w-[260px] border border-hairline bg-transparent px-2 text-m1" />
              <small className="block text-m1 text-fg-muted">Written to the charter as a human edit once the AI has drafted it. It drives the clock; it never blocks anything.</small></label>}
            <div className="mt-4 flex flex-wrap justify-between gap-2"><button type="button" onClick={() => setStep(1)} className={BTN}>Previous</button><button type="button" onClick={() => setStep(3)} data-ember="" className={BTN}>Next</button></div>
          </>
        )}
        {step === 3 && (
          <>
            {/* [ruling M6] `hasLocalCopy` is the server's own field
                (`routes/session.list_sources`); rendered here so the picker never depends
                on a title's phrasing to say a source is a stub. Each option is a
                document's own title, whose numerals are the document's, not this
                application's — the narrowest element holding one is the option. */}
            <label className="block"><span className="og-label block text-b3">Which source should the AI read?</span>
              <select name="source-artifact" value={source} onChange={(e) => setSource(e.target.value)} className="og-label mt-1 min-h-11 w-full border border-hairline bg-transparent px-2 text-b3">
                <option value="">— pick a source —</option>
                {(sources?.sources ?? []).map((s) => <option key={s.artifact} value={s.artifact} data-num="label">{s.title ?? s.name}{s.hasLocalCopy ? '' : ' — no local copy'}</option>)}
              </select>
              {source && <span className="og-mono mt-1 block break-all text-m2 text-fg-secondary" data-num="label">{source}</span>}
              <small className="block text-m1 text-fg-muted">Only sources already in this session can be read, and every draft carries the page it came from.</small></label>
            {stages.length > 0 && <ul className="og-mono mt-3 text-m1 text-fg-secondary">{stages.map((s, i) => <li key={i} data-num="label">→ {s}</li>)}</ul>}
            {refusal && <ErrorState kind="refused" message={refusal.message} unsatisfied={refusal.unsatisfied} />}
            {error && <ErrorState message={error.message} route={error.route} />}
            {/* The two Ember candidates are never on the view together: `Elicit` while
                nothing is drafted, `Go to the model checklist` once something is.
                Disabled drops the fill entirely rather than dimming it — an Ember plane
                means "a human must act", and a button nobody can press asks nothing. */}
            {!done ? (
              <div className="mt-4 flex flex-wrap items-center gap-3"><button type="button" onClick={() => setStep(2)} className={BTN}>Previous</button>
                <button type="button" name="elicit" onClick={elicit} disabled={!canElicit} data-ember={canElicit ? '' : undefined} title={unreachable ? 'No backend reachable' : undefined} className={BTN}>{working ? 'Working' : 'Elicit'}</button>
                {unreachable && <><span className="og-label text-b3 text-fg-secondary">No backend reachable</span><button type="button" onClick={switchToRecorded} disabled={switching} className={BTN}>{switching ? 'switching…' : 'Switch to recorded'}</button></>}</div>
            ) : (
              <div className="mt-4">
                {/* [review fix, Important 1] No count here. `Num` is for values the
                    server sent, and the only number available was the length of an array
                    this file counted; `EpisodeView.counts` is a per-type breakdown of the
                    episode's reference lists, not a count of what was just drafted, so
                    there is no server numeral to print and the heading prints none. */}
                <h3 className="og-label text-b1">What the AI drafted</h3>
                <ul className="mt-2 grid list-none gap-3" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(min(260px, 100%), 1fr))' }}>
                  {(objects.length ? objects : done.objects.map((o) => ({ id: o.id, type: o.type, authorType: o.authorType, confidence: o.confidence, locator: o.provenance?.locator ?? null, summary: '' }))).map((o) => (
                    <ObjectChip key={o.id} id={o.id} type={o.type} summary={o.summary || o.type} authorType={o.authorType} confidence={o.confidence} locator={o.locator} />))}
                </ul>
                <p className="mt-3 text-b3 text-fg-secondary">Every object above is a proposal. Nothing here has been agreed, nothing has been computed, and the gate that decides is on the Model view.</p>
                <p className="mt-3 flex flex-wrap gap-2"><button type="button" onClick={() => navigate('/model')} data-ember="" className={BTN}>Go to the model checklist</button></p>
              </div>
            )}
          </>
        )}
      </div>
      {episode && sessionId && (
        <>
          <h2 className="og-display mt-8 mb-3 text-e2">The request already on the record</h2>
          <div className="mb-3 border border-hairline bg-raised p-4 text-b3">Episode <span className="og-mono text-m2" data-num="label">{episode.id}</span> is open in this session; eliciting again files a second episode beside it.</div>
          <DeadlineForm sessionId={sessionId} charterId={episode.charter} />
        </>
      )}
    </div>
  );
}
