// Everything that stops this decision moving on, each with a Go.
import { useNavigate } from 'react-router-dom';
import { useNeeds } from '../api/useNeeds';
import { useSession } from '../api/useSession';
import { useWorkspace } from '../api/useWorkspace';
import { Sev } from '../components/Sev';
import { Sheet } from './Sheet';

export function BlockersSheet() {
  const { sessionId, episodeId } = useSession();
  const { closeOverlay } = useWorkspace();
  const navigate = useNavigate();
  const { data } = useNeeds(sessionId, episodeId);
  const items = data?.blocking.items ?? [];
  return (
    <Sheet title="What is blocking this decision" onClose={closeOverlay} centre>
      {items.length === 0 ? <p className="text-b3">Nothing is blocking this decision right now.</p> : (
        <ul className="flex flex-col">
          {items.map((b, i) => (
            <li key={`${b.rule}-${i}`} className="flex items-center justify-between gap-3 border-t border-hairline py-2.5">
              <Sev kind={b.severity === 'gate' ? 'stop' : b.severity === 'blocking' ? 'blocking' : 'warning'}>
                <span data-num="label">{b.message}</span> <span className="og-mono text-m2 text-fg-muted">{b.rule}</span>
              </Sev>
              <button type="button" onClick={() => { closeOverlay(); navigate(b.route); }} className="og-label inline-flex min-h-11 min-w-11 items-center justify-center border border-hairline-strong px-3 text-b3">Go</button>
            </li>
          ))}
        </ul>
      )}
    </Sheet>
  );
}
