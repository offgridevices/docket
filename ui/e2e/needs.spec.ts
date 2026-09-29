// What needs you (spec §8) — the first view of the combined design, and the first screen
// a visitor sees. Three things are being asserted here: the queue is the record's own
// list of outstanding human acts (never a to-do list this UI keeps), the one Ember on the
// view sits on the first of them, and the three ways into a decision are on the same page
// when nothing is open yet.
//
// Two departures from the task brief's literal spec text, both because the record says
// otherwise and the record wins:
//   - the episodes table asserts EIGHT rows for Demo B, not five. `prg-omfv` lists five
//     episodes, but the session's copy of the store holds eight `DecisionEpisode`s: the
//     three `-r4-ce/-dc/-fs` what-if episodes belong to no programme. The table's heading
//     is "Episodes in this decision", the route it reads is `/session/{s}/episodes`, and
//     that route returns every episode in the session — so five would be asserting a
//     filter this view does not (and should not) apply.
//   - the Fields test drives Demo B's `refresh-proposed` card rather than Demo A's
//     `signature` card. "Which part of the record" is `NeedsItem.objectId`, and a
//     whole-episode act (signing) has none — the chip is correctly absent there, so a
//     card that names an object is the only honest place to prove the field appears.

import { expect, test } from '@playwright/test';
import { assertBrandConformance } from './_brand';
import { assertFooterSentences, assertNoOverrideControl, assertNoProviderStrings, assertNoUnbracketedNumerals, collectConsoleErrors, forEachViewport } from './_fixtures';
import { currentSessionId, openDecision } from './_session';

