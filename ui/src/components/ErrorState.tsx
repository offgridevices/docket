// Plan Task 5 Step 6, the last two rows of the loading/empty/error table:
//   Error     the error's own words, the route that produced it, and a rotate-ccw
//             retry — never a toast, never a generic apology.
//   Refused   octagon-alert in Ember, the unsatisfied check names in mono, and the
//             sentence "The gate refused and the refusal is now part of the record."
// One component, `kind` picks the row, because both are "here is what the record now
// says" rather than a transient notification — the distinction the plan draws against
// toasts.
//
// Type roles under v3.0 (§5). The check names (`gaps-confirmed`) and the route
// (`session/…/g1`) are identifiers, so they keep mono. The message itself does not: an
// error message is a sentence, and §5 is explicit that a string which is neither a
// number nor an identifier nor code is not mono. It is still printed verbatim — that
// was always the promise, and the typeface was never what kept it.
//
// The Ember here is a glyph colour, not a fill, so it cannot spend a screen's single
// Ember plane (§5's precedence rule): a refusal is exactly the "most severe blocking
// finding" the rule contemplates, but the screen that owns the refusal is the one
// entitled to decide whether it also carries the filled element.

import { OctagonAlert, RotateCcw } from 'lucide-react';
import { ICON_PROPS } from '../lib/icons';

export interface ErrorStateProps {
  message: string;
  route?: string;
  onRetry?: () => void;
  kind?: 'error' | 'refused';
  unsatisfied?: string[];
}

export function ErrorState({ message, route, onRetry, kind = 'error', unsatisfied = [] }: ErrorStateProps) {
  if (kind === 'refused') {
    return (
      <div
        className="border border-hairline p-[clamp(16px,5vw,32px)] flex flex-col gap-3"
        data-state="refused"
      >
        {/* `text-accent-text`, not `text-accent`: see Chip.tsx — Ember as a foreground
            colour fails contrast on the light ground, and the handoff's own accent-text
            token (Ember-Deep) is what "Ember" means as text. */}
        <OctagonAlert
          {...ICON_PROPS}
          size={20} /* smaller than the spec default: an inline status glyph, not a hero icon */
          className="text-accent-text"
          aria-hidden
        />
        {/* Unsatisfied check names are verbatim identifiers (`gaps-confirmed`, never
            reshaped to "GAPS-CONFIRMED") — the one thing on this card that mono is
            actually for. */}
        {unsatisfied.length > 0 && (
          <ul className="og-mono text-m1 break-words">
            {unsatisfied.map((name) => (
              <li key={name}>{name}</li>
            ))}
          </ul>
        )}
        {/* Fix round 1, M10: the server's own refusal text, verbatim — a refusal that
            names no `unsatisfied` check (a 403 `AuthorityViolation` carries none) must
            not degrade to the generic sentence alone with the actual reason dropped. */}
        <p className="text-b2 break-words">{message}</p>
        <p className="text-b2">The gate refused and the refusal is now part of the record.</p>
      </div>
    );
  }

  return (
    <div
      className="border border-hairline p-[clamp(16px,5vw,32px)] flex flex-col gap-3"
      data-state="error"
    >
      {/* The error's own words, verbatim — a sentence, so body type. */}
      <p className="text-b2 break-words">{message}</p>
      {/* A route is a path: an identifier, and mono. */}
      {route && <p className="og-mono text-m2 text-fg-muted break-words">{route}</p>}
      {onRetry && (
        // §5a's 44 px floor; the glyph keeps its 16 px, only the hit area grows.
        <button
          type="button"
          onClick={onRetry}
          className="og-label text-b3 inline-flex min-h-11 w-fit items-center gap-2 self-start"
        >
          {/* Smaller than the spec default: an inline button glyph. */}
          <RotateCcw {...ICON_PROPS} size={16} aria-hidden /> retry
        </button>
      )}
    </div>
  );
}
