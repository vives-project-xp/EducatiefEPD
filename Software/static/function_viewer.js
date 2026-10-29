(() => {
  function initializeViewer(viewer) {
    if (viewer.dataset.viewerInitialized === "true") return;
    const buttons = [...viewer.querySelectorAll("[data-viewer-nav]")];
    const panels = [...viewer.querySelectorAll("[data-viewer-panel]")];
    if (!buttons.length || !panels.length) return;

    const select = (key, focus = false) => {
      const selected = buttons.find((button) => button.dataset.viewerNav === key) || buttons[0];
      buttons.forEach((button, index) => {
        const active = button === selected;
        button.setAttribute("aria-current", String(active));
        button.tabIndex = active ? 0 : -1;
        if (active && focus) button.focus();
        button.dataset.viewerIndex = String(index);
      });
      panels.forEach((panel) => { panel.hidden = panel.dataset.viewerPanel !== selected.dataset.viewerNav; });
      const form = viewer.closest("form");
      const formInput = form?.querySelector('[name="form"]');
      if (formInput) formInput.value = selected.dataset.viewerNav;
    };

    buttons.forEach((button, index) => {
      button.addEventListener("click", () => select(button.dataset.viewerNav));
      button.addEventListener("keydown", (event) => {
        if (!["ArrowDown", "ArrowUp", "Home", "End"].includes(event.key)) return;
        event.preventDefault();
        const next = event.key === "Home" ? 0
          : event.key === "End" ? buttons.length - 1
            : (index + (event.key === "ArrowDown" ? 1 : -1) + buttons.length) % buttons.length;
        select(buttons[next].dataset.viewerNav, true);
      });
    });
    select(buttons.find((button) => button.getAttribute("aria-current") === "true")?.dataset.viewerNav);
    viewer.dataset.viewerInitialized = "true";
  }

  function initializeAll() {
    document.querySelectorAll("[data-function-viewer]").forEach(initializeViewer);
    document.querySelectorAll("[data-function-nav]").forEach((button) => {
      if (button.dataset.viewerInitialized === "true") return;
      const container = button.closest(".base-dossier-functions");
      const select = (id, focus = false) => {
        const selected = [...container.querySelectorAll("[data-function-nav]")].find((item) => item.dataset.functionNav === id);
        if (!selected) return;
        container.querySelectorAll("[data-function-nav]").forEach((item) => {
          const active = item === selected;
          item.setAttribute("aria-current", String(active));
          item.tabIndex = active ? 0 : -1;
          if (active && focus) item.focus();
        });
        container.querySelectorAll("[data-function-panel]").forEach((panel) => {
          panel.hidden = panel.dataset.functionPanel !== selected.dataset.functionNav;
        });
        const formInput = container.closest("form")?.querySelector('[name="function"]');
        if (formInput) formInput.value = selected.dataset.functionNav;
      };
      const buttons = [...container.querySelectorAll("[data-function-nav]")];
      const index = buttons.indexOf(button);
      button.addEventListener("click", () => select(button.dataset.functionNav));
      button.addEventListener("keydown", (event) => {
        if (!["ArrowDown", "ArrowUp", "Home", "End"].includes(event.key)) return;
        event.preventDefault();
        const next = event.key === "Home" ? 0
          : event.key === "End" ? buttons.length - 1
            : (index + (event.key === "ArrowDown" ? 1 : -1) + buttons.length) % buttons.length;
        select(buttons[next].dataset.functionNav, true);
      });
      button.dataset.viewerInitialized = "true";
    });
  }

  document.addEventListener("DOMContentLoaded", initializeAll);
  document.addEventListener("function-viewer:initialize", initializeAll);
})();
