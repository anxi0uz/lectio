import test, { beforeEach } from 'node:test';
import assert from 'node:assert/strict';
import {
  api,
  setAccessToken,
  refreshSession,
  ApiError,
} from '../src/lib/api.js';
const json = (body, status = 200, headers = {}) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json', ...headers },
  });
beforeEach(() => {
  setAccessToken(null);
  globalThis.window = { dispatchEvent() {} };
});

test('parallel requests with an expired session share one rotating refresh and retry with new token', async () => {
  setAccessToken('expired');
  let refreshes = 0,
    oldRequests = 0,
    newRequests = 0;
  globalThis.fetch = async (url, options) => {
    if (url.endsWith('/auth/refresh')) {
      refreshes++;
      await new Promise((r) => setTimeout(r, 10));
      return json({ access_token: 'rotated' });
    }
    if (options.headers.Authorization === 'Bearer expired') {
      oldRequests++;
      return json({ detail: 'expired' }, 401);
    }
    assert.equal(options.headers.Authorization, 'Bearer rotated');
    newRequests++;
    return json({ ok: true });
  };
  const results = await Promise.all([api('/me/dashboard'), api('/me/courses')]);
  assert.deepEqual(results, [{ ok: true }, { ok: true }]);
  assert.equal(refreshes, 1);
  assert.equal(oldRequests, 2);
  assert.equal(newRequests, 2);
});
test('204 response has no JSON body and multipart uses browser-generated boundary', async () => {
  globalThis.fetch = async (url, options) => {
    assert.equal(options.credentials, 'include');
    assert.equal(options.headers['Content-Type'], undefined);
    assert.ok(options.body instanceof FormData);
    return new Response(null, { status: 204 });
  };
  const body = new FormData();
  body.set('file', new Blob(['data']), 'test.mp4');
  assert.equal(await api('/lectures', { method: 'POST', body }), null);
});
test('ambiguous network failure never repeats a creation request', async () => {
  let calls = 0;
  globalThis.fetch = async () => {
    calls++;
    throw new TypeError('Network failure');
  };
  await assert.rejects(
    api('/lectures/import', {
      method: 'POST',
      body: { url: 'https://example.com/video' },
    }),
    (e) => e instanceof ApiError && e.status === 0,
  );
  assert.equal(calls, 1);
});
test('business errors preserve request id and do not automatically retry', async () => {
  let calls = 0;
  globalThis.fetch = async () => {
    calls++;
    return json({ detail: 'pending' }, 409, { 'X-Request-ID': 'request-test' });
  };
  await assert.rejects(
    api('/lectures/id/segments'),
    (e) => e.status === 409 && e.requestId === 'request-test',
  );
  assert.equal(calls, 1);
});
test('a failed refresh ends the session after one retry attempt', async () => {
  let calls = 0,
    expired = 0;
  globalThis.window = {
    dispatchEvent() {
      expired++;
    },
  };
  globalThis.fetch = async () => {
    calls++;
    return json({ detail: 'unauthorized' }, 401);
  };
  await assert.rejects(api('/me/favorites'), (e) => e.status === 401);
  assert.equal(calls, 2);
  assert.equal(expired, 1);
});
