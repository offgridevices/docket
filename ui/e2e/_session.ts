// The one session bootstrap every spec shares from the frame task on: the header's
// decision switcher. Selecting `open:<source>` POSTs /api/session exactly as the old
// SessionPicker did; the select's value becomes `session:<id>` once the copy is open.
import { expect, type Page } from '@playwright/test';

export const DEMO_TITLE = {
  'demo-a': 'Demo A · CBO GCV 2013',
  'demo-b': 'Demo B · OMFV 2019–2023',
  new: 'New session',
} as const;

export async function openDecision(page: Page, source: 'demo-a' | 'demo-b' | 'new'): Promise<void> {
  const select = page.getByLabel('Which decision');
  await expect(select).toBeVisible();
  await select.selectOption(`open:${source}`);
  await expect(select).toHaveValue(/^session:/, { timeout: 15_000 });
}

/** Click a map row by its visible label ("Model", "Package", "What needs you").
 *
 * Matched on the label as a PREFIX, not `{exact: true}`: a row with outstanding acts
 * prints the server's own count inside the link, so the accessible name is "Model 5" as
 * often as it is "Model", and an exact matcher finds the row only while the queue
 * happens to be empty. */
export async function goTo(page: Page, label: string): Promise<void> {
  await page.getByRole('navigation', { name: 'Where this decision stands' })
    .getByRole('link', { name: new RegExp(`^${label}\\b`) }).click();
}

/**
 * Click a view open from the Browse menu, by its name in `ALL_SCREENS`.
 *
 * The one control that reaches all eleven views. `goTo` above cannot: the map carries
 * ten rows, not eleven — Review is not a stage of the ladder — and its home row is
 * labelled "What needs you", so a walk over `ALL_SCREENS` misses two of them. A
 * `page.goto` would reach all eleven but reloads the application, dropping anything held
 * as workspace state (Explain, the open decision's in-memory view state) — so a walk
 * built on it would be testing eleven cold starts rather than one session.
 *
 * `name` is a substring match, not an exact one, which is what lets `'Needs'` find "What
 * needs you" and `'Review'` find "Review, one thing at a time".
 *
 * Lifted out of `coverage.spec.ts` (Task 20), which wrote it first and now imports it:
 * `brand.spec.ts` and `colour.spec.ts` walk the same eleven views for the same reason.
 */
export async function browseTo(page: Page, label: string): Promise<void> {
  await page.getByRole('button', { name: 'Browse the record' }).click();
  await page.getByRole('menu', { name: 'Every view of the record' })
    .getByRole('menuitem', { name: label }).click();
}

/** The heading each view prints — the same string in every state it has, so a spec can
 * wait on it without knowing whether the view has its data yet. `openView` uses it to
 * prove React has committed the view the menu asked for. */
export const VIEW_HEADING = {
  Needs: 'What needs you',
  Request: 'File the request',
  Model: 'Every object in the model',
  Review: 'Read and agree',
  Plan: 'The plan',
  Compute: 'Compute',
  Readiness: 'Readiness',
  Package: 'The package',
  Evidence: 'Evidence',
  Timeline: 'The programme',
  Activity: 'Activity',
} as const;

/**
 * Open a view from Browse and wait until it has finished arriving.
 *
 * WHY THIS IS NOT THREE LINES. A walk that opens a view and asserts against it
 * immediately asserts against the wrong screen, silently, and reports a pass. Three
 * separate races, each of which this was caught doing:
 *
 *   1. `browseTo` returns before React has committed the new view, so the assertions run
 *      against the PREVIOUS one. Waiting on the heading fixes that, and only that.
 *   2. Every view renders its heading in its empty state as well as its loaded one, so a
 *      visible heading says nothing about the data. `networkidle` waits for the view's
 *      own GET, but it fires when the RESPONSE lands, which is one or more microtasks
 *      before React has rendered it — so the read can still catch the loading frame.
 *      Waiting for `role="status"` (the shared `Loading` component, and the only thing
 *      in the tree with that role) to be gone is the signal that the render happened.
 *   3. A rendered response can start the next one — the Timeline's episodes bring its
 *      retro-triggers, the Request's sources bring the recorded-request notice — so one
 *      round of (network, render) is not the end of it.
 *
 * Hence the loop: a round is over when the network is quiet AND nothing is loading, and
 * the view has arrived when two consecutive rounds read the same text. A content marker
 * per view would be the usual answer and cannot work here, because whether a view has
 * any given block is a property of the decision: an absent `[data-pending-trigger]` on
 * Demo A means "this programme has none", and on Demo B it means "not yet".
 *
 * Bounded, and it throws rather than passing quietly if it never converges — a view that
 * is still redrawing after eight rounds is a defect this walk should report, not wait out.
 */
export async function openView(page: Page, screen: keyof typeof VIEW_HEADING): Promise<void> {
  await browseTo(page, screen);
  await expect(
    page.getByRole('heading', { name: VIEW_HEADING[screen], exact: true }),
    `${screen}: the view never arrived`,
  ).toBeVisible({ timeout: 30_000 });

  let last: string | null = null;
  for (let round = 0; round < 8; round++) {
    await page.waitForLoadState('networkidle');
    await expect(page.getByRole('status'), `${screen}: a loading frame never cleared`).toHaveCount(0);
    const text = await page.locator('#view').innerText();
    if (text === last) return;
    last = text;
  }
  throw new Error(`${screen}: the view was still redrawing after eight settled rounds`);
}

/** The current session id the app keeps in sessionStorage. */
export async function currentSessionId(page: Page): Promise<string> {
  const id = await page.evaluate(() => sessionStorage.getItem('docket-session-id'));
  if (!id) throw new Error('no session is open');
  return id;
}
