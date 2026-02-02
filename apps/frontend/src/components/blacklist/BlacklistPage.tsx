import React, { useCallback, useEffect, useMemo, useState } from "react";

import { api, BlacklistEntry, BlacklistLog } from "../../services/api";
import { useWorkspace } from "../../context/WorkspaceContext";
import { useI18n } from "../../i18n/useI18n";

type BlacklistPageProps = {
  onToast?: (message: string, isError?: boolean) => void;
};

type ResolvedWorkspace = {
  id: number | null;
  name?: string | null;
};

const BLACKLIST_GRID =
  "40px minmax(180px,1.2fr) minmax(180px,1fr) minmax(220px,1.4fr) minmax(160px,0.9fr) minmax(140px,0.8fr)";

const getStratzUrl = (steamId?: string | null) => {
  const trimmed = (steamId || "").trim();
  if (!trimmed || trimmed.toLowerCase() === "unknown") return null;
  return `https://stratz.com/search/${trimmed}`;
};

const formatDate = (value?: string | null) => {
  if (!value) return "-";
  const dt = new Date(value);
  if (Number.isNaN(dt.getTime())) return value;
  return dt.toLocaleString();
};

const parseAccountDetails = (details?: string | null) => {
  if (!details) return null;
  const loginMatch = details.match(/login=([^;]+)/i);
  const steamMatch = details.match(/steam_id=([^;]+)/i);
  const normalize = (value?: string | null) => {
    if (!value) return null;
    const trimmed = value.trim();
    if (!trimmed || trimmed.toLowerCase() === "unknown") return null;
    return trimmed;
  };
  return {
    login: normalize(loginMatch?.[1] ?? null),
    steamId: normalize(steamMatch?.[1] ?? null),
  };
};

const formatWorkspaceLabel = (
  workspaceId: number | null | undefined,
  workspaces: { id: number; name: string; is_default?: boolean }[],
  workspaceName?: string | null,
) => {
  if (workspaceId && workspaceName) return `${workspaceName} (ID ${workspaceId})`;
  if (workspaceName) return workspaceName;
  if (!workspaceId) return "Глобально";
  const match = workspaces.find((item) => item.id === workspaceId);
  return match?.name ? `${match.name} (ID ${workspaceId})` : `Рабочее пространство ${workspaceId}`;
};

