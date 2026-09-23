const TOKEN_KEY = "tracker.token";

export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
  }
}

export function getToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setToken(token: string | null): void {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token);
    else localStorage.removeItem(TOKEN_KEY);
  } catch {
    // Storage can be unavailable (private mode); the session just won't persist.
  }
}

/** Turns FastAPI's error bodies (a string or a list of validation errors) into one message. */
export function errorMessage(body: unknown, fallback: string): string {
  if (body && typeof body === "object" && "detail" in body) {
    const detail = (body as { detail: unknown }).detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      const msgs = detail
        .map((d) => (d && typeof d === "object" && "msg" in d ? String(d.msg) : null))
        .filter(Boolean);
      if (msgs.length) return msgs.join("; ");
    }
  }
  return fallback;
}

type Options = Omit<RequestInit, "body"> & { json?: unknown };

export async function api<T>(path: string, { json, headers, ...init }: Options = {}): Promise<T> {
  const h = new Headers(headers);
  const token = getToken();
  if (token) h.set("Authorization", `Bearer ${token}`);
  if (json !== undefined) h.set("Content-Type", "application/json");

  const res = await fetch(`/api${path}`, {
    ...init,
    headers: h,
    body: json === undefined ? undefined : JSON.stringify(json),
  });
  if (res.status === 204) return undefined as T;
  const body: unknown = await res.json().catch(() => null);
  if (!res.ok) throw new ApiError(res.status, errorMessage(body, res.statusText || "Request failed"));
  return body as T;
}
