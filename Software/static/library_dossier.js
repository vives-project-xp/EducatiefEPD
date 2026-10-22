(() => {
  const form = document.querySelector(".library-dossier-form");
  if (!form) return;

  const modulesContainer = document.getElementById("new-modules");
  const moduleTemplate = document.getElementById("module-template");
  const fieldTemplate = document.getElementById("module-field-template");
  const serializedModules = document.getElementById("id_new_modules");

  const splitLines = (value) => value.split(/\r?\n/).map((item) => item.trim()).filter(Boolean);

  function setFieldVisibility(fieldset) {
    const type = fieldset.querySelector('[data-field="type"]').value;
    fieldset.querySelector(".field-options").hidden = type !== "select";
    fieldset.querySelector(".field-rows").hidden = type !== "matrix";
    fieldset.querySelector(".field-columns").hidden = type !== "matrix";
  }

  function addField(moduleElement, data = {}) {
    const fragment = fieldTemplate.content.cloneNode(true);
    const fieldset = fragment.querySelector(".dossier-field-editor");
    for (const [key, value] of Object.entries(data)) {
      const control = fieldset.querySelector(`[data-field="${key}"]`);
      if (control) {
        if (control.type === "checkbox") control.checked = value === true;
        else if (Array.isArray(value)) control.value = value.join("\n");
        else control.value = value;
      }
    }
    fieldset.querySelector(".remove-field").addEventListener("click", () => fieldset.remove());
    fieldset.querySelector('[data-field="type"]').addEventListener("change", () => {
      setFieldVisibility(fieldset);
    });
    moduleElement.querySelector(".dossier-module-field-list").append(fieldset);
    setFieldVisibility(fieldset);
  }

  function addModule(data = {}) {
    const fragment = moduleTemplate.content.cloneNode(true);
    const moduleElement = fragment.querySelector(".dossier-module-editor");
    for (const [key, value] of Object.entries(data)) {
      const control = moduleElement.querySelector(`[data-module="${key}"]`);
      if (control) control.value = value;
    }
    moduleElement.querySelector(".remove-module").addEventListener("click", () => {
      moduleElement.remove();
    });
    moduleElement.querySelector(".add-field").addEventListener("click", () => {
      addField(moduleElement);
    });
    for (const field of data.fields || []) addField(moduleElement, field);
    modulesContainer.append(moduleElement);
  }

  let initialModules = [];
  try {
    initialModules = JSON.parse(serializedModules.value || "[]");
  } catch (error) {
    const message = document.createElement("p");
    message.className = "errorlist";
    message.textContent = `De eerder ingevoerde moduleconfiguratie kon niet worden geladen: ${error.message}`;
    modulesContainer.append(message);
    form.querySelector('[type="submit"]').disabled = true;
  }
  if (Array.isArray(initialModules)) {
    for (const module of initialModules) addModule(module);
  }

  document.getElementById("add-module").addEventListener("click", () => addModule());
  form.addEventListener("submit", () => {
    const modules = [...modulesContainer.querySelectorAll(".dossier-module-editor")].map((module) => {
      const getModuleValue = (key) => module.querySelector(`[data-module="${key}"]`).value.trim();
      const fields = [...module.querySelectorAll(".dossier-field-editor")].map((fieldset) => {
        const getFieldValue = (key) => fieldset.querySelector(`[data-field="${key}"]`);
        return {
          label: getFieldValue("label").value.trim(),
          type: getFieldValue("type").value,
          help_text: getFieldValue("help_text").value.trim(),
          required: getFieldValue("required").checked,
          options: splitLines(getFieldValue("options").value),
          rows: splitLines(getFieldValue("rows").value),
          columns: splitLines(getFieldValue("columns").value),
        };
      });
      return {
        title: getModuleValue("title"),
        category: getModuleValue("category"),
        description: getModuleValue("description"),
        theme: getModuleValue("theme"),
        instructions: getModuleValue("instructions"),
        fields,
      };
    });
    serializedModules.value = JSON.stringify(modules);
  });
})();
