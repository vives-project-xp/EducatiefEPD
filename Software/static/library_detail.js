(() => {
  const root = document.querySelector("[data-library-detail]");
  if (!root) return;

  const picker = root.querySelector("[data-function-picker]");
  const pickerButton = root.querySelector("[data-open-function-picker]");
  const search = root.querySelector("[data-function-search]");
  const options = [...root.querySelectorAll("[data-function-option]")];
  const addButton = root.querySelector("[data-add-functions]");
  const removeDialog = root.querySelector("[data-remove-function-dialog]");
  let removeForm = null;

  function updatePicker() {
    const query = search.value.trim().toLocaleLowerCase();
    let visible = 0;
    options.forEach((option) => {
      const matches = option.dataset.title.toLocaleLowerCase().includes(query);
      option.hidden = !matches;
      if (matches) visible += 1;
    });
    root.querySelector("[data-no-function-results]").hidden = visible > 0;
    addButton.disabled = !options.some((option) => option.querySelector("input").checked);
  }

  pickerButton?.addEventListener("click", () => {
    picker.showModal();
    search.focus();
    updatePicker();
  });
  search?.addEventListener("input", updatePicker);
  options.forEach((option) => option.addEventListener("change", updatePicker));
  picker?.addEventListener("close", () => pickerButton?.focus());
  picker?.querySelector("form")?.addEventListener("submit", () => {
    addButton.disabled = true;
    addButton.textContent = "Bezig...";
  });

  root.querySelectorAll("[data-remove-function]").forEach((button) => {
    button.addEventListener("click", () => {
      removeForm = button.closest("form");
      removeDialog.querySelector("[data-remove-title]").textContent = button.dataset.title;
      removeDialog.showModal();
    });
  });
  removeDialog?.addEventListener("close", () => {
    if (removeDialog.returnValue === "confirm" && removeForm) removeForm.submit();
    removeForm = null;
  });
})();
