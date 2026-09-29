// One overlay shell: a wash, a panel, a close control, Escape and backdrop close — and
// the focus contract `aria-modal="true"` promises. A dialog that claims to be modal
// while the keyboard is still walking the page behind it is worse than no dialog at all:
// it tells assistive technology the rest of the page is inert and then leaves it live.
// Focus moves into the panel on open, Tab and Shift+Tab cycle inside it, and the control
// that opened it gets focus back on close. Every later sheet inherits this.
import { useEffect, useRef, type ReactNode } from 'react';
import { X } from 'lucide-react';
import { ICON_PROPS } from '../lib/icons';

const FOCUSABLE =
  'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

export function Sheet({ title, onClose, children, centre = false }: { title: string; onClose: () => void; children: ReactNode; centre?: boolean }) {
  const panelRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const panel = panelRef.current;
    const opener = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const inside = () => Array.from(panel?.querySelectorAll<HTMLElement>(FOCUSABLE) ?? [])
      .filter((el) => el.getClientRects().length > 0);
    (inside()[0] ?? panel)?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') { onClose(); return; }
      if (e.key !== 'Tab' || !panel) return;
      const stops = inside();
      if (stops.length === 0) { e.preventDefault(); panel.focus(); return; }
      const first = stops[0];
      const last = stops[stops.length - 1];
      const here = document.activeElement;
      const away = !(here instanceof Node) || !panel.contains(here);
      if (e.shiftKey && (away || here === first)) { e.preventDefault(); last.focus(); }
      else if (!e.shiftKey && (away || here === last)) { e.preventDefault(); first.focus(); }
    };
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('keydown', onKey);
      // Only if it is still on the page — the opener may have been a row the sheet's own
      // action navigated away from.
      if (opener?.isConnected) opener.focus();
    };
  }, [onClose]);
  return (
    <div className="fixed inset-0 z-[80] flex bg-canvas/80" onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div ref={panelRef} role="dialog" aria-modal="true" aria-label={title} tabIndex={-1}
        className={`flex max-h-full flex-col overflow-y-auto border-hairline-strong bg-canvas ${centre ? 'm-auto w-[min(880px,calc(100%-2rem))] max-h-[92vh] border' : 'ml-auto h-full w-[min(720px,100%)] border-l'}`}>
        <div className="sticky top-0 flex items-center justify-between gap-3 border-b border-hairline bg-raised px-4 py-3">
          <strong className="og-label text-b2">{title}</strong>
          <button type="button" onClick={onClose} aria-label="Close" className="inline-flex min-h-11 min-w-11 items-center justify-center"><X {...ICON_PROPS} size={20} aria-hidden /></button>
        </div>
        <div className="p-4">{children}</div>
      </div>
    </div>
  );
}
