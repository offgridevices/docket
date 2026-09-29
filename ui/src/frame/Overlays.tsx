// Which overlay is open.
import { useEffect, useState } from 'react';
import { apiGet, ApiError } from '../api/client';
import { useG1 } from '../api/useG1';
import { useReviewBundle } from '../api/useReviewBundle';
import { useSession } from '../api/useSession';
import { useWorkspace } from '../api/useWorkspace';
import { AuthorityDiagram } from '../components/AuthorityDiagram';
import { ErrorState } from '../components/ErrorState';
import { RawObjectDrawer } from '../components/RawObjectDrawer';
import { ReviewDialog } from '../components/ReviewDialog';
import { SettingsPanel } from '../components/SettingsPanel';
import type { ObjectView } from '../types/api';
import { BlockersSheet } from './BlockersSheet';
import { CoverageSheet } from './CoverageSheet';
import { SendBackSheet } from './SendBackSheet';
import { Sheet } from './Sheet';
import { SignSheet } from './SignSheet';

/** The raw object, fetched for whoever opened the drawer.
 *
 * A failed read is said out loud. Swallowing it left the drawer on its "loading" state for
 * ever, which is the one thing the loading/empty/error table forbids: a reader waiting on
 * a panel that will never fill cannot tell a slow route from a dead one. The route's own
 * words, the route that produced them and a retry, in a sheet that closes like any other.
 * The fetch is cancelled on unmount and re-run on retry, so a drawer closed mid-flight
 * never sets state on a component that is gone. */
function RawOverlay({ id }: { id: string }) {
  const { sessionId } = useSession();
  const { closeOverlay } = useWorkspace();
  const [object, setObject] = useState<ObjectView | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  const route = `session/${sessionId}/object/${id}`;
  useEffect(() => {
    if (!sessionId) return;
    let cancelled = false;
    setError(null);
    apiGet<ObjectView>(`/session/${sessionId}/object/${id}`)
      .then((o) => { if (!cancelled) setObject(o); })
      .catch((e) => {
        if (cancelled) return;
        setObject(null);
        setError(e instanceof ApiError ? (e.body.message ?? e.message) : String(e));
      });
    return () => { cancelled = true; };
  }, [sessionId, id, attempt]);
  if (error) {
    return (
      <Sheet title="That object could not be read" onClose={closeOverlay} centre>
        <ErrorState message={error} route={route} onRetry={() => setAttempt((n) => n + 1)} />
      </Sheet>
    );
  }
  return <RawObjectDrawer open onClose={closeOverlay} object={object} />;
}

/** One object of the G1 sheet, reviewed over whatever view is behind it — the review
 * card's third home, over the board rather than as a page of its own.
 *
 * `ReviewDialog` brings its own dialog handling: the card it holds takes focus on open,
 * and the dialog traps Tab and restores focus to the opener on close. So this reuses that
 * rather than wrapping it in `Sheet` — two nested `role="dialog"` elements would be worse
 * than either alone. The one thing `Sheet` has and the dialog does not is an Escape that
 * works when focus has fallen out of the panel — which happens the moment an action
 * completes and its button is replaced — so that listener is added here. */
function ReviewOverlay({ id }: { id: string }) {
  const { sessionId, episodeId, refetch } = useSession();
  // Closing has no address to leave: since Task 11 `/review/:objectId` is the Review VIEW,
  // and this overlay is only ever opened by a card's own action
  // (`openOverlay({kind: 'review'})`), so closing it leaves the reviewer where they were.
  const { closeOverlay: close, openOverlay, toast, bumpRecord } = useWorkspace();
  const g1 = useG1(sessionId, episodeId);
  // The card, the Reject echo and the "no such id" state, on the one hook `/review` uses
  // (`api/useReviewBundle.ts`) — the rules are identical wherever the card is drawn.
  const { bundle, absent } = useReviewBundle(sessionId, episodeId, id, g1.data);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') close(); };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [close]);

  // An id that is on no sheet this decision reaches is a fact, not a blank screen: the
  // frame believes an overlay is open, so something has to be on top of the page and it
  // has to be closable.
  if (absent) {
    return (
      <Sheet title="Nothing to review under this id" onClose={close} centre>
        <ErrorState
          message={`The decision that is open has no object ${id} on its review sheet. It may belong to another episode, or a reviewer may have dropped it from this one.`}
          route={`session/${sessionId}/episode/${episodeId}/g1`}
        />
      </Sheet>
    );
  }
  if (!bundle) return null;
  return (
    // `key`: the dialog seeds its edit boxes from the subject once, on mount, so a new
    // subject has to be a new dialog rather than one carrying the last object's text.
    <ReviewDialog key={bundle.subject.id} subject={bundle.subject} actions={bundle.actions} onClose={close}
      onDone={(r) => { toast(r.kind === 'gaps' ? 'Absence confirmed; confirmedBy is set to your actor id.' : r.kind === 'record' ? `${r.label}: ${r.id}` : 'Recorded; a new revision is authored by you.', 'done'); refetch(); bumpRecord(); }}
      onOpenRaw={() => openOverlay({ kind: 'raw', id })} />
  );
}

export function Overlays() {
  const { overlay, closeOverlay } = useWorkspace();
  if (!overlay) return null;
  switch (overlay.kind) {
    case 'settings': return <SettingsPanel open onClose={closeOverlay} />;
    case 'raw': return <RawOverlay id={overlay.id} />;
    // Keyed on the id: a second object opened over the first is a new review, and none
    // of this overlay's state (the bundle it built, whether that id was on the sheet)
    // belongs to it.
    case 'review': return <ReviewOverlay key={overlay.id} id={overlay.id} />;
    case 'blockers': return <BlockersSheet />;
    case 'coverage': return <CoverageSheet />;
    case 'authority': return <Sheet title="Who may write what" onClose={closeOverlay} centre><AuthorityDiagram /></Sheet>;
    case 'sign': return <SignSheet packageHash={overlay.packageHash} defaultRole={overlay.defaultRole} />;
    case 'sendback': return <SendBackSheet />;
    default: return null;
  }
}
