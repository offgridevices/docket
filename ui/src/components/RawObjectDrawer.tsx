// The raw-object drawer: the one place a provider/model name and the full JSON of an
// object are allowed to appear (design spec §6, "Model settings safety" and the
// per-screen honesty assertions — proposal-facing screens never show either). Purely
// presentational here: it takes an already-fetched `object_view` shape (plan Task 1
// Step 6) as a prop; the fetch itself belongs to whichever screen opens the drawer.
//
// Brand v3.0 (§5a): below 768px the drawer is the whole screen (`inset-0`) rather than a
// panel with the board showing beside it — at 360px a 448px panel is the screen anyway,
// and half a column of unreadable JSON next to half a column of unreadable board is
// worse than either. At 768px and up it keeps the width it had. Elevation is still tone
// plus a hairline; a slide-over never gets a shadow.

import { X } from 'lucide-react';
import { ICON_PROPS } from '../lib/icons';
import type { AuthorType } from '../lib/provenance';
import { Provenance } from './Provenance';

export interface RawObjectDrawerObject {
  id: string;
  type: string;
  rev: number;
  authorType: AuthorType;
  authorId?: string | null;
  confidence?: string | null;
  provenance?: { locator?: string; sourceArtifact?: string; extractor?: string } | null;
  object: unknown;
}

export interface RawObjectDrawerProps {
  open: boolean;
  onClose: () => void;
  object?: RawObjectDrawerObject | null;
}

export function RawObjectDrawer({ open, onClose, object }: RawObjectDrawerProps) {
  if (!open) return null;

  return (
    <aside
      className="fixed inset-0 z-50 w-full og-bg-sunken border-hairline p-6 overflow-y-auto md:inset-y-0 md:left-auto md:right-0 md:max-w-md md:border-l"
      role="dialog"
      aria-label="raw object"
    >
      <button
        type="button"
        onClick={onClose}
        aria-label="close"
        // `z-10`: `Provenance`'s own corner mark is drawn at the top right of the box
        // below and, being later in the document with the same stacking level, covered
        // the middle of this 44px target the moment the object finished loading — the
        // drawer could be opened by mouse and not closed by one. Task 19's chat spec is
        // the first test to click this control, which is why it went unseen.
        className="absolute right-4 top-4 z-10 inline-flex min-h-11 min-w-11 items-center justify-center text-fg-muted"
      >
        {/* Smaller than the spec's 24px default: a small close control in a fixed
            corner. The glyph is 20px; the hit area around it is 44px (§5a). */}
        <X {...ICON_PROPS} size={20} aria-hidden />
      </button>

      {!object ? (
        <p className="text-b3 text-fg-muted">nothing selected</p>
      ) : (
        <Provenance
          authorType={object.authorType}
          confidence={object.confidence}
          locator={object.provenance?.locator}
          actorId={object.authorId}
        >
          {/* Verbatim ids and revs: mono, and rendered exactly as recorded — a
              lowercase-kebab id stays lowercase-kebab. */}
          <p className="og-mono text-m1">
            {object.type} · {object.id} · rev {object.rev}
          </p>
          {/* `data-model-id` (plan 07 Task 10): the stored object carries
              `ingestionProvenance.extractor`, which names the provider and model — this
              drawer is the one surface allowed to show it, and the attribute is what
              keeps it out of a screenshot if a figure ever opens the drawer. */}
          <pre className="og-mono text-m2 whitespace-pre-wrap mt-4" data-model-id>
            {JSON.stringify(object.object, null, 2)}
          </pre>
        </Provenance>
      )}
    </aside>
  );
}
