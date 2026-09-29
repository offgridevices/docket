// The review card's third home: a modal over whatever view is behind it (design spec §4;
// plan 07 Task 6, thinned in Task 11).
//
// Everything a reader looks at — the six regions, the editable fields, the confirm step,
// the recorded echo — is `ReviewCard`, which the reading queue and `/review/:objectId`
// render too. What is left here is only what being a MODAL means: the wash over the
// board, the close control, Escape, a click on the backdrop, the Tab trap that keeps a
// keyboard user inside the panel while it is open, and handing focus back to whatever
// opened it. `data-review-dialog` and `data-kind` stay on the outer element, so the
// existing contracts (`[data-review-dialog] [data-region]`, `[data-state="recorded"]`,
// the close button's `close review` label) still resolve — the card is inside the dialog.
//
// It is a `div` with `role="dialog"` and not a native `<dialog>`: the app's Ember rule is
// painted through `.frame[data-overlay]` (`frame/frame.css`), the panel is screenshot by
// its position in the tree, and a top-layer element would take both out of the cascade
// this app already tests. The behaviour a native dialog would bring — modality, Escape,
// focus containment — is implemented here and asserted by the specs.
//
// The types live with the card. They are re-exported so the callers that already import
// them from this module (`lib/reviewSubject.ts` and everything it feeds) keep working.

import { useEffect, useRef, type KeyboardEvent, type MouseEvent } from 'react';
import { X } from 'lucide-react';
import { ICON_PROPS } from '../lib/icons';
import { FOCUSABLE_SELECTOR, ReviewCard, type ReviewAction, type ReviewResult, type ReviewSubject } from './ReviewCard';

export type { CharterField, ReviewAction, ReviewKind, ReviewResult, ReviewSubject } from './ReviewCard';

export interface ReviewDialogProps {
  subject: ReviewSubject;
  actions: ReviewAction[];
  onDone: (result: ReviewResult) => void;
  onClose: () => void;
  /** Opens the raw-object drawer — the one place this object's full JSON, and the
   * extractor that produced it, are allowed to appear. */
  onOpenRaw?: () => void;
}

export function ReviewDialog({ subject, actions, onDone, onClose, onOpenRaw }: ReviewDialogProps) {
  const panelRef = useRef<HTMLDivElement>(null);
  // [ruling I2, plan 07 T6 fix round] Whatever had focus when this dialog opened, so it
  // can be given back on close — whether that is a Close click, an Escape, a backdrop
  // click or a completed action. Captured during the FIRST RENDER and not in an effect:
  // the card focuses its own first control in its mount effect, and a child's effect runs
  // before its parent's, so an effect here would record the control inside the dialog as
  // "the opener" and never return the keyboard to the board.
  const opener = useRef<Element | null>(null);
  if (opener.current === null) opener.current = document.activeElement;
  useEffect(() => () => {
    if (opener.current instanceof HTMLElement) opener.current.focus();
  }, []);

  function handleKeyDown(e: KeyboardEvent<HTMLDivElement>) {
    if (e.key === 'Escape') {
      e.stopPropagation();
      onClose();
      return;
    }
    if (e.key !== 'Tab') return;
    // Trap: Tab and Shift+Tab cycle within the panel's own focusable elements, so a
    // keyboard user can never Tab past this dialog into the board behind it while it is
    // open — the probe that failed before this fix ("fourteen consecutive Tab presses
    // never enter the dialog") described the opposite defect (focus stuck OUTSIDE); this
    // is the same fix, holding focus IN.
    const panel = panelRef.current;
    if (!panel) return;
    const focusable = Array.from(panel.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR));
    if (focusable.length === 0) return;
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (e.shiftKey && document.activeElement === first) {
      e.preventDefault();
      last.focus();
    } else if (!e.shiftKey && document.activeElement === last) {
      e.preventDefault();
      first.focus();
    }
  }

  /** A click on the overlay itself (never one that bubbled up from inside the panel)
   * closes the dialog — the same "click outside" convention every other slide-over/modal
   * in the app should follow. */
  function handleBackdropClick(e: MouseEvent<HTMLDivElement>) {
    if (e.target === e.currentTarget) onClose();
  }

  return (
    <div
      className="fixed inset-0 z-40 flex items-start justify-center overflow-y-auto bg-canvas/80 p-0 md:p-6"
      role="dialog"
      aria-modal="true"
      aria-label={`review ${subject.id}`}
      data-review-dialog
      data-kind={subject.kind}
      onClick={handleBackdropClick}
      onKeyDown={handleKeyDown}
    >
      <div
        ref={panelRef}
        tabIndex={-1}
        className="relative min-h-full w-full og-bg-sunken border-hairline-strong p-3 flex flex-col gap-2 md:min-h-0 md:max-w-2xl md:border"
      >
        <div className="flex justify-end">
          <button
            type="button"
            onClick={onClose}
            aria-label="close review"
            className="inline-flex min-h-11 min-w-11 items-center justify-center text-fg-muted"
          >
            {/* Smaller than the spec's 24px default: a small close control in a corner.
                The glyph is 20px; the hit area around it is 44px (§5a). */}
            <X {...ICON_PROPS} size={20} aria-hidden />
          </button>
        </div>
        <ReviewCard subject={subject} actions={actions} onDone={onDone} onOpenRaw={onOpenRaw} autoFocus />
      </div>
    </div>
  );
}
