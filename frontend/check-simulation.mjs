import { chromium } from '@playwright/test';
import assert from 'node:assert/strict';

const browser = await chromium.launch({ channel: 'msedge', headless: true });
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
const errors = [];
page.on('pageerror', error => errors.push(error.message));
await page.goto('http://127.0.0.1:8765/?view=simulation');
await page.getByRole('heading', { name: 'Synthetic price paths. Original strategy execution.' }).waitFor();
await page.getByText(/NVIDIA GeForce RTX/).waitFor();
assert(await page.locator('html').evaluate(el => el.classList.contains('dark')));
const runs = await page.evaluate(async () => (await fetch('/workbench/simulations')).json());
const annual = runs.find(run => run.status === 'completed' && run.horizon_days === 365);
assert(annual, 'A completed annual CUDA validation must exist');
await page.getByLabel('Saved simulation').selectOption(annual.id);
await page.getByRole('heading', { name: `${annual.completed.toLocaleString('en-US')} / ${annual.target.toLocaleString('en-US')} paths evaluated` }).waitFor();
for (const regime of ['bear', 'neutral', 'bull']) {
  await page.getByLabel('Market regime').selectOption(regime);
  await page.waitForFunction(() => document.querySelectorAll('.data-table tbody tr').length === 4);
  assert.equal(await page.locator('.data-table tbody').getByText('1 / 0', { exact: true }).count(), 4);
  await page.locator('canvas').first().waitFor();
}
await page.screenshot({ path: '../.runtime/monte-carlo-desktop.png', fullPage: true });
const invalid = await page.evaluate(async () => (await fetch('/workbench/simulations', {
  method: 'POST', headers: { 'Content-Type': 'application/json', 'X-FMA-Request': '1' },
  body: JSON.stringify({ paths: 1000001 }),
})).status);
assert.equal(invalid, 422);
await page.setViewportSize({ width: 390, height: 844 });
await page.waitForTimeout(400);
assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false, 'Simulation mobile overflow');
await page.screenshot({ path: '../.runtime/monte-carlo-mobile.png', fullPage: true });
await browser.close();
assert.deepEqual(errors, [], 'Simulation UI runtime errors');
console.log('CUDA lab: annual results, three regimes, charts, native metrics, dark/mobile layout and API bounds passed.');
