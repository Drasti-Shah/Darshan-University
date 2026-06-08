// Thin client for the Flask backend (the AI voice counsellor API).
// Uses NEXT_PUBLIC_API_BASE if set (e.g. http://127.0.0.1:5000 locally via
// .env.local); otherwise defaults to the deployed Render backend.
const BASE = (process.env.NEXT_PUBLIC_API_BASE || "https://darshan-university.onrender.com").replace(/\/$/, "");

async function req(path, opts = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json", "ngrok-skip-browser-warning": "1" },
    cache: "no-store",
    ...opts,
  });
  if (!res.ok) {
    let detail = "";
    try {
      detail = (await res.json()).error || "";
    } catch (_) {}
    throw new Error(detail || `Request failed (${res.status})`);
  }
  if (res.status === 204) return null;
  return res.json();
}

export const api = {
  base: BASE,
  health: () => req("/health"),
  stats: () => req("/api/stats"),
  leads: () => req("/leads"),
  call: (to) => req("/call", { method: "POST", body: JSON.stringify({ to }) }),
  campaign: (numbers) =>
    req("/campaign", { method: "POST", body: JSON.stringify({ numbers }) }),
  campaigns: () => req("/api/campaigns"),
};
