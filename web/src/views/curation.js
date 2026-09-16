import { api, query, resolveResources } from "../lib/api.js";
import { empty, escapeHtml, failure, loading } from "../lib/html.js";
import { matchesProposal, proposalRow } from "./proposal.js";

export async function renderCuration(main, rail, notify, signal) {
  const parameters = new URLSearchParams(location.search);
  const target = parameters.get("target") || "";
  main.innerHTML = `<header class="view-heading"><p>Curation</p><h1>Review the proposed record</h1>
    <span>Review proposals for your catalog files. Decisions check the repository revision.</span></header>
    <div class="curation-toolbar"><button id="new-proposal">Create proposal</button>
      <label>Status<select id="proposal-status"><option value="open">Open</option><option value="published">Published</option>
      <option value="dismissed">Dismissed</option></select></label></div>
    <form class="resource-search" role="search"><label for="view-query">Search proposals</label><div><input id="view-query" type="search" value="${escapeHtml(parameters.get("q") || "")}" placeholder="Reason, target ID, or proposed changes" /><button>Search</button><button type="button" data-clear>Clear</button></div></form>
    ${target ? `<p class="scope-note">Proposals for <code>${escapeHtml(target)}</code> · <a data-route="curation" href="/curation">Show all resources</a></p>` : ""}
    <div id="proposal-form"></div><div id="curation-output" aria-live="polite">${loading()}</div>`;
  rail.innerHTML = `<div class="rail-section"><h2>Decision rule</h2><p>Publish only when the patch improves agent context and its target is clear. Dismiss without changing canonical data.</p></div>`;
  const context = { main, rail, notify, signal, target, request: 0 };
  const status = parameters.get("status");
  if (["open", "published", "dismissed"].includes(status)) main.querySelector("#proposal-status").value = status;
  main.querySelector("#new-proposal").addEventListener("click", () => proposalForm(context));
  main.querySelector("#proposal-status").addEventListener("change", () => load(context));
  main.querySelector(".resource-search").addEventListener("submit", (event) => { event.preventDefault(); load(context); });
  main.querySelector("[data-clear]").addEventListener("click", () => { main.querySelector("#view-query").value = ""; load(context); });
  await load(context);
}

async function load(context) {
  const { main, rail, signal, target } = context;
  if (signal?.aborted) return;
  const request = ++context.request;
  const output = main.querySelector("#curation-output");
  output.innerHTML = loading("Reading proposals");
  try {
    const status = main.querySelector("#proposal-status").value;
    const text = main.querySelector("#view-query").value;
    const url = new URL(location.href);
    url.searchParams.set("status", status); url.searchParams.set("q", text);
    history.replaceState({}, "", url);
    const [proposals, revisions] = await Promise.all([
      api(`/proposals${query({ status })}`, { signal }), api("/revisions", { signal }),
    ]);
    const matching = proposals.filter((item) => matchesProposal(item, text, target));
    const resources = await resolveResources(matching.map((item) => item.target?.object_id), signal);
    if (signal?.aborted || request !== context.request) return;
    main.dataset.revision = revisions.repository;
    rail.innerHTML = `<div class="rail-section"><h2>Current revision</h2><code>${escapeHtml(revisions.repository)}</code>
      <p>A changed revision blocks stale decisions before files are written.</p><p>Publishing updates the resource's files. Run <code>dal build</code> afterwards to see the changes in the catalog.</p><p>Table, column, and join curation belongs to those resources. Doctrine contains broader methodology.</p></div>`;
    const draw = (count) => {
      output.innerHTML = matching.length ? `<section class="ledger-section"><div class="section-title"><h2>${statusLabel(status)}</h2><span>${matching.length} matches</span></div>${matching.slice(0, count).map((item) => proposalRow(item, resources)).join("")}${matching.length > count ? '<button class="load-more">Show more proposals</button>' : ""}</section>`
        : empty(`No matching ${status} proposals`, "Clear the search, choose another status, or create a focused proposal.");
      output.querySelector(".load-more")?.addEventListener("click", () => draw(count + 50));
      bindDecisions(context);
    };
    draw(50);
  } catch (error) {
    if (!signal?.aborted && request === context.request) output.innerHTML = failure(error);
  }
}

function bindDecisions(context) {
  const { main, notify, signal } = context;
  main.querySelectorAll("[data-decision]").forEach((button) => button.addEventListener("click", async () => {
    button.disabled = true;
    try {
      const result = await api(`/proposals/${encodeURIComponent(button.dataset.id)}/${button.dataset.decision}`, {
        method: "POST", headers: { "If-Match": main.dataset.revision }, body: JSON.stringify({}),
      });
      const completed = { publish: "Published", deprecate: "Deprecated", dismiss: "Dismissed" };
      if (signal?.aborted) return;
      notify(completed[button.dataset.decision] + (button.dataset.decision === "dismiss" ? "" : ". Run dal build to refresh the catalog."));
      main.dataset.revision = result.repository_revision;
      await load(context);
    } catch (error) {
      notify(error.message);
      button.disabled = false;
    }
  }));
}

function proposalForm(context) {
  const { main, notify, target, signal } = context;
  const host = main.querySelector("#proposal-form");
  host.innerHTML = `<form class="proposal-form"><div class="section-title"><h2>Create proposal</h2>
    <button type="button" id="close-proposal">Close</button></div>
    <label>Proposal ID<input name="id" required placeholder="urn:dal:proposal:describe-orders" /></label>
    <label>Change type<select name="change"><option value="patch">Edit an existing object</option><option value="object">Create an object from JSON</option></select></label>
    <label>Target object<input name="object_id" required value="${escapeHtml(target)}" placeholder="urn:dal:table:orders" /></label>
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
      if (signal?.aborted) return;
      notify("Proposal created"); host.innerHTML = ""; await load(context);
    } catch (error) { notify(error.message); }
  });
}

function statusLabel(status) {
  return status.replace(/^./, (letter) => letter.toUpperCase()) + " proposals";
}
