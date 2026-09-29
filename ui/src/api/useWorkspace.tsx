// Per-decision UI state (spec §3): Explain, the chat's shape, overlays, toasts, the
// in-memory chat threads, and a record version every write bumps so the header
// counters, the map and the clock re-read. Nothing here is a decision value.
import { createContext, useCallback, useContext, useMemo, useRef, useState, type ReactNode } from 'react';

export type Overlay =
  | { kind: 'settings' } | { kind: 'coverage' } | { kind: 'blockers' } | { kind: 'authority' }
  | { kind: 'raw'; id: string } | { kind: 'review'; id: string } | { kind: 'sendback' }
  | { kind: 'sign'; packageHash: string; defaultRole: string };
export type ToastTone = 'done' | 'stop' | 'neutral';
export interface Toast { id: number; text: string; tone: ToastTone }
export interface ChatMessage {
  who: 'you' | 'docket';
  text?: string;
  paragraphs?: string[];
  cites?: string[];
  actions?: { label: string; route: string }[];
  source?: string;
}

export interface Workspace {
  explain: boolean; setExplain: (v: boolean) => void;
  chatCollapsed: boolean; setChatCollapsed: (v: boolean) => void;
  chatSheet: boolean; setChatSheet: (v: boolean) => void;
  overlay: Overlay | null; openOverlay: (o: Overlay) => void; closeOverlay: () => void;
  toasts: Toast[]; toast: (text: string, tone?: ToastTone) => void;
  recordVersion: number; bumpRecord: () => void;
  thread: (key: string) => ChatMessage[]; append: (key: string, m: ChatMessage) => void;
  /** Whether a question is in flight on that thread. The flag belongs to the thread, not
   * to the hook: two `useAsk()` instances can be mounted at once — the chat panel and
   * `/ask?q=…`'s redirect — and both read this one flag, so a second question on the same
   * decision waits for the first to answer instead of racing it. */
  sending: (key: string) => boolean; setSending: (key: string, v: boolean) => void;
}

const Ctx = createContext<Workspace | null>(null);

export function WorkspaceProvider({ children }: { children: ReactNode }) {
  const [explain, setExplain] = useState(false);
  const [chatCollapsed, setChatCollapsed] = useState(false);
  const [chatSheet, setChatSheet] = useState(false);
  const [overlay, setOverlay] = useState<Overlay | null>(null);
  const [toasts, setToasts] = useState<Toast[]>([]);
  const [recordVersion, setRecordVersion] = useState(0);
  const [threads, setThreads] = useState<Record<string, ChatMessage[]>>({});
  const [inFlight, setInFlight] = useState<Record<string, boolean>>({});
  const nextId = useRef(1);

  const toast = useCallback((text: string, tone: ToastTone = 'neutral') => {
    const id = nextId.current++;
    setToasts((t) => [...t, { id, text, tone }]);
    window.setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 4200);
  }, []);
  const bumpRecord = useCallback(() => setRecordVersion((v) => v + 1), []);
  const thread = useCallback((key: string) => threads[key] ?? [], [threads]);
  const append = useCallback((key: string, m: ChatMessage) =>
    setThreads((t) => ({ ...t, [key]: [...(t[key] ?? []), m] })), []);
  const sending = useCallback((key: string) => inFlight[key] ?? false, [inFlight]);
  const setSending = useCallback((key: string, v: boolean) =>
    setInFlight((s) => ({ ...s, [key]: v })), []);
  const closeOverlay = useCallback(() => setOverlay(null), []);

  const value = useMemo<Workspace>(() => ({
    explain, setExplain, chatCollapsed, setChatCollapsed, chatSheet, setChatSheet,
    overlay, openOverlay: setOverlay, closeOverlay,
    toasts, toast, recordVersion, bumpRecord, thread, append, sending, setSending,
  }), [explain, chatCollapsed, chatSheet, overlay, closeOverlay, toasts, toast, recordVersion,
    bumpRecord, thread, append, sending, setSending]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useWorkspace(): Workspace {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error('useWorkspace() used outside <WorkspaceProvider>');
  return ctx;
}
