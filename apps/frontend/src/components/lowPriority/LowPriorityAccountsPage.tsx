import React, { useCallback, useEffect, useMemo, useState } from "react";
import { motion } from "framer-motion";
import { Link } from "react-router-dom";

import { api, AccountItem, OrderHistoryItem } from "../../services/api";
import { useWorkspace } from "../../context/WorkspaceContext";

type AccountRow = {
  id: number;
  name: string;
  login: string;
  mmr: number | string;
  owner?: string | null;
  workspaceId?: number | null;
  workspaceName?: string | null;
  lastRentedWorkspaceId?: number | null;
  lastRentedWorkspaceName?: string | null;
  rentalStart?: string | null;
  rentalDuration?: number;
  rentalDurationMinutes?: number | null;
};

type LowPriorityAccountsPageProps = {
  onToast?: (message: string, isError?: boolean) => void;
};

type EnrichedAccountRow = AccountRow & {
  buyer: string | null;
  buyerSource: "active" | "history" | null;
  lastOrder: OrderHistoryItem | null;
};

const GRID =
  "minmax(72px,0.6fr) minmax(200px,1.4fr) minmax(150px,1fr) minmax(150px,1fr) minmax(110px,0.6fr) minmax(200px,1fr) minmax(140px,0.8fr)";
const HISTORY_GRID =
  "minmax(120px,0.9fr) minmax(200px,1.1fr) minmax(140px,0.8fr) minmax(140px,0.7fr) minmax(170px,0.9fr) minmax(170px,0.9fr)";
const EASE: [number, number, number, number] = [0.22, 1, 0.36, 1];

const mapAccount = (item: AccountItem): AccountRow => ({
  id: item.id,
  name: item.account_name,
  login: item.login,
  mmr: item.mmr ?? "-",
  owner: item.owner ?? null,
  workspaceId: item.workspace_id ?? null,
  workspaceName: item.workspace_name ?? null,
  lastRentedWorkspaceId: item.last_rented_workspace_id ?? null,
  lastRentedWorkspaceName: item.last_rented_workspace_name ?? null,
  rentalStart: item.rental_start ?? null,
  rentalDuration: item.rental_duration ?? 0,
  rentalDurationMinutes: item.rental_duration_minutes ?? null,
});

const formatWorkspaceLabel = (
  workspaceId: number | null | undefined,
  workspaceName: string | null | undefined,
  workspaces: { id: number; name: string; is_default?: boolean }[],
) => {
  if (workspaceName && workspaceId) return `${workspaceName} (ID ${workspaceId})`;
  if (workspaceName) return workspaceName;
  if (!workspaceId) return "Workspace";
  const match = workspaces.find((item) => item.id === workspaceId);
  return match?.name ? `${match.name} (ID ${workspaceId})` : `Workspace ${workspaceId}`;
};

const formatDuration = (minutesTotal: number | null | undefined) => {
  if (!minutesTotal && minutesTotal !== 0) return "-";
  const minutes = Math.max(0, Math.floor(minutesTotal));
  const hours = Math.floor(minutes / 60);
  const rem = minutes % 60;
  return `${hours}h ${rem}m`;
};

const formatMinutesLabel = (minutes?: number | null) => {
  const numeric = typeof minutes === "number" ? minutes : Number(minutes);
  if (!Number.isFinite(numeric)) return "-";
  const total = Math.max(0, Math.round(numeric));
  const hours = Math.floor(total / 60);
  const mins = total % 60;
  if (hours && mins) return `${hours}h ${mins}m`;
  if (hours) return `${hours}h`;
  return `${mins}m`;
};

const formatMoscowDateTime = (value?: string | number | null) => {
  if (value === null || value === undefined || value === "") return "-";
  const ts = Date.parse(String(value));
  if (Number.isNaN(ts)) return String(value);
  return new Date(ts).toLocaleString("ru-RU", { timeZone: "Europe/Moscow" });
};

