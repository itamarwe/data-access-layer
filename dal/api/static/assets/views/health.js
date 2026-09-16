import { api } from "../lib/api.js";
import { escapeHtml, failure, loading } from "../lib/html.js";

export async function renderHealth(main, rail, signal) {
  main.innerHTML = `<header class="view-heading"><p>Health</p><h1>Know what needs attention</h1>
    <span>Failures block trust. Gaps identify context that can be improved without pretending the build failed.</span></header>
    <div id="health-output">${loading("Inspecting authored files and bundle")}</div>`;
  rail.innerHTML = `<div class="rail-section"><h2>Recovery</h2><p>Every issue includes one concrete command that moves the repository toward health.</p></div>`;
  try {
    const result = await api("/health", { signal });
    if (signal?.aborted) return;
    main.querySelector("#health-output").innerHTML = `<div class="health-summary ${result.healthy ? "healthy" : "unhealthy"}">
      <span>${result.healthy ? "Operational" : "Attention required"}</span><strong>${result.failures.length}</strong><small>failures</small>
      <strong>${result.gaps.length}</strong><small>knowledge gaps</small></div>
      <section class="ledger-section"><div class="section-title"><h2>Checks performed</h2></div>
        ${(result.checks || []).map((check) => `<article class="health-row"><strong>${escapeHtml(check.name)}</strong>
          <span>${check.performed ? "Checked" : "Not checked"}</span><p>${escapeHtml(check.reason || "")}</p></article>`).join("")}</section>
      ${issues("Failures", result.failures)}${issues("Knowledge gaps", result.gaps)}`;
  } catch (error) {
    if (!signal?.aborted) main.querySelector("#health-output").innerHTML = failure(error);
  }
}

function issues(title, values) {
  return `<section class="ledger-section"><div class="section-title"><h2>${title}</h2><span>${values.length}</span></div>
    ${values.length ? values.map((item) => `<article class="health-row"><span>${escapeHtml(item.code.replaceAll("_", " "))}</span>
      <div><strong>${escapeHtml(item.message)}</strong><code>${escapeHtml(item.location)}</code></div>
      <code class="recovery">${escapeHtml(item.recovery_command)}</code></article>`).join("")
    : `<p class="quiet-empty">Nothing to resolve.</p>`}</section>`;
}
