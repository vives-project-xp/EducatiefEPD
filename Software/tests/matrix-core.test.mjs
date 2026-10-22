import test from 'node:test';
import assert from 'node:assert/strict';
import {newSheet, emptyValues, setSpec, setValue, valueAt, specAt, parseTSV, toTSV, pasteBlock, changeAxis, History, cellError, numberDisplay} from '../static/matrix-core.mjs';

test('Excel TSV round trip preserves multiline, tabs, quotes, empty cells and leading zeros', () => {
    const rows = [['0012', 'two\nlines', 'a\tb', '"quoted"', ''], ['', '=1+1', '0', '', 'last']];
    assert.deepEqual(parseTSV(toTSV(rows)), rows);
    assert.deepEqual(parseTSV('one\ttwo\r\n'), [['one', 'two']]);
    assert.throws(() => parseTSV('"unfinished'), /aanhalingstekens/);
});
test('Pasting is atomic for invalid typed cells, protected cells, and overflow', () => {
    const sheet = newSheet(), values = emptyValues();
    setSpec(sheet, 0, 1, {type: 'number'});
    const before = JSON.stringify({sheet, values});
    assert.throws(() => pasteBlock(sheet, values, {r: 0, c: 0}, [['ok', 'invalid']], false));
    assert.equal(JSON.stringify({sheet, values}), before);
    setSpec(sheet, 0, 1, {type: 'label', text: 'Vast'});
    assert.throws(() => pasteBlock(sheet, values, {r: 0, c: 0}, [['ok', 'overwrite']], false), /alleen-lezen/);
    assert.throws(() => pasteBlock(sheet, values, {r: 5, c: 3}, [['a', 'b']], true), /past niet/);
});
test('Mixed type paste retains precise numbers and structured boolean/multiple choices', () => {
    const sheet = newSheet(), values = emptyValues();
    setSpec(sheet, 0, 1, {type: 'number'}); setSpec(sheet, 0, 2, {type: 'checkbox'}); setSpec(sheet, 0, 3, {type: 'multiselect', options: ['A', 'B']});
    const next = pasteBlock(sheet, values, {r: 0, c: 0}, [['0001', '12345678901234567890,01', 'nee', 'A; B']], false);
    assert.equal(valueAt(next.sheet, next.values, 0, 0), '0001');
    assert.equal(valueAt(next.sheet, next.values, 0, 1), '12345678901234567890,01');
    assert.equal(valueAt(next.sheet, next.values, 0, 2), false);
    assert.deepEqual(valueAt(next.sheet, next.values, 0, 3), ['A', 'B']);
});
test('Moving rows and columns keeps values and types attached to stable identities', () => {
    let sheet = newSheet(), values = emptyValues();
    setSpec(sheet, 0, 0, {type: 'number'}); setValue(sheet, values, 0, 0, '42');
    ({sheet, values} = changeAxis(sheet, values, 'rows', 0, 'down'));
    ({sheet, values} = changeAxis(sheet, values, 'columns', 0, 'down'));
    assert.equal(valueAt(sheet, values, 1, 1), '42'); assert.equal(specAt(sheet, 1, 1).type, 'number');
    assert.equal(valueAt(sheet, values, 0, 0), '');
});
test('Duplicated rows and columns are independent and insertion/deletion retains other cells', () => {
    let sheet = newSheet(), values = emptyValues();
    setSpec(sheet, 0, 0, {type: 'text', default: 'Original'}); setValue(sheet, values, 0, 0, 'Answer');
    const sourceId = sheet.rows[0].id;
    ({sheet, values} = changeAxis(sheet, values, 'rows', 0, 'duplicate'));
    assert.notEqual(sheet.rows[1].id, sourceId);
    setSpec(sheet, 1, 0, {type: 'label', text: 'Independent'}); setValue(sheet, values, 1, 0, 'Changed');
    assert.equal(specAt(sheet, 0, 0).default, 'Original'); assert.equal(valueAt(sheet, values, 0, 0), 'Answer');
    ({sheet, values} = changeAxis(sheet, values, 'columns', 0, 'duplicate'));
    assert.notEqual(sheet.columns[0].id, sheet.columns[1].id);
    ({sheet, values} = changeAxis(sheet, values, 'rows', 1, 'delete'));
    assert.equal(valueAt(sheet, values, 0, 1), 'Answer');
});
test('Undo/redo restores content and structure and branches history after edits', () => {
    const first = {sheet: newSheet(), values: emptyValues()}, history = new History(first);
    const next = changeAxis(first.sheet, first.values, 'rows', 0, 'duplicate'); history.push(next);
    assert.equal(history.travel(-1).sheet.rows.length, 6); assert.equal(history.travel(1).sheet.rows.length, 7);
    history.travel(-1); history.push(changeAxis(first.sheet, first.values, 'columns', 0, 'duplicate'));
    assert.equal(history.travel(1).sheet.columns.length, 5); assert.equal(history.travel(1).sheet.rows.length, 6);
});
test('Typed input checks invalid dates and distinguishes false/zero from empty', () => {
    assert.ok(cellError({type: 'date'}, '2026-02-30'));
    assert.ok(cellError({type: 'time'}, '24:01'));
    assert.equal(cellError({type: 'number', required: true}, '0', true), '');
    assert.equal(cellError({type: 'checkbox', required: true}, false, true), '');
    assert.ok(cellError({type: 'checkbox', required: true}, '', true));
});
test('Teacher prefill can edit readonly answers but never fixed labels', () => {
    const sheet = newSheet(); setSpec(sheet, 0, 0, {read_only: true});
    assert.throws(() => pasteBlock(sheet, emptyValues(), {r: 0, c: 0}, [['x']], false));
    assert.equal(valueAt(sheet, pasteBlock(sheet, emptyValues(), {r: 0, c: 0}, [['x']], false, true).values, 0, 0), 'x');
    setSpec(sheet, 0, 0, {type: 'label'});
    assert.throws(() => pasteBlock(sheet, emptyValues(), {r: 0, c: 0}, [['x']], false, true));
});
test('Numeric display rounds exact strings without changing stored precision or rescaling percentages', () => {
    assert.equal(numberDisplay({number_format: 'currency', currency: 'EUR', decimals: 2}, '12345678901234567890.125'), '€ 12345678901234567890,13');
    assert.equal(numberDisplay({number_format: 'decimal', decimals: 0}, '-9.99'), '-10');
    assert.equal(numberDisplay({number_format: 'percent', decimals: 1}, '12.5'), '12,5 %');
    assert.equal(numberDisplay({}, '0.1234567890123456789'), '0,1234567890123456789');
});
