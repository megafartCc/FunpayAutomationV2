import React, { useCallback, useEffect, useMemo, useState } from "react";
import { useWorkspace } from "../../context/WorkspaceContext";
import { useI18n } from "../../i18n/useI18n";
import { api, BonusBalanceItem, BonusHistoryItem, OrderHistoryItem } from "../../services/api";

type BonusPageProps = {
  onToast?: (message: string, isError?: boolean) => void;
};

const formatMinutesLabel = (minutes: number, hoursLabel: string, minutesLabel: string) => {
  const total = Math.round(minutes || 0);
  const sign = total < 0 ? "-" : "";
  const abs = Math.abs(total);
  const hours = Math.floor(abs / 60);
  const mins = abs % 60;
  if (hours && mins) return `${sign}${hours}${hoursLabel} ${mins}${minutesLabel}`;
  if (hours) return `${sign}${hours}${hoursLabel}`;
  return `${sign}${mins}${minutesLabel}`;
};

const BonusPage: React.FC<BonusPageProps> = ({ onToast }) => {
  const { t } = useI18n();
  const { selectedId, workspaces } = useWorkspace();
  const workspaceId = selectedId === "all" ? null : (selectedId as number);

  const [query, setQuery] = useState("");
  const [balances, setBalances] = useState<BonusBalanceItem[]>([]);
  const [balancesLoading, setBalancesLoading] = useState(false);
  const [balancesError, setBalancesError] = useState<string | null>(null);

  const [selectedOwner, setSelectedOwner] = useState<string | null>(null);
  const [history, setHistory] = useState<BonusHistoryItem[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyError, setHistoryError] = useState<string | null>(null);

  const [orders, setOrders] = useState<OrderHistoryItem[]>([]);
  const [ordersLoading, setOrdersLoading] = useState(false);
  const [ordersError, setOrdersError] = useState<string | null>(null);

  const [adjustMinutes, setAdjustMinutes] = useState(60);
  const [adjustReason, setAdjustReason] = useState("");
  const [adjustLoading, setAdjustLoading] = useState(false);

  const workspaceMap = useMemo(() => {
    const map = new Map<number, string>();
    workspaces.forEach((ws) => map.set(ws.id, ws.name));
    return map;
  }, [workspaces]);

  const hoursLabel = t("common.hoursShort");
  const minutesLabel = t("common.minutesShort");

  const selectedBalance = useMemo(() => {
    if (!selectedOwner) return null;
    return balances.find((item) => item.owner === selectedOwner) || null;
  }, [balances, selectedOwner]);

  const loadBalances = useCallback(async () => {
    setBalancesLoading(true);
    setBalancesError(null);
    try {
      const res = await api.listBonusBalances(query, workspaceId, 200);
      setBalances(res.items || []);
      if (!selectedOwner && res.items && res.items.length > 0) {
        setSelectedOwner(res.items[0].owner);
      }
    } catch (err) {
      const message = (err as { message?: string })?.message || t("bonus.loadError");
      setBalancesError(message);
    } finally {
      setBalancesLoading(false);
    }
  }, [query, workspaceId, selectedOwner, t]);

  useEffect(() => {
    void loadBalances();
  }, [loadBalances]);

  const loadHistory = useCallback(async () => {
    if (!selectedOwner) {
      setHistory([]);
      return;
    }
    setHistoryLoading(true);
    setHistoryError(null);
    try {
      const res = await api.listBonusHistory(selectedOwner, workspaceId, 200);
      setHistory(res.items || []);
    } catch (err) {
      const message = (err as { message?: string })?.message || t("bonus.historyError");
      setHistoryError(message);
    } finally {
      setHistoryLoading(false);
    }
  }, [selectedOwner, workspaceId, t]);

  const loadOrders = useCallback(async () => {
    if (!selectedOwner) {
      setOrders([]);
      return;
    }
    setOrdersLoading(true);
    setOrdersError(null);
    try {
      const res = await api.listOrdersHistory(workspaceId, selectedOwner, 80);
      setOrders(res.items || []);
    } catch (err) {
      const message = (err as { message?: string })?.message || t("bonus.ordersError");
      setOrdersError(message);
    } finally {
      setOrdersLoading(false);
    }
  }, [selectedOwner, workspaceId, t]);

  useEffect(() => {
    void loadHistory();
    void loadOrders();
  }, [loadHistory, loadOrders]);

  const handleAdjust = async (direction: "add" | "remove") => {
    if (!selectedOwner) return;
    const minutes = Math.max(0, Math.round(adjustMinutes || 0));
    if (!minutes) {
      onToast?.(t("bonus.adjustInvalid"), true);
      return;
    }
    const delta = direction === "add" ? minutes : -minutes;
    setAdjustLoading(true);
    try {
      const res = await api.adjustBonusBalance({
        owner: selectedOwner,
        delta_minutes: delta,
        workspace_id: workspaceId,
        reason: adjustReason || (direction === "add" ? "manual_add" : "manual_remove"),
      });
      onToast?.(
        t("bonus.adjustSuccess", { balance: formatMinutesLabel(res.balance_minutes, hoursLabel, minutesLabel) }),
      );
      await loadBalances();
      await loadHistory();
    } catch (err) {
      const message = (err as { message?: string })?.message || t("bonus.adjustError");
      onToast?.(message, true);
    } finally {
      setAdjustLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="rounded-2xl border border-neutral-200 bg-white p-6 shadow-sm shadow-neutral-200/70">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h3 className="text-lg font-semibold text-neutral-900">{t("bonus.title")}</h3>
            <p className="text-sm text-neutral-500">{t("bonus.desc")}</p>
          </div>
          <span className="rounded-full bg-neutral-100 px-3 py-1 text-xs font-semibold text-neutral-600">
            {t("bonus.chatHint")}
          </span>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-[320px_1fr]">
        <div className="rounded-2xl border border-neutral-200 bg-white p-5 shadow-sm shadow-neutral-200/70">
          <div className="flex items-center justify-between gap-2">
            <h4 className="text-sm font-semibold text-neutral-900">{t("bonus.balancesTitle")}</h4>
            <span className="rounded-full bg-neutral-100 px-2 py-0.5 text-[11px] font-semibold text-neutral-600">
              {balances.length}
            </span>
          </div>
          <div className="mt-3">
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder={t("bonus.searchPlaceholder")}
              className="w-full rounded-lg border border-neutral-200 bg-white px-3 py-2 text-sm text-neutral-700"
            />
          </div>
          <div className="mt-4 space-y-2 overflow-y-auto pr-1" style={{ maxHeight: "520px" }}>
            {balancesLoading && (
              <div className="rounded-xl border border-dashed border-neutral-200 bg-neutral-50 px-4 py-6 text-center text-sm text-neutral-500">
                {t("bonus.loading")}
              </div>
            )}
            {!balancesLoading && balancesError && (
              <div className="rounded-xl border border-rose-100 bg-rose-50 px-4 py-6 text-center text-sm text-rose-600">
                {balancesError}
              </div>
            )}
            {!balancesLoading &&
              !balancesError &&
              balances.map((item) => {
                const isActive = item.owner === selectedOwner;
                const balanceLabel = formatMinutesLabel(item.balance_minutes, hoursLabel, minutesLabel);
                const wsLabel =
                  item.workspace_id !== null && item.workspace_id !== undefined
                    ? workspaceMap.get(item.workspace_id) || `${t("common.workspace")} ${item.workspace_id}`
                    : t("common.allWorkspaces");
                return (
                  <button
                    key={`${item.owner}-${item.workspace_id ?? "all"}`}
                    type="button"
                    onClick={() => setSelectedOwner(item.owner)}
                    className={`flex w-full flex-col gap-1 rounded-xl border px-4 py-3 text-left transition ${
                      isActive
                        ? "border-neutral-900 bg-neutral-900 text-white"
                        : "border-neutral-200 bg-neutral-50 text-neutral-700 hover:border-neutral-300"
                    }`}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-sm font-semibold">{item.owner}</span>
                      <span className={`text-xs font-semibold ${isActive ? "text-white" : "text-neutral-600"}`}>
                        {balanceLabel}
                      </span>
                    </div>
                    <span className={`text-[11px] ${isActive ? "text-white/70" : "text-neutral-500"}`}>{wsLabel}</span>
                  </button>
                );
              })}
            {!balancesLoading && !balancesError && balances.length === 0 && (
              <div className="rounded-xl border border-dashed border-neutral-200 bg-neutral-50 px-4 py-6 text-center text-sm text-neutral-500">
                {t("bonus.empty")}
              </div>
            )}
          </div>
        </div>

        <div className="space-y-6">
          <div className="rounded-2xl border border-neutral-200 bg-white p-6 shadow-sm shadow-neutral-200/70">
            {selectedOwner ? (
              <>
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <div className="text-sm font-semibold text-neutral-500">{t("bonus.selectedTitle")}</div>
                    <div className="text-xl font-semibold text-neutral-900">{selectedOwner}</div>
                  </div>
                  <span className="rounded-full bg-neutral-900 px-3 py-1 text-xs font-semibold text-white">
                    {formatMinutesLabel(selectedBalance?.balance_minutes || 0, hoursLabel, minutesLabel)}
                  </span>
                </div>
                <div className="mt-4 grid gap-3 md:grid-cols-[1fr_140px]">
                  <input
                    type="number"
                    min={0}
                    value={adjustMinutes}
                    onChange={(event) => setAdjustMinutes(Number(event.target.value))}
                    className="w-full rounded-lg border border-neutral-200 bg-white px-3 py-2 text-sm text-neutral-700"
                    placeholder={t("bonus.adjustMinutes")}
                  />
                  <div className="flex gap-2">
                    <button
                      type="button"
                      onClick={() => handleAdjust("add")}
                      disabled={adjustLoading}
                      className="flex-1 rounded-lg bg-neutral-900 px-3 py-2 text-xs font-semibold text-white disabled:opacity-60"
                    >
                      {t("bonus.add")}
                    </button>
                    <button
                      type="button"
                      onClick={() => handleAdjust("remove")}
                      disabled={adjustLoading}
                      className="flex-1 rounded-lg border border-neutral-200 bg-white px-3 py-2 text-xs font-semibold text-neutral-600 disabled:opacity-60"
                    >
                      {t("bonus.remove")}
                    </button>
                  </div>
                </div>
                <input
                  value={adjustReason}
                  onChange={(event) => setAdjustReason(event.target.value)}
                  className="mt-3 w-full rounded-lg border border-neutral-200 bg-white px-3 py-2 text-sm text-neutral-700"
                  placeholder={t("bonus.adjustReason")}
                />
              </>
            ) : (
              <div className="text-sm text-neutral-500">{t("bonus.selectHint")}</div>
            )}
          </div>

          <div className="grid gap-6 lg:grid-cols-2">
            <div className="rounded-2xl border border-neutral-200 bg-white p-5 shadow-sm shadow-neutral-200/70">
              <div className="flex items-center justify-between gap-2">
                <h4 className="text-sm font-semibold text-neutral-900">{t("bonus.historyTitle")}</h4>
                <span className="rounded-full bg-neutral-100 px-2 py-0.5 text-[11px] font-semibold text-neutral-600">
                  {history.length}
                </span>
              </div>
              <div className="mt-4 space-y-2 overflow-y-auto pr-1" style={{ maxHeight: "360px" }}>
                {historyLoading && (
                  <div className="rounded-xl border border-dashed border-neutral-200 bg-neutral-50 px-4 py-6 text-center text-sm text-neutral-500">
                    {t("bonus.historyLoading")}
                  </div>
                )}
                {!historyLoading && historyError && (
                  <div className="rounded-xl border border-rose-100 bg-rose-50 px-4 py-6 text-center text-sm text-rose-600">
                    {historyError}
                  </div>
                )}
                {!historyLoading &&
                  !historyError &&
                  history.map((item) => {
                    const deltaLabel = formatMinutesLabel(item.delta_minutes, hoursLabel, minutesLabel);
                    const balanceLabel = formatMinutesLabel(item.balance_minutes, hoursLabel, minutesLabel);
                    return (
                      <div
                        key={item.id}
                        className="rounded-xl border border-neutral-100 bg-neutral-50 px-4 py-3 text-xs text-neutral-600"
                      >
                        <div className="flex items-center justify-between gap-2">
                          <span className="font-semibold text-neutral-800">{item.reason}</span>
                          <span className="text-[11px] text-neutral-400">{item.created_at || "-"}</span>
                        </div>
                        <div className="mt-1 flex flex-wrap items-center justify-between gap-2 text-[11px] text-neutral-500">
                          <span>{t("bonus.delta")}: {deltaLabel}</span>
                          <span>{t("bonus.balance")}: {balanceLabel}</span>
                        </div>
                        {item.order_id ? (
                          <div className="mt-1 text-[11px] text-neutral-400">#{item.order_id}</div>
                        ) : null}
                      </div>
                    );
                  })}
                {!historyLoading && !historyError && history.length === 0 && (
                  <div className="rounded-xl border border-dashed border-neutral-200 bg-neutral-50 px-4 py-6 text-center text-sm text-neutral-500">
                    {t("bonus.historyEmpty")}
                  </div>
                )}
              </div>
            </div>

            <div className="rounded-2xl border border-neutral-200 bg-white p-5 shadow-sm shadow-neutral-200/70">
              <div className="flex items-center justify-between gap-2">
                <h4 className="text-sm font-semibold text-neutral-900">{t("bonus.ordersTitle")}</h4>
                <span className="rounded-full bg-neutral-100 px-2 py-0.5 text-[11px] font-semibold text-neutral-600">
                  {orders.length}
                </span>
              </div>
              <div className="mt-4 space-y-2 overflow-y-auto pr-1" style={{ maxHeight: "360px" }}>
                {ordersLoading && (
                  <div className="rounded-xl border border-dashed border-neutral-200 bg-neutral-50 px-4 py-6 text-center text-sm text-neutral-500">
                    {t("bonus.ordersLoading")}
                  </div>
                )}
                {!ordersLoading && ordersError && (
                  <div className="rounded-xl border border-rose-100 bg-rose-50 px-4 py-6 text-center text-sm text-rose-600">
                    {ordersError}
                  </div>
                )}
                {!ordersLoading &&
                  !ordersError &&
                  orders.map((item) => (
                    <div
                      key={item.id}
                      className="rounded-xl border border-neutral-100 bg-neutral-50 px-4 py-3 text-xs text-neutral-600"
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span className="font-semibold text-neutral-800">#{item.order_id}</span>
                        <span className="text-[11px] text-neutral-400">{item.created_at || "-"}</span>
                      </div>
                      <div className="mt-1 flex flex-wrap items-center gap-2 text-[11px] text-neutral-500">
                        {item.lot_number !== null && item.lot_number !== undefined ? (
                          <span>{t("bonus.orderLot", { number: item.lot_number })}</span>
                        ) : null}
                        {item.rental_minutes ? (
                          <span>{formatMinutesLabel(item.rental_minutes, hoursLabel, minutesLabel)}</span>
                        ) : null}
                        {item.action ? <span>{item.action}</span> : null}
                      </div>
                    </div>
                  ))}
                {!ordersLoading && !ordersError && orders.length === 0 && (
                  <div className="rounded-xl border border-dashed border-neutral-200 bg-neutral-50 px-4 py-6 text-center text-sm text-neutral-500">
                    {t("bonus.ordersEmpty")}
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

export default BonusPage;
