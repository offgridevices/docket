import type { ReactNode } from 'react';

/** One eyebrow, one heading, one sentence, the view's controls on the right (R22). */
export function ViewHead({ eyebrow, title, sentence, right }: { eyebrow: string; title: string; sentence?: ReactNode; right?: ReactNode }) {
  return (
    <div className="mb-5 flex flex-wrap items-start justify-between gap-3">
      <div className="min-w-0">
        <span className="og-label block text-b3 text-fg-muted">{eyebrow}</span>
        <h1 className="og-display text-[clamp(26px,3.6vw,38px)] leading-tight">{title}</h1>
        {sentence && <p className="mt-1 max-w-[70ch] text-b2 text-fg-secondary">{sentence}</p>}
      </div>
      {/* `ml-auto`, not just `justify-between`: when the controls wrap below a long
          sentence they must stay against the RIGHT edge of the view column. A popover
          that opens `right-0` from a control sitting at the left edge would open off the
          column and land over the map. */}
      {right && <div className="ml-auto flex flex-wrap items-center gap-2">{right}</div>}
    </div>
  );
}
