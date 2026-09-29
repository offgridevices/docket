// Retargeted to the 2026-09-11 combined design (Every object in the model, Read and
// agree, Compute, Readiness, The programme). Regenerating the figures is a separate,
// explicit step: run `npx playwright test --project=figures` (or `make figures`).
//
// The documentation figures. Runs ONLY under the `figures` project (`playwright.config.ts`:
// 1600 × 1000 CSS px, deviceScaleFactor 2), never under `smoke` — a figure written at the
// smoke project's 1440 × 900 / DPR 1 would silently overwrite a kept PNG with a
// smaller one. `playwright.config.ts` keeps the two projects disjoint (`figures` matches
// only this file; `smoke` ignores it), so `--project=smoke` never regenerates a PNG and
// `--project=figures` never re-runs the smoke suite at DPR 2.
//
// Five figures, written to `$DOCKET_FIGURES_DIR` (default `ui/test-results/figures/`):
//
//   F1  f1-authority-rail.png   who may write what, from the chat counters
//   F2  f2-review-dialog.png    the review card on the linchpin assumption
//   F3  f3-what-flips.png       Compute: results, flip list, simplex
//   F4  f4-readiness-grid.png   Readiness: verdicts, 36-cell grid, captions
//   F5  f5-timeline.png         Demo B's episodes
//
// The five file names and the five subjects are unchanged; where each subject LIVES is
// not. The old shell put the authority counters and the three-band diagram in a rail down
// the side of the Model screen, and reviewed an object in a dialog over the board. In the
// combined design the counters are the chat column's header and open the diagram as a
// sheet, and reviewing an object is a view of its own at `/review/<id>`. F1 and F2 follow
// them; F3, F4 and F5 keep their subjects and gain the new views' headings.
//
// THE THREE RULES THIS FILE EXISTS TO KEEP
//
// 1. **Light, structurally.** The app ships light only — one ramp in `tokens.css`, no
//    `data-theme`, no stored preference, nothing to switch
//    (`docs/decisions/2026-09-08-demo-ui-is-light-only.md`). Nothing here forces a mode.
//    `emulateMedia` still sets `reducedMotion`, which is a real determinism control and
//    unrelated.
//
// 2. **Masking is not cosmetic.** Every element that could print a provider or model id
//    carries `data-model-id` (`Provenance`'s actor-id line, `ReviewCard`'s recorded actor
//    line, `RawObjectDrawer`'s JSON body, `Activity`'s actor column, `SettingsPanel`'s
//    model `<select>`), and every screenshot below passes
//    `mask: [page.locator('[data-model-id]')]` — not only F2, where the plan's own table
//    asks for it. A mask that matches nothing costs nothing; a mask that is missing the
//    day a fixture changes costs a model name in a published figure. The Settings
//    slide-over is never opened here at all.
//
// 3. **Byte-stability, by removing causes, not by adding tolerance.** Every figure is now
//    taken on a committed demonstration store opened through the header's own decision
//    switcher (`openDecision`), so every object id, every stamp and every numeral in the
//    frame comes off a file in the repository rather than out of a fresh elicitation.
//    That replaces the old fixed-episode-id/fixed-clock apparatus this file used to carry
//    (`elicit` with an explicit `episodeId` and `now`), which existed only because a
//    freshly elicited episode minted `f"ep-{uuid4}"` and stamped itself with the wall
//    clock. What remains pinned here is what the browser, not the record, controls:
//      - fonts: `document.fonts.ready` is awaited before every shot (a first shot taken
//        before the self-hosted faces load ships in fallback type);
//      - motion: transitions, animations and the text caret are killed by an init script
//        (so it survives client-side navigation), `emulateMedia({reducedMotion: 'reduce'})`,
//        and Playwright's own `animations: 'disabled'`.
//    `DOCKET_FIGURES_DIR` redirects the output directory so the determinism check can run
//    this project twice into two directories and `cmp` the PNGs.

import { mkdirSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { expect, test, type Locator, type Page } from '@playwright/test';
import { currentSessionId, openDecision, openView } from './_session';

const HERE = path.dirname(fileURLToPath(import.meta.url));

/** Where the PNGs land. `ui/test-results/figures/` by default — gitignored, so a run
 * never dirties the tree; `DOCKET_FIGURES_DIR` sends them anywhere else (a determinism
 * run points two runs at two throwaway directories and compares them). */
const FIGURES_DIR = process.env.DOCKET_FIGURES_DIR
  ? path.resolve(process.env.DOCKET_FIGURES_DIR)
  : path.join(HERE, '..', 'test-results', 'figures');

function figure(name: string): string {
  mkdirSync(FIGURES_DIR, { recursive: true });
  return path.join(FIGURES_DIR, name);
}

const FREEZE_CSS = `*,*::before,*::after{
  animation:none!important;
  transition:none!important;
  caret-color:transparent!important;
  scroll-behavior:auto!important;
}`;

/** Every screenshot in this file takes the same options. `animations: 'disabled'` is
 * Playwright's own belt to the CSS braces above; `scale: 'device'` keeps the DPR-2 pixels
 * the `figures` project asks for (Playwright's default, `'device'`, is stated rather than
 * assumed because a figure at DPR 1 would be a silent regression in print). */
function shotOptions(page: Page) {
  return {
    animations: 'disabled' as const,
    scale: 'device' as const,
    mask: [page.locator('[data-model-id]')],
    maskColor: '#767676',
  };
}

/** Register the page-level determinism controls. Called before the first `goto` in each
 * test; `addInitScript` re-runs on every navigation, which matters because this app
 * navigates client-side between screens and a one-off `addStyleTag` would not survive a
 * full reload. */
async function pinPage(page: Page): Promise<void> {
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.addInitScript((css: string) => {
    const inject = () => {
      const style = document.createElement('style');
      style.setAttribute('data-figures-freeze', '');
      style.textContent = css;
      document.head.appendChild(style);
    };
    if (document.head) inject();
    else document.addEventListener('DOMContentLoaded', inject, { once: true });
  }, FREEZE_CSS);
}

/** Await the web fonts, then hand back a locator that is on screen and settled. */
async function ready(page: Page, locator: Locator): Promise<Locator> {
  await expect(locator).toBeVisible({ timeout: 20_000 });
  await page.evaluate(async () => {
    await document.fonts.ready;
  });
  return locator;
}

test.describe('documentation figures', () => {
  test('F1 — who may write what, opened from the chat counters on the Model view', async ({ page }) => {
    await pinPage(page);
    await page.goto('/');
    await openDecision(page, 'demo-a');
    await openView(page, 'Model');
    await ready(page, page.getByRole('heading', { name: 'Every object in the model' }));
    // The board has to have rendered before the counters are opened: they come from a
    // second request, and an unanswered one shows a zero placeholder — a real zero state,
    // but not this episode's.
    await expect(page.locator('[data-object-id]').first()).toBeVisible({ timeout: 20_000 });
    const counters = page.getByTestId('authority-counters');
    await expect(counters).toContainText(/numbers authored by model/);
    await counters.click();

    // The sheet the counters open, not the whole page: the wash behind it would put the
    // board (and the scoring panel) into the figure.
    const diagram = page.getByRole('dialog', { name: 'Who may write what' });
    await ready(page, diagram);
    // The three bands, in the order the architecture fixes them.
    await expect(diagram).toContainText('The AI proposes');
    await expect(diagram).toContainText('A person decides');
    await expect(diagram).toContainText('The kernel computes');

    await diagram.screenshot({ path: figure('f1-authority-rail.png'), ...shotOptions(page) });
  });

  test('F2 — the review card on the linchpin assumption', async ({ page }) => {
    await pinPage(page);
    await page.goto('/');
    await openDecision(page, 'demo-a');
    const sessionId = await currentSessionId(page);
    const episodeId = await page.evaluate(
      (sid: string) => sessionStorage.getItem(`docket-episode-id:${sid}`),
      sessionId,
    );
    expect(episodeId, 'the decision must have an episode open').toBeTruthy();

    // WHICH assumption, read off the record rather than guessed — and asserted to be the
    // linchpin rather than assumed to be the only one on the sheet.
    const g1Res = await page.request.get(`/api/session/${sessionId}/episode/${episodeId}/g1`);
    expect(g1Res.ok(), await g1Res.text()).toBe(true);
    const g1 = (await g1Res.json()) as { objects: { id: string; type: string }[] };
    const assumptions = g1.objects.filter((o) => o.type === 'Assumption');
    expect(assumptions.length, 'the episode must carry an Assumption').toBeGreaterThan(0);

    let linchpinId: string | null = null;
    let extractor: string | null = null;
    for (const candidate of assumptions) {
      const objRes = await page.request.get(`/api/session/${sessionId}/object/${candidate.id}`);
      expect(objRes.ok(), await objRes.text()).toBe(true);
      const view = (await objRes.json()) as {
        object: { linchpin?: boolean };
        provenance: { extractor?: string } | null;
      };
      if (view.object.linchpin === true) {
        linchpinId = candidate.id;
        extractor = view.provenance?.extractor ?? null;
        break;
      }
    }
    expect(linchpinId, 'no Assumption on this episode is marked linchpin').toBeTruthy();

    // The card as a place you can go, which is what it became in this design: an address
    // a reader can be sent, not a popup over a board.
    await page.goto(`/review/${linchpinId}`);
    await ready(page, page.getByRole('heading', { name: 'Read and agree' }));
    const card = page.locator('[data-review-card]');
    await ready(page, card);

    // The six regions, in order, are the point of the figure — asserted before shooting
    // rather than trusted to the shot.
    const regions = await card
      .locator('[data-region]')
      .evaluateAll((els) => els.map((el) => el.getAttribute('data-region') ?? ''));
    expect(regions).toEqual([
      'WHAT',
      'WHY THE MODEL PROPOSED IT',
      'SOURCE',
      'IF IT IS WRONG',
      'WHAT YOU CAN DO',
      'WHAT HAPPENS TO THE RECORD',
    ]);

    // Honesty rule 3, asserted on the exact pixels that ship: the card never prints the
    // extractor, so nothing in this figure names a provider or a model.
    const cardText = await card.innerText();
    expect(
      cardText.match(
        /\b(openai|anthropic|claude|ollama|openrouter|gpt-?\d|llama-?\d|mistral|gemini|gemma\d|qwen|deepseek)\b/i,
      ),
      'a provider/model string reached the review card',
    ).toBeNull();
    // Stronger than the family list above: the record's OWN extractor string for this
    // object, whatever it is, must not appear anywhere on the card. Under the recorded
    // backend that string is "recorded:recorded", which no denylist of model families
    // would ever match — but it occupies the same slot a live backend fills with
    // `provider:model`, and it once printed there.
    if (extractor) {
      expect(
        cardText.includes(extractor),
        `the record's extractor ("${extractor}") is printed on the review card`,
      ).toBe(false);
    }

    await card.screenshot({ path: figure('f2-review-dialog.png'), ...shotOptions(page) });
  });

  test('F3 — what flips the decision, on Demo A’s own sealed runs', async ({ page }) => {
    await pinPage(page);
    await page.goto('/');
    // Demo A's seeded episode is `PENDING_SIGNATURE`, with two sealed `EvaluationRun`s,
    // flip analyses and a `flipSummary` already on record. No live walk reaches that state
    // today — no route lets a human name an evaluator — so the figure is taken where the
    // state actually exists, and the demo script says the same thing out loud.
    await openDecision(page, 'demo-a');
    await openView(page, 'Compute');
    await ready(page, page.getByRole('heading', { name: 'Compute' }));

    const section = page.locator('[data-testid="run-section"]').first();
    await ready(page, section);
    await expect(section.getByText('What flips the decision')).toBeVisible();
    await expect(section.locator('[data-testid="flip-row"]').first()).toBeVisible();
    // The weight simplex sits under the flip list in the same section.
    await expect(section.getByText(/simplex/i).first()).toBeVisible();

    await section.screenshot({ path: figure('f3-what-flips.png'), ...shotOptions(page) });
  });

  test('F4 — the readiness grid, three verdicts and the standing captions', async ({ page }) => {
    await pinPage(page);
    await page.goto('/');
    await openDecision(page, 'demo-a');
    await openView(page, 'Readiness');
    await ready(page, page.getByRole('heading', { name: 'Readiness' }));

    const group = page.getByTestId('standards-assessment');
    await ready(page, group);
    expect(await group.locator('[data-testid="grid-cell"]').count()).toBe(36);
    expect(await group.locator('[data-testid="verdict-card"]').count()).toBe(3);
    // The rating-scale caption is standing body text under the grid, never a tooltip —
    // the same requirement `readiness.spec.ts` asserts, re-asserted here because this is
    // the figure a reviewer will read it off.
    const caption = group.getByText(/Rating scale \(GAO-11-82R/);
    await expect(caption).toBeVisible();
    expect(await caption.evaluate((el) => el.hasAttribute('title'))).toBe(false);

    await group.screenshot({ path: figure('f4-readiness-grid.png'), ...shotOptions(page) });
  });

  test('F5 — the programme on Demo B (the alternate; captured, not placed)', async ({ page }) => {
    await pinPage(page);
    await page.goto('/');
    await openDecision(page, 'demo-b');
    await openView(page, 'Timeline');
    await ready(page, page.getByRole('heading', { name: 'The programme' }));

    const rail = page.getByTestId('timeline-rail');
    await ready(page, rail);
    expect(await rail.getByTestId('timeline-episode').count()).toBeGreaterThanOrEqual(4);

    await rail.screenshot({ path: figure('f5-timeline.png'), ...shotOptions(page) });
  });
});
