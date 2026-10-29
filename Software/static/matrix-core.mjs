// Pure sheet operations, shared by the browser editor and Node regression tests.
export const LIMITS = {rows: 100, columns: 40, cells: 2000};
export const TYPES = {text: 'Tekst', long_text: 'Lange tekst', number: 'Getal', date: 'Datum', time: 'Tijd', datetime: 'Datum en tijd', boolean: 'Ja / nee', checkbox: 'Selectievakje', select: 'Keuzelijst', multiselect: 'Meerdere keuzes', label: 'Vaste tekst'};
export const clone = value => JSON.parse(JSON.stringify(value));
export const emptyValues = () => ({version: 2, cells: {}});
export const isBlank = value => value == null || value === '' || (Array.isArray(value) && value.length === 0);
export const specAt = (sheet, r, c) => sheet.cells?.[sheet.rows[r].id]?.[sheet.columns[c].id] || {};
export function valueAt(sheet, values, r, c) {
    const row = values.cells?.[sheet.rows[r].id], column = sheet.columns[c].id;
    return row && Object.hasOwn(row, column) ? row[column] : specAt(sheet, r, c).default ?? '';
}
export const protectedCell = spec => spec.type === 'label' || spec.read_only;
export const newId = prefix => prefix + globalThis.crypto.randomUUID().replaceAll('-', '');
export function columnName(index) {
    let label = '';
    do { label = String.fromCharCode(65 + index % 26) + label; index = Math.floor(index / 26) - 1; } while (index >= 0);
    return label;
}
export function newSheet() {
    return {version: 2, rows: Array.from({length: 6}, (_, i) => ({id: newId('r'), label: String(i + 1), height: 36})), columns: Array.from({length: 4}, (_, i) => ({id: newId('c'), label: columnName(i), width: 150})), cells: {}};
}
export function setSpec(sheet, r, c, spec) {
    const rid = sheet.rows[r].id, cid = sheet.columns[c].id;
    (sheet.cells[rid] ??= {})[cid] = spec;
}
export function setValue(sheet, values, r, c, value) {
    (values.cells[sheet.rows[r].id] ??= {})[sheet.columns[c].id] = value;
}
export function rangeBetween(a, b) {
    return {r0: Math.min(a.r, b.r), r1: Math.max(a.r, b.r), c0: Math.min(a.c, b.c), c1: Math.max(a.c, b.c)};
}
export function eachCell(range, fn) {
    for (let r = range.r0; r <= range.r1; r++) for (let c = range.c0; c <= range.c1; c++) fn(r, c);
}
export function visibleText(spec, value) {
    if (spec.type === 'label') return spec.text || '';
    if (isBlank(value)) return '';
    if (typeof value === 'boolean') return value ? 'Ja' : 'Nee';
    if (Array.isArray(value)) return value.join('; ');
    return String(value);
}
export function numberDisplay(spec, value) {
    const text = String(value).trim().replace(',', '.');
    if (!/^[+-]?(?:\d+(?:\.\d*)?|\.\d+)$/.test(text)) return String(value);
    if (!spec.number_format || spec.number_format === 'plain') return text.replace('.', ',');
    const decimals = Number.isInteger(spec.decimals) && spec.decimals >= 0 && spec.decimals <= 8 ? spec.decimals : 2;
    const negative = text.startsWith('-'), [integer, fraction = ''] = text.replace(/^[+-]/, '').split('.');
    // Round the presentation as integer strings, never through a floating point Number.
    let digits = BigInt((integer || '0') + fraction.slice(0, decimals).padEnd(decimals, '0'));
    if ((fraction[decimals] || '0') >= '5') digits += 1n;
    const padded = digits.toString().padStart(decimals + 1, '0');
    const result = (negative ? '-' : '') + (decimals ? padded.slice(0, -decimals) + ',' + padded.slice(-decimals) : padded);
    if (spec.number_format === 'percent') return result + ' %'; // Entry is in percentage points, no rescaling.
    if (spec.number_format === 'currency') return ({EUR: '€', USD: '$', GBP: '£'}[spec.currency || 'EUR']) + ' ' + result;
    return result;
}
export function cellError(spec, value, complete = false) {
    if (typeof value === 'string') value = value.trim();
    if (spec.type === 'label') return '';
    if (isBlank(value)) return complete && spec.required && !spec.read_only ? 'Deze cel is verplicht.' : '';
    const type = spec.type || 'text';
    if (['boolean', 'checkbox'].includes(type)) return typeof value === 'boolean' ? '' : 'Kies ja of nee.';
    if (type === 'multiselect') return Array.isArray(value) && value.every(v => spec.options?.includes(v)) ? '' : 'Kies geldige opties.';
    if (typeof value !== 'string') return 'Ongeldige tekstwaarde.';
    if (value.length > (spec.max_length || 10000)) return 'De tekst is te lang.';
    if (type === 'number' && !/^[+-]?(?:\d+(?:[.,]\d*)?|[.,]\d+)$/.test(value.trim())) return 'Vul een geldig getal in.';
    if (type === 'select' && !spec.options?.includes(value)) return 'Kies een geldige optie.';
    if (['date', 'time', 'datetime'].includes(type)) {
        const patterns = {date: /^\d{4}-\d{2}-\d{2}$/, time: /^\d{2}:\d{2}(?::\d{2})?$/, datetime: /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2})?$/};
        if (!patterns[type].test(value)) return 'Gebruik een geldige datum of tijd.';
        const [day, clock] = type === 'datetime' ? value.split('T') : type === 'date' ? [value, null] : [null, value];
        if (day) {
            const parsed = new Date(day + 'T00:00:00Z');
            if (Number.isNaN(parsed.getTime()) || parsed.toISOString().slice(0, 10) !== day || day.startsWith('0000')) return 'Ongeldige datum.';
        }
        if (clock && (Number(clock.slice(0, 2)) > 23 || Number(clock.slice(3, 5)) > 59 || Number(clock.slice(6) || 0) > 59)) return 'Ongeldige tijd.';
    }
    return '';
}
export function clipboardValue(text, spec) {
    if (text === '') return '';
    if (['boolean', 'checkbox'].includes(spec.type)) {
        const lower = text.trim().toLowerCase();
        if (['ja', 'true', '1'].includes(lower)) return true;
        if (['nee', 'false', '0'].includes(lower)) return false;
        throw new Error('Gebruik ja/nee voor booleans.');
    }
    if (spec.type === 'multiselect') return text.split(';').map(v => v.trim()).filter(Boolean);
    return text;
}
export function parseTSV(text) {
    if (text.length > 512000) throw new Error('Dit plakbereik is te groot.');
    text = text.replace(/\r\n/g, '\n').replace(/\r/g, '\n');
    const rows = []; let row = [], cell = '', quoted = false, closed = false;
    for (let i = 0; i < text.length; i++) {
        const ch = text[i];
        if (quoted) {
            if (ch === '"') {
                if (text[i + 1] === '"') { cell += '"'; i++; } else { quoted = false; closed = true; }
            } else cell += ch;
        } else if (ch === '\t' || ch === '\n') {
            row.push(cell); cell = ''; closed = false;
            if (ch === '\n') { rows.push(row); row = []; }
        } else if (ch === '"' && cell === '' && !closed) quoted = true;
        else { if (closed) throw new Error('Ongeldige aanhalingstekens in de plakgegevens.'); cell += ch; }
    }
    if (quoted) throw new Error('Niet-afgesloten aanhalingstekens in de plakgegevens.');
    if (cell !== '' || row.length || !text.endsWith('\n')) { row.push(cell); rows.push(row); }
    if (!rows.length) return [['']];
    const width = Math.max(...rows.map(r => r.length));
    if (rows.length > LIMITS.rows || width > LIMITS.columns || rows.length * width > LIMITS.cells) throw new Error('Dit plakbereik is te groot.');
    return rows.map(r => [...r, ...Array(width - r.length).fill('')]);
}
export function toTSV(rows) {
    return rows.map(row => row.map(value => {
        const text = String(value);
        return /["\t\n\r]/.test(text) ? '"' + text.replaceAll('"', '""') + '"' : text;
    }).join('\t')).join('\r\n');
}
export function pasteBlock(sheet, values, start, block, designer, editReadonly = false) {
    if (start.r + block.length > sheet.rows.length || start.c + block[0].length > sheet.columns.length) throw new Error('Het plakbereik past niet. Voeg eerst rijen of kolommen toe.');
    // Build a full candidate before changing anything: a protected/invalid cell cancels all.
    const next = {sheet: clone(sheet), values: clone(values)};
    block.forEach((row, ri) => row.forEach((text, ci) => {
        const r = start.r + ri, c = start.c + ci, spec = clone(specAt(sheet, r, c));
        if (!designer && (spec.type === 'label' || (spec.read_only && !editReadonly))) throw new Error(`Cel ${columnName(c)}${r + 1} is alleen-lezen. Er is niets geplakt.`);
        const value = spec.type === 'label' ? text : clipboardValue(text, spec);
        const error = cellError(spec, value);
        if (error) throw new Error(`Cel ${columnName(c)}${r + 1}: ${error} Er is niets geplakt.`);
        if (designer) { spec[spec.type === 'label' ? 'text' : 'default'] = value; setSpec(next.sheet, r, c, spec); }
        else setValue(next.sheet, next.values, r, c, value);
    }));
    return next;
}
export function changeAxis(sheet, values, axis, index, action) {
    const next = {sheet: clone(sheet), values: clone(values)}, list = next.sheet[axis], other = axis === 'rows' ? 'columns' : 'rows';
    if (action === 'before' || action === 'after' || action === 'duplicate') {
        if (list.length >= LIMITS[axis] || (list.length + 1) * next.sheet[other].length > LIMITS.cells) throw new Error('Maximum: 100 rijen, 40 kolommen en 2.000 cellen.');
        const source = list[index], id = newId(axis === 'rows' ? 'r' : 'c');
        const item = action === 'duplicate' ? {...source, id, label: source.label + ' (kopie)'} : {id, label: axis === 'rows' ? 'Nieuwe rij' : 'Nieuwe kolom', [axis === 'rows' ? 'height' : 'width']: axis === 'rows' ? 36 : 150};
        list.splice(index + (action === 'before' ? 0 : 1), 0, item);
        if (action === 'duplicate') {
            if (axis === 'rows') {
                next.sheet.cells[id] = clone(next.sheet.cells[source.id] || {});
                next.values.cells[id] = clone(next.values.cells[source.id] || {});
            } else {
                for (const map of [next.sheet.cells, next.values.cells]) for (const cells of Object.values(map)) if (source.id in cells) cells[id] = clone(cells[source.id]);
            }
        }
    } else if (action === 'delete') {
        if (list.length === 1) throw new Error('Behoud minstens één rij en één kolom.');
        const [removed] = list.splice(index, 1);
        for (const map of [next.sheet.cells, next.values.cells]) {
            if (axis === 'rows') delete map[removed.id];
            else for (const cells of Object.values(map)) delete cells[removed.id];
        }
    } else {
        const target = index + (action === 'up' ? -1 : 1);
        if (target < 0 || target >= list.length) throw new Error('De rand van de matrix is bereikt.');
        [list[index], list[target]] = [list[target], list[index]];
    }
    return next;
}
export class History {
    constructor(state) { this.states = [clone(state)]; this.index = 0; }
    push(state) { this.states = this.states.slice(0, this.index + 1); this.states.push(clone(state)); if (this.states.length > 40) this.states.shift(); this.index = this.states.length - 1; }
    travel(delta) { this.index = Math.max(0, Math.min(this.states.length - 1, this.index + delta)); return clone(this.states[this.index]); }
}
