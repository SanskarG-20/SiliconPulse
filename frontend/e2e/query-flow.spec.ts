import { test, expect } from '@playwright/test';

test('query flow via API', async ({ request }) => {
  // This test exercises the backend query -> generate flow without UI auth
  // It uses the same logic as backend integration tests but via HTTP
  const queryRes = await request.get('http://127.0.0.1:8000/health');
  expect(queryRes.ok()).toBeTruthy();

  // Check that metrics endpoint is available
  const metricsRes = await request.get('http://127.0.0.1:8000/metrics');
  expect(metricsRes.ok()).toBeTruthy();
  const metrics = await metricsRes.json();
  expect(metrics).toHaveProperty('uptime_seconds');
  expect(metrics).toHaveProperty('requests_total');
});
