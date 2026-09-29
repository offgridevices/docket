// `/ask?q=…` — the fallback answer's own chips route here (the server percent-encodes
// each suggested question into the route), and so does any pasted link. It is not a
// view: it opens the chat, asks the question once and hands the reader back to Home.
import { useEffect, useRef } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useAsk } from '../api/useAsk';
import { useWorkspace } from '../api/useWorkspace';

export function AskRedirect() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const { send, key } = useAsk();
  const { setChatCollapsed, setChatSheet } = useWorkspace();
  // Once, even under StrictMode's deliberate double effect — and `send` changes identity
  // the moment it sets `busy`, which re-runs this effect a second time on its own.
  const asked = useRef(false);
  useEffect(() => {
    if (asked.current) return;
    const q = params.get('q')?.trim();
    // No question to ask is not a screen: `/ask` on its own, or with an empty `q`, has
    // nothing to wait for and would otherwise sit on a blank view for ever.
    if (!q) { asked.current = true; navigate('/', { replace: true }); return; }
    // A session, on the other hand, is worth waiting a beat for: a hard load resolves
    // one an instant after this first runs.
    if (!key) return;
    asked.current = true;
    // Below 1024 the chat is a bottom sheet; above it, a column that may be collapsed.
    if (window.innerWidth < 1024) setChatSheet(true); else setChatCollapsed(false);
    void send(q);
    navigate('/', { replace: true });
  }, [key, params, send, navigate, setChatCollapsed, setChatSheet]);
  return null;
}
