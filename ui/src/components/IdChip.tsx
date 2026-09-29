// A bare object id, as a chip that opens the stored object.
//
// Not `ObjectChip`: that one is the G1 sheet's card and needs a type, a one-line summary
// and an authorship line to say anything at all. What a blocker, an activity row or a
// chat citation has is an id and nothing else, and inventing the rest would be writing a
// claim the caller never made. So this is the whole component: the id, a hairline, and a
// way in to the record behind it.

/** A bare object id as a chip that opens the stored object. An id is an identifier,
 * not a value, so the numeral walk's label carve-out applies. */
export function IdChip({ id, onOpen }: { id: string; onOpen: () => void }) {
  return (
    // 44px (§5a), not the 32px this chip was first drawn at: it is a target, and a
    // target is 44px at every width. The type inside keeps its size — only the box grows.
    <button
      type="button"
      onClick={onOpen}
      className="og-mono inline-flex min-h-11 min-w-11 items-center justify-center border border-hairline px-1.5 text-m2 text-fg-secondary"
      data-id-chip={id}
      data-num="label"
    >
      {id}
    </button>
  );
}
