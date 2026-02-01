import React, { useCallback, useEffect, useMemo, useState } from "react";
import { motion } from "framer-motion";
import { Link } from "react-router-dom";

import { api, AccountItem, OrderHistoryItem } from "../../services/api";
import { useWorkspace } from "../../context/WorkspaceContext";
import { useI18n } from "../../i18n/useI18n";

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

type TranslateFn = (en: string, ru: string, vars?: Record<string, string | number>) => string;

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
  tr: TranslateFn,
) => {
  if (workspaceName && workspaceId) return `${workspaceName} (ID ${workspaceId})`;
  if (workspaceName) return workspaceName;
  if (!workspaceId) return tr("Workspace", "Рабочее пространство");
  const match = workspaces.find((item) => item.id === workspaceId);
  return match?.name
    ? `${match.name} (ID ${workspaceId})`
    : tr("Workspace {id}", "Рабочее пространство {id}", { id: workspaceId });
};

const formatDuration = (minutesTotal: number | null | undefined, tr: TranslateFn) => {
  if (!minutesTotal && minutesTotal !== 0) return "-";
  const minutes = Math.max(0, Math.floor(minutesTotal));
  const hours = Math.floor(minutes / 60);
  const rem = minutes % 60;
  return `${hours}${tr("h", "ч")} ${rem}${tr("m", "м")}`;
};

const formatMinutesLabel = (minutes: number | null | undefined, tr: TranslateFn) => {
  const numeric = typeof minutes === "number" ? minutes : Number(minutes);
  if (!Number.isFinite(numeric)) return "-";
  const total = Math.max(0, Math.round(numeric));
  const hours = Math.floor(total / 60);
  const mins = total % 60;
  if (hours && mins) return `${hours}${tr("h", "ч")} ${mins}${tr("m", "м")}`;
  if (hours) return `${hours}${tr("h", "ч")}`;
  return `${mins}${tr("m", "м")}`;
};

const formatMoscowDateTime = (value?: string | number | null) => {
  if (value === null || value === undefined || value === "") return "-";
  const ts = Date.parse(String(value));
  if (Number.isNaN(ts)) return String(value);
  return new Date(ts).toLocaleString("ru-RU", { timeZone: "Europe/Moscow" });
};

