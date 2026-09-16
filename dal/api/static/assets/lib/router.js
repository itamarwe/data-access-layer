const known = new Set(["search", "catalog", "ontology", "curation", "doctrine", "gold-queries", "health"]);

export function currentRoute() {
  const candidate = window.location.pathname.split("/").filter(Boolean)[0] || "search";
  return known.has(candidate) ? candidate : "search";
}

export function navigate(route, parameters = {}) {
  const search = new URLSearchParams(parameters);
  history.pushState({}, "", `/${route}${search.size ? `?${search}` : ""}`);
  window.dispatchEvent(new Event("dal:navigate"));
}

export function bindRoutes() {
  document.addEventListener("click", (event) => {
    const link = event.target.closest("[data-route]");
    if (!link || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    navigate(link.dataset.route, Object.fromEntries(new URL(link.href).searchParams));
  });
}
