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
  search: (signal) => renderSearch(workspace, evidenceRail, signal),
  catalog: (signal) => renderCatalog(workspace, evidenceRail, null, signal),
  ontology: (signal) => renderCatalog(workspace, evidenceRail, "ontology", signal),
  curation: (signal) => renderCuration(workspace, evidenceRail, notify, signal),
  doctrine: (signal) => renderCatalog(workspace, evidenceRail, "doctrine", signal),
  "gold-queries": (signal) => renderCatalog(workspace, evidenceRail, "gold_query", signal),
  health: (signal) => renderHealth(workspace, evidenceRail, signal),
};

let activeView;
function render() {
  activeView?.abort();
  activeView = new AbortController();
  const route = currentRoute();
  document.querySelectorAll("[data-route]").forEach((link) => {
    const active = link.dataset.route === route;
    link.toggleAttribute("aria-current", active);
  });
  views[route](activeView.signal);
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
  if (event.key === "/" && !["INPUT", "TEXTAREA", "SELECT"].includes(document.activeElement.tagName) && !document.activeElement.isContentEditable) {
    event.preventDefault();
    const scopedSearch = document.querySelector("#view-query");
    if (scopedSearch) { scopedSearch.focus(); return; }
    if (currentRoute() !== "search") navigate("search");
    window.setTimeout(() => document.querySelector("#context-query")?.focus(), 0);
  }
});

bindRoutes();
window.addEventListener("popstate", render);
window.addEventListener("dal:navigate", render);
readRevision();
render();
