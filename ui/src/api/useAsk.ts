// Ask about this decision (spec §7), client side.
//
// The whole read surface of the chat: `GET /api/ask/questions` once per page load and
// `POST …/ask` once per send. Nothing here calls `bumpRecord()` and nothing here posts
// anywhere else, because the chat never changes the record — an answer's action button
// navigating is the only way this feature touches the rest of the app.
//
// The thread key is `${sessionId}:${episodeId}`: one decision is one workspace (R2), so
// switching decisions shows that decision's own thread and leaves this one where it was.
// The threads themselves live in `useWorkspace` (in memory, never persisted).
import { useCallback, useEffect, useState } from 'react';
import { apiGet, apiPost, ApiError } from './client';
import { useSession } from './useSession';
import { useWorkspace, type ChatMessage } from './useWorkspace';
import type { AskQuestionsResponse, AskResponse } from '../types/api';

// Module scope, not component state: the nine questions are the server's own constant
// and every mount of the panel would otherwise re-ask for them. The PROMISE is cached,
// not only its result — two consumers mounting in the same tick (the panel and
// `/ask?q=…`'s redirect) would otherwise both find an empty cache and both fetch.
let questionsCache: string[] | null = null;
let questionsInFlight: Promise<string[]> | null = null;

function loadQuestions(): Promise<string[]> {
  if (!questionsInFlight) {
    questionsInFlight = apiGet<AskQuestionsResponse>('/ask/questions')
      .then((r) => { questionsCache = r.questions; return r.questions; })
      // A failed read is not cached: the next mount may as well try again.
      .catch(() => { questionsInFlight = null; return []; });
  }
  return questionsInFlight;
}

/** The one client of `POST …/ask`. Reads the decision; never writes to it. */
export function useAsk() {
  const { sessionId, episodeId } = useSession();
  const { thread, append, sending, setSending } = useWorkspace();
  const [questions, setQuestions] = useState<string[]>(questionsCache ?? []);
  const key = sessionId && episodeId ? `${sessionId}:${episodeId}` : null;
  // One flag per thread, shared by every `useAsk()` on the page — see `useWorkspace`.
  const busy = key ? sending(key) : false;

  useEffect(() => {
    if (questionsCache) return;
    let cancelled = false;
    void loadQuestions().then((qs) => { if (!cancelled) setQuestions(qs); });
    return () => { cancelled = true; };
  }, []);

  const send = useCallback(async (question: string) => {
    const q = question.trim();
    if (!key || !q || sending(key)) return;
    append(key, { who: 'you', text: q });
    setSending(key, true);
    try {
      const r = await apiPost<AskResponse>(`/session/${sessionId}/episode/${episodeId}/ask`, { question: q });
      append(key, { who: 'docket', paragraphs: r.answer.paragraphs, cites: r.answer.cites, actions: r.answer.actions, source: r.source });
    } catch (e) {
      // A refusal is an answer too: it is shown in the thread, in the server's own
      // words, rather than swallowed into a toast the reader has to have been watching.
      append(key, { who: 'docket', paragraphs: [e instanceof ApiError ? (e.body.message ?? e.message) : String(e)], cites: [], actions: [], source: 'error' });
    } finally {
      setSending(key, false);
    }
  }, [key, sessionId, episodeId, append, sending, setSending]);

  return { key, messages: key ? thread(key) : ([] as ChatMessage[]), questions, busy, send };
}
