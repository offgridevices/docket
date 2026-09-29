export const COLOUR_KEY: [string, string, string][] = [
  ['act', 'bg-act-tint border-act', 'the act to do next'],
  ['stop', 'bg-stop-tint border-stop', 'stops progress · refused · overdue'],
  ['wait', 'bg-wait-tint border-wait', 'in progress · waiting · time running low'],
  ['done', 'bg-done-tint border-done', 'done · passed · agreed by a person'],
  ['ai', 'bg-ai-tint border-ai border-dashed', 'drafted by the AI, not yet agreed'],
];
/** The five-line key (R24): printed at the foot of the map, in the Explain panel and
 * in the Coverage sheet. */
export function ColourKey({ compact = false }: { compact?: boolean }) {
  return (
    <ul className="flex flex-col gap-1" data-colour-key>
      {COLOUR_KEY.map(([k, cls, text]) => (
        <li key={k} className={`flex items-center gap-2 text-fg-secondary ${compact ? 'text-m2' : 'text-m1'}`}>
          <span aria-hidden className={`inline-block h-2.5 w-2.5 shrink-0 border ${cls}`} />
          {text}
        </li>
      ))}
    </ul>
  );
}
