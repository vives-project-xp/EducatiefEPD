(() => {g
  const root = document.querySelector("[data-function-page]");
  if (!root) return;

  const symbols = {
    trash: "🗑︎", copy: "⧉", up: "↑", down: "↓", drag: "⠿",
    chevron: "›", warning: "⚠︎", plus: "+",
  };
  const stringsElement = root.querySelector("#function-management-strings");
  const strings = stringsElement ? JSON.parse(stringsElement.textContent) : {};

  function text(key, values = {}) {
    const template = strings[key] || key;
    return template.replace(/%\((\w+)\)s/g, (_, name) => values[name] ?? "");
  }

  function node(tag, className = "", text = "") {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (text !== undefined && text !== null) element.textContent = text;
    return element;
  }

  function symbol(name) {
    const element = node("span", "function-symbol", symbols[name] || "");
    element.setAttribute("aria-hidden", "true");
    return element;
  }

  function csrfToken() {
    return root.querySelector(".function-csrf [name='csrfmiddlewaretoken']")?.value || "";
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
      const error = new Error(result.message || text("genericError"));
      error.warning = Boolean(result.warning);
      throw error;
    }
    return result;
  }

  function toast(message, warning = false) {
    const region = root.querySelector(".function-toast-region");
    if (!region) return;
    const item = node("p", `message ${warning ? "warning" : "success"}`);
    if (warning) item.append(symbol("warning"));
    item.append(node("span", "", message));
    region.replaceChildren(item);
    window.setTimeout(() => item.remove(), 4200);
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
      button.addEventListener("click", () => toast(text("standardWarning"), true));
    });
    root.querySelectorAll("[data-delete-function]").forEach((button) => {
      button.addEventListener("click", async () => {
        if (!window.confirm(text("deleteFunction", { title: button.dataset.title }))) return;
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
          ? text("deletePermanent", { title: button.dataset.title })
          : text("restore");
        if (deleting && !window.confirm(message)) return;
        try {
          const result = await post(url, { action: button.dataset.trashAction, functionId: Number(button.dataset.id) });
          toast(result.message);
          window.setTimeout(() => window.location.assign(result.redirect), 1000);
        } catch (error) { toast(error.message, error.warning); }
      });
    });
    root.querySelector("[data-empty-trash]")?.addEventListener("click", async (event) => {
      if (event.currentTarget.disabled || !window.confirm(text("emptyTrash"))) return;
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

  const fieldTypes = strings.fieldTypes || [];
  const informative = new Set(["image", "link", "info"]);

  function blankQuestion() {
    return { fieldType: "text", question: "", unit: "", required: false, options: [], columns: [], rows: [], url: "", buttonText: "", image: "", caption: "", explanation: "" };
  }

  function initEditor() {
    let data;
    try { data = JSON.parse(root.querySelector("#managed-function-data").textContent); }
    catch { toast(text("emptyFunctionData"), true); return; }
    let state = structuredClone(data);
    let saved = structuredClone(data);
    let selectedFormId = state.forms[0]?.id ?? null;
    let openQuestion = 0;
    let dirty = false;
    const standalone = root.dataset.standalone === "true";
    let locked = data.locked;
    const formList = root.querySelector("[data-form-list]");
    const editorPanel = root.querySelector("[data-editor-panel]");
    const editor = root.querySelector("[data-form-editor]");
    const actions = root.querySelector("[data-form-actions]");
    const previewPanel = root.querySelector("[data-preview-panel]");
    const previewContent = root.querySelector("[data-preview-content]");
    const lockButton = root.querySelector("[data-lock]");
    const renameButton = root.querySelector("[data-rename]");
    const saveButton = node("button", "primary button", text("saveChanges"));
    saveButton.type = "button";
    saveButton.disabled = true;
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
      if (!window.confirm(text("unsavedChanges"))) return false;
      state = structuredClone(saved);
      if (!state.forms.some((form) => form.id === selectedFormId)) {
        selectedFormId = state.forms[0]?.id ?? null;
      }
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
      button.append(symbol(name));
      if (action) button.addEventListener("click", action);
      return button;
    }

    function fieldSelect(question, index) {
      const label = node("label", "managed-field field-wide");
      label.append(node("span", "managed-label", text("questionType")));
      const select = node("select", "managed-input");
      fieldTypes.forEach((group) => {
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
            toast(text("matrixLimit"), true);
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
          const remove = iconButton("trash", `${text("delete")}: ${title}`, "text-button function-icon-button danger", () => {
          values.splice(index, 1);
          renderEditor();
          setDirty();
        });
        row.append(input, remove);
        rows.append(row);
      });
      const addLabel = {
        [text("answerOptions")]: text("addOption"),
        [text("columns")]: text("addColumn"),
        [text("rows")]: text("addRow"),
      }[title] || text("add");
      const add = node("button", "outline button", addLabel);
      add.type = "button";
      add.addEventListener("click", () => { values.push(""); renderEditor(); setDirty(); });
      section.append(rows, add);
      container.append(section);
    }

    function renderQuestionFields(question, index, body) {
      body.append(fieldSelect(question, index));
      const change = () => setDirty();
      if (question.fieldType === "info") {
        addTextField(body, text("explanation"), question.explanation, (value) => { question.explanation = value; change(); }, { multiline: true, wide: true, rows: 5 });
      } else if (question.fieldType === "link") {
        addTextField(body, text("title"), question.question, (value) => { question.question = value; change(); }, { wide: true });
        addTextField(body, text("link"), question.url, (value) => { question.url = value; change(); }, { type: "url" });
        addTextField(body, text("buttonText"), question.buttonText, (value) => { question.buttonText = value; change(); });
      } else if (question.fieldType === "image") {
        const wrapper = node("div", "managed-field field-wide");
        const input = node("input", "managed-input image-picker");
        input.type = "file";
        input.id = `managed-image-${index}`;
        input.accept = "image/png,image/jpeg,image/gif,image/webp";
        const imageLabel = node("label", "managed-label");
        imageLabel.htmlFor = input.id;
        imageLabel.textContent = question.image ? text("imageReplace") : text("imageChoose");
        wrapper.append(imageLabel, input);
        input.addEventListener("change", () => {
          const file = input.files?.[0];
          if (!file) return;
          if (!file.type.startsWith("image/") || file.size > 300_000) {
            toast(file.size > 300_000 ? text("imageTooLarge") : text("invalidImage"), true);
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
          image.alt = text("imagePreviewAlt");
          wrapper.append(image);
          const remove = node("button", "text-button danger", text("imageRemove"));
          remove.type = "button";
          remove.addEventListener("click", () => { question.image = ""; renderEditor(); setDirty(); });
          wrapper.append(remove);
        }
        body.append(wrapper);
        addTextField(body, text("caption"), question.caption, (value) => { question.caption = value; change(); }, { wide: true });
      } else if (!informative.has(question.fieldType)) {
        addTextField(body, text("question"), question.question, (value) => { question.question = value; change(); }, { wide: true });
        checkboxField(body, text("required"), question.required, (value) => { question.required = value; change(); });
        if (["text", "number"].includes(question.fieldType)) {
          addTextField(body, text("unit"), question.unit, (value) => { question.unit = value; change(); });
        }
        if (question.fieldType === "multipleChoice") listField(body, text("answerOptions"), question.options, change);
        if (question.fieldType === "matrix") {
          listField(body, text("columns"), question.columns, change);
          listField(body, text("rows"), question.rows, change);
        }
      }
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
      section.append(node("h3", "", text("questions")));
      const list = node("div", "managed-question-list");
      form.questions.forEach((question, index) => {
        const item = node("article", "managed-question");
        item.dataset.questionIndex = String(index);
        const header = node("div", "question-heading");
        const drag = iconButton("drag", text("dragQuestion"), "drag-handle", null);
        drag.draggable = !locked;
        drag.disabled = locked;
        drag.setAttribute("aria-label", text("dragQuestion"));
        const title = node("button", `question-title${question.question ? "" : " is-placeholder"}`, question.question || text("newQuestion"));
        title.type = "button";
        title.title = question.question || text("newQuestion");
        title.addEventListener("click", () => { openQuestion = openQuestion === index ? -1 : index; renderEditor(); });
        const actionsGroup = node("div", "question-actions");
        const reorder = node("div", "reorder-actions");
        const moveUp = iconButton("up", text("moveQuestionUp"), "text-button function-icon-button", () => reorderQuestions(index, index - 1));
        const moveDown = iconButton("down", text("moveQuestionDown"), "text-button function-icon-button", () => reorderQuestions(index, index + 1));
        moveUp.disabled = locked || index === 0;
        moveDown.disabled = locked || index === form.questions.length - 1;
        reorder.append(moveUp, moveDown);
        actionsGroup.append(reorder);
        actionsGroup.append(iconButton("copy", text("duplicate"), "text-button function-icon-button", () => {
          form.questions.splice(index + 1, 0, structuredClone(question));
          openQuestion = index + 1;
          renderEditor();
          setDirty();
        }));
        actionsGroup.append(iconButton("trash", text("delete"), "text-button function-icon-button danger", async () => {
          if (!window.confirm(text("deleteQuestion"))) return;
          form.questions.splice(index, 1);
          openQuestion = Math.min(openQuestion, form.questions.length - 1);
          renderEditor();
          setDirty();
        }));
        const disclosure = iconButton("chevron", openQuestion === index ? text("closeQuestion") : text("openQuestion"), "text-button function-icon-button question-disclosure", () => {
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
      const add = node("button", "new-question", `${text("newQuestion")} +`);
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
        const drag = iconButton("drag", text("dragForm"), "drag-handle", null);
        drag.draggable = !locked && form.id !== null;
        drag.disabled = locked || form.id === null;
        const select = node("button", "managed-form-select", form.title || text("unnamedForm"));
        select.type = "button";
        select.addEventListener("click", async () => {
          if (form.id === selectedFormId || !await discardIfNeeded()) return;
          selectedFormId = form.id;
          openQuestion = 0;
          renderEditor();
        });
        const move = node("div", "reorder-actions");
        const moveUp = iconButton("up", `${text("moveFormUp")}: ${form.title || text("unnamedForm")}`, "text-button function-icon-button", async () => moveForm(index, -1));
        const moveDown = iconButton("down", `${text("moveFormDown")}: ${form.title || text("unnamedForm")}`, "text-button function-icon-button", async () => moveForm(index, 1));
        moveUp.disabled = locked || form.id === null || index === 0;
        moveDown.disabled = locked || form.id === null || index === state.forms.length - 1;
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
      if (state.forms.some((form) => form.id === null)) {
        toast(text("saveDraftFirst"), true);
        return;
      }
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
        editor.append(node("p", "empty-state", text("noForms")));
        return;
      }
      if (!standalone && form.id !== null) {
        const removeForm = node("button", "outline button danger-outline", text("delete"));
        removeForm.type = "button";
        removeForm.disabled = locked;
        removeForm.addEventListener("click", async () => {
          if (!await discardIfNeeded()) return;
          if (!window.confirm(text("deleteForm", { title: form.title || text("unnamedForm") }))) return;
          try {
            await post(root.dataset.actionUrl, { action: "delete_form", formId: form.id });
            state.forms = state.forms.filter((item) => item.id !== form.id);
            selectedFormId = state.forms[0]?.id ?? null;
            saved = structuredClone(state);
            renderEditor();
            toast(text("formRemoved"));
          } catch (error) { toast(error.message, error.warning); }
        });
        actions.append(removeForm);
      }
      saveButton.disabled = locked || !dirty;
      actions.append(saveButton);
      const fields = node("div", "managed-form-fields");
      if (!standalone) {
        fields.append(node("h3", "managed-form-name", text("formName")));
        const title = addTextField(fields, text("name"), form.title, (value) => {
          form.title = value;
          const selected = formList?.querySelector(`[data-form-id="${form.id}"] .managed-form-select`);
          if (selected) selected.textContent = value || text("unnamedForm");
          setDirty();
        }, { wide: true, maxLength: 180 });
        title.disabled = locked;
      }
      editor.append(fields, renderQuestions(form));
      editor.querySelectorAll("input,textarea,select,button").forEach((control) => {
        if (control !== saveButton) control.disabled = locked || control.disabled;
      });
      root.querySelectorAll(".drag-handle").forEach((handle) => { handle.draggable = !locked && !handle.disabled; });
      root.querySelector("[data-new-form]")?.toggleAttribute("disabled", locked);
      renameButton.disabled = locked || data.std;
      lockButton.querySelector("[data-lock-label]").textContent = locked ? text("unlock") : text("lock");
      lockButton.setAttribute("aria-pressed", String(locked));
    }

    async function saveCurrentForm() {
      const form = currentForm();
      if (!form || !dirty) return;
      if (!standalone && !form.title.trim()) {
        toast(text("formNameRequired"), true);
        return;
      }
      try {
        const result = await post(root.dataset.actionUrl, {
          action: "save_form", formId: form.id, isNew: form.id === null, title: form.title,
          questions: form.questions,
        });
        form.id = result.formId;
        form.position = state.forms.indexOf(form);
        selectedFormId = form.id;
        saved = structuredClone(state);
        dirty = false;
        saveButton.disabled = true;
        renderEditor();
        toast(result.message || text("saved"));
      } catch (error) { toast(error.message, error.warning); }
    }
    saveButton.addEventListener("click", saveCurrentForm);

    root.querySelector("[data-new-form]")?.addEventListener("click", async () => {
      if (!await discardIfNeeded()) return;
      state.forms.push({
        id: null,
        title: "",
        position: state.forms.length,
        questions: [],
      });
      selectedFormId = null;
      openQuestion = 0;
      setDirty();
      renderEditor();
    });

    lockButton.addEventListener("click", async () => {
      if (!await discardIfNeeded()) return;
      try {
        const result = await post(root.dataset.actionUrl, { action: "toggle_lock" });
        locked = result.locked;
        data.locked = locked;
        renderEditor();
        toast(locked ? text("functionLocked") : text("functionUnlocked"));
      } catch (error) { toast(error.message, error.warning); }
    });

    renameButton.addEventListener("click", async () => {
      if (locked || !await discardIfNeeded()) return;
      const proposedTitle = window.prompt(
        `${text("functionNameTitle")}\n${text("enterNewName")}`,
        state.title,
      );
      const nextTitle = proposedTitle?.trim() || "";
      if (!nextTitle || nextTitle === state.title) return;
      try {
        const response = await post(root.dataset.actionUrl, { action: "rename", title: nextTitle });
        state.title = response.title;
        saved.title = response.title;
        if (standalone && state.forms[0]) {
          state.forms[0].title = response.title;
          saved.forms[0].title = response.title;
        }
        root.querySelector("[data-function-title]").textContent = response.title;
        document.title = `${response.title} | ${text("managementTitle")}`;
        renderEditor();
        toast(text("functionRenamed"));
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
      let questionNumber = 0;
      snapshot.forms.forEach((form) => {
        const section = node("section", "editor-section preview-form");
        if (!standalone) section.append(node("h3", "", form.title));
        if (!form.questions.length) section.append(node("p", "empty-state", text("noQuestions")));
        form.questions.forEach((question) => {
          const questionWrap = node("div", "preview-question");
          const controlId = `preview-${form.id}-${question.id || questionNumber++}`;
          if (question.fieldType === "info") {
            questionWrap.append(node("p", "", question.explanation));
          } else if (question.fieldType === "image") {
            if (question.image) {
              const image = node("img", "preview-image");
              image.src = question.image;
              image.alt = question.caption || question.question || text("image");
              questionWrap.append(image);
            }
            if (question.caption) questionWrap.append(node("p", "", question.caption));
          } else if (question.fieldType === "link") {
            questionWrap.append(node("h4", "", question.question));
            const url = safeHttpUrl(question.url);
            if (url) {
              const link = node("a", "primary button", question.buttonText || text("open"));
              link.href = url;
              link.target = "_blank";
              link.rel = "noopener";
              questionWrap.append(link);
            }
          } else if (question.fieldType === "matrix") {
            questionWrap.append(node("h4", "", question.question || text("question")));
            questionWrap.append(previewControl(question, controlId));
          } else {
            const control = previewControl(question, controlId);
            if (question.fieldType !== "multipleChoice") {
              const label = node("label", "preview-label", question.question || text("question"));
              label.htmlFor = controlId;
              questionWrap.append(label);
            }
            questionWrap.append(control);
            if (question.unit) questionWrap.append(node("span", "preview-unit", question.unit));
          }
          section.append(questionWrap);
        });
        previewContent.append(section);
      });
    }

    function safeHttpUrl(value) {
      try { const parsed = new URL(value); return ["http:", "https:"].includes(parsed.protocol) ? parsed.href : ""; }
      catch { return ""; }
    }

    function previewControl(question, controlId) {
      const typeMap = { text: "text", number: "number", date: "date", dateTime: "datetime-local", time: "time", imageUpload: "file", fileUpload: "file" };
      if (question.fieldType === "multipleChoice") {
        const group = node("fieldset", "preview-options");
        group.append(node("legend", "", question.question || text("question")));
        question.options.forEach((answer, index) => {
          const label = node("label");
          const radio = node("input");
          radio.type = "radio";
          radio.id = `${controlId}-${index}`;
          radio.name = controlId;
          radio.value = answer;
          radio.required = Boolean(question.required);
          label.htmlFor = radio.id;
          label.append(radio, node("span", "", answer)); group.append(label);
        });
        return group;
      }
      if (question.fieldType === "matrix") {
        const scroll = node("div", "matrix-wrap");
        const table = node("table");
        const head = node("tr");
        const corner = node("th");
        corner.scope = "col";
        head.append(corner);
        question.columns.forEach((column) => {
          const heading = node("th", "", column);
          heading.scope = "col";
          head.append(heading);
        });
        const thead = node("thead"); thead.append(head); table.append(thead);
        const body = node("tbody");
        question.rows.forEach((rowTitle, rowIndex) => {
          const row = node("tr");
          const heading = node("th", "", rowTitle);
          heading.scope = "row";
          row.append(heading);
          question.columns.forEach((column, columnIndex) => {
            const cell = node("td");
            const input = node("input", "managed-input");
            input.id = `${controlId}-${rowIndex}-${columnIndex}`;
            input.type = "text";
            input.required = Boolean(question.required);
            input.setAttribute("aria-label", `${rowTitle || text("row")}, ${column || text("column", { number: columnIndex + 1 })}`);
            cell.append(input);
            row.append(cell);
          });
          body.append(row);
        });
        table.append(body);
        scroll.append(table);
        return scroll;
      }
      const input = node("input", "managed-input");
      input.id = controlId;
      input.type = typeMap[question.fieldType] || "text";
      input.required = Boolean(question.required);
      if (question.fieldType === "imageUpload") input.accept = "image/*";
      return input;
    }

    root.querySelector("[data-editor-back]").addEventListener("click", async (event) => {
      if (!await discardIfNeeded()) event.preventDefault();
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
