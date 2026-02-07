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
  last_rented_workspace_id?: number | null;
  last_rented_workspace_name?: string | null;
  account_name: string;
  login: string;
  password: string;
  lot_url?: string | null;
  lot_number?: number | null;
  mmr?: number | null;
  owner?: string | null;
  rental_start?: string | null;
  rental_duration?: number;
  rental_duration_minutes?: number | null;
  low_priority?: number;
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
  workspace_id?: number | null;
};

export type LotItem = {
  lot_number: number;
  account_id: number;
  account_name: string;
  lot_url?: string | null;
  workspace_id?: number | null;
};

export type LotSyncResult = {
  ok: boolean;
  updated: boolean;
};


export type RaiseCategoryItem = {
  category_id: number;
  category_name: string;
  workspace_id?: number | null;
  updated_at?: string | null;
};

export type AutoRaiseLogItem = {
  id: number;
  level: string;
  source?: string | null;
  line?: number | null;
  message: string;
  workspace_id?: number | null;
  created_at?: string | null;
};

export type BonusBalanceItem = {
  id: number;
  owner: string;
  balance_minutes: number;
  workspace_id?: number | null;
  workspace_name?: string | null;
  updated_at?: string | null;
};

export type BonusHistoryItem = {
  id: number;
  owner: string;
  delta_minutes: number;
  balance_minutes: number;
  reason: string;
  order_id?: string | null;
  account_id?: number | null;
  workspace_id?: number | null;
  workspace_name?: string | null;
  created_at?: string | null;
};

export type AutoRaiseSettings = {
  enabled: boolean;
  all_workspaces: boolean;
  interval_minutes: number;
  workspaces: Record<number, boolean>;
};


export type BotCustomizationSettings = {
  ai_enabled: boolean;
  tone: string;
  persona?: string;
  commands: Record<string, string>;
  responses: Record<string, string>;
  review_bonus_hours: number;
  blacklist: {
    compensation_hours: number;
    unit_minutes: number;
    permanent_message: string;
    blocked_message: string;
  };
  ai: {
    model?: string;
    temperature?: number;
    max_tokens?: number;
  };
};

export type BotCustomizationResponse = {
  workspace_id?: number | null;
  source: "workspace" | "global" | "default";
  settings: BotCustomizationSettings;
};

export type LotCreatePayload = {
  workspace_id?: number | null;
  lot_number: number;
  account_id: number;
  lot_url?: string | null;
};

export type BlacklistEntry = {
  id: number;
  owner: string;
  reason?: string | null;
  details?: string | null;
  status?: string | null;
  workspace_id?: number | null;
  created_at?: string | null;
};

export type BlacklistLog = {
  id: number;
  owner: string;
  action: string;
  reason?: string | null;
  details?: string | null;
  amount?: number | null;
  workspace_id?: number | null;
  created_at?: string | null;
};

export type BlacklistCreatePayload = {
  owner: string;
  reason?: string | null;
  order_id?: string | null;
  status?: string | null;
};

export type BlacklistUpdatePayload = {
  owner: string;
  reason?: string | null;
  status?: string | null;
};

export type OrderResolveItem = {
  order_id: string;
  owner: string;
  lot_number?: number | null;
  account_name?: string | null;
  account_id?: number | null;
  amount?: number | null;
  workspace_id?: number | null;
  workspace_name?: string | null;
  created_at?: string | null;
};

export type OrderHistoryItem = {
  id: number;
  order_id: string;
  buyer: string;
  account_name?: string | null;
  account_login?: string | null;
  account_id?: number | null;
  steam_id?: string | null;
  rental_minutes?: number | null;
  lot_number?: number | null;
  amount?: number | null;
  price?: number | null;
  action?: string | null;
  workspace_id?: number | null;
  workspace_name?: string | null;
  created_at?: string | null;
};

export type NotificationItem = {
  id: number;
  event_type: string;
  status: string;
  title: string;
  message?: string | null;
  owner?: string | null;
  account_name?: string | null;
  account_id?: number | null;
  order_id?: string | null;
  workspace_id?: number | null;
  workspace_name?: string | null;
  created_at?: string | null;
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
  platform: string;
  proxy_url: string;
  is_default: boolean;
  created_at?: string | null;
  key_hint?: string | null;
};