const BlacklistPage: React.FC<BlacklistPageProps> = ({ onToast }) => {
  const { workspaces } = useWorkspace();
  const { tr } = useI18n();
  const isAllWorkspaces = true;
  const workspaceId: number | null = null;

  const [blacklistEntries, setBlacklistEntries] = useState<BlacklistEntry[]>([]);
  const [blacklistQuery, setBlacklistQuery] = useState("");
  const [blacklistLoading, setBlacklistLoading] = useState(false);
  const [blacklistOwner, setBlacklistOwner] = useState("");
  const [blacklistOrderId, setBlacklistOrderId] = useState("");
  const [blacklistReason, setBlacklistReason] = useState("");
  const [blacklistSelected, setBlacklistSelected] = useState<string[]>([]);
  const [blacklistEditingId, setBlacklistEditingId] = useState<string | number | null>(null);
  const [blacklistEditOwner, setBlacklistEditOwner] = useState("");
  const [blacklistEditReason, setBlacklistEditReason] = useState("");
  const [blacklistResolving, setBlacklistResolving] = useState(false);
  const [blacklistLogs, setBlacklistLogs] = useState<BlacklistLog[]>([]);
  const [blacklistLogsLoading, setBlacklistLogsLoading] = useState(false);
  const [resolvedWorkspace, setResolvedWorkspace] = useState<ResolvedWorkspace | null>(null);

  const resolveOrderOwner = useCallback(
    async (orderId: string) => {
      const trimmed = orderId.trim();
      if (!trimmed) {
        onToast?.(tr("Enter an order ID first.", "Сначала введите ID заказа."), true);
        return null;
      }
      setBlacklistResolving(true);
      try {
        const res = await api.resolveOrder(trimmed, workspaceId ?? undefined);
        if (!res?.owner) {
          onToast?.(tr("Buyer not found for this order yet.", "Покупатель по этому заказу пока не найден."), true);
          setResolvedWorkspace(null);
          return null;
        }
        setBlacklistOwner(res.owner);
        const workspaceLabel =
          res.workspace_id || res.workspace_name
            ? formatWorkspaceLabel(res.workspace_id ?? null, workspaces, res.workspace_name)
            : null;
        setResolvedWorkspace({
          id: res.workspace_id ?? null,
          name: res.workspace_name ?? null,
        });
        const ownerLabel = tr("Buyer found: {owner}", "Покупатель найден: {owner}", { owner: res.owner });
        onToast?.(
          workspaceLabel
            ? tr("Buyer found: {owner} (Workspace: {workspace})", "Покупатель найден: {owner} (Пространство: {workspace})", {
                owner: res.owner,
                workspace: workspaceLabel,
              })
            : ownerLabel,
        );
        return res.owner;
      } catch (err) {
        const message =
          (err as { message?: string })?.message || tr("Order lookup failed.", "Поиск заказа не удался.");
        onToast?.(message, true);
        setResolvedWorkspace(null);
        return null;
      } finally {
        setBlacklistResolving(false);
      }
    },
    [workspaceId, onToast, workspaces],
  );

  const loadBlacklist = useCallback(async () => {
    const effectiveWorkspaceId = workspaceId ?? undefined;
    setBlacklistLoading(true);
    try {
      const res = await api.listBlacklist(effectiveWorkspaceId, blacklistQuery.trim() || undefined);
      setBlacklistEntries(res.items || []);
      setBlacklistSelected((prev) => prev.filter((owner) => res.items.some((entry) => entry.owner === owner)));
    } catch (err) {
      const message =
        (err as { message?: string })?.message || tr("Failed to load blacklist.", "Не удалось загрузить чёрный список.");
      onToast?.(message, true);
    } finally {
      setBlacklistLoading(false);
    }
  }, [workspaceId, blacklistQuery, onToast]);

  const loadBlacklistLogs = useCallback(async () => {
    const effectiveWorkspaceId = workspaceId ?? undefined;
    setBlacklistLogsLoading(true);
    try {
      const res = await api.listBlacklistLogs(effectiveWorkspaceId, 200);
      setBlacklistLogs(res.items || []);
    } catch (err) {
      const message =
        (err as { message?: string })?.message ||
        tr("Failed to load blacklist activity.", "Не удалось загрузить активность чёрного списка.");
      onToast?.(message, true);
    } finally {
      setBlacklistLogsLoading(false);
    }
  }, [workspaceId, onToast]);

  useEffect(() => {
    void loadBlacklist();
    void loadBlacklistLogs();
  }, [loadBlacklist, loadBlacklistLogs]);

  const toggleBlacklistSelected = (owner: string) => {
    setBlacklistSelected((prev) =>
      prev.includes(owner) ? prev.filter((item) => item !== owner) : [...prev, owner],
    );
  };

  const toggleBlacklistSelectAll = () => {
    if (!blacklistEntries.length) return;
    setBlacklistSelected((prev) =>
      prev.length === blacklistEntries.length ? [] : blacklistEntries.map((entry) => entry.owner),
    );
  };

  const handleResolveBlacklistOrder = async () => {
    await resolveOrderOwner(blacklistOrderId);
  };

  const handleAddBlacklist = async () => {
    let owner = blacklistOwner.trim();
    const orderId = blacklistOrderId.trim();
    if (!owner && !orderId) {
      onToast?.(tr("Enter a buyer username or order ID.", "Введите имя покупателя или ID заказа."), true);
      return;
    }
    if (!owner && orderId) {
      const resolvedOwner = await resolveOrderOwner(orderId);
      if (!resolvedOwner) return;
      owner = resolvedOwner;
    }
    setBlacklistResolving(true);
    try {
      const entry = await api.createBlacklist(
        { owner, reason: blacklistReason.trim() || null, order_id: orderId || null },
        workspaceId ?? undefined,
      );
      setBlacklistOwner("");
      setBlacklistOrderId("");
      setBlacklistReason("");
      setResolvedWorkspace(null);
      setBlacklistEntries((prev) => [entry, ...prev.filter((item) => item.id !== entry.id)]);
      onToast?.(tr("User added to blacklist.", "Пользователь добавлен в чёрный список."));
      await loadBlacklist();
      await loadBlacklistLogs();
    } catch (err) {
      const message =
        (err as { message?: string })?.message ||
        tr("Failed to add user to blacklist.", "Не удалось добавить пользователя в чёрный список.");
      onToast?.(message, true);
    } finally {
      setBlacklistResolving(false);
    }
  };

  const startEditBlacklist = (entry: BlacklistEntry) => {
    setBlacklistEditingId(entry.id ?? null);
    setBlacklistEditOwner(entry.owner || "");
    setBlacklistEditReason(entry.reason || "");
  };

  const cancelEditBlacklist = () => {
    setBlacklistEditingId(null);
    setBlacklistEditOwner("");
    setBlacklistEditReason("");
  };

  const handleSaveBlacklistEdit = async () => {
    if (blacklistEditingId === null || blacklistEditingId === undefined) return;
    const owner = blacklistEditOwner.trim();
    if (!owner) {
      onToast?.(tr("Owner cannot be empty.", "Владелец не может быть пустым."), true);
      return;
    }
    try {
      const entryStatus =
        blacklistEntries.find((item) => String(item.id) === String(blacklistEditingId))?.status ||
        "confirmed";
      const entry = await api.updateBlacklist(
        Number(blacklistEditingId),
        { owner, reason: blacklistEditReason.trim() || null, status: entryStatus },
        workspaceId ?? undefined,
      );
      onToast?.(tr("Blacklist entry updated.", "Запись чёрного списка обновлена."));
      cancelEditBlacklist();
      setBlacklistEntries((prev) => prev.map((item) => (item.id === entry.id ? entry : item)));
      await loadBlacklistLogs();
    } catch (err) {
      const message =
        (err as { message?: string })?.message ||
        tr("Failed to update blacklist entry.", "Не удалось обновить запись чёрного списка.");
      onToast?.(message, true);
    }
  };

  const handleRemoveSelected = async () => {
    if (!blacklistSelected.length) {
      onToast?.(tr("Select users to unblacklist.", "Выберите пользователей для разблокировки."), true);
      return;
    }
    try {
      await api.removeBlacklist(blacklistSelected, workspaceId ?? undefined);
      onToast?.(tr("Selected users removed from blacklist.", "Выбранные пользователи удалены из чёрного списка."));
      setBlacklistSelected([]);
      await loadBlacklist();
      await loadBlacklistLogs();
    } catch (err) {
      const message =
        (err as { message?: string })?.message ||
        tr("Failed to unblacklist users.", "Не удалось удалить пользователей из чёрного списка.");
      onToast?.(message, true);
    }
  };

  const handleClearBlacklist = async () => {
    if (!blacklistEntries.length) {
      onToast?.(tr("Blacklist is already empty.", "Чёрный список уже пуст."), true);
      return;
    }
    if (!window.confirm(tr("Remove everyone from the blacklist?", "Удалить всех из чёрного списка?"))) return;
    try {
      await api.clearBlacklist(workspaceId ?? undefined);
      onToast?.(tr("Blacklist cleared.", "Чёрный список очищен."));
      setBlacklistSelected([]);
      await loadBlacklist();
      await loadBlacklistLogs();
    } catch (err) {
      const message =
        (err as { message?: string })?.message ||
        tr("Failed to clear blacklist.", "Не удалось очистить чёрный список.");
      onToast?.(message, true);
    }
  };

  const allBlacklistSelected =
    blacklistEntries.length > 0 && blacklistSelected.length === blacklistEntries.length;
  const totalBlacklisted = useMemo(() => blacklistEntries.length, [blacklistEntries]);
  const pendingBlacklisted = useMemo(
    () => blacklistEntries.filter((entry) => (entry.status || "confirmed") === "pending").length,
    [blacklistEntries],
  );

  const handleConfirmBlacklist = async (entry: BlacklistEntry) => {
    if (!entry.id) return;
    try {
      await api.updateBlacklist(
        Number(entry.id),
        { owner: entry.owner, reason: entry.reason || null, status: "confirmed" },
        workspaceId ?? undefined,
      );
      onToast?.(tr("Blacklist confirmed.", "Чёрный список подтверждён."));
      await loadBlacklist();
      await loadBlacklistLogs();
    } catch (err) {
      const message =
        (err as { message?: string })?.message ||
        tr("Failed to confirm blacklist.", "Не удалось подтвердить чёрный список.");
      onToast?.(message, true);
    }
  };

  const handleDeclineBlacklist = async (entry: BlacklistEntry) => {
    if (!entry.owner) return;
    try {
      await api.removeBlacklist([entry.owner], workspaceId ?? undefined);
      onToast?.(tr("Blacklist request declined.", "Заявка на чёрный список отклонена."));
      await loadBlacklist();
      await loadBlacklistLogs();
    } catch (err) {
      const message =
        (err as { message?: string })?.message ||
        tr("Failed to decline blacklist.", "Не удалось отклонить заявку.");
      onToast?.(message, true);
    }
  };

  return (
    <div className="space-y-6">
      <div className="rounded-2xl border border-neutral-200 bg-white p-6 shadow-sm shadow-neutral-200/70">
        <div className="mb-5 flex flex-wrap items-center justify-between gap-4">
          <div>
            <h3 className="text-lg font-semibold text-neutral-900">{tr("Blacklist", "Чёрный список")}</h3>
            <p className="text-sm text-neutral-500">
              {tr(
                "Block buyers from renting and send a penalty payment notice.",
                "Блокируйте аренду и отправляйте уведомление о штрафе.",
              )}
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-xs rounded-full bg-neutral-100 px-3 py-1 font-semibold text-neutral-600">
              {tr("{count} blocked", "Заблокировано: {count}", { count: totalBlacklisted })}
            </span>
            {pendingBlacklisted > 0 && (
              <span className="text-xs rounded-full bg-amber-100 px-3 py-1 font-semibold text-amber-700">
                {tr("{count} pending", "На проверке: {count}", { count: pendingBlacklisted })}
              </span>
            )}
            <button
              onClick={() => loadBlacklist()}
              className="rounded-lg border border-neutral-200 bg-neutral-50 px-3 py-2 text-xs text-neutral-600"
            >
              {tr("Refresh", "Обновить")}
            </button>
          </div>
        </div>
        <div className="grid gap-4 lg:grid-cols-[1.15fr_1fr]">
          <div className="rounded-xl border border-neutral-200 bg-neutral-50 p-4">
            <div className="mb-2 text-sm font-semibold text-neutral-800">{tr("Add to blacklist", "Добавить в чёрный список")}</div>
            {isAllWorkspaces && (
              <div className="mb-3 rounded-lg border border-dashed border-neutral-200 bg-neutral-50 px-3 py-2 text-xs text-neutral-500">
                {tr(
                  "All workspaces + platforms selected - blacklist applies globally.",
                  "Выбраны все рабочие пространства и платформы — чёрный список применяется глобально.",
                )}
              </div>
            )}
            <div className="space-y-3">
              <div className="grid gap-3 md:grid-cols-[1fr_auto]">
                <input
                  value={blacklistOrderId}
                  onChange={(e) => {
                    setBlacklistOrderId(e.target.value);
                    setResolvedWorkspace(null);
                  }}
                  placeholder={tr("Order ID (optional)", "ID заказа (необязательно)")}
                  disabled={blacklistResolving}
                  className="w-full rounded-lg border border-neutral-200 bg-white px-3 py-2 text-sm text-neutral-700 outline-none placeholder:text-neutral-400"
                />
                <button
                  onClick={handleResolveBlacklistOrder}
                  disabled={blacklistResolving}
                  className="rounded-lg border border-neutral-200 bg-white px-3 py-2 text-xs font-semibold text-neutral-700 transition hover:bg-neutral-100 disabled:cursor-not-allowed disabled:text-neutral-400"
                >
                  {tr("Find buyer", "Найти покупателя")}
                </button>
              </div>
              <input
                value={blacklistOwner}
                onChange={(e) => {
                  setBlacklistOwner(e.target.value);
                  if (resolvedWorkspace) setResolvedWorkspace(null);
                }}
                placeholder={tr("Buyer username", "Имя покупателя")}
                className="w-full rounded-lg border border-neutral-200 bg-white px-3 py-2 text-sm text-neutral-700 outline-none placeholder:text-neutral-400"
              />
              {resolvedWorkspace ? (
                <div className="text-xs text-neutral-500">
                  {tr("Order workspace:", "Рабочее пространство заказа:")}{" "}
                  {formatWorkspaceLabel(
                    resolvedWorkspace.id ?? null,
                    workspaces,
                    resolvedWorkspace.name ?? null,
                  )}
                </div>
              ) : null}
              <input
                value={blacklistReason}
                onChange={(e) => setBlacklistReason(e.target.value)}
                placeholder={tr("Reason (optional)", "Причина (необязательно)")}
                className="w-full rounded-lg border border-neutral-200 bg-white px-3 py-2 text-sm text-neutral-700 outline-none placeholder:text-neutral-400"
              />
              <button
                onClick={handleAddBlacklist}
                disabled={blacklistResolving || (!blacklistOwner.trim() && !blacklistOrderId.trim())}
                className="w-full rounded-lg bg-neutral-900 px-4 py-2 text-sm font-semibold text-white transition hover:bg-neutral-800 disabled:cursor-not-allowed disabled:bg-neutral-300"
              >
                {blacklistResolving ? tr("Resolving...", "Поиск...") : tr("Add user", "Добавить пользователя")}
              </button>
            </div>
          </div>
          <div className="rounded-xl border border-neutral-200 bg-neutral-50 p-4">
            <div className="mb-2 text-sm font-semibold text-neutral-800">{tr("Manage", "Управление")}</div>
            <input
              value={blacklistQuery}
              onChange={(e) => setBlacklistQuery(e.target.value)}
              placeholder={tr("Search by buyer", "Поиск по покупателю")}
              type="search"
              className="w-full rounded-lg border border-neutral-200 bg-white px-3 py-2 text-sm text-neutral-700 outline-none placeholder:text-neutral-400"
            />
            <div className="mt-3 flex flex-wrap gap-2">
              <button
                onClick={handleRemoveSelected}
                disabled={!blacklistSelected.length}
                className="rounded-lg border border-neutral-200 bg-white px-3 py-2 text-xs font-semibold text-neutral-700 transition hover:bg-neutral-100 disabled:cursor-not-allowed disabled:text-neutral-400"
              >
                {tr("Unblacklist selected", "Разблокировать выбранных")}
              </button>
              <button
                onClick={handleClearBlacklist}
                disabled={!blacklistEntries.length}
                className="rounded-lg border border-neutral-200 bg-white px-3 py-2 text-xs font-semibold text-neutral-700 transition hover:bg-neutral-100 disabled:cursor-not-allowed disabled:text-neutral-400"
              >
                {tr("Unblacklist all", "Разблокировать всех")}
              </button>
            </div>
          </div>
        </div>
        <div className="mt-5 rounded-2xl border border-neutral-200 bg-white">
          <div className="overflow-x-auto">
            <div className="min-w-[680px]">
              <div
                className="grid gap-3 px-6 py-3 text-xs font-semibold text-neutral-500"
                style={{ gridTemplateColumns: BLACKLIST_GRID }}
              >
                <label className="flex items-center justify-center">
                  <input
                    type="checkbox"
                    checked={allBlacklistSelected}
                    onChange={toggleBlacklistSelectAll}
                    className="h-4 w-4 rounded border-neutral-300 text-neutral-900"
                  />
                </label>
                <span>{tr("Buyer", "Покупатель")}</span>
                <span>{tr("Steam account", "Steam аккаунт")}</span>
                <span>{tr("Reason", "Причина")}</span>
                <span>{tr("Added", "Добавлено")}</span>
                <span>{tr("Actions", "Действия")}</span>
              </div>
              <div className="divide-y divide-neutral-100 overflow-x-hidden">
                {blacklistLoading ? (
                  <div className="px-6 py-6 text-center text-sm text-neutral-500">
                    {tr("Loading blacklist...", "Загружаем чёрный список...")}
                  </div>
                ) : blacklistEntries.length ? (
                  blacklistEntries.map((entry, idx) => {
                    const isSelected = blacklistSelected.includes(entry.owner);
                    const isEditing =
                      blacklistEditingId !== null &&
                      entry.id !== undefined &&
                      String(blacklistEditingId) === String(entry.id);
                    const accountDetails = parseAccountDetails(entry.details);
                    return (
                      <div
                        key={entry.id ?? entry.owner ?? idx}
                        className={`grid items-center gap-3 px-6 py-3 text-sm ${
                          isSelected ? "bg-neutral-50" : "bg-white"
                        }`}
                        style={{ gridTemplateColumns: BLACKLIST_GRID }}
                      >
                        <label className="flex items-center justify-center">
                          <input
                            type="checkbox"
                            checked={isSelected}
                            onChange={() => toggleBlacklistSelected(entry.owner)}
                            className="h-4 w-4 rounded border-neutral-300 text-neutral-900"
                          />
                        </label>
                        {isEditing ? (
                          <input
                            value={blacklistEditOwner}
                            onChange={(e) => setBlacklistEditOwner(e.target.value)}
                            className="w-full rounded-lg border border-neutral-200 bg-white px-3 py-2 text-sm text-neutral-700 outline-none"
                          />
                        ) : (
                          <div className="min-w-0">
                            <div className="truncate font-semibold text-neutral-900">{entry.owner}</div>
                            {(entry.status || "confirmed") === "pending" && (
                              <span className="mt-1 inline-flex items-center rounded-full bg-amber-100 px-2 py-0.5 text-[10px] font-semibold text-amber-700">
                                {tr("Pending review", "На проверке")}
                              </span>
                            )}
                            {accountDetails?.login ? (
                              <div className="mt-1 text-xs text-neutral-500">
                                {tr("Account login:", "Логин аккаунта:")}{" "}
                                {getStratzUrl(accountDetails.steamId) ? (
                                  <a
                                    href={getStratzUrl(accountDetails.steamId)!}
                                    target="_blank"
                                    rel="noreferrer"
                                    className="font-semibold text-blue-600 hover:underline"
                                  >
                                    {accountDetails.login}
                                  </a>
                                ) : (
                                  <span className="font-semibold text-neutral-700">{accountDetails.login}</span>
                                )}
                              </div>
                            ) : null}
                            {entry.details ? (
                              <div className="mt-1 truncate text-xs text-neutral-400">{entry.details}</div>
                            ) : null}
                            {isAllWorkspaces && (
                              <div className="text-xs text-neutral-400">
                                {formatWorkspaceLabel(entry.workspace_id ?? null, workspaces)}
                              </div>
                            )}
                          </div>
                        )}
                        <div className="min-w-0">
                          {accountDetails?.login ? (
                            getStratzUrl(accountDetails.steamId) ? (
                              <a
                                href={getStratzUrl(accountDetails.steamId)!}
                                target="_blank"
                                rel="noreferrer"
                                className="truncate font-semibold text-blue-600 hover:underline"
                              >
                                {accountDetails.login}
                              </a>
                            ) : (
                              <span className="truncate font-semibold text-neutral-700">{accountDetails.login}</span>
                            )
                          ) : (
                            <span className="text-neutral-400">-</span>
                          )}
                        </div>
                        {isEditing ? (
                          <input
                            value={blacklistEditReason}
                            onChange={(e) => setBlacklistEditReason(e.target.value)}
                            placeholder={tr("Reason (optional)", "Причина (необязательно)")}
                            className="w-full rounded-lg border border-neutral-200 bg-white px-3 py-2 text-sm text-neutral-700 outline-none"
                          />
                        ) : (
                          <span className="min-w-0 truncate text-neutral-600">{entry.reason || "-"}</span>
                        )}
                        <span className="text-xs text-neutral-500">{formatDate(entry.created_at)}</span>
                        <div className="flex items-center gap-2">
                          {isEditing ? (
                            <>
                              <button
                                onClick={handleSaveBlacklistEdit}
                                className="rounded-lg bg-neutral-900 px-3 py-1 text-xs font-semibold text-white"
                              >
                                {tr("Save", "Сохранить")}
                              </button>
                              <button
                                onClick={cancelEditBlacklist}
                                className="rounded-lg border border-neutral-200 px-3 py-1 text-xs font-semibold text-neutral-600"
                              >
                                {tr("Cancel", "Отмена")}
                              </button>
                            </>
                          ) : (
                            <>
                              {(entry.status || "confirmed") === "pending" ? (
                                <>
                                  <button
                                    onClick={() => handleConfirmBlacklist(entry)}
                                    className="rounded-lg bg-neutral-900 px-3 py-1 text-xs font-semibold text-white"
                                  >
                                    {tr("Confirm", "Подтвердить")}
                                  </button>
                                  <button
                                    onClick={() => handleDeclineBlacklist(entry)}
                                    className="rounded-lg border border-neutral-200 px-3 py-1 text-xs font-semibold text-neutral-600"
                                  >
                                    {tr("Decline", "Отклонить")}
                                  </button>
                                </>
                              ) : (
                                <button
                                  onClick={() => startEditBlacklist(entry)}
                                  className="rounded-lg border border-neutral-200 px-3 py-1 text-xs font-semibold text-neutral-600"
                                >
                                  {tr("Edit", "Редактировать")}
                                </button>
                              )}
                            </>
                          )}
                        </div>
                      </div>
                    );
                  })
                ) : (
                  <div className="px-6 py-6 text-center text-sm text-neutral-500">
                    {tr("Blacklist is empty.", "Чёрный список пуст.")}
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
        <div className="mt-5 rounded-2xl border border-neutral-200 bg-white p-4">
          <div className="mb-3 flex items-center justify-between">
            <div>
              <div className="text-sm font-semibold text-neutral-900">{tr("Activity", "Активность")}</div>
              <div className="text-xs text-neutral-500">{tr("Latest blacklist / unblacklist events.", "Последние события блокировок и разблокировок.")}</div>
            </div>
            <button
              onClick={() => loadBlacklistLogs()}
              disabled={blacklistLogsLoading}
              className="rounded-lg border border-neutral-200 bg-white px-3 py-2 text-xs font-semibold text-neutral-700 transition hover:bg-neutral-100 disabled:cursor-not-allowed disabled:text-neutral-400"
            >
              {tr("Refresh", "Обновить")}
            </button>
          </div>
          {blacklistLogsLoading ? (
            <div className="py-4 text-sm text-neutral-500">{tr("Loading activity...", "Загружаем активность...")}</div>
          ) : blacklistLogs.length === 0 ? (
            <div className="py-4 text-sm text-neutral-500">{tr("No activity yet.", "Пока нет активности.")}</div>
          ) : (
            <div className="space-y-2">
              {blacklistLogs.map((log, idx) => {
                const action = (log.action || "").toLowerCase();
                const badge =
                  action === "add"
                    ? { label: tr("Added", "Добавлено"), className: "bg-blue-100 text-blue-700" }
                    : action.includes("unblacklist")
                      ? { label: tr("Unblocked", "Разблокировано"), className: "bg-green-100 text-green-700" }
                      : action === "blocked_order"
                        ? { label: tr("Blocked order", "Заблокирован заказ"), className: "bg-red-100 text-red-700" }
                        : action === "blacklist_comp"
                          ? { label: tr("Payment", "Платёж"), className: "bg-amber-100 text-amber-700" }
                          : action === "update"
                            ? { label: tr("Updated", "Обновлено"), className: "bg-neutral-100 text-neutral-700" }
                            : action === "clear_all"
                              ? { label: tr("Cleared", "Очищено"), className: "bg-neutral-100 text-neutral-700" }
                              : { label: action || tr("Event", "Событие"), className: "bg-neutral-100 text-neutral-700" };
                return (
                  <div
                    key={`${log.owner}-${log.action}-${idx}`}
                    className="flex flex-wrap items-center gap-3 rounded-xl border border-neutral-100 bg-neutral-50 px-3 py-2"
                  >
                    <span
                      className={`inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-semibold ${badge.className}`}
                    >
                      {badge.label}
                    </span>
                    <span className="text-sm font-semibold text-neutral-900">{log.owner}</span>
                    {log.reason && <span className="text-xs text-neutral-600">- {log.reason}</span>}
                    {log.details && <span className="text-xs text-neutral-500">- {log.details}</span>}
                    <span className="ml-auto text-[11px] text-neutral-500">{formatDate(log.created_at)}</span>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default BlacklistPage;