const orderActionPill = (action?: string | null) => {
  const lower = (action || "").toLowerCase();
  if (lower.includes("assign") || lower.includes("issued") || lower.includes("paid")) {
    return { className: "bg-emerald-50 text-emerald-600", label: "Issued" };
  }
  if (lower.includes("extend")) return { className: "bg-sky-50 text-sky-600", label: "Extended" };
  if (lower.includes("blacklist_comp") || lower.includes("penalty")) {
    return { className: "bg-amber-50 text-amber-700", label: "Penalty paid" };
  }
  if (lower.includes("blacklist")) return { className: "bg-neutral-200 text-neutral-700", label: "Blacklisted" };
  if (lower.includes("busy")) return { className: "bg-amber-50 text-amber-600", label: "Busy" };
  if (lower.includes("unmapped")) return { className: "bg-neutral-100 text-neutral-600", label: "Unmapped" };
  if (lower.includes("refund")) return { className: "bg-rose-50 text-rose-600", label: "Refunded" };
  if (lower.includes("closed")) return { className: "bg-neutral-200 text-neutral-700", label: "Closed" };
  if (!lower) return { className: "bg-neutral-100 text-neutral-600", label: "-" };
  return { className: "bg-neutral-100 text-neutral-700", label: action || "-" };
};

const buildChatLink = (buyer?: string | null) => {
  if (!buyer) return null;
  const params = new URLSearchParams();
  params.set("q", buyer);
  return `/chats?${params.toString()}`;
};

