import React, { useEffect, useMemo, useState } from "react";
import { motion } from "framer-motion";

import { api, AccountItem } from "../../services/api";
import { useWorkspace } from "../../context/WorkspaceContext";

type AccountRow = {
  id: number;
  name: string;
  login: string;
  password: string;
  steamId: string;
  lotUrl?: string | null;
  lotNumber?: number | null;
  mmr: number | string;
  workspaceId?: number | null;
  workspaceName?: string | null;
  lastRentedWorkspaceId?: number | null;
  lastRentedWorkspaceName?: string | null;
  owner?: string | null;
  rentalStart?: string | null;
  rentalDuration?: number;
  rentalDurationMinutes?: number | null;
  accountFrozen?: boolean;
  rentalFrozen?: boolean;
  lowPriority?: boolean;
};

const INVENTORY_GRID =
  "minmax(0,0.45fr) minmax(0,1.4fr) minmax(0,1.1fr) minmax(0,1.1fr) minmax(0,1.25fr) minmax(0,0.6fr) minmax(0,0.7fr)";
const EASE: [number, number, number, number] = [0.22, 1, 0.36, 1];

const mapAccount = (item: AccountItem): AccountRow => ({
  id: item.id,
  name: item.account_name,
  login: item.login,
  password: item.password || "",
  steamId: item.steam_id ?? "",
  lotUrl: item.lot_url ?? null,
  lotNumber: item.lot_number ?? null,
  mmr: item.mmr ?? "-",
  workspaceId: item.workspace_id ?? null,
  workspaceName: item.workspace_name ?? null,
  lastRentedWorkspaceId: item.last_rented_workspace_id ?? null,
  lastRentedWorkspaceName: item.last_rented_workspace_name ?? null,
  owner: item.owner ?? null,
  rentalStart: item.rental_start ?? null,
  rentalДлительность: item.rental_duration ?? 0,
  rentalDurationMinutes: item.rental_duration_minutes ?? null,
  accountFrozen: !!item.account_frozen,
  rentalFrozen: !!item.rental_frozen,
  lowPriority: !!item.low_priority,
});

type ИнвентарьPageProps = {
  onToast?: (message: string, isError?: boolean) => void;
};

const formatDuration = (minutesTotal: number | null | undefined) => {
  if (!minutesTotal && minutesTotal !== 0) return "-";
  const minutes = Math.max(0, Math.floor(minutesTotal));
  const hours = Math.floor(minutes / 60);
  const rem = minutes % 60;
  return `${hours}ч ${rem}м`;
};

const stratzUrl = (steamId?: string | null) => {
  const trimmed = steamId?.trim();
  if (!trimmed) return null;
  return `https://stratz.com/search/${trimmed}`;
};

