import { api, query } from "../lib/api.js";
import { empty, escapeHtml, failure, kindName, loading } from "../lib/html.js";
import { navigate } from "../lib/router.js";

const kinds = [
  "table", "column", "join", "metric", "entity", "property",
  "relation", "database", "doctrine", "gold_query",
];

export async function renderCatalog(main, rail, fixedKind = null) {
  const parameters = new URLSearchParams(location.search);
  const kind = fixedKind || parameters.get("kind") || "table";
  const objectId = parameters.get("id");
  main.innerHTML = `<header class="view-heading"><p>${fixedKind ? kindName(kind) : "Catalog"}</p>
    <h1>${fixedKind ? title(kind) : "Browse the compiled catalog"}</h1>
    <span>${fixedKind ? subtitle(kind) : "Inspect tables, ontology, and methodology without loading the whole graph."}</span></header>
    ${fixedKind ? "" : selector(kind)}<div id="catalog-output">${loading()}</div>`;
  rail.innerHTML = `<div class="rail-section"><h2>Catalog scope</h2><p>Lists are typed and bounded. Open one resource to inspect its complete compiled payload.</p></div>`;
  main.querySelector("#kind")?.addEventListener("change", (event) => navigate("catalog", { kind: event.target.value }));
  try {
    if (objectId) await showObject(main, rail, kind, objectId, fixedKind);
    else await showList(main, kind, fixedKind);
  } catch (error) {
    main.querySelector("#catalog-output").innerHTML = failure(error);
  }
}

async function showList(main, kind, fixedKind) {
  const data = await api(`/resources/${kind}${query({ limit: 50 })}`);
  const output = main.querySelector("#catalog-output");
  output.innerHTML = data.results.length ? `<section class="ledger-section"><div class="section-title">
    <h2>${title(kind)}</h2><span>${data.results.length} shown</span></div>${data.results.map((item) =>
      `<button class="catalog-row" data-id="${escapeHtml(item.id)}"><span>${kindName(item.kind)}</span>
      <strong>${escapeHtml(item.name)}</strong><code>${escapeHtml(item.source || item.id)}</code></button>`).join("")}</section>`
    : empty(`No ${title(kind).toLowerCase()}`, "Publish or compile resources to make them available here.");
  output.querySelectorAll("[data-id]").forEach((button) => button.addEventListener("click", () => {
    navigate(fixedKind === "gold_query" ? "gold-queries" : fixedKind || "catalog",
      fixedKind ? { id: button.dataset.id } : { kind, id: button.dataset.id });
  }));
}

async function showObject(main, rail, kind, objectId, fixedKind) {
  const item = await api(`/resources/${kind}/${encodeURIComponent(objectId)}`);
  main.querySelector("#catalog-output").innerHTML = `<button class="back-button" id="catalog-back">Back to ${title(kind).toLowerCase()}</button>
    <section class="object-sheet"><div class="object-line"><span>${kindName(item.kind)}</span><h2>${escapeHtml(item.name)}</h2></div>
      <code>${escapeHtml(item.id)}</code>${item.source ? `<p><strong>Source</strong> ${escapeHtml(item.source)}</p>` : ""}
      <pre>${escapeHtml(JSON.stringify(item.payload, null, 2))}</pre></section>`;
  main.querySelector("#catalog-back").addEventListener("click", () => navigate(
    fixedKind === "gold_query" ? "gold-queries" : fixedKind || "catalog",
    fixedKind ? {} : { kind },
  ));
  const [neighbors, evidence, connections] = await Promise.all([
    api(`/graph/neighbors${query({ object_id: item.id, limit: 8 })}`),
    api(`/graph/evidence${query({ object_id: item.id, limit: 8 })}`),
    api(`/graph/connections${query({ object_id: item.id, limit: 8 })}`),
  ]);
  const groups = [["relations", "Business relations"], ["joins", "Data joins"], ["mappings", "Mappings"]];
  rail.innerHTML = groups.map(([key, label]) => `<div class="rail-section"><h2>${label}</h2>
    ${connections[key].map((value) => `<article><strong>${escapeHtml(value.name)}</strong>
      <code>${escapeHtml(value.source_id)} → ${escapeHtml(value.target_id)}</code></article>`).join("") || "<p>None recorded.</p>"}</div>`).join("") +
    `<div class="rail-section"><h2>Resource navigation</h2>${neighbors.neighbors.map((value) =>
    `<article><span>${kindName(value.via)}</span><strong>${escapeHtml(value.object?.name || "Unresolved")}</strong></article>`).join("") || "<p>No connected resources.</p>"}</div>
    <div class="rail-section"><h2>Evidence</h2><p>${evidence.evidence.length} records attached.</p></div>`;
}

function selector(kind) {
  return `<label class="kind-selector" for="kind">Resource type<select id="kind">${kinds.map((item) =>
    `<option value="${item}" ${item === kind ? "selected" : ""}>${title(item)}</option>`).join("")}</select></label>`;
}

function title(kind) {
  if (kind === "entity") return "Entities";
  if (kind === "gold_query") return "Gold queries";
  if (kind === "property") return "Properties";
  return `${kindName(kind).replace(/^./, (letter) => letter.toUpperCase())}s`;
}

function subtitle(kind) {
  return kind === "doctrine" ? "Published methodology for using organizational data."
    : "Curated questions and SQL that establish trusted ways to query the data.";
}
