// Session bootstrap shared by the screens plan 07 Task 8 builds (Evidence, Timeline,
// Package). Home (Task 6) is the screen that will eventually own "how a session and an
// episode get established" end to end — plan 07 Task 5's own report left that wiring
// point explicitly open ("AppShell takes episode/sessionId as optional props with no
// provider/context wiring them up yet ... not decided here"). Task 8 cannot wait on
// Task 6 (the dispatch order in the ledger runs Task 8 first), so this hook is the
// minimal, honest thing that lets three session-scoped screens work today: it creates
// or resumes exactly one session per browser tab (`sessionStorage`, not `localStorage`
// — a session is a copy of a demo store on this server process; surviving a browser
// restart into a session the server may no longer have would be a worse default than
// starting fresh), lists its episodes, and remembers which one is "current". Nothing
// here computes a decision value; it only remembers ids.
//
// Task 6 took the invitation above: the state now lives in ONE `SessionProvider` at the
// root of the tree (`App.tsx`), and `useSession()` reads it out of context. Nothing in
// the six screens that already call `useSession()` had to change — but they now share a
// single session with each other AND with the shell, which is what makes the header's
// episode line and the authority rail's counters work at all: Home opening Demo A has to
// be visible to `AppShell`, and six independent copies of this state could never agree.
// The `sessionStorage` keys are unchanged, so a tab open across the refactor still
// resolves the same session.
//
// `?session=<id>` (plan 07 Task 9's `docket ui --demo a|b`, which creates the session
// server-side and opens the browser on that URL) is adopted on first mount and then
// stripped from the address bar, so a reload does not keep re-adopting a session the
// visitor may since have left.

import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react';
import { apiGet, apiPost, ApiUnreachable } from './client';
import type { EpisodeView, SessionInfo } from '../types/api';

const SESSION_KEY = 'docket-session-id';
const SESSION_QUERY_PARAM = 'session';
const EPISODE_KEY_PREFIX = 'docket-episode-id:';

export type DemoSource = 'new' | 'demo-a' | 'demo-b';

export interface UseSessionResult {
  sessionId: string | null;
  episodes: EpisodeView[];
  episodeId: string | null;
  episode: EpisodeView | null;
  loading: boolean;
  /** True once the episode read for the current session has produced an answer (or
   * there is no session to read). `loading` alone cannot say this: it is false both
   * before the read starts — the read begins in an effect, a frame after the first
   * render — and after it finishes, and a view that read it alone would state something
   * about a decision it has not read yet, on every hard load and every deep link. It is
   * `false` again while a re-read is in flight, so "settled" always means the answer on
   * screen is this session's. */
  settled: boolean;
  error: Error | null;
  apiAbsent: boolean;
  /** Create a fresh session from `source` ("new", "demo-a" or "demo-b") and make it
   * current. Never reuses an existing session — opening a demo again is the "five
   * copies at an event" case `sessions.py` documents. */
  openSession: (source: DemoSource) => Promise<void>;
  /** Make an already-existing session the current one (Home's list of open sessions —
   * a demo opened five times at an event is five sessions, and switching between them
   * must not create a sixth). Never creates anything. */
  adoptSession: (id: string) => void;
  setEpisodeId: (id: string) => void;
  /** Forget the session on this browser tab without deleting it server-side (a session
   * is cheap and this screen has no "delete" affordance of its own). */
  clearSession: () => void;
  refetch: () => void;
}

function readEpisodeKey(sessionId: string): string {
  return `${EPISODE_KEY_PREFIX}${sessionId}`;
}

/** Highest `sequence` wins — the most recently opened episode in the chain, which is
 * the sensible default for a screen that has not been told otherwise. `sequence` is a
 * kernel-authored integer on every `DecisionEpisode`, never computed here. */
function latestEpisode(episodes: EpisodeView[]): EpisodeView | null {
  if (episodes.length === 0) return null;
  return episodes.reduce((latest, ep) => (ep.sequence > latest.sequence ? ep : latest));
}

/** The session id on the URL (`?session=<id>`), if any, consumed exactly once.
 *
 * `docket ui --demo a` creates the demo session server-side and opens the browser on
 * `/?session=<id>` (see `cli._open_browser_when_healthy`). Reading it here — rather than
 * in Home alone — means the deep link works whatever screen it lands on, and writing it
 * into `sessionStorage` immediately makes it the same "current session" every other
 * screen already agrees on. The parameter is then removed from the address bar with
 * `replaceState`, so it is a one-time hand-off and not a permanent override that would
 * silently undo a later session change on the next reload. */
