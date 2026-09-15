import { api, query } from "../lib/api.js";
import { empty, escapeHtml, failure, loading } from "../lib/html.js";

export async function renderCuration(main, rail, notify) {
  main.innerHTML = `<header class="view-heading"><p>Curation</p><h1>Review the proposed record</h1>
    <span>Review proposals for your catalog files. Decisions check the repository revision.</span></header>
    <div class="curation-toolbar"><button id="new-proposal">Create proposal</button>
      <label>Status<select id="proposal-status"><option value="open">Open</option><option value="published">Published</option>
      <option value="dismissed">Dismissed</option></select></label></div>
    <div id="proposal-form"></div><div id="curation-output">${loading()}</div>`;
  rail.innerHTML = `<div class="rail-section"><h2>Decision rule</h2><p>Publish only when the patch improves agent context and its target is clear. Dismiss without changing canonical data.</p></div>`;
  main.querySelector("#new-proposal").addEventListener("click", () => proposalForm(main, notify));
  main.querySelector("#proposal-status").addEventListener("change", () => load(main, rail, notify));
  await load(main, rail, notify);
}

async function load(main, rail, notify) {
  const output = main.querySelector("#curation-output");
  output.innerHTML = loading("Reading proposals");
  try {
    const status = main.querySelector("#proposal-status").value;
    const [proposals, revisions] = await Promise.all([
      api(`/proposals${query({ status })}`), api("/revisions"),
    ]);
    main.dataset.revision = revisions.repository;
    rail.innerHTML = `<div class="rail-section"><h2>Current revision</h2><code>${escapeHtml(revisions.repository)}</code>
      <p>A changed revision blocks stale decisions before files are written.</p></div>`;
    output.innerHTML = proposals.length ? `<section class="ledger-section"><div class="section-title"><h2>${statusLabel(status)}</h2>
      <span>${proposals.length}</span></div>${proposals.map(proposalRow).join("")}</section>`
      : empty(`No ${status} proposals`, status === "open" ? "Create a focused patch when catalog context needs correction." : "Decided proposals will remain visible here.");
    bindDecisions(main, rail, notify);
  } catch (error) {
    output.innerHTML = failure(error);
  }
}

function proposalRow(item) {
  const target = item.target || {};
  const decision = (item.patch || []).some((change) => change.path === "/status" && change.value === "deprecated")
    ? "deprecate" : "publish";
  return `<article class="proposal-row"><div><span class="status-dot ${item.status}">${escapeHtml(item.status)}</span>
    <strong>${escapeHtml(item.reason || item.id)}</strong><code>${escapeHtml(target.object_id || "")}</code>
    <pre>${escapeHtml(JSON.stringify(item.object || item.patch || [], null, 2))}</pre></div>
    ${item.status === "open" ? `<div class="decision-actions"><button data-decision="${decision}" data-id="${escapeHtml(item.id)}">${decision === "deprecate" ? "Deprecate" : "Publish"}</button>
      <button class="danger-text" data-decision="dismiss" data-id="${escapeHtml(item.id)}">Dismiss</button></div>` : ""}</article>`;
}

function bindDecisions(main, rail, notify) {
  main.querySelectorAll("[data-decision]").forEach((button) => button.addEventListener("click", async () => {
    button.disabled = true;
    try {
      const result = await api(`/proposals/${encodeURIComponent(button.dataset.id)}/${button.dataset.decision}`, {
        method: "POST", headers: { "If-Match": main.dataset.revision }, body: JSON.stringify({}),
      });
      const completed = { publish: "Published", deprecate: "Deprecated", dismiss: "Dismissed" };
      notify(completed[button.dataset.decision]);
      main.dataset.revision = result.repository_revision;
      await load(main, rail, notify);
    } catch (error) {
      notify(error.message);
      button.disabled = false;
    }
  }));
}

function proposalForm(main, notify) {
  const host = main.querySelector("#proposal-form");
  host.innerHTML = `<form class="proposal-form"><div class="section-title"><h2>Create proposal</h2>
    <button type="button" id="close-proposal">Close</button></div>
    <label>Proposal ID<input name="id" required placeholder="urn:dal:proposal:describe-orders" /></label>
    <label>Change type<select name="change"><option value="patch">Edit an existing object</option><option value="object">Create an object from JSON</option></select></label>
    <label>Target object<input name="object_id" required placeholder="urn:dal:table:orders" /></label>
    <label>Property path (existing objects)<input name="path" placeholder="/description" /></label>
    <label>Value<textarea name="value" required placeholder="Curated description"></textarea></label>
    <label>Value format<select name="format"><option value="text">Text</option><option value="json">JSON (lists, numbers, or structured values)</option></select></label>
    <label>Reason<input name="reason" required placeholder="Why this helps an agent query correctly" /></label>
    <button type="submit">Create proposal</button></form>`;
  host.querySelector("#close-proposal").addEventListener("click", () => { host.innerHTML = ""; });
  host.querySelector("form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const values = Object.fromEntries(new FormData(event.currentTarget));
    try {
      const value = values.format === "json" || values.change === "object" ? JSON.parse(values.value) : values.value;
      const proposal = { id: values.id, status: "open",
        target: { object_id: values.object_id }, base_revision: main.dataset.revision,
        ...(values.change === "object" ? { object: value } : { patch: [{ op: "add", path: values.path, value }] }),
        reason: values.reason };
      await api("/proposals", { method: "POST", headers: { "If-Match": main.dataset.revision },
        body: JSON.stringify({ proposal }) });
      notify("Proposal created"); host.innerHTML = ""; await load(main, document.querySelector("#evidence-rail"), notify);
    } catch (error) { notify(error.message); }
  });
}

function statusLabel(status) {
  return status.replace(/^./, (letter) => letter.toUpperCase()) + " proposals";
}
