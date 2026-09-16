import { api, query, resolveResources } from "../lib/api.js";
import { empty, escapeHtml, failure, loading } from "../lib/html.js";
import { dataKinds, ontologyKinds, kindTitle, referenceIds } from "../lib/resources.js";
import { navigate } from "../lib/router.js";
import { resourceSheet, resourceRows, columnRows, connectionsView, evidenceView } from "./resource.js";

const pageSize = 50;

export async function renderCatalog(main, rail, fixedKind = null, signal) {
  const parameters = new URLSearchParams(location.search);
  const ontology = fixedKind === "ontology";
  const kinds = ontology ? ontologyKinds : fixedKind ? [fixedKind] : dataKinds;
  const kind = kinds.includes(parameters.get("kind")) ? parameters.get("kind") : kinds[0];
  const route = ontology ? "ontology" : fixedKind === "gold_query" ? "gold-queries" : fixedKind || "catalog";
  const state = { kind, q: parameters.get("q") || "", offset: Math.max(0, parseInt(parameters.get("offset"), 10) || 0), include_deprecated: parameters.get("include_deprecated") === "true" };
  const heading = ontology ? "The business meaning of your data" : fixedKind ? kindTitle(kind) : "Your data, explained";
  const subtitle = ontology ? "Entities, properties, relations, and metrics—with links to the tables, columns, and joins that implement them."
    : kind === "doctrine" ? "Published methodology for using organizational data. Table, column, and join definitions live on those resources."
    : kind === "gold_query" ? "Curated questions, reusable SQL, and the context needed to apply them."
    : "Descriptions, grain, columns, joins, and curation together on each resource.";
  main.innerHTML = `<header class="view-heading ${parameters.get("id") ? "compact-heading" : ""}"><p>${ontology ? "Ontology" : fixedKind ? kindTitle(kind) : "Catalog"}</p><h1>${heading}</h1><span>${subtitle}</span></header>
    ${kinds.length > 1 ? `<nav class="resource-tabs" aria-label="Resource types">${kinds.map((value) => `<a data-route="${route}" href="/${route}?kind=${value}" ${value === kind ? 'aria-current="page"' : ""}>${kindTitle(value)}</a>`).join("")}</nav>` : ""}
    <form class="resource-search" role="search"><label for="view-query">Search ${kindTitle(kind).toLowerCase()}</label><div><input id="view-query" name="q" type="search" value="${escapeHtml(state.q)}" placeholder="Names, descriptions, and content" /><button>Search</button><button type="button" data-clear>Clear</button></div>
    <label class="checkbox-label"><input type="checkbox" name="deprecated" ${state.include_deprecated ? "checked" : ""} /> Include deprecated</label></form><div id="catalog-output" aria-live="polite">${loading()}</div>`;
  rail.innerHTML = '<div class="rail-section"><h2>Published context</h2><p>Resource definitions stay with their table, column, or join. Doctrine is the methodology above them.</p><p>After publishing changes, run <code>dal build</code> to refresh this compiled catalog.</p></div>';
  const form = main.querySelector("form");
  const search = () => navigate(route, { ...state, offset: 0, q: form.elements.q.value.trim(), include_deprecated: form.elements.deprecated.checked });
  form.addEventListener("submit", (event) => { event.preventDefault(); search(); });
  form.elements.deprecated.addEventListener("change", search);
  form.querySelector("[data-clear]").addEventListener("click", () => { form.elements.q.value = ""; search(); });
  const output = main.querySelector("#catalog-output");
  try {
    if (parameters.get("id")) await showObject(output, rail, kind, parameters.get("id"), route, state, signal);
    else await showList(output, kind, route, state, signal);
  } catch (error) { if (!signal?.aborted) output.innerHTML = failure(error); }
}

async function showList(output, kind, route, state, signal) {
  let items, more = false, note;
  if (state.q) {
    const data = await api(`/search${query({ q: state.q, kind, include_deprecated: state.include_deprecated, token_budget: 8000 })}`, { signal });
    const ids = [...data.results.map((result) => result.object.id), ...data.also_matched.map((item) => item.id)];
    items = [...(await resolveResources(ids, signal)).values()];
    note = `${items.length} ranked matches shown. Search returns a bounded selection; narrow your search if needed.`;
  } else {
    const data = await api(`/resources/${kind}${query({ limit: pageSize + 1, offset: state.offset, include_deprecated: state.include_deprecated })}`, { signal });
    items = data.results.slice(0, pageSize); more = data.results.length > pageSize;
    note = items.length ? `${state.offset + 1}–${state.offset + items.length} shown` : "0 shown";
  }
  const resources = await resolveResources(items.flatMap(referenceIds), signal);
  if (signal?.aborted) return;
  output.innerHTML = `<section class="ledger-section"><div class="section-title"><h2>${kindTitle(kind)}</h2></div><p class="result-count">${note}</p>${items.length ? resourceRows(items, resources) : empty("No matching resources", state.q ? "Try another name or description, or clear the search." : "Publish and build resources to make them available here.")}</section>${state.q ? "" : pager(state.offset, more)}`;
  output.querySelectorAll("[data-offset]").forEach((button) => button.addEventListener("click", () => navigate(route, { ...state, offset: button.dataset.offset })));
  output.querySelectorAll(`a[data-route="${route}"]`).forEach((link) => {
    const url = new URL(link.href);
    if (url.searchParams.get("kind") !== kind) return;
    Object.entries(state).forEach(([key, value]) => url.searchParams.set(key, value));
    link.href = url.pathname + url.search;
  });
}

