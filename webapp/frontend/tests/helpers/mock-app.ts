import type { Page } from '@playwright/test';

export async function mockApp(page: Page) {
  const state = { active: false, paid: false, checks: 0, creates: 0, statusError: false, checkError: false };
  await page.route('https://telegram.org/js/telegram-web-app.js', route => route.fulfill({ body: '' }));
  await page.route('https://fonts.googleapis.com/**', route => route.fulfill({ body: '' }));
  await page.addInitScript(() => {
    Object.assign(window, { Telegram: { WebApp: {
      initData: 'local-test-only', initDataUnsafe: { user: { id: 42, first_name: 'Тест' } },
      colorScheme: 'light', themeParams: {}, ready() {}, expand() {}, onEvent() {}, offEvent() {},
      HapticFeedback: { impactOccurred() {}, notificationOccurred() {}, selectionChanged() {} },
    } } });
  });
  await page.route('**/api/**', async route => {
    const path = new URL(route.request().url()).pathname;
    const json = (body: unknown, status = 200, headers = {}) => route.fulfill({ status, contentType: 'application/json', headers, body: JSON.stringify(body) });
    if (path === '/api/me') {
      if (!state.active) return json({ detail: 'Subscription required' }, 403, { 'X-Subscription-Status': 'inactive' });
      return json({ user: { user_id: 42 }, subscription_active: true, profile: { onboarding_completed: true } });
    }
    if (path === '/api/subscription-status') return json({ active: state.active }, state.statusError ? 503 : 200);
    if (path === '/api/payment/check') {
      state.checks += 1;
      if (state.checkError) return json({ detail: 'Unavailable' }, 500);
      if (state.paid) state.active = true;
      return json({ status: state.paid ? 'succeeded' : 'pending', subscription_active: state.active });
    }
    if (path === '/api/payment/create') {
      state.creates += 1;
      return json({ detail: 'Test must not create a payment' }, 500);
    }
    if (path === '/api/dashboard') return json({ date: '2026-09-09', food: { entries: [], count: 0 }, sleep: { score: null }, summary: { available: false }, streak: { current: 0, best: 0 } });
    if (path.startsWith('/api/workouts/')) return json({ workouts: [] });
    if (path === '/api/achievements') return json({ achievements: [] });
    return json({});
  });
  return state;
}

