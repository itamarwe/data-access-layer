import { escapeHtml, kindName } from "../lib/html.js";
import { label, markdown, sqlBlock, valueView } from "../lib/format.js";
import { curated, referenceLink, resourceLink, resourceSummary } from "../lib/resources.js";

const section = (title, body, badge = "") => `<section class="resource-section"><h3>${escapeHtml(title)} ${badge}</h3>${body}</section>`;
const references = (ids, resources) => `<ul class="reference-list">${ids.map((id) => `<li>${referenceLink(id, resources)}</li>`).join("")}</ul>`;

export function resourceSheet(item, resources) {
  const p = item.payload;
  const status = p.status || "published";
  const fields = p.curation?.fields || [];
  let body = p.description ? section("Description", markdown(p.description), curated(item, "description")) : "";
  if (p.kind === "doctrine") body += section("Methodology", markdown(p.content), curated(item, "content"));
  if (p.kind === "gold_query") {
    body += section("Question", `<p class="query-question">${escapeHtml(p.question)}</p>`);
    body += `<section class="resource-section"><div class="section-title"><h3>SQL ${curated(item, "sql")}</h3>
      <button type="button" data-copy-sql>Copy SQL</button></div><p class="sql-dialect">${escapeHtml(p.dialect)} · Saved query, not executed</p>${sqlBlock(p.sql)}<span class="copy-status" role="status"></span></section>`;
    if (p.parameters) body += section("Parameters", valueView(p.parameters));
  }
  if (["table", "metric"].includes(p.kind)) {
    body += section("Grain", p.grain ? valueView(p.grain) : '<p class="knowledge-gap">Grain is not defined yet. Confirm what one row represents before aggregating.</p>', curated(item, "grain"));
  }
  if (p.kind === "join") {
    body += section("Join columns", `<div class="relationship-line"><div>${references(p.left, resources)}</div><span aria-label="joins to">→</span><div>${references(p.right, resources)}</div></div>`);
    body += section("Join condition", p.predicate ? sqlBlock(p.predicate) : '<p class="knowledge-gap">No executable condition recorded. Review evidence before using this join.</p>', curated(item, "predicate"));
  }
  if (p.kind === "relation") body += section("Business relation", `<div class="relationship-line"><div>${referenceLink(p.from_id, resources)}</div><span>${escapeHtml(p.name)}</span><div>${referenceLink(p.to_id, resources)}</div></div>`);
  if (p.expression) body += section("Expression", sqlBlock(p.expression), curated(item, "expression"));
  const facts = ["data_type", "nullable", "unit", "join_type", "cardinality", "grain_effect", "owner", "freshness", "recommendation", "restricted", "schema_revision"];
  const defined = facts.filter((key) => p[key] !== undefined);
  if (defined.length) body += section("Details", `<dl class="fact-list">${defined.map((key) => `<div><dt>${escapeHtml(label(key))} ${curated(item, key)}</dt><dd>${valueView(p[key])}</dd></div>`).join("")}</dl>`);
  if (p.required_filters?.length) body += section("Required filters", p.required_filters.map(sqlBlock).join(""), curated(item, "required_filters"));
  if (p.aliases?.length) body += section("Also known as", valueView(p.aliases));
  for (const [key, title] of [["primary_key", "Primary key"], ["identifier_ids", "Identifiers"], ["bindings", "Mapped to data"], ["object_ids", "Applies to"]]) {
    if (p[key]?.length) body += section(title, references(p[key], resources), curated(item, key));
  }
  return `<article class="object-sheet"><header class="resource-heading"><div><span class="resource-kind">${escapeHtml(kindName(item.kind))}</span>
    <h2>${escapeHtml(item.name)}</h2></div><span class="publication-badge ${status === "deprecated" ? "deprecated" : ""}">${escapeHtml(label(status))}</span></header>
    ${item.source ? `<p class="source-name">${escapeHtml(item.source)}</p>` : ""}
    ${item.parent_id ? `<p class="parent-resource">Part of ${referenceLink(item.parent_id, resources)}</p>` : ""}
    ${body}
    <section class="resource-section curation-summary"><h3>Curation on this ${escapeHtml(kindName(item.kind))}</h3>
      ${fields.length ? `<p>Reviewed fields: ${fields.map((field) => escapeHtml(label(field))).join(", ")}.</p>` : "<p>No field-level review is recorded. A description alone does not prove it was reviewed.</p>"}
      <a data-route="curation" href="/curation?target=${encodeURIComponent(item.id)}">Review or propose changes</a>
      ${["table", "column", "join"].includes(item.kind) ? "<p>These definitions belong to this resource. Doctrine holds the broader methodology for using them.</p>" : ""}</section>
    <details class="raw-record"><summary>Technical record</summary><code>${escapeHtml(item.id)}</code><pre>${escapeHtml(JSON.stringify(p, null, 2))}</pre></details></article>`;
}

