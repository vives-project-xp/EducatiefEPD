document.addEventListener("DOMContentLoaded", () => {
  const options = [...document.querySelectorAll("input[data-status-filter]")];
  const cards = [...document.querySelectorAll(".case-card[data-case-status]")];
  const empty = document.querySelector(".case-filter-empty");
  const selectedOrder = [];

  if (!options.length || !empty) return;

  const update = () => {
    const statuses = selectedOrder.filter((status) =>
      options.some((option) => option.checked && option.value === status)
    );
    let visible = 0;

    cards.forEach((card) => {
      card.hidden = false;
      card.style.order = statuses.length
        ? statuses.indexOf(card.dataset.caseStatus)
        : "";
    });

    cards.forEach((card) => {
      const matches = statuses.length === 0 || statuses.includes(card.dataset.caseStatus);
      card.hidden = !matches;
      if (matches) visible += 1;
    });

    empty.hidden = visible !== 0;
  };

  options.forEach((option) => option.addEventListener("change", () => {
    if (option.checked) {
      selectedOrder.push(option.value);
    } else {
      const index = selectedOrder.indexOf(option.value);
      if (index !== -1) selectedOrder.splice(index, 1);
    }
    update();
  }));
  update();
});
