document.addEventListener('DOMContentLoaded', () => {
  const browser = document.defaultView;
  const navigation = document.querySelector('.form-navigation');

  if (navigation) {
    const selectForm = (key) => {
      const buttons = [...navigation.querySelectorAll('[data-form-nav]')];
      if (!buttons.some((item) => item.dataset.formNav === key)) return;
      buttons.forEach((item) => {
        item.classList.toggle('is-active', item.dataset.formNav === key);
        item.setAttribute('aria-pressed', item.dataset.formNav === key ? 'true' : 'false');
      });
      document.querySelectorAll('[data-function-form]').forEach((form) => {
        form.hidden = form.dataset.functionForm !== key;
      });
      document.querySelectorAll('[name="form"]').forEach((input) => {
        input.value = key;
      });
    };

    navigation.addEventListener('click', (event) => {
      const button = event.target.closest('[data-form-nav]');
      if (!button) return;
      const key = button.dataset.formNav;
      const url = new URL(browser.location.href);
      url.searchParams.set('form', key);
      browser.history.pushState({}, '', url);
      selectForm(key);
    });

    browser.addEventListener('popstate', () => {
      const firstForm = navigation.querySelector('[data-form-nav]');
      const key = new URL(browser.location.href).searchParams.get('form')
        || (firstForm && firstForm.dataset.formNav);
      if (key) selectForm(key);
    });
  }

  if (typeof tinymce !== 'undefined') {
    tinymce.init({
      selector: 'textarea.rich, .dynamic-field textarea, .answer-form textarea, .js-tinymce',
      license_key: 'gpl',
      base_url: '/static/tinymce',
      suffix: '.min',
      menubar: false,
      plugins: 'lists link table',
      toolbar: 'undo redo | blocks bold italic forecolor backcolor bullist numlist newdocument | importdocx exportdocx',
      color_cols: 5,
      setup(editor) {
        editor.ui.registry.addButton('importdocx', {
          text: 'Import Word', onAction: () => importDocx(editor),
        });
        editor.ui.registry.addButton('exportdocx', {
          text: 'Export Word', onAction: () => exportDocx(editor),
        });
      },
    });
  }

  document.querySelectorAll('[data-nav-toggle]').forEach((button) => {
    button.addEventListener('click', () => {
      if (button.dataset.navUrl) {
        browser.location.href = button.dataset.navUrl;
        return;
      }
      const expanded = button.getAttribute('aria-expanded') === 'true';
      document.querySelectorAll('[data-nav-toggle]').forEach((item) => {
        item.setAttribute('aria-expanded', item === button && !expanded ? 'true' : 'false');
        const panel = document.getElementById(item.getAttribute('aria-controls'));
        if (panel) panel.hidden = item !== button || expanded;
      });
    });
  });
});

function importDocx(editor) {
  const input = document.createElement('input');
  input.type = 'file';
  input.accept = '.docx';
  input.onchange = async () => {
    if (!input.files[0]) return;
    const body = new FormData();
    body.append('file', input.files[0]);
    body.append('csrfmiddlewaretoken', document.querySelector('[name=csrfmiddlewaretoken]').value);
    const response = await fetch('/import/docx/', { method: 'POST', body });
    let data = {};
    try { data = await response.json(); } catch (e) {}  
    if (!response.ok) return alert(data.error || `Import mislukt (HTTP ${response.status}).`);
    editor.insertContent(data.html);
  };
  input.click();
}

function exportDocx(editor) {
  editor.windowManager.open({
    title: 'Exporteer naar Word',
    body: {
      type: 'panel',
      items: [{
        type: 'input',
        name: 'filename',
        label: 'Bestandsnaam',
        placeholder: 'bijvoorbeeld: zorgplan-mia',
      }],
    },
    initialData: { filename: 'dossier' },
    buttons: [
      { type: 'cancel', text: 'Annuleren' },
      { type: 'submit', text: 'Downloaden', buttonType: 'primary' },
    ],
    onSubmit: async (dialog) => {
      const filename = dialog.getData().filename;
      dialog.close();
      const body = new FormData();
      body.append('html', editor.getContent());
      body.append('filename', filename);
      body.append('csrfmiddlewaretoken',
        document.querySelector('[name=csrfmiddlewaretoken]').value);
      const response = await fetch('/export/docx/', { method: 'POST', body });
      if (!response.ok) return alert(`Export mislukt (HTTP ${response.status}).`);
      const link = document.createElement('a');
      link.href = URL.createObjectURL(await response.blob());
      link.download = (filename.trim() || 'dossier') + '.docx';
      link.click();
      URL.revokeObjectURL(link.href);
    },
  });
}