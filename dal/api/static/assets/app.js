import { api, setAccessToken } from "./lib/api.js";
import { bindRoutes, currentRoute, navigate } from "./lib/router.js";
import { renderCatalog } from "./views/catalog.js";
import { renderCuration } from "./views/curation.js";
import { renderHealth } from "./views/health.js";
import { renderSearch } from "./views/search.js";

const workspace = document.querySelector("#workspace");
const evidenceRail = document.querySelector("#evidence-rail");
const revision = document.querySelector("#revision");
const toast = document.querySelector("#toast");

const views = {
  search: () => renderSearch(workspace, evidenceRail),
  catalog: () => renderCatalog(workspace, evidenceRail),
  curation: () => renderCuration(workspace, evidenceRail, notify),
  doctrine: () => renderCatalog(workspace, evidenceRail, "doctrine"),
  "gold-queries": () => renderCatalog(workspace, evidenceRail, "gold_query"),
  health: () => renderHealth(workspace, evidenceRail),
};

function render() {
  const route = currentRoute();
  document.querySelectorAll("[data-route]").forEach((link) => {
    const active = link.dataset.route === route;
    link.toggleAttribute("aria-current", active);
  });
  views[route]();
}

function notify(message) {
  toast.textContent = message;
  toast.classList.add("visible");
  window.setTimeout(() => toast.classList.remove("visible"), 2600);
}

async function readRevision() {
  try {
    const value = await api("/revisions");
    revision.textContent = `Repository ${value.repository.slice(7, 15)} · Bundle ${value.compiled?.slice(0, 8) || "none"}`;
  } catch (error) {
    revision.textContent = "Revision unavailable";
  }
}

document.querySelector("#access-token").addEventListener("click", () => {
  const value = window.prompt("Bearer token for this browser session. Leave blank to clear it.", "");
  if (value === null) return;
  setAccessToken(value);
  notify(value.trim() ? "Access token set" : "Access token cleared");
  readRevision();
  render();
});

document.addEventListener("keydown", (event) => {
  if (event.key === "/" && !["INPUT", "TEXTAREA"].includes(document.activeElement.tagName)) {
    event.preventDefault();
    if (currentRoute() !== "search") navigate("search");
    window.setTimeout(() => document.querySelector("#context-query")?.focus(), 0);
  }
});

bindRoutes();
window.addEventListener("popstate", render);
window.addEventListener("dal:navigate", render);
readRevision();
render();
