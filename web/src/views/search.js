import { api, query } from "../lib/api.js";
import { empty, escapeHtml, failure, kindName, loading } from "../lib/html.js";
import { navigate } from "../lib/router.js";

const examples = [
  "Which table should I use for orders by customer?",
  "How is revenue defined?",
  "What joins customers to orders?",
];

export async function renderSearch(main, rail) {
  const asked = new URLSearchParams(location.search).get("q") || "";
  main.innerHTML = searchShell(asked);
  rail.innerHTML = sideIntro();
  bind(main);
  if (!asked) return;
  const output = main.querySelector("#search-output");
  output.innerHTML = loading("Finding the smallest useful context");
  try {
    const result = await api(`/search${query({ q: asked })}`);
    output.innerHTML = resultView(result);
    if (result.start_with) await renderTrail(result, rail);
  } catch (error) {
    output.innerHTML = failure(error);
  }
}

function bind(main) {
  main.querySelector("form").addEventListener("submit", (event) => {
    event.preventDefault();
    const value = new FormData(event.currentTarget).get("q").trim();
    if (value) navigate("search", { q: value });
  });
  main.querySelectorAll("[data-example]").forEach((button) => button.addEventListener("click", () => {
    navigate("search", { q: button.dataset.example });
  }));
}

function searchShell(asked) {
  return `<header class="view-heading">
    <p>Query context</p><h1>Find the right place to begin</h1>
    <span>One question returns a bounded route through ontology, data, evidence, and method.</span>
  </header>
  <form class="query-bar" role="search">
    <label for="context-query">What does the agent need to know?</label>
    <div><input id="context-query" name="q" value="${escapeHtml(asked)}" autocomplete="off"
      placeholder="Which table should I use for orders by customer?" autofocus />
      <button type="submit">Find context</button></div>
  </form>
  ${asked ? "" : `<div class="examples"><span>Try a real task</span>${examples.map((item) =>
    `<button data-example="${escapeHtml(item)}">${escapeHtml(item)}</button>`).join("")}</div>`}
  <div id="search-output" aria-live="polite"></div>`;
}

function resultView(result) {
  if (!result.results.length && result.also_matched.length) return `<section class="ledger-section">
    <div class="section-title"><h2>Matching context</h2><span>${result.estimated_tokens} estimated tokens</span></div>
    <p>${escapeHtml(result.read_as)}</p>${result.also_matched.map(compactRow).join("")}
    ${result.next_commands.map((item) => `<article><code>${escapeHtml(item.command)}</code><p>${escapeHtml(item.purpose)}</p></article>`).join("")}</section>`;
  if (!result.results.length) return empty(
    result.omissions.total_matches ? "Context exceeds this budget" : "No matching context",
    result.omissions.total_matches ? result.next_commands.map((item) => item.command).join("; ")
      : "Try the nouns used in your warehouse, ontology, or methodology.",
  );
  const reading = result.read_as.replace("start_with", "the recommended starting object");
  return `<section class="read-as"><span>Read as</span><p>${escapeHtml(reading)}</p>
      <small>${result.estimated_tokens} estimated tokens · ${result.omissions.omitted} matches omitted</small></section>
    <section class="start-line"><span>Start with</span><strong>${escapeHtml(result.results[0].object.name)}</strong>
      <code>${escapeHtml(result.start_with.object_id)}</code><p>${escapeHtml(result.start_with.reason)}</p></section>
    <section class="context-trail-section"><div class="section-title"><h2>Context trail</h2><span>Bounded, not exhaustive</span></div>
      <div class="context-trail" id="context-trail"><div class="trail-node start"><small>${kindName(result.results[0].object.kind)}</small>
        <strong>${escapeHtml(result.results[0].object.name)}</strong></div><span class="trail-loading">Reading neighbors…</span></div></section>
    <section class="ledger-section"><div class="section-title"><h2>Best matches</h2><span>${result.results.length} detailed</span></div>
      ${result.results.map(resultRow).join("")}</section>
    ${result.also_matched.length ? `<section class="ledger-section"><div class="section-title"><h2>Also matched</h2>
      <span>Compact by design</span></div>${result.also_matched.map(compactRow).join("")}</section>` : ""}
    ${result.gaps.length ? `<section class="ledger-section gaps"><div class="section-title"><h2>Known gaps</h2></div>
      ${result.gaps.map((gap) => `<p><strong>${escapeHtml(gap.code.replaceAll("_", " "))}</strong>${escapeHtml(gap.message)}</p>`).join("")}</section>` : ""}`;
}

function resultRow(item) {
  const value = item.object;
  return `<article class="result-row"><div class="result-index">${Math.round(item.score * 100)}</div><div>
    <div class="object-line"><span>${kindName(value.kind)}</span><strong>${escapeHtml(value.name)}</strong></div>
    <code>${escapeHtml(value.id)}</code><p>${escapeHtml(value.description || "No curated description yet.")}</p>
    ${item.details ? `<pre>${escapeHtml(JSON.stringify(item.details, null, 2))}</pre>` : ""}
    <div class="signal-line"><span style="--value:${item.signals.lexical}">Lexical</span>
      <span style="--value:${item.signals.embedding}">Semantic</span><span style="--value:${item.signals.evidence}">Evidence</span></div>
  </div></article>`;
}

function compactRow(item) {
  return `<div class="compact-row"><span>${kindName(item.kind)}</span><strong>${escapeHtml(item.name)}</strong>
    <code>${escapeHtml(item.id)}</code><b>${Math.round(item.score * 100)}</b></div>`;
}

async function renderTrail(result, rail) {
  const objectId = result.start_with.object_id;
  const [neighbors, evidence] = await Promise.all([
    api(`/graph/neighbors${query({ object_id: objectId, limit: 3 })}`),
    api(`/graph/evidence${query({ object_id: objectId, limit: 5 })}`),
  ]);
  const trail = document.querySelector("#context-trail");
  trail.innerHTML += neighbors.neighbors.map((item) => `<span class="trail-join" aria-hidden="true"></span>
    <div class="trail-node"><small>${kindName(item.via)}</small>
    <strong>${escapeHtml(item.object?.name || "Unresolved object")}</strong></div>`).join("");
  if (evidence.evidence.length) {
    const record = evidence.evidence[0];
    trail.innerHTML += `<span class="trail-join" aria-hidden="true"></span><div class="trail-node evidence">
      <small>${escapeHtml(record.layer)} evidence</small><strong>${escapeHtml(record.claim_path)}</strong></div>`;
  }
  trail.querySelector(".trail-loading")?.remove();
  rail.innerHTML = `<div class="rail-section"><h2>Evidence</h2>${evidence.evidence.length
    ? evidence.evidence.map((item) => `<article><span class="evidence-layer">${escapeHtml(item.layer)}</span>
      <strong>${escapeHtml(item.claim_path)}</strong><pre>${escapeHtml(JSON.stringify(item.claim_value))}</pre>
      <small>${escapeHtml(item.source_kind)} · ${escapeHtml(item.collected_at || "Collection time unavailable")}</small></article>`).join("")
    : `<p>No evidence is attached to this object yet.</p>`}</div>
    <div class="rail-section"><h2>Next steps</h2>${result.next_commands.map((item) =>
      `<article><code>${escapeHtml(item.command)}</code><small>${escapeHtml(item.purpose)}</small></article>`).join("") || "<p>No next step suggested.</p>"}</div>`;
}

function sideIntro() {
  return `<div class="rail-section"><h2>How to read this</h2><p>The center holds enough context to choose a starting point.
    This rail adds evidence and at most two useful continuations.</p></div>`;
}
