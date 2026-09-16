import { escapeHtml } from "../lib/html.js";
import { label, markdown, sqlBlock, valueView } from "../lib/format.js";
import { referenceLink } from "../lib/resources.js";

export function matchesProposal(item, text, target = "") {
  if (target && item.target?.object_id !== target) return false;
  const words = text.toLocaleLowerCase().trim().split(/\s+/).filter(Boolean);
  const content = JSON.stringify(item).toLocaleLowerCase();
  return words.every((word) => content.includes(word));
}

function fieldValue(field, value) {
  if (["sql", "predicate", "expression"].includes(field) && typeof value === "string") return sqlBlock(value);
  if (["description", "content", "reason"].includes(field) && typeof value === "string") return markdown(value);
  return valueView(value);
}

export function proposalRow(item, resources = new Map()) {
  const decision = (item.patch || []).some((change) => change.path === "/status" && change.value === "deprecated") ? "deprecate" : "publish";
  const changes = item.object ? `<h4>New ${escapeHtml(item.object.kind)}</h4><dl class="fact-list">${Object.entries(item.object).filter(([key]) => !["id", "kind"].includes(key)).map(([field, value]) => `<div><dt>${escapeHtml(label(field))}</dt><dd>${fieldValue(field, value)}</dd></div>`).join("")}</dl>`
    : (item.patch || []).map((change) => {
      const field = change.path.slice(1).replaceAll("~1", "/").replaceAll("~0", "~");
      const before = item.before?.[field];
      return `<section class="field-change"><h4>${escapeHtml(label(field))}</h4><div class="change-comparison"><div><h5>Before</h5>${before ? before.present ? fieldValue(field, before.value) : '<p class="quiet-empty">Not set</p>' : '<p class="quiet-empty">Not recorded</p>'}</div><div><h5>${change.op === "remove" ? "Remove" : "After"}</h5>${change.op === "remove" ? '<p class="quiet-empty">Field removed</p>' : fieldValue(field, change.value)}</div></div></section>`;
    }).join("");
  return `<article class="proposal-row"><div><span class="status-dot ${escapeHtml(item.status)}">${escapeHtml(label(item.status))}</span><h3>${escapeHtml(item.reason || item.id)}</h3>
    <p class="proposal-target">${referenceLink(item.target?.object_id, resources)}</p>${changes}
    ${item.decision ? `<p class="quiet-empty">${item.decision.decided_by ? `Decision by ${escapeHtml(item.decision.decided_by)}. ` : ""}${escapeHtml(item.decision.reason || "")}</p>` : ""}
    <details class="raw-record"><summary>Technical record</summary><pre>${escapeHtml(JSON.stringify(item, null, 2))}</pre></details></div>
    ${item.status === "open" ? `<div class="decision-actions"><button data-decision="${decision}" data-id="${escapeHtml(item.id)}">${decision === "deprecate" ? "Deprecate" : "Publish"}</button><button class="danger-text" data-decision="dismiss" data-id="${escapeHtml(item.id)}">Dismiss</button></div>` : ""}</article>`;
}