const orderActionPill = (action: string | null | undefined, tr: TranslateFn) => {
  const lower = (action || "").toLowerCase();
  if (lower.includes("assign") || lower.includes("issued") || lower.includes("paid")) {
    return { className: "bg-emerald-50 text-emerald-600", label: tr("Issued", "Выдан") };
  }
  if (lower.includes("extend")) {
    return { className: "bg-sky-50 text-sky-600", label: tr("Extended", "Продлён") };
  }
  if (lower.includes("blacklist_comp") || lower.includes("penalty")) {
    return { className: "bg-amber-50 text-amber-700", label: tr("Penalty paid", "Штраф оплачен") };
  }
  if (lower.includes("blacklist")) {
    return { className: "bg-neutral-200 text-neutral-700", label: tr("Blacklisted", "В чёрном списке") };
  }
  if (lower.includes("busy")) return { className: "bg-amber-50 text-amber-600", label: tr("Busy", "Занят") };
  if (lower.includes("unmapped")) {
    return { className: "bg-neutral-100 text-neutral-600", label: tr("Unmapped", "Не привязан") };
  }
  if (lower.includes("refund")) return { className: "bg-rose-50 text-rose-600", label: tr("Refunded", "Возврат") };
  if (lower.includes("closed")) return { className: "bg-neutral-200 text-neutral-700", label: tr("Closed", "Закрыт") };
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
  const { tr } = useI18n();
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
      const message =
        (err as { message?: string })?.message ||
        tr("Failed to load low priority accounts.", "Не удалось загрузить аккаунты с низким приоритетом.");
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
      const message =
        (err as { message?: string })?.message ||
        tr("Failed to load orders history.", "Не удалось загрузить историю заказов.");
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
      ? tr("active", "активный")
      : selectedAccount?.buyerSource === "history"
        ? tr("history", "история")
        : null;
  const selectedChatHref = buildChatLink(selectedAccount?.buyer ?? null);
  const latestOrderPill = latestOrder ? orderActionPill(latestOrder.action, tr) : null;

  const handleRestore = async (account: AccountRow) => {
    if (actionBusy) return;
    const targetWorkspace =
      !isAllWorkspaces && workspaceId
        ? workspaceId
        : account.workspaceId ?? account.lastRentedWorkspaceId ?? undefined;
    if (!targetWorkspace) {
      onToast?.(
        tr(
          "Select a workspace to restore this account.",
          "Выберите рабочее пространство, чтобы восстановить этот аккаунт.",
        ),
        true,
      );
      return;
    }
    setActionBusy(true);
    try {
      await api.setLowPriority(account.id, false, targetWorkspace);
      onToast?.(tr("Low priority removed.", "Низкий приоритет снят."));
      await loadAccounts();
      void loadHistory();
    } catch (err) {
      const message =
        (err as { message?: string })?.message ||
        tr("Failed to restore account.", "Не удалось восстановить аккаунт.");
      onToast?.(message, true);
    } finally {
      setActionBusy(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="grid gap-4 md:grid-cols-3">
        <div className="rounded-2xl border border-neutral-200 bg-white p-5 shadow-sm">
          <div className="text-xs font-semibold uppercase tracking-wide text-neutral-500">
            {tr("Low priority", "Низкий приоритет")}
          </div>
          <div className="mt-2 text-2xl font-semibold text-neutral-900">{totalCount}</div>
          <div className="mt-1 text-xs text-neutral-500">
            {tr("Accounts blocked from auto-assign.", "Аккаунты исключены из автоназначения.")}
          </div>
        </div>
        <div className="rounded-2xl border border-neutral-200 bg-white p-5 shadow-sm">
          <div className="text-xs font-semibold uppercase tracking-wide text-neutral-500">
            {tr("Buyer linked", "Покупатель привязан")}
          </div>
          <div className="mt-2 text-2xl font-semibold text-neutral-900">{buyerMatched}</div>
          <div className="mt-1 text-xs text-neutral-500">
            {totalCount === 0
              ? tr("No low priority accounts yet.", "Пока нет аккаунтов с низким приоритетом.")
              : buyerMissing === 0
                ? tr("All accounts mapped to a buyer.", "Все аккаунты связаны с покупателем.")
                : tr("{count} missing buyer info.", "Нет данных о покупателе: {count}.", { count: buyerMissing })}
          </div>
        </div>
        <div className="rounded-2xl border border-neutral-200 bg-white p-5 shadow-sm">
          <div className="text-xs font-semibold uppercase tracking-wide text-neutral-500">
            {tr("Workspace scope", "Область рабочих пространств")}
          </div>
          <div className="mt-2 text-lg font-semibold text-neutral-900">
            {isAllWorkspaces
              ? tr("All workspaces", "Все рабочие пространства")
              : tr("Workspace {id}", "Рабочее пространство {id}", { id: workspaceId ?? "-" })}
          </div>
          <div className="mt-1 text-xs text-neutral-500">
            {tr("Filter in the top bar to change.", "Измените фильтр в верхней панели.")}
          </div>
        </div>
      </div>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_360px]">
        <div className="rounded-2xl border border-neutral-200 bg-white p-6 shadow-sm shadow-neutral-200/70">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h3 className="text-lg font-semibold text-neutral-900">
                {tr("Low Priority Accounts", "Аккаунты с низким приоритетом")}
              </h3>
              <p className="text-sm text-neutral-500">
                {tr("Review and restore accounts when ready.", "Проверьте и восстановите аккаунты, когда будете готовы.")}
              </p>
            </div>
            <button
              onClick={() => {
                void loadAccounts();
                void loadHistory();
              }}
              className="rounded-lg border border-neutral-200 bg-neutral-50 px-3 py-2 text-xs text-neutral-600"
              disabled={loading || historyLoading}
            >
              {tr("Refresh", "Обновить")}
            </button>
          </div>
          <div className="mt-4 flex flex-wrap items-center gap-3">
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder={tr(
                "Search by account, login, buyer, workspace...",
                "Поиск по аккаунту, логину, покупателю, рабочему пространству...",
              )}
              className="flex-1 rounded-lg border border-neutral-200 bg-white px-3 py-2 text-sm text-neutral-700 outline-none placeholder:text-neutral-400"
            />
            {query ? (
              <button
                onClick={() => setQuery("")}
                className="rounded-lg border border-neutral-200 bg-white px-3 py-2 text-xs text-neutral-600"
              >
                {tr("Clear", "Очистить")}
              </button>
            ) : null}
          </div>

          <div className="mt-5 overflow-hidden rounded-xl border border-neutral-200">
            <div className="grid bg-neutral-50 px-4 py-3 text-xs font-semibold uppercase tracking-wide text-neutral-500" style={{ gridTemplateColumns: GRID }}>
              <span>ID</span>
              <span>{tr("Account", "Аккаунт")}</span>
              <span>{tr("Login", "Логин")}</span>
              <span>{tr("Buyer", "Покупатель")}</span>
              <span>MMR</span>
              <span>{tr("Workspace", "Рабочее пространство")}</span>
              <span className="justify-self-end text-right">{tr("Actions", "Действия")}</span>
            </div>
            <div className="max-h-[520px] overflow-y-auto">
              {loading ? (
                <div className="px-4 py-8 text-center text-sm text-neutral-500">
                  {tr("Loading low priority accounts...", "Загружаем аккаунты с низким приоритетом...")}
                </div>
              ) : filtered.length ? (
                filtered.map((acc) => {
                  const isActive = acc.id === selectedId;
                  const workspaceLabel = formatWorkspaceLabel(acc.workspaceId, acc.workspaceName, workspaces, tr);
                  const buyerLabel = acc.buyer || "-";
                  const buyerTag =
                    acc.buyerSource === "active"
                      ? tr("active", "активный")
                      : acc.buyerSource === "history"
                        ? tr("history", "история")
                        : null;
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
                            {tr("Chat", "Чат")}
                          </Link>
                        ) : (
                          <span className="rounded-lg border border-neutral-200 bg-neutral-50 px-3 py-1 text-xs text-neutral-400">
                            {tr("Chat", "Чат")}
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
                          {tr("Restore", "Восстановить")}
                        </button>
                      </div>
                    </motion.button>
                  );
                })
              ) : (
                <div className="px-4 py-8 text-center text-sm text-neutral-500">
                  {query
                    ? tr("No matching accounts found.", "Совпадений не найдено.")
                    : tr("No low priority accounts right now.", "Сейчас нет аккаунтов с низким приоритетом.")}
                </div>
              )}
            </div>
          </div>
        </div>

        <div className="rounded-2xl border border-neutral-200 bg-white p-6 shadow-sm shadow-neutral-200/70">
          <div className="mb-4 flex items-center justify-between">
            <h3 className="text-lg font-semibold text-neutral-900">{tr("Account details", "Детали аккаунта")}</h3>
            <span className="text-xs text-neutral-500">
              {selectedAccount ? tr("Ready", "Готово") : tr("Select an account", "Выберите аккаунт")}
            </span>
          </div>
          {selectedAccount ? (
            <div className="space-y-4">
              <div className="rounded-xl border border-neutral-200 bg-neutral-50 p-4">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="text-xs font-semibold uppercase tracking-wide text-neutral-500">
                      {tr("Selected", "Выбран")}
                    </div>
                    <div className="mt-1 text-sm font-semibold text-neutral-900">
                      {selectedAccount.name || tr("Account", "Аккаунт")}
                    </div>
                  </div>
                  <span className="rounded-full bg-rose-50 px-3 py-1 text-xs font-semibold text-rose-600">
                    {tr("Low Priority", "Низкий приоритет")}
                  </span>
                </div>
                <div className="mt-3 grid gap-2 text-xs text-neutral-600">
                  <div className="flex items-center gap-2">
                    <span>{tr("Login:", "Логин:")}</span>
                    <span className="min-w-0 truncate">{selectedAccount.login || "-"}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span>{tr("Buyer:", "Покупатель:")}</span>
                    <span className="min-w-0 truncate">{selectedBuyerLabel}</span>
                    {selectedBuyerTag ? (
                      <span className="rounded-full bg-neutral-100 px-2 py-0.5 text-[10px] font-semibold text-neutral-500">
                        {selectedBuyerTag}
                      </span>
                    ) : null}
                  </div>
                  <div>MMR: {selectedAccount.mmr}</div>
                  <div>
                    {tr("Workspace:", "Рабочее пространство:")}{" "}
                    {formatWorkspaceLabel(
                      selectedAccount.workspaceId,
                      selectedAccount.workspaceName,
                      workspaces,
                      tr,
                    )}
                  </div>
                  <div>
                    {tr("Last rented:", "Последняя аренда:")}{" "}
                    {selectedAccount.lastRentedWorkspaceId
                      ? formatWorkspaceLabel(
                          selectedAccount.lastRentedWorkspaceId,
                          selectedAccount.lastRentedWorkspaceName,
                          workspaces,
                          tr,
                        )
                      : "-"}
                  </div>
                  <div>{tr("Rental start:", "Начало аренды:")} {selectedAccount.rentalStart || "-"}</div>
                  <div>{tr("Duration:", "Длительность:")} {formatDuration(selectedAccount.rentalDurationMinutes, tr)}</div>
                  <div className="flex flex-wrap items-center gap-2">
                    <span>{tr("Last order:", "Последний заказ:")}</span>
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
                    {tr("Open buyer chat", "Открыть чат с покупателем")}
                  </Link>
                ) : (
                  <div className="mt-3 text-[11px] text-neutral-400">
                    {tr("No buyer chat linked yet.", "Чат с покупателем пока не привязан.")}
                  </div>
                )}
              </div>
              <div className="rounded-xl border border-neutral-200 bg-neutral-50 p-4">
                <div className="mb-2 text-sm font-semibold text-neutral-800">
                  {tr("Restore account", "Восстановить аккаунт")}
                </div>
                <p className="text-xs text-neutral-500">
                  {tr(
                    "Restored accounts return to the available inventory and stock lists.",
                    "Восстановленные аккаунты возвращаются в доступный инвентарь и списки стока.",
                  )}
                </p>
                <button
                  onClick={() => handleRestore(selectedAccount)}
                  disabled={actionBusy}
                  className="mt-4 w-full rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-2 text-sm font-semibold text-emerald-700 transition hover:bg-emerald-100 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {tr("Remove low priority", "Снять низкий приоритет")}
                </button>
              </div>
            </div>
          ) : (
            <div className="rounded-xl border border-dashed border-neutral-200 bg-neutral-50 px-4 py-6 text-center text-sm text-neutral-500">
              {tr("Select an account to review the buyer and history.", "Выберите аккаунт, чтобы посмотреть покупателя и историю.")}
            </div>
          )}
        </div>
      </div>

      <div className="rounded-2xl border border-neutral-200 bg-white p-6 shadow-sm shadow-neutral-200/70">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <div>
            <h3 className="text-lg font-semibold text-neutral-900">{tr("Replacement history", "История замен")}</h3>
            <p className="text-sm text-neutral-500">
              {tr("Order log for the selected low-priority account.", "Журнал заказов для выбранного аккаунта с низким приоритетом.")}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <span className="rounded-full bg-neutral-100 px-3 py-1 text-xs font-semibold text-neutral-600">
              {selectedAccount
                ? tr("{count} records", "{count} записей", { count: selectedHistory.length })
                : tr("Select an account", "Выберите аккаунт")}
            </span>
            <button
              onClick={() => loadHistory()}
              className="rounded-lg border border-neutral-200 bg-neutral-50 px-3 py-2 text-xs text-neutral-600"
              disabled={historyLoading}
            >
              {tr("Refresh logs", "Обновить журнал")}
            </button>
          </div>
        </div>
        <div className="overflow-x-auto">
          <div className="min-w-[900px]">
            <div
              className="grid gap-3 px-6 text-xs font-semibold uppercase tracking-wide text-neutral-500"
              style={{ gridTemplateColumns: HISTORY_GRID }}
            >
              <span>{tr("Order", "Заказ")}</span>
              <span>{tr("Buyer", "Покупатель")}</span>
              <span>{tr("Action", "Действие")}</span>
              <span>{tr("Duration", "Длительность")}</span>
              <span>{tr("Date", "Дата")}</span>
              <span>{tr("Workspace", "Рабочее пространство")}</span>
            </div>
            <div className="mt-3 space-y-3 overflow-y-auto pr-1" style={{ maxHeight: "420px" }}>
              {historyLoading ? (
                <div className="rounded-xl border border-dashed border-neutral-200 bg-neutral-50 px-4 py-6 text-center text-sm text-neutral-500">
                  {tr("Loading history...", "Загружаем историю...")}
                </div>
              ) : selectedAccount ? (
                selectedHistory.length ? (
                  selectedHistory.map((item, idx) => {
                    const pill = orderActionPill(item.action, tr);
                    const subLabel = item.lot_number
                      ? tr("Lot {num}", "Лот {num}", { num: item.lot_number })
                      : item.account_id
                        ? `ID ${item.account_id}`
                        : "-";
                    const workspaceLabel = item.workspace_id
                      ? item.workspace_name
                        ? `${item.workspace_name} (ID ${item.workspace_id})`
                        : formatWorkspaceLabel(item.workspace_id, null, workspaces, tr)
                      : tr("Global", "Глобально");
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
                          {formatMinutesLabel(item.rental_minutes, tr)}
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
                    {tr("No history for this account yet.", "Для этого аккаунта пока нет истории.")}
                  </div>
                )
              ) : (
                <div className="rounded-xl border border-dashed border-neutral-200 bg-neutral-50 px-4 py-6 text-center text-sm text-neutral-500">
                  {tr("Select an account to view history.", "Выберите аккаунт, чтобы увидеть историю.")}
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
