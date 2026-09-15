let accessToken = sessionStorage.getItem("dal-access-token") || "";

export function setAccessToken(value) {
  accessToken = value.trim();
  if (accessToken) sessionStorage.setItem("dal-access-token", accessToken);
  else sessionStorage.removeItem("dal-access-token");
}

export async function api(path, options = {}) {
  const headers = new Headers(options.headers || {});
  headers.set("Accept", "application/json");
  if (options.body) headers.set("Content-Type", "application/json");
  if (accessToken) headers.set("Authorization", `Bearer ${accessToken}`);
  const response = await fetch(`/api/v1${path}`, { ...options, headers });
  const payload = await response.json().catch(() => ({ detail: "The server returned no JSON." }));
  if (!response.ok) {
    const detail = Array.isArray(payload.detail)
      ? payload.detail.map((item) => item.msg).join("; ")
      : payload.detail || `Request failed (${response.status}).`;
    throw new Error(detail);
  }
  return payload;
}

export function query(values) {
  const parameters = new URLSearchParams();
  Object.entries(values).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") parameters.set(key, value);
  });
  return `?${parameters}`;
}
