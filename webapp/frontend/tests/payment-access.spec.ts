import { expect, test, type Page } from '@playwright/test';

async function mockApp(page: Page) {
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

const checkButton = (page: Page) => page.getByRole('button', { name: 'Я уже оплатил — проверить доступ' });
const dashboard = (page: Page) => page.getByRole('heading', { name: /^Сегодня,/ });

test('an already active subscriber opens the tracker without a paywall', async ({ page }) => {
  const state = await mockApp(page);
  state.active = true;
  await page.goto('/');
  await expect(dashboard(page)).toBeVisible();
  await expect(page.getByText('Этот котик грустит')).toHaveCount(0);
  expect(state.creates).toBe(0);
});

test('an administrator can open the console without a paid subscription', async ({ page }) => {
  await mockApp(page);
  await page.route('**/api/admin/me', route => route.fulfill({
    contentType: 'application/json', body: JSON.stringify({ admin: true, user: { user_id: 42 } }),
  }));
  await page.goto('/admin/console');
  await expect(page.getByRole('heading', { name: 'Админ-пульт' })).toBeVisible();
  await expect(page.getByText('Этот котик грустит')).toHaveCount(0);
});

for (const failure of ['network', '500', '401', '403', 'invalid-json']) {
  test(`${failure} during sign-in never claims there is no subscription`, async ({ page }) => {
    await mockApp(page);
    await page.route('**/api/me', route => failure === 'network'
      ? route.abort()
      : route.fulfill({ status: failure === 'invalid-json' ? 200 : Number(failure), contentType: 'application/json', body: failure === 'invalid-json' ? '<html>bad gateway</html>' : '{}' }));
    await page.goto('/');
    await expect(page.getByRole('heading', { name: 'Ошибка', exact: true })).toBeVisible();
    await expect(page.getByText('Этот котик грустит')).toHaveCount(0);
    await expect(page.getByRole('button', { name: 'Попробовать снова' })).toBeEnabled();
  });
}

test('retrying a failed sign-in restores access without paying again', async ({ page }) => {
  const state = await mockApp(page);
  await page.route('**/api/me', route => route.abort());
  await page.goto('/');
  await expect(page.getByRole('button', { name: 'Попробовать снова' })).toBeVisible();
  await page.unroute('**/api/me');
  state.active = true;
  await page.getByRole('button', { name: 'Попробовать снова' }).click();
  await expect(dashboard(page)).toBeVisible();
  expect(state.creates).toBe(0);
});

test('the first subscription slide can recover a payment completed earlier', async ({ page }) => {
  const state = await mockApp(page);
  await page.goto('/');
  await expect(checkButton(page)).toBeVisible();
  state.active = true;
  await checkButton(page).click();
  await expect(dashboard(page)).toBeVisible();
  expect(state.checks).toBe(0);
  expect(state.creates).toBe(0);
});

test('a newly succeeded payment reloads into the tracker', async ({ page }) => {
  const state = await mockApp(page);
  state.paid = true;
  await page.goto('/');
  await checkButton(page).click();
  await expect(dashboard(page)).toBeVisible();
  expect(state.checks).toBe(1);
  expect(state.creates).toBe(0);
});

for (const failure of ['pending', 'status-error', 'payment-error']) {
  test(`${failure} leaves a visible message and a working retry`, async ({ page }) => {
    const state = await mockApp(page);
    state.statusError = failure === 'status-error';
    state.checkError = failure === 'payment-error';
    await page.goto('/');
    await checkButton(page).click();
    await expect(page.getByRole('status')).toContainText(failure === 'pending' ? 'Оплата пока не подтверждена' : 'Не удалось проверить оплату');
    await expect(checkButton(page)).toBeEnabled();
    expect(await page.locator('body').evaluate(el => el.scrollWidth <= window.innerWidth)).toBe(true);
    state.statusError = state.checkError = false;
    state.active = true;
    await checkButton(page).click();
    await expect(dashboard(page)).toBeVisible();
    expect(state.creates).toBe(0);
  });
}

test('a slow old sign-in cannot overwrite a successful retry', async ({ page }) => {
  const state = await mockApp(page);
  state.active = true;
  await page.clock.install();
  let release!: () => void;
  const held = new Promise<void>(resolve => { release = resolve; });
  await page.route('**/api/me', async route => {
    await held;
    await route.fulfill({ status: 500, contentType: 'application/json', body: '{}' });
  }, { times: 1 });
  const firstRequest = page.waitForRequest('**/api/me');
  await page.goto('/');
  await firstRequest;
  await page.clock.fastForward(11000);
  await page.getByRole('button', { name: 'Повторить', exact: true }).click();
  await expect(dashboard(page)).toBeVisible();
  const oldResponse = page.waitForResponse(response => response.url().endsWith('/api/me') && response.status() === 500);
  release();
  await oldResponse;
  await expect(dashboard(page)).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Ошибка', exact: true })).toHaveCount(0);
});

test('a stalled response body times out and releases the payment button', async ({ page }) => {
  await mockApp(page);
  await page.addInitScript(() => {
    const realFetch = window.fetch.bind(window);
    window.fetch = async (input, init) => {
      if (String(input).endsWith('/subscription-status')) {
        return new Response(new ReadableStream({
          start(controller) {
            init?.signal?.addEventListener('abort', () => controller.error(new DOMException('Aborted', 'AbortError')));
          },
        }), { status: 200 });
      }
      return realFetch(input, init);
    };
  });
  await page.clock.install();
  await page.goto('/');
  await checkButton(page).click();
  await expect(page.getByRole('button', { name: 'Загрузка...' })).toBeDisabled();
  await page.clock.fastForward(13000);
  await expect(page.getByRole('status')).toContainText('Не удалось проверить оплату');
  await expect(checkButton(page)).toBeEnabled();
});