export type WorkspaceProxyCheck = {
  ok: boolean;
  direct_ip?: string | null;
  proxy_ip?: string | null;
  error?: string | null;
};

export type LotBulkSyncResponse = {
  ok: boolean;
  total: number;
  updated: number;
  skipped: number;
  failed: number;
};

export type WorkspaceStatusItem = {
  workspace_id?: number | null;
  platform: string;
  status: string;
  message?: string | null;
  updated_at?: string | null;
};

export type ChatItem = {
  id: number;
  chat_id: number;
  name?: string | null;
  last_message_text?: string | null;
  last_message_time?: string | null;
  unread?: number;
  admin_unread_count?: number;
  admin_requested?: number;
  workspace_id?: number | null;
};

export type ChatMessageItem = {
  id: number;
  message_id: number;
  chat_id: number;
  author?: string | null;
  text?: string | null;
  sent_time?: string | null;
  by_bot?: number;
  message_type?: string | null;
  workspace_id?: number | null;
};

export type PriceDumperResponse = {
  url: string;
  title?: string | null;
  description?: string | null;
  prices: number[];
  currency?: string | null;
  price_texts: string[];
  labels: string[];
  items: {
    title: string;
    price: number;
    currency?: string | null;
    url?: string | null;
    raw_price?: string | null;
    rent?: boolean;
  }[];
};

export type PriceDumperAnalysisResponse = {
  recommended_price?: number | null;
  currency?: string | null;
  lowest_price?: number | null;
  second_price?: number | null;
  price_count: number;
  analysis: string;
  model?: string | null;
};

export type PriceDumperHistoryItem = {
  created_at: string;
  avg_price?: number | null;
  median_price?: number | null;
  recommended_price?: number | null;
  lowest_price?: number | null;
  second_price?: number | null;
  price_count: number;
  currency?: string | null;
};

export type PriceDumperHistoryResponse = {
  url?: string | null;
  items: PriceDumperHistoryItem[];
};

export type PriceDumperRefreshResponse = {
  ok: boolean;
  processed: number;
  urls: string[];
};

export type RefundResponse = {
  ok: boolean;
  order_id: string;
  owner: string;
  workspace_id?: number | null;
  message?: string | null;
};

