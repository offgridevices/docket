// The two reads the G1 board is built on (plan 07 Task 6, Step 1), each returning
// `{data, error, loading, refresh}`.
//
// They are two hooks and not one because they answer two different questions about the
// same episode — "what is in the model" (`g1_review`) and "where does the episode stand
// at the gate" (`episode_view`, which carries the gate ladder and the transition
// history, including refused attempts). The plan's rule for every mutating action on
// that screen is to call BOTH `refresh()`es: an accept changes the object *and* the
// ladder, and a stale ladder is the one thing this screen may not show — a reviewer who
// confirms a gap and still sees `gaps-confirmed` unsatisfied cannot tell whether the
// write failed or the screen is lying.
//
// Neither hook polls. The record only changes when this browser changes it, and a timer
// re-fetching a review sheet under a reviewer's cursor is a worse failure than a manual
// refresh: the dialog states what it is about to do, and the answer must still be the
// one the reviewer read.

import type { EpisodeView, G1Review } from '../types/api';
import { useFetched, type Fetched } from './useFetched';
import { useWorkspace } from './useWorkspace';

// `Fetched` and `useFetched` were defined here until the workspace hooks needed the same
// one GET; they live in ./useFetched.ts now. Re-exported so the screens that already
// import the type from this module keep working.
export type { Fetched };

/** `GET /api/session/{s}/episode/{e}/g1` — `agent.review.g1_review` verbatim.
 *
 * Re-read after every write (`recordVersion`), the same way `useNeeds` is: an accept, a
 * gap confirmation or an approval changes what this sheet says, and a caller that had to
 * remember to call `refresh()` from every place a write can happen — including an
 * overlay it does not own — is a stale checklist waiting to happen. */
export function useG1(sessionId: string | null, episodeId: string | null): Fetched<G1Review> {
  const { recordVersion } = useWorkspace();
  return useFetched<G1Review>(
    sessionId && episodeId ? `/session/${sessionId}/episode/${episodeId}/g1` : null,
    [recordVersion],
  );
}

/** `GET /api/session/{s}/episode/{e}` — `serialize.episode_view`: the episode, its gate
 * ladder and its transition history. Distinct from `useSession().episode`, which is the
 * same shape but refreshed only when the *session's* episode list is re-read; the G1
 * board needs the ladder to re-evaluate after every single write. */
export function useEpisode(
  sessionId: string | null,
  episodeId: string | null,
): Fetched<EpisodeView> {
  const { recordVersion } = useWorkspace();
  return useFetched<EpisodeView>(
    sessionId && episodeId ? `/session/${sessionId}/episode/${episodeId}` : null,
    [recordVersion],
  );
}
