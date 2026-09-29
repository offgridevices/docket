import { useEffect, useState } from 'react';
import { apiGet } from '../api/client';
import { useHealth } from '../api/useHealth';
import { useSession, type DemoSource } from '../api/useSession';
import { useWorkspace } from '../api/useWorkspace';
import type { SessionInfo } from '../types/api';

export const DEMO_TITLE: Record<DemoSource, string> = {
  'demo-a': 'Demo A · CBO GCV 2013',
  'demo-b': 'Demo B · OMFV 2019–2023',
  new: 'New session',
};

/** One decision = one workspace (R2): choosing here swaps map, queue, views and chat. */
export function DecisionSwitcher() {
  const { sessionId, openSession, adoptSession } = useSession();
  const { data: health } = useHealth();
  const { toast, bumpRecord } = useWorkspace();
  const [sessions, setSessions] = useState<SessionInfo[]>([]);
  useEffect(() => {
    apiGet<{ sessions: SessionInfo[] }>('/sessions').then((r) => setSessions(r.sessions)).catch(() => setSessions([]));
  }, [sessionId]);

  async function change(value: string) {
    if (value.startsWith('session:')) { adoptSession(value.slice('session:'.length)); bumpRecord(); return; }
    if (value.startsWith('open:')) {
      const source = value.slice('open:'.length) as DemoSource;
      await openSession(source);
      bumpRecord();
      toast(`Now in ${DEMO_TITLE[source]}. The map, the queue and the chat are this decision's own.`);
    }
  }
  const built = (s: DemoSource) => s === 'new' || health?.demoStores?.[s] !== false;
  return (
    // `data-num="label"` on every option, the same carve-out Home's demo cards take: a
    // demo's name carries the years it covers ("Demo A · CBO GCV 2013"), and that year
    // is part of a name, not a value read out of the record.
    <select aria-label="Which decision" value={sessionId ? `session:${sessionId}` : ''} onChange={(e) => void change(e.target.value)}
      className="og-label text-b3 min-h-11 min-w-0 max-w-[96px] sm:max-w-[168px] lg:max-w-[220px] border border-hairline-strong bg-canvas px-2">
      <option value="" disabled>— choose a decision —</option>
      {sessions.length > 0 && (
        <optgroup label="Open">
          {sessions.map((s) => (
            <option key={s.id} value={`session:${s.id}`} data-num="label">{DEMO_TITLE[s.source as DemoSource] ?? s.source} · {s.id}</option>
          ))}
        </optgroup>
      )}
      <optgroup label="Start">
        {(['demo-a', 'demo-b', 'new'] as DemoSource[]).map((s) => (
          <option key={s} value={`open:${s}`} disabled={!built(s)} data-num="label">{built(s) ? DEMO_TITLE[s] : `${DEMO_TITLE[s]} — not built`}</option>
        ))}
      </optgroup>
    </select>
  );
}
