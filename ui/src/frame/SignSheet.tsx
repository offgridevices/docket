// Sign this decision (Task 15) — `POST …/sign`, `kernel.commit.sign`. The person chooses
// the option, names their role, writes at least one stop rule and, if they wish, a dissent
// that is recorded with the signature (`Commitment.dissent`). The commitment binds to the
// full package's hash and the SIGNED transition is driven through the kernel's own gate:
// a refusal there is a 409 with the checks by name, written to the record, so the sheet
// bumps the record on that answer as well as on a signature.
//
// The `Sign` here carries `data-ember` like the view's own, but the frame unpaints every
// Ember while a sheet is open (`frame.css`), so nothing is lit twice.
import { useEffect, useState } from 'react';
import { apiGet, apiPost, ApiError } from '../api/client';
import { useSession } from '../api/useSession';
import { useWorkspace } from '../api/useWorkspace';
import { Sev } from '../components/Sev';
import type { ObjectView, SignRequest, SignResponse } from '../types/api';
import { Sheet } from './Sheet';

export function SignSheet({ packageHash, defaultRole }: { packageHash: string; defaultRole: string }) {
  const { sessionId, episodeId, episode, refetch } = useSession();
  const { closeOverlay, toast, bumpRecord } = useWorkspace();
  const [options, setOptions] = useState<{ id: string; name: string }[]>([]);
  const [selected, setSelected] = useState('');
  const [role, setRole] = useState(defaultRole);
  const [rules, setRules] = useState('');
  const [dissent, setDissent] = useState<{ who: string; text: string } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    if (!sessionId || !episode) return;
    let cancelled = false;
    // One read per option, for its name (`Alternative.name`), falling back to the id; the
    // ids themselves are the episode's own `alternatives`, never a list this sheet keeps.
    Promise.all(episode.alternatives.map((id) => apiGet<ObjectView>(`/session/${sessionId}/object/${id}`).then((v) => ({ id, name: String((v.object as { name?: string }).name ?? id) }))))
      .then((o) => { if (cancelled) return; setOptions(o); setSelected((s) => s || o[0]?.id || ''); })
      .catch(() => { if (!cancelled) setError('The options could not be read from the record.'); });
    return () => { cancelled = true; };
  }, [sessionId, episode]);
  async function doSign() {
    const stopRules = rules.split('\n').map((s) => s.trim()).filter(Boolean);
    if (!selected || !role.trim() || stopRules.length === 0) { setError('Choose the option, name your role, and write at least one stop rule.'); return; }
    setBusy(true); setError(null);
    try {
      const body: SignRequest = { selected, role: role.trim(), stopRules, dissent: dissent && dissent.text.trim() ? [dissent] : null };
      await apiPost<SignResponse>(`/session/${sessionId}/episode/${episodeId}/sign`, body);
      toast('Signed. The commitment is on the record, bound to the package hash.', 'done'); refetch(); bumpRecord(); closeOverlay();
    } catch (e) {
      setError(e instanceof ApiError ? (e.body.message ?? e.message) : String(e));
      // A 409 is the gate's refusal: the commitment and the refused attempt are on the
      // record, so the view behind this sheet re-reads and shows the refusal by name.
      if (e instanceof ApiError && e.status === 409) { refetch(); bumpRecord(); }
    }
    finally { setBusy(false); }
  }
  const input = 'mt-1 min-h-11 w-full border border-hairline-strong bg-transparent p-2 text-b2';
  return (
    <Sheet title="Sign this decision" onClose={closeOverlay}>
      <h2 className="og-display text-e2">Sign this decision</h2>
      <p className="mt-1 text-b3 text-fg-secondary" data-num="label">What happens: a Commitment object is written in your name, bound to package hash <span className="og-mono text-m2">{packageHash}</span>, and the decision moves to SIGNED. Nothing about the package changes. Conditions are not yet captured here.</p>
      <label className="mt-4 block text-b3"><span className="og-label">The option you are choosing</span>
        <select aria-label="The option you are choosing" value={selected} onChange={(e) => setSelected(e.target.value)} className={input}>{options.map((o) => <option key={o.id} value={o.id}>{o.name}</option>)}</select></label>
      <label className="mt-3 block text-b3"><span className="og-label">Your role</span><input aria-label="Your role" value={role} onChange={(e) => setRole(e.target.value)} className={input} /></label>
      <label className="mt-3 block text-b3"><span className="og-label">Stop rules</span><span className="block text-fg-muted">one per line — what would make this decision wrong</span>
        <textarea aria-label="Stop rules" rows={3} value={rules} onChange={(e) => setRules(e.target.value)} className={input} /></label>
      {dissent ? (<div className="mt-3 border border-hairline p-3">
        <label className="block text-b3"><span className="og-label">Who dissents</span><input aria-label="Who dissents" value={dissent.who} onChange={(e) => setDissent({ ...dissent, who: e.target.value })} className={input} /></label>
        <label className="mt-2 block text-b3"><span className="og-label">The dissent</span><textarea aria-label="The dissent" rows={3} value={dissent.text} onChange={(e) => setDissent({ ...dissent, text: e.target.value })} className={input} /></label>
      </div>) : <p className="mt-3"><button type="button" onClick={() => setDissent({ who: '', text: '' })} className="og-label inline-flex min-h-11 items-center px-3 text-b3 underline underline-offset-4">Add a dissent</button></p>}
      {error && <p className="mt-2" data-field-error><Sev kind="stop">{error}</Sev></p>}
      <p className="mt-4 flex gap-2">
        {/* Out of reach until the options have been read and one is selected: a click that
            landed first would be swallowed by the check above rather than sent. */}
        <button type="button" onClick={() => void doSign()} disabled={busy || !selected} data-ember="" className="og-label inline-flex min-h-11 items-center border border-hairline-strong px-4 text-b3">Sign</button>
        <button type="button" onClick={closeOverlay} className="og-label inline-flex min-h-11 items-center px-3 text-b3 underline underline-offset-4">Not yet</button>
      </p>
    </Sheet>
  );
}
