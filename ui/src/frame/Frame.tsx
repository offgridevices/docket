import { useEffect, useRef, type ReactNode } from 'react';
import { useLocation } from 'react-router-dom';
import { useSession } from '../api/useSession';
import { useWorkspace } from '../api/useWorkspace';
import { useNeeds } from '../api/useNeeds';
import { useClock } from '../api/useClock';
import { Footer } from '../components/Footer';
import { ChatPanel } from './ChatPanel';
import { ExplainPanel } from './ExplainPanel';
import { Header } from './Header';
import { Overlays } from './Overlays';
import { ProgressMap } from './ProgressMap';
import { StatusRow } from './StatusRow';
import { Toasts } from './Toasts';
import './frame.css';

export function Frame({ children }: { children: ReactNode }) {
  const { sessionId, episodeId, episode } = useSession();
  const { chatCollapsed, chatSheet, overlay } = useWorkspace();
  const needs = useNeeds(sessionId, episodeId);
  const clock = useClock(sessionId, episodeId);
  const location = useLocation();
  const viewRef = useRef<HTMLElement>(null);
  const footRef = useRef<HTMLElement>(null);

  // A new address starts at the top of the view column — unless it names an anchor, in
  // which case that block is what the reader asked for. React Router does not honour a
  // hash (it never touches the scroll position), so without this every `#charter`,
  // `#propose`, `#approve`, `#commit` and `#clock` link in the app — the coverage sheet's
  // Go buttons among them — silently lands at the top of the wrong part of the page.
  // Keyed on the hash as well as the path so a second Go at the same anchor still moves.
  useEffect(() => {
    const view = viewRef.current;
    if (!view) return;
    const id = location.hash.slice(1);
    if (!id) { view.scrollTo({ top: 0 }); return; }
    // After paint: the view for this address has not rendered its anchor yet on the tick
    // the address changes.
    const frame = requestAnimationFrame(() => {
      const target = view.querySelector(`#${CSS.escape(id)}`);
      if (target) target.scrollIntoView({ block: 'start' });
      else view.scrollTo({ top: 0 });
    });
    return () => cancelAnimationFrame(frame);
  }, [location.pathname, location.hash]);
  useEffect(() => {
    const foot = footRef.current;
    if (!foot) return;
    const fit = () => document.documentElement.style.setProperty('--foot-h', `${foot.offsetHeight || 44}px`);
    fit();
    const ro = new ResizeObserver(fit);
    ro.observe(foot);
    return () => ro.disconnect();
  }, []);

  return (
    // `data-overlay` sits on the frame, not only on the canvas: while a sheet is open
    // the Ember comes off the whole page, header and footer included.
    <div className="frame bg-canvas text-fg font-body" data-overlay={overlay ? overlay.kind : undefined}>
      <header className="frame__header flex flex-col border-b border-hairline bg-raised">
        <Header episode={episode} />
        <StatusRow needs={needs.data} clock={clock.data} episodeState={episode?.lifecycleState ?? null} />
      </header>
      <div className="canvas" data-chat={chatCollapsed ? 'collapsed' : 'open'} data-chat-sheet={chatSheet ? 'open' : 'closed'} data-overlay={overlay ? overlay.kind : undefined}>
        <ProgressMap needs={needs.data} episodeState={episode?.lifecycleState ?? null} hasEpisode={!!episode} />
        <main id="view" ref={viewRef} className="view px-[clamp(14px,2.2vw,30px)] py-6" tabIndex={-1}>
          <ExplainPanel />
          {children}
        </main>
        <ChatPanel />
      </div>
      <Footer ref={footRef} />
      <Overlays />
      <Toasts />
    </div>
  );
}
