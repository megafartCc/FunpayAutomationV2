import React, { useCallback, useEffect, useMemo, useState } from "react";

import { api, OrderHistoryItem } from "../../services/api";
import { useWorkspace } from "../../context/WorkspaceContext";

type OrdersHistoryPageProps = {
  onToast?: (message: string, isError?: boolean) => void;
};

const ORDERS_GRID =
  "minmax(0,0.9fr) minmax(0,1.1fr) minmax(0,1.3fr) minmax(0,1fr) minmax(0,0.7fr) minmax(0,0.7fr) minmax(0,0.8fr) minmax(0,0.9fr) minmax(0,0.9fr) minmax(0,1fr) minmax(0,0.7fr)";

const formatMinutesLabel = (minutes?: number | null) => {
  const numeric = typeof minutes === "number" ? minutes : Number(minutes);
  if (!Number.isFinite(numeric)) return "-";
  const total = Math.max(0, Math.round(numeric));
  const hours = Math.floor(total / 60);
  const mins = total % 60;
  if (hours && mins) return `${hours}ч ${mins}м`;
  if (hours) return `${hours}ч`;
  return `${mins}м`;
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
    return { className: "bg-emerald-50 text-emerald-600", label: "Выдан" };
  }
  if (lower.includes("extend")) return { className: "bg-sky-50 text-sky-600", label: "Продлён" };
  if (lower.includes("blacklist_comp") || lower.includes("penalty")) {
    return { className: "bg-amber-50 text-amber-700", label: "Штраф оплачен" };
  }
  if (lower.includes("blacklist")) return { className: "bg-neutral-200 text-neutral-700", label: "В чёрном списке" };
  if (lower.includes("busy")) return { className: "bg-amber-50 text-amber-600", label: "Занят" };
  if (lower.includes("unmapped")) return { className: "bg-neutral-100 text-neutral-600", label: "Не привязан" };
  if (lower.includes("refund")) return { className: "bg-rose-50 text-rose-600", label: "Возврат" };
  if (lower.includes("closed")) return { className: "bg-neutral-200 text-neutral-700", label: "Закрыт" };
  if (!lower) return { className: "bg-neutral-100 text-neutral-600", label: "-" };
  return { className: "bg-neutral-100 text-neutral-700", label: action || "-" };
};

const orderStatusPill = (action?: string | null) => {
  const lower = (action || "").toLowerCase();
  if (lower.includes("refund")) {
    return { className: "bg-rose-50 text-rose-600", label: "Возврат" };
  }
  if (lower.includes("paid")) {
    return { className: "bg-emerald-50 text-emerald-600", label: "Оплачен" };
  }
  return { className: "bg-sky-50 text-sky-700", label: "Подтвержден" };
};

const formatWorkspaceLabel = (
  workspaceId: number | null | undefined,
  workspaceName: string | null | undefined,
) => {
  if (!workspaceId) return "Глобально";
  if (workspaceName) return `${workspaceName} (ID ${workspaceId})`;
  return `Рабочее пространство ${workspaceId}`;
};

