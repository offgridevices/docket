import { useState, type FormEvent } from 'react';
import { ChevronRight, MessageSquare, X } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { useAsk } from '../api/useAsk';
import { useAuthority } from '../api/useAuthority';
import { useSession } from '../api/useSession';
import { useWorkspace } from '../api/useWorkspace';
import { IdChip } from '../components/IdChip';
import { Num } from '../components/Num';
import { ICON_PROPS } from '../lib/icons';

/** After three exchanges the nine suggestions are in the way rather than in the
 * offer; the `Suggestions` link brings them back. */
const CHIPS_UNTIL = 6;

export function ChatPanel() {
  const { sessionId, episodeId } = useSession();
  const { chatCollapsed, setChatCollapsed, setChatSheet, openOverlay, explain } = useWorkspace();
  const { key, messages, questions, busy, send } = useAsk();
  // Until a decision and an episode are both open there is nothing to ask about, and a
  // chip that answered a click with silence would be a lie about what it does.
  const ready = !!key;
  const navigate = useNavigate();
  const [draft, setDraft] = useState('');
  // "the reader asked for them back", not "they are on": starting it true would keep the
  // row up for ever and the length rule below would never fire.
  const [restored, setRestored] = useState(false);
  const chips = restored || messages.length <= CHIPS_UNTIL;
  // An answer's actions navigate — except the fallback's own chips, which the server
  // writes as `/ask?q=<the question>` because it has no other way to say "ask this one".
  const act = (route: string) => {
    if (route.startsWith('/ask?q=')) { void send(decodeURIComponent(route.slice('/ask?q='.length))); return; }
    navigate(route);
  };
  // The guard comes BEFORE the draft is cleared: `send` declines while an answer is in
  // flight, and clearing first would throw away what the reader had typed.
  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (!ready || busy || !draft.trim()) return;
    const q = draft;
    setDraft('');
    void send(q);
  };
  const authority = useAuthority(sessionId, episodeId);
  const model = authority.data?.numerals.agent ?? 0;
  const kernel = authority.data?.numerals.kernel ?? 0;
  const from = episodeId ?? 'authority';
  return (
    <aside className="chat flex flex-col border-l border-hairline bg-raised" aria-label="Ask about this decision">
      {chatCollapsed ? (
        <button type="button" onClick={() => setChatCollapsed(false)} aria-label="Open the chat"
          className="hide-below-1024 flex min-h-11 flex-col items-center gap-2 px-1 py-3 text-m1">
          <MessageSquare {...ICON_PROPS} size={20} aria-hidden /><span style={{ writingMode: 'vertical-rl' }}>Ask about this decision</span>
        </button>
      ) : (
        <>
          <div className="flex-none border-b border-hairline p-3">
            <div className="flex items-center justify-between gap-2">
              <h2 className="og-display text-b1">Ask about this decision</h2>
              <span className="flex">
                <button type="button" onClick={() => setChatCollapsed(true)} aria-label="Collapse the chat" className="hide-below-1024 inline-flex min-h-11 min-w-11 items-center justify-center"><ChevronRight {...ICON_PROPS} size={20} aria-hidden /></button>
                <button type="button" onClick={() => setChatSheet(false)} aria-label="Close the chat" className="inline-flex min-h-11 min-w-11 items-center justify-center"><X {...ICON_PROPS} size={20} aria-hidden /></button>
              </span>
            </div>
            <p className="mt-1 text-m1 text-fg-secondary">Reads this decision. Never writes to it.</p>
            <button type="button" onClick={() => openOverlay({ kind: 'authority' })} title="Who is allowed to write what"
              className="og-mono text-m2 mt-2 inline-flex min-h-11 items-center gap-1 border border-hairline-strong bg-canvas px-2" data-testid="authority-counters">
              numbers authored by model <Num value={model} from={from} /> · by kernel <Num value={kernel} from={from} />
            </button>
          </div>
          {/* The thread scrolls; the composer under it does not. Both sit inside
              `[data-chat-body]` — the body is the panel below its header, and a reader
              who has scrolled up a long thread still has somewhere to type. */}
          <div className="flex min-h-0 flex-1 flex-col" data-chat-body>
            <div className="flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto p-3">
              {messages.length === 0 && (
                <p className="text-m1 text-fg-muted">Ask anything about this decision. The answers are read out of the record, with the object ids they came from, and every one ends in a button that takes you there.</p>
              )}
              {messages.map((m, i) => (
                // `data-num="label"` on every line of an answer: each numeral inside one
                // is a value copied out of a cited object by the server (§7), not a sum
                // this panel worked out.
                <div key={i} className={`text-b3 ${m.who === 'you' ? 'self-end border border-hairline-strong bg-canvas px-3 py-2' : 'border border-dashed border-ai-line bg-ai-tint px-3 py-2'}`} data-chat-message data-who={m.who} data-source={m.source}>
                  {m.text && <p data-num="label">{m.text}</p>}
                  {m.paragraphs?.map((p, j) => <p key={j} className="mb-1" data-num="label">{p}</p>)}
                  {m.cites && m.cites.length > 0 && (
                    <p className="mt-1 flex flex-wrap gap-1">
                      {m.cites.map((id) => <span key={id} data-cite><IdChip id={id} onOpen={() => openOverlay({ kind: 'raw', id })} /></span>)}
                    </p>
                  )}
                  {m.actions && m.actions.length > 0 && (
                    <p className="mt-2 flex flex-wrap gap-1">
                      {m.actions.map((a) => (
                        <button key={a.route + a.label} type="button" onClick={() => act(a.route)} data-chat-action
                          className="og-label inline-flex min-h-11 items-center border border-hairline-strong bg-canvas px-2 text-b3">{a.label}</button>
                      ))}
                    </p>
                  )}
                  {explain && m.source && <p className="og-mono mt-1 text-m2 text-fg-muted">source: {m.source}</p>}
                </div>
              ))}
              {busy && <p className="text-b3 text-fg-muted">reading the record…</p>}
              {chips ? (
                <div className="flex flex-wrap gap-1">
                  {questions.map((q) => (
                    <button key={q} type="button" onClick={() => void send(q)} disabled={!ready || busy} data-chat-chip
                      className="og-label inline-flex min-h-11 items-center border border-hairline px-2 text-b3">{q}</button>
                  ))}
                </div>
              ) : (
                <button type="button" onClick={() => setRestored(true)}
                  className="og-label inline-flex min-h-11 items-center self-start text-b3 underline underline-offset-4">Suggestions</button>
              )}
            </div>
            <form onSubmit={submit} className="flex-none border-t border-hairline p-3">
              <textarea aria-label="Ask about this decision" rows={2} value={draft} onChange={(e) => setDraft(e.target.value)} disabled={!ready || busy}
                onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); submit(e); } }}
                className="w-full border border-hairline-strong bg-canvas p-2 text-b2" placeholder="Ask in your own words" />
              <div className="mt-2 flex items-center justify-between gap-2">
                <span className="text-m1 text-fg-muted">Answers cite object ids; every number is copied from the record.</span>
                {/* Bordered, never Ember: the one lit act on a screen belongs to the
                    record, and asking a question changes nothing. */}
                <button type="submit" disabled={!ready || busy || !draft.trim()}
                  className="og-label inline-flex min-h-11 flex-none items-center border border-hairline-strong px-3 text-b3">Ask</button>
              </div>
            </form>
          </div>
        </>
      )}
    </aside>
  );
}
