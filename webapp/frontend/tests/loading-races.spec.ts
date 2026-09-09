import { expect, test, type Page } from '@playwright/test';
import { responses, tracker } from './helpers/tracker';

test.use({ timezoneId: 'Europe/Moscow' });

function deferred() {
  let resolve!: () => void;
  const promise = new Promise<void>(done => { resolve = done; });
  return { promise, resolve };
}

// Wait for fetch parsing and React rendering after deliberately releasing an old response.
async function rendered(page: Page) {
  await page.evaluate(() => new Promise<void>(resolve => requestAnimationFrame(() => requestAnimationFrame(() => resolve()))));
}

const users = responses['/admin/users'];
const detail = (id: number) => ({
  ...responses['/admin/users/42'],
  user: { ...responses['/admin/users/42'].user, user_id: id },
});

test('a filter chosen during the initial admin load is applied and wins over the old response', async ({ page }) => {
  const check = await tracker(page);
  const oldLoad = deferred();
  const started = deferred();
  await page.route(/\/api\/admin\/users\?/, async route => {
    const status = new URL(route.request().url()).searchParams.get('status');
    if (status === 'all') {
      started.resolve();
      await oldLoad.promise;
      return route.fulfill({ json: users });
    }
    return route.fulfill({ json: { ...users, items: [], total: 0 } });
  });
  await page.goto('/admin/console');
  await started.promise;
  await page.getByRole('button', { name: 'Истёкшие', exact: true }).click();
  await expect(page.getByText('Клиенты не найдены')).toBeVisible();
  oldLoad.resolve();
  await check();
  await expect(page.getByText('Клиенты не найдены')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Продлить на 30 дней' })).toHaveCount(0);
});

for (const oldStatus of [200, 503]) {
  test(`a late ${oldStatus} for the previous client cannot replace the selected client or action target`, async ({ page }) => {
    const check = await tracker(page);
    const oldLoad = deferred();
    const started = deferred();
    await page.route('**/api/admin/users/42', async route => {
      started.resolve();
      await oldLoad.promise;
      await route.fulfill({ status: oldStatus, json: oldStatus === 200 ? detail(42) : { detail: 'Старый запрос не прошёл' } });
    });
    await page.route('**/api/admin/users/43', route => route.fulfill({ json: detail(43) }));
    let actionUser: string | undefined;
    await page.route('**/api/admin/users/*/extend', route => {
      actionUser = new URL(route.request().url()).pathname.split('/').at(-2);
      return route.fulfill({ json: { ok: true, expires_at: 1790000000 } });
    });
    await page.goto('/admin/console');
    await started.promise;
    await page.getByRole('button', { name: /ID 43/ }).click();
    await expect(page.getByRole('heading', { name: 'ID 43', exact: true })).toBeVisible();
    oldLoad.resolve();
    await check();
    await expect(page.getByRole('heading', { name: 'ID 43', exact: true })).toBeVisible();
    await expect(page.getByText(/Старый запрос не прошёл/)).toHaveCount(0);
    await page.getByRole('button', { name: 'Продлить на 30 дней' }).click();
    await expect.poll(() => actionUser).toBe('43');
    await expect(page.getByText('Подписка продлена на 30 дней', { exact: true })).toBeVisible();
    await check();
  });
}

test('a failed selected client request never leaves actions for the previous client visible', async ({ page }) => {
  const check = await tracker(page);
  await page.route('**/api/admin/users/43', route => route.fulfill({ status: 503, json: { detail: 'Клиент временно недоступен' } }));
  await page.goto('/admin/console');
  await expect(page.getByRole('heading', { name: 'ID 42', exact: true })).toBeVisible();
  await page.getByRole('button', { name: /ID 43/ }).click();
  await expect(page.getByText(/Клиент временно недоступен/)).toBeVisible();
  await expect(page.getByRole('button', { name: 'Продлить на 30 дней' })).toHaveCount(0);
  await expect(page.getByRole('heading', { name: 'ID 42', exact: true })).toHaveCount(0);
  await check();
});

test('admin search submits on demand and an older search cannot replace its results', async ({ page }) => {
  const check = await tracker(page);
  const oldSearch = deferred();
  const started = deferred();
  const searches: string[] = [];
  await page.route(/\/api\/admin\/users\?/, async route => {
    const q = new URL(route.request().url()).searchParams.get('q') || '';
    searches.push(q);
    if (q === '42') { started.resolve(); await oldSearch.promise; }
    return route.fulfill({ json: q === 'nobody' ? { ...users, items: [], total: 0 } : users });
  });
  await page.goto('/admin/console');
  await expect(page.getByRole('heading', { name: 'ID 42', exact: true })).toBeVisible();
  const search = page.getByPlaceholder('ID, username, телефон');
  await search.fill('42');
  await rendered(page);
  expect(searches).toEqual(['']);
  await search.press('Enter');
  await started.promise;
  await search.fill('nobody');
  await page.getByRole('button', { name: 'Найти', exact: true }).click();
  await expect(page.getByText('Клиенты не найдены')).toBeVisible();
  oldSearch.resolve();
  await check();
  await expect(page.getByText('Клиенты не найдены')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Продлить на 30 дней' })).toHaveCount(0);
});

for (const table of ['payments', 'events'] as const) {
  test(`admin ${table} filters remain correct when responses arrive in reverse order`, async ({ page }) => {
    const check = await tracker(page);
    const oldLoad = deferred();
    const started = deferred();
    const isPayment = table === 'payments';
    const oldFilter = isPayment ? 'pending' : 'resolved';
    const row = isPayment
      ? { payment_id: 'late-payment', user_id: 42, amount: 999, status: 'pending', created_at: 1780000000 }
      : { id: 123, event_type: 'late-event', message: 'Поздняя тревога', resolved: true, created_at: 1780000000 };
    await page.route(new RegExp(`/api/admin/${table}\\?`), async route => {
      if (new URL(route.request().url()).searchParams.get(isPayment ? 'status' : 'state') === oldFilter) {
        started.resolve();
        await oldLoad.promise;
        return route.fulfill({ json: { items: [row], total: 1, limit: 50, offset: 0 } });
      }
      return route.fulfill({ json: { items: [], total: 0, limit: 50, offset: 0 } });
    });
    await page.goto('/admin/console');
    await page.getByRole('button', { name: isPayment ? /^Платежи/ : /^Тревоги/ }).click();
    await page.getByRole('button', { name: isPayment ? 'Pending' : 'Закрытые', exact: true }).click();
    await started.promise;
    await page.getByRole('button', { name: isPayment ? 'Успешные' : 'Открытые', exact: true }).click();
    await expect(page.getByText(isPayment ? 'Платежи не найдены' : 'Тревог нет')).toBeVisible();
    oldLoad.resolve();
    await check();
    await expect(page.getByText(isPayment ? 'late-payment' : 'Поздняя тревога')).toHaveCount(0);
    await expect(page.getByText(isPayment ? 'Платежи не найдены' : 'Тревог нет')).toBeVisible();
  });
}

test('switching clients while a mutation completes keeps the new client selected and blocks overlapping actions', async ({ page }) => {
  const check = await tracker(page);
  const action = deferred();
  const started = deferred();
  await page.route('**/api/admin/users/43', route => route.fulfill({ json: detail(43) }));
  let actions = 0;
  await page.route('**/api/admin/users/42/extend', async route => {
    actions++;
    started.resolve();
    await action.promise;
    await route.fulfill({ json: { ok: true, expires_at: 1790000000 } });
  });
  await page.goto('/admin/console');
  await page.getByRole('button', { name: 'Продлить на 30 дней' }).click();
  await started.promise;
  await expect(page.getByRole('button', { name: 'Отправить ссылку в группу' })).toBeDisabled();
  await page.getByRole('button', { name: /ID 43/ }).click();
  await expect(page.getByRole('heading', { name: 'ID 43', exact: true })).toBeVisible();
  action.resolve();
  await expect(page.getByRole('button', { name: 'Продлить на 30 дней' })).toBeEnabled();
  await check();
  await expect(page.getByRole('heading', { name: 'ID 43', exact: true })).toBeVisible();
  expect(actions).toBe(1);
});

test('a slow previous month cannot clear the calendar for the newly selected month', async ({ page }) => {
  const check = await tracker(page);
  await page.route('**/api/summary/2026-09-09', route => route.fulfill({ json: { date: '2026-09-09', summary: null } }));
  await page.clock.install({ time: new Date('2026-09-09T12:00:00Z') });
  const oldMonth = deferred();
  const started = deferred();
  await page.route('**/api/food/calendar/*/*', async route => {
    const month = new URL(route.request().url()).pathname.split('/').at(-1);
    if (month === '8') { started.resolve(); await oldMonth.promise; }
    await route.fulfill({ json: month === '8' ? { year: 2026, month: 8, days: {} } : responses['/food/calendar'] });
  });
  await page.goto('/calendar');
  await page.getByRole('button', { name: '9', exact: true }).click();
  await page.getByRole('button', { name: 'Закрыть день' }).click();
  await page.getByRole('button', { name: 'Предыдущий месяц' }).click();
  await started.promise;
  await page.getByRole('button', { name: 'Следующий месяц' }).click();
  await expect(page.getByRole('button', { name: '9', exact: true })).toBeVisible();
  oldMonth.resolve();
  await check();
  await page.getByRole('button', { name: '9', exact: true }).click();
  await expect(page.getByText('Курица с гречкой', { exact: true })).toBeVisible();
});

test('the daily summary always belongs to the opened day', async ({ page }) => {
  const check = await tracker(page);
  await page.clock.install({ time: new Date('2026-09-09T12:00:00Z') });
  const oldDay = deferred();
  const started = deferred();
  const day = responses['/food/calendar'].days['2026-09-09'];
  await page.route('**/api/food/calendar/*/*', route => route.fulfill({ json: {
    ...responses['/food/calendar'], days: { '2026-09-08': day, '2026-09-09': day },
  } }));
  await page.route('**/api/summary/2026-09-*', async route => {
    const date = new URL(route.request().url()).pathname.split('/').at(-1);
    if (date === '2026-09-08') { started.resolve(); await oldDay.promise; }
    await route.fulfill({ json: { summary: { analysis: date === '2026-09-08' ? 'Старый итог за восьмое' : 'Итог за девятое' } } });
  });
  await page.goto('/calendar');
  await page.getByRole('button', { name: '8', exact: true }).click();
  await started.promise;
  await page.getByRole('button', { name: 'Закрыть день' }).click();
  await page.getByRole('button', { name: '9', exact: true }).click();
  await expect(page.getByText('Итог за девятое', { exact: true })).toBeVisible();
  oldDay.resolve();
  await check();
  await expect(page.getByText('Итог за девятое', { exact: true })).toBeVisible();
  await expect(page.getByText('Старый итог за восьмое')).toHaveCount(0);
});

for (const [path, endpoint, heading] of [
  ['/food', '**/api/food/today', 'Не удалось загрузить записи'],
  ['/calendar', '**/api/food/calendar/*/*', 'Не удалось загрузить календарь'],
  ['/admin/ops', '**/api/admin/operations', 'Ошибка загрузки'],
] as const) {
  test(`${path} distinguishes an outage from empty data or denied access and supports retry`, async ({ page }) => {
    const check = await tracker(page);
    await page.route(endpoint, route => route.fulfill({ status: 503, json: { detail: 'Временная ошибка сервера' } }));
    await page.goto(path);
    await expect(page.getByRole('heading', { name: heading, exact: true })).toBeVisible();
    await page.unroute(endpoint);
    await page.getByRole('button', { name: 'Попробовать снова' }).click();
    await check();
    await expect(page.getByRole('heading', { name: heading, exact: true })).toHaveCount(0);
  });
}

test('dashboard workouts use the tracker date around local midnight', async ({ page }) => {
  const check = await tracker(page);
  await page.clock.install({ time: new Date('2026-09-08T21:30:00Z') });
  const dates: string[] = [];
  await page.route('**/api/workouts/*', route => {
    dates.push(new URL(route.request().url()).pathname.split('/').at(-1)!);
    return route.fulfill({ json: { workouts: [] } });
  });
  await page.goto('/');
  await check();
  expect(dates).toEqual(['2026-09-09']);
});

test('an old food detail error cannot navigate away from a newly opened entry', async ({ page }) => {
  const check = await tracker(page);
  const oldEntry = deferred();
  const started = deferred();
  const first = responses['/food/entry/1'].entry;
  const second = { ...first, id: 2, description: 'Вторая запись' };
  await page.route('**/api/food/today', route => route.fulfill({ json: { entries: [first, second] } }));
  await page.route('**/api/food/entry/1', async route => {
    started.resolve();
    await oldEntry.promise;
    await route.fulfill({ status: 503, json: { detail: 'Старый запрос' } });
  });
  await page.route('**/api/food/entry/2', route => route.fulfill({ json: { entry: second } }));
  await page.goto('/food');
  await page.getByText(first.description, { exact: true }).click();
  await started.promise;
  await page.goBack();
  await page.getByText(second.description, { exact: true }).click();
  await expect(page).toHaveURL(/\/food\/2$/);
  await expect(page.getByText(second.description, { exact: true })).toBeVisible();
  oldEntry.resolve();
  await check();
  await expect(page).toHaveURL(/\/food\/2$/);
  await expect(page.getByText(second.description, { exact: true })).toBeVisible();
});

test('leaving a pending list cancels the read and returning fetches fresh data', async ({ page }) => {
  const check = await tracker(page);
  const oldList = deferred();
  const started = deferred();
  let reads = 0;
  let cancelled = false;
  page.on('requestfailed', request => {
    if (request.url().endsWith('/api/food/today')) cancelled = true;
  });
  await page.route('**/api/food/today', async route => {
    reads++;
    if (reads === 1) {
      started.resolve();
      await oldList.promise;
      return route.fulfill({ json: { entries: [] } });
    }
    return route.fulfill({ json: { entries: [{ ...responses['/food/entry/1'].entry, description: 'Свежая запись' }] } });
  });
  await page.goto('/food');
  await started.promise;
  await page.getByRole('button').first().click();
  await expect(page.getByRole('heading', { name: /^Сегодня,/ })).toBeVisible();
  await expect.poll(() => cancelled).toBe(true);
  await page.goBack();
  await expect(page.getByText('Свежая запись', { exact: true })).toBeVisible();
  oldList.resolve();
  await check();
  await expect(page.getByText('Свежая запись', { exact: true })).toBeVisible();
  expect(reads).toBe(2);
});

test('a cancellable list read still times out if its response body stalls', async ({ page }) => {
  await tracker(page);
  await page.addInitScript(() => {
    const fetch = window.fetch.bind(window);
    window.fetch = (input, init) => {
      if (String(input).endsWith('/food/today')) {
        return Promise.resolve(new Response(new ReadableStream({
          start(controller) {
            init?.signal?.addEventListener('abort', () => controller.error(new DOMException('Aborted', 'AbortError')));
          },
        })));
      }
      return fetch(input, init);
    };
  });
  await page.clock.install();
  await page.goto('/food');
  await expect(page.getByRole('heading', { name: 'Питание сегодня' })).toBeVisible();
  await page.clock.fastForward(13000);
  await expect(page.getByRole('heading', { name: 'Не удалось загрузить записи' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Попробовать снова' })).toBeEnabled();
});

test('opening a list after losing connectivity shows an error instead of an empty diary', async ({ page }) => {
  const check = await tracker(page);
  const dashboard = responses['/dashboard'];
  await page.route('**/api/dashboard', route => route.fulfill({ json: {
    ...dashboard,
    food: { ...dashboard.food, entries: [1, 2, 3, 4].map(id => ({ ...responses['/food/entry/1'].entry, id })) },
  } }));
  await page.route('**/api/food/today', route => route.abort('internetdisconnected'));
  await page.goto('/');
  await expect(page.getByRole('button', { name: 'Показать все (4)' })).toBeVisible();
  await page.evaluate(() => window.dispatchEvent(new Event('offline')));
  await page.getByRole('button', { name: 'Показать все (4)' }).click();
  await expect(page.getByRole('heading', { name: 'Не удалось загрузить записи' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Нет записей', exact: true })).toHaveCount(0);
  await check();
});
