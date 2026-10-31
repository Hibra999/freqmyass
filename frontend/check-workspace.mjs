import { chromium } from '@playwright/test';
import assert from 'node:assert/strict';
const browser = await chromium.launch({ channel: 'msedge', headless: true });
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
const errors = [];
page.on('pageerror', e => errors.push(e.message));
await page.goto('http://127.0.0.1:8765/');
await page.getByText('A clearer view of your trading.').waitFor();
await page.getByText('539', { exact: false }).first().waitFor();
assert.equal(await page.locator('.workspace').evaluate((el) => getComputedStyle(el).textAlign), 'left');
await page.screenshot({path: '../.runtime/overview.png', fullPage: true});
for (const [view, heading] of [['strategies', 'Find your next edge.'], ['backtesting', 'Test an idea. See the whole picture.'], ['reports', 'Understand every result.'], ['data', 'Your entire market library.'], ['setup', 'Make this workspace yours.']]) {
  await page.goto(`http://127.0.0.1:8765/?view=${view}`);
  await page.getByRole('heading', { name: heading }).waitFor();
  if (view === 'reports') {
    await page.getByText('RECONCILED', {exact: true}).waitFor();
    await page.screenshot({path: '../.runtime/reports.png', fullPage: true});
    await page.getByRole('button', {name: 'QuantStats HTML', exact: true}).click();
    const frame = page.frameLocator('iframe');
    await frame.locator('body').waitFor();
    assert((await frame.locator('body').innerText()).includes('FreqMyAss'));
  }
}
await page.setViewportSize({width: 390, height: 844});
await page.goto('http://127.0.0.1:8765/');
await page.getByRole('button', {name: 'Toggle navigation'}).click();
await page.getByRole('link', {name: 'Backtesting', exact: true}).click();
await page.getByRole('heading', {name: 'Test an idea. See the whole picture.'}).waitFor();
await page.screenshot({path: '../.runtime/mobile.png', fullPage: true});
assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth), false, 'Mobile horizontal overflow');
await browser.close();
assert.deepEqual(errors, [], 'Browser runtime errors');
console.log('Desktop, mobile, reports, iframe and navigation passed.');