async function showObject(output, rail, kind, id, route, state, signal) {
  const item = await api(`/resources/${kind}/${encodeURIComponent(id)}`, { signal });
  const [connections, evidence, doctrines, goldQueries] = await Promise.all([
    api(`/graph/connections${query({ object_id: id, limit: 100 })}`, { signal }),
    api(`/graph/evidence${query({ object_id: id, limit: 100 })}`, { signal }),
    api(`/resources/doctrine${query({ referenced_object_id: id, limit: 11 })}`, { signal }),
    api(`/resources/gold_query${query({ referenced_object_id: id, limit: 11 })}`, { signal }),
  ]);
  const edges = [...connections.relations, ...connections.joins, ...connections.mappings];
  const resources = await resolveResources([id, ...referenceIds(item), ...edges.flatMap((edge) => [edge.id, edge.source_id, edge.target_id, ...referenceIds(edge.details || {})])], signal);
  const parents = await resolveResources([...resources.values()].map((value) => value.parent_id), signal);
  parents.forEach((value, key) => resources.set(key, value));
  if (signal?.aborted) return;
  output.innerHTML = `<button class="back-button" data-back>Back to ${kindTitle(kind).toLowerCase()}</button>${resourceSheet(item, resources)}<div data-children></div>${edges.length || !["doctrine", "gold_query"].includes(kind) ? connectionsView(connections, resources) : ""}
    ${edges.length >= 100 ? '<p class="quiet-empty">Showing up to 100 connections. Open connected resources to explore further.</p>' : ""}${related("Related methodology", doctrines.results)}${related("Related gold queries", goldQueries.results)}`;
  output.querySelector("[data-back]").addEventListener("click", () => navigate(route, state));
  output.querySelector("[data-copy-sql]")?.addEventListener("click", async () => {
    const status = output.querySelector(".copy-status");
    try { await navigator.clipboard.writeText(item.payload.sql); status.textContent = "SQL copied"; }
    catch { status.textContent = "Clipboard unavailable. Select the SQL to copy it."; }
  });
  rail.innerHTML = evidenceView(evidence.evidence) + (evidence.evidence.length === 100 ? '<p class="quiet-empty">Showing up to 100 evidence records.</p>' : "");
  const childKind = { table: "column", entity: "property", database: "table" }[kind];
  if (childKind) await children(output.querySelector("[data-children]"), childKind, id, 0, signal);
}

async function children(host, kind, parent, offset, signal, text = "") {
  host.innerHTML = loading(`Reading ${kindTitle(kind).toLowerCase()}`);
  try {
    let data;
    if (text) {
      const matches = await api(`/search${query({ q: text, kind, parent_id: parent, token_budget: 8000 })}`, { signal });
      data = { results: [...(await resolveResources([...matches.results.map((value) => value.object.id), ...matches.also_matched.map((value) => value.id)], signal)).values()] };
    } else data = await api(`/resources/${kind}${query({ parent_id: parent, limit: pageSize + 1, offset })}`, { signal });
    const items = data.results.slice(0, pageSize);
    const resources = await resolveResources(items.flatMap(referenceIds), signal);
    if (signal?.aborted) return;
    host.innerHTML = `<section class="resource-section"><h3>${kindTitle(kind)}</h3>${kind === "column" ? `<form class="resource-search" role="search"><label for="column-query">Search this table's columns</label><div><input id="column-query" name="q" type="search" value="${escapeHtml(text)}" /><button>Search columns</button></div></form>` : ""}${text ? '<p class="quiet-empty">Ranked matches within this table. Clear the search to browse all columns.</p>' : ""}${kind === "column" ? columnRows(items) : resourceRows(items, resources) || '<p class="quiet-empty">None recorded.</p>'}${text ? "" : pager(offset, data.results.length > pageSize)}</section>`;
    host.querySelector("form")?.addEventListener("submit", (event) => { event.preventDefault(); children(host, kind, parent, 0, signal, event.currentTarget.elements.q.value.trim()); });
    host.querySelectorAll("[data-offset]").forEach((button) => button.addEventListener("click", () => children(host, kind, parent, Number(button.dataset.offset), signal)));
  } catch (error) { if (!signal?.aborted) host.innerHTML = failure(error); }
}

function pager(offset, more) {
  if (!offset && !more) return "";
  return `<nav class="pagination" aria-label="Results pages"><button data-offset="${Math.max(0, offset - pageSize)}" ${offset ? "" : "disabled"}>Previous</button><span>Page ${Math.floor(offset / pageSize) + 1}</span><button data-offset="${offset + pageSize}" ${more ? "" : "disabled"}>Next</button></nav>`;
}

function related(title, items) {
  return items.length ? `<section class="resource-section"><h3>${title}</h3>${resourceRows(items.slice(0, 10))}${items.length > 10 ? '<p class="quiet-empty">Showing 10 related resources. Search the dedicated screen for more.</p>' : ""}</section>` : "";
}
