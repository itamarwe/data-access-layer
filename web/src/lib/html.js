export function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

export function kindName(value) {
  return String(value || "context").replaceAll("_", " ");
}

export function empty(title, guidance) {
  return `<div class="empty-state"><strong>${escapeHtml(title)}</strong><p>${escapeHtml(guidance)}</p></div>`;
}

export function failure(error) {
  return `<div class="fault" role="alert"><strong>Could not load this view</strong><p>${escapeHtml(error.message)}</p></div>`;
}

export function loading(label = "Reading the ledger") {
  return `<div class="loading" role="status"><span></span>${escapeHtml(label)}…</div>`;
}
