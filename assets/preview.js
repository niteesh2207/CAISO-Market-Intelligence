"use strict";

const button = document.getElementById("preview-action");
const status = document.getElementById("preview-status");

button.addEventListener("click", () => {
  status.hidden = false;
  status.textContent =
    "Static preview confirmed. No market-data request was made. Run the FastAPI service server-side to exercise configured research connectors.";
  button.textContent = "Preview status shown";
});
