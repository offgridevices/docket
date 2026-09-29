// Plan Task 5 Step 6: "the panel's hairline frame with an eyebrow reading `loading` —
// never a spinner over an empty page. The frame is the promise that something belongs
// there." Every screen reuses this one component rather than inventing its own.
//
// The default label is sentence case, not the ALL-CAPS the v1.2 build shipped: §5 says
// nothing in the interface is uppercase, and "loading" is a word, not an acronym. The
// eyebrow is Instrument Sans 500 for the same reason every other eyebrow is — it is a
// label, not an identifier. A caller may still pass its own `label`.

export interface LoadingProps {
  label?: string;
}

export function Loading({ label = 'loading' }: LoadingProps) {
  return (
    <div
      className="border border-hairline p-[clamp(16px,5vw,32px)]"
      role="status"
      aria-live="polite"
    >
      <p className="og-label text-b3 text-fg-muted">{label}</p>
    </div>
  );
}
