import { expect, type Page } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { mockApp } from './mock-app';

export const responses = JSON.parse(readFileSync(new URL('../fixtures/api-responses.json', import.meta.url), 'utf8'));

export async function tracker(page: Page) {
  await mockApp(page);
  const errors: string[] = [];
  const unknown: string[] = [];
  const pending = new Set<string>();
  page.on('pageerror', error => errors.push(error.message));
  page.on('request', request => { if (request.url().includes('/api/')) pending.add(request.url()); });
  for (const event of ['requestfinished', 'requestfailed'] as const) page.on(event, request => pending.delete(request.url()));
  await page.route('**/api/**', route => {
    const path = new URL(route.request().url()).pathname.slice(4);
    const key = path.startsWith('/food/calendar/') ? '/food/calendar' : path;
    const fixture = (responses as Record<string, unknown>)[key];
    if (fixture) return route.fulfill({ json: fixture });
    if (path.startsWith('/workouts/')) return route.fulfill({ json: { date: '2026-09-09', workouts: [] } });
    unknown.push(path);
    return route.fulfill({ status: 503, json: { detail: 'No test fixture for ' + path } });
  });
  return async () => {
    await expect.poll(() => pending.size).toBe(0);
    await page.evaluate(() => new Promise<void>(resolve => requestAnimationFrame(() => requestAnimationFrame(() => resolve()))));
    expect(errors).toEqual([]);
    expect(unknown).toEqual([]);
  };
}