const ИнвентарьPage: React.FC<ИнвентарьPageProps> = ({ onToast }) => {
  const [accounts, setAccounts] = useState<AccountRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [assignOwner, setAssignOwner] = useState("");
  const [accountEditName, setAccountEditName] = useState("");
  const [accountEditLogin, setAccountEditLogin] = useState("");
  const [accountEditPassword, setAccountEditPassword] = useState("");
  const [accountEditMmr, setAccountEditMmr] = useState("");
  const [accountEditWorkspaceId, setAccountEditWorkspaceId] = useState<number | null>(null);
  const [accountActionBusy, setAccountActionBusy] = useState(false);
  const [accountControlBusy, setAccountControlBusy] = useState(false);
  const [statusFilter, setStatusFilter] = useState("all");
  const [mmrMin, setMmrMin] = useState("");
  const [mmrMax, setMmrMax] = useState("");
  const { workspaces } = useWorkspace();

  const resolveWorkspaceName = (workspaceName?: string | null, workspaceId?: number | null) => {
    if (workspaceName) return workspaceName;
    if (workspaceId) {
      const match = workspaces.find((item) => item.id === workspaceId);
      if (match?.name) return match.name;
    }
    const fallback = workspaces.find((item) => item.is_default);
    if (fallback?.name) return fallback.name;
    if (workspaceId) return `Рабочее пространство ${workspaceId}`;
    return "Рабочее пространство";
  };

  const formatWorkspaceLabel = (workspaceName?: string | null, workspaceId?: number | null) => {
    const label = resolveWorkspaceName(workspaceName, workspaceId);
    return workspaceId ? `${label} (ID ${workspaceId})` : label;
  };

  const selectedAccount = useMemo(
    () => accounts.find((acc) => acc.id === selectedId) ?? null,
    [accounts, selectedId],
  );

  const getAccountStatus = (acc: AccountRow) => {
    if (acc.lowPriority) return { key: "low_priority", label: "Низкий приоритет" };
    if (acc.accountFrozen) return { key: "frozen", label: "Заморожено" };
    if (acc.owner) return { key: "rented", label: "В аренде" };
    return { key: "available", label: "Доступен" };
  };

  const statusCounts = useMemo(() => {
    const base = {
      all: accounts.length,
      available: 0,
      rented: 0,
      frozen: 0,
      low_priority: 0,
    };
    return accounts.reduce((acc, item) => {
      const status = getAccountStatus(item).key as keyof typeof base;
      acc[status] += 1;
      return acc;
    }, base);
  }, [accounts]);

  const filteredAccounts = useMemo(() => {
    const min = mmrMin.trim() === "" ? null : Number(mmrMin);
    const max = mmrMax.trim() === "" ? null : Number(mmrMax);
    return accounts.filter((acc) => {
      const status = getAccountStatus(acc).key;
      if (statusFilter !== "all" && status !== statusFilter) return false;
      const mmrValue = typeof acc.mmr === "number" ? acc.mmr : Number(acc.mmr);
      if (Number.isFinite(min) && (Number.isNaN(mmrValue) || mmrValue < min)) return false;
      if (Number.isFinite(max) && (Number.isNaN(mmrValue) || mmrValue > max)) return false;
      return true;
    });
  }, [accounts, mmrMin, mmrMax, statusFilter]);

  const statusOptions = [
    { key: "all", label: "Все" },
    { key: "available", label: "Доступные" },
    { key: "rented", label: "В аренде" },
    { key: "frozen", label: "Замороженные" },
    { key: "low_priority", label: "Низкий приоритет" },
  ];

  const workspaceOptions = useMemo(() => {
    const baseOptions = workspaces.map((workspace) => ({
      id: workspace.id,
      label: formatWorkspaceLabel(workspace.name, workspace.id),
    }));
    if (
      accountEditWorkspaceId !== null &&
      accountEditWorkspaceId !== undefined &&
      !baseOptions.some((option) => option.id === accountEditWorkspaceId)
    ) {
      baseOptions.push({
        id: accountEditWorkspaceId,
        label: formatWorkspaceLabel(selectedAccount?.workspaceName, accountEditWorkspaceId),
      });
    }
    return baseOptions;
  }, [workspaces, accountEditWorkspaceId, selectedAccount?.workspaceName]);

  const loadAccounts = async () => {
    setLoading(true);
    try {
      const res = await api.listAccounts();
      setAccounts((res.items || []).map(mapAccount));
      setError(null);
    } catch (err) {
      setError((err as { message?: string })?.message || "Не удалось загрузить аккаунты.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadAccounts();
  }, []);

  useEffect(() => {
    if (selectedId && !accounts.some((acc) => acc.id === selectedId)) {
      setSelectedId(null);
    }
  }, [accounts, selectedId]);

  useEffect(() => {
    if (!selectedAccount) {
      setAssignOwner("");
      setAccountEditName("");
      setAccountEditLogin("");
      setAccountEditPassword("");
      setAccountEditMmr("");
      setAccountEditWorkspaceId(null);
      return;
    }
    setAccountEditName(selectedAccount.name || "");
    setAccountEditLogin(selectedAccount.login || "");
    setAccountEditPassword(selectedAccount.password || "");
    setAccountEditMmr(selectedAccount.mmr !== "-" && selectedAccount.mmr !== undefined ? String(selectedAccount.mmr) : "");
    setAccountEditWorkspaceId(selectedAccount.workspaceId ?? null);
  }, [selectedAccount]);

  const emptyMessage = loading
    ? "Загружаем аккаунты..."
    : error
      ? `Не удалось загрузить аккаунты: ${error}`
      : "Аккаунты ещё не загружены.";

  const handleAssignAccount = async () => {
    if (!selectedAccount) {
      onToast?.("Сначала выберите аккаунт.", true);
      return;
    }
    if (accountActionBusy) return;
    if (selectedAccount.lowPriority) {
      onToast?.("Снимите низкий приоритет перед назначением покупателя.", true);
      return;
    }
    if (selectedAccount.accountFrozen) {
      onToast?.("Разморозьте аккаунт перед назначением покупателя.", true);
      return;
    }
    if (selectedAccount.owner) {
      onToast?.("Release the account first.", true);
      return;
    }
    const owner = assignOwner.trim();
    if (!owner) {
      onToast?.("Enter a buyer username.", true);
      return;
    }
    setAccountActionBusy(true);
    try {
      const workspaceId =
        selectedAccount.workspaceId ?? selectedAccount.lastRentedWorkspaceId ?? undefined;
      await api.assignAccount(selectedAccount.id, owner, workspaceId);
      onToast?.("Аренда назначена.");
      setAssignOwner("");
      await loadAccounts();
    } catch (err) {
      const message = (err as { message?: string })?.message || "Не удалось назначить аренду.";
      onToast?.(message, true);
    } finally {
      setAccountActionBusy(false);
    }
  };

  const handleUpdateAccount = async () => {
    if (!selectedAccount) {
      onToast?.("Сначала выберите аккаунт.", true);
      return;
    }
    if (accountActionBusy) return;
    const payload: Record<string, unknown> = {};
    const name = accountEditName.trim();
    const login = accountEditLogin.trim();
    const password = accountEditPassword.trim();
    const mmrRaw = accountEditMmr.trim();

    if (name && name !== (selectedAccount.name || "")) payload.account_name = name;
    if (login && login !== (selectedAccount.login || "")) payload.login = login;
    if (password && password !== (selectedAccount.password || "")) payload.password = password;
    if (mmrRaw) {
      const mmr = Number(mmrRaw);
      if (!Number.isFinite(mmr) || mmr < 0) {
        onToast?.("ММР должен быть 0 или выше.", true);
        return;
      }
      if (String(mmr) !== String(selectedAccount.mmr ?? "")) payload.mmr = mmr;
    }
    if (
      accountEditWorkspaceId !== null &&
      accountEditWorkspaceId !== (selectedAccount.workspaceId ?? null)
    ) {
      payload.workspace_id = accountEditWorkspaceId;
    }

    if (!Object.keys(payload).length) {
      onToast?.("Нет изменений для сохранения.", true);
      return;
    }

    setAccountActionBusy(true);
    try {
      const workspaceId =
        selectedAccount.workspaceId ?? selectedAccount.lastRentedWorkspaceId ?? undefined;
      await api.updateAccount(selectedAccount.id, payload, workspaceId);
      onToast?.("Account updated.");
      await loadAccounts();
    } catch (err) {
      const message = (err as { message?: string })?.message || "Не удалось обновить аккаунт.";
      onToast?.(message, true);
    } finally {
      setAccountActionBusy(false);
    }
  };

  const handleToggleAccountFreeze = async (nextFrozen: boolean) => {
    if (!selectedAccount) {
      onToast?.("Сначала выберите аккаунт.", true);
      return;
    }
    if (accountControlBusy) return;
    setAccountControlBusy(true);
    try {
      const workspaceId =
        selectedAccount.workspaceId ?? selectedAccount.lastRentedWorkspaceId ?? undefined;
      await api.freezeAccount(selectedAccount.id, nextFrozen, workspaceId);
      onToast?.(nextFrozen ? "Аккаунт заморожен." : "Аккаунт разморожен.");
      await loadAccounts();
    } catch (err) {
      const message = (err as { message?: string })?.message || "Не удалось обновить статус заморозки.";
      onToast?.(message, true);
    } finally {
      setAccountControlBusy(false);
    }
  };

  const handleToggleLowPriority = async (nextLowPriority: boolean) => {
    if (!selectedAccount) {
      onToast?.("Сначала выберите аккаунт.", true);
      return;
    }
    if (accountControlBusy) return;
    setAccountControlBusy(true);
    try {
      const workspaceId =
        selectedAccount.workspaceId ?? selectedAccount.lastRentedWorkspaceId ?? undefined;
      await api.setLowPriority(selectedAccount.id, nextLowPriority, workspaceId);
      onToast?.(nextLowPriority ? "Marked as low priority." : "Низкий приоритет removed.");
      await loadAccounts();
    } catch (err) {
      const message = (err as { message?: string })?.message || "Не удалось обновить низкий приоритет.";
      onToast?.(message, true);
    } finally {
      setAccountControlBusy(false);
    }
  };

  const handleDeleteAccount = async () => {
    if (!selectedAccount) {
      onToast?.("Сначала выберите аккаунт.", true);
      return;
    }
    if (accountControlBusy) return;
    if (!window.confirm(`Удалить ${selectedAccount.name}?`)) return;
    setAccountControlBusy(true);
    try {
      const workspaceId =
        selectedAccount.workspaceId ?? selectedAccount.lastRentedWorkspaceId ?? undefined;
      await api.deleteAccount(selectedAccount.id, workspaceId);
      onToast?.("Account deleted.");
      await loadAccounts();
    } catch (err) {
      const message = (err as { message?: string })?.message || "Не удалось удалить аккаунт.";
      onToast?.(message, true);
    } finally {
      setAccountControlBusy(false);
    }
  };

  const handleSteamDeauthorize = async () => {
    if (!selectedAccount) {
      onToast?.("Сначала выберите аккаунт.", true);
      return;
    }
    if (accountControlBusy) return;
    if (!window.confirm(`Деавторизовать Steam для ${selectedAccount.name}?`)) return;
    setAccountControlBusy(true);
    try {
      const workspaceId =
        selectedAccount.workspaceId ?? selectedAccount.lastRentedWorkspaceId ?? undefined;
      await api.deauthorizeSteam(selectedAccount.id, workspaceId);
      onToast?.("Steam-сессии деавторизованы.");
    } catch (err) {
      const message = (err as { message?: string })?.message || "Не удалось деавторизовать Steam.";
      onToast?.(message, true);
    } finally {
      setAccountControlBusy(false);
    }
  };

  const renderAccountActionsPanel = (title = "Account actions") => {
    return (
      <div className="rounded-2xl border border-neutral-200 bg-white p-6 shadow-sm shadow-neutral-200/70">
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-lg font-semibold text-neutral-900">{title}</h3>
          <span className="text-xs text-neutral-500">{selectedAccount ? "Готово" : "Выберите аккаунт"}</span>
        </div>
        {selectedAccount ? (
          (() => {
            const rented = !!selectedAccount.owner;
            const frozen = !!selectedAccount.accountFrozen;
            const lowPriority = !!selectedAccount.lowPriority;
            const stateLabel = lowPriority ? "Низкий приоритет" : frozen ? "Заморожено" : rented ? "В аренде" : "Доступен";
            const stateClass = lowPriority
              ? "bg-rose-50 text-rose-600"
              : frozen
                ? "bg-slate-100 text-slate-700"
                : rented
                  ? "bg-amber-50 text-amber-700"
                  : "bg-emerald-50 text-emerald-600";
            const lotLinked = selectedAccount.lotNumber !== null && selectedAccount.lotNumber !== undefined;
            const lotLabel = lotLinked ? "Лот: привязан" : "Лот: не привязан";
            const lotClass = lotLinked ? "bg-emerald-50 text-emerald-700" : "bg-neutral-100 text-neutral-500";
            const lotUrlLabel = selectedAccount.lotUrl || "-";
            const lotNumberLabel = lotLinked ? `#${selectedAccount.lotNumber}` : "-";
            const ownerLabel = selectedAccount.owner ? String(selectedAccount.owner) : "-";
            const totalMinutes =
              selectedAccount.rentalDurationMinutes ??
              (selectedAccount.rentalDuration ? selectedAccount.rentalDuration * 60 : null);
            const hoursLabel = formatDuration(totalMinutes);
            const canAssign = !selectedAccount.owner && !frozen && !lowPriority;
            const editMmrRaw = accountEditMmr.trim();
            const editMmrValue = editMmrRaw ? Number(editMmrRaw) : null;
            const editMmrValid = editMmrRaw === "" || (Number.isFinite(editMmrValue) && editMmrValue >= 0);
            const nameChanged = accountEditName.trim() && accountEditName.trim() !== (selectedAccount.name || "");
            const loginChanged = accountEditLogin.trim() && accountEditLogin.trim() !== (selectedAccount.login || "");
            const passwordChanged = accountEditPassword.trim() && accountEditPassword.trim() !== (selectedAccount.password || "");
            const mmrChanged =
              editMmrRaw &&
              Number.isFinite(editMmrValue) &&
              String(editMmrValue) !== String(selectedAccount.mmr ?? "");
            const workspaceChanged =
              accountEditWorkspaceId !== null &&
              accountEditWorkspaceId !== (selectedAccount.workspaceId ?? null);
            const hasChanges = nameChanged || loginChanged || passwordChanged || mmrChanged || workspaceChanged;
            return (
              <div className="space-y-4">
                <div className="rounded-xl border border-neutral-200 bg-neutral-50 p-4">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <div className="text-xs font-semibold uppercase tracking-wide text-neutral-500">
                        Выбранный аккаунт
                      </div>
                      <div className="mt-1 text-sm font-semibold text-neutral-900">
                        {selectedAccount.name || "Account"}
                      </div>
                    </div>
                    <span className={`rounded-full px-3 py-1 text-xs font-semibold ${stateClass}`}>{stateLabel}</span>
                  </div>
                  <div className="mt-3 grid gap-1 text-xs text-neutral-600">
                    <span>
                      Login:{" "}
                      {stratzUrl(selectedAccount.steamId) ? (
                        <a
                          href={stratzUrl(selectedAccount.steamId)!}
                          target="_blank"
                          rel="noreferrer"
                          className="text-blue-600 underline"
                        >
                          {selectedAccount.login || selectedAccount.steamId || "-"}
                        </a>
                      ) : (
                        selectedAccount.login || "-"
                      )}
                    </span>
                    <span>Steam ID: {selectedAccount.steamId || "-"}</span>
                    <span>Покупатель: {ownerLabel}</span>
                    <span className="flex flex-wrap items-center gap-2">
                      <span className={`inline-flex rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${lotClass}`}>
                        {lotLabel}
                      </span>
                      <span className="text-xs text-neutral-500">
                        Лот: {lotNumberLabel}{" "}
                        {selectedAccount.lotUrl ? (
                          <a
                            href={selectedAccount.lotUrl}
                            target="_blank"
                            rel="noreferrer"
                            className="font-semibold text-blue-600 underline"
                          >
                            {lotUrlLabel}
                          </a>
                        ) : (
                          lotUrlLabel
                        )}
                      </span>
                    </span>
                    <span>Основное рабочее пространство: {formatWorkspaceLabel(selectedAccount.workspaceName, selectedAccount.workspaceId)}</span>
                    <span>
                      Last rented:{" "}
                      {selectedAccount.lastRentedWorkspaceId
                        ? formatWorkspaceLabel(
                            selectedAccount.lastRentedWorkspaceName,
                            selectedAccount.lastRentedWorkspaceId,
                          )
                        : "-"}
                    </span>
                    <span>Начало аренды: {selectedAccount.rentalStart || "-"}</span>
                    <span>Длительность: {hoursLabel}</span>
                  </div>
                </div>
                <div className="rounded-xl border border-neutral-200 bg-neutral-50 p-4">
                  <div className="mb-2 text-sm font-semibold text-neutral-800">Назначить аренду</div>
                  <p className="text-xs text-neutral-500">Отсчёт начинается после запроса кода покупателем.</p>
                  <div className="mt-3 space-y-3">
                    <input
                      value={assignOwner}
                      onChange={(e) => setAssignOwner(e.target.value)}
                      placeholder="Buyer username"
                      className="w-full rounded-lg border border-neutral-200 bg-white px-3 py-2 text-sm text-neutral-700 outline-none placeholder:text-neutral-400"
                    />
                    <button
                      onClick={handleAssignAccount}
                      disabled={accountActionBusy || !assignOwner.trim() || !canAssign}
                      className="w-full rounded-lg bg-neutral-900 px-4 py-2 text-sm font-semibold text-white transition hover:bg-neutral-800 disabled:cursor-not-allowed disabled:bg-neutral-300"
                    >
                      Назначить аренду
                    </button>
                    {!canAssign && (
                      <div className="text-xs text-neutral-500">
                        {lowPriority
                          ? "Снимите низкий приоритет перед назначением покупателя."
                          : frozen
                            ? "Разморозьте аккаунт перед назначением покупателя."
                            : "Release the account first."}
                      </div>
                    )}
                  </div>
                </div>
                <div className="rounded-xl border border-neutral-200 bg-neutral-50 p-4">
                  <div className="mb-2 text-sm font-semibold text-neutral-800">Обновить аккаунт</div>
                  <div className="grid gap-3">
                    <input
                      value={accountEditName}
                      onChange={(e) => setAccountEditName(e.target.value)}
                      placeholder="Account name"
                      className="w-full rounded-lg border border-neutral-200 bg-white px-3 py-2 text-sm text-neutral-700 outline-none placeholder:text-neutral-400"
                    />
                    <div className="grid gap-3 md:grid-cols-2">
                      <input
                        value={accountEditLogin}
                        onChange={(e) => setAccountEditLogin(e.target.value)}
                        placeholder="Логин"
                        className="w-full rounded-lg border border-neutral-200 bg-white px-3 py-2 text-sm text-neutral-700 outline-none placeholder:text-neutral-400"
                      />
                      <input
                        value={accountEditPassword}
                        onChange={(e) => setAccountEditPassword(e.target.value)}
                        placeholder="Пароль"
                        className="w-full rounded-lg border border-neutral-200 bg-white px-3 py-2 text-sm text-neutral-700 outline-none placeholder:text-neutral-400"
                      />
                    </div>
                    <div className="space-y-1">
                      <label className="text-xs font-semibold uppercase tracking-wide text-neutral-500">Рабочее пространство</label>
                      <select
                        value={accountEditWorkspaceId ?? ""}
                        onChange={(event) => {
                          const value = event.target.value;
                          setAccountEditWorkspaceId(value ? Number(value) : null);
                        }}
                        className="w-full rounded-lg border border-neutral-200 bg-white px-3 py-2 text-sm text-neutral-700 outline-none"
                      >
                        <option value="">Выберите пространство</option>
                        {workspaceOptions.map((workspace) => (
                          <option key={workspace.id} value={workspace.id}>
                            {workspace.label}
                          </option>
                        ))}
                      </select>
                    </div>
                    <input
                      value={accountEditMmr}
                      onChange={(e) => setAccountEditMmr(e.target.value)}
                      placeholder="MMR"
                      type="number"
                      min="0"
                      className="w-full rounded-lg border border-neutral-200 bg-white px-3 py-2 text-sm text-neutral-700 outline-none placeholder:text-neutral-400"
                    />
                  </div>
                  {!editMmrValid && (
                    <div className="mt-2 text-xs text-rose-500">ММР должен быть 0 или выше.</div>
                  )}
                  <button
                    onClick={handleUpdateAccount}
                    disabled={accountActionBusy || !hasChanges || !editMmrValid}
                    className="mt-3 w-full rounded-lg bg-neutral-900 px-4 py-2 text-sm font-semibold text-white transition hover:bg-neutral-800 disabled:cursor-not-allowed disabled:bg-neutral-300"
                  >
                    Сохранить изменения
                  </button>
                </div>
              </div>
            );
          })()
        ) : (
          <div className="rounded-xl border border-dashed border-neutral-200 bg-neutral-50 px-4 py-6 text-center text-sm text-neutral-500">
            Выберите аккаунт, чтобы открыть действия.
          </div>
        )}
      </div>
    );
  };

  const renderИнвентарьActionsPanel = () => {
    const frozen = !!selectedAccount?.accountFrozen;
    const lowPriority = !!selectedAccount?.lowPriority;
    return (
      <div className="rounded-2xl border border-neutral-200 bg-white p-6 shadow-sm shadow-neutral-200/70">
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-lg font-semibold text-neutral-900">Управление аккаунтом</h3>
          <span className="text-xs text-neutral-500">{selectedAccount ? "Готово" : "Выберите аккаунт"}</span>
        </div>
        {selectedAccount ? (
          <div className="space-y-4">
            <div className="rounded-xl border border-neutral-200 bg-neutral-50 p-4">
              <div className="mb-2 text-sm font-semibold text-neutral-800">Заморозить аккаунт</div>
              <p className="text-xs text-neutral-500">
                Frozen accounts are hidden from available slots until you unfreeze them.
              </p>
              <button
                onClick={() => handleToggleAccountFreeze(!frozen)}
                disabled={accountControlBusy}
                className={`mt-3 w-full rounded-lg px-4 py-2 text-sm font-semibold transition disabled:cursor-not-allowed disabled:opacity-60 ${
                  frozen
                    ? "border border-emerald-200 bg-emerald-50 text-emerald-700 hover:bg-emerald-100"
                    : "border border-rose-200 bg-rose-50 text-rose-700 hover:bg-rose-100"
                }`}
              >
                {frozen ? "Разморозить аккаунт" : "Заморозить аккаунт"}
              </button>
            </div>
            <div className="rounded-xl border border-neutral-200 bg-neutral-50 p-4">
              <div className="mb-2 text-sm font-semibold text-neutral-800">Низкий приоритет</div>
              <p className="text-xs text-neutral-500">
                Аккаунты с низким приоритетом исключены из автоназначения и списков стока до восстановления.
              </p>
              <button
                onClick={() => handleToggleLowPriority(!lowPriority)}
                disabled={accountControlBusy}
                className={`mt-3 w-full rounded-lg px-4 py-2 text-sm font-semibold transition disabled:cursor-not-allowed disabled:opacity-60 ${
                  lowPriority
                    ? "border border-emerald-200 bg-emerald-50 text-emerald-700 hover:bg-emerald-100"
                    : "border border-rose-200 bg-rose-50 text-rose-700 hover:bg-rose-100"
                }`}
              >
                {lowPriority ? "Снять низкий приоритет" : "Пометить низкий приоритет"}
              </button>
            </div>
            <div className="rounded-xl border border-neutral-200 bg-neutral-50 p-4">
              <div className="mb-2 text-sm font-semibold text-neutral-800">Деавторизация Steam</div>
              <p className="text-xs text-neutral-500">
                Выйти со всех устройств Steam для выбранного аккаунта.
              </p>
              <button
                onClick={handleSteamDeauthorize}
                disabled={accountControlBusy}
                className="mt-3 w-full rounded-lg border border-amber-200 bg-amber-50 px-4 py-2 text-sm font-semibold text-amber-700 transition hover:bg-amber-100 disabled:cursor-not-allowed disabled:opacity-60"
              >
                Деавторизовать Steam
              </button>
            </div>
            <div className="rounded-xl border border-neutral-200 bg-neutral-50 p-4">
              <div className="mb-2 text-sm font-semibold text-neutral-800">Удалить аккаунт</div>
              <p className="text-xs text-neutral-500">Удаляет аккаунт и его привязки лотов.</p>
              <button
                onClick={handleDeleteAccount}
                disabled={accountControlBusy}
                className="mt-3 w-full rounded-lg border border-rose-200 bg-rose-50 px-4 py-2 text-sm font-semibold text-rose-700 transition hover:bg-rose-100 disabled:cursor-not-allowed disabled:opacity-60"
              >
                Удалить аккаунт
              </button>
            </div>
          </div>
        ) : (
          <div className="rounded-xl border border-dashed border-neutral-200 bg-neutral-50 px-4 py-6 text-center text-sm text-neutral-500">
            Выберите аккаунт, чтобы управлять заморозкой и удалением.
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="space-y-6">
      <div className="grid items-start gap-6 xl:grid-cols-[minmax(0,1.55fr)_minmax(0,1fr)]">
        <div className="rounded-2xl border border-neutral-200 bg-white p-6 shadow-sm shadow-neutral-200/70">
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
            <div>
              <h3 className="text-lg font-semibold text-neutral-900">Инвентарь</h3>
              <p className="text-xs text-neutral-500">Выберите аккаунт, чтобы управлять арендами.</p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <div className="flex items-center gap-2 rounded-full bg-neutral-100 px-3 py-1 text-xs font-semibold text-neutral-600">
                <span className="uppercase tracking-wide text-neutral-500">Область</span>
                <span className="font-semibold text-neutral-700">Все платформы и рабочие пространства</span>
              </div>
              {selectedAccount ? (
                <span className="text-xs rounded-full bg-neutral-100 px-3 py-1 font-semibold text-neutral-600">
                  Выбранный ID {selectedAccount.id ?? "-"}
                </span>
              ) : (
                <span className="text-xs rounded-full bg-neutral-100 px-3 py-1 font-semibold text-neutral-600">
                  Аккаунт не выбран
                </span>
              )}
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-3 rounded-xl border border-neutral-200 bg-neutral-50 px-4 py-3 text-xs text-neutral-600">
            <div className="flex flex-wrap items-center gap-2">
              {statusOptions.map((option) => (
                <button
                  key={option.key}
                  type="button"
                  onClick={() => setStatusFilter(option.key)}
                  className={`rounded-full px-3 py-1 font-semibold transition ${
                    statusFilter === option.key
                      ? "bg-neutral-900 text-white"
                      : "bg-white text-neutral-600 hover:bg-neutral-100"
                  }`}
                >
                  {option.label} · {statusCounts[option.key as keyof typeof statusCounts]}
                </button>
              ))}
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-[11px] uppercase tracking-wide text-neutral-500">MMR</span>
              <input
                className="w-20 rounded-lg border border-neutral-200 bg-white px-2 py-1 text-xs text-neutral-700 outline-none focus:border-neutral-400"
                placeholder="Мин."
                value={mmrMin}
                onChange={(event) => setMmrMin(event.target.value)}
              />
              <input
                className="w-20 rounded-lg border border-neutral-200 bg-white px-2 py-1 text-xs text-neutral-700 outline-none focus:border-neutral-400"
                placeholder="Макс."
                value={mmrMax}
                onChange={(event) => setMmrMax(event.target.value)}
              />
              <button
                type="button"
                onClick={() => {
                  setMmrMin("");
                  setMmrMax("");
                }}
                className="rounded-lg border border-neutral-200 bg-white px-2 py-1 text-[11px] font-semibold text-neutral-600 hover:bg-neutral-100"
              >
                Сброс
              </button>
            </div>
          </div>
          <div className="overflow-x-hidden">
            <div className="min-w-0">
              <div className="mt-3 list-scroll">
                <div
                  className="sticky top-0 z-10 grid gap-3 bg-white px-6 py-2 text-xs font-semibold text-neutral-500"
                  style={{ gridTemplateColumns: INVENTORY_GRID }}
                >
                  <span>ID</span>
                  <span>Название</span>
                  <span>Логин</span>
                  <span>Пароль</span>
                  <span>Steam ID</span>
                  <span>MMR</span>
                  <span className="text-center">Статус</span>
                </div>
                <div className="mt-3 space-y-3">
                  {filteredAccounts.map((acc, idx) => {
                  const rented = !!acc.owner;
                  const frozen = !!acc.accountFrozen;
                  const lowPriority = !!acc.lowPriority;
                  const lotLinked = acc.lotNumber !== null && acc.lotNumber !== undefined;
                  const lotLabel = lotLinked ? "Лот: привязан" : "Лот: не привязан";
                  const lotClass = lotLinked ? "bg-emerald-50 text-emerald-700" : "bg-neutral-100 text-neutral-500";
                  const stateLabel = lowPriority ? "Низкий приоритет" : frozen ? "Заморожено" : rented ? "В аренде" : "Доступен";
                  const stateClass = lowPriority
                    ? "bg-rose-50 text-rose-600"
                    : frozen
                      ? "bg-slate-100 text-slate-700"
                      : rented
                        ? "bg-amber-50 text-amber-700"
                        : "bg-emerald-50 text-emerald-600";
                  const rowId = acc.id ?? idx;
                  const isSelected = selectedId !== null && String(selectedId) === String(rowId);
                  return (
                    <motion.div
                      key={rowId}
                      role="button"
                      tabIndex={0}
                      onKeyDown={(event) => {
                        if (event.key === "Enter" || event.key === " ") {
                          event.preventDefault();
                          setSelectedId((prev) => (prev !== null && String(prev) === String(rowId) ? null : rowId));
                        }
                      }}
                      onClick={() =>
                        setSelectedId((prev) => (prev !== null && String(prev) === String(rowId) ? null : rowId))
                      }
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0, transition: { duration: 0.25, delay: idx * 0.03, ease: EASE } }}
                      className={`grid items-center gap-3 rounded-xl border px-6 py-4 text-sm shadow-[0_4px_18px_-14px_rgba(0,0,0,0.18)] transition ${
                        isSelected
                          ? "border-neutral-900/20 bg-white ring-2 ring-neutral-900/10"
                          : "border-neutral-100 bg-neutral-50 hover:border-neutral-200"
                      } cursor-pointer`}
                      style={{ gridTemplateColumns: INVENTORY_GRID }}
                    >
                      <span className="min-w-0 font-semibold text-neutral-900" title={String(rowId)}>
                        {rowId}
                      </span>
                      <div className="min-w-0">
                        <div className="truncate font-semibold leading-tight text-neutral-900" title={acc.name || "Account"}>
                          {acc.name || "Account"}
                        </div>
                        <div className="mt-1 flex flex-wrap gap-1">
                          <span className={`inline-flex w-fit rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${lotClass}`}>
                            {lotLabel}
                          </span>
                          <span className="inline-flex w-fit rounded-full bg-neutral-100 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-neutral-600">
                            Лот: {lotLinked ? `#${acc.lotNumber}` : "-"}
                          </span>
                          <span className="inline-flex w-fit rounded-full bg-neutral-100 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-neutral-600">
                            Основное: {formatWorkspaceLabel(acc.workspaceName, acc.workspaceId)}
                          </span>
                          <span className="inline-flex w-fit rounded-full bg-neutral-100 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-neutral-600">
                            Last rented:{" "}
                            {acc.lastRentedWorkspaceId
                              ? formatWorkspaceLabel(acc.lastRentedWorkspaceName, acc.lastRentedWorkspaceId)
                              : "-"}
                          </span>
                        </div>
                      </div>
                      <span className="min-w-0 truncate text-neutral-700" title={acc.login || ""}>
                        {stratzUrl(acc.steamId) ? (
                          <a
                            href={stratzUrl(acc.steamId)!}
                            target="_blank"
                            rel="noreferrer"
                            className="text-blue-600 underline"
                            onClick={(e) => e.stopPropagation()}
                          >
                            {acc.login || acc.steamId || ""}
                          </a>
                        ) : (
                          acc.login || ""
                        )}
                      </span>
                      <span className="min-w-0 truncate text-neutral-700" title={acc.password || ""}>
                        {acc.password || ""}
                      </span>
                      <span
                        className="min-w-0 truncate font-mono text-xs leading-tight text-neutral-800 tabular-nums"
                        title={acc.steamId || ""}
                      >
                        {acc.steamId || ""}
                      </span>
                      <span className="min-w-0 truncate text-neutral-700" title={String(acc.mmr ?? "")}>
                        {acc.mmr ?? ""}
                      </span>
                      <span className={`justify-self-center rounded-full px-3 py-1 text-xs font-semibold ${stateClass}`}>
                        {stateLabel}
                      </span>
                    </motion.div>
                  );
                  })}
                  {filteredAccounts.length === 0 && (
                    <div className="rounded-xl border border-dashed border-neutral-200 bg-neutral-50 px-4 py-6 text-center text-sm text-neutral-500">
                      {accounts.length === 0 ? emptyMessage : "Нет аккаунтов по текущим фильтрам."}
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>
        <div className="mt-6 grid gap-6 lg:grid-cols-2">
          {renderAccountActionsPanel("Account actions")}
          {renderИнвентарьActionsPanel()}
        </div>
      </div>
    </div>
  );
};

export default ИнвентарьPage;
