// Local browser smoke test. Uses Chrome DevTools directly, without npm packages.
import { spawn } from 'node:child_process';
import { mkdtemp, readFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

const chrome = process.env.CHROME_PATH || 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe';
const profile = await mkdtemp(join(tmpdir(), 'epd-oidc-'));
const port = 20000 + Math.floor(Math.random() * 30000);
const child = spawn(chrome, [
  '--headless=new', '--no-first-run', '--disable-gpu', '--disable-gpu-compositing',
  '--disable-gpu-rasterization', '--disable-software-rasterizer', '--no-sandbox',
  '--disable-features=Vulkan,UseSkiaRenderer,CanvasOopRasterization',
  `--remote-debugging-port=${port}`, `--user-data-dir=${profile}`, 'about:blank',
], { windowsHide: true, stdio: ['ignore', 'ignore', 'pipe'] });
let browserError = '';
child.stderr.on('data', chunk => { browserError += chunk.toString(); });

const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
const fixture = process.argv[2] || 'student';
const account = {
  student: ['epd-student', 'EPD_TEST_STUDENT_PASSWORD'],
  docent: ['epd-docent', 'EPD_TEST_TEACHER_PASSWORD'],
  beheerder: ['epd-beheerder', 'EPD_TEST_MANAGER_PASSWORD'],
}[fixture];
if (!account) throw Error('Use student, docent or beheerder');
const localEnv = Object.fromEntries((await readFile(join(import.meta.dirname, '.env'), 'utf8'))
  .split(/\r?\n/).filter(line => line.includes('=')).map(line => {
    const at = line.indexOf('='); return [line.slice(0, at), line.slice(at + 1)];
  }));
let socket;
let id = 0;
const pending = new Map();
async function command(method, params = {}) {
  const key = ++id;
  const promise = new Promise((resolve, reject) => pending.set(key, { resolve, reject }));
  socket.send(JSON.stringify({ id: key, method, params }));
  return promise;
}
async function evaluate(expression) {
  const result = await command('Runtime.evaluate', {
    expression, returnByValue: true, awaitPromise: true,
  });
  if (result.exceptionDetails) throw Error(JSON.stringify(result.exceptionDetails));
  return result.result?.value;
}
async function waitFor(predicate, label, timeout = 15000) {
  const until = Date.now() + timeout;
  while (Date.now() < until) {
    const value = await evaluate(predicate);
    if (value) return value;
    await sleep(250);
  }
  throw Error(`Timeout waiting for ${label}`);
}
const deepSelector = `(selector) => {
  const visit = root => {
    const found = root.querySelector(selector);
    if (found) return found;
    for (const element of root.querySelectorAll('*')) {
      if (element.shadowRoot) {
        const nested = visit(element.shadowRoot);
        if (nested) return nested;
      }
    }
    return null;
  };
  return visit(document);
}`;
async function enter(selector, value) {
  await evaluate(`(() => {
    const field = (${deepSelector})(${JSON.stringify(selector)});
    const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;
    setter.call(field,${JSON.stringify(value)});
    field.dispatchEvent(new Event('input',{bubbles:true,composed:true}));
    field.dispatchEvent(new Event('change',{bubbles:true,composed:true}));
    return true;
  })()`);
}
async function click(selector) {
  await evaluate(`(() => { (${deepSelector})(${JSON.stringify(selector)}).click(); return true; })()`);
}

try {
  let target;
  for (let attempt = 0; attempt < 60; attempt++) {
    try {
      const response = await fetch(`http://127.0.0.1:${port}/json/new?about:blank`, { method: 'PUT' });
      if (response.ok) { target = await response.json(); break; }
    } catch { /* browser is starting */ }
    await sleep(250);
  }
  if (!target) throw Error(`Chrome did not start: ${browserError.slice(-1000)}`);
  socket = new WebSocket(target.webSocketDebuggerUrl);
  socket.addEventListener('message', event => {
    const payload = JSON.parse(event.data);
    if (!payload.id || !pending.has(payload.id)) return;
    const request = pending.get(payload.id);
    pending.delete(payload.id);
    if (payload.error) request.reject(Error(JSON.stringify(payload.error)));
    else request.resolve(payload.result);
  });
  socket.addEventListener('close', event => {
    for (const request of pending.values()) request.reject(Error(`CDP closed: ${event.code}; ${browserError.slice(-500)}`));
    pending.clear();
  });
  await new Promise((resolve, reject) => {
    socket.addEventListener('open', resolve, { once: true });
    socket.addEventListener('error', reject, { once: true });
  });
  await command('Page.enable');
  await command('Runtime.enable');
  await command('Page.navigate', { url: 'http://localhost:8001/accounts/login/' });
  await waitFor("location.href.includes('localhost:9000')", 'Authentik page');
  await waitFor(`Boolean((${deepSelector})('input[name="uidField"]'))`, 'username field');
  await enter('input[name="uidField"]', account[0]);
  await click('button[type="submit"]');
  await waitFor(`Boolean((${deepSelector})('#ak-stage-password-input'))`, 'password field');
  await enter('#ak-stage-password-input', localEnv[account[1]]);
  await click('button[name="continue"]');
  const denied = process.argv.includes('--expect-denied');
  await waitFor("location.href.startsWith('http://localhost:8001/') && !location.pathname.startsWith('/oidc/')", 'EPD landing page', 20000);
  if (denied) {
    const outcome = await evaluate(`fetch('/accounts/login-fout/')
      .then(response => ({path: location.pathname, status: response.status}))`);
    if (outcome.path !== '/accounts/login-fout/' || outcome.status !== 403) {
      throw Error(`Expected denied login, got ${JSON.stringify(outcome)}`);
    }
    console.log(JSON.stringify({fixture, denied: true, status: 403}, null, 2));
  } else {
  const state = await evaluate(`({url: location.href, title: document.title,
    body: document.body.innerText.slice(0, 1200),
    shadow: document.querySelector('ak-flow-executor')?.shadowRoot?.innerText?.slice(0, 1000)})`);
  const expected = fixture === 'student' ? '/' : '/docent/';
  if (new URL(state.url).pathname !== expected) throw Error(`${fixture} landed on ${state.url}`);
  if (fixture === 'beheerder' && !state.body.includes('Opleidingen')) {
    throw Error('Admin management navigation is missing');
  }
  const permissions = await evaluate(`Promise.all([
    fetch('/beheer/opleidingen/').then(response => response.status),
    fetch('/docent/groepen/').then(response => response.status),
  ])`);
  const expectedPermissions = fixture === 'beheerder' ? [200, 200]
    : fixture === 'docent' ? [403, 200] : [403, 403];
  if (JSON.stringify(permissions) !== JSON.stringify(expectedPermissions)) {
    throw Error(`${fixture} permission mismatch: ${permissions}`);
  }
  console.log(JSON.stringify({fixture, path: new URL(state.url).pathname,
    educationStatus: permissions[0], groupStatus: permissions[1]}, null, 2));
  if (process.argv.includes('--library')) {
    if (fixture === 'student') {
      const status = await evaluate("fetch('/bibliotheek/').then(response => response.status)");
      if (status !== 403) throw Error(`Student can open library: ${status}`);
      console.log(JSON.stringify({libraryStatus: status}));
    } else {
      await command('Page.navigate', { url: 'http://localhost:8001/bibliotheek/' });
      await waitFor("document.querySelectorAll('.library-card').length > 0", 'library cards');
      const library = await evaluate(`(() => {
        const cards = [...document.querySelectorAll('.library-card')];
        const editable = cards.every(card => card.querySelector('.row-actions a') &&
          card.querySelector('form button[type="submit"]'));
        const anamnese = cards.find(card => card.querySelector('h2').textContent === 'Anamnese');
        return {cards: cards.length, editable, url: anamnese?.querySelector('a').href};
      })()`);
      if (!library.editable || !library.url) throw Error(`Missing library controls: ${JSON.stringify(library)}`);
      await command('Page.navigate', { url: library.url });
      await waitFor("Boolean(document.querySelector('.library-field-row'))", 'library fields');
      const editor = await evaluate(`(() => {
        const rows = [...document.querySelectorAll('.library-field-row')];
        return {fields: rows.length, editable: rows.every(row =>
          row.querySelector('.row-actions a') && row.querySelector('form button[type="submit"]')),
          settings: Boolean(document.querySelector('input[name="title"]')),
          addField: Boolean(document.querySelector('a[href$="/veld/nieuw/"]'))};
      })()`);
      if (!editor.editable || !editor.settings || !editor.addField) {
        throw Error(`Missing library field editor: ${JSON.stringify(editor)}`);
      }
      console.log(JSON.stringify({libraryCards: library.cards, editor}, null, 2));
    }
  }
  if (process.argv.includes('--logout')) {
    await evaluate(`(() => {
      document.querySelector('form[action="/accounts/logout/"]').requestSubmit();
      return true;
    })()`);
    await waitFor(`location.href.startsWith('http://localhost:9000/') &&
      Boolean((${deepSelector})('input[name="uidField"]'))`, 'signed-out Authentik login');
    console.log(JSON.stringify({logout: 'Authentik requests credentials again'}, null, 2));
  }
  }
} finally {
  socket?.close();
  child.kill();
  await rm(profile, { recursive: true, force: true, maxRetries: 5, retryDelay: 200 });
}
