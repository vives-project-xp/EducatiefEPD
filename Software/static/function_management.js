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
    function pageUrl(pageNumber) {
      const url = new URL(window.location.href);
      url.searchParams.set(root.dataset.pageParam || "page", String(pageNumber));
      if (root.dataset.embeddedFunctions === "true") {
        url.searchParams.set("manage_functions", "1");
        url.hash = "function-management";
      }
      return url.href;
    }

    function updateAfterDelete(button, result) {
      const row = button.closest("[data-function-row]");
      if (!row) throw new Error("De functie kon niet uit de lijst worden verwijderd.");
      row.remove();

      const activeCount = Number(result.activeCount);
      const deletedCount = Number(result.deletedCount);
      const pageNumber = Number(root.dataset.pageNumber);
      const pageSize = Number(root.dataset.pageSize);
      if (
        !Number.isInteger(activeCount) || activeCount < 0
        || !Number.isInteger(deletedCount) || deletedCount < 0
        || !Number.isInteger(pageNumber) || pageNumber < 1
        || !Number.isInteger(pageSize) || pageSize < 1
      ) {
        throw new Error("De bijgewerkte functielijst kon niet worden weergegeven.");
      }

      root.dataset.totalCount = String(activeCount);
      const list = root.querySelector("[data-function-list]");
      const rows = [...list.querySelectorAll("[data-function-row]")];
      const totalPages = Math.ceil(activeCount / pageSize);
      if (!rows.length) {
        const emptyMessage = activeCount === 0
          ? (root.dataset.query
            ? "Geen functies gevonden."
            : "Er zijn nog geen functies. Maak een functie aan om te beginnen.")
          : "De laatste functie op deze pagina is verwijderd. Gebruik Vorige om verder te bladeren.";
        list.replaceChildren(node("p", "empty-state", emptyMessage));
      }

      const count = root.querySelector("[data-function-count]");
      if (count) {
        count.hidden = activeCount === 0 || pageNumber > totalPages;
        if (!count.hidden) {
          const firstIndex = (pageNumber - 1) * pageSize + 1;
          const lastIndex = Math.min(firstIndex + rows.length - 1, activeCount);
          count.textContent = `${firstIndex}–${lastIndex} van ${activeCount}`;
        }
      }

      const deletedCountNode = root.querySelector("[data-deleted-count]");
      if (deletedCountNode) {
        deletedCountNode.textContent = deletedCount ? ` (${deletedCount})` : "";
      }

      const pagination = root.querySelector("[data-function-pagination]");
      if (pagination) {
        const previous = pagination.querySelector('[data-function-page-link="previous"]');
        const next = pagination.querySelector('[data-function-page-link="next"]');
        const hasPrevious = pageNumber > 1;
        const hasNext = pageNumber < totalPages;
        if (previous) {
          previous.hidden = !hasPrevious;
          if (hasPrevious) previous.href = pageUrl(pageNumber - 1);
        }
        if (next) {
          next.hidden = !hasNext;
          if (hasNext) next.href = pageUrl(pageNumber + 1);
        }
        const pageInfo = pagination.querySelector("[data-function-page-info]");
        if (pageInfo) {
          pageInfo.textContent = pageNumber > totalPages
            ? "Geen functies op deze pagina"
            : `Pagina ${pageNumber} van ${totalPages}`;
        }
        pagination.hidden = !hasPrevious && !hasNext;
      }
    }

    root.querySelector("[data-page-size]")?.addEventListener("change", (event) => {
      event.currentTarget.form.submit();
    });
    const sortButton = root.querySelector("[data-sort-control]");
    sortButton?.addEventListener("click", () => {
      const sequence = ["az", "za", "oldest"];
      const next = sequence[(sequence.indexOf(sortButton.dataset.sort) + 1) % sequence.length];
      const url = new URL(window.location.href);
      url.searchParams.set(root.dataset.sortParam || "sort", next);
      if (root.dataset.embeddedFunctions === "true") {
        url.searchParams.set("manage_functions", "1");
        url.hash = "function-management";
      }
      window.location.assign(url);
    });
    root.querySelectorAll("[data-standard-warning]").forEach((button) => {
      button.addEventListener("click", () => toast("Standaardfuncties mogen niet worden bewerkt.", true));
    });
    root.querySelectorAll("[data-duplicate-function]").forEach((button) => {
      button.addEventListener("click", async () => {
        button.disabled = true;
        try {
          const result = await post(button.dataset.url, { action: "duplicate" });
          window.location.assign(result.redirect);
        } catch (error) {
          button.disabled = false;
          toast(error.message, error.warning);
        }
      });
    });
    root.querySelectorAll("[data-delete-function]").forEach((button) => {
      button.addEventListener("click", async () => {
        if (!await confirm(`Functie \u201c${button.dataset.title}\u201d verwijderen? Je kunt de functie 30 dagen herstellen via Recent verwijderd.`, "Verwijderen")) return;
        try {
          const result = await post(button.dataset.url, {
            action: "delete",
            query: root.dataset.query,
          });
          updateAfterDelete(button, result);
          toast(result.message);
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
    const requestedFormId = Number(new URLSearchParams(window.location.search).get("form"));
    if (state.forms.some((form) => form.id === requestedFormId)) selectedFormId = requestedFormId;
    let openQuestion = 0;
    let dirty = false;
    const standalone = root.dataset.standalone === "true";
    const typeGroups = fieldTypes(data);
    let locked = data.locked;
    let canToggleLock = data.canToggleLock;
    const isReadOnly = () => locked && !data.isManager;
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
    const isDirty = () => dirty && JSON.stringify(state) !== JSON.stringify(saved);
    function setDirty() {
      dirty = JSON.stringify(state) !== JSON.stringify(saved);
      saveButton.disabled = isReadOnly() || !dirty;
    }
    async function discardIfNeeded() {
      if (!isDirty()) return true;
      if (!await confirm("Er zijn niet-opgeslagen wijzigingen. Wil je die weggooien?", "Weggooien")) return false;
      state = structuredClone(saved);
      dirty = false;
      saveButton.disabled = isReadOnly() || !dirty;
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
        const wrapper = node("label", "managed-field field-wide image-question-field");
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
        drag.draggable = !isReadOnly();
        drag.disabled = isReadOnly();
        drag.setAttribute("aria-label", "Vraag verslepen");
        const title = node("button", `question-title${question.question ? "" : " is-placeholder"}`, question.question || "Nieuwe vraag");
        title.type = "button";
        title.title = question.question || "Nieuwe vraag";
        title.addEventListener("click", () => { openQuestion = openQuestion === index ? -1 : index; renderEditor(); });
        const actionsGroup = node("div", "question-actions");
        const reorder = node("div", "reorder-actions");
        const moveUp = iconButton("up", "Vraag omhoog", "icon-action", () => reorderQuestions(index, index - 1));
        const moveDown = iconButton("down", "Vraag omlaag", "icon-action", () => reorderQuestions(index, index + 1));
        moveUp.disabled = isReadOnly() || index === 0;
        moveDown.disabled = isReadOnly() || index === form.questions.length - 1;
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
        if (!handle || isReadOnly()) { event.preventDefault(); return; }
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
      add.disabled = isReadOnly();
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
        drag.draggable = !isReadOnly();
        drag.disabled = isReadOnly();
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
        moveUp.disabled = isReadOnly() || index === 0;
        moveDown.disabled = isReadOnly() || index === state.forms.length - 1;
        select.disabled = isReadOnly();
        const duplicate = iconButton(
          "copy",
          `Formulier dupliceren: ${form.title || "Naamloos formulier"}`,
          "icon-action",
          () => duplicateForm(form),
        );
        duplicate.disabled = isReadOnly();
        move.append(moveUp, moveDown, duplicate);
        item.append(drag, select, move);
        formList.append(item);
      });
    }

    function formDragStart(event) {
      const handle = event.target.closest(".drag-handle");
      if (!handle || isReadOnly()) { event.preventDefault(); return; }
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

    async function duplicateForm(form) {
      if (isReadOnly() || !await discardIfNeeded()) return;
      try {
        const result = await post(root.dataset.actionUrl, {
          action: "duplicate_form",
          formId: form.id,
        });
        window.location.assign(result.redirect);
      } catch (error) { toast(error.message, error.warning); }
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
        removeForm.disabled = isReadOnly();
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
      if (standalone) {
        const duplicate = iconButton(
          "copy",
          "Formulier dupliceren",
          "icon-action",
          () => duplicateForm(form),
        );
        duplicate.disabled = isReadOnly();
        actions.append(duplicate);
      }
      saveButton.disabled = isReadOnly() || !dirty;
      actions.append(saveButton);
      const fields = node("div", "managed-form-fields");
      if (!standalone) {
        const title = addTextField(fields, "Naam van het formulier", form.title, (value) => {
          form.title = value;
          const selected = formList?.querySelector(`[data-form-id="${form.id}"] .managed-form-select`);
          if (selected) selected.textContent = value || "Naamloos formulier";
          setDirty();
        }, { wide: true, maxLength: 180 });
        title.disabled = isReadOnly();
      }
      editor.append(fields, renderQuestions(form));
      editor.querySelectorAll("input,textarea,select,button").forEach((control) => {
        if (control !== saveButton) control.disabled = isReadOnly() || control.disabled;
      });
      root.querySelectorAll(".drag-handle").forEach((handle) => { handle.draggable = !isReadOnly(); });
      root.querySelector("[data-new-form]")?.toggleAttribute("disabled", isReadOnly());
      renameButton.disabled = isReadOnly() || data.std;
      lockButton.disabled = data.std || !canToggleLock;
      lockButton.querySelector("span").textContent = locked ? "Ontgrendelen" : "Vergrendelen";
      lockButton.setAttribute("aria-pressed", String(locked));
      const lockStatus = root.querySelector("[data-lock-status]");
      lockStatus.hidden = !locked;
      lockStatus.textContent = locked
        ? `Vergrendeld door ${data.lockedByName || "onbekende gebruiker"}`
        : "";
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
        data.lockedByName = result.lockedByName;
        canToggleLock = result.canToggleLock;
        renderEditor();
        toast(result.message);
      } catch (error) { toast(error.message, error.warning); }
    });

    renameButton.addEventListener("click", async () => {
      if (isReadOnly() || !await discardIfNeeded()) return;
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
      button.querySelector("span").textContent = showPreview ? "Terug naar ontwerp" : "Voorbeeld";
      editorPanel.hidden = showPreview;
      root.querySelector("[data-editor-layout]").hidden = showPreview;
      previewPanel.hidden = !showPreview;
      if (showPreview) renderPreview(saved);
    });

    function renderPreview(snapshot) {
      previewContent.replaceChildren();
      const forms = snapshot.forms || [];
      let activeIndex = 0;
      const sections = [];
      const viewer = node("div", "function-viewer");
      viewer.dataset.functionViewer = "";
      const body = node("div", "function-viewer-body");
      const content = node("div", "function-viewer-content");
      body.append(content);
      viewer.append(body);
      previewContent.append(viewer);
      if (forms.length > 1) {
        viewer.classList.add("has-function-navigation");
        const navigation = node("nav", "selection-list function-form-navigation", "Formulieren");
        navigation.dataset.selectionList = "";
        navigation.setAttribute("aria-label", "Formulieren");
        const list = node("ul", "managed-form-list");
        forms.forEach((form, index) => {
          const item = node("li");
          const button = node("button", "form-navigation-item", form.title || "Naamloos formulier");
          button.type = "button";
          button.dataset.viewerNav = `preview-${index}`;
          button.setAttribute("aria-current", String(index === 0));
          item.append(button);
          list.append(item);
        });
        navigation.append(list);
        body.insertBefore(navigation, content);
      }
      forms.forEach((form, formIndex) => {
        const section = node("section", "preview-form");
        section.dataset.viewerPanel = `preview-${formIndex}`;
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
            const label = node("label", "preview-label", question.question || "Vraag");
            if (question.required) {
              label.append(node("span", "required-marker", " *"));
              label.lastChild.setAttribute("aria-hidden", "true");
              label.append(node("span", "visually-hidden", " verplicht"));
            }
            questionWrap.append(label);
            const control = previewControl(question);
            questionWrap.append(control);
            if (question.unit) questionWrap.append(node("span", "preview-unit", question.unit));
          }
          section.append(questionWrap);
        });
        content.append(section);
        sections.push(section);
      });
      document.dispatchEvent(new CustomEvent("function-viewer:initialize"));
    }

    function safeHttpUrl(value) {
      try { const parsed = new URL(value); return ["http:", "https:"].includes(parsed.protocol) ? parsed.href : ""; }
      catch { return ""; }
    }

    function previewControl(question) {
      const typeMap = { text: "text", number: "number", date: "date", dateTime: "datetime-local", imageUpload: "file", fileUpload: "file" };
      if (question.fieldType === "multipleChoice") {
        const select = node("select", "managed-input");
        select.disabled = true;
        select.append(node("option", "", "Maak een keuze"));
        question.options.forEach((answer) => select.append(node("option", "", answer)));
        return select;
      }
      if (question.fieldType === "matrix") {
        const matrix = node("div", "matrix-wrap");
        matrix.dataset.matrix = "";
        matrix.dataset.readonly = "true";
        const payload = {
          definition: question.matrixDefinition || {
            version: 2,
            rows: (question.rows || []).map((label, index) => ({ id: `row-${index}`, label })),
            columns: (question.columns || []).map((label, index) => ({ id: `column-${index}`, label })),
            cells: {},
          },
          values: { version: 2, cells: {} },
          label: question.question || "Matrix",
        };
        const script = document.createElement("script");
        script.type = "application/json";
        script.textContent = JSON.stringify(payload);
        matrix.append(script);
        queueMicrotask(() => document.dispatchEvent(new CustomEvent("function-matrix-preview", { detail: matrix })));
        return matrix;
      }
      if (question.fieldType === "observation") {
        const group = node("div", "function-observation");
        const list = node("div", "observation-list");
        list.append(node("p", "muted", "Nog geen observaties."));
        group.append(list);
        const entry = node("div", "observation-entry");
        const timestamp = node("input", "managed-input");
        timestamp.type = "datetime-local";
        timestamp.setAttribute("aria-label", "Observaties: tijdstip");
        entry.append(timestamp);
        const value = node("input", "managed-input");
        value.placeholder = "Waarde of observatie";
        value.setAttribute("aria-label", "Observaties: waarde of observatie");
        entry.append(value);
        const note = node("input", "managed-input");
        note.placeholder = "Toelichting";
        note.setAttribute("aria-label", "Observaties: toelichting");
        entry.append(note);
        const add = node("button", "outline button", "Observatie toevoegen");
        add.type = "button";
        add.addEventListener("click", () => {
          if (!timestamp.value || !value.value.trim()) {
            value.setCustomValidity("Vul een observatie in voordat je deze toevoegt.");
            value.reportValidity();
            value.addEventListener("input", () => value.setCustomValidity(""), {once: true});
            return;
          }
          list.querySelector(".muted")?.remove();
          const row = node("div", "observation-row");
          const time = node("time");
          time.textContent = timestamp.value;
          const strong = node("strong");
          strong.textContent = value.value.trim();
          const span = node("span");
          span.textContent = note.value.trim();
          row.append(time, strong, span);
          list.append(row);
          timestamp.value = "";
          value.value = "";
          note.value = "";
        });
        entry.append(add);
        group.append(entry);
        return group;
      }
      const input = node(question.fieldType === "text" ? "textarea" : "input", "managed-input");
      if (question.fieldType !== "text") input.type = typeMap[question.fieldType] || "text";
      if (question.fieldType === "text") input.rows = 5;
      input.classList.add("js-tinymce");
      input.disabled = true;
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
      if (!isDirty()) return;
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