export type TelegramStatus = {
  connected: boolean;
  chat_id?: number | null;
  verified_at?: string | null;
  token_hint?: string | null;
  start_url?: string | null;
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
    let message = res.statusText || "Request failed";
    const detail = (details as { detail?: unknown })?.detail;
    if (typeof detail === "string" && detail.trim()) {
      message = detail;
    } else if (Array.isArray(detail)) {
      const parts = detail
        .map((item) => {
          if (typeof item === "string") return item;
          if (item && typeof item === "object" && "msg" in item) {
            const msg = (item as { msg?: string }).msg;
            if (msg) return msg;
          }
          try {
            return JSON.stringify(item);
          } catch {
            return String(item);
          }
        })
        .filter(Boolean);
      if (parts.length) message = parts.join(", ");
    } else if (detail && typeof detail === "object") {
      try {
        message = JSON.stringify(detail);
      } catch {
        message = String(detail);
      }
    }
    const error: ApiError = {
      message,
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
  listLowPriorityAccounts: (workspaceId?: number) =>
    request<{ items: AccountItem[] }>(withWorkspace("/accounts/low-priority", workspaceId), { method: "GET" }),
  createAccount: (payload: AccountCreatePayload) =>
    request<AccountItem>("/accounts", { method: "POST", body: payload }),
  updateAccount: (accountId: number, payload: AccountUpdatePayload, workspaceId?: number | null) =>
    request<AccountItem>(withWorkspace(`/accounts/${accountId}`, workspaceId), {
      method: "PATCH",
      body: payload,
    }),
  deleteAccount: (accountId: number, workspaceId?: number | null) =>
    request<{ status: string }>(withWorkspace(`/accounts/${accountId}`, workspaceId), { method: "DELETE" }),
  assignAccount: (accountId: number, owner: string, hours?: number | null, minutes?: number | null, workspaceId?: number | null) =>
    request<{ status: string }>(withWorkspace(`/accounts/${accountId}/assign`, workspaceId), {
      method: "POST",
      body: {
        owner,
        ...(hours !== null && hours !== undefined ? { hours } : {}),
        ...(minutes !== null && minutes !== undefined ? { minutes } : {}),
      },
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
  setLowPriority: (accountId: number, lowPriority: boolean, workspaceId?: number | null) =>
    request<{ success: boolean; low_priority: boolean }>(
      withWorkspace(`/accounts/${accountId}/low-priority`, workspaceId),
      {
        method: "POST",
        body: { low_priority: lowPriority },
      },
    ),
  freezeRental: (accountId: number, frozen: boolean, workspaceId?: number | null) =>
    request<{ success: boolean; frozen: boolean }>(withWorkspace(`/rentals/${accountId}/freeze`, workspaceId), {
      method: "POST",
      body: { frozen },
    }),
  replaceRental: (accountId: number, workspaceId?: number | null, mmrRange?: number) =>
    request<{ success: boolean; new_account_id?: number }>(
      withWorkspace(`/rentals/${accountId}/replace`, workspaceId),
      {
        method: "POST",
        body: mmrRange ? { mmr_range: mmrRange } : {},
      },
    ),
  deauthorizeSteam: (accountId: number, workspaceId?: number | null) =>
    request<{ success: boolean }>(withWorkspace(`/accounts/${accountId}/steam/deauthorize`, workspaceId), {
      method: "POST",
    }),
  listLots: (workspaceId?: number) =>
    request<{ items: LotItem[] }>(
      workspaceId ? `/lots?workspace_id=${workspaceId}` : "/lots",
      { method: "GET" },
    ),
  listRaiseCategories: (workspaceId?: number | null) => {
    const params = new URLSearchParams();
    if (workspaceId) params.set("workspace_id", String(workspaceId));
    const suffix = params.toString();
    return request<{ items: RaiseCategoryItem[] }>(
      `/raise-categories${suffix ? `?${suffix}` : ""}`,
      { method: "GET" },
    );
  },
  listAutoRaiseLogs: (workspaceId?: number | null, limit: number = 200) => {
    const params = new URLSearchParams();
    if (workspaceId) params.set("workspace_id", String(workspaceId));
    if (limit) params.set("limit", String(limit));
    const suffix = params.toString();
    return request<{ items: AutoRaiseLogItem[] }>(
      `/auto-raise/logs${suffix ? `?${suffix}` : ""}`,
      { method: "GET" },
    );
  },
  getAutoRaiseSettings: () =>
    request<AutoRaiseSettings>("/auto-raise/settings", { method: "GET" }),
  saveAutoRaiseSettings: (payload: AutoRaiseSettings) =>
    request<AutoRaiseSettings>("/auto-raise/settings", { method: "PUT", body: payload }),
  requestAutoRaise: (workspaceId?: number | null) =>
    request<{ created: number }>("/auto-raise/manual", {
      method: "POST",
      body: workspaceId ? { workspace_id: workspaceId } : {},
    }),
  getBotCustomization: (workspaceId?: number | null) =>
    request<BotCustomizationResponse>(withWorkspace("/bot-customization", workspaceId), { method: "GET" }),
  saveBotCustomization: (payload: BotCustomizationSettings, workspaceId?: number | null) =>
    request<BotCustomizationResponse>(withWorkspace("/bot-customization", workspaceId), {
      method: "PUT",
      body: payload,
    }),
  deleteBotCustomization: (workspaceId?: number | null) =>
    request<{ ok: boolean; removed?: number }>(withWorkspace("/bot-customization", workspaceId), {
      method: "DELETE",
    }),
  listBonusBalances: (query?: string, workspaceId?: number | null, limit: number = 200) => {
    const params = new URLSearchParams();
    if (query) params.set("query", query);
    if (workspaceId) params.set("workspace_id", String(workspaceId));
    if (limit) params.set("limit", String(limit));
    const suffix = params.toString();
    return request<{ items: BonusBalanceItem[] }>(`/bonus/balances${suffix ? `?${suffix}` : ""}`, {
      method: "GET",
    });
  },
  listBonusHistory: (owner: string, workspaceId?: number | null, limit: number = 200) => {
    const params = new URLSearchParams();
    params.set("owner", owner);
    if (workspaceId) params.set("workspace_id", String(workspaceId));
    if (limit) params.set("limit", String(limit));
    return request<{ items: BonusHistoryItem[] }>(`/bonus/history?${params.toString()}`, {
      method: "GET",
    });
  },
  adjustBonusBalance: (payload: {
    owner: string;
    delta_minutes: number;
    workspace_id?: number | null;
    reason?: string | null;
    order_id?: string | null;
    account_id?: number | null;
  }) =>
    request<{ balance_minutes: number; applied_delta: number }>("/bonus/adjust", {
      method: "POST",
      body: payload,
    }),
  createLot: (payload: LotCreatePayload) => request<LotItem>("/lots", { method: "POST", body: payload }),
  deleteLot: (lotNumber: number, workspaceId?: number) =>
    request<{ ok: boolean }>(
      workspaceId ? `/lots/${lotNumber}?workspace_id=${workspaceId}` : `/lots/${lotNumber}`,
      { method: "DELETE" },
    ),
  syncLotTitle: (lotNumber: number, workspaceId?: number) =>
    request<LotSyncResult>(
      workspaceId ? `/lots/${lotNumber}/sync-title?workspace_id=${workspaceId}` : `/lots/${lotNumber}/sync-title`,
      { method: "POST" },
    ),
  syncLotTitles: (workspaceId: number) =>
    request<LotBulkSyncResponse>(`/lots/sync-titles?workspace_id=${workspaceId}`, { method: "POST" }),
  listActiveRentals: (workspaceId?: number) =>
    request<{ items: ActiveRentalItem[] }>(withWorkspace("/rentals/active", workspaceId), { method: "GET" }),
  listBlacklist: (workspaceId?: number, query?: string, status?: string) => {
    const params = new URLSearchParams();
    if (workspaceId) params.set("workspace_id", String(workspaceId));
    if (query) params.set("query", query);
    if (status) params.set("status", status);
    const suffix = params.toString();
    return request<{ items: BlacklistEntry[] }>(`/blacklist${suffix ? `?${suffix}` : ""}`, { method: "GET" });
  },
  listBlacklistLogs: (workspaceId?: number, limit?: number) => {
    const params = new URLSearchParams();
    if (workspaceId) params.set("workspace_id", String(workspaceId));
    if (limit) params.set("limit", String(limit));
    const suffix = params.toString();
    return request<{ items: BlacklistLog[] }>(`/blacklist/logs${suffix ? `?${suffix}` : ""}`, { method: "GET" });
  },
  resolveOrder: (orderId: string, workspaceId?: number | null) => {
    const params = new URLSearchParams();
    params.set("order_id", orderId);
    return request<OrderResolveItem>(withWorkspace(`/orders/resolve?${params.toString()}`, workspaceId), {
      method: "GET",
    });
  },
  listOrdersHistory: (workspaceId?: number | null, query?: string, limit?: number) => {
    const params = new URLSearchParams();
    if (query) params.set("query", query);
    if (limit) params.set("limit", String(limit));
    const suffix = params.toString();
    return request<{ items: OrderHistoryItem[] }>(
      withWorkspace(`/orders/history${suffix ? `?${suffix}` : ""}`, workspaceId),
      { method: "GET" },
    );
  },
  listNotifications: (workspaceId?: number | null, limit?: number) => {
    const params = new URLSearchParams();
    const safeLimit = limit ? Math.min(limit, 500) : undefined;
    if (safeLimit) params.set("limit", String(safeLimit));
    const suffix = params.toString();
    return request<{ items: NotificationItem[] }>(
      withWorkspace(`/notifications${suffix ? `?${suffix}` : ""}`, workspaceId),
      { method: "GET" },
    );
  },
  createBlacklist: (payload: BlacklistCreatePayload, workspaceId?: number | null) =>
    request<BlacklistEntry>(withWorkspace("/blacklist", workspaceId), { method: "POST", body: payload }),
  updateBlacklist: (entryId: number, payload: BlacklistUpdatePayload, workspaceId?: number | null) =>
    request<BlacklistEntry>(withWorkspace(`/blacklist/${entryId}`, workspaceId), { method: "PATCH", body: payload }),
  removeBlacklist: (owners: string[], workspaceId?: number | null) =>
    request<{ removed: number }>(withWorkspace("/blacklist/remove", workspaceId), { method: "POST", body: { owners } }),
  clearBlacklist: (workspaceId?: number | null) =>
    request<{ removed: number }>(withWorkspace("/blacklist/clear", workspaceId), { method: "POST" }),
  listWorkspaces: () => request<{ items: WorkspaceItem[] }>("/workspaces", { method: "GET" }),
  listWorkspaceStatuses: (workspaceId?: number | null, platform?: string) => {
    const params = new URLSearchParams();
    if (workspaceId) params.set("workspace_id", String(workspaceId));
    if (platform) params.set("platform", platform);
    const suffix = params.toString();
    return request<{ items: WorkspaceStatusItem[] }>(
      `/workspaces/status${suffix ? `?${suffix}` : ""}`,
      { method: "GET" },
    );
  },
  createWorkspace: (payload: { name: string; platform?: string; golden_key: string; proxy_url: string; is_default?: boolean }) =>
    request<WorkspaceItem>("/workspaces", { method: "POST", body: payload }),
  updateWorkspace: (workspaceId: number, payload: { name?: string; golden_key?: string; proxy_url?: string; is_default?: boolean }) =>
    request<WorkspaceItem>(`/workspaces/${workspaceId}`, { method: "PATCH", body: payload }),
  setDefaultWorkspace: (workspaceId: number) =>
    request<{ ok: boolean }>(`/workspaces/${workspaceId}/default`, { method: "POST" }),
  deleteWorkspace: (workspaceId: number) =>
    request<{ ok: boolean }>(`/workspaces/${workspaceId}`, { method: "DELETE" }),
  checkWorkspaceProxy: (workspaceId: number) =>
    request<WorkspaceProxyCheck>(`/workspaces/${workspaceId}/proxy-check`, { method: "POST" }),
  listChats: (workspaceId?: number | null, query?: string, limit?: number, since?: string) => {
    const params = new URLSearchParams();
    if (query) params.set("query", query);
    if (limit) params.set("limit", String(limit));
    if (since) params.set("since", since);
    const suffix = params.toString();
    return request<{ items: ChatItem[] }>(
      withWorkspace(`/chats${suffix ? `?${suffix}` : ""}`, workspaceId),
      { method: "GET" },
    );
  },
  getChatHistory: (chatId: number, workspaceId?: number | null, limit?: number, afterId?: number | null) => {
    const params = new URLSearchParams();
    if (limit) params.set("limit", String(limit));
    if (afterId) params.set("after_id", String(afterId));
    const suffix = params.toString();
    return request<{ items: ChatMessageItem[] }>(
      withWorkspace(`/chats/${chatId}/history${suffix ? `?${suffix}` : ""}`, workspaceId),
      { method: "GET" },
    );
  },
  sendChatMessage: (chatId: number, text: string, workspaceId?: number | null) =>
    request<{ ok: boolean; queued_id?: number }>(withWorkspace(`/chats/${chatId}/send`, workspaceId), {
      method: "POST",
      body: { text },
    }),
  getTelegramStatus: () => request<TelegramStatus>("/telegram/status", { method: "GET" }),
  createTelegramToken: () => request<TelegramStatus>("/telegram/token", { method: "POST" }),
  disconnectTelegram: () => request<TelegramStatus>("/telegram/connection", { method: "DELETE" }),
  scrapePriceDumper: (url: string) =>
    request<PriceDumperResponse>("/plugins/price-dumper/scrape", {
      method: "POST",
      body: { url, rent_only: true },
    }),
  analyzePriceDumper: (items: PriceDumperResponse["items"], currency?: string | null, url?: string | null) =>
    request<PriceDumperAnalysisResponse>("/plugins/price-dumper/analyze", {
      method: "POST",
      body: { items, currency, url },
    }),
  refreshPriceDumper: () =>
    request<PriceDumperRefreshResponse>("/plugins/price-dumper/refresh", {
      method: "POST",
    }),
  priceDumperHistory: (url?: string | null, days: number = 30) => {
    const params = new URLSearchParams();
    if (url) params.set("url", url);
    if (days) params.set("days", String(days));
    const suffix = params.toString();
    return request<PriceDumperHistoryResponse>(
      `/plugins/price-dumper/history${suffix ? `?${suffix}` : ""}`,
      { method: "GET" },
    );
  },
  refundOrder: (payload: { order_id?: string; owner?: string; account_id?: number; workspace_id?: number | null }) =>
    request<RefundResponse>("/orders/refund", { method: "POST", body: payload }),
};
