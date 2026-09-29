// One dimension's verdict (design spec Screen 6; plan Task 7 Step 4). Prints
// `StandardsAssessment.dimensionVerdicts[dim].verdict` and, when present, its
// `qualifier` sentence — both verbatim: `verdict` is a closed kernel-authored token
// (`generally_objective`, `insufficient_to_conclude`, …) and `qualifier` is a full
// sentence the kernel composed from named question ids (`kernel.standards`'s own
// qualifier text, e.g. "generally reliable, with concerns: EXE-5 (...)") — neither is a
// caption this screen gets to reword or summarise.
//
// The three faces, per §5: the dimension is this card's eyebrow, so it is a label; the
// verdict is a closed token, which is what mono is for; the qualifier is a sentence, so
// it is body type. v1.2 set all three in mono, which left nothing on the card reading as
// an identifier.

export interface VerdictCardProps {
  dimension: string;
  verdict: string;
  qualifier?: string | null;
}

export function VerdictCard({ dimension, verdict, qualifier }: VerdictCardProps) {
  return (
    <div className="border border-hairline p-4 flex flex-col gap-2" data-testid="verdict-card">
      <p className="og-label text-b3 text-fg-muted">{dimension}</p>
      <p className="og-mono text-m1 break-words">{verdict}</p>
      {qualifier && <p className="text-b2 text-fg-secondary">{qualifier}</p>}
    </div>
  );
}
