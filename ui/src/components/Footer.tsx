import { forwardRef } from 'react';
import markInk from '../brand/logo/mark-ink.svg';
import { useWorkspace } from '../api/useWorkspace';

/** One compact row, always visible (R25/R26): the two disclosures, Coverage, the lockup. */
export const Footer = forwardRef<HTMLElement>(function Footer(_props, ref) {
  const { openOverlay } = useWorkspace();
  return (
    <footer ref={ref} className="frame__footer flex min-h-11 flex-wrap items-center gap-x-4 gap-y-1 border-t border-hairline bg-surface px-[clamp(14px,2.2vw,30px)] py-1.5">
      <span className="flex min-w-0 flex-1 basis-80 flex-wrap gap-x-2 text-m1 text-fg-secondary">
        <p>All data here is public. Classification values are schema fields, not markings.</p>
        <span aria-hidden>·</span>
        <p>Single-user demonstration. Not a production authorisation system.</p>
      </span>
      <span className="ml-auto flex items-center gap-4">
        <button type="button" onClick={() => openOverlay({ kind: 'coverage' })} className="og-label min-h-11 text-m1 text-fg-secondary underline underline-offset-4">
          <span className="hide-below-520">Coverage — every control and every requirement</span><span className="only-below-520">Coverage</span>
        </button>
        <span className="inline-flex items-center gap-1.5"><img src={markInk} alt="" width={16} height={16} className="opacity-70" /><span className="og-label text-b3 text-fg-secondary">OffGrid</span></span>
      </span>
    </footer>
  );
});
