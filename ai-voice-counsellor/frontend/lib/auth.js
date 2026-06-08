// Simple demo auth (frontend-only). For a real deployment, replace with a
// proper auth provider (NextAuth / JWT against a backend).
const KEY = "duvc_auth";
const DEMO_USER = process.env.NEXT_PUBLIC_DEMO_USER || "admin";
const DEMO_PASS = process.env.NEXT_PUBLIC_DEMO_PASS || "darshan123";

export function login(username, password) {
  if (username === DEMO_USER && password === DEMO_PASS) {
    const session = { user: username, ts: Date.now() };
    localStorage.setItem(KEY, JSON.stringify(session));
    return { ok: true };
  }
  return { ok: false, error: "Invalid username or password" };
}

export function logout() {
  localStorage.removeItem(KEY);
}

export function getSession() {
  if (typeof window === "undefined") return null;
  try {
    return JSON.parse(localStorage.getItem(KEY) || "null");
  } catch (_) {
    return null;
  }
}

export function isAuthed() {
  return !!getSession();
}
