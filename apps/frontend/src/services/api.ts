export type ApiError = {
  message: string;
  status: number;
  details?: unknown;
};

type RequestOptions = Omit<RequestInit, "body"> & { body?: unknown };

export type AuthResponse = {
  user_id: number;
  username: string;
  email?: string | null;
};

export type AccountItem = {
  id: number;
  account_name: string;
  login: string;
  password: string;
  lot_url?: string | null;
  mmr?: number | null;
  owner?: string | null;
  state?: string;
  steam_id?: string | null;
};

export type AccountCreatePayload = {
  account_name: string;
  login: string;
  password: string;
  mafile_json: string;
  mmr?: number | null;
  rental_duration?: number;
  rental_minutes?: number;
};

export type LotItem = {
  lot_number: number;
  account_id: number;
  account_name: string;
  lot_url?: string | null;
};

export type LotCreatePayload = {
  lot_number: number;
  account_id: number;
  lot_url: string;
};

export type ActiveRentalItem = {
  id: number;
  account: string;
  buyer: string;
  started: string;
  time_left: string;
  match_time?: string;
  hero?: string;
  status?: string;
};

const API_BASE = (import.meta as { env?: Record<string, string | undefined> }).env?.VITE_API_URL || "";
const API_PREFIX = "/api";

const buildUrl = (path: string) => {
  const base = API_BASE.replace(/\/$/, "");
  if (path.startsWith("http://") || path.startsWith("https://")) return path;
  if (path.startsWith("/")) return `${base}${API_PREFIX}${path}`;
  return `${base}${API_PREFIX}/${path}`;
};

const request = async <T>(path: string, options: RequestOptions = {}): Promise<T> => {
  const headers = new Headers(options.headers);
  if (!headers.has("Content-Type") && options.body !== undefined) {
    headers.set("Content-Type", "application/json");
  }

  const res = await fetch(buildUrl(path), {
    ...options,
    headers,
    credentials: "include",
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
  me: () => request<AuthResponse>("/auth/me", { method: "GET" }),
  logout: () => request<{ ok: boolean }>("/auth/logout", { method: "POST" }),
  listAccounts: () => request<{ items: AccountItem[] }>("/accounts", { method: "GET" }),
  createAccount: (payload: AccountCreatePayload) =>
    request<AccountItem>("/accounts", { method: "POST", body: payload }),
  deauthorizeSteam: (accountId: number) =>
    request<{ success: boolean }>(`/accounts/${accountId}/steam/deauthorize`, { method: "POST" }),
  listLots: () => request<{ items: LotItem[] }>("/lots", { method: "GET" }),
  createLot: (payload: LotCreatePayload) => request<LotItem>("/lots", { method: "POST", body: payload }),
  deleteLot: (lotNumber: number) => request<{ ok: boolean }>(`/lots/${lotNumber}`, { method: "DELETE" }),
  listActiveRentals: () => request<{ items: ActiveRentalItem[] }>("/rentals/active", { method: "GET" }),
};
