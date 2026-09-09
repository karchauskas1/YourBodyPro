import { expect, test } from '@playwright/test';
import { tracker } from './helpers/tracker';

test.use({ timezoneId: 'Europe/Moscow' });

for (const [path, heading] of [
  ['/', /^Сегодня,/], ['/food', 'Питание сегодня'], ['/food/add', 'Добавить еду'],
  ['/food/1', 'Прием пищи'], ['/sleep', 'Трекер сна'], ['/workout/add', 'Отметить тренировку'],
  ['/summary', 'Итог дня'], ['/weekly', 'Недельный обзор'], ['/settings', 'Настройки'],
  ['/calendar', 'Календарь питания'], ['/achievements', 'Достижения'], ['/edit-request', 'Изменить запрос'],
  ['/onboarding', 'Добро пожаловать!'], ['/admin', 'Аналитика'], ['/admin/ops', 'Контроль'],
  ['/admin/console', 'Админ-пульт'],
] as const) {
  test(`${path} renders with complete API responses and no runtime errors`, async ({ page }) => {
    const check = await tracker(page);
    await page.goto(path);
    await check();
    await expect(page.getByRole('heading', { name: heading, exact: typeof heading === 'string' })).toBeVisible();
    expect(await page.locator('body').evaluate(element => element.scrollWidth <= window.innerWidth)).toBe(true);
  });
}

test('an entry from an earlier day opens without looking in today’s food', async ({ page }) => {
  const check = await tracker(page);
  await page.route('**/api/food/today', route => route.fulfill({ json: { date: '2026-09-09', entries: [] } }));
  await page.goto('/food/1');
  await check();
  await expect(page.getByRole('heading', { name: 'Прием пищи' })).toBeVisible();
  await expect(page.getByText('Курица с гречкой', { exact: true })).toBeVisible();
});

test('food analysis may take longer than the sign-in timeout and saves only once', async ({ page }) => {
  const check = await tracker(page);
  await page.clock.install({ time: new Date('2026-09-09T13:58:00Z') });
  let release!: () => void;
  const held = new Promise<void>(resolve => { release = resolve; });
  let saves = 0;
  await page.route('**/api/food/text', async route => {
    saves++;
    expect(route.request().postDataJSON().time).toBe('16:45');
    await held;
    await route.fulfill({ json: { success: true, entry_id: 2, analysis: { description: 'Обед', products: [], categories: {} } } });
  });
  await page.goto('/food/add');
  await page.getByText('Описать текстом', { exact: true }).click();
  await page.getByPlaceholder('Например: овсянка с ягодами и мёдом').fill('Обед: курица с гречкой');
  const request = page.waitForRequest('**/api/food/text');
  await page.getByRole('button', { name: 'Сохранить', exact: true }).click();
  await request;
  await page.clock.fastForward(20000);
  await expect(page.getByRole('button', { name: 'Загрузка...' })).toBeDisabled();
  release();
  await expect(page.getByRole('heading', { name: /^Сегодня,/ })).toBeVisible();
  expect(saves).toBe(1);
  await check();
});

test('a food analysis failure leaves text in place for a successful retry', async ({ page }) => {
  const check = await tracker(page);
  let failing = true;
  await page.route('**/api/food/text', route => route.fulfill(failing
    ? { status: 503, json: { detail: 'Анализ временно недоступен. Попробуйте ещё раз.' } }
    : { json: { success: true, entry_id: 2 } }));
  await page.goto('/food/add');
  await page.getByText('Описать текстом', { exact: true }).click();
  await page.getByPlaceholder('Например: овсянка с ягодами и мёдом').fill('Обед: курица');
  await page.getByRole('button', { name: 'Сохранить', exact: true }).click();
  await expect(page.getByText('Анализ временно недоступен. Попробуйте ещё раз.')).toBeVisible();
  await expect(page.getByPlaceholder('Например: овсянка с ягодами и мёдом')).toHaveValue('Обед: курица');
  failing = false;
  await page.getByRole('button', { name: 'Сохранить', exact: true }).click();
  await expect(page.getByRole('heading', { name: /^Сегодня,/ })).toBeVisible();
  await check();
});
