// Plan Task 5 Step 6, the two "empty" rows:
//   Empty (nothing yet)  eyebrow + one sentence saying *why* it is empty in lifecycle
//                        terms + the action that would fill it.
//   Empty (by gate)      the literal line "No numbers exist yet. Nothing is computed
//                        before the model is approved." with a link to the Model screen.
// `byGate` selects the second, fixed wording — it is quoted in the plan verbatim and is
// not a place for a screen to write its own variant.
//
// The eyebrow is Instrument Sans 500 (§5: "eyebrow labels are `--og-b3` in Instrument
// Sans 500, not mono caps"), not the mono it was under v1.2 — an eyebrow names a screen,
// it is not an identifier. Callers still choose the eyebrow's own wording; a caller that
// passes a shouted one is shouting, not this component.

import { Link } from 'react-router-dom';

export interface EmptyStateAction {
  label: string;
  to: string;
}

export interface EmptyStateProps {
  eyebrow: string;
  message: string;
  action?: EmptyStateAction;
  byGate?: boolean;
}

export function EmptyState({ eyebrow, message, action, byGate = false }: EmptyStateProps) {
  return (
    // Fluid padding rather than a fixed 32 px: at 360 px a third of the width was frame
    // (§5a, "the gutter is a ceiling, never a fixed value").
    <div className="border border-hairline p-[clamp(16px,5vw,32px)] flex flex-col gap-3">
      <p className="og-label text-b3 text-fg-muted">{eyebrow}</p>
      <p className="text-b2">
        {byGate ? 'No numbers exist yet. Nothing is computed before the model is approved.' : message}
      </p>
      {(action || byGate) && (
        // `inline-flex` + `min-h-11`: §5a's 44 px floor. As a bare inline link this was
        // exempt from the touch-target rule on a technicality rather than compliant
        // with it, and it is the one thing on this panel a visitor is invited to click.
        <Link
          to={action?.to ?? '/model'}
          className="og-label text-b3 inline-flex min-h-11 w-fit items-center underline underline-offset-4"
        >
          {action?.label ?? 'Go to Model'}
        </Link>
      )}
    </div>
  );
}
