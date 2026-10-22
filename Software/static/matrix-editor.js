import {TYPES, clone, emptyValues, newSheet, specAt, valueAt, setSpec, setValue, rangeBetween, eachCell, visibleText, numberDisplay, cellError, clipboardValue, columnName, parseTSV, toTSV, pasteBlock, changeAxis, History} from './matrix-core.mjs';

const el = (tag, text, attrs = {}) => {
    const node = document.createElement(tag);
    if (text !== null) node.textContent = text;
    for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, value);
    return node;
};
const button = (text, handler, title = text) => {
    const node = el('button', text, {type: 'button', title});
    node.addEventListener('click', handler);
    return node;
};
const option = (value, text) => el('option', text, {value});
const isInput = target => target.matches('input,textarea,select');

class MatrixEditor {
    constructor(root, payload, {designer = false, input = null, readonly = false} = {}) {
        this.root = root; this.designer = designer; this.input = input; this.readonly = readonly;
        this.sheet = clone(payload.definition || newSheet());
        this.values = payload.values?.version === 2 && payload.values.cells && typeof payload.values.cells === 'object' ? clone(payload.values) : emptyValues();
        this.label = payload.label || 'Matrix'; this.serverErrors = payload.errors || [];
        this.editReadonly = payload.editReadonly === true;
        this.anchor = {r: 0, c: 0}; this.focus = {r: 0, c: 0};
        this.history = new History(this.state()); this.preview = false; this.dirty = false;
        this.form = root.closest('form');
        root.classList.add('sheet');
        this.toolbar = el('div', null, {class: 'sheet-toolbar', 'aria-label': 'Matrixacties'});
        this.status = el('p', '', {class: 'sheet-status', role: 'status', 'aria-live': 'polite'});
        this.body = el('div', null, {class: designer ? 'sheet-body sheet-designer' : 'sheet-body'});
        this.viewport = el('div', null, {class: 'sheet-viewport'});
        this.panel = el('aside', null, {class: 'sheet-properties', 'aria-label': 'Celeigenschappen'});
        this.body.append(this.viewport); if (designer) this.body.append(this.panel);
        root.append(this.toolbar, this.status, this.body);
        this.buildToolbar(); this.render(); this.sync();
        if (this.serverErrors.length) {
            this.announce(this.serverErrors[0]);
            requestAnimationFrame(() => {
                const invalid = this.viewport.querySelector('td[aria-invalid="true"]');
                if (invalid && document.activeElement === document.body) { this.anchor = {r: Number(invalid.dataset.r), c: Number(invalid.dataset.c)}; this.focus = {...this.anchor}; this.selection(); invalid.scrollIntoView({block: 'nearest'}); }
            });
        }
        root.addEventListener('copy', event => this.copy(event));
        root.addEventListener('paste', event => this.paste(event));
        root.addEventListener('keydown', event => this.keydown(event));
        window.addEventListener('beforeunload', event => { if (this.dirty && !this.form?.dataset.submitting) { event.preventDefault(); event.returnValue = ''; } });
        this.form?.addEventListener('submit', () => { this.finishEdit(); this.sync(); this.form.dataset.submitting = 'true'; });
        // Other fields and pending observations share the same save transaction.
        this.form?.addEventListener('input', () => { this.dirty = true; });
    }
    state() { return {sheet: this.sheet, values: this.values}; }
    designing() { return this.designer && !this.preview; }
    protected(spec) { return spec.type === 'label' || (spec.read_only && !this.editReadonly); }
    range() { return rangeBetween(this.anchor, this.focus); }
    announce(message) { this.status.textContent = message; }
    sync() { if (this.input) this.input.value = JSON.stringify(this.designer ? this.sheet : this.values); }
    changed(next = this.state(), message = 'Wijzigingen nog niet bewaard.') {
        this.sheet = next.sheet; this.values = next.values;
        if (!this.preview) { this.history.push(this.state()); this.dirty = true; }
        this.serverErrors = [];
        this.sync(); this.render(); this.announce(this.preview ? 'Voorbeeld gewijzigd; dit zijn geen opgeslagen antwoorden.' : message);
    }
    attempt(action) { try { action(); } catch (error) { this.announce(error.message); } }
    buildToolbar() {
        this.toolbar.replaceChildren();
        this.toolbar.append(el('strong', this.designer ? 'Matrixontwerper' : this.label));
        if (!this.readonly) {
            this.undoButton = button('Ongedaan maken', () => this.undo(-1));
            this.redoButton = button('Opnieuw', () => this.undo(1));
            this.toolbar.append(this.undoButton, this.redoButton);
        }
        if (this.designer) {
            for (const [axis, title] of [['rows', 'Rij'], ['columns', 'Kolom']]) {
                const select = el('select', null, {'aria-label': `${title} bewerken`});
                select.append(option('', `${title} bewerken…`));
                for (const [action, label] of [['before', 'Invoegen vóór'], ['after', 'Invoegen na'], ['duplicate', 'Dupliceren'], ['up', 'Naar voren'], ['down', 'Naar achteren'], ['delete', 'Verwijderen']]) select.append(option(action, label));
                select.addEventListener('change', () => {
                    const action = select.value; select.value = '';
                    if (action) this.axisAction(axis, action);
                });
                select.dataset.designControl = ''; this.toolbar.append(select);
            }
            this.previewButton = button('Studentvoorbeeld', () => {
                this.finishEdit(); this.preview = !this.preview;
                this.values = emptyValues(); this.render();
                this.announce(this.preview ? 'Probeer de antwoordcellen. Voorbeeldantwoorden worden niet bewaard.' : 'Ontwerpmodus: invoer in cellen wordt vaste tekst of een standaardantwoord.');
            });
            this.previewButton.setAttribute('aria-pressed', 'false');
            this.toolbar.append(this.previewButton);
        }
        const help = el('details', null, {class: 'sheet-help'});
        help.append(el('summary', 'Bediening'), el('p', 'Klik om te selecteren; dubbelklik, typ of druk Enter om te bewerken. Pijlen verplaatsen de selectie, Shift + pijlen/klik selecteert een bereik. Tab gaat naar de volgende cel. Ctrl/Cmd+C en V kopiëren en plakken met Excel. Delete maakt de selectie leeg. Escape annuleert celinvoer. Enter bewaart de cel; Ctrl+Enter bewaart lange tekst. Gebruik Ctrl/Cmd+Z en Shift+Z voor ongedaan maken/opnieuw. Meerdere keuzes: Ctrl/Cmd+klik of Shift+pijlen, daarna Tab. Formules worden als tekst behandeld.'));
        this.toolbar.append(help);
    }
    render() {
        this.focus.r = Math.min(this.focus.r, this.sheet.rows.length - 1); this.focus.c = Math.min(this.focus.c, this.sheet.columns.length - 1);
        this.anchor.r = Math.min(this.anchor.r, this.sheet.rows.length - 1); this.anchor.c = Math.min(this.anchor.c, this.sheet.columns.length - 1);
        if (this.undoButton) {
            this.undoButton.disabled = this.preview || this.history.index === 0;
            this.redoButton.disabled = this.preview || this.history.index === this.history.states.length - 1;
        }
        if (this.previewButton) {
            this.previewButton.textContent = this.preview ? 'Terug naar ontwerp' : 'Studentvoorbeeld';
            this.previewButton.setAttribute('aria-pressed', String(this.preview));
            this.toolbar.querySelectorAll('[data-design-control]').forEach(node => { node.disabled = this.preview; });
            this.panel.hidden = this.preview;
            this.body.classList.toggle('sheet-designer', !this.preview);
        }
        const table = el('table', null, {class: 'sheet-grid', role: 'grid', 'aria-label': this.label, 'aria-multiselectable': 'true', 'aria-readonly': String(this.readonly)});
        const caption = el('caption', `${this.sheet.rows.length} rijen × ${this.sheet.columns.length} kolommen${this.designing() ? ' · Ontwerp en standaardantwoorden' : ''}`);
        table.append(caption);
        const colgroup = el('colgroup', null); colgroup.append(el('col', null, {style: 'width:100px'}));
        this.sheet.columns.forEach(column => colgroup.append(el('col', null, {style: `width:${Math.max(70, Math.min(column.width || 150, 600))}px`})));
        table.append(colgroup);
        table.style.width = `${100 + this.sheet.columns.reduce((sum, column) => sum + (column.width || 150), 0)}px`;
        const head = el('thead', null), headers = el('tr', null);
        headers.append(el('th', '', {scope: 'col'}));
        this.sheet.columns.forEach((column, c) => {
            const th = el('th', null, {scope: 'col', role: 'columnheader'});
            th.append(button(`${columnName(c)} · ${column.label}`, () => { this.anchor = {r: 0, c}; this.focus = {r: this.sheet.rows.length - 1, c}; this.selection(); }, `Kolom ${column.label} selecteren`));
            headers.append(th);
        });
        head.append(headers); table.append(head);
        const body = el('tbody', null);
        this.sheet.rows.forEach((row, r) => {
            const tr = el('tr', null, {role: 'row'}), header = el('th', null, {scope: 'row', role: 'rowheader'});
            header.append(button(row.label || String(r + 1), () => { this.anchor = {r, c: 0}; this.focus = {r, c: this.sheet.columns.length - 1}; this.selection(); }, `Rij ${row.label} selecteren`));
            tr.append(header);
            this.sheet.columns.forEach((column, c) => {
                const spec = specAt(this.sheet, r, c), value = this.designing() ? spec.default ?? '' : valueAt(this.sheet, this.values, r, c);
                const locked = this.readonly || (!this.designing() && this.protected(spec));
                const td = el('td', null, {role: 'gridcell', tabindex: '-1', 'data-r': r, 'data-c': c, 'aria-readonly': String(locked), 'aria-label': `${columnName(c)}${r + 1}, ${row.label}, ${column.label}, ${TYPES[spec.type || 'text']}${spec.required ? ', verplicht' : ''}${locked ? ', alleen-lezen' : ''}`});
                td.style.height = `${row.height || 36}px`;
                const style = spec.style || {};
                td.style.fontWeight = style.bold ? '700' : ''; td.style.fontStyle = style.italic ? 'italic' : '';
                td.style.textAlign = ['left', 'center', 'right'].includes(style.align) ? style.align : 'left';
                td.classList.toggle('sheet-nowrap', style.wrap === false);
                for (const [key, css] of [['color', 'color'], ['background', 'backgroundColor']]) if (/^#[0-9a-f]{6}$/i.test(style[key])) td.style[css] = style[key];
                if (style.border === 'strong') td.classList.add('sheet-border-strong');
                if (style.border === 'none') td.classList.add('sheet-border-none');
                if (locked || spec.type === 'label') td.classList.add('sheet-fixed');
                const text = spec.type === 'number' && value !== '' && value != null ? numberDisplay(spec, value) : visibleText(spec, value);
                td.dataset.editorLabel = td.getAttribute('aria-label');
                td.setAttribute('aria-label', `${td.dataset.editorLabel}, ${text || 'leeg'}${spec.unit ? ' ' + spec.unit : ''}`);
                if (spec.help) td.setAttribute('aria-description', spec.help);
                const display = el('span', `${spec.type === 'checkbox' && typeof value === 'boolean' ? (value ? '☑ ' : '☐ ') : ''}${text}${text && spec.unit ? ' ' + spec.unit : ''}`, {class: 'sheet-cell-text'});
                if (!text && spec.placeholder) { display.textContent = spec.placeholder; display.classList.add('sheet-placeholder'); }
                td.append(display);
                if (this.designing() && spec.type && spec.type !== 'text') td.append(el('small', TYPES[spec.type], {class: 'sheet-type'}));
                if (spec.required && spec.type !== 'label') td.append(el('span', '*', {class: 'sheet-required', 'aria-hidden': 'true'}));
                const serverError = this.serverErrors.find(error => error.startsWith(`Rij ${r + 1} (`) && error.includes(`, kolom ${c + 1} (`));
                const error = serverError || cellError(spec, value);
                if (error) { td.setAttribute('aria-invalid', 'true'); td.title = error; td.setAttribute('aria-description', error); td.append(el('span', '!', {class: 'sheet-error-marker', 'aria-label': error})); }
                else if (spec.help) td.title = spec.help;
                td.addEventListener('pointerdown', event => {
                    if (isInput(event.target) || event.button !== 0) return;
                    this.finishEdit();
                    if (!event.shiftKey) this.anchor = {r, c}; this.focus = {r, c}; this.dragging = true; this.selection();
                });
                td.addEventListener('pointerenter', event => { if (this.dragging && event.buttons === 1) { this.focus = {r, c}; this.selection(false); } });
                td.addEventListener('dblclick', () => this.startEdit());
                td.addEventListener('focus', () => { if (!this.editing && (r !== this.focus.r || c !== this.focus.c)) { this.anchor = {r, c}; this.focus = {r, c}; this.selection(false); } });
                tr.append(td);
            });
            body.append(tr);
        });
        table.append(body); this.viewport.replaceChildren(table);
        if (!this.pointerEnd) { this.pointerEnd = () => { this.dragging = false; }; window.addEventListener('pointerup', this.pointerEnd); }
        this.selection(false);
    }
    selection(focus = true) {
        const range = this.range();
        this.viewport.querySelectorAll('td').forEach(td => {
            const r = Number(td.dataset.r), c = Number(td.dataset.c), active = r === this.focus.r && c === this.focus.c;
            td.classList.toggle('sheet-active', active); td.tabIndex = active ? 0 : -1;
            td.setAttribute('aria-selected', String(r >= range.r0 && r <= range.r1 && c >= range.c0 && c <= range.c1));
        });
        if (this.designing()) this.properties();
        if (focus) this.activeCell()?.focus({preventScroll: true});
    }
    activeCell() { return this.viewport.querySelector(`[data-r="${this.focus.r}"][data-c="${this.focus.c}"]`); }
    move(dr, dc, extend = false, tab = false) {
        let r = this.focus.r + dr, c = this.focus.c + dc;
        if (tab && c >= this.sheet.columns.length) { c = 0; r++; }
        if (tab && c < 0) { c = this.sheet.columns.length - 1; r--; }
        if (r < 0 || r >= this.sheet.rows.length || c < 0 || c >= this.sheet.columns.length) return false;
        this.focus = {r, c}; if (!extend) this.anchor = {...this.focus};
        this.selection(); this.activeCell()?.scrollIntoView({block: 'nearest', inline: 'nearest'}); return true;
    }
    keydown(event) {
        if (isInput(event.target) || !event.target.closest('td') || !this.viewport.contains(event.target)) return;
        const modifier = event.ctrlKey || event.metaKey;
        if (modifier && event.key.toLowerCase() === 'z') { event.preventDefault(); this.undo(event.shiftKey ? 1 : -1); return; }
        const arrows = {ArrowUp: [-1, 0], ArrowDown: [1, 0], ArrowLeft: [0, -1], ArrowRight: [0, 1]};
        if (arrows[event.key]) { event.preventDefault(); this.move(...arrows[event.key], event.shiftKey); }
        else if (event.key === 'Tab') { if (this.move(0, event.shiftKey ? -1 : 1, false, true)) event.preventDefault(); }
        else if (event.key === 'Home' || event.key === 'End') { event.preventDefault(); this.focus.c = event.key === 'Home' ? 0 : this.sheet.columns.length - 1; if (modifier) this.focus.r = event.key === 'Home' ? 0 : this.sheet.rows.length - 1; if (!event.shiftKey) this.anchor = {...this.focus}; this.selection(); }
        else if (event.key === 'Enter' || event.key === 'F2') { event.preventDefault(); this.startEdit(); }
        else if (event.key === 'Delete' || event.key === 'Backspace') { event.preventDefault(); this.clear(); }
        else if (!modifier && !event.altKey && event.key.length === 1) { event.preventDefault(); this.startEdit(event.key); }
    }
    startEdit(initial) {
        if (this.readonly || this.editing) return;
        const {r, c} = this.focus, spec = specAt(this.sheet, r, c), type = spec.type || 'text';
        if (!this.designing() && this.protected(spec)) { this.announce('Deze cel is alleen-lezen.'); return; }
        let value = this.designing() ? (type === 'label' ? spec.text || '' : spec.default ?? '') : valueAt(this.sheet, this.values, r, c);
        const invalid = cellError(spec, value);
        let input;
        if (!invalid && type === 'checkbox') {
            input = el('input', null, {type: 'checkbox'}); input.checked = value === true;
        } else if (!invalid && ['select', 'multiselect', 'boolean'].includes(type)) {
            input = el('select', null);
            if (type === 'multiselect') {
                input.multiple = true; input.size = Math.min(6, Math.max(2, spec.options.length));
                spec.options.forEach(text => { const item = option(text, text); item.selected = Array.isArray(value) && value.includes(text); input.append(item); });
            } else {
                input.append(option('', 'Maak een keuze'));
                if (type === 'select') spec.options?.forEach(text => input.append(option(text, text)));
                else { input.append(option('true', 'Ja'), option('false', 'Nee')); }
                input.value = String(value);
            }
        } else if (type === 'long_text' || type === 'label') {
            input = el('textarea', null, {rows: '3'}); input.value = String(value);
        } else {
            const native = !invalid && ['date', 'time', 'datetime'].includes(type) ? (type === 'datetime' ? 'datetime-local' : type) : 'text';
            input = el('input', null, {type: native}); input.value = String(value);
            if (type === 'number') input.inputMode = 'decimal';
            if (['time', 'datetime'].includes(type)) input.step = '1';
        }
        input.classList.add('sheet-cell-editor'); input.setAttribute('aria-label', this.activeCell().dataset.editorLabel);
        if (input.matches('input[type="text"],textarea')) input.maxLength = Math.min(spec.max_length || 10000, 10000);
        if (spec.placeholder) input.placeholder = spec.placeholder;
        if (initial !== undefined && !input.matches('select') && input.type !== 'date' && input.type !== 'time' && input.type !== 'datetime-local') input.value = initial;
        this.editing = {input, r, c, spec}; this.activeCell().replaceChildren(input); input.focus();
        if (input.select && initial === undefined) input.select();
        input.addEventListener('blur', () => this.finishEdit());
        input.addEventListener('keydown', event => {
            if (event.key === 'Escape') { event.preventDefault(); this.finishEdit(true); this.selection(); }
            else if (event.key === 'Tab') { event.preventDefault(); this.finishEdit(); if (!this.move(0, event.shiftKey ? -1 : 1, false, true)) this.selection(); }
            else if (event.key === 'Enter' && (!input.matches('textarea') || event.ctrlKey || event.metaKey)) { event.preventDefault(); this.finishEdit(); this.move(1, 0); this.selection(); }
            event.stopPropagation();
        });
    }
    finishEdit(cancel = false) {
        if (!this.editing) return;
        const {input, r, c, spec} = this.editing; this.editing = null;
        if (cancel) { this.render(); return; }
        let value = input.value;
        if (input.type === 'checkbox') value = input.checked;
        else if (input.multiple) value = [...input.selectedOptions].map(item => item.value);
        else if (['boolean', 'checkbox'].includes(spec.type) && input.matches('select')) value = value === '' ? '' : value === 'true';
        if (this.designing()) { const next = clone(spec); next[spec.type === 'label' ? 'text' : 'default'] = value; setSpec(this.sheet, r, c, next); }
        else setValue(this.sheet, this.values, r, c, value);
        this.changed();
    }
    undo(delta) {
        if (this.readonly || this.preview) return;
        this.finishEdit(); const next = this.history.travel(delta); this.sheet = next.sheet; this.values = next.values;
        this.dirty = true; this.sync(); this.render(); this.selection(); this.announce(delta < 0 ? 'Wijziging ongedaan gemaakt.' : 'Wijziging opnieuw uitgevoerd.');
    }
    clear() {
        if (this.readonly) return;
        this.attempt(() => {
            const range = this.range(), block = Array.from({length: range.r1 - range.r0 + 1}, () => Array(range.c1 - range.c0 + 1).fill(''));
            this.changed(pasteBlock(this.sheet, this.values, {r: range.r0, c: range.c0}, block, this.designing(), this.editReadonly)); this.selection();
        });
    }
    copy(event) {
        if (isInput(event.target) || !this.viewport.contains(event.target)) return;
        const range = this.range(), rows = [];
        for (let r = range.r0; r <= range.r1; r++) {
            const row = [];
            for (let c = range.c0; c <= range.c1; c++) { const spec = specAt(this.sheet, r, c); row.push(visibleText(spec, this.designing() ? spec.default ?? '' : valueAt(this.sheet, this.values, r, c))); }
            rows.push(row);
        }
        event.clipboardData.setData('text/plain', toTSV(rows)); event.preventDefault(); this.announce('Selectie gekopieerd als waarden.');
    }
    paste(event) {
        if (this.readonly || isInput(event.target) || !this.viewport.contains(event.target)) return;
        event.preventDefault(); this.attempt(() => {
            const range = this.range(), block = parseTSV(event.clipboardData.getData('text/plain'));
            this.changed(pasteBlock(this.sheet, this.values, {r: range.r0, c: range.c0}, block, this.designing(), this.editReadonly), 'Waarden geplakt. Nog niet bewaard.');
            this.anchor = {r: range.r0, c: range.c0}; this.focus = {r: range.r0 + block.length - 1, c: range.c0 + block[0].length - 1}; this.selection();
        });
    }
    axisAction(axis, action) {
        if (!this.designing()) return;
        this.finishEdit();
        if (action === 'delete' && !window.confirm(`Geselecteerde ${axis === 'rows' ? 'rij' : 'kolom'} verwijderen? U kunt dit vóór bewaren ongedaan maken.`)) return;
        this.attempt(() => {
            const coordinate = axis === 'rows' ? 'r' : 'c', index = this.focus[coordinate];
            const next = changeAxis(this.sheet, this.values, axis, index, action);
            this.focus[coordinate] = index + (action === 'up' ? -1 : ['down', 'after', 'duplicate'].includes(action) ? 1 : 0);
            this.anchor = {...this.focus}; this.changed(next); this.selection();
        });
    }
    property(label, control) {
        control.setAttribute('aria-label', label);
        const wrapper = el('label', null, {class: 'sheet-property'}); wrapper.append(el('span', label), control); this.panel.append(wrapper); return control;
    }
    applyProperty(name, value, style = false) {
        eachCell(this.range(), (r, c) => {
            const spec = clone(specAt(this.sheet, r, c)), target = style ? (spec.style ??= {}) : spec;
            if (value === undefined) delete target[name]; else target[name] = value;
            if (name === 'type') {
                // Keep content visible when changing type; invalid values must be consciously corrected.
                if (value === 'label') { spec.text = visibleText(specAt(this.sheet, r, c), spec.default ?? ''); delete spec.default; }
                else if (specAt(this.sheet, r, c).type === 'label') { spec.default = spec.text || ''; delete spec.text; }
                if (['select', 'multiselect'].includes(value) && !spec.options?.length) spec.options = ['Optie 1', 'Optie 2'];
                if (typeof spec.default === 'string' && ['boolean', 'checkbox', 'multiselect'].includes(value)) {
                    try { spec.default = clipboardValue(spec.default, spec); } catch { /* Keep incompatible input visible for correction. */ }
                }
            }
            setSpec(this.sheet, r, c, spec);
        });
        this.changed();
    }
    properties() {
        this.panel.replaceChildren(); const {r, c} = this.focus, spec = specAt(this.sheet, r, c), range = this.range();
        this.panel.append(el('h3', `${columnName(range.c0)}${range.r0 + 1}${range.r0 !== range.r1 || range.c0 !== range.c1 ? ` – ${columnName(range.c1)}${range.r1 + 1}` : ''}`));
        this.panel.append(el('p', 'Instellingen tonen de actieve cel. Een wijziging geldt voor de hele selectie.', {class: 'muted'}));
        const type = el('select', null); Object.entries(TYPES).forEach(([key, text]) => type.append(option(key, text))); type.value = spec.type || 'text';
        type.addEventListener('change', () => this.applyProperty('type', type.value)); this.property('Celtype', type);
        const textControl = (label, name, value, {style = false, multiline = false, numeric = false} = {}) => {
            const input = el(multiline ? 'textarea' : 'input', null); if (!multiline) input.type = numeric ? 'number' : 'text'; else input.rows = 3;
            if (numeric) { input.min = '1'; input.max = '10000'; }
            input.value = value ?? ''; input.addEventListener('change', () => {
                if (numeric && !input.checkValidity()) { input.reportValidity(); return; }
                let val = input.value;
                if (name === 'options') val = [...new Set(val.split('\n').map(v => v.trim()).filter(Boolean))];
                else if (numeric) val = val === '' ? undefined : Number(val);
                else if (['min', 'max'].includes(name) && val === '') val = undefined;
                this.applyProperty(name, val, style);
            });
            return this.property(label, input);
        };
        const checkbox = (label, name, value, style = false) => {
            const input = el('input', null, {type: 'checkbox'}); input.checked = Boolean(value);
            input.addEventListener('change', () => this.applyProperty(name, input.checked, style)); this.property(label, input);
        };
        if (spec.type === 'label') textControl('Vaste tekst', 'text', spec.text, {multiline: true});
        else {
            this.panel.append(button('Standaardantwoord bewerken', () => this.startEdit()), el('small', 'Typ in de cel voor een standaardantwoord. Laat leeg voor studentinvoer.'));
            checkbox('Verplicht bij indienen', 'required', spec.required);
            checkbox('Alleen-lezen voor studenten', 'read_only', spec.read_only);
            textControl('Voorbeeldtekst in lege cel', 'placeholder', spec.placeholder);
            textControl('Hulptekst', 'help', spec.help);
            if (['select', 'multiselect'].includes(spec.type)) textControl('Keuzes: één per regel', 'options', (spec.options || []).join('\n'), {multiline: true});
            if (spec.type === 'number') {
                textControl('Minimum', 'min', spec.min); textControl('Maximum', 'max', spec.max); textControl('Eenheid (bijv. mmol/L)', 'unit', spec.unit);
                const format = el('select', null);
                for (const [key, label] of [['plain', 'Alle decimalen'], ['decimal', 'Vast aantal decimalen'], ['percent', 'Percentage'], ['currency', 'Valuta']]) format.append(option(key, label));
                format.value = spec.number_format || 'plain'; format.addEventListener('change', () => this.applyProperty('number_format', format.value)); this.property('Getalweergave', format);
                if (spec.number_format && spec.number_format !== 'plain') {
                    const decimals = textControl('Decimalen in weergave (0–8)', 'decimals', spec.decimals ?? 2, {numeric: true}); decimals.min = '0'; decimals.max = '8';
                    this.panel.append(el('small', 'Alleen de weergave wordt afgerond. Het volledige getal blijft bewaard. Bij percentage betekent 12,5 invoeren: 12,5%.'));
                }
                if (spec.number_format === 'currency') {
                    const currency = el('select', null); ['EUR', 'USD', 'GBP'].forEach(code => currency.append(option(code, code)));
                    currency.value = spec.currency || 'EUR'; currency.addEventListener('change', () => this.applyProperty('currency', currency.value)); this.property('Valuta', currency);
                }
            }
            if (['text', 'long_text'].includes(spec.type || 'text')) textControl('Maximum aantal tekens', 'max_length', spec.max_length, {numeric: true});
        }
        this.panel.append(el('h4', 'Opmaak'));
        checkbox('Vet', 'bold', spec.style?.bold, true); checkbox('Cursief', 'italic', spec.style?.italic, true); checkbox('Tekstterugloop', 'wrap', spec.style?.wrap !== false, true);
        for (const [name, label, choices] of [['align', 'Uitlijning', [['left', 'Links'], ['center', 'Midden'], ['right', 'Rechts']]], ['border', 'Rand', [['normal', 'Normaal'], ['strong', 'Dik'], ['none', 'Geen']]]]) {
            const select = el('select', null); choices.forEach(([key, text]) => select.append(option(key, text))); select.value = spec.style?.[name] || choices[0][0];
            select.addEventListener('change', () => this.applyProperty(name, select.value, true)); this.property(label, select);
        }
        for (const [name, label, fallback] of [['color', 'Tekstkleur', '#172f44'], ['background', 'Achtergrond', '#ffffff']]) {
            const input = el('input', null, {type: 'color'}); input.value = spec.style?.[name] || fallback;
            input.addEventListener('change', () => this.applyProperty(name, input.value, true)); this.property(label, input);
        }
        this.panel.append(button('Opmaak wissen', () => { eachCell(this.range(), (ri, ci) => { const s = clone(specAt(this.sheet, ri, ci)); delete s.style; setSpec(this.sheet, ri, ci, s); }); this.changed(); }));
        this.panel.append(el('h4', 'Actieve rij en kolom'));
        for (const [axis, index, name, size, min, max] of [['rows', r, 'Rij', 'height', 28, 300], ['columns', c, 'Kolom', 'width', 70, 600]]) {
            const entry = this.sheet[axis][index];
            const label = el('input', null, {type: 'text', maxlength: '180'}); label.value = entry.label;
            label.addEventListener('change', () => { entry.label = label.value; this.changed(); }); this.property(`${name}kop`, label);
            const dimension = el('input', null, {type: 'number', min, max}); dimension.value = entry[size];
            dimension.addEventListener('change', () => { if (dimension.checkValidity()) { entry[size] = Number(dimension.value); this.changed(); } else dimension.reportValidity(); });
            this.property(`${name === 'Rij' ? 'Hoogte' : 'Breedte'} (px)`, dimension);
        }
    }
}

for (const root of document.querySelectorAll('[data-matrix]')) {
    try {
        const payload = JSON.parse(root.querySelector('script[type="application/json"]').textContent);
        const readonly = root.dataset.readonly === 'true';
        let input = null;
        if (!readonly) { input = el('input', null, {type: 'hidden', name: root.dataset.name}); root.append(input); }
        new MatrixEditor(root, payload, {input, readonly}); root.querySelector('.sheet-fallback')?.remove();
    } catch (error) { root.append(el('p', 'De matrixeditor kon niet worden geladen. Uw opgeslagen gegevens zijn niet gewijzigd.', {role: 'alert'})); }
}
for (const root of document.querySelectorAll('[data-matrix-designer]')) {
    const input = document.getElementById('id_matrix_definition'), type = document.getElementById('id_field_type');
    let editor;
    const update = () => {
        root.hidden = type.value !== 'matrix';
        document.querySelectorAll('[data-legacy-matrix]').forEach(node => { node.hidden = true; });
        document.querySelectorAll('[data-select-options]').forEach(node => { node.hidden = type.value !== 'select'; });
        if (root.hidden || editor) return;
        try {
            const definition = JSON.parse(input.value || '{}');
            editor = new MatrixEditor(root, {definition: definition.version === 2 ? definition : newSheet()}, {designer: true, input});
        } catch (error) { root.append(el('p', 'De matrixindeling is ongeldig. Herlaad de pagina of herstel de ingevoerde indeling.', {role: 'alert'})); }
    };
    type.addEventListener('change', update); update();
}
