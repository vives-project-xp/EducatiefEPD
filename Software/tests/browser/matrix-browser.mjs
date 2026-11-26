// Optional browser regression: use an isolated DB seeded by matrix_browser_seed.py.
// PLAYWRIGHT_MODULE can be a file URL to an already installed Playwright module.
import assert from 'node:assert/strict';
import {mkdir} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
const {chromium} = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const base = process.env.MATRIX_TEST_URL || 'http://127.0.0.1:8017';
if (!/^http:\/\/(127\.0\.0\.1|localhost):8017$/.test(base)) throw new Error('This fixture test only targets the isolated local test server on port 8017.');
const password = process.env.EPD_BROWSER_TEST_PASSWORD;
if (!password) throw new Error('Set EPD_BROWSER_TEST_PASSWORD to the disposable fixture password.');
const ids = JSON.parse(process.env.MATRIX_TEST_IDS || '{"case":1,"module":1,"template":1,"field":1,"student_case":1}');
const artifacts = process.env.MATRIX_TEST_ARTIFACTS || join(tmpdir(), 'epd-matrix-browser');
await mkdir(artifacts, {recursive: true});
const browser = await chromium.launch({headless: true, channel: process.env.PLAYWRIGHT_CHANNEL || 'msedge'});
const errors = [];
async function session(user, viewport = {width: 1440, height: 1000}) {
    const context = await browser.newContext({viewport});
    const page = await context.newPage();
    page.setDefaultTimeout(10000);
    page.on('pageerror', error => errors.push(error.message));
    page.on('dialog', dialog => dialog.accept());
    await page.goto(`${base}/accounts/login/`);
    await page.getByLabel('Gebruikersnaam').fill(user); await page.getByLabel('Wachtwoord').fill(password);
    await Promise.all([page.waitForURL(url => !url.pathname.includes('login')), page.getByRole('button', {name: 'Aanmelden', exact: true}).click()]);
    return page;
}
const cell = (page, r, c) => page.locator(`.sheet-grid td[data-r="${r}"][data-c="${c}"]`);
async function editCell(page, r, c, value) {
    await cell(page, r, c).dblclick(); const input = page.locator('.sheet-cell-editor');
    if (await input.getAttribute('type') === 'checkbox') await input.setChecked(value === 'true');
    else if (await input.evaluate(node => node.tagName === 'SELECT')) await input.selectOption(value);
    else await input.fill(value);
    await input.press('Tab');
}
async function paste(page, text) {
    await page.locator('.sheet-active').evaluate((node, content) => {
        const data = new DataTransfer(); data.setData('text/plain', content);
        node.dispatchEvent(new ClipboardEvent('paste', {clipboardData: data, bubbles: true, cancelable: true}));
    }, text);
}
try {
    const teacher = await session('matrix-teacher');
    await teacher.goto(`${base}/bibliotheek/${ids.template}/veld/nieuw/`);
    await teacher.locator('#id_label').fill('Browsermatrix');
    await teacher.locator('#id_field_type').selectOption('matrix');
    await teacher.locator('.sheet-grid').waitFor();
    assert.equal(await teacher.locator('.sheet-grid td').count(), 24);
    assert.equal(await teacher.locator('[data-legacy-matrix]:visible').count(), 0);
    await cell(teacher, 0, 0).click(); await paste(teacher, 'Kop\t0012\n"Twee\nregels"\t=1+1');
    assert.match(await cell(teacher, 1, 0).innerText(), /Twee\nregels/);
    assert.match(await cell(teacher, 0, 1).innerText(), /0012/);
    const copied = await teacher.locator('.sheet-active').evaluate(node => {
        const data = new DataTransfer(); node.dispatchEvent(new ClipboardEvent('copy', {clipboardData: data, bubbles: true, cancelable: true})); return data.getData('text/plain');
    });
    assert.match(copied, /Kop\t0012/); assert.match(copied, /"Twee\nregels"/);
    await cell(teacher, 0, 0).click(); await teacher.getByLabel('Celtype', {exact: true}).selectOption('label');
    await cell(teacher, 0, 0).click(); await cell(teacher, 0, 1).click({modifiers: ['Shift']});
    await teacher.getByLabel('Vet', {exact: true}).check();
    assert.equal(await cell(teacher, 0, 0).evaluate(node => getComputedStyle(node).fontWeight), '700');
    assert.equal(await cell(teacher, 0, 1).evaluate(node => getComputedStyle(node).fontWeight), '700');
    await teacher.getByRole('button', {name: 'Ongedaan maken', exact: true}).click();
    assert.notEqual(await cell(teacher, 0, 0).evaluate(node => getComputedStyle(node).fontWeight), '700');
    await teacher.getByRole('button', {name: 'Opnieuw', exact: true}).click();
    await teacher.getByLabel('Rij bewerken', {exact: true}).selectOption('duplicate');
    assert.equal(await teacher.locator('.sheet-grid tbody tr').count(), 7);
    await teacher.getByRole('button', {name: 'Ongedaan maken', exact: true}).click();
    await teacher.getByRole('button', {name: 'Studentvoorbeeld', exact: true}).click();
    assert.equal(await cell(teacher, 0, 0).getAttribute('aria-readonly'), 'true');
    await editCell(teacher, 0, 1, 'Voorbeeldantwoord');
    await teacher.getByRole('button', {name: 'Terug naar ontwerp', exact: true}).click();
    assert.match(await cell(teacher, 0, 1).innerText(), /0012/);
    await teacher.screenshot({path: join(artifacts, 'designer-desktop.png'), fullPage: true});
    await teacher.getByRole('button', {name: 'Bewaren', exact: true}).click();
    await teacher.waitForURL(`${base}/bibliotheek/${ids.template}/`);
    console.log('PASS designer: paste, mixed cells, range formatting, undo/redo, row duplication, preview, save');

    await teacher.goto(`${base}/bibliotheek/${ids.template}/veld/nieuw/`);
    await teacher.locator('#id_field_type').selectOption('matrix');
    const examples = [['long_text', 'Lijn 1\nLijn 2'], ['number', '12,555'], ['date', '2026-10-15'], ['time', '12:30'], ['datetime', '2026-10-15T12:30'], ['boolean', 'true'], ['checkbox', 'true'], ['select', 'Optie 2'], ['multiselect', ['Optie 1', 'Optie 2']]];
    for (const [index, [type, value]] of examples.entries()) {
        const r = Math.floor(index / 4), c = index % 4;
        await cell(teacher, r, c).click(); await teacher.getByLabel('Celtype', {exact: true}).selectOption(type);
        await editCell(teacher, r, c, value);
        assert.notEqual(await cell(teacher, r, c).getAttribute('aria-invalid'), 'true');
    }
    await cell(teacher, 0, 1).click(); await teacher.getByLabel('Getalweergave', {exact: true}).selectOption('currency');
    assert.match(await cell(teacher, 0, 1).innerText(), /€ 12,56/);
    const decimals = teacher.getByLabel('Decimalen in weergave (0–8)', {exact: true}); await decimals.fill('3'); await decimals.press('Tab');
    assert.match(await cell(teacher, 0, 1).innerText(), /€ 12,555/);
    await teacher.setViewportSize({width: 390, height: 844});
    assert.ok(await teacher.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth));
    await teacher.screenshot({path: join(artifacts, 'designer-mobile.png'), fullPage: true});
    await teacher.setViewportSize({width: 1440, height: 1000});
    console.log('PASS every native cell editor, precise numeric presentation, mobile designer');

    if (ids.large) {
        const started = Date.now(); await teacher.goto(`${base}/bibliotheek/${ids.template}/veld/${ids.large}/`);
        await teacher.locator('.sheet-grid td').last().waitFor();
        assert.equal(await teacher.locator('.sheet-grid td').count(), 2000);
        const rendered = Date.now() - started;
        await editCell(teacher, 99, 19, 'Laatste cel');
        assert.match(await cell(teacher, 99, 19).innerText(), /Laatste cel/);
        await teacher.getByRole('button', {name: 'Ongedaan maken', exact: true}).click();
        assert.doesNotMatch(await cell(teacher, 99, 19).innerText(), /Laatste cel/);
        console.log(`PASS supported maximum: 2,000 cells rendered in ${rendered} ms; last-cell edit and undo`);
    }

    const student = await session('matrix-student');
    await student.goto(`${base}/dossier/${ids.case}/`); await student.locator('.sheet-grid').waitFor();
    assert.equal(await cell(student, 0, 0).getAttribute('aria-readonly'), 'true');
    await cell(student, 0, 0).click(); await paste(student, 'Geen overschrijving');
    assert.match(await student.locator('.sheet-status').innerText(), /alleen-lezen/);
    await editCell(student, 0, 1, '36,75');
    await editCell(student, 0, 2, 'false');
    await editCell(student, 1, 1, 'Nee');
    await editCell(student, 1, 2, ['A', 'C']);
    await student.locator('#field_other').fill('Gewone invoer samen bewaren');
    await student.getByRole('button', {name: /Bewaren|Opslaan/}).first().click();
    await student.waitForLoadState('networkidle');
    assert.match(await cell(student, 0, 1).innerText(), /36[.,]75/);
    assert.match(await cell(student, 0, 2).innerText(), /Nee/);
    assert.match(await cell(student, 1, 2).innerText(), /A; C/);
    await editCell(student, 0, 1, 'geen getal');
    await student.locator('#field_other').fill('Blijft na fout');
    await student.getByRole('button', {name: /Bewaren|Opslaan/}).first().click();
    await student.waitForLoadState('networkidle');
    assert.match(await cell(student, 0, 1).innerText(), /geen getal/);
    assert.equal(await student.locator('#field_other').inputValue(), 'Blijft na fout');
    assert.equal(await cell(student, 0, 1).getAttribute('aria-invalid'), 'true');
    assert.equal(await student.locator(':focus').getAttribute('data-c'), '1');
    assert.match(await cell(student, 0, 1).getAttribute('aria-label'), /geen getal/);
    await editCell(student, 0, 1, '37');
    await student.getByRole('button', {name: /Bewaren|Opslaan/}).first().click();
    await student.waitForLoadState('networkidle');
    await cell(student, 0, 1).click(); await student.keyboard.press('ArrowDown');
    assert.equal(await student.locator('.sheet-active').getAttribute('data-r'), '1');
    await student.keyboard.press('Shift+ArrowRight');
    assert.equal(await student.locator('td[aria-selected="true"]').count(), 2);
    await student.screenshot({path: join(artifacts, 'student-desktop.png'), fullPage: true});
    await student.setViewportSize({width: 390, height: 844});
    await student.screenshot({path: join(artifacts, 'student-mobile.png'), fullPage: true});
    assert.ok(await student.locator('.sheet-viewport').evaluate(node => node.clientWidth < node.scrollWidth));
    console.log('PASS student: protected cells, all mixed inputs, persistence, error preservation, correction, keyboard selection, narrow viewport');

    await teacher.goto(`${base}/docent/studentdossier/${ids.student_case}/`);
    await teacher.locator('.response-detail > summary').first().click();
    await teacher.locator('.sheet-grid').waitFor();
    assert.equal(await teacher.locator('[data-matrix] input[name]').count(), 0);
    assert.equal(await cell(teacher, 0, 1).getAttribute('aria-readonly'), 'true');
    assert.match(await cell(teacher, 0, 1).innerText(), /37/);
    await teacher.screenshot({path: join(artifacts, 'review.png'), fullPage: true});
    console.log('PASS review: shared grid, saved values, read-only');
    assert.deepEqual(errors, []);
    console.log(`PASS no browser JavaScript errors. Screenshots: ${artifacts}`);
} catch (error) {
    for (const [index, context] of browser.contexts().entries()) for (const page of context.pages()) await page.screenshot({path: join(artifacts, `failure-${index}.png`), fullPage: true}).catch(() => {});
    console.error('Browser errors:', errors);
    throw error;
} finally { await browser.close(); }
