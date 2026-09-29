// A thin fetch wrapper. It does not compute anything: every response body is handed
// back as-is (parsed JSON, nothing rounded or reshaped), because the values inside it
// are what a <Num> is allowed to print unchanged. Its only job is turning the API's
// error-handler table (plan Task 1 Step 7) into a typed exception the rest of the UI
// can branch on without re-parsing a response body at every call site.

import type { ApiErrorBody } from '../types/api';

export const API_BASE = '/api';

export class ApiError extends Error {
  readonly status: number;
  readonly body: ApiErrorBody;

  constructor(status: number, body: ApiErrorBody) {
    super(body.message ?? body.error ?? `request failed with ${status}`);
    this.name = 'ApiError';
    this.status = status;
    this.body = body;
  }
}

/** True when the service is not reachable at all — no server, wrong port, offline —
 * as distinct from an `ApiError`, which means the server answered and refused. The
 * distinction matters to every screen's empty state: "the API is absent" renders a
 * placeholder (per plan Task 5), "the API refused" renders the refusal itself. */
export class ApiUnreachable extends Error {
  constructor(cause: unknown) {
    super('the docket API is not reachable');
    this.name = 'ApiUnreachable';
    this.cause = cause;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      ...init,
      headers: { 'content-type': 'application/json', ...init?.headers },
    });
  } catch (err) {
    throw new ApiUnreachable(err);
  }

  if (!res.ok) {
    let body: ApiErrorBody;
    try {
      body = (await res.json()) as ApiErrorBody;
    } catch {
      body = { error: 'unknown', message: res.statusText };
    }
    throw new ApiError(res.status, body);
  }

  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export function apiGet<T>(path: string): Promise<T> {
  return request<T>(path, { method: 'GET' });
}

export function apiPost<T>(path: string, body?: unknown): Promise<T> {
  return request<T>(path, { method: 'POST', body: body === undefined ? undefined : JSON.stringify(body) });
}

export function apiPut<T>(path: string, body?: unknown): Promise<T> {
  return request<T>(path, { method: 'PUT', body: body === undefined ? undefined : JSON.stringify(body) });
}

export function apiDelete<T>(path: string): Promise<T> {
  return request<T>(path, { method: 'DELETE' });
}

/** `request`'s JSON parsing does not fit the one route that answers plain text
 * (`GET /session/{s}/package/{pkg}/text` — `PlainTextResponse`, `text/markdown`; plan
 * Task 8's Package screen). Same error handling as `request` (an unreachable server
 * throws `ApiUnreachable`, a non-2xx status throws `ApiError`, best-effort JSON body if
 * the server sent one), the body is just read as text instead of parsed as JSON. */
export async function apiGetText(path: string): Promise<string> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, { method: 'GET' });
  } catch (err) {
    throw new ApiUnreachable(err);
  }
  if (!res.ok) {
    let body: ApiErrorBody;
    try {
      body = (await res.json()) as ApiErrorBody;
    } catch {
      body = { error: 'unknown', message: res.statusText };
    }
    throw new ApiError(res.status, body);
  }
  return res.text();
}
