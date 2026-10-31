import { test } from 'node:test';
import assert from 'node:assert/strict';
import { request, ApiError, formatDate, formatMoney } from '../src/api.ts';

test('request sends bearer token and JSON without exposing it in the URL', async () => {
  globalThis.fetch = async (url, init) => {
    assert.equal(url, '/api/jobs/');
    const headers = new Headers(init?.headers);
    assert.equal(headers.get('Authorization'), 'Bearer private-token');
    assert.equal(headers.get('Content-Type'), 'application/json');
    return Response.json({ id: 1 });
  };
  assert.deepEqual(await request('/jobs/', { method: 'POST', body: '{}' }, 'private-token'), { id: 1 });
});
test('validation errors show field details', async () => {
  globalThis.fetch = async () => Response.json({ error: { details: [{ field: 'body.address', message: 'Too long' }] } }, { status: 422 });
  await assert.rejects(request('/jobs/'), /body.address: Too long/);
});
test('expired session retains 401 status for logout handling', async () => {
  globalThis.fetch = async () => Response.json({ detail: 'Token expired' }, { status: 401 });
  await assert.rejects(request('/auth/me'), error => error instanceof ApiError && error.status === 401);
});
test('unreachable backend produces actionable message', async () => {
  globalThis.fetch = async () => { throw new TypeError('Failed to fetch'); };
  await assert.rejects(request('/demo-info'), /port 8001/);
});
test('HTML proxy failures are handled without JSON parse errors', async () => {
  globalThis.fetch = async () => new Response('<html>Bad gateway</html>', { status: 502 });
  await assert.rejects(request('/jobs/mine'), error => error instanceof ApiError && error.status === 502);
});
test('zero amounts and UTC dates are represented correctly', () => {
  assert.match(formatMoney(0), /0/);
  assert.equal(formatMoney(null), 'Set at acceptance');
  assert.equal(formatDate('2026-10-25T10:00:00'), formatDate('2026-10-25T10:00:00Z'));
});
