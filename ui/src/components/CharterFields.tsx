import { useCallback, useEffect, useState, type ReactNode } from 'react';
import { apiGet, apiPost, ApiError } from '../api/client';
import { useWorkspace } from '../api/useWorkspace';
import { ErrorState } from './ErrorState';
import { Loading } from './Loading';
import { Term } from './Term';
import type { ObjectView } from '../types/api';

/** The three AR 5-11 ¶4-5b fields `charter-three-fields` reads, with the plain question
 * each one asks. The schema's own name stays beside it under Explain. */
const FIELDS: [string, string][] = [['question', 'the question being decided'], ['decisionToBeMade', 'the decision to be made'], ['consequencesOfErroneousOutput', 'what happens if this is wrong']];

function text(v: unknown): string { return typeof v === 'string' ? v : ''; }
function message(e: unknown): string { return e instanceof ApiError ? (e.body.message ?? e.message) : e instanceof Error ? e.message : String(e); }

/** The charter's three mandated fields, inline; an empty one is typed here and saved as
 * a human revision through the same `accept` every other edit uses. Saving both fills
 * the field and puts a person's name on the charter, which is the two checks the gate
 * reads about it — so the gate ladder offers no button for either while this block is
 * working. When the read fails it says so and offers a retry, and it tells the view, so
 * the ladder puts its own remedies back rather than pointing at a box nobody can see. */
export function CharterFields({ sessionId, charterId, editable, onWritten, onUnavailable }: {
  sessionId: string; charterId: string; editable: boolean; onWritten: () => void; onUnavailable: (unavailable: boolean) => void;
}) {
  const [view, setView] = useState<ObjectView | null>(null);
  const [draft, setDraft] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const { toast, explain } = useWorkspace();
  const load = useCallback(() => {
    apiGet<ObjectView>(`/session/${sessionId}/object/${charterId}`)
      .then((v) => {
        setView(v);
        setDraft(Object.fromEntries(FIELDS.map(([k]) => [k, text((v.object as Record<string, unknown>)[k])])));
        setError(null);
        onUnavailable(false);
      })
      .catch((e: unknown) => { setView(null); setError(message(e)); onUnavailable(true); });
  }, [sessionId, charterId, onUnavailable]);
  useEffect(load, [load]);
  const stored = (k: string) => text((view?.object as Record<string, unknown> | undefined)?.[k]);
  const changed = Object.fromEntries(FIELDS.filter(([k]) => draft[k] !== stored(k)).map(([k]) => [k, draft[k]]));
  async function save() {
    setBusy(true);
    try {
      const v = await apiPost<ObjectView>(`/session/${sessionId}/object/${charterId}/accept`, { edits: changed });
      setView(v); toast(`Charter revised: rev ${v.rev}, authored by you.`, 'done'); onWritten();
    } catch (e) { toast(message(e), 'stop'); }
    finally { setBusy(false); }
  }
  // The frame is on the page from the first paint, carrying the charter's id, and the
  // fields arrive into it — an object the sheet lists must never be missing from the
  // view while a second read is in flight, and a read that failed must never look like
  // one that is still going.
  const frame = (children: ReactNode) => (
    <div id="charter" className="border border-hairline bg-raised p-4" data-object-id={charterId} data-object-type="Charter">{children}</div>
  );
  if (error) return frame(<ErrorState message={error} route={`session/${sessionId}/object/${charterId}`} onRetry={load} />);
  if (!view) return frame(<Loading label="the charter" />);
  const obj = view.object as Record<string, unknown>;
  const signer = text((obj.authority as { signer?: string } | undefined)?.signer);
  return frame(
    <>
      <dl className="grid gap-x-4 gap-y-1.5 text-b3 md:grid-cols-[minmax(110px,0.4fr)_1fr]">
        {FIELDS.map(([k, plain]) => (
          <div key={k} className="contents" data-charter-field={k}>
            <dt className="og-label text-fg-muted">{plain}{explain && <span className="og-mono text-m2"> {k}</span>}</dt>
            <dd className="min-w-0">{editable
              ? <textarea rows={3} value={draft[k] ?? ''} onChange={(e) => setDraft((d) => ({ ...d, [k]: e.target.value }))} placeholder="the record does not say — type it here" className="w-full border border-hairline-strong bg-transparent p-2 text-b2" />
              : <span data-num="label">{stored(k) || <span className="text-fg-muted">— <Term k="gap" /></span>}</span>}</dd>
          </div>
        ))}
        <dt className="og-label text-fg-muted">what is in scope</dt><dd className="min-w-0" data-num="label">{((obj.scope as { included?: string[] })?.included ?? []).join('; ') || '—'}</dd>
        <dt className="og-label text-fg-muted">what is out of scope</dt><dd className="min-w-0" data-num="label">{((obj.scope as { excluded?: string[] })?.excluded ?? []).join('; ') || '—'}</dd>
      </dl>
      {/* Who asked, as a sentence rather than a bare value in the table above: the
          record's own string here is an organisation's initials as often as a name, and
          a lone run of capitals in a value column reads as the interface shouting. */}
      <p className="mt-2 text-b3 text-fg-secondary" data-num="label">
        {signer ? `Asked for by ${signer}.` : 'The record does not say who asked for it.'}
      </p>
      {editable && <p className="mt-3"><button type="button" onClick={save} disabled={busy || Object.keys(changed).length === 0} className="og-label inline-flex min-h-11 items-center border border-hairline-strong px-3 text-b3">Save the charter</button></p>}
    </>,
  );
}
