// One object's review subject and its actions, built for whatever is about to draw the
// card — the reading queue, `/review/:objectId`, or the dialog over the board. Written
// once here because all three want the same three rules, and two hand-rolled copies of
// them had already drifted apart:
//
//   1. The bundle belongs to an id AND to an episode. A sheet that has not caught up with
//      the decision the header now shows must never be used to build a card: `useFetched`
//      keeps the previous path's data while the next read is in flight, so "the data
//      arrived" and "the data is about this episode" are different facts and only the
//      second one may be acted on. Anything held from a previous episode is not returned.
//   2. A rebuild that finds NOTHING after a card has been shown is the ordinary
//      consequence of a Reject — the id is dropped from the episode, so the sheet stops
//      listing it. The card stays up with its "Exclusion written" echo until the reviewer
//      moves on; it must not vanish under their hand.
//   3. An id that was never on the sheet is `absent`: a fact to state, never a blank.
import { useEffect, useState } from 'react';
import { buildReview, type ReviewBundle } from '../lib/reviewSubject';
import type { G1Review } from '../types/api';

/** The card to draw, if any, and whether the id is on no sheet this decision reaches.
 * `absent` is never true while there is a bundle: a rejected object is not a missing one. */
export interface ReviewBundleState {
  bundle: ReviewBundle | null;
  absent: boolean;
}

interface Held {
  sessionId: string;
  episodeId: string;
  objectId: string;
}

/** Build the review bundle for `objectId` off `review`, the G1 sheet already in hand
 * (this makes one `GET …/object/{id}` for the stored object; it never re-reads the
 * sheet). `null` for `objectId` — nothing is open — holds nothing. */
export function useReviewBundle(
  sessionId: string | null,
  episodeId: string | null,
  objectId: string | null,
  review: G1Review | null,
): ReviewBundleState {
  const [held, setHeld] = useState<(Held & { bundle: ReviewBundle }) | null>(null);
  const [missing, setMissing] = useState<Held | null>(null);
  // The sheet in hand has to be THIS episode's, or the card would be built out of the
  // objects of the decision the reviewer just left.
  const sheet = review && review.episode === episodeId ? review : null;

  useEffect(() => {
    if (!sessionId || !episodeId || !objectId || !sheet) return;
    let cancelled = false;
    buildReview(sessionId, episodeId, objectId, sheet).then((b) => {
      if (cancelled) return;
      const at = { sessionId, episodeId, objectId };
      if (b) { setHeld({ ...at, bundle: b }); setMissing(null); } else setMissing(at);
    });
    return () => { cancelled = true; };
  }, [sessionId, episodeId, objectId, sheet]);

  // Compared on the way OUT rather than cleared on the way in: a bundle held for another
  // id, episode or session is simply not this card, and deciding that during render means
  // there is never a frame in which the wrong card is on screen.
  const at = (h: Held | null) =>
    !!h && h.sessionId === sessionId && h.episodeId === episodeId && h.objectId === objectId;
  const bundle = at(held) ? held!.bundle : null;
  return { bundle, absent: !bundle && at(missing) };
}
