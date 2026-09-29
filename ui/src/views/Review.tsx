// Read and agree (spec §11) — the review card as a place you can go, not only a popup
// that happens to you.
//
// Two addresses, one component:
//   `/review`            the reading queue. Everything the AI drafted and every absence
//                        it recorded, one card at a time, with what needs a person first.
//   `/review/:objectId`  that one object, opened from a card, a remedy on the gate
//                        ladder or a link somebody pasted. Back to the model, and on to
//                        the next unread.
// The third home is `ReviewDialog`, the modal the model's own cards open over the board.
// All three render `ReviewCard`, and all three build their subject through
// `useReviewBundle`, so the six regions read the same wherever a reviewer meets them.
//
// Nothing here counts. The reading order is `needs.items`' own order (the server decided
// what needs a person and in what order) followed by the rest of the sheet, and the
// position indicator is a row of marks rather than "3 of 9" — a numeral the browser
// counted is exactly what the `Num` convention exists to keep off the screen.
//
// THE READING IS FIXED once, when the record has answered FOR THE EPISODE IN HAND, and
// then left alone. Both halves matter:
//   · Fixed, because accepting a draft makes it human-authored, which drops it out of the
//     live queue — a list recomputed under the reviewer's hand would swap the card they
//     just acted on for a different object before they had read what was written.
//   · For the episode in hand, because `useFetched` keeps the previous path's data while
//     the next read is in flight. "The sheet arrived" and "the sheet is this decision's"
//     are different facts, and freezing on the first one binds the reading to the
//     decision the reviewer just left.
// What the record SAYS about each card still updates on every write; only the order is
// held still.
import { useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { useG1 } from '../api/useG1';
import { useNeeds } from '../api/useNeeds';
import { useReviewBundle } from '../api/useReviewBundle';
import { useSession } from '../api/useSession';
import { useWorkspace } from '../api/useWorkspace';
import { ErrorState } from '../components/ErrorState';
import { Loading } from '../components/Loading';
import { ReviewCard } from '../components/ReviewCard';
import { ViewHead } from '../components/ViewHead';

/** The two queue kinds `kernel.queue.needs` raises against one object: an assumption the
 * answer depends on that nobody has read, and a recorded absence nobody has confirmed. */
const NEEDS_A_PERSON = ['linchpin-unreviewed', 'gap-unconfirmed'];

const BTN = 'og-label inline-flex min-h-11 items-center border border-hairline-strong px-3 text-b3 disabled:text-fg-muted';

/** The reading order: what needs a person first, in the order the server listed it, then
 * everything else drafted, in the order the sheet lists it. A filter and a de-duplication
 * — no sort, and nothing counted. */
function order(drafted: string[], needsFirst: string[]): string[] {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const id of [...needsFirst, ...drafted]) {
    if (seen.has(id) || !drafted.includes(id)) continue;
    seen.add(id);
    out.push(id);
  }
  return out;
}

