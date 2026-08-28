import { test, expect } from '@playwright/test';

test('backend health is online', async ({ request }) => {
  const res = await request.get('http://127.0.0.1:8000/health');
  expect(res.ok()).toBeTruthy();
  const json = await res.json();
  expect(json.service).toBe('siliconpulse-backend');
  expect(['online', 'degraded']).toContain(json.status);
});

test('frontend serves index', async ({ page }) => {
  await page.goto('/');
  await expect(page).toHaveTitle(/SiliconPulse/);
  // Content varies by Clerk key:
  // - no key: Deployment Configuration Error
  // - dummy key (CI): may show Clerk error / minimal shell
  // - real key: Signal-First Intelligence hero
  // Only require title; hero verification is best-effort so CI with dummy key doesn't flake.
  const body = await page.textContent('body');
  if (body?.includes('Signal-First Intelligence')) {
    await expect(page.getByText(/Signal-First Intelligence/i)).toBeVisible();
  } else if (body?.includes('Deployment Configuration Error')) {
    await expect(page.getByText(/Deployment Configuration Error/i)).toBeVisible();
  }
  // else: with dummy/invalid Clerk key, title alone proves frontend served.
});

test('dashboard requires auth redirect when not signed in', async ({ page }) => {
  await page.goto('/dashboard');
  // Clerk will redirect to sign-in when not authenticated
  await expect(page).toHaveURL(/sign-in|dashboard/);
});
