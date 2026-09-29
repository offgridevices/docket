// The brand checks that are about the source rather than about a rendered page, plus the
// two guards that keep the per-screen ratchet honest.
//
// Per-screen conformance runs inside each screen's own spec, where the screen is already
// in the state that spec put it — see `_brand.ts`'s header for why it is not centralised
// here.

import { expect, test } from '@playwright/test';
import {
  ALL_SCREENS,
  assertBrandConformance,
  assertNoColourLiteralsInSource,
  CONVERTED_SCREENS,
  isShoutedPhrase,
} from './_brand';
import { openDecision, openView } from './_session';

test.describe('brand conformance', () => {
  // The shout detector, tested directly. It is the one assertion whose own bug is
  // invisible from the outside: a detector that fails open still reports "no offenders",
  // which reads exactly like a clean screen. It shipped in this branch requiring EVERY
  // word to start with a capital, so a single bare numeral disabled it — "STAGE 2
  // COMPLETE" escaped, while the comment beside it claimed the opposite. Caught in
  // review on PR #6. These cases are the fix's evidence.
  test.describe('isShoutedPhrase', () => {
    const shouting = [
      'LOADING EPISODE',
      'NUMBERS AUTHORED BY MODEL',
      'STAGE 2 COMPLETE',        // the regression the old version let through
      'LOADING 3 ITEMS',         // ditto — a bare numeral must not disable the check
      'NO SESSION OPEN',
    ];
    const notShouting = [
      'CRS R45519',              // a document's own name, served from the record
      'GAO-23-106549',           // one token, and an identifier
      'MODEL_APPROVED',          // one token, a lifecycle state
      'Numbers authored by model',
      'GAO did not assess the work.',
      '21 36',                   // numbers, not prose
      'DES-1',                   // too short, and an identifier
      'Open Demo A',
    ];
    for (const t of shouting) {
      test(`catches ${JSON.stringify(t)}`, () => expect(isShoutedPhrase(t)).toBe(true));
    }
    for (const t of notShouting) {
      test(`allows ${JSON.stringify(t)}`, () => expect(isShoutedPhrase(t)).toBe(false));
    }
  });

  test('no component names a colour — the palette lives in tokens.css', () => {
    assertNoColourLiteralsInSource();
  });

  // A name on the ratchet has to be backed by an actual assertion, or the ratchet is
  // just a list of good intentions. This is the check that makes adding a screen to
  // CONVERTED_SCREENS mean something.
  test('every screen on the ratchet really does assert conformance', async () => {
    const { readFileSync, readdirSync } = await import('node:fs');
    const path = await import('node:path');
    const { fileURLToPath } = await import('node:url');
    const here = path.dirname(fileURLToPath(import.meta.url));

    const specs = readdirSync(here).filter((f) => f.endsWith('.spec.ts'));
    const uncovered = CONVERTED_SCREENS.filter((screen) => {
      const spec = specs.find((f) => f.toLowerCase() === `${screen.toLowerCase()}.spec.ts`);
      if (!spec) return true;
      return !readFileSync(path.join(here, spec), 'utf8').includes('assertBrandConformance');
    });

    expect(uncovered, 'these screens are on the ratchet but assert nothing').toEqual([]);
  });

  // The walk that replaced the ratchet's last test.
  //
  // For the length of the rebuild this slot held "the rebuild covers all eleven views":
  // `ALL_SCREENS` minus `CONVERTED_SCREENS`, skipped while that list was short, and the
  // one test that said the rebuild was not finished. The two lists are now the same
  // object (`_brand.ts`), so that comparison can no longer fail and asserts nothing. In
  // its place, the thing it was a stand-in for: one session, every view in turn, brand
  // conformance on each.
  //
  // Not a duplicate of the per-screen specs. Each of those asserts conformance on its own
  // screen in the state that spec put it — a state it reached by acting. This walks the
  // eleven the way a reader does, in one session, changing nothing, and so covers the
  // states no spec sets up on purpose: the register a decision has no rows for, the stage
  // whose act is not available yet.
  //
  // Browse rather than the map (`openView`): the map carries ten rows, not eleven.
  test('every view of one decision is brand-conformant, walked in one session', async ({ page }) => {
    test.setTimeout(120_000);
    await page.goto('/');
    await openDecision(page, 'demo-a');
    for (const screen of ALL_SCREENS) {
      await openView(page, screen);
      await assertBrandConformance(page);
    }
  });

  // The glossary is the single source for every label a person reads (spec §11). Checked
  // here rather than on a page because it is a data table: a missing term is a blank
  // label on some screen nobody opened in this suite.
  test('the glossary has every term the brief lists, each with plain, record and explain text', async () => {
    const { GLOSSARY } = await import('../src/lib/glossary');
    const keys = Object.keys(GLOSSARY);
    expect(keys.length).toBe(26);
    for (const [key, entry] of Object.entries(GLOSSARY)) {
      expect(entry.plain, key).not.toBe('');
      expect(entry.record, key).not.toBe('');
      expect(entry.explain, key).not.toBe('');
      expect(isShoutedPhrase(entry.plain), `${key} is plain language, never a shout`).toBe(false);
      expect(
        entry.plain[0],
        `${key}'s plain form is a phrase in running prose, not a heading`,
      ).toBe(entry.plain[0].toLowerCase());
    }
    expect(GLOSSARY.linchpin.plain).toBe('an assumption the answer depends on');
    expect(GLOSSARY.gap.record).toBe('InsufficientEvidence');
  });

  // semantic.css is the second and last file allowed to name a colour, and the five
  // state values are asserted at their source as well as on the root (brand-tokens.spec)
  // — a token deleted from this file would otherwise only show up as a screen going grey.
  test('the five semantic tokens are the only colour literals outside tokens.css', async () => {
    assertNoColourLiteralsInSource();
    const { readFileSync } = await import('node:fs');
    const path = await import('node:path');
    const { fileURLToPath } = await import('node:url');
    const here = path.dirname(fileURLToPath(import.meta.url));
    const css = readFileSync(path.join(here, '..', 'src', 'brand', 'semantic.css'), 'utf8');
    for (const hex of ['#FBE3D1', '#F0B892', '#B3261E', '#F4DFDB', '#D9A49C', '#8A5F00',
      '#F6EBCB', '#D9BF7A', '#2E6B3F', '#DDEBDC', '#9DC3A2', '#2F5F8F', '#DEE7F1', '#9FB9D3']) {
      expect(css.toUpperCase()).toContain(hex);
    }
  });
});
