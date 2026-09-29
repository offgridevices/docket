import { useEffect, useRef, useState } from 'react';
import { Check, SlidersHorizontal } from 'lucide-react';
import { ICON_PROPS } from '../lib/icons';
import { useFields, type Fields, type FieldSpec } from '../lib/fields';

/** The Fields popover (R20/spec §12): a checkbox per field; the choice persists per list.
 *
 * A view that also renders the fields themselves calls `useFields(list, spec)` for
 * itself and passes the result as `shownOverride`, so one state instance drives both the
 * popover and the cards. Left out, the control owns its own copy — correct for a popover
 * nothing else reads, and wrong the moment a card list reads the same list name, because
 * two `useState`s seeded from storage do not hear each other's writes. */
export function FieldsControl(
  { list, spec, shownOverride }: { list: string; spec: FieldSpec[]; shownOverride?: Fields },
) {
  const own = useFields(list, spec);
  const { shown, toggle } = shownOverride ?? own;
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLSpanElement>(null);
  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => { if (!ref.current?.contains(e.target as Node)) setOpen(false); };
    document.addEventListener('mousedown', onDoc);
    return () => document.removeEventListener('mousedown', onDoc);
  }, [open]);
  return (
    <span ref={ref} className="relative inline-flex" data-fields={list}>
      <button type="button" onClick={() => setOpen((o) => !o)} aria-expanded={open}
        className="og-label text-b3 inline-flex min-h-11 items-center gap-1.5 border border-hairline-strong px-3">
        <SlidersHorizontal {...ICON_PROPS} size={18} aria-hidden /> Fields
      </button>
      {open && (
        <span className="absolute right-0 top-full z-50 mt-1 flex w-[min(280px,calc(100vw-2rem))] flex-col border border-hairline-strong bg-raised p-3">
          {/* Not `<input type="checkbox">` in a 44 px label (this control's own shape
              until Task 20): the native box is 13 px, which is the target a thumb
              actually has to hit, and §5a's floor is 44 px — so every brand walk had to
              close this popover before it ran. It is now the outline control `Activity`
              already uses for a choice, carrying the checkbox role and `aria-checked`,
              so it is still a checkbox to a screen reader and to a spec. Nothing about
              what `useFields` stores changed. */}
          {spec.map((f) => (
            <button
              key={f.key}
              type="button"
              role="checkbox"
              aria-checked={!!shown[f.key]}
              onClick={() => toggle(f.key)}
              className={`og-label text-b3 mb-1.5 inline-flex min-h-11 items-center gap-2 border px-3 text-left ${shown[f.key] ? 'border-hairline-strong text-fg' : 'border-hairline text-fg-muted'}`}
            >
              <Check {...ICON_PROPS} size={16} aria-hidden className={`shrink-0 ${shown[f.key] ? '' : 'invisible'}`} /> {f.label}
            </button>
          ))}
          <span className="text-m1 text-fg-muted">Cards show the minimum by default. Your choice is kept on this browser.</span>
        </span>
      )}
    </span>
  );
}
