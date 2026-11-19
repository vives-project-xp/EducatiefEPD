(() => {
  const states = new WeakMap();

  function status(section, message, isError = false) {
    const node = section.querySelector('.epd-save-status');
    if (node) {
      node.textContent = message;
      node.className = `epd-save-status${isError ? ' is-error' : ''}`;
    }
  }

  function setDirty(section, dirty) {
    const state = states.get(section);
    if (!state) return;
    state.dirty = dirty;
    section.querySelectorAll('[data-form-save]').forEach((button) => {
      button.disabled = !dirty || state.saving;
    });
  }

  function getCsrf() {
    return document.querySelector('[name="csrfmiddlewaretoken"]')?.value || '';
  }

  function addObservation(section, button) {
    const entry = button.closest('[data-observation-entry]');
    if (!entry) return;
    if (button.disabled) return;
    const key = entry.dataset.observationEntry;
    const rows = entry.querySelector('[data-new-observation-rows]');
    if (!rows) return;
    const template = entry.querySelector('[data-observation-template]');
    if (template) {
      const fragment = template.content.cloneNode(true);
      const timestamp = fragment.querySelector('[name^="observation_timestamp_"]');
      const value = fragment.querySelector('[name^="observation_value_"]');
      if (timestamp) timestamp.value = '';
      if (value) value.value = '';
      rows.append(fragment);
    } else {
      const row = document.createElement('div');
      row.className = 'observation-edit-row';
      row.innerHTML = `
        <input type="datetime-local" name="observation_timestamp_${key}" aria-label="Nieuw observatietijdstip">
        <input name="observation_value_${key}" aria-label="Nieuwe observatie" placeholder="Waarde of observatie">
        <input name="observation_note_${key}" aria-label="Nieuwe observatietoelichting" placeholder="Toelichting">`;
      rows.append(row);
    }
    setDirty(section, true);
    button.disabled = true;
  }

  function updateObservationAddButtons() {
    document.querySelectorAll('[data-observation-entry]').forEach((entry) => {
      const button = entry.querySelector('[data-add-observation]');
      if (!button) return;
      const rows = [...entry.querySelectorAll('.observation-edit-row')];
      const lastRow = rows[rows.length - 1];
      if (!lastRow) {
        button.disabled = true;
        return;
      }
      const timestamp = lastRow.querySelector('[name^="observation_timestamp_"]');
      const value = lastRow.querySelector('[name^="observation_value_"]');
      button.disabled = !(timestamp?.value.trim() && value?.value.trim());
    });
  }

  function collectAnswer(section, field) {
    const name = field.name || '';
    if (name.startsWith('function_')) {
      const key = name.slice('function_'.length);
      if (field.type === 'file') return [key, {type: 'file', name: field.name}];
      return [key, field.value];
    }
    if (name.startsWith('field_')) {
      const rest = name.slice('field_'.length);
      if (field.type === 'file') return [rest, {type: 'file', name: field.name}];
      const parts = rest.split('_');
      const legacyMatrix = rest.match(/^(.+)_(\d+)_(\d+)$/);
      if (legacyMatrix) return [`${legacyMatrix[1]}:${legacyMatrix[2]}:${legacyMatrix[3]}`, field.value];
      return [rest, field.value];
    }
    if (name.startsWith('matrix_')) return [name.slice('matrix_'.length), JSON.parse(field.value || 'null')];
  }

  async function save(section) {
    const state = states.get(section);
    if (!state || !state.dirty || state.saving) return;
    state.saving = true;
    setDirty(section, true);

    const form = section.closest('form');
    const moduleId = form?.querySelector('[name="module"]')?.value
      || document.querySelector('[name="module"]')?.value;
    const functionId = form?.querySelector('[name="function"]')?.value || '';
    const formKey = section.dataset.formKey === 'module'
      ? 'module'
      : section.dataset.formKey || '';
    const answers = {};

    if (window.tinymce?.triggerSave) {
      window.tinymce.triggerSave();
    }

    section.querySelectorAll('input, textarea, select').forEach((field) => {
      if (field.disabled) return;
      if (field.closest('[data-observation-entry]')) return;
      const collected = collectAnswer(section, field);
      if (!collected) return;
      const [key, value] = collected;
      if (key.includes(':')) {
        const [matrixKey, row, column] = key.split(':');
        answers[matrixKey] = answers[matrixKey] || {legacyCells: {}};
        answers[matrixKey].legacyCells[`${row}_${column}`] = value;
      } else {
        answers[key] = value;
      }
    });

    section.querySelectorAll('[data-observation-entry]').forEach((entry) => {
      const key = entry.dataset.observationEntry;
      const observations = [];
      const existing = entry.querySelector('[name^="existing_observations_"]');
      try {
        const parsed = JSON.parse(existing?.value || '[]');
        if (Array.isArray(parsed)) observations.push(...parsed);
      } catch (_) {}
      entry.querySelectorAll('.observation-edit-row').forEach((row) => {
        const timestamp = row.querySelector('[name^="observation_timestamp_"]')?.value || '';
        const value = row.querySelector('[name^="observation_value_"]')?.value.trim() || '';
        const note = row.querySelector('[name^="observation_note_"]')?.value.trim() || '';
        if (!timestamp && !value && !note) return;
        observations.push({
          timestamp,
          value,
          note,
        });
      });
      answers[key] = observations;
    });

    const payload = {
      module_id: Number(moduleId),
      function_id: functionId ? Number(functionId) : null,
      form_key: formKey,
      answers,
    };

    const body = new FormData();
    body.append('payload', JSON.stringify(payload));
    body.append('csrfmiddlewaretoken', getCsrf());
    section.querySelectorAll('input[type="file"]').forEach((input) => {
      [...(input.files || [])].forEach((file) => body.append(input.name, file));
    });

    try {
      const response = await fetch('/dossier/save-form/', {
        method: 'POST',
        body,
        headers: {'Accept': 'application/json'},
        credentials: 'same-origin',
      });
      let data = {};
      try { data = await response.json(); } catch (_) {}
      if (!response.ok) throw new Error(data.error || `Opslaan mislukt (HTTP ${response.status}).`);
      state.saving = false;
      setDirty(section, false);
      status(section, data.message || 'Bewaard.');
    } catch (error) {
      state.saving = false;
      setDirty(section, true);
      status(section, error.message || 'Opslaan mislukt. Controleer uw waarden en probeer opnieuw.', true);
    }
  }

  document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('[data-save-form]').forEach((section) => {
      states.set(section, {dirty: false, saving: false});
      setDirty(section, false);
    });
    updateObservationAddButtons();
  });

  document.addEventListener('input', (event) => {
    const section = event.target.closest('[data-save-form]');
    if (section && event.isTrusted) setDirty(section, true);
    if (event.target.closest('[data-observation-entry]')) updateObservationAddButtons();
  });
  document.addEventListener('change', (event) => {
    const section = event.target.closest('[data-save-form]');
    if (section && event.isTrusted) setDirty(section, true);
    if (event.target.closest('[data-observation-entry]')) updateObservationAddButtons();
  });
  document.addEventListener('epd:dirty', (event) => {
    const section = event.target.closest('[data-save-form]');
    if (section) setDirty(section, true);
  });
  document.addEventListener('click', (event) => {
    const addButton = event.target.closest('[data-add-observation]');
    if (addButton) {
      event.preventDefault();
      const section = addButton.closest('[data-save-form]');
      if (section) addObservation(section, addButton);
      return;
    }
    const saveButton = event.target.closest('[data-form-save]');
    if (saveButton) {
      event.preventDefault();
      const section = saveButton.closest('[data-save-form]');
      if (section) save(section);
    }
  });
})();
