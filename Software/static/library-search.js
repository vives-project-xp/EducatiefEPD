(() => {
  const form = document.getElementById("dossier-filter");
  const results = document.getElementById("dossier-results");
  if (!form || !results) return;

  const input = form.elements["dossier_q"];
  let timer;
  let controller;

  async function search() {
    controller?.abort();                       // cancel the previous request
    controller = new AbortController();
    const params = new URLSearchParams(new FormData(form));
    try {
      const response = await fetch(`${location.pathname}?${params}`, {
        signal: controller.signal,
        credentials: "same-origin",
      });
      if (!response.ok) return;
      const doc = new DOMParser().parseFromString(await response.text(), "text/html");
      const fresh = doc.getElementById("dossier-results");
      if (fresh) results.replaceChildren(...fresh.childNodes);
      history.replaceState(null, "", `?${params}`);   // keep the URL shareable
    } catch (error) {
      if (error.name !== "AbortError") form.submit();  // fallback: normal page load
    }
  }

  input.addEventListener("input", () => {
    clearTimeout(timer);
    timer = setTimeout(search, 100);           // debounce: wait 300 ms after typing stops
  });
  form.elements["dossier_education"]?.addEventListener("change", search);
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    clearTimeout(timer);
    search();
  });
})();