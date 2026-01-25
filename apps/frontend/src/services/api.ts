export type ApiError = {
  message: string;
  status: number;
  details?: unknown;
};

type RequestOptions = Omit<RequestInit, "body"> & { body?: unknown };

type AuthResponse = {
  access_token: string;
  token_type: "bearer";
};

const API_PREFIX = "/api";

const buildUrl = (path: string) => {
  if (path.startsWith("http://") || path.startsWith("https://")) return path;
  if (path.startsWith("/")) return `${API_PREFIX}${path}`;
  return `${API_PREFIX}/${path}`;
};

const request = async <T>(path: string, options: RequestOptions = {}): Promise<T> => {
  const headers = new Headers(options.headers);
  if (!headers.has("Content-Type") && options.body !== undefined) {
    headers.set("Content-Type", "application/json");
  }

  const res = await fetch(buildUrl(path), {
    ...options,
    headers,
    body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
  });

  if (!res.ok) {
    let details: unknown = undefined;
    try {
      details = await res.json();
    } catch {
      // ignore
    }
    const error: ApiError = {
      message: (details as { detail?: string })?.detail || res.statusText || "Request failed",
      status: res.status,
      details,
    };
    throw error;
  }

  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
};

export const api = {
  login: (payload: { username: string; password: string }) =>
    request<AuthResponse>("/auth/login", { method: "POST", body: payload }),
  register: (payload: { username: string; password: string; golden_key: string }) =>
    request<AuthResponse>("/auth/register", { method: "POST", body: payload }),
};
