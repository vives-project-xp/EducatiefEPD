document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll(".function-form-navigation").forEach((navigation) => {
    const card = navigation.closest(".function-snapshot-card");
    const buttons = [...navigation.querySelectorAll("[data-function-form-nav]")];
    const select = (key) => {
      buttons.forEach((button, index) => {
        const active = button.dataset.functionFormNav === key;
        button.classList.toggle("is-active", active);
        button.setAttribute("aria-pressed", String(active));
        button.tabIndex = active ? 0 : -1;
        if (active) button.dataset.index = String(index);
      });
      card.querySelectorAll("[data-function-form]").forEach((form) => {
        form.hidden = form.dataset.functionForm !== key;
      });
    };
    buttons.forEach((button, index) => {
      button.addEventListener("click", () => select(button.dataset.functionFormNav));
      button.addEventListener("keydown", (event) => {
        if (!["ArrowDown", "ArrowUp"].includes(event.key)) return;
        event.preventDefault();
        const next = (index + (event.key === "ArrowDown" ? 1 : -1) + buttons.length) % buttons.length;
        buttons[next].focus();
        select(buttons[next].dataset.functionFormNav);
      });
    });
    const first = buttons.find((button) => button.classList.contains("is-active")) || buttons[0];
    if (first) select(first.dataset.functionFormNav);
  });
});
