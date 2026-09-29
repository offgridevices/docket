// The one bootstrap the Model, Review and choreography specs share: a decision open,
// the committed request loaded into the wizard, elicited against the committed recording.
//
// It has to be a real elicitation and not a fixture store, because the G1 board is the
// view for a DRAFT episode and NEITHER committed demo has one — Demo A's single episode
// is `PENDING_SIGNATURE` and every Demo B episode is `SUPERSEDED` or `PLAN_APPROVED`. The
// only way to put a DRAFT episode in front of the gate is to elicit one, which is also
// exactly what the seven-minute demo does.
//
// `playwright.config.ts` points `DOCKET_LLM_RECORDING` at
// `tests/fixtures/recorded/elicit.json` and runs the server in recorded mode, so this
// reaches no network: `routes/agent._settings_for` forces the recorded backend whenever
// the server is in recorded mode, and the fixture answers the exact prompt the loaded
// request produces (`GET /api/sources`'s `recordedRequest` carries the source artefact
// and the policy id it was recorded under, and its own `answerRecorded` flag says
// whether the configured recording holds the response).
import { expect, type Page } from '@playwright/test';
import { openDecision } from './_session';

/** Whoever asked for the trade study. Typed by the test because the wizard has no default
 * for it and the server refuses a blank one — `Charter.authority.signer` is a claim about
 * a person, and the operator running a demo is not that person. */
export const REQUESTED_BY = 'NGCV CFT';

export interface ElicitBody {
  episode: { id: string; lifecycleState: string; charter: string };
  objects: { id: string; type: string; provenance: { locator: string | null } | null }[];
  gaps: string[];
}

/** Open a decision of `source` if this tab has none yet — a no-op on a tab that already
 * has one.
 *
 * Reads `sessionStorage` (the app's own source of truth, the same key `currentSessionId`
 * reads) rather than the switcher's value: the switcher shows an empty value both when
 * there is no session AND, briefly, when there is one whose `<option>` has not arrived
 * yet, because `GET /api/sessions` has not resolved. Asking the select would open a
 * second decision in that window. */
export async function ensureSession(page: Page, source: 'new' | 'demo-a' | 'demo-b' = 'new'): Promise<void> {
  const existing = await page.evaluate(() => sessionStorage.getItem('docket-session-id'));
  if (!existing) await openDecision(page, source);
}

/** Steps 1→3 of the wizard, filled from the server's own recorded request.
 *
 * `baseUrl` is for the two specs that run against a private server of their own
 * (`fallback.spec.ts`, `live.spec.ts`): everything else leaves it empty and gets
 * `playwright.config.ts`'s `baseURL`. */
export async function loadRecordedRequest(page: Page, baseUrl = ''): Promise<void> {
  await page.goto(`${baseUrl}/request?step=1`);
  await page.getByRole('button', { name: 'Load the recorded request' }).click();
  await expect(page.locator('textarea[name="request-text"]')).not.toHaveValue('');
  await page.getByRole('button', { name: 'Next' }).click();
  await page.locator('input[name="requested-by"]').fill(REQUESTED_BY);
  await expect(page.locator('input[name="policy-id"]')).not.toHaveValue('');
  await page.getByRole('button', { name: 'Next' }).click();
  await expect(page.locator('select[name="source-artifact"]')).not.toHaveValue('');
}

/** File the request, end to end: a decision of `source` (a fresh empty one by default),
 * the committed request, one elicitation. Leaves the browser on `/request` step 3 with
 * the drafted cards rendered and the new DRAFT episode current, and hands back the
 * server's own response body so a spec can check the view against what the server
 * actually said rather than against a hand-counted number. */
export async function elicitRecorded(page: Page, source: 'new' | 'demo-a' | 'demo-b' = 'new'): Promise<ElicitBody> {
  await page.goto('/request');
  await ensureSession(page, source);
  await loadRecordedRequest(page);
  const elicited = page.waitForResponse((r) => /\/api\/session\/[^/]+\/elicit$/.test(r.url()) && r.request().method() === 'POST');
  // Case-insensitive and anchored, not `{name: 'ELICIT', exact: true}`: brand v3.0 stops
  // the interface shouting, so this button's visible label changed case. A case-sensitive
  // exact matcher would have silently un-clicked every elicit in the suite rather than
  // failing loudly.
  await page.getByRole('button', { name: /^elicit$/i }).click();
  const response = await elicited;
  expect(response.status(), await response.text()).toBe(200);
  await expect(page.locator('[data-object-id]').first()).toBeVisible({ timeout: 15_000 });
  return (await response.json()) as ElicitBody;
}
