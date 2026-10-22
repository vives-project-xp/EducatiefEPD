// Browser regression test against disposable fixtures from main_browser_seed.py.
// Usage: node tests/main-browser.mjs <fixture.json> <artifact-directory>
import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { mkdir, mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

const fixture = JSON.parse(await readFile(process.argv[2], 'utf8'));
const artifacts = process.argv[3];
await mkdir(artifacts, { recursive: true });
const base = process.env.EPD_TEST_URL || 'http://127.0.0.1:8018';
if (!['127.0.0.1', 'localhost'].includes(new URL(base).hostname)) throw Error('Local test server required');
const profile = await mkdtemp(join(tmpdir(), 'epd-main-browser-'));
const port = 20000 + Math.floor(Math.random() * 30000);
const chrome = process.env.CHROME_PATH || 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe';
const browser = spawn(chrome, [
  '--headless=new', '--no-first-run', '--disable-gpu',
  `--remote-debugging-port=${port}`, `--user-data-dir=${profile}`, 'about:blank',
], { windowsHide: true, stdio: 'ignore' });
const pause = ms => new Promise(resolve => setTimeout(resolve, ms));
let socket;
let id = 0;
const pending = new Map();
const errors = [];
function command(method, params = {}) {
  const key = ++id;
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => { pending.delete(key); reject(Error(`CDP timeout: ${method}`)); }, 15000);
    pending.set(key, { resolve, reject, timer });
    socket.send(JSON.stringify({ id: key, method, params }));
  });
}
async function evaluate(expression) {
  const result = await command('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true });
  if (result.exceptionDetails) throw Error(result.exceptionDetails.text);
  return result.result?.value;
}
async function waitFor(expression, label) {
  const deadline = Date.now() + 15000;
  while (Date.now() < deadline) {
    if (await evaluate(expression)) return;
    await pause(100);
  }
  throw Error(`Timeout: ${label}`);
}
async function navigate(path) {
  await command('Page.navigate', { url: base + path });
  await waitFor(`location.pathname === ${JSON.stringify(path)} && document.readyState === 'complete'`, path);
}
async function click(selector) {
  await evaluate(`document.querySelector(${JSON.stringify(selector)}).click()`);
}
async function enter(selector, value) {
  await evaluate(`(() => {
    const input = document.querySelector(${JSON.stringify(selector)});
    input.value = ${JSON.stringify(value)};
    input.dispatchEvent(new Event('input', { bubbles: true }));
  })()`);
}
async function screenshot(name) {
  const result = await command('Page.captureScreenshot', { format: 'png', captureBeyondViewport: true });
  await writeFile(join(artifacts, name), Buffer.from(result.data, 'base64'));
}
try {
  let target;
  for (let attempt = 0; attempt < 60; attempt++) {
    try {
      const response = await fetch(`http://127.0.0.1:${port}/json/new?about:blank`, { method: 'PUT' });
      if (response.ok) { target = await response.json(); break; }
    } catch { /* browser starting */ }
    await pause(100);
  }
  assert.ok(target, 'Headless browser started');
  socket = new WebSocket(target.webSocketDebuggerUrl);
  socket.addEventListener('message', event => {
    const message = JSON.parse(event.data);
    if (message.method === 'Runtime.exceptionThrown') errors.push(message.params.exceptionDetails.text);
    const item = pending.get(message.id);
    if (!item) return;
    pending.delete(message.id); clearTimeout(item.timer);
    if (message.error) item.reject(Error(message.error.message)); else item.resolve(message.result);
  });
  await new Promise((resolve, reject) => {
    socket.addEventListener('open', resolve, { once: true });
    socket.addEventListener('error', reject, { once: true });
  });
  await command('Page.enable'); await command('Runtime.enable'); await command('Network.enable');
  await command('Network.setBlockedURLs', { urls: ['*fonts.googleapis.com*', '*fonts.gstatic.com*'] });
  await command('Network.setCookie', { name: 'sessionid', value: fixture.session, url: base, httpOnly: true });
  await command('Emulation.setDeviceMetricsOverride', { width: 1440, height: 1000, deviceScaleFactor: 1, mobile: false });
  await navigate('/bibliotheek/');
  assert.equal(await evaluate(`Boolean(document.querySelector('a[href="/bibliotheek/functies-beheer/"]'))`), true);
  assert.equal(await evaluate(`document.querySelector('.library-component-management-details').open`), false);
  await screenshot('library-desktop.png');
  await click('.library-component-management-details > summary');
  await enter('.library-component-management input[name="q"]', 'Anamnese');
  await evaluate(`document.querySelector('.library-component-management .filter-bar').requestSubmit()`);
  await waitFor(`location.search.includes('q=Anamnese') && document.readyState === 'complete'`, 'component filter');
  assert.deepEqual(await evaluate(`[...document.querySelectorAll('.library-component-management .library-card h2')].map(x => x.textContent)`), ['Anamnese']);
  assert.equal(await evaluate(`document.querySelector('.library-component-management-details').open`), true);
  await command('Emulation.setDeviceMetricsOverride', { width: 390, height: 844, deviceScaleFactor: 1, mobile: true });
  await screenshot('library-mobile.png');
  assert.equal(await evaluate('document.documentElement.scrollWidth <= innerWidth + 1'), true, 'Mobile page fits viewport');
  await command('Emulation.setDeviceMetricsOverride', { width: 1440, height: 1000, deviceScaleFactor: 1, mobile: false });
  const editorPath = `/bibliotheek/functies-beheer/${fixture.functionId}/`;
  await navigate(editorPath);
  await waitFor(`Boolean(document.querySelector('.managed-form-fields input'))`, 'editor initialized');
  await enter('.managed-form-fields input', 'Bewaard formulier');
  await click('[data-form-actions] .primary');
  await waitFor(`document.querySelector('.function-toast-region').textContent.includes('opgeslagen')`, 'save with CSRF');
  await command('Page.reload');
  await waitFor(`document.querySelector('.managed-form-fields input')?.value === 'Bewaard formulier'`, 'persisted form');
  await click('[data-preview]');
  await click('.preview-options label:nth-child(1) input');
  await click('.preview-options label:nth-child(2) input');
  assert.equal(await evaluate(`document.querySelectorAll('.preview-options input:checked').length`), 1);
  await screenshot('function-preview.png');
  await click('[data-preview]');
  await enter('.managed-form-fields input', 'Onbewaard formulier');
  await click('[data-editor-back]');
  await waitFor(`document.querySelector('[data-function-dialog]').open`, 'unsaved changes dialog');
  assert.equal(await evaluate('location.pathname'), editorPath);
  await click('button[value="cancel"]');
  assert.equal(await evaluate('location.pathname'), editorPath);
  assert.equal(await evaluate(`document.querySelector('.managed-form-fields input').value`), 'Onbewaard formulier');
  await click('[data-editor-back]');
  await waitFor(`document.querySelector('[data-function-dialog]').open`, 'discard dialog');
  await click('[data-dialog-confirm]');
  await waitFor(`location.pathname === '/bibliotheek/functies-beheer/'`, 'confirmed navigation');
  await navigate(editorPath);
  await waitFor(`document.querySelector('.managed-form-fields input')?.value === 'Bewaard formulier'`, 'discard preserved saved data');
  assert.deepEqual(errors, []);
  console.log('Browser OK: navigation, filters, mobile layout, save/reload, radio groups, unsaved-change cancel/discard.');
} finally {
  socket?.close();
  for (const item of pending.values()) clearTimeout(item.timer);
  browser.kill();
  await pause(300);
  await rm(profile, { recursive: true, force: true, maxRetries: 10, retryDelay: 200 });
}