function adoptSessionFromUrl(): string | null {
  const params = new URLSearchParams(window.location.search);
  const fromUrl = params.get(SESSION_QUERY_PARAM);
  if (!fromUrl) return null;
  sessionStorage.setItem(SESSION_KEY, fromUrl);
  params.delete(SESSION_QUERY_PARAM);
  const query = params.toString();
  window.history.replaceState(
    null,
    '',
    `${window.location.pathname}${query ? `?${query}` : ''}${window.location.hash}`,
  );
  return fromUrl;
}

function useSessionState(): UseSessionResult {
  const [sessionId, setSessionIdState] = useState<string | null>(
    () => adoptSessionFromUrl() ?? sessionStorage.getItem(SESSION_KEY),
  );
  const [episodes, setEpisodes] = useState<EpisodeView[]>([]);
  const [episodeId, setEpisodeIdState] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [settled, setSettled] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const [tick, setTick] = useState(0);

  const refetch = useCallback(() => setTick((t) => t + 1), []);

  useEffect(() => {
    if (!sessionId) {
      setEpisodes([]);
      setEpisodeIdState(null);
      setSettled(true);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setSettled(false);
    apiGet<{ episodes: EpisodeView[] }>(`/session/${sessionId}/episodes`)
      .then((res) => {
        if (cancelled) return;
        setEpisodes(res.episodes);
        setError(null);
        const stored = sessionStorage.getItem(readEpisodeKey(sessionId));
        const resolved =
          (stored && res.episodes.find((ep) => ep.id === stored)) || latestEpisode(res.episodes);
        setEpisodeIdState(resolved?.id ?? null);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        // The stored session id no longer exists on this server (a restart, or a
        // different `DOCKET_STATE_DIR`) — forget it rather than showing a permanent
        // error for a tab nobody can fix by clicking anything.
        sessionStorage.removeItem(SESSION_KEY);
        setSessionIdState(null);
        setEpisodes([]);
        setEpisodeIdState(null);
        setError(err instanceof Error ? err : new Error(String(err)));
      })
      .finally(() => {
        if (cancelled) return;
        setLoading(false);
        setSettled(true);
      });
    return () => {
      cancelled = true;
    };
  }, [sessionId, tick]);

  const openSession = useCallback(async (source: DemoSource) => {
    setLoading(true);
    setError(null);
    try {
      const info = await apiPost<SessionInfo>('/session', { source });
      sessionStorage.setItem(SESSION_KEY, info.id);
      setSessionIdState(info.id);
    } catch (err) {
      setError(err instanceof Error ? err : new Error(String(err)));
      setLoading(false);
    }
  }, []);

  const adoptSession = useCallback((id: string) => {
    sessionStorage.setItem(SESSION_KEY, id);
    setSessionIdState(id);
  }, []);

  const setEpisodeId = useCallback(
    (id: string) => {
      setEpisodeIdState(id);
      if (sessionId) sessionStorage.setItem(readEpisodeKey(sessionId), id);
    },
    [sessionId],
  );

  const clearSession = useCallback(() => {
    if (sessionId) sessionStorage.removeItem(readEpisodeKey(sessionId));
    sessionStorage.removeItem(SESSION_KEY);
    setSessionIdState(null);
    setEpisodes([]);
    setEpisodeIdState(null);
  }, [sessionId]);

  const episode = episodes.find((ep) => ep.id === episodeId) ?? null;

  return {
    sessionId,
    episodes,
    episodeId,
    episode,
    loading,
    settled,
    error,
    apiAbsent: error instanceof ApiUnreachable,
    openSession,
    adoptSession,
    setEpisodeId,
    clearSession,
    refetch,
  };
}


// ---- the single instance every screen and the shell share -----------------------------

const SessionContext = createContext<UseSessionResult | null>(null);

/** Wraps the whole app exactly once (`App.tsx`). Deliberately has no fallback: a
 * `useSession()` outside the provider would silently get its *own* copy of the state,
 * which is the bug this context exists to remove, so it throws instead. */
export function SessionProvider({ children }: { children: ReactNode }) {
  const value = useSessionState();
  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession(): UseSessionResult {
  const ctx = useContext(SessionContext);
  if (!ctx) throw new Error('useSession() used outside <SessionProvider>');
  return ctx;
}
