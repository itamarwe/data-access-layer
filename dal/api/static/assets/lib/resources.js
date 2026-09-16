import { escapeHtml, kindName } from "./html.js";

export const ontologyKinds = ["entity", "property", "relation", "metric"];
export const dataKinds = ["table", "column", "join", "database"];

export function kindTitle(kind) {
  return { entity: "Entities", property: "Properties", doctrine: "Doctrine", gold_query: "Gold queries" }[kind]
    || `${kindName(kind).replace(/^./, (letter) => letter.toUpperCase())}s`;
}

export function resourceRoute(kind) {
  return ontologyKinds.includes(kind) ? "ontology" : kind === "doctrine" ? "doctrine" : kind === "gold_query" ? "gold-queries" : "catalog";
}

export function resourceLink(item, text = item.name) {
  const route = resourceRoute(item.kind);
  const parameters = new URLSearchParams({ kind: item.kind, id: item.id });
  return `<a class="resource-link" data-route="${route}" href="/${route}?${escapeHtml(parameters)}">${escapeHtml(text)}</a>`;
}

export function referenceLink(id, resources) {
  const item = resources.get(id);
  if (!item) return `<code class="unresolved" title="Resource details unavailable">${escapeHtml(id)}</code>`;
  const parent = resources.get(item.parent_id);
  return resourceLink(item, parent ? `${parent.name}.${item.name}` : item.name);
}

export function referenceIds(item) {
  const p = item.payload || item;
  return [p.parent_id, p.from_id, p.to_id, ...["bindings", "object_ids", "identifier_ids", "primary_key", "left", "right"].flatMap((field) => Array.isArray(p[field]) ? p[field] : [])].filter(Boolean);
}

export function curated(item, field) {
  const fields = (item.payload || item).curation?.fields || [];
  return (field ? fields.includes(field) : fields.length > 0) ? '<span class="curated-badge">Curated</span>' : "";
}

export function resourceSummary(item) {
  const p = item.payload || {};
  const prose = p.question || p.description || p.content;
  if (!prose) return "No description recorded.";
  const paragraph = prose.split(/\n\s*\n/).find((part) => !/^\s*(#|```|\|)/.test(part)) || prose;
  return paragraph.replace(/^\s*#{1,6}\s+/gm, "").replace(/\[([^\]]+)\]\([^)]*\)/g, "$1")
    .replace(/[`*]/g, "").replace(/\s+/g, " ").trim();
}