const OrdersHistoryPage: React.FC<OrdersHistoryPageProps> = ({ onToast }) => {
  const { selectedId: selectedWorkspaceId, selectedPlatform, workspaces } = useWorkspace();
  const workspaceId = selectedWorkspaceId === "all" ? null : (selectedWorkspaceId as number);

  const [orders, setOrders] = useState<OrderHistoryItem[]>([]);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [refundLoadingId, setRefundLoadingId] = useState<string | null>(null);

  const workspacePlatforms = useMemo(() => {
    const map = new Map<number, "funpay" | "playerok">();
    workspaces.forEach((item) => {
      const key = (item.platform || "funpay").toLowerCase() === "playerok" ? "playerok" : "funpay";
      map.set(item.id, key);
    });
    return map;
  }, [workspaces]);

  const scopedWorkspaceIds = useMemo(() => {
    if (selectedPlatform === "all") return null;
    return new Set(
      workspaces
        .filter((item) => (item.platform || "funpay") === selectedPlatform)
        .map((item) => item.id),
    );
  }, [workspaces, selectedPlatform]);

  const visibleOrders = useMemo(() => {
    if (selectedPlatform === "all" || !scopedWorkspaceIds) return orders;
    return orders.filter((order) => order.workspace_id && scopedWorkspaceIds.has(order.workspace_id));
  }, [orders, selectedPlatform, scopedWorkspaceIds]);

  const loadOrders = useCallback(
    async (q?: string, silent = false) => {
      if (!silent) setLoading(true);
      try {
        const res = await api.listOrdersHistory(workspaceId ?? undefined, q?.trim() || undefined, 300);
        setOrders(res.items || []);
      } catch (err) {
        const message = (err as { message?: string })?.message || "Не удалось загрузить историю заказов.";
        onToast?.(message, true);
      } finally {
        if (!silent) setLoading(false);
      }
    },
    [workspaceId, onToast],
  );

  useEffect(() => {
    const handle = window.setTimeout(() => {
      void loadOrders(query);
    }, 350);
    return () => window.clearTimeout(handle);
  }, [query, loadOrders]);

  const totalLabel = useMemo(() => `${visibleOrders.length} записей`, [visibleOrders.length]);

  const platformPill = useCallback((platform: "funpay" | "playerok") => {
    if (platform === "playerok") {
      return { label: "PlayerOk", className: "bg-sky-50 text-sky-700" };
    }
    return { label: "FunPay", className: "bg-amber-50 text-amber-700" };
  }, []);

  const handleRefund = useCallback(
    async (order: OrderHistoryItem) => {
      if (!order.order_id) return;
      if (!window.confirm("Оформить возврат по этому заказу?")) return;
      setRefundLoadingId(order.order_id);
      try {
        const res = await api.refundOrder(order.order_id, order.workspace_id ?? undefined);
        if (!res.ok) {
          onToast?.(res.message || "Не удалось оформить возврат.", true);
        } else {
          onToast?.(res.message || "Возврат отправлен.");
          await loadOrders(query, true);
        }
      } catch (err) {
        const message = (err as { message?: string })?.message || "Не удалось оформить возврат.";
        onToast?.(message, true);
      } finally {
        setRefundLoadingId(null);
      }
    },
    [loadOrders, onToast, query],
  );

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h3 className="text-lg font-semibold text-neutral-900">История заказов</h3>
          <p className="text-sm text-neutral-500">
            Поиск по покупателю, ID заказа, аккаунту, Steam ID или лоту.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs rounded-full bg-neutral-100 px-3 py-1 font-semibold text-neutral-600">
            {totalLabel}
          </span>
          <button
            onClick={() => loadOrders(query)}
            className="rounded-lg border border-neutral-200 bg-neutral-50 px-3 py-2 text-xs text-neutral-600"
          >
            Обновить
          </button>
        </div>
      </div>
      <div className="rounded-2xl border border-neutral-200 bg-white p-6 shadow-sm shadow-neutral-200/70">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <label className="relative flex h-11 w-full max-w-xl items-center gap-3 rounded-lg border border-neutral-200 bg-neutral-50 px-4 text-sm text-neutral-500 shadow-sm shadow-neutral-200">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path
                d="M11 19C15.4183 19 19 15.4183 19 11C19 6.58172 15.4183 3 11 3C6.58172 3 3 6.58172 3 11C3 15.4183 6.58172 19 11 19Z"
                stroke="#9CA3AF"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
              <path d="M21 21L16.65 16.65" stroke="#9CA3AF" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
            <input
              type="search"
              placeholder="Поиск по покупателю, ID заказа, аккаунту, Steam ID"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              className="w-full bg-transparent text-neutral-700 placeholder:text-neutral-400 outline-none"
            />
          </label>
          <div className="text-xs text-neutral-500">
            {selectedWorkspaceId === "all" && selectedPlatform === "all"
              ? "Все рабочие пространства вместе."
              : "Фильтр по рабочему пространству."}
          </div>
        </div>
        <div className="overflow-x-hidden">
          <div className="min-w-0">
            <div className="mt-3 list-scroll">
              <div
                className="sticky top-0 z-10 grid gap-3 bg-white px-6 py-2 text-xs font-semibold text-neutral-500"
                style={{ gridTemplateColumns: ORDERS_GRID }}
              >
                <span>Заказ</span>
                <span>Покупатель</span>
                <span>Аккаунт</span>
                <span>Steam ID</span>
                <span>Длительность</span>
                <span>Цена</span>
                <span className="text-center">Действие</span>
                <span className="text-center">Статус</span>
                <span>Дата</span>
                <span>Рабочее пространство</span>
                <span className="text-center">Возврат</span>
              </div>
              <div className="mt-3 space-y-3">
                {loading && (
                  <div className="rounded-xl border border-dashed border-neutral-200 bg-neutral-50 px-4 py-6 text-center text-sm text-neutral-500">
                    Загружаем заказы...
                  </div>
                )}
                {!loading &&
                  visibleOrders.map((order, idx) => {
                    const pill = orderActionPill(order.action);
                    const statusPill = orderStatusPill(order.action);
                    const priceLabel =
                      order.price !== null && order.price !== undefined && !Number.isNaN(Number(order.price))
                        ? `RUB ${Number(order.price).toLocaleString()}`
                        : "-";
                    const accountLabel = order.account_name || order.account_login || "-";
                    const subLabelParts: string[] = [];
                    if (order.lot_number) subLabelParts.push(`Лот ${order.lot_number}`);
                    if (order.account_id) subLabelParts.push(`ID ${order.account_id}`);
                    if (order.account_login) subLabelParts.push(order.account_login);
                    const subLabel = subLabelParts.join(" · ");
                    const platformKey = workspacePlatforms.get(order.workspace_id ?? -1) || "funpay";
                    const platformBadge = platformPill(platformKey);
                    return (
                      <div
                        key={order.id ?? idx}
                        className="grid items-center gap-3 rounded-xl border border-neutral-100 bg-neutral-50 px-6 py-4 text-sm shadow-[0_4px_18px_-14px_rgba(0,0,0,0.18)]"
                        style={{ gridTemplateColumns: ORDERS_GRID }}
                      >
                      <a
                        href={`https://funpay.com/orders/${order.order_id}/`}
                        target="_blank"
                        rel="noreferrer"
                        className="min-w-0 truncate font-mono text-xs text-neutral-700 hover:underline"
                      >
                        {order.order_id || "-"}
                      </a>
                      <span className="min-w-0 truncate font-semibold text-neutral-800">{order.buyer || "-"}</span>
                      <div className="min-w-0">
                        <div className="truncate font-semibold text-neutral-900">{accountLabel}</div>
                        {subLabel ? <div className="text-xs text-neutral-400">{subLabel}</div> : <div className="text-xs text-neutral-300">-</div>}
                      </div>
                      <span className="min-w-0 truncate font-mono text-xs text-neutral-700">
                        {order.steam_id || "-"}
                      </span>
                      <span className="min-w-0 truncate font-mono text-neutral-900">
                        {formatMinutesLabel(order.rental_minutes)}
                      </span>
                      <span className="min-w-0 truncate font-semibold text-neutral-900">{priceLabel}</span>
                      <div className="flex items-center justify-center">
                        <span className={`inline-flex w-fit rounded-full px-3 py-1 text-xs font-semibold ${pill.className}`}>
                          {pill.label}
                        </span>
                      </div>
                      <div className="flex items-center justify-center">
                        <span
                          className={`inline-flex w-fit rounded-full px-3 py-1 text-xs font-semibold ${statusPill.className}`}
                        >
                          {statusPill.label}
                        </span>
                      </div>
                      <span className="min-w-0 truncate text-xs text-neutral-500">
                        {formatMoscowDateTime(order.created_at)}
                      </span>
                      <div className="flex min-w-0 items-center gap-2 text-xs text-neutral-600">
                        <span className="min-w-0 truncate">
                          {formatWorkspaceLabel(order.workspace_id, order.workspace_name)}
                        </span>
                        {selectedPlatform === "all" ? (
                          <span
                            className={`shrink-0 rounded-full px-2 py-0.5 text-[10px] font-semibold ${platformBadge.className}`}
                          >
                            {platformBadge.label}
                          </span>
                        ) : null}
                      </div>
                      <div className="flex items-center justify-center">
                        <button
                          type="button"
                          onClick={() => handleRefund(order)}
                          disabled={
                            !order.order_id ||
                            !!refundLoadingId ||
                            (order.action || "").toLowerCase().includes("refund") ||
                            platformKey !== "funpay"
                          }
                          className="rounded-lg border border-neutral-200 bg-white px-3 py-1 text-xs font-semibold text-rose-600 shadow-sm disabled:cursor-not-allowed disabled:opacity-50"
                        >
                          {refundLoadingId === order.order_id ? "..." : "Возврат"}
                        </button>
                      </div>
                      </div>
                    );
                  })}
                {!loading && visibleOrders.length === 0 && (
                  <div className="rounded-xl border border-dashed border-neutral-200 bg-neutral-50 px-4 py-6 text-center text-sm text-neutral-500">
                    Заказы не найдены.
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default OrdersHistoryPage;
