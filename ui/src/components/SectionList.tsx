// The Package screen's left rail: the 16 `SECTIONS` from `GET /api/sections`
// (`kernel.render.SECTIONS`), never restated by hand — a section added or renamed in
// the renderer shows up here for free instead of a rail that quietly disagrees with the
// document it points into.
//
// §5a's stacked treatment applies here: below 768 px each entry is a label-over-value
// card (the section's key above its title), and at 768 px and up the pair sits on one
// line as a two-column label/value row — the shape the brand's own `.spec` table
// already uses, followed rather than reinvented. The key is worth showing on its own
// line because it is the name the renderer, the API and the anchor all use; the title
// is the sentence a reader recognises.

export interface SectionListSection {
  key: string;
  title: string;
}

export interface SectionListProps {
  sections: SectionListSection[];
  activeKey?: string | null;
  onSelect: (key: string) => void;
}

export function SectionList({ sections, activeKey, onSelect }: SectionListProps) {
  if (sections.length === 0) {
    return <p className="og-label text-b3 text-fg-muted">no sections</p>;
  }
  return (
    <nav aria-label="package sections" className="flex flex-col">
      {sections.map((s) => (
        // `min-h-11` plus `flex items-center`: the type stays its size and the hit area
        // grows to the 44 px floor §5a sets for every interactive target at every width.
        // The active marker is a solid `fg` rule, not an Ember one — §5 spends the one
        // Ember per screen on "a human must act", and "which section am I reading" is
        // not that, so this falls back to shape and tone like every other non-blocking
        // state in the table.
        <button
          key={s.key}
          type="button"
          data-testid="package-section"
          onClick={() => onSelect(s.key)}
          aria-current={activeKey === s.key ? 'true' : undefined}
          className={`flex min-h-11 w-full min-w-0 flex-col justify-center gap-x-3 gap-y-0 py-1 text-left md:flex-row md:items-baseline ${
            activeKey === s.key ? 'text-fg border-l-2 border-fg pl-2 -ml-2' : 'text-fg-secondary'
          }`}
        >
          {/* The section key is an identifier the renderer and the API both use — mono,
              per §5's "object ids, revs, hashes, seeds, states" rule. */}
          <span className="og-mono text-m2 text-fg-muted md:w-24 md:shrink-0 md:truncate">{s.key}</span>
          {/* A section title is fixed document structure ("1. Problem statement (AR
              5-11 ¶4-5b)") from `kernel.render.SECTIONS` — a template's own numbering
              and citation, not a computed value (plan 07 Task 9 Part B found this
              unmarked). It is a sentence, so it is body type, not mono. */}
          <span className="text-b3 min-w-0 break-words" data-num="label">
            {s.title}
          </span>
        </button>
      ))}
    </nav>
  );
}
