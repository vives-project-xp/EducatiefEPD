// Browser regression test for teacher feedback against disposable fixtures from feedback_browser_seed.py.
// Covers what the Django tests cannot: script execution, TinyMCE form submission, the
// "Importeer antwoord" confirmation, the open/close-all toggle and the responsive layout.
// Usage: node tests/browser/feedback-browser.mjs <fixture.json> <artifact-directory>
import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { mkdir, mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

const fixture = JSON.parse(await readFile(process.argv[2], 'utf8'));
const artifacts = process.argv[3];
await mkdir(artifacts, { recursive: true });
const base = process.env.EPD_TEST_URL || 'http://127.0.0.1:8019';
if (!['127.0.0.1', 'localhost'].includes(new URL(base).hostname)) throw Error('Local test server required');
const profile = await mkdtemp(join(tmpdir(), 'epd-feedback-browser-'));
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
const dialogs = [];
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
  if (result.exceptionDetails) throw Error(result.exceptionDetails.exception?.description || result.exceptionDetails.text);
  return result.result?.value;
}
async function waitFor(expression, label) {
  const deadline = Date.now() + 15000;
  while (Date.now() < deadline) {
    try { if (await evaluate(expression)) return; } catch { /* page navigating */ }
    await pause(100);
  }
  throw Error(`Timeout: ${label}`);
}
async function navigate(path) {
  await command('Page.navigate', { url: base + path });
  await waitFor(`location.pathname + location.search === ${JSON.stringify(path)} && document.readyState === 'complete'`, path);
}
const editorReady = editor => waitFor(`typeof tinymce !== 'undefined' && tinymce.get(${JSON.stringify(editor)})?.initialized === true`, `editor ${editor}`);
const editorHtml = editor => evaluate(`tinymce.get(${JSON.stringify(editor)}).getContent()`);
const setEditor = (editor, html) => evaluate(`tinymce.get(${JSON.stringify(editor)}).setContent(${JSON.stringify(html)})`);
async function submit(formSelector, doneExpression, label) {
  // The marker disappears once the browser has loaded the response page.
  await evaluate(`window.__marker = 1; document.querySelector(${JSON.stringify(formSelector)}).requestSubmit()`);
  await waitFor(`window.__marker === undefined && document.readyState === 'complete' && (${doneExpression})`, label);
}
async function viewport(width, height, mobile) {
  await command('Emulation.setDeviceMetricsOverride', { width, height, deviceScaleFactor: 1, mobile });
  await pause(300);
}
async function screenshot(name) {
  const result = await command('Page.captureScreenshot', { format: 'png', captureBeyondViewport: true });
  await writeFile(join(artifacts, name), Buffer.from(result.data, 'base64'));
}
const reviewPath = `/docent/studentdossier/${fixture.studentCaseId}/`;
const item = `#opdracht-${fixture.submissionId}`;
const feedback = `id_feedback_${fixture.submissionId}`;
const moduleFeedback = `id_module_feedback_${fixture.moduleId}`;
try {
  let target;
  for (let attempt = 0; attempt < 100; attempt++) {
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
    if (message.method === 'Runtime.exceptionThrown') errors.push(message.params.exceptionDetails.exception?.description || message.params.exceptionDetails.text);
    if (message.method === 'Page.javascriptDialogOpening') {
      dialogs.push(message.params.message);
      socket.send(JSON.stringify({ id: ++id, method: 'Page.handleJavaScriptDialog', params: { accept: false } }));
    }
    const entry = pending.get(message.id);
    if (!entry) return;
    pending.delete(message.id); clearTimeout(entry.timer);
    if (message.error) entry.reject(Error(message.error.message)); else entry.resolve(message.result);
  });
  await new Promise((resolve, reject) => {
    socket.addEventListener('open', resolve, { once: true });
    socket.addEventListener('error', reject, { once: true });
  });
  await command('Page.enable'); await command('Runtime.enable'); await command('Network.enable');
  await command('Network.setBlockedURLs', { urls: ['*fonts.googleapis.com*', '*fonts.gstatic.com*', '*cdn.jsdelivr.net*'] });
  await command('Network.setCookie', { name: 'sessionid', value: fixture.teacher, url: base, httpOnly: true });
  await viewport(1440, 1000, false);

  // Teacher: unsafe legacy answer is rendered without running its script.
  await navigate(reviewPath);
  await editorReady(feedback);
  assert.equal(await evaluate('window.__xss'), undefined, 'Legacy script/onerror not executed');

  // "Importeer antwoord": no confirmation on an empty field, confirmation (cancelled) on a filled one.
  await evaluate(`document.querySelector('${item} .button-copy-answer').click()`);
  assert.equal(dialogs.length, 0, 'No confirmation for an empty feedback field');
  assert.ok((await editorHtml(feedback)).includes('38,5'), 'Answer imported');
  await setEditor(feedback, '<p>Eigen feedback</p>');
  await evaluate(`document.querySelector('${item} .button-copy-answer').click()`);
  await pause(300); // dialog is answered from the CDP message handler
  assert.equal(dialogs.length, 1, 'Confirmation asked');
  assert.equal(await editorHtml(feedback), '<p>Eigen feedback</p>', 'Cancelling keeps the typed feedback');

  // Status has no default; the browser blocks the form until one is chosen.
  assert.equal(await evaluate(`document.querySelector('${item} form.review-form').checkValidity()`), false, 'Empty status blocked');

  // TinyMCE content (with colour) is submitted and shown back.
  await evaluate(`document.querySelector('#id_status_${fixture.submissionId}').value = 'resubmit'`);
  await setEditor(feedback, '<p><span style="color: #e03e2d;">Temperatuur klopt niet</span></p>');
  await submit(`${item} form.review-form`, `document.body.textContent.includes('Beoordeling opgeslagen.')`, 'review saved');
  assert.ok(await evaluate(`Boolean(document.querySelector('.previous-review-feedback span[style*="color"]'))`), 'Coloured feedback saved');

  // Open/close-all toggle and module feedback with a revision request.
  await evaluate(`document.querySelector('[data-toggle-modules]').click()`);
  assert.equal(await evaluate(`[...document.querySelectorAll('details.response-detail')].every(d => d.open)`), true, 'All modules open');
  await editorReady(moduleFeedback);
  await setEditor(moduleFeedback, '<p>Vermeld ook de <strong>pariteit</strong>.</p>');
  await evaluate(`document.querySelector('#id_module_revision_requested_${fixture.moduleId}').checked = true`);
  await submit(`#module-${fixture.moduleId} form`, `document.body.textContent.includes('opnieuw aanpassen')`, 'module feedback');
  assert.ok(await evaluate(`document.querySelector('#module-${fixture.moduleId} summary').textContent.includes('Aanpassing gevraagd')`));
  assert.ok(await evaluate(`location.hash === '#module-${fixture.moduleId}' && document.querySelector('#module-${fixture.moduleId}').open`), 'Saved module reopened');

  await editorReady('id_final_final_feedback');
  await setEditor('id_final_final_feedback', '<p>Mooi klinisch redeneren.</p>');
  await submit('#algemene-feedback form', `document.body.textContent.includes('Algemene feedback bewaard.')`, 'final feedback');

  // Layout: three full-width sections stacked; module fields left of the feedback form, stacked on mobile.
  await evaluate(`document.querySelector('[data-toggle-modules]').click()`);
  await editorReady(moduleFeedback);
  const sections = await evaluate(`[...document.querySelectorAll('.review-stack > section')].map(s => { const r = s.getBoundingClientRect(); return { x: Math.round(r.left), w: Math.round(r.width), y: Math.round(r.top) }; })`);
  assert.equal(sections.length, 3);
  assert.ok(sections.every(s => s.x === sections[0].x && s.w === sections[0].w), 'Sections share the full width');
  assert.ok(sections[0].y < sections[1].y && sections[1].y < sections[2].y, 'Sections stacked');
  const columnsSideBySide = `(() => { const [values, form] = document.querySelector('.response-body').children; return Math.abs(values.getBoundingClientRect().top - form.getBoundingClientRect().top) < 20 && values.getBoundingClientRect().width > form.getBoundingClientRect().width; })()`;
  assert.equal(await evaluate(columnsSideBySide), true, 'Fields left, feedback right');
  await screenshot('teacher-desktop.png');
  await viewport(390, 844, true);
  assert.equal(await evaluate(columnsSideBySide), false, 'Stacked on mobile');
  assert.equal(await evaluate('document.documentElement.scrollWidth <= innerWidth + 1'), true, 'Teacher page fits mobile viewport');
  await screenshot('teacher-mobile.png');
  await evaluate(`document.querySelector('[data-toggle-modules]').click()`);
  assert.equal(await evaluate(`[...document.querySelectorAll('details.response-detail')].some(d => d.open)`), false, 'All modules closed');

  // Student: pages with the new feedback blocks load without errors and fit the mobile viewport.
  await command('Network.clearBrowserCookies');
  await command('Network.setCookie', { name: 'sessionid', value: fixture.student, url: base, httpOnly: true });
  await navigate(`/casus/${fixture.caseId}/?assignment=${fixture.submissionId}`);
  assert.ok(await evaluate(`Boolean(document.querySelector('.feedback span[style*="color"]')) && Boolean(document.querySelector('.revision-notice'))`));
  assert.equal(await evaluate('document.documentElement.scrollWidth <= innerWidth + 1'), true, 'Student page fits mobile viewport');
  await screenshot('student-mobile.png');
  await viewport(1440, 1000, false);
  await navigate(`/dossier/${fixture.caseId}/?module=${fixture.moduleId}`);
  assert.ok(await evaluate(`Boolean(document.querySelector('.module-feedback')) && Boolean(document.querySelector('.nav-flag-revision'))`));
  await screenshot('student-dossier.png');

  assert.deepEqual(errors, []);
  console.log('Browser OK: no legacy script execution, import confirmation, TinyMCE review/module/final feedback, toggle, layout desktop/mobile, student views.');
} finally {
  socket?.close();
  for (const entry of pending.values()) clearTimeout(entry.timer);
  browser.kill();
  await pause(300);
  await rm(profile, { recursive: true, force: true, maxRetries: 10, retryDelay: 200 });
}
