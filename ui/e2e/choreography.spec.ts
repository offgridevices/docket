// The seven-minute demo's first four minutes, through the new frame: elicit → the
// checklist refuses → confirm the absence → agree the linchpin → write the field →
// approve → MODEL_APPROVED, and the queue drains as you act.
import { expect, test } from '@playwright/test';
import { elicitRecorded } from './_elicit';
import { assertNoProviderStrings, assertNoUnbracketedNumerals, collectConsoleErrors, openDemoASeeded } from './_fixtures';
import { goTo } from './_session';

const NOISE = /status of 409/;

test('elicit → refuse → confirm → agree → write → approve → MODEL_APPROVED', async ({ page, request }) => {
  const errors = collectConsoleErrors(page);
  const body = await elicitRecorded(page);
  expect(body.episode.lifecycleState).toBe('DRAFT');
  await expect(page.locator('header').getByText('recorded')).toBeVisible();

  // The header counter is the server's own `needs.count`, re-read after the write the
  // elicitation just made — polled, because "the queue has caught up" is a state the
  // page arrives at, not one it is in the instant the last card renders.
  const needs = page.getByRole('button', { name: /needs you/ });
  await expect
    .poll(async () => Number((await needs.locator('[data-num]').innerText()).replace(/[^\d]/g, '')), { timeout: 15_000 })
    .toBeGreaterThan(0);

  await goTo(page, 'Model');
  const list = page.locator('[data-gate="G1"]');
  const first = page.waitForResponse((r) => /\/transition$/.test(r.url()));
  await list.getByRole('button', { name: /^Approve the model/ }).click();
  expect((await first).status()).toBe(409);
  await expect(list.locator('[data-refusal]')).toContainText('gaps-confirmed');

  // confirm every absence through the review card the remedy button opens. The remedy is
  // an ADDRESS (`/review/<gap>`, the Review view) and not a popup over the board, so what
  // follows is a page and the way back to the model is the map.
  await list.locator('[data-remedy]').getByRole('button').click();
  await page.locator('[data-review-card]').getByRole('button', { name: 'Confirm gap', exact: true }).click();
  await expect(page.locator('[data-review-card] [data-state="recorded"]')).toContainText('confirmedBy', { timeout: 15_000 });

  await goTo(page, 'Model');
  await expect(list.locator('[data-check="gaps-confirmed"]')).toHaveAttribute('data-satisfied', 'true', { timeout: 15_000 });
  await page.locator('[data-object-type="Assumption"][data-linchpin="true"]').first().getByRole('button', { name: /Read it|Open it/ }).click();
  await page.locator('[data-review-dialog]').getByRole('button', { name: 'Accept', exact: true }).click();
  await expect(page.locator('[data-review-dialog] [data-state="recorded"]')).toBeVisible({ timeout: 15_000 });
  await page.keyboard.press('Escape');
  await page.locator('[data-charter-field="consequencesOfErroneousOutput"] textarea').fill('A solicitation the Army must revise after industry comment.');
  await page.getByRole('button', { name: 'Save the charter' }).click();
  await expect(list.getByRole('button', { name: /^Approve the model/ })).toHaveAttribute('data-ember', '', { timeout: 15_000 });

  const second = page.waitForResponse((r) => /\/transition$/.test(r.url()));
  await list.getByRole('button', { name: /^Approve the model/ }).click();
  expect((await second).status()).toBe(200);
  await expect(page.locator('header').getByText('model approved')).toBeVisible({ timeout: 15_000 });
  // `.last()`: the charter's own "revised" toast is still on screen this soon after.
  await expect(page.locator('[data-toast="done"]').last()).toContainText('MODEL_APPROVED');

  const sessionId = await page.evaluate(() => sessionStorage.getItem('docket-session-id'));
  const ep = await (await request.get(`/api/session/${sessionId}/episode/${body.episode.id}`)).json();
  expect(ep.lifecycleState).toBe('MODEL_APPROVED');
  expect(ep.transitions.filter((t: { refused: boolean }) => t.refused).length).toBe(1);
  await assertNoUnbracketedNumerals(page);
  await assertNoProviderStrings(page);
  expect(errors.filter((e) => !NOISE.test(e))).toEqual([]);
});