const LowPriorityAccountsPage: React.FC<LowPriorityAccountsPageProps> = ({ onToast }) => {
  const { selectedId: selectedWorkspaceId, workspaces } = useWorkspace();
  const isAllWorkspaces = selectedWorkspaceId === "all";
  const workspaceId = isAllWorkspaces ? null : (selectedWorkspaceId as number);

  const [accounts, setAccounts] = useState<AccountRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [query, setQuery] = useState("");
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [actionBusy, setActionBusy] = useState(false);
  const [orderHistory, setOrderHistory] = useState<OrderHistoryItem[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);

  const loadAccounts = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.listLowPriorityAccounts(workspaceId ?? undefined);
      setAccounts((res.items || []).map(mapAccount));
    } catch (err) {
      const message = (err as { message?: string })?.message || "Failed to load low priority accounts.";
      onToast?.(message, true);
    } finally {
      setLoading(false);
    }
  }, [workspaceId, onToast]);

  const loadHistory = useCallback(async () => {
    setHistoryLoading(true);
    try {
      const res = await api.listOrdersHistory(workspaceId ?? undefined, undefined, 500);
      setOrderHistory(res.items || []);
    } catch (err) {
      const message = (err as { message?: string })?.message || "Failed to load order history.";
      onToast?.(message, true);
    } finally {
      setHistoryLoading(false);
    }
  }, [workspaceId, onToast]);

  useEffect(() => {
    void loadAccounts();
  }, [loadAccounts]);

  useEffect(() => {
    void loadHistory();
  }, [loadHistory]);

  useEffect(() => {
    if (selectedId && !accounts.some((acc) => acc.id === selectedId)) {
      setSelectedId(null);
    }
  }, [accounts, selectedId]);

  const historyByAccountId = useMemo(() => {
    const map = new Map<number, OrderHistoryItem[]>();
    for (const item of orderHistory) {
      const accountId = item.account_id;
      if (!accountId) continue;
      const list = map.get(accountId);
      if (list) {
        list.push(item);
      } else {
        map.set(accountId, [item]);
      }
    }
    return map;
  }, [orderHistory]);

  const lastOrderByAccountId = useMemo(() => {
    const map = new Map<number, OrderHistoryItem>();
    for (const item of orderHistory) {
      const accountId = item.account_id;
      if (!accountId) continue;
      if (!map.has(accountId)) {
        map.set(accountId, item);
      }
    }
    return map;
  }, [orderHistory]);

  const enrichedAccounts = useMemo<EnrichedAccountRow[]>(
    () =>
      accounts.map((acc) => {
        const lastOrder = lastOrderByAccountId.get(acc.id) ?? null;
        const buyer = acc.owner ?? lastOrder?.buyer ?? null;
        const buyerSource = acc.owner ? "active" : lastOrder?.buyer ? "history" : null;
        return {
          ...acc,
          buyer,
          buyerSource,
          lastOrder,
        };
      }),
    [accounts, lastOrderByAccountId],
  );

  const filtered = useMemo(() => {
    const trimmed = query.trim().toLowerCase();
    if (!trimmed) return enrichedAccounts;
    return enrichedAccounts.filter((acc) => {
      const haystack = [
        acc.name,
        acc.login,
        acc.owner,
        acc.buyer,
        acc.workspaceName,
        acc.lastRentedWorkspaceName,
        acc.lastOrder?.order_id,
        acc.lastOrder?.lot_number ? String(acc.lastOrder?.lot_number) : null,
        acc.workspaceId ? String(acc.workspaceId) : null,
        acc.id ? String(acc.id) : null,
      ]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();
      return haystack.includes(trimmed);
    });
  }, [enrichedAccounts, query]);

  const selectedAccount = useMemo(
    () => enrichedAccounts.find((acc) => acc.id === selectedId) ?? null,
    [enrichedAccounts, selectedId],
  );

  const totalCount = enrichedAccounts.length;
  const buyerMatched = enrichedAccounts.filter((acc) => acc.buyer).length;
  const buyerMissing = Math.max(totalCount - buyerMatched, 0);
  const selectedHistory = useMemo(() => {
    if (!selectedAccount) return [];
    return (historyByAccountId.get(selectedAccount.id) || []).slice(0, 60);
  }, [historyByAccountId, selectedAccount]);
  const latestOrder = selectedHistory[0] ?? null;
  const selectedBuyerLabel = selectedAccount?.buyer ?? "-";
  const selectedBuyerTag =
    selectedAccount?.buyerSource === "active"
      ? "active"
      : selectedAccount?.buyerSource === "history"
        ? "history"
        : null;
  const selectedChatHref = buildChatLink(selectedAccount?.buyer ?? null);
  const latestOrderPill = latestOrder ? orderActionPill(latestOrder.action) : null;

  const handleRestore = async (account: AccountRow) => {
    if (actionBusy) return;
    const targetWorkspace =
      !isAllWorkspaces && workspaceId
        ? workspaceId
        : account.workspaceId ?? account.lastRentedWorkspaceId ?? undefined;
    if (!targetWorkspace) {
      onToast?.("Select a workspace to restore this account.", true);
      return;
    }
    setActionBusy(true);
    try {
      await api.setLowPriority(account.id, false, targetWorkspace);
      onToast?.("Low priority removed.");
      await loadAccounts();
      void loadHistory();
    } catch (err) {
      const message = (err as { message?: string })?.message || "Failed to restore account.";
      onToast?.(message, true);
    } finally {
      setActionBusy(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="grid gap-4 md:grid-cols-3">
        <div className="rounded-2xl border border-neutral-200 bg-white p-5 shadow-sm">
          <div className="text-xs font-semibold uppercase tracking-wide text-neutral-500">Low priority</div>
          <div className="mt-2 text-2xl font-semibold text-neutral-900">{totalCount}</div>
          <div className="mt-1 text-xs text-neutral-500">Accounts blocked from auto-assign.</div>
        </div>
        <div className="rounded-2xl border border-neutral-200 bg-white p-5 shadow-sm">
          <div className="text-xs font-semibold uppercase tracking-wide text-neutral-500">Buyer linked</div>
          <div className="mt-2 text-2xl font-semibold text-neutral-900">{buyerMatched}</div>
          <div className="mt-1 text-xs text-neutral-500">
            {totalCount === 0
              ? "No low priority accounts yet."
              : buyerMissing === 0
                ? "All accounts mapped to a buyer."
                : `${buyerMissing} missing buyer info.`}
          </div>
        </div>
        <div className="rounded-2xl border border-neutral-200 bg-white p-5 shadow-sm">
          <div className="text-xs font-semibold uppercase tracking-wide text-neutral-500">Workspace scope</div>
          <div className="mt-2 text-lg font-semibold text-neutral-900">
            {isAllWorkspaces ? "All workspaces" : `Workspace ${workspaceId ?? "-"}`}
          </div>
          <div className="mt-1 text-xs text-neutral-500">Filter in the top bar to change.</div>
        </div>
      </div>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_360px]">
        <div className="rounded-2xl border border-neutral-200 bg-white p-6 shadow-sm shadow-neutral-200/70">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h3 className="text-lg font-semibold text-neutral-900">Low Priority Accounts</h3>
              <p className="text-sm text-neutral-500">Review and restore accounts when ready.</p>
            </div>
            <button
              onClick={() => {
                void loadAccounts();
                void loadHistory();
              }}
              className="rounded-lg border border-neutral-200 bg-neutral-50 px-3 py-2 text-xs text-neutral-600"
              disabled={loading || historyLoading}
            >
              Refresh
            </button>
          </div>
          <div className="mt-4 flex flex-wrap items-center gap-3">
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search by account, login, buyer, workspace..."
              className="flex-1 rounded-lg border border-neutral-200 bg-white px-3 py-2 text-sm text-neutral-700 outline-none placeholder:text-neutral-400"
            />
            {query ? (
              <button
                onClick={() => setQuery("")}
                className="rounded-lg border border-neutral-200 bg-white px-3 py-2 text-xs text-neutral-600"
              >
                Clear
              </button>
            ) : null}
          </div>

          <div className="mt-5 overflow-hidden rounded-xl border border-neutral-200">
            <div className="grid bg-neutral-50 px-4 py-3 text-xs font-semibold uppercase tracking-wide text-neutral-500" style={{ gridTemplateColumns: GRID }}>
              <span>ID</span>
              <span>Account</span>
              <span>Login</span>
              <span>Buyer</span>
              <span>MMR</span>
              <span>Workspace</span>
              <span className="justify-self-end text-right">Actions</span>
            </div>
            <div className="max-h-[520px] overflow-y-auto">
              {loading ? (
                <div className="px-4 py-8 text-center text-sm text-neutral-500">Loading low priority accounts...</div>
              ) : filtered.length ? (
                filtered.map((acc) => {
                  const isActive = acc.id === selectedId;
                  const workspaceLabel = formatWorkspaceLabel(acc.workspaceId, acc.workspaceName, workspaces);
                  const buyerLabel = acc.buyer || "-";
                  const buyerTag =
                    acc.buyerSource === "active" ? "active" : acc.buyerSource === "history" ? "history" : null;
                  const chatHref = buildChatLink(acc.buyer);
                  return (
                    <motion.button
                      key={acc.id}
                      type="button"
                      onClick={() => setSelectedId(acc.id)}
                      className={`grid w-full items-center gap-2 border-t border-neutral-200 px-4 py-3 text-left text-sm transition ${
                        isActive ? "bg-neutral-50" : "bg-white"
                      }`}
                      style={{ gridTemplateColumns: GRID }}
                      whileHover={{ backgroundColor: "#f9fafb" }}
                      transition={{ duration: 0.15, ease: EASE }}
                    >
                      <span className="text-xs font-semibold text-neutral-600">#{acc.id}</span>
                      <span className="truncate text-sm font-semibold text-neutral-900">{acc.name}</span>
                      <span className="truncate text-xs text-neutral-500">{acc.login}</span>
                      <div className="min-w-0">
                        <div className="flex min-w-0 items-center gap-2">
                          <span className="min-w-0 truncate text-xs text-neutral-500">{buyerLabel}</span>
                          {buyerTag ? (
                            <span className="rounded-full bg-neutral-100 px-2 py-0.5 text-[10px] font-semibold text-neutral-500">
                              {buyerTag}
                            </span>
                          ) : null}
                        </div>
                      </div>
                      <span className="text-xs text-neutral-500">{acc.mmr}</span>
                      <span className="truncate text-xs text-neutral-500">{workspaceLabel}</span>
                      <div className="flex items-center justify-end gap-2 justify-self-end">
                        {chatHref ? (
                          <Link
                            to={chatHref}
                            onClick={(event) => event.stopPropagation()}
                            className="rounded-lg border border-neutral-200 bg-white px-3 py-1 text-xs font-semibold text-neutral-600 transition hover:border-neutral-300"
                          >
                            Chat
                          </Link>
                        ) : (
                          <span className="rounded-lg border border-neutral-200 bg-neutral-50 px-3 py-1 text-xs text-neutral-400">
                            Chat
                          </span>
                        )}
                        <button
                          type="button"
                          onClick={(event) => {
                            event.stopPropagation();
                            void handleRestore(acc);
                          }}
                          disabled={actionBusy}
                          className="rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-1 text-xs font-semibold text-emerald-700 transition hover:bg-emerald-100 disabled:cursor-not-allowed disabled:opacity-60"
                        >
                          Restore
                        </button>
                      </div>
                    </motion.button>
                  );
                })
              ) : (
                <div className="px-4 py-8 text-center text-sm text-neutral-500">
                  {query ? "No matching accounts found." : "No low priority accounts right now."}
                </div>
              )}
            </div>
          </div>
        </div>

        <div className="rounded-2xl border border-neutral-200 bg-white p-6 shadow-sm shadow-neutral-200/70">
          <div className="mb-4 flex items-center justify-between">
            <h3 className="text-lg font-semibold text-neutral-900">Account details</h3>
            <span className="text-xs text-neutral-500">{selectedAccount ? "Ready" : "Select an account"}</span>
          </div>
          {selectedAccount ? (
            <div className="space-y-4">
              <div className="rounded-xl border border-neutral-200 bg-neutral-50 p-4">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="text-xs font-semibold uppercase tracking-wide text-neutral-500">Selected</div>
                    <div className="mt-1 text-sm font-semibold text-neutral-900">
                      {selectedAccount.name || "Account"}
                    </div>
                  </div>
                  <span className="rounded-full bg-rose-50 px-3 py-1 text-xs font-semibold text-rose-600">
                    Low Priority
                  </span>
                </div>
                <div className="mt-3 grid gap-2 text-xs text-neutral-600">
                  <div className="flex items-center gap-2">
                    <span>Login:</span>
                    <span className="min-w-0 truncate">{selectedAccount.login || "-"}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span>Buyer:</span>
                    <span className="min-w-0 truncate">{selectedBuyerLabel}</span>
                    {selectedBuyerTag ? (
                      <span className="rounded-full bg-neutral-100 px-2 py-0.5 text-[10px] font-semibold text-neutral-500">
                        {selectedBuyerTag}
                      </span>
                    ) : null}
                  </div>
                  <div>MMR: {selectedAccount.mmr}</div>
                  <div>
                    Workspace:{" "}
                    {formatWorkspaceLabel(
                      selectedAccount.workspaceId,
                      selectedAccount.workspaceName,
                      workspaces,
                    )}
                  </div>
                  <div>
                    Last rented:{" "}
                    {selectedAccount.lastRentedWorkspaceId
                      ? formatWorkspaceLabel(
                          selectedAccount.lastRentedWorkspaceId,
                          selectedAccount.lastRentedWorkspaceName,
                          workspaces,
                        )
                      : "-"}
                  </div>
                  <div>Rental start: {selectedAccount.rentalStart || "-"}</div>
                  <div>Duration: {formatDuration(selectedAccount.rentalDurationMinutes)}</div>
                  <div className="flex flex-wrap items-center gap-2">
                    <span>Last order:</span>
                    {latestOrder ? (
                      <>
                        <a
                          href={`https://funpay.com/orders/${latestOrder.order_id}/`}
                          target="_blank"
                          rel="noreferrer"
                          className="font-mono text-[11px] text-neutral-700 hover:underline"
                        >
                          {latestOrder.order_id || "-"}
                        </a>
                        {latestOrderPill ? (
                          <span className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${latestOrderPill.className}`}>
                            {latestOrderPill.label}
                          </span>
                        ) : null}
                        <span className="text-[11px] text-neutral-400">
                          {formatMoscowDateTime(latestOrder.created_at)}
                        </span>
                      </>
                    ) : (
                      <span>-</span>
                    )}
                  </div>
                </div>
                {selectedChatHref ? (
                  <Link
                    to={selectedChatHref}
                    className="mt-3 inline-flex items-center gap-2 rounded-lg border border-neutral-200 bg-white px-3 py-2 text-[11px] font-semibold text-neutral-700 transition hover:border-neutral-300"
                  >
                    Open buyer chat
                  </Link>
                ) : (
                  <div className="mt-3 text-[11px] text-neutral-400">No buyer chat linked yet.</div>
                )}
              </div>
              <div className="rounded-xl border border-neutral-200 bg-neutral-50 p-4">
                <div className="mb-2 text-sm font-semibold text-neutral-800">Restore account</div>
                <p className="text-xs text-neutral-500">
                  Restored accounts return to the available inventory and stock lists.
                </p>
                <button
                  onClick={() => handleRestore(selectedAccount)}
                  disabled={actionBusy}
                  className="mt-4 w-full rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-2 text-sm font-semibold text-emerald-700 transition hover:bg-emerald-100 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  Remove low priority
                </button>
              </div>
            </div>
          ) : (
            <div className="rounded-xl border border-dashed border-neutral-200 bg-neutral-50 px-4 py-6 text-center text-sm text-neutral-500">
              Select an account to review the buyer and history.
            </div>
          )}
        </div>
      </div>

      <div className="rounded-2xl border border-neutral-200 bg-white p-6 shadow-sm shadow-neutral-200/70">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <div>
            <h3 className="text-lg font-semibold text-neutral-900">Replacement history</h3>
            <p className="text-sm text-neutral-500">Order log for the selected low-priority account.</p>
          </div>
          <div className="flex items-center gap-2">
            <span className="rounded-full bg-neutral-100 px-3 py-1 text-xs font-semibold text-neutral-600">
              {selectedAccount ? `${selectedHistory.length} records` : "Select an account"}
            </span>
            <button
              onClick={() => loadHistory()}
              className="rounded-lg border border-neutral-200 bg-neutral-50 px-3 py-2 text-xs text-neutral-600"
              disabled={historyLoading}
            >
              Refresh logs
            </button>
          </div>
        </div>
        <div className="overflow-x-auto">
          <div className="min-w-[900px]">
            <div
              className="grid gap-3 px-6 text-xs font-semibold uppercase tracking-wide text-neutral-500"
              style={{ gridTemplateColumns: HISTORY_GRID }}
            >
              <span>Order</span>
              <span>Buyer</span>
              <span>Action</span>
              <span>Duration</span>
              <span>Date</span>
              <span>Workspace</span>
            </div>
            <div className="mt-3 space-y-3 overflow-y-auto pr-1" style={{ maxHeight: "420px" }}>
              {historyLoading ? (
                <div className="rounded-xl border border-dashed border-neutral-200 bg-neutral-50 px-4 py-6 text-center text-sm text-neutral-500">
                  Loading history...
                </div>
              ) : selectedAccount ? (
                selectedHistory.length ? (
                  selectedHistory.map((item, idx) => {
                    const pill = orderActionPill(item.action);
                    const subLabel = item.lot_number
                      ? `Lot ${item.lot_number}`
                      : item.account_id
                        ? `ID ${item.account_id}`
                        : "-";
                    const workspaceLabel = item.workspace_id
                      ? item.workspace_name
                        ? `${item.workspace_name} (ID ${item.workspace_id})`
                        : formatWorkspaceLabel(item.workspace_id, null, workspaces)
                      : "Global";
                    return (
                      <div
                        key={item.id ?? idx}
                        className="grid items-center gap-3 rounded-xl border border-neutral-100 bg-neutral-50 px-6 py-4 text-sm shadow-[0_4px_18px_-14px_rgba(0,0,0,0.18)]"
                        style={{ gridTemplateColumns: HISTORY_GRID }}
                      >
                        <div className="min-w-0">
                          {item.order_id ? (
                            <a
                              href={`https://funpay.com/orders/${item.order_id}/`}
                              target="_blank"
                              rel="noreferrer"
                              className="min-w-0 truncate font-mono text-xs text-neutral-700 hover:underline"
                            >
                              {item.order_id}
                            </a>
                          ) : (
                            <span className="text-xs text-neutral-400">-</span>
                          )}
                          <div className="text-[11px] text-neutral-400">{subLabel}</div>
                        </div>
                        <span className="min-w-0 truncate font-semibold text-neutral-800">{item.buyer || "-"}</span>
                        <span className={`inline-flex w-fit justify-self-start rounded-full px-3 py-1 text-xs font-semibold ${pill.className}`}>
                          {pill.label}
                        </span>
                        <span className="min-w-0 truncate font-mono text-xs text-neutral-700">
                          {formatMinutesLabel(item.rental_minutes)}
                        </span>
                        <span className="min-w-0 truncate text-xs text-neutral-500">
                          {formatMoscowDateTime(item.created_at)}
                        </span>
                        <span className="min-w-0 truncate text-xs text-neutral-600">{workspaceLabel}</span>
                      </div>
                    );
                  })
                ) : (
                  <div className="rounded-xl border border-dashed border-neutral-200 bg-neutral-50 px-4 py-6 text-center text-sm text-neutral-500">
                    No history for this account yet.
                  </div>
                )
              ) : (
                <div className="rounded-xl border border-dashed border-neutral-200 bg-neutral-50 px-4 py-6 text-center text-sm text-neutral-500">
                  Select an account to view history.
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default LowPriorityAccountsPage;
