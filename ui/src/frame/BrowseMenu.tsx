import { useEffect, useRef, useState, type KeyboardEvent as ReactKeyboardEvent } from 'react';
import { ChevronRight, HelpCircle, List } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { useWorkspace } from '../api/useWorkspace';
import { ICON_PROPS } from '../lib/icons';
import { VIEWS } from '../routes';

/**
 * A flat list of every view, nothing nested (R11/R21), plus the Explain toggle so a
 * phone can reach it.
 *
 * `role="menu"` is a keyboard contract, not a label: opening moves focus to the first
 * item, Up/Down walk the list and wrap, Home/End jump to its ends, and Escape closes and
 * hands focus back to the trigger. Without that, the role tells a screen-reader user
 * they are in a menu and then leaves them tabbing through the page behind it.
 */
export function BrowseMenu() {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLSpanElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const itemsRef = useRef<(HTMLButtonElement | null)[]>([]);
  const navigate = useNavigate();
  const { explain, setExplain } = useWorkspace();

  /** Close, and put the keyboard back where it came from. */
  function close(restoreFocus = true) {
    setOpen(false);
    if (restoreFocus) triggerRef.current?.focus();
  }

  useEffect(() => {
    if (!open) { itemsRef.current = []; return; }
    itemsRef.current[0]?.focus();
    const onDoc = (e: MouseEvent) => { if (!ref.current?.contains(e.target as Node)) setOpen(false); };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') { setOpen(false); triggerRef.current?.focus(); }
    };
    document.addEventListener('mousedown', onDoc); document.addEventListener('keydown', onKey);
    return () => { document.removeEventListener('mousedown', onDoc); document.removeEventListener('keydown', onKey); };
  }, [open]);

  function onMenuKeyDown(e: ReactKeyboardEvent<HTMLDivElement>) {
    const items = itemsRef.current.filter((el): el is HTMLButtonElement => el !== null);
    if (items.length === 0) return;
    const here = items.indexOf(document.activeElement as HTMLButtonElement);
    const go = (i: number) => { e.preventDefault(); items[(i + items.length) % items.length].focus(); };
    if (e.key === 'ArrowDown') go(here + 1);
    else if (e.key === 'ArrowUp') go(here - 1);
    else if (e.key === 'Home') go(0);
    else if (e.key === 'End') go(items.length - 1);
  }

  const item = 'flex min-h-11 w-full items-center justify-between gap-3 px-2.5 text-left text-b3 hover:bg-surface';
  return (
    <span ref={ref} className="relative">
      {/* `aria-label`, so the button answers to the same name once the words come off
          to make room below 1280. */}
      <button ref={triggerRef} type="button" onClick={() => setOpen((o) => !o)} aria-expanded={open} aria-haspopup="menu"
        aria-label="Browse the record" title="Every view of the record"
        className="inline-flex min-h-11 min-w-11 items-center gap-1.5 px-2 og-label text-b3 border border-transparent hover:border-hairline-strong">
        <List {...ICON_PROPS} size={20} aria-hidden /><span className="hide-below-1280">Browse the record</span>
      </button>
      {open && (
        <div role="menu" aria-label="Every view of the record" onKeyDown={onMenuKeyDown}
          className="absolute right-0 top-full z-[70] mt-1 w-[min(320px,calc(100vw-2rem))] border border-hairline-strong bg-raised p-2">
          <span className="og-label block px-2.5 py-1 text-b3 text-fg-muted">every view, flat — nothing is nested</span>
          {VIEWS.map((v, i) => (
            <button key={v.key} role="menuitem" type="button" className={item}
              ref={(el) => { itemsRef.current[i] = el; }}
              onClick={() => { close(false); navigate(v.path); }}>
              {v.label}<ChevronRight {...ICON_PROPS} size={18} aria-hidden />
            </button>
          ))}
          <span className="og-label block px-2.5 py-1 text-b3 text-fg-muted">reading</span>
          <button role="menuitem" type="button" className={item} aria-pressed={explain}
            ref={(el) => { itemsRef.current[VIEWS.length] = el; }}
            onClick={() => { setExplain(!explain); close(); }}>
            {explain ? "Hide the record's own terms" : "Show the record's own terms beside every label"}<HelpCircle {...ICON_PROPS} size={18} aria-hidden />
          </button>
        </div>
      )}
    </span>
  );
}
