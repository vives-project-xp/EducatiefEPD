(() => {
  document.querySelectorAll("[data-patient-image]").forEach((widget) => {
    const input = widget.querySelector("[data-image-input]");
    const clear = widget.querySelector("[data-image-clear]");
    const preview = widget.querySelector("[data-image-preview]");
    const thumbnail = widget.querySelector("[data-image-thumbnail]");
    const actions = widget.querySelector("[data-image-actions]");
    const choose = widget.querySelector("[data-image-choose]");
    const remove = widget.querySelector("[data-image-remove]");
    const status = widget.querySelector("[data-image-status]");
    const initialUrl = widget.dataset.initialUrl || "";
    let previewUrl = "";

    const releasePreview = () => {
      if (previewUrl) URL.revokeObjectURL(previewUrl);
      previewUrl = "";
    };

    const update = () => {
      releasePreview();
      const file = input.files[0];
      const removing = !clear.disabled;
      const hasImage = Boolean(file || (initialUrl && !removing));
      if (file) {
        previewUrl = URL.createObjectURL(file);
        thumbnail.src = previewUrl;
        status.textContent = `${file.name} wordt bewaard wanneer je de wijzigingen bewaart.`;
      } else if (removing) {
        thumbnail.removeAttribute("src");
        status.textContent = "De afbeelding wordt verwijderd wanneer je de wijzigingen bewaart.";
      } else if (initialUrl) {
        thumbnail.src = initialUrl;
        status.textContent = "Wijzigingen worden pas bewaard met het formulier.";
      } else {
        thumbnail.removeAttribute("src");
        status.textContent = "Nog geen afbeelding gekozen.";
      }
      preview.hidden = !hasImage;
      remove.hidden = !hasImage;
      choose.textContent = initialUrl || file ? "Afbeelding wijzigen" : "Afbeelding toevoegen";
    };

    choose.addEventListener("click", () => input.click());
    input.addEventListener("change", () => {
      if (input.files.length) clear.disabled = true;
      update();
    });
    remove.addEventListener("click", () => {
      input.value = "";
      clear.disabled = !initialUrl;
      update();
      choose.focus();
    });
    window.addEventListener("pagehide", releasePreview);
    input.hidden = true;
    actions.hidden = false;
    update();
  });
})();