export function Review() {
  const { sessionId, episodeId, refetch } = useSession();
  const { objectId } = useParams<{ objectId: string }>();
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const g1 = useG1(sessionId, episodeId);
  const needs = useNeeds(sessionId, episodeId);
  const { toast, bumpRecord, openOverlay } = useWorkspace();
  /** The reading, and the episode it was taken from. */
  const [reading, setReading] = useState<{ episodeId: string; ids: string[] } | null>(null);
  /** The episode whose reading the reviewer has closed with `Finish reading`. */
  const [closed, setClosed] = useState<string | null>(null);

  // The two reads, but only while they are about the decision the header now shows.
  const sheet = g1.data && g1.data.episode === episodeId ? g1.data : null;
  const queue = needs.data && needs.data.episode === episodeId ? needs.data : null;

  /** Everything on this episode's sheet a person could still read and agree: the AI's own
   * drafts that the record offers an act on, and the absences this episode may confirm. */
  const live = useMemo(() => {
    if (!sheet) return [];
    // A recorded absence is on the sheet twice — as a gap and as the
    // `InsufficientEvidence` object behind it — and only the gap's own rule decides
    // whether it is still waiting: once a person has confirmed it, the act the record
    // wanted has happened, and the object's standing offer to "accept the gap as written"
    // is not a second thing to read.
    const recordedAbsence = new Set(sheet.gaps.map((g) => g.id));
    const drafted = [
      ...sheet.objects.filter((o) => o.authorType === 'agent' && o.actions.length > 0 && !recordedAbsence.has(o.id)).map((o) => o.id),
      ...sheet.gaps.filter((g) => !g.confirmed && g.confirmableHere).map((g) => g.id),
    ];
    const first = (queue?.items ?? [])
      .filter((i) => i.objectId && NEEDS_A_PERSON.includes(i.kind))
      .map((i) => i.objectId as string);
    return order(drafted, first);
  }, [sheet, queue]);

  // Settled when the sheet is this episode's and the queue has answered for it. An error
  // on the queue read still settles it: the sheet's own order is the honest fallback, and
  // waiting forever would be a blank page.
  const settled = !!sheet && (!!queue || !!needs.error);
  useEffect(() => {
    if (!settled || !episodeId) return;
    setReading((prev) => (prev?.episodeId === episodeId ? prev : { episodeId, ids: live }));
    // `live` is deliberately read but not depended on: this effect exists to take the
    // FIRST reading of an episode, and re-running it as the record changes would be the
    // recomputation the whole design is avoiding.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [settled, episodeId]);

  // Compared on the way out, so a reading held for another episode is never on screen —
  // not even for the one frame between the switch and the effect that replaces it.
  const list = reading?.episodeId === episodeId ? reading.ids : [];
  const finished = closed === episodeId;
  const index = Math.min(Math.max(Number(params.get('i') ?? 0) || 0, 0), Math.max(list.length - 1, 0));
  const current = finished ? null : objectId ?? list[index] ?? null;
  /** What of this reading is still waiting on a person. */
  const remaining = list.filter((id) => live.includes(id));
  const { bundle, absent } = useReviewBundle(sessionId, episodeId, current, g1.data);

  if (!sessionId || !episodeId) {
    return <ViewHead eyebrow="review" title="Read and agree" sentence="Choose a decision in the header first." />;
  }

  const go = (i: number) => navigate(`/review?i=${Math.min(Math.max(i, 0), Math.max(list.length - 1, 0))}`);
  const nextUnread = remaining.find((id) => id !== current);
  // Nothing on this reading is waiting on a person any more. The card in hand stays, with
  // its recorded echo, until the reviewer closes the reading themselves — the finished
  // sentence and a card are never on screen together.
  const nothingLeft = settled && remaining.length === 0;

  return (
    <div>
      <ViewHead eyebrow={`review · ${episodeId}`} title="Read and agree"
        sentence="One drafted object at a time: what it says, why the AI proposed it, where it came from, what happens if it is wrong, and what you can do." />

      {!current && settled && sheet && (
        sheet.objects.length === 0
          ? <ErrorState message="Nothing to review yet. File a request first." />
          : (
            <p className="mb-4 flex flex-wrap items-center gap-3 border border-hairline bg-raised p-4 text-b2">
              Everything drafted has been read. Return to the model checklist.
              <button type="button" onClick={() => navigate('/model')} className={BTN}>Open the model</button>
            </p>
          )
      )}

      {current && (
        <>
          {/* Where you are, with no numeral the browser counted (the `Num` convention is
              for values the server authored, and "card four of nine" is neither): one mark
              per card in the reading, and a sentence saying what the marks mean, since a
              row of ticks on its own is a puzzle. */}
          <p className="mb-3 flex flex-wrap items-center gap-3 text-b3 text-fg-secondary" data-review-position>
            {objectId ? (
              <span>Opened directly from the model.</span>
            ) : (
              <>
                <span className="flex flex-wrap gap-1" aria-hidden>
                  {list.map((id, i) => (
                    <span key={id} data-mark data-current={i === index ? 'true' : undefined}
                      data-answered={remaining.includes(id) ? undefined : 'true'}
                      className={`h-2 w-5 border ${i === index ? 'border-fg bg-fg' : remaining.includes(id) ? 'border-hairline-strong' : 'border-hairline bg-fg-muted'}`} />
                  ))}
                </span>
                <span>One mark for each card in this reading: the dark one is where you are, a grey one has been answered, an outline is still waiting on you.</span>
              </>
            )}
          </p>

          {absent ? (
            <ErrorState
              message={`The decision that is open has no object ${current} on its review sheet. It may belong to another episode, or a reviewer may have dropped it from this one.`}
              route={`session/${sessionId}/episode/${episodeId}/g1`}
            />
          ) : bundle ? (
            // Keyed on the id: the card seeds its edit boxes from the subject once, on
            // mount, so the next card has to be a new card rather than one carrying the
            // last object's text and the last object's recorded echo.
            <ReviewCard key={current} subject={bundle.subject} actions={bundle.actions} ember
              onOpenRaw={() => openOverlay({ kind: 'raw', id: current })}
              onDone={(r) => {
                toast(r.kind === 'gaps' ? 'Absence confirmed; confirmedBy is set to your actor id.'
                  : r.kind === 'record' ? `${r.label}: ${r.id}`
                  : 'Recorded; a new revision is authored by you.', 'done');
                refetch(); bumpRecord();
              }} />
          ) : (
            <Loading label="the card" />
          )}

          <div className="mt-4 flex flex-wrap gap-2">
            {objectId ? (
              <>
                <button type="button" onClick={() => navigate('/model')} className={BTN}>Back to the model</button>
                {nextUnread && <button type="button" onClick={() => navigate(`/review/${nextUnread}`)} className={BTN}>Next unread</button>}
              </>
            ) : (
              <>
                <button type="button" onClick={() => go(index - 1)} disabled={index <= 0} className={BTN}>Previous</button>
                {nothingLeft ? (
                  // The forward control once nothing is waiting: closing the reading is
                  // the reviewer's act, so the echo of what they just wrote stays until
                  // they take it.
                  <button type="button" onClick={() => setClosed(episodeId)} className={BTN}>Finish reading</button>
                ) : (
                  <>
                    <button type="button" onClick={() => go(index + 1)} disabled={index >= list.length - 1} className={BTN}>Next</button>
                    {/* Skip is Next without agreeing to anything — the same move, said out
                        loud, so leaving a card unanswered is a choice and not an accident. */}
                    <button type="button" onClick={() => go(index + 1)} disabled={index >= list.length - 1}
                      className="og-label inline-flex min-h-11 items-center px-3 text-b3 underline underline-offset-4 disabled:text-fg-muted">Skip</button>
                  </>
                )}
                <button type="button" onClick={() => navigate('/model')} className={BTN}>Back to the model</button>
              </>
            )}
          </div>
        </>
      )}

      {!current && !settled && !g1.error && <Loading label="the reading queue" />}
      {g1.error && <ErrorState message={g1.error.message} route={`session/${sessionId}/episode/${episodeId}/g1`} onRetry={g1.refresh} />}
    </div>
  );
}
