// The colour and overflow matrix: every view, three widths, both decisions.
//
// WHY THIS FILE EXISTS. Every screen spec already runs `assertBrandConformance` on its
// own screen, in the state that spec put it, at the smoke project's 1440 px. That leaves
// two gaps this file closes. The first is width: a second Ember, a red plane or a table
// that pushes the page sideways can appear at 360 and at nowhere else, and nothing was
// looking. The second is the colour system itself (spec §10) — the five state colours are
// allowed on glyphs, marks, borders, chips, tints, outline buttons and the two header
// counters, and on nothing else — which no per-screen spec asserts because it is a rule
// about the whole palette rather than about any one screen.
//
// NOTHING HERE NAMES A COLOUR. `semanticColours(page)` reads the token names off
// `semantic.css` and `tokens.css` and resolves their values in the running page, so the
// matrix always asserts against the palette that actually shipped. Retuning a token
// changes what this file expects, automatically and in the same commit; a hard-coded
// `rgb(...)` would instead go on passing while asserting last month's design.
//
// Six tests, not sixty-six: one per (decision, width), each walking all eleven views on
// one page. The walk is the expensive part — a session bootstrap and eleven view loads —
// and splitting it per view would pay for it eleven times over for no extra coverage.

import { expect, test } from '@playwright/test';
import { ALL_SCREENS, assertNoStopFill, assertSingleEmber, semanticColours } from './_brand';
import { openDecision, openView } from './_session';

const WIDTHS = [360, 768, 1440] as const;

