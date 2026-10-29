document.addEventListener('DOMContentLoaded', () => {
  tinymce.init({
    selector: '.rich, .dynamic-field textarea, .answer-form textarea, .js-tinymce',
    license_key: 'gpl',
    base_url: '/static/tinymce',
    suffix: '.min',
    // language: 'nl',            // needs the nl language file in static/tinymce/langs/
    menubar: false,
    plugins: 'lists link table image autoresize',
    toolbar: 'undo redo | blocks bold italic forecolor backcolor bullist numlist newdocument | image importdocx exportdocx',
    color_cols: 5,
    setup(editor) {
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
            editor.insertContent(
              `<img src="${reader.result}" alt="">`
            );
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