// The programme (spec §17). Every number this view prints comes from
// `GET .../timeline`'s own `timing` block (`kernel.clock.programme_timing`) — the days
// each episode lived, the whole months between them, the months since the last one and
// the re-accreditation clock — so this spec reads the same route the view reads and
// requires the two to agree, rather than hand-copying a number the browser must never
// have computed in the first place.
//
// Three places where this spec deliberately differs from the task brief's draft, each
// because the committed fixture says otherwise:
//   * the diff test clicks the THIRD node, not the second. `demos/b_omfv_2019_2023`'s
//     main chain pairs 2→3 and 3→4 as `unknown` and 1→2 as `replacements`, so the
//     second node's diff has a field-level pairing and would never print the sentence
//     this test exists to require (the pre-rebuild spec clicked the same third node,
//     for the same reason).
//   * the standing caption asserted beside the 3×3 grid is `GAO_23_106549_CAPTION`, the
//     one this view actually prints. The rating-scale caption ("Rating scale
//     (GAO-11-82R…)") belongs to the readiness grid's server-rendered captions, which
//     nothing on the timeline route serves.
//   * the watch test intercepts `POST .../watch`. `agent.refresh_watch.detect` is
//     deterministic and finds nothing at all in either committed demo store (verified
//     directly: zero proposals for `prg-gcv-2013` and for every episode of `prg-omfv`),
//     so the half of the contract this view owns — a proposal renders as a dashed blue
//     AI card, unfiled, with the "Detected, not filed" sentence beside it — can only be
//     exercised against a proposal the route is made to return. Same technique, and
//     the same reason, as `evidence.spec.ts`'s withheld-field test.
// Demo B carries TWO filed-and-unopened triggers, so `Open refresh` appears twice and
// only the first is lit: §5 allows one Ember per view, whatever the record holds.
// And the session with no programme is a brand-new one, not Demo A — Demo A's fixture
// has always carried `prg-gcv-2013`.

import { expect, test } from '@playwright/test';
import { assertBrandConformance } from './_brand';
import { assertFooterSentences, assertNoOverrideControl, assertNoProviderStrings, assertNoUnbracketedNumerals, collectConsoleErrors, forEachViewport } from './_fixtures';
import { goTo, openDecision } from './_session';
import type { WatchProposal, WatchResponse } from '../src/types/api';

interface Timing { episodes: { id: string; days: number }[]; between: { months: number }[]; sinceLast: { months: number }; accreditationMonths: number; overdue: boolean }
interface TimelineBody { timing: Timing; episodes: { id: string; refreshedBecause?: string | null }[]; refreshTriggers: { id: string; detectedAt: string }[] }

const NO_PROGRAMME = 'This decision is not part of a programme; there is no timeline to show.';

/** The one proposal the stubbed watch route answers with, typed as the route's own
 * `WatchProposal` so a server-side rename of any field shows up here as a type error
 * rather than as a spec that quietly stops proving anything. (`ui/tsconfig.json`
 * currently includes `src` only, so this is enforced the day `e2e` joins it; the
 * unstubbed empty-watch test below is what checks the live shape today.) */
const DETECTED: WatchProposal = {
  kind: 'elapsed-time',
  source: 'kernel.scope.check_scope:ReaccreditationRequired',
  description: 'the accreditation on this model is older than three years',
  detectedAt: '2026-09-13',
  affected: ['ep-omfv-2020-02-r5'],
};

async function timelineBody(page: import('@playwright/test').Page, programId: string): Promise<TimelineBody> {
  const sessionId = await page.evaluate(() => sessionStorage.getItem('docket-session-id'));
  return (await (await page.request.get(`/api/session/${sessionId}/program/${programId}/timeline`)).json()) as TimelineBody;
}

