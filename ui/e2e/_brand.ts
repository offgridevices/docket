// Brand v3.0's rules, as assertions.
//
// The handoff's own tagline is "Built to be checked", and most of what it asks for is
// mechanically checkable: right angles, no shadows, three faces, sentence case, one
// Ember per surface. Those rules rot silently — nobody notices a second Ember or a 6px
// radius in review — so they are tested rather than trusted.
//
// HOW THIS IS USED, in three places. Each screen's own spec calls
// `assertBrandConformance(page)` at the end of its main test, where the screen is already
// populated the way the spec put it — that is the primary check, and it is per-screen
// because most screens need a bootstrapped session and a central file would have to
// duplicate that setup, then assert against a state no visitor ever sees. `brand.spec.ts`
// adds one walk of every view of one decision, changing nothing, which covers the states
// no spec sets up on purpose. `colour.spec.ts` walks the same views at three widths on
// both demonstration decisions for the rules that are about colour and overflow.
//
// A screen is "converted" when its own spec makes that call, and
// `brand.spec.ts` still checks that every name on `CONVERTED_SCREENS` is backed by one.
//
// Spec: docs/design/frontend-design.md §5 (visual language) and §5a (layout).

import { readdirSync, readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { expect, type Page } from '@playwright/test';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const SRC = path.join(HERE, '..', 'src');

/** The eleven views of the combined design (spec §5). Every walk of the whole interface
 * — `brand.spec.ts`'s, `colour.spec.ts`'s, `coverage.spec.ts`'s — iterates this list, so
 * a twelfth view is covered by all three the moment it is named here. */
export const ALL_SCREENS = [
  'Needs', 'Request', 'Model', 'Review', 'Plan', 'Compute',
  'Readiness', 'Package', 'Evidence', 'Timeline', 'Activity',
] as const;

/**
 * The ratchet, complete.
 *
 * This was a hand-maintained subset of `ALL_SCREENS` for the length of the rebuild: a
 * view joined in the task that landed its spec, and `brand.spec.ts`'s last test failed
 * until the two lists agreed. They agree, so the list is now the same object rather than
 * a copy of it — a second literal list could only ever drift back apart, and there is no
 * longer a state in which it should.
 */
export const CONVERTED_SCREENS = ALL_SCREENS;

/** Ember, as the browser reports it. Kept here rather than inline so the ember ruling
 * (docs/decisions/2026-09-08-ember-is-ff6a00.md) has exactly one home in the test code. */
const EMBER_RGB = 'rgb(255, 106, 0)';

/**
 * The five state colours in the form §10 lets them touch type. NAMES, not values.
 *
 * `--c-act` is deliberately not here: it is the fill, and Ember on the paper ground fails
 * 4.5:1 — `semantic.css` says so in its own comment and carries `--c-act-text` for
 * exactly this. The other four tokens' single value is already their text value.
 *
 * This list is the point of `Palette.text`. A set built from every `--c-*` the file
 * defines would also admit `--c-act-tint`, `--c-stop-line` and their six siblings, and a
 * severity glyph drawn in a pale tint — unreadable, and the exact mistake §10 is written
 * to prevent — would pass the check meant to catch it.
 */
const TEXT_TOKENS = ['--c-act-text', '--c-stop', '--c-wait', '--c-done', '--c-ai'] as const;

/**
 * The brand's colours, read at run time and never written down here.
 *
 * `all` is every colour token the two files define, keyed by the `rgb(r, g, b)` string
 * the browser reports and valued by the token it came from — so `all.has(colour)` is a
 * membership test and `all.get(colour)` names the token when a check needs to. Tints and
 * hairlines are in it, because some things (a chip's background, a 3 px rule) are
 * supposed to be a tint.
 *
 * `text` is the narrow set: the five state colours above in their text-safe form, plus
 * the ink ramp. This is what a coloured glyph or a coloured numeral is allowed to be. The
 * ink ramp belongs in it because `Sev`'s `info` kind is deliberately uncoloured (R24 —
 * the glyph carries the state, and "for information" is not a state) and draws
 * `--og-fg-secondary`; a set of only the five would report that one correct case as the
 * violation.
 *
 * `value(name)` is one token's resolved colour, for the checks that are about a specific
 * token rather than about membership.
 *
 * HOW IT IS READ. The token NAMES come off disk (`semantic.css` for the state colours,
 * `tokens.css` for the ink ramp — the same two files `assertNoColourLiteralsInSource`
 * treats as the only places allowed to name a colour) and each name's VALUE is resolved
 * in the running page against a throwaway probe element. Not by parsing hex out of the
 * file, for two reasons: `--c-act` and `--c-act-text` are not hex at all, they are
 * `var()` references into `tokens.css`, so a hex parser would silently miss the two most
 * important tokens; and `getComputedStyle(probe).color` hands back the exact `rgb()`
 * spelling the assertions compare against, with no hand-rolled conversion to get wrong.
 * Retuning a token therefore changes what the specs expect, in the same commit.
 */
export interface Palette {
  readonly all: ReadonlyMap<string, string>;
  readonly text: ReadonlySet<string>;
  value(name: string): string;
}

export async function semanticColours(page: Page): Promise<Palette> {
  const stateTokens = tokenNames(path.join(SRC, 'brand', 'semantic.css'), /--c-[a-z0-9-]+/g);
  const inkTokens = tokenNames(path.join(SRC, 'brand', 'tokens.css'), /--og-fg(?:-[a-z0-9]+)?/g);

  const byName = new Map(await resolveTokens(page, [...stateTokens, ...inkTokens]));
  const value = (name: string): string => {
    const rgb = byName.get(name);
    if (!rgb) throw new Error(`${name} is not defined in semantic.css or tokens.css any more`);
    return rgb;
  };

  const all = new Map([...byName].map(([name, rgb]) => [rgb, name]));
  const text = new Set([...TEXT_TOKENS, ...inkTokens].map(value));
  return { all, text, value };
}

/** Resolve `names` to the `rgb(...)` strings the browser reports for them, in order.
 * A throwaway probe rather than `getPropertyValue`, so a token defined as `var(--other)`
 * comes back as a colour rather than as the text of its own reference. */
async function resolveTokens(page: Page, names: string[]): Promise<[string, string][]> {
  return page.evaluate((wanted: string[]) => {
    const probe = document.createElement('span');
    probe.style.position = 'fixed';
    probe.style.visibility = 'hidden';
    document.body.appendChild(probe);
    const out: [string, string][] = [];
    for (const name of wanted) {
      probe.style.color = `var(${name})`;
      out.push([name, getComputedStyle(probe).color]);
    }
    probe.remove();
    return out;
  }, names);
}

/** The distinct custom-property names `pattern` finds in `file`, in file order. */
function tokenNames(file: string, pattern: RegExp): string[] {
  return [...new Set(readFileSync(file, 'utf8').match(pattern) ?? [])];
}

/** Right angles, always. Brand quick-rule 2. */
export async function assertRadiusZero(page: Page): Promise<void> {
  const offenders = await page.evaluate(() =>
    Array.from(document.querySelectorAll<HTMLElement>('body *'))
      .filter((el) => {
        const r = getComputedStyle(el).borderRadius;
        return r !== '' && !/^0px([ 0px]*)$/.test(r) && r !== '0%';
      })
      .map((el) => `${el.tagName.toLowerCase()}.${el.className}`)
      .slice(0, 8),
  );
  expect(offenders, 'border-radius is 0 everywhere (brand quick-rule 2)').toEqual([]);
}

/** Surfaces don't float. Elevation is tone plus a hairline, never a shadow. */
export async function assertNoShadows(page: Page): Promise<void> {
  const offenders = await page.evaluate(() =>
    Array.from(document.querySelectorAll<HTMLElement>('body *'))
      .filter((el) => {
        const s = getComputedStyle(el);
        return (s.boxShadow !== 'none' && s.boxShadow !== '') || s.filter.includes('drop-shadow');
      })
      .map((el) => `${el.tagName.toLowerCase()}.${el.className}`)
      .slice(0, 8),
  );
  expect(offenders, 'surfaces do not float (brand quick-rule 2)').toEqual([]);
}

/**
 * Is this run of text shouted prose?
 *
 * Pure, exported and unit-tested (`brand.spec.ts`) rather than inlined into the
 * `page.evaluate` below, because the previous inline version was wrong in a way nothing
 * could catch: it required EVERY word to match `/^[A-Z].../`, so one bare numeral made
 * the whole phrase fail the test and escape detection. "STAGE 2 COMPLETE" sailed
 * through — the exact opposite of what its own comment claimed. A predicate this fiddly
 * needs its own tests, so it is a function, not a regex buried in a browser callback.
 *
 * Two classes are deliberately NOT shouting, because the record genuinely spells them
 * that way and the UI must render them verbatim:
 *   - bare acronyms and lifecycle states (GAO, DoW, MODEL_APPROVED) — single words, and
 *     a shout needs two or more;
 *   - document identifiers (CRS R45519, GAO-23-106549) — two tokens, but names.
 * An identifier token mixes letters and digits, or carries a hyphen or underscore.
 * A bare number is NOT an identifier, so "LOADING 3 ITEMS" is caught.
 */
export function isShoutedPhrase(text: string): boolean {
  const t = text.trim();
  if (t.length < 8) return false;

  const words = t.split(/\s+/);
  if (words.length < 2) return false;

  const isShoutWord = (w: string) => /^[A-Z][A-Z0-9_·—–-]*[.,:;]?$/.test(w);
  const isBareNumber = (w: string) => /^\d+[.,:;]?$/.test(w);

  // Every word is either shouted or a bare numeral, AND at least one is a real word —
  // so "21 36" is a pair of numbers, not shouting.
  if (!words.every((w) => isShoutWord(w) || isBareNumber(w))) return false;
  if (!words.some(isShoutWord)) return false;

  const hasIdentifier = words.some((w) => (/[A-Z]/.test(w) && /\d/.test(w)) || /[-_]/.test(w));
  return !hasIdentifier;
}

/** v3.0 takes authority from size, never from caps. Nothing in the interface is
 * uppercased — not by CSS, and not by a shouty string literal either. */
export async function assertNoUppercase(page: Page): Promise<void> {
  const transformed = await page.evaluate(() =>
    Array.from(document.querySelectorAll<HTMLElement>('body *'))
      .filter((el) => getComputedStyle(el).textTransform === 'uppercase')
      .map((el) => `${el.tagName.toLowerCase()}.${el.className}`)
      .slice(0, 8),
  );
  expect(transformed, 'v3.0 display type is sentence case, never caps').toEqual([]);

  // The browser only collects candidates — anything with no lower-case letter in it.
  // The decision is made in Node by `isShoutedPhrase`, so the rule is one testable
  // function rather than a regex that can only be exercised through a live page.
  const candidates = await page.evaluate(() => {
    const out: string[] = [];
    const walk = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    for (let n = walk.nextNode(); n; n = walk.nextNode()) {
      const t = (n.textContent ?? '').trim();
      if (t.length >= 8 && !/[a-z]/.test(t)) out.push(t);
    }
    return out;
  });

  const shouted = candidates.filter(isShoutedPhrase).map((t) => t.slice(0, 60)).slice(0, 8);
  expect(shouted, 'no ALL-CAPS prose (§5: sentence case)').toEqual([]);
}

/** Four families, four jobs — and only three of them are ever set on an element, since
 * v3.0 collapsed display and body onto one face. */
export async function assertOnlyBrandFaces(page: Page): Promise<void> {
  const offenders = await page.evaluate(() => {
    const allowed = ['instrument sans', 'newsreader', 'jetbrains mono'];
    const seen = new Set<string>();
    for (const el of Array.from(document.querySelectorAll<HTMLElement>('body *'))) {
      const direct = Array.from(el.childNodes).some(
        (n) => n.nodeType === Node.TEXT_NODE && (n.textContent ?? '').trim(),
      );
      if (!direct) continue;
      const first = getComputedStyle(el).fontFamily.split(',')[0].replace(/["']/g, '').toLowerCase();
      if (first && !allowed.includes(first)) seen.add(first);
    }
    return Array.from(seen).slice(0, 8);
  });
  expect(offenders, 'three faces, three jobs (§5)').toEqual([]);
}

/**
 * §5's precedence rule: exactly one element on a rendered screen carries Ember as a
 * fill — the screen's primary human action, else the single most severe blocking
 * finding, else nothing. Zero is a valid and common answer: a screen that asks nothing
 * of a human has no Ember at all.
 *
 * Counts only the outermost Ember element, so an Ember button wrapping an Ember-
 * inheriting span is one lit point, not two.
 */
export async function assertSingleEmber(page: Page): Promise<void> {
  const lit = await page.evaluate((ember) => {
    const isEmber = (el: Element) => getComputedStyle(el).backgroundColor === ember;
    return Array.from(document.querySelectorAll('body *'))
      .filter((el) => isEmber(el) && !(el.parentElement && isEmber(el.parentElement)))
      .map((el) => `${el.tagName.toLowerCase()}.${(el as HTMLElement).className}`);
  }, EMBER_RGB);
  expect(
    lit.length,
    `one Ember per surface — found ${lit.length}${lit.length ? ': ' + lit.join(' | ') : ''}`,
  ).toBeLessThanOrEqual(1);
}

/**
 * Red is never a fill (spec Appendix B §1): the stop token lives on glyphs, hairlines,
 * 3 px left borders, chips and tints — a solid red plane would read as a second accent.
 *
 * The value is resolved from `--c-stop` at call time, not written here. It used to be the
 * literal `rgb(179, 38, 30)`, which was correct and still wrong to keep: retuning the
 * token would have left this assertion hunting for a colour the app no longer paints, and
 * reporting every screen clean. The one place the value is written down is
 * `brand.spec.ts`'s source-level pin, which reads the hex straight out of `semantic.css`
 * and is meant to fail when somebody changes it.
 *
 * A caller that has already built a `Palette` can pass its `--c-stop` in rather than pay
 * for a second read; `assertBrandConformance` does not, because most callers have no
 * palette in hand and one page evaluation is cheap.
 */
export async function assertNoStopFill(page: Page, stopRgb?: string): Promise<void> {
  const stop = stopRgb ?? (await semanticColours(page)).value('--c-stop');
  const filled = await page.evaluate((red) =>
    Array.from(document.querySelectorAll<HTMLElement>('body *'))
      .filter((el) => getComputedStyle(el).backgroundColor === red)
      .map((el) => `${el.tagName.toLowerCase()}.${el.className}`)
      .slice(0, 8), stop);
  expect(filled, 'red is a glyph, a hairline or a tint — never a fill').toEqual([]);
}

/** §5a: every interactive target is at least 44x44 at every width. Ignores elements the
 * layout has collapsed to zero (a closed dialog's contents), which are not targets. */
export async function assertTouchTargets(page: Page): Promise<void> {
  const small = await page.evaluate(() =>
    Array.from(
      document.querySelectorAll<HTMLElement>(
        'button, a[href], input:not([type="hidden"]), select, textarea, [role="button"]',
      ),
    )
      .filter((el) => {
        const r = el.getBoundingClientRect();
        if (r.width === 0 || r.height === 0) return false;
        if (getComputedStyle(el).display === 'inline') return false; // inline link in prose
        return r.width < 44 || r.height < 44;
      })
      .map((el) => {
        const r = el.getBoundingClientRect();
        return `${el.tagName.toLowerCase()}.${el.className} ${Math.round(r.width)}x${Math.round(r.height)}`;
      })
      .slice(0, 8),
  );
  expect(small, 'every interactive target is at least 44x44 (§5a)').toEqual([]);
}

/** §5a: no screen scrolls sideways, at any supported width. This is the regression that
 * returns silently the moment somebody adds a wide table. */
export async function assertNoHorizontalOverflow(page: Page): Promise<void> {
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  );
  expect(overflow, 'no screen scrolls horizontally (§5a)').toBeLessThanOrEqual(0);
}

/**
 * No colour literal outside tokens.css. Checked against the source text rather than
 * against computed styles: a computed-style check cannot tell a token-derived colour
 * from a hand-written one once the browser has resolved both to rgb(), and it produces
 * false positives the moment anything composes a colour with opacity or color-mix.
 * Reading the source is exact, and it fails at the place the fix belongs.
 */
export function assertNoColourLiteralsInSource(): void {
  const offenders: string[] = [];
  const hex = /#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})\b/;
  const walk = (dir: string): void => {
    for (const entry of readdirSync(dir, { withFileTypes: true })) {
      const full = path.join(dir, entry.name);
      if (entry.isDirectory()) {
        walk(full);
        continue;
      }
      if (!/\.(tsx?|css)$/.test(entry.name)) continue;
      // tokens.css is the one file allowed to name a colour; it is the palette.
      if (full.endsWith(path.join('brand', 'tokens.css'))) continue;
      // semantic.css is the second and last file allowed to name a colour (spec §10).
      if (full.endsWith(path.join('brand', 'semantic.css'))) continue;
      // Comments are stripped before scanning, not skipped line-by-line. This codebase
      // documents *why* a token has the value it does, and writing `#5C554A` inside a
      // `{/* … */}` JSX comment is exactly the right thing to do there — a line-prefix
      // test misses it and reports the documentation as a violation.
      stripComments(readFileSync(full, 'utf8'))
        .split('\n')
        .forEach((line, i) => {
          if (hex.test(line)) {
            offenders.push(`${path.relative(SRC, full)}:${i + 1} ${line.trim().slice(0, 60)}`);
          }
        });
    }
  };
  walk(SRC);
  expect(offenders, 'colours come from tokens.css, never from a component (§5)').toEqual([]);
}

/** Blank out `/* … *\/` blocks (which covers `{/* … *\/}`) and `// …` tails, preserving
 * line numbering so an offender still reports the line it is on. Deliberately naive
 * about strings containing comment markers: a false negative here costs a missed hex in
 * a string literal, which no component has; a false positive costs a broken build over a
 * comment, which is worse. */
function stripComments(source: string): string {
  return source
    .replace(/\/\*[\s\S]*?\*\//g, (block) => block.replace(/[^\n]/g, ' '))
    .replace(/\/\/[^\n]*/g, '');
}

/** Every rule above, in one call. A screen spec runs this at the end of its main test,
 * where the screen is already in the state that spec put it. */
export async function assertBrandConformance(page: Page): Promise<void> {
  await assertRadiusZero(page);
  await assertNoShadows(page);
  await assertNoUppercase(page);
  await assertOnlyBrandFaces(page);
  await assertSingleEmber(page);
  await assertNoStopFill(page);
  await assertTouchTargets(page);
  await assertNoHorizontalOverflow(page);
}
