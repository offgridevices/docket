export type GlyphKind = 'done' | 'needs' | 'doing' | 'later';
const CLASS: Record<GlyphKind, string> = {
  done: 'text-done', needs: 'text-act-text', doing: 'text-wait', later: 'text-fg-muted',
};
/** The map's state glyph (R1/R24): done = filled square with a tick, needs you = solid
 * square, in progress = half square, not yet = hollow. Colour on the glyph only. */
export function StateGlyph({ kind }: { kind: GlyphKind }) {
  return (
    <svg width={14} height={14} viewBox="0 0 14 14" aria-hidden className={`shrink-0 ${CLASS[kind]}`} data-glyph={kind}>
      {kind === 'done' && (<><rect x="0.5" y="0.5" width="13" height="13" fill="currentColor" /><path d="M3.5 7.2 6 9.6 10.6 4.4" fill="none" stroke="var(--og-bg)" strokeWidth="1.6" /></>)}
      {kind === 'needs' && <rect x="0.5" y="0.5" width="13" height="13" fill="currentColor" />}
      {kind === 'doing' && (<><rect x="0.5" y="0.5" width="13" height="13" fill="none" stroke="currentColor" /><path d="M1 13 13 1 13 13z" fill="currentColor" /></>)}
      {kind === 'later' && <rect x="0.5" y="0.5" width="13" height="13" fill="none" stroke="currentColor" />}
    </svg>
  );
}