test.describe('What needs you', () => {
  forEachViewport(() => {
    test('Demo A needs one signature; the card names who it waits on and goes to the package', async ({ page }) => {
      const errors = collectConsoleErrors(page);
      await page.goto('/');
      await openDecision(page, 'demo-a');
      await expect(page.getByRole('heading', { name: 'What needs you' })).toBeVisible();
      await expect(page.locator('[data-bignum]')).toHaveText('1');
      const cards = page.locator('[data-queue-card][data-actionable="true"]');
      await expect(cards).toHaveCount(1);
      await expect(cards.first()).toHaveAttribute('data-kind', 'signature');
      await expect(cards.first()).toContainText('waiting on the decision authority');
      await expect(cards.first().locator('[data-age]')).toContainText('waiting');
      const button = cards.first().getByRole('button', { name: 'Open the package' });
      await expect(button).toHaveAttribute('data-ember', '');
      await assertFooterSentences(page);
      await assertNoUnbracketedNumerals(page);
      await assertNoProviderStrings(page);
      await assertNoOverrideControl(page);
      await assertBrandConformance(page);
      await button.click();
      await expect(page).toHaveURL(/\/package$/);
      expect(errors).toEqual([]);
    });
  });

  test('Demo B lists dispatch first, collapses blocking findings per rule with a count, and greys the later steps', async ({ page }) => {
    await page.goto('/');
    await openDecision(page, 'demo-b');
    const cards = page.locator('[data-queue-card][data-actionable="true"]');
    await expect(cards.first()).toHaveAttribute('data-kind', 'dispatch');
    // Five rules, one row each, standing for 146 findings between them — the grouping
    // `kernel.queue` does, asserted at its exact size so a regrouping cannot pass.
    const findings = page.locator('[data-queue-card][data-kind="blocking-finding"]');
    await expect(findings).toHaveCount(5);
    await expect(findings.first().locator('[data-count]')).toBeVisible();
    const later = page.locator('[data-queue-card][data-actionable="false"]');
    await expect(later).toHaveCount(2);
    await expect(page.getByRole('heading', { name: 'Waiting for an earlier step' })).toBeVisible();
    await expect(later.first()).toContainText('unlocks once');
    await assertNoUnbracketedNumerals(page);
  });

  test('a send-back leads the queue and the signature is greyed, waiting on it', async ({ page, request }) => {
    await page.goto('/');
    await openDecision(page, 'demo-a');
    const session = await currentSessionId(page);
    const filed = await request.post(`/api/session/${session}/episode/ep-cbo-2013/send-back`, {
      data: { reason: 'The cost basis needs a source a reader can check.' },
    });
    expect(filed.status()).toBe(200);
    await page.reload();
    const acts = page.locator('[data-queue-card][data-actionable="true"]');
    await expect(acts).toHaveCount(1);
    await expect(acts.first()).toHaveAttribute('data-kind', 'sent-back');
    await expect(acts.first().getByRole('button')).toHaveAttribute('data-ember', '');
    // The RECORD says the signature is unavailable — `commit.sign` refuses while a return
    // stands — so `kernel.queue` sends the row down as not actionable, with the words for
    // what unlocks it. The view pairs nothing of its own any more.
    const signature = page.locator('[data-queue-card][data-kind="signature"]');
    await expect(signature).toHaveAttribute('data-actionable', 'false');
    await expect(signature).toContainText('unlocks once the send-back is answered');
    await expect(page.getByRole('heading', { name: 'Waiting for an earlier step' })).toBeVisible();
    // …and it is not counted: one thing waits on a person, not two.
    await expect(page.locator('[data-bignum]')).toHaveText('1');
    await expect(page.getByText('You can do them in any order.')).toBeVisible();
  });

  test('a decision with nothing left for a person says so, and lights nothing', async ({ page, request }) => {
    await page.goto('/');
    await openDecision(page, 'demo-a');
    const session = await currentSessionId(page);
    // The one terminal state this session copy can be driven into through a route that
    // exists today: `VOID` has no gate checks and is human-only, and `kernel.queue`
    // treats every terminal state alike — nothing is left for a person. Signing would be
    // the truer end of the walk, and there is no `POST …/sign` until Task 15; see the
    // fix report. Nothing outside this test's own copy of the store is touched.
    const voided = await request.post(`/api/session/${session}/episode/ep-cbo-2013/transition`, {
      data: { to: 'VOID' },
    });
    expect(voided.status()).toBe(200);
    await page.reload();
    await expect(page.getByText('Nothing is waiting on a person in this decision.')).toBeVisible();
    await expect(page.locator('[data-queue-card]')).toHaveCount(0);
    await expect(page.locator('[data-bignum]')).toHaveText('0');
    // The Ember is the act to do next, and there is none — zero is the right answer.
    await expect(page.locator('[data-ember]')).toHaveCount(0);
    await assertBrandConformance(page);
  });

  test('the Fields control adds and removes a card field, and the choice survives a reload', async ({ page }) => {
    await page.goto('/');
    await openDecision(page, 'demo-b');
    const card = page.locator('[data-queue-card][data-kind="refresh-proposed"]').first();
    // Nothing is stored until a person actually chooses something: the defaults are the
    // defaults, not a preference this browser has expressed.
    expect(await page.evaluate(() => localStorage.getItem('docket.fields.queue'))).toBeNull();
    await expect(card.locator('[data-field="where"]')).toHaveCount(0);
    await page.getByRole('button', { name: 'Fields' }).click();
    await page.getByRole('checkbox', { name: 'which part of the record' }).check();
    await expect(card.locator('[data-field="where"]')).toBeVisible();
    await page.reload();
    await expect(page.locator('[data-queue-card][data-kind="refresh-proposed"]').first().locator('[data-field="where"]')).toBeVisible();
    expect(await page.evaluate(() => JSON.parse(localStorage.getItem('docket.fields.queue') ?? '{}').where)).toBe(true);
  });

  test('with no decision open the view offers the three ways in', async ({ page }) => {
    await page.goto('/');
    await expect(page.getByText('Nothing is open yet')).toBeVisible();
    await expect(page.locator('[data-start="demo-a"]')).toBeVisible();
    await expect(page.locator('[data-start="demo-b"]')).toBeVisible();
    await expect(page.locator('[data-start="new"]')).toBeVisible();
    await page.locator('[data-start="demo-b"]').getByRole('button').click();
    // The header's own episode control, which for a session holding more than one
    // episode is a select — a closed select's options are never "visible", so its value
    // is what says the frame moved to Demo B's live episode.
    await expect(page.getByLabel('Episode')).toHaveValue('ep-omfv-2020-02-r5', { timeout: 15_000 });
  });

  test('an unbuilt store shows the sentence and the build command, and a 409 is printed verbatim', async ({ page }) => {
    const message = 'demo store not built: /repo/demos/a_cbo_gcv_2013/out/graph';
    await page.route('**/api/health', async (route) => {
      const response = await route.fetch();
      const body = await response.json();
      body.demoStores = { ...body.demoStores, 'demo-a': false };
      await route.fulfill({ response, json: body });
    });
    await page.route('**/api/session', async (route) => {
      if (route.request().method() !== 'POST') return route.fallback();
      await route.fulfill({ status: 409, json: { error: 'demo-not-built', message } });
    });
    await page.goto('/');
    const card = page.locator('[data-start="demo-a"]');
    await expect(card).toContainText("Demo A's store has not been built. Run `uv run python -m demos.a_cbo_gcv_2013.run`.");
    await card.getByRole('button', { name: 'Build now' }).click();
    await expect(card.getByText(message, { exact: true })).toBeVisible();
  });

  test('a backend that does not answer and a refused config each print their fixed sentence', async ({ page }) => {
    await page.route('**/api/health', async (route) => {
      const response = await route.fetch();
      const body = await response.json();
      body.backend = { ...body.backend, reachable: false };
      body.configRefused = true;
      body.configRefusedMessage = 'model x matches a denylisted family';
      await route.fulfill({ response, json: body });
    });
    await page.goto('/');
    await expect(page.getByText('No backend answered the health probe. Open Settings for the reason it gave.')).toBeVisible();
    await expect(page.getByText('The configured model was refused by policy. Open Settings for the reason.')).toBeVisible();
    await expect(page.getByText('matches a denylisted family')).toHaveCount(0);
  });

  test('the episodes table lists every episode with its state and its last hash in full', async ({ page }) => {
    await page.goto('/');
    await openDecision(page, 'demo-b');
    const rows = page.locator('[data-episode-row]');
    await expect(rows).toHaveCount(8);
    await expect(rows.first()).toContainText('superseded');
    await expect(rows.last()).toContainText('plan approved');
  });
});
