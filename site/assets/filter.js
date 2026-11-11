"use strict";

document.querySelectorAll("[data-filter]").forEach((input) => {
  input.addEventListener("input", () => {
    const query = input.value.trim().toLocaleLowerCase();
    document.querySelectorAll(input.dataset.filter).forEach((card) => {
      card.hidden = !card.textContent.toLocaleLowerCase().includes(query);
    });
  });
});
