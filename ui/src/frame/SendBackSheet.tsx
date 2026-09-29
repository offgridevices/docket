// Send this package back (Task 15) — `POST …/send-back`, `kernel.refresh.signer_return`.
// A human act, written in the server's configured actor's name with the reason verbatim;
// the package and the episode stay exactly as they were, and the rework becomes a new
// episode through the programme's own refresh path. An empty reason never reaches the
// server: the inline error is the first line of defence, the route's 422 the second.
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { apiPost, ApiError } from '../api/client';
import { useSession } from '../api/useSession';
import { useWorkspace } from '../api/useWorkspace';
import { Sev } from '../components/Sev';
import { Sheet } from './Sheet';

export function SendBackSheet() {
  const { sessionId, episodeId, refetch } = useSession();
  const { closeOverlay, toast, bumpRecord } = useWorkspace();
  const navigate = useNavigate();
  const [reason, setReason] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  async function send() {
    if (!reason.trim()) { setError('Sending back needs a named reason.'); return; }
    setBusy(true); setError(null);
    try {
      await apiPost(`/session/${sessionId}/episode/${episodeId}/send-back`, { reason: reason.trim() });
      toast('Sent back. A signer-return trigger is on the record; the programme can open a new episode from it.', 'done');
      refetch(); bumpRecord(); closeOverlay(); navigate('/');
    } catch (e) { setError(e instanceof ApiError ? (e.body.message ?? e.message) : String(e)); }
    finally { setBusy(false); }
  }
  return (
    <Sheet title="Send this package back" onClose={closeOverlay}>
      <h2 className="og-display text-e2">Send this package back</h2>
      <p className="mt-1 text-b3 text-fg-secondary">What happens: a signer-return trigger is written in your name with your reason, and the decision stays exactly as it is. Nothing is deleted; a new episode is how the rework happens.</p>
      <label className="mt-4 block text-b3"><span className="og-label">Why it is going back</span>
        <textarea aria-label="Why it is going back" rows={4} value={reason} onChange={(e) => setReason(e.target.value)} className="mt-1 w-full border border-hairline-strong bg-transparent p-2 text-b2" /></label>
      {error && <p className="mt-2" data-field-error><Sev kind="stop">{error}</Sev></p>}
      <p className="mt-4 flex gap-2">
        <button type="button" onClick={() => void send()} disabled={busy} className="og-label inline-flex min-h-11 items-center border border-hairline-strong px-4 text-b3">Send it back</button>
        <button type="button" onClick={closeOverlay} className="og-label inline-flex min-h-11 items-center px-3 text-b3 underline underline-offset-4">Keep it</button>
      </p>
    </Sheet>
  );
}
