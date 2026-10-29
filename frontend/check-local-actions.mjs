import { chromium } from '@playwright/test';
import assert from 'node:assert/strict';

const browser = await chromium.launch({ channel: 'msedge', headless: true });
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
const errors = [];
page.on('pageerror', (error) => errors.push(error.message));
await page.goto('http://127.0.0.1:8765/?view=reports');
await page.getByText('Generate QuantStats for a saved engine archive', { exact: true }).click();
const state = await (await page.request.get('http://127.0.0.1:8765/workbench/status')).json();
const report = state.reports.find((r) => r.strategy === 'SingleB_FixedRR' && r.start.startsWith('2025-01-01'));
assert(report, 'Run the engine smoke test before this browser check.');
await page.getByLabel(/^Engine archive/).selectOption(report.file);
const responsePromise = page.waitForResponse((r) => r.url().endsWith('/workbench/reports/create'));
await page.getByRole('button', { name: 'Generate report', exact: true }).click();
const response = await responsePromise;
assert.equal(response.status(), 200);
const submitted = await response.json();
let job;
for (let attempt = 0; attempt < 60; attempt++) {
  const status = await (await page.request.get('http://127.0.0.1:8765/workbench/status')).json();
  job = status.jobs.find((j) => j.id === submitted.id);
  if (!['queued', 'running'].includes(job.status)) break;
  await page.waitForTimeout(1000);
}
assert.equal(job.status, 'completed', job.message);
const html = await page.request.get(`http://127.0.0.1:8765/workbench/reports/${job.results[0]}/html`);
assert.equal(html.status(), 200);
assert((await html.text()).includes('initial capital'));
await page.goto('http://127.0.0.1:8765/?view=backtesting');
await page.getByLabel(/^Exchange/).selectOption('kucoin');
await page.getByText('Advanced configuration', { exact: true }).click();
await page.getByRole('button', { name: 'Check and select available markets', exact: true }).click();
await page.getByRole('status').filter({ hasText: 'Available markets selected.' }).waitFor({ timeout: 60000 });
assert((await page.locator('textarea').first().inputValue()).includes('BTC/USDT'));
assert((await page.locator('body').innerText()).includes('Exchange no longer returns market metadata.'));
await browser.close();
assert.deepEqual(errors, []);
console.log('Saved-archive report generation and visible market exclusions passed.');
