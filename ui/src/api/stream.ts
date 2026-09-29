// SSE client for `GET /api/stream/{session}` (plan Task 3 / design spec §6). The server
// is a hand-rolled `StreamingResponse`, not `EventSource`-flavoured multiplexed channels,
// so this wraps the browser's native `EventSource` and dispatches on the fixed event
// names the spec defines: `stage`, `object`, `finding`, `done`, `error`. No screen in
// Task 5 opens a stream yet (Intake, Plan and Compute do, from Task 6 onward) — this
// module exists now so those tasks share one implementation instead of each hand-rolling
// `EventSource` wiring.

import { API_BASE } from './client';
import type { StreamEvent } from '../types/api';

export type StreamHandler = (event: StreamEvent) => void;

const EVENT_NAMES = ['stage', 'object', 'finding', 'done', 'error'] as const;

export interface StreamOptions {
  /** Fired once the browser has actually established the connection.
   *
   * A plain `GET /api/stream/{s}` is a *live* subscription: nothing that happened before
   * the socket opened is replayed [T3 ruling I2]. `POST /elicit` publishes its whole
   * burst of `object` events synchronously while the request is still in flight, so a
   * caller that opens the stream and POSTs in the same tick can miss all of them —
   * `EventSource` connects asynchronously. Callers that need every event wait for this
   * before making the call that produces them (plan 07 Task 6's Intake screen). */
  onOpen?: () => void;
  /** Replay every ring event after this sequence number before going live. Omitted is
   * "live only". */
  since?: number;
}

/** Opens one SSE connection for `sessionId` and calls `onEvent` for every message,
 * tagged with the SSE event name it arrived under. Returns a cleanup function that
 * closes the connection — call it from a `useEffect` cleanup so navigating away from a
 * streaming screen doesn't leave a socket open against a session nobody is looking at. */
export function openStream(
  sessionId: string,
  onEvent: StreamHandler,
  options: StreamOptions = {},
): () => void {
  const query = options.since === undefined ? '' : `?since=${options.since}`;
  const source = new EventSource(`${API_BASE}/stream/${encodeURIComponent(sessionId)}${query}`);
  if (options.onOpen) source.onopen = options.onOpen;

  const listeners = EVENT_NAMES.map((name) => {
    const listener = (raw: MessageEvent<string>) => {
      try {
        const data = JSON.parse(raw.data);
        onEvent({ event: name, data } as StreamEvent);
      } catch (err) {
        onEvent({ event: 'error', data: { error: 'bad-event', message: String(err) } });
      }
    };
    source.addEventListener(name, listener);
    return { name, listener };
  });

  source.onerror = () => {
    onEvent({ event: 'error', data: { error: 'stream-error', message: 'the event stream closed unexpectedly' } });
  };

  return () => {
    for (const { name, listener } of listeners) source.removeEventListener(name, listener);
    source.close();
  };
}
