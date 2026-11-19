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
      plugins: 'lists link table image',
      toolbar: 'undo redo | blocks bold italic forecolor backcolor bullist numlist newdocument | image uploadimage | importdocx exportdocx',
      color_cols: 5,
      setup(editor) {
        editor.on('change input', () => {
          const target = editor.getElement();
          target?.dispatchEvent(new Event('epd:dirty', {bubbles: true}));
        });
        editor.ui.registry.addButton('uploadimage', {
          text: 'Upload image',
          icon: 'image',
          onAction: () => {
            const input = document.createElement('input');
            input.type = 'file';
            input.accept = 'image/*';
            input.onchange = () => {
              const file = input.files?.[0];
              if (!file) return;
              const reader = new FileReader();
              reader.onload = () => {
                editor.insertContent(`<img src="${reader.result}" alt="">`);
              };
              reader.readAsDataURL(file);
            };
            input.click();
          },
        });
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

document.addEventListener("click", function (event) {
  const button = event.target.closest(".button-copy-answer");
  if (!button) return;

  const reviewField = button.closest(".review-field");
  const feedback = reviewField?.querySelector("textarea");
  const answerElement = button.closest("article")?.querySelector(".student-answer");

  if (!feedback || !answerElement) return;

  // The student's answer is already rendered in the card; copy it as-is.
  const answer = answerElement.innerHTML;

  // Update TinyMCE if it manages this textarea, otherwise the raw field.
  const editor = typeof tinymce !== "undefined" ? tinymce.get(feedback.id) : null;
  if (editor) {
    editor.setContent(answer);
    editor.save();
    editor.focus();
  } else {
    feedback.value = answer;
    feedback.focus();
  }
});

function importDocx(editor) {
  const input = document.createElement('input');
  input.type = 'file';
  input.accept = '.docx';
  file_picker_callback: (callback, value, meta) => {
    if (meta.filetype !== 'image') return;

    const input = document.createElement('input');
    input.type = 'file';
    input.accept = 'image/*';

    input.onchange = () => {
      const file = input.files[0];
      if (!file) return;

      const reader = new FileReader();

      reader.onload = () => {
        const id = 'blobid' + Date.now();
        const blobCache = tinymce.activeEditor.editorUpload.blobCache;
        const base64 = reader.result.split(',')[1];

        const blobInfo = blobCache.create(id, file, base64);
        blobCache.add(blobInfo);

        callback(blobInfo.blobUri(), { title: file.name });
      };

      reader.readAsDataURL(file);
    };

    input.click();
  },    
  input.onchange = async () => {
    if (!input.files[0]) return;
    const body = new FormData();
    body.append('file', input.files[0]);
    body.append('csrfmiddlewaretoken', document.querySelector('[name=csrfmiddlewaretoken]').value);
    const response = await fetch('/import/docx/', { method: 'POST', body });
    let data = {};
    try { data = await response.json(); } catch (e) {}  
    if (!response.ok) return alert(data.error || `Import mislukt (HTTP ${response.status}).`);
    console.log(data.html);
    console.log('Images:', data.html.match(/<img\b[^>]*>/gi));  
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