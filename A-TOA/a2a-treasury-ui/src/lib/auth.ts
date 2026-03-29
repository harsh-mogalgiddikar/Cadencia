import type { RegisterPayload } from "./types";

/** Client-side login — calls our Route Handler (not FastAPI directly) */
export async function login(email: string, password: string) {
  const res = await fetch("/api/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) {
    const err = await res.json();
    throw err;
  }
  return res.json();
}

/** Client-side register — calls our Route Handler */
export async function register(data: RegisterPayload) {
  const res = await fetch("/api/auth/register", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const err = await res.json();
    throw err;
  }
  return res.json();
}

/** Client-side logout — clears httpOnly cookie via Route Handler */
export async function logout() {
  await fetch("/api/auth/logout", { method: "POST" });
  window.location.href = "/";
}

/** Fetch current enterprise profile from proxying Route Handler */
export async function getMe() {
  const res = await fetch("/api/auth/me");
  if (!res.ok) return null;
  return res.json();
}