export function resourceRows(items, resources = new Map()) {
  return items.map((item) => {
    const p = item.payload || {};
    const summary = resourceSummary(item);
    return `<article class="catalog-entry"><div class="entry-heading"><h3>${resourceLink(item)}</h3>${curated(item)}
      ${p.status === "deprecated" ? '<span class="publication-badge deprecated">Deprecated</span>' : ""}</div>
      ${item.source ? `<code>${escapeHtml(item.source)}</code>` : ""}
      <p>${escapeHtml(summary.length > 260 ? summary.slice(0, 257) + "…" : summary)}</p>
      ${p.kind === "relation" && p.from_id && p.to_id ? `<div class="relationship-line">${referenceLink(p.from_id, resources)}<span>${escapeHtml(p.cardinality || "relates to")}</span>${referenceLink(p.to_id, resources)}</div>` : ""}
      ${p.bindings?.length ? `<div class="mapping-preview"><span>Mapped to</span>${p.bindings.slice(0, 5).map((id) => referenceLink(id, resources)).join(", ")}${p.bindings.length > 5 ? ` +${p.bindings.length - 5} more` : ""}</div>` : ""}
      ${p.grain?.description ? `<p class="grain-preview"><strong>Grain</strong> ${escapeHtml(p.grain.description)}</p>` : ""}</article>`;
  }).join("");
}

export function columnRows(items) {
  if (!items.length) return '<p class="quiet-empty">No columns recorded for this table.</p>';
  return `<div class="table-scroll"><table class="data-table"><thead><tr><th scope="col">Column</th><th scope="col">Type</th><th scope="col">Description & curation</th></tr></thead>
    <tbody>${items.map((item) => `<tr><th scope="row">${resourceLink(item)}</th><td><code>${escapeHtml(item.payload.data_type || "Not recorded")}</code>
      ${item.payload.nullable !== undefined ? `<small>${item.payload.nullable ? "Nullable" : "Not nullable"}</small>` : ""}</td>
      <td>${curated(item, "description")}${item.payload.description ? markdown(item.payload.description) : '<span class="quiet-empty">No description recorded.</span>'}
      <a class="small-link" data-route="curation" href="/curation?target=${encodeURIComponent(item.id)}">Review curation</a></td></tr>`).join("")}</tbody></table></div>`;
}

export function connectionsView(connections, resources) {
  const groups = [["relations", "Business relations"], ["joins", "Data joins"], ["mappings", "Ontology mappings"]];
  return groups.map(([key, title]) => section(title, connections[key].length ? connections[key].map((value) => {
    const item = resources.get(value.id);
    const p = item?.payload || value.details || {};
    return `<article class="connection-entry"><h4>${item ? resourceLink(item) : escapeHtml(value.name)} ${item ? curated(item) : ""}</h4>
      <div class="relationship-line">${referenceLink(value.source_id, resources)}<span>${escapeHtml(p.cardinality || (key === "mappings" ? "maps to" : "→"))}</span>${referenceLink(value.target_id, resources)}</div>
      ${p.description ? markdown(p.description) : ""}${p.predicate ? sqlBlock(p.predicate) : ""}
      ${p.join_type ? `<p>${escapeHtml(label(p.join_type))} join</p>` : ""}
      ${p.required_filters?.length ? `<h5>Required filters</h5>${p.required_filters.map(sqlBlock).join("")}` : ""}</article>`;
  }).join("") : `<p class="quiet-empty">No ${title.toLowerCase()} recorded.</p>`)).join("");
}

export function evidenceView(records) {
  return ["physical", "usage", "curation"].map((layer) => {
    const items = records.filter((record) => record.layer === layer);
    return `<div class="rail-section"><h2>${label(layer)} evidence</h2>${items.length ? items.map((record) => `<article>
      <strong>${escapeHtml(label(record.claim_path.replace(/^\//, "").replaceAll("/", " · ")))}</strong>${valueView(record.claim_value)}
      <small>${escapeHtml(kindName(record.source_kind))}</small><small>Collected ${escapeHtml(record.collected_at || "at an unknown time")}</small>
      ${record.strength !== null && record.strength !== undefined ? `<small>Strength ${escapeHtml(record.strength)}</small>` : ""}
      ${record.measurement ? "<small>Measured</small>" : ""}
      ${record.content?.uri ? `<code>${escapeHtml(record.content.uri)}</code>` : ""}</article>`).join("") : "<p>No records shown for this layer.</p>"}</div>`;
  }).join("");
}
