// Where everything lives: the colour key, every view with a Go link, and — Task 20 —
// the full inventory of the old interface's controls with the home each one now has.
//
// The inventory is the answer to "did the rebuild lose anything?", so it is data
// (`coverage.ts`) a spec can count rather than prose a reader has to trust. Every row's
// Go either navigates to a real address or opens the overlay that holds the control.
import { useNavigate } from 'react-router-dom';
import { useWorkspace } from '../api/useWorkspace';
import { ColourKey } from '../components/ColourKey';
import { VIEWS } from '../routes';
import { COVERAGE, type CoverageItem } from './coverage';
import { Sheet } from './Sheet';

export function CoverageSheet() {
  const { closeOverlay, openOverlay } = useWorkspace();
  const navigate = useNavigate();
  // A row's home is one act: close the sheet, then either go to the address or open the
  // overlay that holds it. Nothing here computes a route — `coverage.ts` names it.
  const go = (it: CoverageItem) => {
    closeOverlay();
    if (it.overlay) openOverlay({ kind: it.overlay });
    else if (it.route) navigate(it.route);
  };
  return (
    <Sheet title="Where everything lives" onClose={closeOverlay} centre>
      <h3 className="og-label text-b1">What the colours mean</h3>
      <p className="mb-2 text-b3 text-fg-secondary">A deliberate deviation from the brand's one-accent rule: a working tool needs state colour that people learn once. Only one Ember-filled button exists per view.</p>
      <ColourKey />
      <h3 className="og-label mt-5 text-b1">The views</h3>
      <table className="w-full text-b3" data-coverage-views>
        <tbody>
          {VIEWS.map((v) => (
            <tr key={v.key} className="border-b border-hairline">
              <td className="py-1.5">{v.label}</td>
              <td className="og-mono text-m2 text-fg-muted">{v.path}</td>
              <td className="text-right"><button type="button" onClick={() => { closeOverlay(); navigate(v.path); }} className="og-label inline-flex min-h-11 min-w-11 items-center justify-end underline underline-offset-4">go</button></td>
            </tr>
          ))}
        </tbody>
      </table>

      <h3 className="og-label mt-5 text-b1">Every control of the old interface</h3>
      <p className="mb-2 text-b3 text-fg-secondary">Each line is one control the nine screens before this rebuild carried, and the place it lives now. Nothing on this list was dropped.</p>
      {COVERAGE.map((group) => (
        <details key={group.group} open className="mt-3 border border-hairline">
          {/* The group name is a name — "Model (gate 1)" — not a measurement, so the
              numeral walk reads it as a label. */}
          <summary className="og-label cursor-pointer bg-surface px-3 py-2 text-b2" data-num="label">{group.group}</summary>
          <div className="px-3 pb-2">
            {group.items.map((it) => (
              <div key={it.item} data-coverage-item className="grid grid-cols-[1fr_auto] gap-2 border-t border-hairline py-2 text-b3">
                {/* Verbatim inventory text: it names old buttons, old sections and the
                    standard's own clause numbers, none of which this view computed. */}
                <span data-num="label">{it.item}<span className="block text-fg-secondary">{it.where}</span></span>
                <button type="button" onClick={() => go(it)} className="og-label inline-flex min-h-11 min-w-11 items-center justify-end underline underline-offset-4">Go</button>
              </div>
            ))}
          </div>
        </details>
      ))}
    </Sheet>
  );
}
