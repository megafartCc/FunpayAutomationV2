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
  workspace_id?: number | null;
  workspace_name?: string | null;
  account_name: string;
  login: string;
  password: string;
  lot_url?: string | null;
  mmr?: number | null;
  owner?: string | null;
  rental_start?: string | null;
  rental_duration?: number;
  rental_duration_minutes?: number | null;
  account_frozen?: number;
  rental_frozen?: number;
  state?: string;
  steam_id?: string | null;
};

export type AccountCreatePayload = {
  workspace_id: number;
  account_name: string;
  login: string;
  password: string;
  mafile_json: string;
  mmr?: number | null;
  rental_duration?: number;
  rental_minutes?: number;
};

export type AccountUpdatePayload = {
  account_name?: string;
  login?: string;
  password?: string;
  mmr?: number | null;
  rental_duration?: number;
  rental_minutes?: number;
};

export type LotItem = {
  lot_number: number;
  account_id: number;
  account_name: string;
  lot_url?: string | null;
  workspace_id?: number | null;
};

export type LotCreatePayload = {
  workspace_id?: number | null;
  lot_number: number;
  account_id: number;
  lot_url: string;
};

export type LotAliasItem = {
  id: number;
  lot_number: number;
  funpay_url: string;
  workspace_id?: number | null;
};

export type LotAliasCreatePayload = {
  lot_number: number;
  funpay_url: string;
  workspace_id?: number | null;
};

export type LotAliasReplacePayload = {
  lot_number: number;
  urls: string[];
  workspace_id?: number | null;
};

export type ActiveRentalItem = {
  id: number;
  account: string;
  buyer: string;
  started: string;
  time_left: string;
  workspace_id?: number | null;
  workspace_name?: string | null;
  match_time?: string;
  hero?: string;
  status?: string;
};

export type WorkspaceItem = {
  id: number;
  name: string;
  proxy_url: string;
  is_default: boolean;
  created_at?: string | null;
  key_hint?: string | null;
};

const API_BASE = (import.meta as { env?: Record<string, string | undefined> }).env?.VITE_API_URL || "";
const API_PREFIX = "/api";

const withWorkspace = (path: string, workspaceId?: number | null) => {
  if (!workspaceId) return path;
  const joiner = path.includes("?") ? "&" : "?";
  return `${path}${joiner}workspace_id=${workspaceId}`;
};

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
  listAccounts: (workspaceId?: number) =>
    request<{ items: AccountItem[] }>(withWorkspace("/accounts", workspaceId), { method: "GET" }),
  createAccount: (payload: AccountCreatePayload) =>
    request<AccountItem>("/accounts", { method: "POST", body: payload }),
  updateAccount: (accountId: number, payload: AccountUpdatePayload, workspaceId?: number | null) =>
    request<AccountItem>(withWorkspace(`/accounts/${accountId}`, workspaceId), {
      method: "PATCH",
      body: payload,
    }),
  deleteAccount: (accountId: number, workspaceId?: number | null) =>
    request<{ status: string }>(withWorkspace(`/accounts/${accountId}`, workspaceId), { method: "DELETE" }),
  assignAccount: (accountId: number, owner: string, workspaceId?: number | null) =>
    request<{ status: string }>(withWorkspace(`/accounts/${accountId}/assign`, workspaceId), {
      method: "POST",
      body: { owner },
    }),
  releaseAccount: (accountId: number, workspaceId?: number | null) =>
    request<{ status: string }>(withWorkspace(`/accounts/${accountId}/release`, workspaceId), {
      method: "POST",
    }),
  extendAccount: (accountId: number, hours: number, minutes: number, workspaceId?: number | null) =>
    request<{ status: string }>(withWorkspace(`/accounts/${accountId}/extend`, workspaceId), {
      method: "POST",
      body: { hours, minutes },
    }),
  freezeAccount: (accountId: number, frozen: boolean, workspaceId?: number | null) =>
    request<{ success: boolean; frozen: boolean }>(withWorkspace(`/accounts/${accountId}/freeze`, workspaceId), {
      method: "POST",
      body: { frozen },
    }),
  freezeRental: (accountId: number, frozen: boolean, workspaceId?: number | null) =>
    request<{ success: boolean; frozen: boolean }>(withWorkspace(`/rentals/${accountId}/freeze`, workspaceId), {
      method: "POST",
      body: { frozen },
    }),
  deauthorizeSteam: (accountId: number, workspaceId?: number | null) =>
    request<{ success: boolean }>(withWorkspace(`/accounts/${accountId}/steam/deauthorize`, workspaceId), {
      method: "POST",
    }),
  listLots: (workspaceId?: number) =>
    request<{ items: LotItem[] }>(
      workspaceId ? `/lots?workspace_id=${workspaceId}` : "/lots",
      { method: "GET" },
    ),
  createLot: (payload: LotCreatePayload) => request<LotItem>("/lots", { method: "POST", body: payload }),
  deleteLot: (lotNumber: number, workspaceId?: number) =>
    request<{ ok: boolean }>(
      workspaceId ? `/lots/${lotNumber}?workspace_id=${workspaceId}` : `/lots/${lotNumber}`,
      { method: "DELETE" },
    ),
  listLotAliases: (workspaceId?: number) =>
    request<{ items: LotAliasItem[] }>(withWorkspace("/lot-aliases", workspaceId), { method: "GET" }),
  createLotAlias: (payload: LotAliasCreatePayload) =>
    request<LotAliasItem>("/lot-aliases", { method: "POST", body: payload }),
  deleteLotAlias: (aliasId: number, workspaceId?: number | null) =>
    request<{ ok: boolean }>(withWorkspace(`/lot-aliases/${aliasId}`, workspaceId), {
      method: "DELETE",
    }),
  replaceLotAliases: (payload: LotAliasReplacePayload) =>
    request<{ items: LotAliasItem[] }>("/lot-aliases/replace", { method: "POST", body: payload }),
  listActiveRentals: (workspaceId?: number) =>
    request<{ items: ActiveRentalItem[] }>(withWorkspace("/rentals/active", workspaceId), { method: "GET" }),
  listWorkspaces: () => request<{ items: WorkspaceItem[] }>("/workspaces", { method: "GET" }),
  createWorkspace: (payload: { name: string; golden_key: string; proxy_url: string; is_default?: boolean }) =>
    request<WorkspaceItem>("/workspaces", { method: "POST", body: payload }),
  updateWorkspace: (workspaceId: number, payload: { name?: string; golden_key?: string; proxy_url?: string; is_default?: boolean }) =>
    request<WorkspaceItem>(`/workspaces/${workspaceId}`, { method: "PATCH", body: payload }),
  setDefaultWorkspace: (workspaceId: number) =>
    request<{ ok: boolean }>(`/workspaces/${workspaceId}/default`, { method: "POST" }),
  deleteWorkspace: (workspaceId: number) =>
    request<{ ok: boolean }>(`/workspaces/${workspaceId}`, { method: "DELETE" }),
};
