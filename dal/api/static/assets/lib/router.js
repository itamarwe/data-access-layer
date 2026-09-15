const known = new Set(["search", "catalog", "curation", "doctrine", "gold-queries", "health"]);

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
    if (!link) return;
    event.preventDefault();
    navigate(link.dataset.route);
  });
}
