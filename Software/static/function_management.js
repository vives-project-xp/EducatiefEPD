(() => {
  const root = document.querySelector("[data-function-page]");
  if (!root) return;

  const paths = {
    trash: ["M3.5 5.5h13m-11.5 0 .8 11h8.4l.8-11M7 5.5V3h6v2.5m-5 3v5m4-5v5"],
    copy: ["M7 6V3.5h9.5V14H14", "M4 6h10v10H4z"],
    up: ["m5 12 5-5 5 5"],
    down: ["m5 8 5 5 5-5"],
    drag: ["M7 5h.01M7 10h.01M7 15h.01M13 5h.01M13 10h.01M13 15h.01"],
    chevron: ["m7 4 6 6-6 6"],
    warning: ["M10 2.5 18 17H2z", "M10 7v4m0 2.5h.01"],
  };

  function node(tag, className = "", text = "") {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (text !== undefined && text !== null) element.textContent = text;
    return element;
  }

  function icon(name) {
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("viewBox", "0 0 20 20");
    svg.setAttribute("aria-hidden", "true");
    svg.setAttribute("focusable", "false");
    (paths[name] || []).forEach((d, index) => {
      const shape = document.createElementNS("http://www.w3.org/2000/svg", "path");
      shape.setAttribute("d", d);
      if (name === "copy" && index === 0) shape.setAttribute("fill", "none");
      svg.append(shape);
    });
    return svg;
  }

  function csrfToken() {
    return document.cookie.split(";").map((part) => part.trim()).find((part) => part.startsWith("csrftoken="))?.slice(10) || "";
  }

  async function post(url, payload) {
    const response = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken() },
      credentials: "same-origin",
      body: JSON.stringify(payload),
    });
    const result = await response.json();
    if (!response.ok || !result.ok) {
      const error = new Error(result.message || "Er ging iets mis.");
      error.warning = Boolean(result.warning);
      throw error;
    }
    return result;
  }

  function toast(message, warning = false) {
    const region = root.querySelector(".function-toast-region");
    if (!region) return;
    const item = node("p", `function-toast${warning ? " warning" : ""}`);
    if (warning) item.append(icon("warning"));
    item.append(node("span", "", message));
    region.replaceChildren(item);
    window.setTimeout(() => item.remove(), 4200);
  }

  function dialog(title, message, options = {}) {
    const element = root.querySelector("[data-function-dialog]");
    if (!element) return Promise.resolve({ confirmed: window.confirm(message), value: "" });
    const titleNode = element.querySelector("[data-dialog-title]");
    const messageNode = element.querySelector("[data-dialog-message]");
    const inputWrap = element.querySelector("[data-dialog-input-wrap]");
    const input = element.querySelector("[data-dialog-input]");
    const confirmButton = element.querySelector("[data-dialog-confirm]");
    titleNode.textContent = title;
    messageNode.textContent = message;
    inputWrap.hidden = !options.input;
    input.value = options.value || "";
    confirmButton.textContent = options.confirmText || "Bevestigen";
    element.showModal();
    if (options.input) input.focus();
    else element.querySelector("button[value='cancel']").focus();
    return new Promise((resolve) => {
      element.addEventListener("close", () => resolve({
        confirmed: element.returnValue === "confirm",
        value: input.value.trim(),
      }), { once: true });
    });
  }

  async function confirm(message, confirmText = "Bevestigen") {
    return (await dialog("Bevestigen", message, { confirmText })).confirmed;
  }

  function initList() {
    const sortButton = root.querySelector("[data-sort-control]");
    sortButton?.addEventListener("click", () => {
      const sequence = ["az", "za", "oldest"];
      const next = sequence[(sequence.indexOf(sortButton.dataset.sort) + 1) % sequence.length];
      const url = new URL(window.location.href);
      url.searchParams.set("sort", next);
      window.location.assign(url);
    });
    root.querySelectorAll("[data-standard-warning]").forEach((button) => {
      button.addEventListener("click", () => toast("Standaardfuncties mogen niet worden bewerkt.", true));
    });
    root.querySelectorAll("[data-delete-function]").forEach((button) => {
      button.addEventListener("click", async () => {
        if (!await confirm(`Functie \u201c${button.dataset.title}\u201d verwijderen? Je kunt de functie 30 dagen herstellen via Recent verwijderd.`, "Verwijderen")) return;
        try {
          const result = await post(button.dataset.url, { action: "delete" });
          toast(result.message);
          window.setTimeout(() => window.location.assign(result.redirect), 1000);
        } catch (error) { toast(error.message, error.warning); }
      });
    });
  }

  function initDeleted() {
    const url = root.dataset.actionUrl;
    root.querySelectorAll("[data-trash-action]").forEach((button) => {
      button.addEventListener("click", async () => {
        const deleting = button.dataset.trashAction === "permanent_delete";
        const message = deleting
          ? `Functie \u201c${button.dataset.title}\u201d definitief verwijderen? Dit kan niet ongedaan worden gemaakt.`
          : "Functie herstellen?";
        if (deleting && !await confirm(message, "Definitief verwijderen")) return;
        try {
          const result = await post(url, { action: button.dataset.trashAction, functionId: Number(button.dataset.id) });
          toast(result.message);
          window.setTimeout(() => window.location.assign(result.redirect), 1000);
        } catch (error) { toast(error.message, error.warning); }
      });
    });
    root.querySelector("[data-empty-trash]")?.addEventListener("click", async (event) => {
      if (event.currentTarget.disabled || !await confirm("Alle functies uit Recent verwijderd definitief verwijderen? Dit kan niet ongedaan worden gemaakt.", "Prullenbak legen")) return;
      try {
        const result = await post(url, { action: "empty" });
        toast(result.message);
        window.setTimeout(() => window.location.assign(result.redirect), 1000);
      } catch (error) { toast(error.message, error.warning); }
    });
  }

  function initGeneral() {
    const input = root.querySelector("[data-function-name]");
    const button = root.querySelector("[data-continue]");
    const update = () => { button.disabled = !input.value.trim(); };
    input.addEventListener("input", update);
    update();
  }

  const fieldTypes = (data) => {
    const groups = new Map();
    (data.typeRegistry || []).forEach((item) => {
      if (!groups.has(item.group)) groups.set(item.group, { label: item.group, options: [] });
      groups.get(item.group).options.push([item.key, item.label]);
    });
    return [...groups.values()];
  };
  const informative = new Set(["image", "link", "info"]);

  function blankQuestion() {
    return { fieldType: "text", question: "", unit: "", required: false, options: [], columns: [], rows: [], matrixDefinition: {}, url: "", buttonText: "", image: "", caption: "", explanation: "" };
  }

  function initEditor() {
    let data;
    try { data = JSON.parse(root.querySelector("#managed-function-data").textContent); }
    catch { toast("De functiegegevens konden niet worden gelezen.", true); return; }
    let state = structuredClone(data);
    let saved = structuredClone(data);
    let selectedFormId = state.forms[0]?.id ?? null;
    let openQuestion = 0;
    let dirty = false;
    const standalone = root.dataset.standalone === "true";
    const typeGroups = fieldTypes(data);
    let locked = data.locked;
    const formList = root.querySelector("[data-form-list]");
    const editorPanel = root.querySelector("[data-editor-panel]");
    const editor = root.querySelector("[data-form-editor]");
    const actions = root.querySelector("[data-form-actions]");
    const previewPanel = root.querySelector("[data-preview-panel]");
    const previewContent = root.querySelector("[data-preview-content]");
    const matrixDialog = root.querySelector("[data-matrix-dialog]");
    const matrixDialogContent = root.querySelector("[data-matrix-dialog-content]");
    const lockButton = root.querySelector("[data-lock]");
    const renameButton = root.querySelector("[data-rename]");
    const saveButton = node("button", "primary button", "Wijzigingen opslaan");
    saveButton.type = "button";
    saveButton.disabled = true;
    let matrixQuestion = null;
    let matrixOriginal = "";
    formList?.addEventListener("dragstart", formDragStart);
    formList?.addEventListener("dragover", formDragOver);
    formList?.addEventListener("drop", formDrop);

    const currentForm = () => state.forms.find((form) => form.id === selectedFormId) || null;
    const isDirty = () => dirty;
    function setDirty() {
      dirty = true;
      saveButton.disabled = locked || !dirty;
    }
    async function discardIfNeeded() {
      if (!isDirty()) return true;
      if (!await confirm("Er zijn niet-opgeslagen wijzigingen. Wil je die weggooien?", "Weggooien")) return false;
      state = structuredClone(saved);
      dirty = false;
      saveButton.disabled = true;
      return true;
    }

    function addTextField(container, labelText, value, onChange, options = {}) {
      const wrapper = node("label", `managed-field${options.wide ? " field-wide" : ""}`);
      const label = node("span", "managed-label", labelText);
      const input = node(options.multiline ? "textarea" : "input", "managed-input");
      if (options.multiline) input.rows = options.rows || 3;
      else input.type = options.type || "text";
      input.value = value || "";
      if (options.placeholder) input.placeholder = options.placeholder;
      if (options.maxLength) input.maxLength = options.maxLength;
      input.addEventListener("input", () => onChange(input.value));
      wrapper.append(label, input);
      container.append(wrapper);
      return input;
    }

    function checkboxField(container, labelText, checked, onChange) {
      const label = node("label", "managed-checkbox");
      const input = node("input");
      input.type = "checkbox";
      input.checked = Boolean(checked);
      input.addEventListener("change", () => onChange(input.checked));
      label.append(input, node("span", "", labelText));
      container.append(label);
    }

    function iconButton(name, label, className, action) {
      const button = node("button", className);
      button.type = "button";
      button.setAttribute("aria-label", label);
      button.title = label;
      button.append(icon(name));
      if (action) button.addEventListener("click", action);
      return button;
    }

    function fieldSelect(question, index) {
      const label = node("label", "managed-field field-wide");
      label.append(node("span", "managed-label", "Veld type"));
      const select = node("select", "managed-input");
      typeGroups.forEach((group) => {
        const optgroup = node("optgroup");
        optgroup.label = group.label;
        group.options.forEach(([value, title]) => {
          const option = node("option", "", title);
          option.value = value;
          option.selected = question.fieldType === value;
          optgroup.append(option);
        });
        select.append(optgroup);
      });
      select.addEventListener("change", () => {
        if (select.value === "matrix" && question.fieldType !== "matrix") {
          const matrixCount = currentForm().questions.filter((item) => item.fieldType === "matrix").length;
          if (matrixCount >= 2) {
            select.value = question.fieldType;
            toast("Een formulier mag maximaal 2 matrices bevatten.", true);
            return;
          }
        }
        question.fieldType = select.value;
        renderEditor();
        setDirty();
      });
      label.append(select);
      return label;
    }

    function listField(container, title, values, onChange) {
      const section = node("fieldset", "managed-list-field");
      section.append(node("legend", "", title));
      const rows = node("div", "managed-list-values");
      values.forEach((value, index) => {
        const row = node("div", "managed-list-value");
        const input = node("input", "managed-input");
        input.type = "text";
        input.value = value;
        input.setAttribute("aria-label", `${title} ${index + 1}`);
        input.addEventListener("input", () => { values[index] = input.value; onChange(); });
        const remove = iconButton("trash", `${title} verwijderen`, "icon-action danger", () => {
          values.splice(index, 1);
          renderEditor();
          setDirty();
        });
        row.append(input, remove);
        rows.append(row);
      });
      const add = node("button", "outline button", "Toevoegen");
      add.type = "button";
      add.addEventListener("click", () => { values.push(""); renderEditor(); setDirty(); });
      section.append(rows, add);
      container.append(section);
    }

    function renderQuestionFields(question, index, body) {
      body.append(fieldSelect(question, index));
      const change = () => setDirty();
      if (question.fieldType === "info") {
        addTextField(body, "Toelichting", question.explanation, (value) => { question.explanation = value; change(); }, { multiline: true, wide: true, rows: 5 });
      } else if (question.fieldType === "link") {
        addTextField(body, "Titel", question.question, (value) => { question.question = value; change(); }, { wide: true });
        addTextField(body, "Link (https://…)", question.url, (value) => { question.url = value; change(); }, { type: "url" });
        addTextField(body, "Knoptekst", question.buttonText, (value) => { question.buttonText = value; change(); });
      } else if (question.fieldType === "image") {
        const wrapper = node("label", "managed-field field-wide");
        wrapper.append(node("span", "managed-label", "Afbeelding"));
        const input = node("input", "managed-input image-picker");
        input.type = "file";
        input.accept = "image/png,image/jpeg,image/gif,image/webp";
        input.addEventListener("change", () => {
          const file = input.files?.[0];
          if (!file) return;
          if (!file.type.startsWith("image/") || file.size > 300_000) {
            toast(file.size > 300_000 ? "De afbeelding mag maximaal 300 kB groot zijn." : "Kies een afbeeldingsbestand.", true);
            input.value = "";
            return;
          }
          const reader = new FileReader();
          reader.addEventListener("load", () => { question.image = String(reader.result); renderEditor(); setDirty(); });
          reader.readAsDataURL(file);
        });
        wrapper.append(input);
        if (question.image) {
          const image = node("img", "question-image-thumb");
          image.src = question.image;
          image.alt = "Voorbeeld van de gekozen afbeelding";
          wrapper.append(image);
          const remove = node("button", "text-button danger", "Afbeelding verwijderen");
          remove.type = "button";
          remove.addEventListener("click", () => { question.image = ""; renderEditor(); setDirty(); });
          wrapper.append(remove);
        }
        body.append(wrapper);
        addTextField(body, "Bijschrift", question.caption, (value) => { question.caption = value; change(); }, { wide: true });
      } else if (question.fieldType === "observation") {
        addTextField(body, "Vraag", question.question, (value) => { question.question = value; change(); }, { wide: true });
        checkboxField(body, "Verplicht antwoord", question.required, (value) => { question.required = value; change(); });
      } else if (["imageUpload", "fileUpload"].includes(question.fieldType)) {
        addTextField(body, "Vraag", question.question, (value) => { question.question = value; change(); }, { wide: true });
        checkboxField(body, "Verplicht antwoord", question.required, (value) => { question.required = value; change(); });
      } else if (!informative.has(question.fieldType)) {
        addTextField(body, "Vraag", question.question, (value) => { question.question = value; change(); }, { wide: true });
        checkboxField(body, "Verplicht antwoord", question.required, (value) => { question.required = value; change(); });
        if (["text", "number"].includes(question.fieldType)) {
          addTextField(body, "Eenheid", question.unit, (value) => { question.unit = value; change(); });
        }
        if (question.fieldType === "multipleChoice") listField(body, "Antwoordopties", question.options, change);
        if (question.fieldType === "matrix") {
          const definition = question.matrixDefinition || {};
          const rows = definition.rows || question.rows || [];
          const columns = definition.columns || question.columns || [];
          const summary = node("div", "matrix-question-summary");
          summary.append(node("span", "", `${rows.length} rijen × ${columns.length} kolommen`));
          const open = node("button", "outline button", definition.version ? "Matrix bewerken" : "Matrix ontwerpen");
          open.type = "button";
          open.addEventListener("click", () => openMatrixDesigner(question, open));
          summary.append(open);
          body.append(summary);
        }
      }
    }

    function openMatrixDesigner(question, opener) {
      if (!matrixDialog || !matrixDialogContent) return;
      matrixQuestion = question;
      matrixOriginal = JSON.stringify(question.matrixDefinition || {});
      matrixDialogContent.replaceChildren();
      const matrix = node("div", "function-matrix-designer");
      const input = node("input");
      input.type = "hidden";
      input.value = matrixOriginal;
      matrix.append(input);
      matrixDialogContent.append(matrix);
      document.dispatchEvent(new CustomEvent("function-matrix-designer", { detail: { root: matrix, input } }));
      matrixDialog.showModal();
      matrixDialog.querySelector("[data-matrix-save]").focus();
      matrixDialog.querySelector("[data-matrix-save]").onclick = () => {
        try {
          matrixQuestion.matrixDefinition = JSON.parse(input.value || "{}");
        } catch {
          toast("De matrixindeling is ongeldig.", true);
          return;
        }
        matrixDialog.close("save");
        renderEditor();
        setDirty();
        opener.focus();
      };
      matrixDialog.querySelector("[data-matrix-cancel]").onclick = async () => {
        if (input.value !== matrixOriginal && !await confirm("Er zijn niet-opgeslagen matrixwijzigingen. Wil je die weggooien?", "Weggooien")) return;
        matrixDialog.close("cancel");
        opener.focus();
      };
      matrixDialog.oncancel = (event) => {
        event.preventDefault();
        matrixDialog.querySelector("[data-matrix-cancel]").click();
      };
      matrixDialog.onclose = () => {
        if (matrixDialog.returnValue !== "save") opener.focus();
      };
    }

    function reorderQuestions(from, to) {
      const form = currentForm();
      if (!form || from === to || to < 0 || to >= form.questions.length) return;
      const [question] = form.questions.splice(from, 1);
      form.questions.splice(to, 0, question);
      openQuestion = to;
      renderEditor();
      setDirty();
    }

    function renderQuestions(form) {
      const section = node("section", "managed-questions");
      section.append(node("h3", "", "Vragen"));
      const list = node("div", "managed-question-list");
      form.questions.forEach((question, index) => {
        const item = node("article", "managed-question");
        item.dataset.questionIndex = String(index);
        const header = node("div", "question-heading");
        const drag = iconButton("drag", "Versleep vraag", "drag-handle", null);
        drag.draggable = !locked;
        drag.disabled = locked;
        drag.setAttribute("aria-label", "Vraag verslepen");
        const title = node("button", `question-title${question.question ? "" : " is-placeholder"}`, question.question || "Nieuwe vraag");
        title.type = "button";
        title.title = question.question || "Nieuwe vraag";
        title.addEventListener("click", () => { openQuestion = openQuestion === index ? -1 : index; renderEditor(); });
        const actionsGroup = node("div", "question-actions");
        const reorder = node("div", "reorder-actions");
        const moveUp = iconButton("up", "Vraag omhoog", "icon-action", () => reorderQuestions(index, index - 1));
        const moveDown = iconButton("down", "Vraag omlaag", "icon-action", () => reorderQuestions(index, index + 1));
        moveUp.disabled = locked || index === 0;
        moveDown.disabled = locked || index === form.questions.length - 1;
        reorder.append(moveUp, moveDown);
        actionsGroup.append(reorder);
        actionsGroup.append(iconButton("copy", "Dupliceren", "icon-action", () => {
          form.questions.splice(index + 1, 0, structuredClone(question));
          openQuestion = index + 1;
          renderEditor();
          setDirty();
        }));
        actionsGroup.append(iconButton("trash", "Verwijderen", "icon-action danger", async () => {
          if (!await confirm("Deze vraag verwijderen?", "Verwijderen")) return;
          form.questions.splice(index, 1);
          openQuestion = Math.min(openQuestion, form.questions.length - 1);
          renderEditor();
          setDirty();
        }));
        const disclosure = iconButton("chevron", openQuestion === index ? "Vraag sluiten" : "Vraag openen", "question-disclosure", () => {
          openQuestion = openQuestion === index ? -1 : index;
          renderEditor();
        });
        disclosure.setAttribute("aria-expanded", String(openQuestion === index));
        actionsGroup.append(disclosure);
        header.append(drag, title, actionsGroup);
        item.append(header);
        if (openQuestion === index) {
          const body = node("div", "question-body");
          renderQuestionFields(question, index, body);
          item.append(body);
        }
        list.append(item);
      });
      list.addEventListener("dragstart", (event) => {
        const handle = event.target.closest(".drag-handle");
        if (!handle || locked) { event.preventDefault(); return; }
        event.dataTransfer.setData("text/plain", handle.closest("[data-question-index]").dataset.questionIndex);
        event.dataTransfer.effectAllowed = "move";
      });
      list.addEventListener("dragover", (event) => { if (event.target.closest("[data-question-index]")) event.preventDefault(); });
      list.addEventListener("drop", (event) => {
        const target = event.target.closest("[data-question-index]");
        const from = Number(event.dataTransfer.getData("text/plain"));
        if (target) reorderQuestions(from, Number(target.dataset.questionIndex));
      });
      section.append(list);
      const add = node("button", "new-question", "Nieuwe vraag +");
      add.type = "button";
      add.disabled = locked;
      add.addEventListener("click", () => { form.questions.push(blankQuestion()); openQuestion = form.questions.length - 1; renderEditor(); setDirty(); });
      section.append(add);
      return section;
    }

    function renderFormList() {
      if (!formList) return;
      formList.replaceChildren();
      state.forms.forEach((form, index) => {
        const item = node("li", `managed-form-row${form.id === selectedFormId ? " selected" : ""}`);
        item.dataset.formId = String(form.id);
        const drag = iconButton("drag", "Formulier verslepen", "drag-handle", null);
        drag.draggable = !locked;
        drag.disabled = locked;
        const select = node("button", "managed-form-select", form.title || "Naamloos formulier");
        select.type = "button";
        select.addEventListener("click", async () => {
          if (form.id === selectedFormId || !await discardIfNeeded()) return;
          selectedFormId = form.id;
          openQuestion = 0;
          renderEditor();
        });
        const move = node("div", "reorder-actions");
        const moveUp = iconButton("up", `Formulier omhoog: ${form.title || "Naamloos formulier"}`, "icon-action", async () => moveForm(index, -1));
        const moveDown = iconButton("down", `Formulier omlaag: ${form.title || "Naamloos formulier"}`, "icon-action", async () => moveForm(index, 1));
        moveUp.disabled = locked || index === 0;
        moveDown.disabled = locked || index === state.forms.length - 1;
        select.disabled = locked;
        move.append(moveUp, moveDown);
        item.append(drag, select, move);
        formList.append(item);
      });
    }

    function formDragStart(event) {
      const handle = event.target.closest(".drag-handle");
      if (!handle || locked) { event.preventDefault(); return; }
      event.dataTransfer.setData("text/plain", handle.closest("[data-form-id]").dataset.formId);
    }
    function formDragOver(event) { if (event.target.closest("[data-form-id]")) event.preventDefault(); }
    async function formDrop(event) {
      const target = event.target.closest("[data-form-id]");
      if (!target) return;
      const sourceId = Number(event.dataTransfer.getData("text/plain"));
      const targetId = Number(target.dataset.formId);
      await reorderForms(sourceId, targetId);
    }

    async function reorderForms(sourceId, targetId) {
      if (!await discardIfNeeded()) return;
      const source = state.forms.findIndex((form) => form.id === sourceId);
      const target = state.forms.findIndex((form) => form.id === targetId);
      if (source < 0 || target < 0 || source === target) return;
      const [moved] = state.forms.splice(source, 1);
      state.forms.splice(target, 0, moved);
      try {
        await post(root.dataset.actionUrl, { action: "reorder_forms", formIds: state.forms.map((form) => form.id) });
        saved = structuredClone(state);
        renderEditor();
      } catch (error) { state = structuredClone(saved); renderEditor(); toast(error.message, error.warning); }
    }

    async function moveForm(index, offset) {
      const target = state.forms[index + offset];
      if (target) await reorderForms(state.forms[index].id, target.id);
    }

    function renderEditor() {
      renderFormList();
      editor.replaceChildren();
      actions.replaceChildren();
      const form = currentForm();
      if (!form) {
        editor.append(node("p", "empty-state", "Nog geen formulieren. Kies Nieuw + om een formulier toe te voegen."));
        return;
      }
      if (!standalone) {
        const removeForm = node("button", "outline button danger-outline", "Verwijderen");
        removeForm.type = "button";
        removeForm.disabled = locked;
        removeForm.addEventListener("click", async () => {
          if (!await discardIfNeeded()) return;
          if (!await confirm(`Formulier \u201c${form.title || "Naamloos formulier"}\u201d verwijderen?`, "Verwijderen")) return;
          try {
            await post(root.dataset.actionUrl, { action: "delete_form", formId: form.id });
            state.forms = state.forms.filter((item) => item.id !== form.id);
            selectedFormId = state.forms[0]?.id ?? null;
            saved = structuredClone(state);
            renderEditor();
            toast("Formulier verwijderd");
          } catch (error) { toast(error.message, error.warning); }
        });
        actions.append(removeForm);
      }
      saveButton.disabled = locked || !dirty;
      actions.append(saveButton);
      const fields = node("div", "managed-form-fields");
      if (!standalone) {
        const title = addTextField(fields, "Naam van het formulier", form.title, (value) => {
          form.title = value;
          const selected = formList?.querySelector(`[data-form-id="${form.id}"] .managed-form-select`);
          if (selected) selected.textContent = value || "Naamloos formulier";
          setDirty();
        }, { wide: true, maxLength: 180 });
        title.disabled = locked;
      }
      editor.append(fields, renderQuestions(form));
      editor.querySelectorAll("input,textarea,select,button").forEach((control) => {
        if (control !== saveButton) control.disabled = locked || control.disabled;
      });
      root.querySelectorAll(".drag-handle").forEach((handle) => { handle.draggable = !locked; });
      root.querySelector("[data-new-form]")?.toggleAttribute("disabled", locked);
      renameButton.disabled = locked || data.std;
      lockButton.querySelector("span").textContent = locked ? "Ontgrendelen" : "Vergrendelen";
      lockButton.setAttribute("aria-pressed", String(locked));
    }

    async function saveCurrentForm() {
      const form = currentForm();
      if (!form || !dirty) return;
      if (!standalone && !form.title.trim()) {
        toast("Geef het formulier een naam", true);
        return;
      }
      try {
        const result = await post(root.dataset.actionUrl, {
          action: "save_form", formId: form.id, title: form.title,
          questions: form.questions,
        });
        saved = structuredClone(state);
        dirty = false;
        saveButton.disabled = true;
        toast(result.message);
      } catch (error) { toast(error.message, error.warning); }
    }
    saveButton.addEventListener("click", saveCurrentForm);

    root.querySelector("[data-new-form]")?.addEventListener("click", async () => {
      if (!await discardIfNeeded()) return;
      try {
        const result = await post(root.dataset.actionUrl, { action: "create_form" });
        state.forms.push(result.form);
        selectedFormId = result.form.id;
        saved = structuredClone(state);
        openQuestion = 0;
        renderEditor();
      } catch (error) { toast(error.message, error.warning); }
    });

    lockButton.addEventListener("click", async () => {
      if (!await discardIfNeeded()) return;
      try {
        const result = await post(root.dataset.actionUrl, { action: "toggle_lock" });
        locked = result.locked;
        data.locked = locked;
        renderEditor();
        toast(result.message);
      } catch (error) { toast(error.message, error.warning); }
    });

    renameButton.addEventListener("click", async () => {
      if (locked || !await discardIfNeeded()) return;
      const result = await dialog("Functienaam wijzigen", "Voer een nieuwe naam in.", { input: true, value: state.title, confirmText: "Opslaan" });
      if (!result.confirmed || !result.value || result.value === state.title) return;
      try {
        const response = await post(root.dataset.actionUrl, { action: "rename", title: result.value });
        state.title = response.title;
        saved.title = response.title;
        if (standalone && state.forms[0]) {
          state.forms[0].title = response.title;
          saved.forms[0].title = response.title;
        }
        root.querySelector("[data-function-title]").textContent = response.title;
        document.title = `${response.title} | Functies beheer`;
        renderEditor();
        toast(response.message);
      } catch (error) { toast(error.message, error.warning); }
    });

    root.querySelector("[data-preview]").addEventListener("click", (event) => {
      const button = event.currentTarget;
      const showPreview = button.getAttribute("aria-pressed") !== "true";
      button.setAttribute("aria-pressed", String(showPreview));
      editorPanel.hidden = showPreview;
      root.querySelector("[data-editor-layout]").hidden = showPreview;
      previewPanel.hidden = !showPreview;
      if (showPreview) renderPreview(saved);
    });

    function renderPreview(snapshot) {
      previewContent.replaceChildren();
      previewContent.append(node("h2", "", snapshot.title));
      const forms = snapshot.forms || [];
      let activeIndex = 0;
      const sections = [];
      if (forms.length > 1) {
        const navigation = node("nav", "function-form-navigation", "Formulieren");
        navigation.setAttribute("aria-label", "Formulieren");
        const list = node("div", "preview-form-list");
        forms.forEach((form, index) => {
          const button = node("button", `form-navigation-item${index === 0 ? " is-active" : ""}`, form.title || "Naamloos formulier");
          button.type = "button";
          button.setAttribute("aria-pressed", String(index === 0));
          button.addEventListener("click", () => {
            activeIndex = index;
            sections.forEach((section, sectionIndex) => { section.hidden = sectionIndex !== activeIndex; });
            list.querySelectorAll("button").forEach((item, itemIndex) => {
              item.classList.toggle("is-active", itemIndex === activeIndex);
              item.setAttribute("aria-pressed", String(itemIndex === activeIndex));
            });
          });
          list.append(button);
        });
        navigation.append(list);
        previewContent.append(navigation);
      }
      forms.forEach((form, formIndex) => {
        const section = node("section", "preview-form");
        section.hidden = formIndex !== activeIndex;
        if (!standalone) section.append(node("h3", "", form.title));
        form.questions.forEach((question) => {
          const questionWrap = node("div", "preview-question");
          if (question.fieldType === "info") {
            questionWrap.append(node("p", "", question.explanation));
          } else if (question.fieldType === "image") {
            if (question.image) {
              const image = node("img", "preview-image");
              image.src = question.image;
              image.alt = question.caption || question.question || "Afbeelding";
              questionWrap.append(image);
            }
            if (question.caption) questionWrap.append(node("p", "", question.caption));
          } else if (question.fieldType === "link") {
            questionWrap.append(node("h4", "", question.question));
            const url = safeHttpUrl(question.url);
            if (url) {
              const link = node("a", "primary button", question.buttonText || "Openen");
              link.href = url;
              link.target = "_blank";
              link.rel = "noopener";
              questionWrap.append(link);
            }
          } else {
            questionWrap.append(node("label", "preview-label", question.question || "Vraag"));
            const control = previewControl(question);
            questionWrap.append(control);
            if (question.unit) questionWrap.append(node("span", "preview-unit", question.unit));
          }
          section.append(questionWrap);
        });
        previewContent.append(section);
        sections.push(section);
      });
    }

    function safeHttpUrl(value) {
      try { const parsed = new URL(value); return ["http:", "https:"].includes(parsed.protocol) ? parsed.href : ""; }
      catch { return ""; }
    }

    function previewControl(question) {
      const typeMap = { text: "text", number: "number", date: "date", dateTime: "datetime-local", imageUpload: "file", fileUpload: "file" };
      if (question.fieldType === "multipleChoice") {
        const group = node("fieldset", "preview-options");
        const groupName = `answer-${question.id ?? "new"}-${Math.random()}`;
        question.options.forEach((answer, index) => {
          const label = node("label");
          const radio = node("input"); radio.type = "radio"; radio.name = groupName; radio.value = answer;
          label.append(radio, node("span", "", answer)); group.append(label);
        });
        return group;
      }
      if (question.fieldType === "matrix") {
        const scroll = node("div", "matrix-scroll");
        const table = node("table", "preview-matrix");
        const head = node("tr"); head.append(node("th", "", ""));
        question.columns.forEach((column) => head.append(node("th", "", column)));
        const thead = node("thead"); thead.append(head); table.append(thead);
        const body = node("tbody");
        question.rows.forEach((rowTitle) => {
          const row = node("tr"); row.append(node("th", "", rowTitle));
          question.columns.forEach((column, index) => {
            const cell = node("td"); const input = node("input"); input.type = "text"; input.setAttribute("aria-label", `${rowTitle || "Rij"}, ${column || `kolom ${index + 1}`}`); cell.append(input); row.append(cell);
          });
          body.append(row);
        });
        table.append(body); scroll.append(table); return scroll;
      }
      if (question.fieldType === "observation") {
        const group = node("div", "observation-entry");
        const list = node("div", "observation-list");
        list.append(node("p", "muted", "Nog geen observaties."));
        group.append(list);
        const timestamp = node("input", "managed-input");
        timestamp.type = "datetime-local";
        timestamp.setAttribute("aria-label", "Observaties: tijdstip");
        group.append(timestamp);
        const value = node("input", "managed-input");
        value.placeholder = "Waarde of observatie";
        value.setAttribute("aria-label", "Observaties: waarde of observatie");
        group.append(value);
        const note = node("input", "managed-input");
        note.placeholder = "Toelichting";
        note.setAttribute("aria-label", "Observaties: toelichting");
        group.append(note);
        group.append(node("button", "outline button", "Observatie en wijzigingen bewaren"));
        return group;
      }
      const input = node("input", "managed-input");
      input.type = typeMap[question.fieldType] || "text";
      input.required = Boolean(question.required);
      return input;
    }

    root.querySelector("[data-editor-back]").addEventListener("click", async (event) => {
      if (!isDirty()) return;
      event.preventDefault();
      const destination = event.currentTarget.href;
      if (await discardIfNeeded()) window.location.assign(destination);
    });
    window.addEventListener("beforeunload", (event) => {
      if (!dirty) return;
      event.preventDefault();
      event.returnValue = "";
    });
    renderEditor();
  }

  if (root.dataset.functionPage === "list") initList();
  if (root.dataset.functionPage === "deleted") initDeleted();
  if (root.dataset.functionPage === "general") initGeneral();
  if (root.dataset.functionPage === "editor") initEditor();
})();
