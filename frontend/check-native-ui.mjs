import { chromium } from '@playwright/test';
import assert from 'node:assert/strict';

const browser = await chromium.launch({ channel: 'msedge', headless: true });
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
const errors = [];
page.on('pageerror', (error) => errors.push(error.message));
await page.goto('http://127.0.0.1:8765/');
await page.getByRole('button', { name: 'Full FreqUI', exact: true }).click();
await page.getByText('FreqMyAss · Full FreqUI', { exact: true }).waitFor();
assert.equal(await page.locator('.workspace').count(), 0, 'Guided CSS must not wrap native views');
await page.getByRole('button', { name: 'Research engine', exact: true }).click();
await page.waitForURL('**/backtest', { timeout: 60000 });
await page.getByRole('link', { name: 'Backtest', exact: true }).waitFor();
await page.getByRole('link', { name: 'Download Data', exact: true }).waitFor();
assert.equal(await page.locator('[role="alert"]').filter({ hasText: 'Engine did not' }).count(), 0);
await page.screenshot({ path: '../.runtime/full-frequi-research.png', fullPage: true });
await page.getByRole('button', { name: 'Trading engine', exact: true }).click();
await page.waitForURL('**/trade', { timeout: 60000 });
await page.getByRole('link', { name: 'Dashboard', exact: true }).waitFor();
await page.getByTitle('Toggle Night Mode').click();
assert(await page.locator('html').evaluate((el) => el.classList.contains('dark')));
await page.reload();
await page.getByText('FreqMyAss · Full FreqUI', { exact: true }).waitFor();
assert(await page.locator('html').evaluate((el) => el.classList.contains('dark')));
await page.getByRole('link', { name: 'Dashboard', exact: true }).click();
await page.waitForURL('**/dashboard');
assert.equal(await page.locator('main').getByText('Research Lab', { exact: true }).count(), 0, 'Research engine is not a trading portfolio');
await page.waitForFunction(() => {
  const panels = [...document.querySelectorAll('.vue-grid-item')].map((el) => el.getBoundingClientRect());
  return panels.length > 4 && panels.every((a, i) => panels.slice(i + 1).every((b) =>
    Math.min(a.right, b.right) - Math.max(a.left, b.left) <= 2 ||
    Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top) <= 2));
});
await page.screenshot({ path: '../.runtime/full-frequi-dashboard.png', fullPage: true });
await page.setViewportSize({ width: 390, height: 844 });
await page.waitForTimeout(600);
assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false, 'Native mobile overflow');
await page.getByRole('link', { name: 'Balance', exact: true }).waitFor();
await page.screenshot({ path: '../.runtime/full-frequi-mobile.png', fullPage: true });
await page.getByRole('button', { name: 'QuantStats reports', exact: true }).click();
await page.getByRole('heading', { name: 'Understand every result.' }).waitFor();
assert.equal(await page.locator('.native-workspace').count(), 0);
await page.goto('http://127.0.0.1:8765/?view=setup');
await page.getByRole('button', { name: 'Install Freqtrade command menu', exact: true }).waitFor();
await page.getByText(/Engine running · send \/help/).waitFor();
await browser.close();
assert.deepEqual(errors, [], 'Native UI runtime errors');
console.log('Full FreqUI: both engines, original navigation, persisted view, mobile, report return and Telegram status passed.');