// Rewritten for the application frame (the frame task): the same claim — one shared
// session, not six copies — read off the frame's own surfaces. The episode chip
// replaces the old header's "no episode selected", and the authority counters moved
// from the standing rail into the chat column. The start card the session is opened
// from is the Needs view's (Task 8), not the deleted Home screen's.
test('the frame, the chat counters and the map all follow the one open session', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByText('no decision open')).toBeVisible();

  // Task 8 replaced Home with the Needs view: the same three cards, now `[data-start]`,
  // and the card's own button reads "Open it" while nothing is open. The card no longer
  // lists the session's episodes — the frame's episode control does, and that is what
  // the rest of this test reads anyway.
  await page.locator('[data-start="demo-b"]').getByRole('button', { name: /^open it$/i }).click();

  // The frame learned about the session the start card opened — one shared state, not
  // six copies.
  // Demo B's session holds eight episodes, so the header chip is the episode selector;
  // its VALUE is the current episode, which is the thing this test is about.
  const current = page.locator('header').getByLabel('Episode');
  await expect(current).toHaveValue(/^ep-omfv/);

  // …and it survives navigation to a view that never opened a session itself.
  await page.getByRole('link', { name: /Readiness/ }).click();
  await expect(current).toHaveValue(/^ep-omfv/);
  await expect(page.getByTestId('authority-counters')).toContainText(/by kernel \[\s*[1-9]/, {
    timeout: 15_000,
  });
});

// [plan 07 Task 9 Part B; extended by the "weights" task] The continuation of the
// first test above: past G1 approval (which that test deliberately does not reach —
// its own comment says why) into a FULL live G1 round trip, using the shared walk
// `openDemoASeeded` builds (`_fixtures.ts`) so a figure and a smoke test can never
// disagree about what state this produces. Asserts the walk's own documented
// contract rather than re-deriving it: `MODEL_APPROVED` is real (read back from the
// transition record, not the client's belief), a human-authored `WeightSet` is real
// (read back from the graph, not the route's own response trusted a second time),
// and the stop at `plan-propose` names the actual, current gap — no `Model`/
// evaluator a freshly elicited episode could use, NOT the `WeightSet` gap this task
// closed — rather than papering over it.
test('the live G1 round trip reaches MODEL_APPROVED, authors a WeightSet, then stops at the documented wall', async ({
  page,
  request,
}) => {
  const consoleErrors = collectConsoleErrors(page);
  const result = await openDemoASeeded(page);

  expect(result.reachedState).toBe('MODEL_APPROVED');
  expect(result.weightSetId).toBe(`ws-${result.episodeId}-human`);
  expect(result.stoppedAt).toBe('plan-propose');
  expect(result.stopReason ?? '').toContain('evaluator');
  expect(result.stopReason ?? '').not.toContain('has no weight sets');

  // Read the record back independently, through the API rather than trusting the
  // helper's own return value a second time.
  const episode = await (
    await request.get(`/api/session/${result.sessionId}/episode/${result.episodeId}`)
  ).json();
  expect(episode.lifecycleState).toBe('MODEL_APPROVED');
  const approval = episode.transitions.find((t: { to: string }) => t.to === 'MODEL_APPROVED');
  expect(approval).toBeTruthy();
  expect(approval.refused).toBe(false);
  expect(approval.checksUnsatisfied).toEqual([]);
  expect(approval.actor.actorType).toBe('human');
  expect(episode.weightSets).toContain(result.weightSetId);

  const weightSet = await (
    await request.get(`/api/session/${result.sessionId}/object/${result.weightSetId}`)
  ).json();
  expect(weightSet.authorType).toBe('human');
  expect(weightSet.object.method).toBe('stated');
  const weights = weightSet.object.weights as Record<string, number>;
  expect(Object.keys(weights).sort()).toEqual([...episode.objectives].sort());
  expect(
    Object.values(weights).reduce((a: number, b: number) => a + b, 0),
  ).toBeCloseTo(1, 6);

  // The session still holds Demo A's own seeded episode too — this walk adds a
  // second episode, it does not replace the first.
  const { episodes } = await (
    await request.get(`/api/session/${result.sessionId}/episodes`)
  ).json();
  expect(episodes.some((e: { id: string }) => e.id === 'ep-cbo-2013')).toBe(true);

  // [ruling, plan 07 Task 9 review REFUSAL_NETWORK_NOISE] `openDemoASeeded` makes no
  // call this suite expects to be refused, so no exemption is needed here — a
  // console error at any point would be a real regression.
  expect(consoleErrors).toEqual([]);
});