test.describe('Colour and overflow, every view, every width', () => {
  for (const source of ['demo-a', 'demo-b'] as const) {
    for (const width of WIDTHS) {
      test(`${source} at ${width}`, async ({ page }) => {
        // Eleven views, each with its own fetches, on one page. The default 30 s is a
        // budget for one screen, not for a walk of them.
        test.setTimeout(240_000);
        await page.setViewportSize({ width, height: width < 768 ? 780 : 900 });
        await page.goto('/');
        await openDecision(page, source);
        const palette = await semanticColours(page);
        // Read out of the palette, never written down. `value` throws by name if a token
        // is renamed, rather than quietly making every Ember count come out zero and
        // every view look clean.
        const ember = palette.value('--c-act');
        const stop = palette.value('--c-stop');

        // The page is the frame and the frame alone: `index.css` gives html, body and the
        // React root the full viewport height and hides the overflow, so the columns
        // inside scroll and the page never does. Asserted once per test rather than once
        // per view — it is one static stylesheet rule, and repeating a constant eleven
        // times only makes a walk look more thorough than it is.
        expect(
          await page.evaluate(() => [
            getComputedStyle(document.documentElement).overflowY,
            getComputedStyle(document.body).overflowY,
          ]),
          'html and body hide their overflow — the frame is the page',
        ).toEqual(['hidden', 'hidden']);

        /** Severity glyphs seen across the whole walk. Zero would mean the check below
         * never ran, which is the way this assertion fails without saying so. */
        let glyphsSeen = 0;

        for (const screen of ALL_SCREENS) {
          await openView(page, screen);

          // Red is a glyph, a hairline or a tint, never a plane (Appendix B §1).
          await assertNoStopFill(page, stop);

          // At most one Ember fill. Zero is the common and correct answer on a view that
          // asks nothing of a person — a register, or a stage whose act is unavailable in
          // this decision's current state.
          const embers = await page.locator('[data-ember]').evaluateAll(
            (els, fill) => els.filter((e) => getComputedStyle(e).backgroundColor === fill).length,
            ember,
          );
          expect(embers, `${screen}: Ember fills`).toBeLessThanOrEqual(1);
          if (embers === 1) await assertSingleEmber(page);

          // The two header counters are the one place §10 lets a numeral carry state
          // colour, and only while it is counting something: a lit "[ 0 ]" would read as
          // an alarm about nothing.
          const counters = await page.locator('[data-counter]').evaluateAll((els) =>
            els.map((e) => {
              const num = e.querySelector('[data-num]') as HTMLElement | null;
              return {
                n: Number((num?.innerText ?? '').replace(/[^\d]/g, '')),
                colour: num ? getComputedStyle(num).color : '',
                body: getComputedStyle(document.body).color,
              };
            }),
          );
          expect(counters.length, `${screen}: the header counters are missing`).toBe(2);
          for (const c of counters) {
            if (c.n === 0) {
              expect(c.colour, `${screen}: a zero counter must not be coloured`).toBe(c.body);
            } else {
              expect(c.colour, `${screen}: a counter that counts something is coloured`).not.toBe(c.body);
              expect(
                palette.text.has(c.colour),
                `${screen}: a counter in ${c.colour}, which is no state colour a numeral may carry`,
              ).toBe(true);
            }
          }

          // Every severity glyph draws its colour from the five state colours in their
          // text-safe form, or from the ink ramp, and from nowhere else. `palette.text`,
          // not `palette.all`: the full map holds the tints and hairlines too, and a glyph
          // drawn in a pale tint is unreadable — the exact mistake this is here to catch.
          //
          // `> svg` is the glyph itself. A descendant selector would also collect the
          // bracket spans `Num` marks `aria-hidden`, which are ink by design and would
          // pad the sample with passes.
          const glyphColours = await page
            .locator('[data-sev] > svg')
            .evaluateAll((els) => els.map((e) => getComputedStyle(e).color));
          glyphsSeen += glyphColours.length;
          for (const colour of new Set(glyphColours)) {
            expect(
              palette.text.has(colour),
              `${screen}: a severity glyph in ${colour}, which is no state colour`,
            ).toBe(true);
          }

          // §5a: nothing pushes the page sideways, and nothing pushes it down.
          //
          // Height is measured on BODY's scroll height, not the root's. The root's is
          // inflated on Readiness at every width by something that is not a defect:
          // Tailwind's `sr-only` positions its screen-reader text absolutely, and with no
          // positioned ancestor between it and the root, the standards grid's thirty-six
          // one-pixel, clipped cell labels resolve against the initial containing block —
          // several hundred pixels of scrollable area that no pixel of the interface
          // occupies. Those labels are not in body's scrollable overflow, so body's
          // scroll height is the height of the interface itself: it stays at the viewport
          // while the columns inside scroll, and it grows the moment anything in the
          // frame's own flow (a header that has outgrown its budget, a view rendered
          // outside the scrolling column) pushes past the bottom of the window.
          const box = await page.evaluate(() => ({
            width: document.documentElement.scrollWidth,
            height: document.body.scrollHeight,
            window: { width: window.innerWidth, height: window.innerHeight },
          }));
          expect(box.width, `${screen}: horizontal overflow`).toBeLessThanOrEqual(box.window.width);
          expect(box.height, `${screen}: the page grew taller than the window`)
            .toBeLessThanOrEqual(box.window.height);

          // …and nothing pushes a COLUMN sideways either. `frame.css` gives the three
          // columns `overflow-x: hidden`, so a table or a code block wider than its column
          // is clipped rather than shown: the page measurement above stays clean and the
          // reader silently loses the right-hand end of the thing. `scrollWidth` still
          // reports the content's own width through a hidden overflow, which is what makes
          // this checkable at all. The map strip is exempt: below 768 it scrolls sideways
          // by design, and `shell.spec.ts` asserts that it does.
          const columns = await page.evaluate(() => {
            const measure = (el: Element | null) =>
              el && (el as HTMLElement).getBoundingClientRect().width > 0
                ? { scroll: el.scrollWidth, client: el.clientWidth }
                : null;
            return { view: measure(document.querySelector('#view')),
                     chat: measure(document.querySelector('.chat')) };
          });
          expect(columns.view, `${screen}: the view column is missing`).not.toBeNull();
          expect(columns.view!.scroll, `${screen}: the view column overflows sideways`)
            .toBeLessThanOrEqual(columns.view!.client);
          if (columns.chat) {
            expect(columns.chat.scroll, `${screen}: the chat column overflows sideways`)
              .toBeLessThanOrEqual(columns.chat.client);
          }
        }

        // The glyph check above is a loop over whatever the view happened to draw, so a
        // walk that found none would report eleven passes and have asserted nothing.
        expect(glyphsSeen, 'no severity glyph anywhere in the walk — the check never ran')
          .toBeGreaterThan(0);
      });
    }
  }
});