test.describe('The programme', () => {
  forEachViewport((viewport) => {
    test('Demo B: every episode with the days it lived, months on the connectors, the re-accreditation line', async ({ page }) => {
      const errors = collectConsoleErrors(page);
      await page.goto('/');
      await openDecision(page, 'demo-b');
      await goTo(page, 'Timeline');
      await expect(page.getByRole('heading', { name: 'The programme' })).toBeVisible();
      const nodes = page.getByTestId('timeline-episode');
      await expect(nodes.first()).toBeVisible({ timeout: 15_000 });
      const body = await timelineBody(page, 'prg-omfv');
      const timing = body.timing;
      expect(await nodes.count()).toBe(timing.episodes.length);
      for (const ep of timing.episodes) await expect(page.locator(`[data-episode-days="${ep.id}"] [data-num]`)).toHaveText(`[ ${ep.days} ]`, { useInnerText: true });
      expect(await page.locator('[data-connector-months]').count()).toBe(timing.between.length);
      const since = page.locator('[data-since-last]');
      await expect(since).toContainText(`months since`);
      await expect(since).toContainText(`re-accreditation expected every`);
      if (timing.overdue) await expect(since.locator('[data-sev="blocking"]')).toBeVisible();
      // Containment, measured: at 768 and up the five-episode rail is wider than its own
      // box and it is the RAIL that scrolls (`overflow-x: auto` on the rail, and the
      // page's own scrollWidth still equal to its client width). Below 768 §5a stacks
      // the episodes down the page instead, so there is nothing to scroll sideways at
      // all — the containment proof at 360 is that neither the rail nor the page
      // overflows by a single pixel.
      const rail = await page.getByTestId('timeline-rail').evaluate((el) => ({
        scrollW: el.scrollWidth,
        clientW: el.clientWidth,
        overflowX: getComputedStyle(el).overflowX,
      }));
      const pageWidths = await page.evaluate(() => ({
        scrollW: document.documentElement.scrollWidth,
        clientW: document.documentElement.clientWidth,
      }));
      expect(pageWidths.scrollW).toBe(pageWidths.clientW);
      if (viewport.width >= 768) {
        expect(rail.scrollW).toBeGreaterThan(rail.clientW);
        expect(rail.overflowX).toBe('auto');
      } else {
        expect(rail.scrollW).toBe(rail.clientW);
      }

      // The one Ember is the longest-waiting pending trigger — the earliest `detectedAt`
      // among those filed and never opened — not whichever the store happens to list
      // first, and the view says why beside it.
      const opened = new Set(body.episodes.map((e) => e.refreshedBecause).filter(Boolean));
      const pending = body.refreshTriggers
        .filter((t) => !opened.has(t.id))
        .sort((a, b) => a.detectedAt.localeCompare(b.detectedAt));
      expect(pending.length).toBeGreaterThan(1);
      await expect(page.locator(`[data-pending-trigger="${pending[0].id}"] button[data-ember]`)).toBeVisible();
      await expect(page.locator(`[data-pending-trigger="${pending[0].id}"] [data-ember-reason]`)).toBeVisible();
      await expect(page.locator(`[data-pending-trigger="${pending[1].id}"] button`)).not.toHaveAttribute('data-ember', '');
      expect(await page.locator('[data-ember]').count()).toBe(1);
      await assertFooterSentences(page);
      await assertNoUnbracketedNumerals(page);
      await assertNoProviderStrings(page);
      await assertNoOverrideControl(page);
      await assertBrandConformance(page);
      expect(errors).toEqual([]);
    });
  });

  test('clicking an episode shows the diff panel and names an unknown pairing in words', async ({ page }) => {
    await page.goto('/');
    await openDecision(page, 'demo-b');
    await goTo(page, 'Timeline');
    const nodes = page.getByTestId('timeline-episode');
    await expect(nodes.first()).toBeVisible({ timeout: 15_000 });
    await nodes.nth(2).click();
    const diff = page.getByTestId('diff-panel');
    await expect(diff).toBeVisible();
    await expect(diff).toContainText('field-level pairing unavailable for this diff');
    // The 3×3 sub-episode grid is best-effort discovery, so its standing anti-overclaim
    // caption is required exactly when the grid itself rendered.
    if ((await page.getByText('3×3 verdict grid').count()) > 0) {
      await expect(page.getByText("GAO did not assess or verify the Army's underlying analytical work.")).toBeVisible();
    }
  });

  test('Fields puts the days line away and brings it back', async ({ page }) => {
    await page.goto('/');
    await openDecision(page, 'demo-b');
    await goTo(page, 'Timeline');
    await expect(page.locator('[data-episode-days]').first()).toBeVisible({ timeout: 15_000 });
    await page.getByRole('button', { name: 'Fields' }).click();
    await page.getByRole('checkbox', { name: 'days each episode lived' }).uncheck();
    await expect(page.locator('[data-episode-days]')).toHaveCount(0);
    // The rail itself never goes with it: hiding a field hides that field.
    expect(await page.getByTestId('timeline-episode').count()).toBeGreaterThan(0);
    await page.getByRole('checkbox', { name: 'days each episode lived' }).check();
    await expect(page.locator('[data-episode-days]').first()).toBeVisible();
  });

  test('watch proposals are drafted in blue and recording is a separate act', async ({ page }) => {
    const detected: WatchResponse = { proposals: [DETECTED], filed: [] };
    const afterFiling: WatchResponse = { proposals: [DETECTED], filed: ['rt-stubbed-1'] };
    await page.route('**/api/session/*/program/*/watch*', async (route) => {
      await route.fulfill({ json: route.request().url().includes('file=true') ? afterFiling : detected });
    });
    let timelineReads = 0;
    page.on('request', (r) => {
      if (r.url().includes('/timeline')) timelineReads += 1;
    });
    await page.goto('/');
    await openDecision(page, 'demo-b');
    await goTo(page, 'Timeline');
    await page.getByRole('button', { name: 'Ask the AI what changed' }).click();
    const card = page.locator('[data-watch-proposal]').first();
    await expect(card).toBeVisible({ timeout: 30_000 });
    await expect(card.locator('[data-sev="ai"]')).toBeVisible();
    // The card prints the route's own fields, so a rename shows up as a missing card.
    await expect(card).toContainText(DETECTED.kind);
    await expect(card).toContainText(DETECTED.description);
    await expect(card).toContainText(DETECTED.detectedAt);
    await expect(page.getByText('Detected, not recorded. Recording a trigger is a write; opening a refresh is a human act.')).toBeVisible();
    const file = page.getByRole('button', { name: 'File this trigger' });
    await expect(file).toBeVisible();

    // Filing is a write, so the whole record is re-read: without that, the pending list
    // (and the Ember on it) would still describe the record as it was before the act.
    const before = timelineReads;
    await file.click();
    await expect.poll(() => timelineReads, { timeout: 15_000 }).toBeGreaterThan(before);
  });

  // The unstubbed half of the same act, against the real route: `refresh_watch.detect`
  // is deterministic and finds nothing in either committed store, so what a person
  // actually sees today is the empty answer — said in words, with no card and nothing
  // to file.
  test('asking the real route on Demo B says plainly that nothing was detected', async ({ page }) => {
    await page.goto('/');
    await openDecision(page, 'demo-b');
    await goTo(page, 'Timeline');
    await page.getByRole('button', { name: 'Ask the AI what changed' }).click();
    await expect(page.getByText('no new triggers detected')).toBeVisible({ timeout: 30_000 });
    await expect(page.locator('[data-watch-proposal]')).toHaveCount(0);
    await expect(page.getByRole('button', { name: 'File this trigger' })).toHaveCount(0);
  });

  // Demo A's programme has exactly one episode: one node, no connector, and the server
  // says the same (`between: []`).
  test('a one-episode programme has one node and no connector', async ({ page }) => {
    await page.goto('/');
    await openDecision(page, 'demo-a');
    await goTo(page, 'Timeline');
    await expect(page.getByTestId('timeline-episode')).toHaveCount(1, { timeout: 15_000 });
    const { timing } = await timelineBody(page, 'prg-gcv-2013');
    expect(timing.episodes.length).toBe(1);
    expect(timing.between).toEqual([]);
    await expect(page.locator('[data-connector-months]')).toHaveCount(0);
    await expect(page.getByText(NO_PROGRAMME)).toHaveCount(0);
  });

  test('a session with no programme says so', async ({ page }) => {
    await page.goto('/');
    await openDecision(page, 'new');
    await goTo(page, 'Timeline');
    await expect(page.getByText(NO_PROGRAMME)).toBeVisible();
  });

  // The false sentence must never appear about a decision this view has not read yet:
  // on a hard load of /timeline the session id is restored synchronously and the
  // episode read only starts a frame later. The read is held open here so the in-flight
  // window is long enough to observe.
  test('a hard load of the timeline never claims the decision has no programme', async ({ page }) => {
    await page.goto('/');
    await openDecision(page, 'demo-b');
    let release = () => {};
    const held = new Promise<void>((resolve) => { release = resolve; });
    await page.route('**/api/session/*/episodes', async (route) => {
      await held;
      await route.continue();
    });
    const load = page.goto('/timeline');
    // While the decision is still being read: nothing is claimed about a programme, and
    // the view says what it is doing instead.
    await expect(page.getByText(NO_PROGRAMME)).toHaveCount(0);
    await expect(page.getByText('loading the decision')).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText(NO_PROGRAMME)).toHaveCount(0);
    release();
    await load;
    await expect(page.getByTestId('timeline-episode').first()).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText(NO_PROGRAMME)).toHaveCount(0);
  });
});
