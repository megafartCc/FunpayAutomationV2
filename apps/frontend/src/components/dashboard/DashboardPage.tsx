import React, { useEffect, useMemo, useState } from "react";
import { motion } from "framer-motion";

import { api, AccountItem, ActiveRentalItem } from "../../services/api";
import { useWorkspace } from "../../context/WorkspaceContext";
import BuyerChatPanel from "../chats/BuyerChatPanel";

type DeltaTone = "up" | "down";

type StatCardProps = {
  label: string;
  value: string | number;
  delta?: string;
  deltaTone?: DeltaTone;
  icon: React.ReactNode;
};

const CardUsersIcon = () => (
  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
    <path
      d="M21 19.9999C21 18.2583 19.3304 16.7767 17 16.2275M15 20C15 17.7909 12.3137 16 9 16C5.68629 16 3 17.7909 3 20M15 13C17.2091 13 19 11.2091 19 9C19 6.79086 17.2091 5 15 5M9 13C6.79086 13 5 11.2091 5 9C5 6.79086 6.79086 5 9 5C11.2091 5 13 6.79086 13 9C13 11.2091 11.2091 13 9 13Z"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
  </svg>
);

const CardCloudCheckIcon = () => (
  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
    <path
      d="M15 11L11 15L9 13M23 15C23 12.7909 21.2091 11 19 11C18.9764 11 18.9532 11.0002 18.9297 11.0006C18.4447 7.60802 15.5267 5 12 5C9.20335 5 6.79019 6.64004 5.66895 9.01082C3.06206 9.18144 1 11.3498 1 13.9999C1 16.7613 3.23858 19.0001 6 19.0001L19 19C21.2091 19 23 17.2091 23 15Z"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
  </svg>
);

const CardBarsIcon = () => (
  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
    <path
      d="M19.5 5.5V18.5M12 3.5V18.5M4.5 9.5V18.5M22 18.5H2"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
  </svg>
);

const EASE: [number, number, number, number] = [0.22, 1, 0.36, 1];

const stratzUrl = (steamId?: string | null) => {
  const trimmed = steamId?.trim();
  if (!trimmed) return null;
  return `https://stratz.com/search/${trimmed}`;
};

const StatCard: React.FC<StatCardProps> = ({ label, value, delta, deltaTone, icon }) => (
  <div className="flex items-start justify-between rounded-2xl border border-neutral-200 bg-white px-5 py-4 shadow-sm" style={{ minHeight: 110 }}>
    <div className="flex gap-3">
      <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-neutral-100 text-neutral-700">{icon}</div>
      <div className="flex flex-col">
        <p className="text-sm font-semibold text-neutral-900">{label}</p>
        <p className="mt-1 text-2xl font-semibold text-neutral-900">{value}</p>
      </div>
    </div>
    {delta ? (
      <span
        className={`rounded-full px-3 py-1 text-xs font-semibold ${
          deltaTone === "down" ? "bg-rose-50 text-rose-600" : "bg-emerald-50 text-emerald-600"
        }`}
      >
        {delta}
      </span>
    ) : null}
  </div>
);

const statusPill = (status?: string) => {
  const lower = (status || "").toLowerCase();
  if (lower.includes("frozen") || lower.includes("заморож"))
    return { className: "bg-slate-100 text-slate-700", label: "Заморожен" };
  if (lower.includes("demo") || lower.includes("демо"))
    return { className: "bg-amber-50 text-amber-700", label: "Демо-герой" };
  if (lower.includes("bot") || lower.includes("бот"))
    return { className: "bg-amber-50 text-amber-700", label: "Матч с ботами" };
  if (lower.includes("custom") || lower.includes("пользовател"))
    return { className: "bg-amber-50 text-amber-600", label: "Пользовательская игра" };
  if (lower.includes("match") || lower.includes("матч"))
    return { className: "bg-emerald-50 text-emerald-600", label: "В матче" };
  if (lower.includes("game") || lower.includes("игра"))
    return { className: "bg-amber-50 text-amber-600", label: "В игре" };
  if (lower.includes("online") || lower.includes("в сети") || lower === "1" || lower === "true")
    return { className: "bg-emerald-50 text-emerald-600", label: "В сети" };
  if (lower.includes("idle") || lower.includes("away") || lower.includes("отош"))
    return { className: "bg-amber-50 text-amber-600", label: "Отошёл" };
  if (lower.includes("off") || lower.includes("не в сети") || lower === "" || lower === "0")
    return { className: "bg-rose-50 text-rose-600", label: "Не в сети" };
  return { className: "bg-neutral-100 text-neutral-600", label: status || "Неизвестно" };
};

const makeAccountKey = (workspaceId: number | null | undefined, id: number) =>
  `${workspaceId ?? "none"}:${id}`;

const makeRowKey = (_prefix: "acc" | "rent", workspaceId: number | null | undefined, id: number) =>
  makeAccountKey(workspaceId, id);

type AccountRow = {
  id: number;
  rowKey: string;
  accountKey: string;
  workspaceId?: number | null;
  workspaceName?: string | null;
  lastRentedWorkspaceId?: number | null;
  lastRentedWorkspaceName?: string | null;
  name: string;
  login: string;
  password: string;
  steamId: string;
  mmr: number | string;
  owner?: string | null;
  rentalStart?: string | null;
  rentalDuration?: number;
  rentalDurationMinutes?: number | null;
  accountFrozen?: boolean;
  rentalFrozen?: boolean;
  lowPriority?: boolean;
};

type RentalRow = {
  id: number;
  rowKey: string;
  accountKey: string;
  workspaceId?: number | null;
  workspaceName?: string | null;
  account: string;
  buyer: string;
  started: string;
  timeLeft: string;
  matchTime: string;
  matchTimeSeconds?: number | null;
  matchTimeObservedAt?: number | null;
  hero: string;
  status: string;
};

const INVENTORY_GRID =
  "minmax(0,0.45fr) minmax(0,1.4fr) minmax(0,1.1fr) minmax(0,1.1fr) minmax(0,1.25fr) minmax(0,0.6fr) minmax(0,0.7fr)";
const RENTALS_GRID =
  "minmax(0,0.5fr) minmax(0,1.3fr) minmax(0,1fr) minmax(0,0.9fr) minmax(0,0.9fr) minmax(0,0.8fr) minmax(0,1fr) minmax(0,0.7fr)";

const mapAccount = (item: AccountItem): AccountRow => ({
  id: item.id,
  rowKey: makeRowKey("acc", item.workspace_id ?? null, item.id),
  accountKey: makeAccountKey(item.workspace_id ?? null, item.id),
  workspaceId: item.workspace_id ?? null,
  workspaceName: item.workspace_name ?? null,
  lastRentedWorkspaceId: item.last_rented_workspace_id ?? null,
  lastRentedWorkspaceName: item.last_rented_workspace_name ?? null,
  name: item.account_name,
  login: item.login,
  password: item.password || "",
  steamId: item.steam_id ?? "",
  mmr: item.mmr ?? "-",
  owner: item.owner ?? null,
  rentalStart: item.rental_start ?? null,
  rentalДлительность: item.rental_duration ?? 0,
  rentalDurationMinutes: item.rental_duration_minutes ?? null,
  accountFrozen: !!item.account_frozen,
  rentalFrozen: !!item.rental_frozen,
  lowPriority: !!item.low_priority,
});

const parseMatchTimeSeconds = (value?: string | null) => {
  if (!value) return null;
  const trimmed = value.trim();
  if (!trimmed || trimmed === "-") return null;
  if (/^\d+$/.test(trimmed)) return Number.parseInt(trimmed, 10);
  if (!trimmed.includes(":")) return null;
  const parts = trimmed.split(":").map((part) => Number.parseInt(part, 10));
  if (parts.some((part) => Number.isNaN(part))) return null;
  if (parts.length === 2) return parts[0] * 60 + parts[1];
  if (parts.length === 3) return parts[0] * 3600 + parts[1] * 60 + parts[2];
  return null;
};

const formatMatchTime = (seconds: number) => {
  const safe = Math.max(0, Math.floor(seconds));
  const hours = Math.floor(safe / 3600);
  const minutes = Math.floor((safe % 3600) / 60);
  const secs = safe % 60;
  if (hours > 0) {
    return `${hours}:${String(minutes).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
  }
  return `${minutes}:${String(secs).padStart(2, "0")}`;
};

const mapRental = (item: ActiveRentalItem, observedAt: number): RentalRow => {
  const rawMatch = item.match_time || "-";
  const matchSeconds = parseMatchTimeSeconds(rawMatch);
  return {
    id: item.id,
    rowKey: makeRowKey("rent", item.workspace_id ?? null, item.id),
    accountKey: makeAccountKey(item.workspace_id ?? null, item.id),
    workspaceId: item.workspace_id ?? null,
    workspaceName: item.workspace_name ?? null,
    account: item.account,
    buyer: item.buyer,
    started: item.started,
    timeLeft: item.time_left,
    matchTime: rawMatch,
    matchTimeSeconds: matchSeconds,
    matchTimeObservedAt: matchSeconds !== null ? observedAt : null,
    hero: item.hero || "-",
    status: item.status || "",
  };
};

const formatDuration = (minutesTotal: number | null | undefined) => {
  if (!minutesTotal && minutesTotal !== 0) return "-";
  const minutes = Math.max(0, Math.floor(minutesTotal));
  const hours = Math.floor(minutes / 60);
  const rem = minutes % 60;
  return `${hours} ч ${rem} мин`;
};

const parseUtcMs = (value?: string | null) => {
  if (!value) return null;
  const normalized = value.includes("T") ? value : value.replace(" ", "T");
  const hasZone = /[zZ]|[+-]\d{2}:?\d{2}$/.test(normalized);
  if (!hasZone) {
    const utcTs = Date.parse(`${normalized}Z`);
    if (!Number.isNaN(utcTs)) return utcTs;
  }
  const localTs = Date.parse(normalized);
  if (!Number.isNaN(localTs)) return localTs;
  return null;
};

const getCountdownLabel = (
  account: AccountRow | null | undefined,
  fallback: string,
  nowMs: number,
) => {
  if (!account) return fallback || "-";
  const minutes =
    account.rentalDurationMinutes ?? (account.rentalDuration ? account.rentalDuration * 60 : 0);
  if (!minutes || minutes <= 0) return fallback || "-";
  const startMs = parseUtcMs(account.rentalStart ?? null);
  if (!startMs) return fallback || "-";
  const endMs = startMs + minutes * 60_000;
  const remainingMs = Math.max(0, endMs - nowMs);
  const totalSeconds = Math.floor(remainingMs / 1000);
  const hours = Math.floor(totalSeconds / 3600);
  const minutesLeft = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;
  return `${hours} \u0447 ${minutesLeft} \u043c\u0438\u043d ${seconds} \u0441\u0435\u043a`;
};

const getMatchTimeLabel = (row: RentalRow | null | undefined, nowMs: number) => {
  if (!row) return "-";
  if (row.matchTimeSeconds === null || row.matchTimeSeconds === undefined) {
    return row.matchTime || "-";
  }
  if (!row.matchTimeObservedAt) {
    return formatMatchTime(row.matchTimeSeconds);
  }
  const elapsed = Math.max(0, Math.floor((nowMs - row.matchTimeObservedAt) / 1000));
  return formatMatchTime(row.matchTimeSeconds + elapsed);
};

const resolveWorkspaceName = (
  workspaceId: number | null | undefined,
  workspaceName: string | null | undefined,
  workspaces: { id: number; name: string; is_default?: boolean }[],
) => {
  if (workspaceName) return workspaceName;
  if (workspaceId) {
    const match = workspaces.find((item) => item.id === workspaceId);
    if (match) return match.name;
  }
  const fallback = workspaces.find((item) => item.is_default);
  if (fallback) return fallback.name;
  if (workspaceId) return `Рабочее пространство ${workspaceId}`;
  return "Рабочее пространство";
};

const formatWorkspaceLabel = (
  workspaceId: number | null | undefined,
  workspaceName: string | null | undefined,
  workspaces: { id: number; name: string; is_default?: boolean }[],
) => {
  const label = resolveWorkspaceName(workspaceId, workspaceName, workspaces);
  return workspaceId ? `${label} (ID ${workspaceId})` : label;
};

const DashboardPage: React.FC<DashboardPageProps> = ({ onToast }) => {
  const { selectedId: selectedWorkspaceId, selectedPlatform, workspaces } = useWorkspace();
  const workspaceId = selectedWorkspaceId === "all" ? null : (selectedWorkspaceId as number | null);
  const accountWorkspaceId = selectedPlatform === "all" ? selectedWorkspaceId : "all";
  const [allAccounts, setAllAccounts] = useState<AccountRow[]>([]);
  const [rentals, setRentals] = useState<RentalRow[]>([]);
  const [loadingAccounts, setLoadingAccounts] = useState(true);
  const [loadingRentals, setLoadingRentals] = useState(true);
  const [now, setNow] = useState(Date.now());
  const [selectedRowKey, setSelectedRowKey] = useState<string | null>(null);
  const [assignOwner, setAssignOwner] = useState("");
  const [assignHours, setAssignHours] = useState("");
  const [assignMinutes, setAssignMinutes] = useState("");
  const [accountEditName, setAccountEditName] = useState("");
  const [accountEditLogin, setAccountEditLogin] = useState("");
  const [accountEditPassword, setAccountEditPassword] = useState("");
  const [accountEditMmr, setAccountEditMmr] = useState("");
  const [rentalExtendHours, setRentalExtendHours] = useState("");
  const [rentalExtendMinutes, setRentalExtendMinutes] = useState("");
  const [accountActionBusy, setAccountActionBusy] = useState(false);
  const [rentalActionBusy, setRentalActionBusy] = useState(false);
  const [chatTarget, setChatTarget] = useState<{ buyer: string; workspaceId?: number | null } | null>(null);

  const filteredAccounts = useMemo(() => {
    if (accountWorkspaceId === "all") {
      return allAccounts;
    }
    const workspaceId = accountWorkspaceId as number;
    return allAccounts.filter((acc) => {
      const scopedId = acc.lastRentedWorkspaceId ?? acc.workspaceId ?? null;
      return scopedId === workspaceId;
    });
  }, [allAccounts, accountWorkspaceId]);

  const filteredRentals = useMemo(() => {
    return rentals;
  }, [rentals]);

  const accountById = useMemo(
    () => new Map(allAccounts.map((acc) => [acc.id, acc])),
    [allAccounts],
  );
  const selectedRental = useMemo(
    () => filteredRentals.find((row) => row.rowKey === selectedRowKey) ?? null,
    [filteredRentals, selectedRowKey],
  );
  const selectedAccount = useMemo(() => {
    const direct = filteredAccounts.find((acc) => acc.rowKey === selectedRowKey) ?? null;
    if (direct) return direct;
    if (selectedRental) {
      return accountById.get(selectedRental.id) ?? null;
    }
    return null;
  }, [filteredAccounts, selectedRental, accountById, selectedRowKey]);

  const statCards = useMemo<StatCardProps[]>(() => {
    const totalAccounts = filteredAccounts.length;
    const activeRentals = filteredRentals.length;
    const freeAccounts = filteredAccounts.filter((acc) => !acc.owner && !acc.accountFrozen && !acc.lowPriority).length;
    const past24h = filteredAccounts.filter((acc) => {
      const startMs = parseUtcMs(acc.rentalStart ?? null);
      return startMs !== null && now - startMs <= 24 * 60 * 60 * 1000;
    }).length;
    return [
      { label: "Всего аккаунтов", value: totalAccounts, icon: <CardUsersIcon /> },
      { label: "Активные аренды", value: activeRentals, icon: <CardUsersIcon /> },
      { label: "Свободные аккаунты", value: freeAccounts, icon: <CardCloudCheckIcon /> },
      { label: "За 24 часа", value: past24h, icon: <CardBarsIcon /> },
    ];
  }, [filteredAccounts, filteredRentals, now]);

  const loadAccounts = async (silent = false) => {
    if (!silent) setLoadingAccounts(true);
    try {
      const res = await api.listAccounts();
      setAllAccounts((res.items || []).map(mapAccount));
    } catch {
      setAllAccounts([]);
    } finally {
      if (!silent) setLoadingAccounts(false);
    }
  };

  const loadRentals = async (silent = false) => {
    if (!silent) setLoadingRentals(true);
    try {
      if (selectedWorkspaceId === "all") {
        const res = await api.listActiveRentals();
        const observedAt = Date.now();
        setRentals(res.items.map((item) => mapRental(item, observedAt)));
        return;
      }
      const workspaceId = selectedWorkspaceId as number;
      const res = await api.listActiveRentals(workspaceId);
      const observedAt = Date.now();
      setRentals(res.items.map((item) => mapRental(item, observedAt)));
    } catch {
      setRentals([]);
    } finally {
      if (!silent) setLoadingRentals(false);
    }
  };

  useEffect(() => {
    void loadAccounts();
    void loadRentals();
  }, [selectedWorkspaceId]);

  useEffect(() => {
    const id = window.setInterval(() => {
      void loadAccounts(true);
      void loadRentals(true);
    }, 30_000);
    return () => window.clearInterval(id);
  }, [selectedWorkspaceId]);

  useEffect(() => {
    const id = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(id);
  }, []);

  useEffect(() => {
    if (
      selectedRowKey &&
      !filteredAccounts.some((acc) => acc.rowKey === selectedRowKey) &&
      !filteredRentals.some((r) => r.rowKey === selectedRowKey)
    ) {
      setSelectedRowKey(null);
    }
  }, [filteredAccounts, filteredRentals, selectedRowKey]);

  useEffect(() => {
    if (!selectedAccount) {
      setAssignOwner("");
      setAccountEditName("");
      setAccountEditLogin("");
      setAccountEditPassword("");
      setAccountEditMmr("");
      return;
    }
    setAccountEditName(selectedAccount.name || "");
    setAccountEditLogin(selectedAccount.login || "");
    setAccountEditPassword(selectedAccount.password || "");
    setAccountEditMmr(
      selectedAccount.mmr !== "-" && selectedAccount.mmr !== undefined ? String(selectedAccount.mmr) : "",
    );
  }, [selectedAccount]);

  const emptyAccountMessage = loadingAccounts ? "Загрузка аккаунтов..." : "Пока нет аккаунтов.";
  const emptyRentalMessage = loadingRentals ? "Загрузка аренд..." : "Нет активных аренд.";
  const inventoryAccounts = accountWorkspaceId === "all" ? allAccounts : filteredAccounts;

  const handleAssignAccount = async () => {
    if (!selectedAccount) {
      onToast?.("Сначала выберите аккаунт.", true);
      return;
    }
    if (accountActionBusy) return;
    if (selectedAccount.lowPriority) {
      onToast?.("Сначала снимите низкий приоритет перед назначением покупателя.", true);
      return;
    }
    if (selectedAccount.accountFrozen) {
      onToast?.("Разморозьте аккаунт перед назначением покупателя.", true);
      return;
    }
    if (selectedAccount.owner) {
      onToast?.("Сначала освободите аккаунт.", true);
      return;
    }
    const owner = assignOwner.trim();
    if (!owner) {
      onToast?.("Введите имя пользователя покупателя.", true);
      return;
    }
    const hasManualDuration = assignHours.trim() !== "" || assignMinutes.trim() !== "";
    let manualHours: number | null = null;
    let manualMinutes: number | null = null;
    if (hasManualDuration) {
      const hoursValue = Number(assignHours || 0);
      const minutesValue = Number(assignMinutes || 0);
      if (!Number.isFinite(hoursValue) || !Number.isFinite(minutesValue) || hoursValue < 0 || minutesValue < 0) {
        onToast?.("Введите корректное количество часов и минут.", true);
        return;
      }
      if (minutesValue >= 60) {
        onToast?.("Минуты должны быть меньше 60.", true);
        return;
      }
      if (hoursValue > 9999) {
        onToast?.("Слишком большое количество часов.", true);
        return;
      }
      if (hoursValue * 60 + minutesValue <= 0) {
        onToast?.("Укажите продолжительность больше 0.", true);
        return;
      }
      manualHours = hoursValue;
      manualMinutes = minutesValue;
    }
    setAccountActionBusy(true);
    try {
      const workspaceId =
        accountWorkspaceId === "all"
          ? selectedAccount.workspaceId ?? selectedAccount.lastRentedWorkspaceId ?? undefined
          : (accountWorkspaceId as number);
      await api.assignAccount(selectedAccount.id, owner, manualHours, manualMinutes, workspaceId);
      onToast?.("Аренда назначена.");
      setAssignOwner("");
      setAssignHours("");
      setAssignMinutes("");
      await Promise.all([loadAccounts(), loadRentals()]);
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
        onToast?.("MMR должен быть 0 или выше.", true);
        return;
      }
      if (String(mmr) !== String(selectedAccount.mmr ?? "")) payload.mmr = mmr;
    }

    if (!Object.keys(payload).length) {
      onToast?.("Нет изменений для сохранения.", true);
      return;
    }

    setAccountActionBusy(true);
    try {
      const workspaceId =
        accountWorkspaceId === "all"
          ? selectedAccount.workspaceId ?? selectedAccount.lastRentedWorkspaceId ?? undefined
          : (accountWorkspaceId as number);
      await api.updateAccount(selectedAccount.id, payload, workspaceId);
      onToast?.("Аккаунт обновлён.");
      await Promise.all([loadAccounts(), loadRentals()]);
    } catch (err) {
      const message = (err as { message?: string })?.message || "Не удалось обновить аккаунт.";
      onToast?.(message, true);
    } finally {
      setAccountActionBusy(false);
    }
  };

  const handleExtendRental = async () => {
    if (!selectedRental || !selectedAccount) {
      onToast?.("Сначала выберите аренду.", true);
      return;
    }
    if (rentalActionBusy) return;
    const hours = Number(rentalExtendHours || 0);
    const minutes = Number(rentalExtendMinutes || 0);
    if (!Number.isFinite(hours) || !Number.isFinite(minutes) || hours < 0 || minutes < 0) {
      onToast?.("Введите корректные часы и минуты.", true);
      return;
    }
    if (hours * 60 + minutes <= 0) {
      onToast?.("Продление должно быть больше 0.", true);
      return;
    }
    setRentalActionBusy(true);
    try {
      const workspaceId =
        accountWorkspaceId === "all"
          ? selectedAccount.lastRentedWorkspaceId ?? selectedAccount.workspaceId ?? undefined
          : (accountWorkspaceId as number);
      await api.extendAccount(selectedAccount.id, hours, minutes, workspaceId);
      onToast?.("Аренда продлена.");
      setRentalExtendHours("");
      setRentalExtendMinutes("");
      await Promise.all([loadAccounts(), loadRentals()]);
    } catch (err) {
      const message = (err as { message?: string })?.message || "Не удалось продлить аренду.";
      onToast?.(message, true);
    } finally {
      setRentalActionBusy(false);
    }
  };

  const handleReleaseRental = async () => {
    if (!selectedRental || !selectedAccount) {
      onToast?.("Сначала выберите аренду.", true);
      return;
    }
    if (rentalActionBusy) return;
    setRentalActionBusy(true);
    try {
      const workspaceId =
        accountWorkspaceId === "all"
          ? selectedAccount.lastRentedWorkspaceId ?? selectedAccount.workspaceId ?? undefined
          : (accountWorkspaceId as number);
      await api.releaseAccount(selectedAccount.id, workspaceId);
      onToast?.("Аренда завершена.");
      await Promise.all([loadAccounts(), loadRentals()]);
    } catch (err) {
      const message = (err as { message?: string })?.message || "Не удалось завершить аренду.";
      onToast?.(message, true);
    } finally {
      setRentalActionBusy(false);
    }
  };

  const handleToggleRentalFreeze = async (nextFrozen: boolean) => {
    if (!selectedRental || !selectedAccount) {
      onToast?.("Сначала выберите аренду.", true);
      return;
    }
    if (rentalActionBusy) return;
    setRentalActionBusy(true);
    try {
      const workspaceId =
        accountWorkspaceId === "all"
          ? selectedAccount.lastRentedWorkspaceId ?? selectedAccount.workspaceId ?? undefined
          : (accountWorkspaceId as number);
      await api.freezeRental(selectedAccount.id, nextFrozen, workspaceId);
      onToast?.(nextFrozen ? "Аренда заморожена." : "Аренда разморожена.");
      await Promise.all([loadAccounts(), loadRentals()]);
    } catch (err) {
      const message = (err as { message?: string })?.message || "Не удалось обновить статус заморозки аренды.";
      onToast?.(message, true);
    } finally {
      setRentalActionBusy(false);
    }
  };

  const handleToggleLowPriority = async (nextLowPriority: boolean) => {
    if (!selectedAccount) {
      onToast?.("Сначала выберите аккаунт.", true);
      return;
    }
    if (accountActionBusy) return;
    setAccountActionBusy(true);
    try {
      const workspaceId =
        accountWorkspaceId === "all"
          ? selectedAccount.workspaceId ?? selectedAccount.lastRentedWorkspaceId ?? undefined
          : (accountWorkspaceId as number);
      await api.setLowPriority(selectedAccount.id, nextLowPriority, workspaceId);
      onToast?.(nextLowPriority ? "Помечено как низкий приоритет." : "Низкий приоритет снят.");
      await Promise.all([loadAccounts(), loadRentals()]);
    } catch (err) {
      const message = (err as { message?: string })?.message || "Не удалось обновить низкий приоритет.";
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
    if (accountActionBusy) return;
    setAccountActionBusy(true);
    try {
      const workspaceId =
        accountWorkspaceId === "all"
          ? selectedAccount.workspaceId ?? selectedAccount.lastRentedWorkspaceId ?? undefined
          : (accountWorkspaceId as number);
      await api.freezeAccount(selectedAccount.id, nextFrozen, workspaceId);
      onToast?.(nextFrozen ? "Аккаунт заморожен." : "Аккаунт разморожен.");
      await Promise.all([loadAccounts(), loadRentals()]);
    } catch (err) {
      const message = (err as { message?: string })?.message || "Не удалось обновить статус заморозки аккаунта.";
      onToast?.(message, true);
    } finally {
      setAccountActionBusy(false);
    }
  };

  const renderAccountActionsPanel = () => {
    return (
      <div className="rounded-2xl border border-neutral-200 bg-white p-6 shadow-sm shadow-neutral-200/70">
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-lg font-semibold text-neutral-900">Действия с аккаунтом</h3>
          <span className="text-xs text-neutral-500">{selectedAccount ? "Готово" : "Выберите аккаунт"}</span>
        </div>
        {selectedAccount ? (
          (() => {
            const rented = !!selectedAccount.owner;
            const frozen = !!selectedAccount.accountFrozen;
            const lowPriority = !!selectedAccount.lowPriority;
            const stateLabel = lowPriority ? "Низкий приоритет" : frozen ? "Заморожен" : rented ? "В аренде" : "Свободен";
            const stateClass = lowPriority
              ? "bg-rose-50 text-rose-600"
              : frozen
                ? "bg-slate-100 text-slate-700"
                : rented
                  ? "bg-amber-50 text-amber-700"
                  : "bg-emerald-50 text-emerald-600";
            const ownerLabel = selectedAccount.owner ? String(selectedAccount.owner) : "-";
            const workspaceLabel = formatWorkspaceLabel(
              selectedAccount.workspaceId,
              selectedAccount.workspaceName,
              workspaces,
            );
            const workspaceRecord = selectedAccount.workspaceId
              ? workspaces.find((item) => item.id === selectedAccount.workspaceId)
              : workspaces.find((item) => item.is_default) ?? null;
            const workspaceDisplay = workspaceRecord?.is_default
              ? `${workspaceLabel} (По умолчанию)`
              : workspaceLabel;
            const lastRentedLabel = selectedAccount.lastRentedWorkspaceId
              ? formatWorkspaceLabel(
                  selectedAccount.lastRentedWorkspaceId,
                  selectedAccount.lastRentedWorkspaceName,
                  workspaces,
                )
              : "-";
            const lastRentedRecord = selectedAccount.lastRentedWorkspaceId
              ? workspaces.find((item) => item.id === selectedAccount.lastRentedWorkspaceId)
              : null;
            const lastRentedDisplay = lastRentedRecord?.is_default
              ? `${lastRentedLabel} (По умолчанию)`
              : lastRentedLabel;
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
            const passwordChanged =
              accountEditPassword.trim() && accountEditPassword.trim() !== (selectedAccount.password || "");
            const mmrChanged =
              editMmrRaw &&
              Number.isFinite(editMmrValue) &&
              String(editMmrValue) !== String(selectedAccount.mmr ?? "");
            const hasChanges = nameChanged || loginChanged || passwordChanged || mmrChanged;
            return (
              <div className="space-y-4">
                <div className="rounded-xl border border-neutral-200 bg-neutral-50 p-4">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <div className="text-xs font-semibold uppercase tracking-wide text-neutral-500">
                        Выбранный аккаунт
                      </div>
                      <div className="mt-1 text-sm font-semibold text-neutral-900">
                        {selectedAccount.name || "Аккаунт"}
                      </div>
                    </div>
                    <span className={`rounded-full px-3 py-1 text-xs font-semibold ${stateClass}`}>{stateLabel}</span>
                  </div>
                  <div className="mt-3 grid gap-1 text-xs text-neutral-600">
                    <span>
                      Логин:{" "}
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
                    <span>Основное рабочее пространство: {workspaceDisplay}</span>
                    <span>Последняя аренда: {lastRentedDisplay}</span>
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
                      placeholder="Логин покупателя"
                      className="w-full rounded-lg border border-neutral-200 bg-white px-3 py-2 text-sm text-neutral-700 outline-none placeholder:text-neutral-400"
                    />
                    <div className="grid gap-3 sm:grid-cols-2">
                      <input
                        value={assignHours}
                        onChange={(e) => setAssignHours(e.target.value)}
                        placeholder="Часы (опционально)"
                        type="number"
                        min="0"
                        className="w-full rounded-lg border border-neutral-200 bg-white px-3 py-2 text-sm text-neutral-700 outline-none placeholder:text-neutral-400"
                      />
                      <input
                        value={assignMinutes}
                        onChange={(e) => setAssignMinutes(e.target.value)}
                        placeholder="Минуты (опционально)"
                        type="number"
                        min="0"
                        max="59"
                        className="w-full rounded-lg border border-neutral-200 bg-white px-3 py-2 text-sm text-neutral-700 outline-none placeholder:text-neutral-400"
                      />
                    </div>
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
                          ? "Сначала снимите низкий приоритет перед назначением покупателя."
                          : frozen
                            ? "Разморозьте аккаунт перед назначением покупателя."
                            : "Сначала освободите аккаунт."}
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
                      placeholder="Название аккаунта"
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
                        value={workspaceDisplay}
                        disabled
                        className="w-full rounded-lg border border-neutral-200 bg-white px-3 py-2 text-sm text-neutral-700 outline-none"
                      >
                        <option value={workspaceDisplay}>{workspaceDisplay}</option>
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
                <div className="rounded-xl border border-neutral-200 bg-neutral-50 p-4">
                  <div className="mb-2 text-sm font-semibold text-neutral-800">Статус аккаунта</div>
                  <p className="text-xs text-neutral-500">
                    Low priority accounts stay out of stock lists until you restore them.
                  </p>
                  <div className="mt-3 grid gap-2 sm:grid-cols-2">
                    <button
                      onClick={() => handleToggleAccountFreeze(!frozen)}
                      disabled={accountActionBusy}
                      className={`rounded-lg px-3 py-2 text-xs font-semibold transition disabled:cursor-not-allowed disabled:opacity-60 ${
                        frozen
                          ? "border border-emerald-200 bg-emerald-50 text-emerald-700 hover:bg-emerald-100"
                          : "border border-rose-200 bg-rose-50 text-rose-700 hover:bg-rose-100"
                      }`}
                    >
                      {frozen ? "Разморозить аккаунт" : "Заморозить аккаунт"}
                    </button>
                    <button
                      onClick={() => handleToggleLowPriority(!lowPriority)}
                      disabled={accountActionBusy}
                      className={`rounded-lg px-3 py-2 text-xs font-semibold transition disabled:cursor-not-allowed disabled:opacity-60 ${
                        lowPriority
                          ? "border border-emerald-200 bg-emerald-50 text-emerald-700 hover:bg-emerald-100"
                          : "border border-rose-200 bg-rose-50 text-rose-700 hover:bg-rose-100"
                      }`}
                    >
                      {lowPriority ? "Снять низкий приоритет" : "Пометить низким приоритетом"}
                    </button>
                  </div>
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

  const renderRentalActionsPanel = () => {
    return (
      <div className="rounded-2xl border border-neutral-200 bg-white p-6 shadow-sm shadow-neutral-200/70">
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-lg font-semibold text-neutral-900">Действия с арендой</h3>
          <span className="text-xs text-neutral-500">{selectedRental ? "Готово" : "Выберите аренду"}</span>
        </div>
        {selectedRental ? (
          (() => {
            const frozen = !!selectedAccount?.rentalFrozen;
            const pill = statusPill(frozen ? "Заморожен" : selectedRental.status);
            const presenceLabel = pill.label;
            const workspaceLabel = resolveWorkspaceName(
              selectedAccount?.workspaceId ?? selectedRental?.workspaceId,
              selectedAccount?.workspaceName ?? selectedRental?.workspaceName,
              workspaces,
            );
            const workspaceRecord = selectedAccount?.workspaceId
              ? workspaces.find((item) => item.id === selectedAccount.workspaceId)
              : selectedRental?.workspaceId
                ? workspaces.find((item) => item.id === selectedRental.workspaceId)
              : workspaces.find((item) => item.is_default) ?? null;
            const workspaceDisplay = workspaceRecord?.is_default
              ? `${workspaceLabel} (По умолчанию)`
              : workspaceLabel;
            return (
              <div className="space-y-4">
                <div className="rounded-xl border border-neutral-200 bg-neutral-50 p-4">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <div className="text-xs font-semibold uppercase tracking-wide text-neutral-500">
                        Выбранная аренда
                      </div>
                      <div className="mt-1 text-sm font-semibold text-neutral-900">
                        {selectedRental.account || "Аренда"}
                      </div>
                    </div>
                    <span className={`rounded-full px-3 py-1 text-xs font-semibold ${pill.className}`}>{presenceLabel}</span>
                  </div>
                  <div className="mt-3 grid gap-1 text-xs text-neutral-600">
                    <span>
                      Покупатель:{" "}
                      {selectedRental.buyer ? (
                        <button
                          type="button"
                          className="font-semibold text-neutral-800 hover:text-neutral-900"
                          onClick={() =>
                            setChatTarget({
                              buyer: selectedRental.buyer,
                              workspaceId: selectedRental.workspaceId ?? selectedAccount?.workspaceId ?? null,
                            })
                          }
                        >
                          {selectedRental.buyer}
                        </button>
                      ) : (
                        "-"
                      )}
                    </span>
                    <span>
                      Осталось:{" "}
                      {selectedRental
                        ? getCountdownLabel(
                            accountById.get(selectedRental.id),
                            selectedRental.timeLeft,
                            now,
                          )
                        : "-"}
                    </span>
                    <span>Время матча: {getMatchTimeLabel(selectedRental, now)}</span>
                    <span>Герой: {selectedRental.hero || "-"}</span>
                    <span>Рабочее пространство: {workspaceDisplay}</span>
                    <span>Начало: {selectedRental.started || "-"}</span>
                    {frozen && <span className="text-rose-600">Заморожено: таймер приостановлен до разморозки.</span>}
                  </div>
                </div>
                <div className="rounded-xl border border-neutral-200 bg-neutral-50 p-4">
                  <div className="mb-2 text-sm font-semibold text-neutral-800">Заморозить аренду</div>
                  <p className="text-xs text-neutral-500">Заморозка ставит таймер на паузу и выгоняет пользователя из Steam.</p>
                  <button
                    onClick={() => handleToggleRentalFreeze(!frozen)}
                    disabled={rentalActionBusy}
                    className={`mt-3 w-full rounded-lg px-4 py-2 text-sm font-semibold transition disabled:cursor-not-allowed disabled:opacity-60 ${
                      frozen
                        ? "border border-emerald-200 bg-emerald-50 text-emerald-700 hover:bg-emerald-100"
                        : "border border-rose-200 bg-rose-50 text-rose-700 hover:bg-rose-100"
                    }`}
                  >
                    {frozen ? "Разморозить аренду" : "Заморозить аренду"}
                  </button>
                </div>
                <div className="rounded-xl border border-neutral-200 bg-neutral-50 p-4">
                  <div className="mb-2 text-sm font-semibold text-neutral-800">Продлить аренду</div>
                  <div className="grid grid-cols-2 gap-3">
                    <input
                      value={rentalExtendHours}
                      onChange={(e) => setRentalExtendHours(e.target.value)}
                      placeholder="Часы"
                      type="number"
                      min="0"
                      className="w-full rounded-lg border border-neutral-200 bg-white px-3 py-2 text-sm text-neutral-700 outline-none placeholder:text-neutral-400"
                    />
                    <input
                      value={rentalExtendMinutes}
                      onChange={(e) => setRentalExtendMinutes(e.target.value)}
                      placeholder="Минуты"
                      type="number"
                      min="0"
                      className="w-full rounded-lg border border-neutral-200 bg-white px-3 py-2 text-sm text-neutral-700 outline-none placeholder:text-neutral-400"
                    />
                  </div>
                  <button
                    onClick={handleExtendRental}
                    disabled={rentalActionBusy}
                    className="mt-3 w-full rounded-lg bg-neutral-900 px-4 py-2 text-sm font-semibold text-white transition hover:bg-neutral-800 disabled:cursor-not-allowed disabled:bg-neutral-300"
                  >
                    Extend rental
                  </button>
                </div>
                <div className="rounded-xl border border-neutral-200 bg-neutral-50 p-4">
                  <div className="mb-2 text-sm font-semibold text-neutral-800">Завершить аренду</div>
                  <p className="text-xs text-neutral-500">Останавливает аренду и освобождает аккаунт.</p>
                  <button
                    onClick={handleReleaseRental}
                    disabled={rentalActionBusy}
                    className="mt-3 w-full rounded-lg border border-neutral-200 bg-white px-3 py-2 text-sm font-semibold text-neutral-700 transition hover:bg-neutral-100 disabled:cursor-not-allowed disabled:text-neutral-400"
                  >
                    Release rental
                  </button>
                </div>
              </div>
            );
          })()
        ) : (
          <div className="rounded-xl border border-dashed border-neutral-200 bg-neutral-50 px-4 py-6 text-center text-sm text-neutral-500">
            Выберите активную аренду, чтобы открыть действия.
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="space-y-6">
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {statCards.map((card) => (
          <StatCard key={card.label} {...card} />
        ))}
      </div>

      <div className="grid items-start gap-4 lg:grid-cols-2">
        <div className="min-h-[880px] rounded-2xl border border-neutral-200 bg-white p-6 shadow-sm flex flex-col">
          <div className="mb-4 flex items-center justify-between">
            <h3 className="text-lg font-semibold text-neutral-900">Инвентарь</h3>
          </div>
          <div className="flex-1 min-h-0 overflow-x-hidden">
            <div className="flex h-full min-w-0 flex-col">
              <div className="mt-3 list-scroll dashboard-list-scroll flex-1 min-h-0">
                <div
                  className="sticky top-0 z-10 grid gap-4 bg-white px-6 py-2 text-xs font-semibold text-neutral-500"
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
                  {inventoryAccounts.map((acc, idx) => {
                    const rented = !!acc.owner;
                    const frozen = !!acc.accountFrozen;
                    const lowPriority = !!acc.lowPriority;
                  const stateLabel = lowPriority ? "Низкий приоритет" : frozen ? "Заморожен" : rented ? "В аренде" : "Свободен";
                  const stateClass = lowPriority
                    ? "bg-rose-50 text-rose-600"
                    : frozen
                      ? "bg-slate-100 text-slate-700"
                      : rented
                        ? "bg-amber-50 text-amber-700"
                        : "bg-emerald-50 text-emerald-600";
                  const workspaceLabel = formatWorkspaceLabel(acc.workspaceId, acc.workspaceName, workspaces);
                  const workspaceRecord = acc.workspaceId
                    ? workspaces.find((item) => item.id === acc.workspaceId)
                    : workspaces.find((item) => item.is_default) ?? null;
                  const workspaceBadge = workspaceRecord?.is_default
                    ? `${workspaceLabel} (По умолчанию)`
                    : workspaceLabel;
                  const lastRentedLabel = acc.lastRentedWorkspaceId
                    ? formatWorkspaceLabel(
                        acc.lastRentedWorkspaceId,
                        acc.lastRentedWorkspaceName,
                        workspaces,
                      )
                    : "-";
                  const lastRentedRecord = acc.lastRentedWorkspaceId
                    ? workspaces.find((item) => item.id === acc.lastRentedWorkspaceId)
                    : null;
                  const lastRentedBadge = lastRentedRecord?.is_default
                    ? `${lastRentedLabel} (По умолчанию)`
                    : lastRentedLabel;
                  const rowKey = acc.rowKey || `acc:${idx}`;
                  const isSelected = selectedRowKey === rowKey;
                  return (
                    <motion.div
                      key={rowKey}
                      role="button"
                      tabIndex={0}
                      onKeyDown={(event) => {
                        if (event.key === "Enter" || event.key === " ") {
                          event.preventDefault();
                          setSelectedRowKey((prev) =>
                            prev && prev === rowKey ? null : rowKey
                          );
                        }
                      }}
                      onClick={() =>
                        setSelectedRowKey((prev) =>
                          prev && prev === rowKey ? null : rowKey
                        )
                      }
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0, transition: { duration: 0.25, delay: idx * 0.03, ease: EASE } }}
                      className={`grid items-center gap-4 rounded-xl border px-6 py-4 text-sm shadow-[0_4px_18px_-14px_rgba(0,0,0,0.18)] transition ${
                        isSelected
                          ? "border-neutral-900/20 bg-white ring-2 ring-neutral-900/10"
                          : "border-neutral-100 bg-neutral-50 hover:border-neutral-200"
                      } cursor-pointer`}
                      style={{ gridTemplateColumns: INVENTORY_GRID }}
                    >
                      <span className="min-w-0 font-semibold text-neutral-900" title={String(acc.id)}>
                        {acc.id}
                      </span>
                      <div className="min-w-0">
                        <div className="truncate font-semibold leading-tight text-neutral-900" title={acc.name || "Аккаунт"}>
                          {acc.name || "Аккаунт"}
                        </div>
                        <div className="mt-1 flex flex-wrap gap-1">
                          <span className="inline-flex w-fit rounded-full bg-neutral-100 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-neutral-600">
                            Основной: {workspaceBadge}
                          </span>
                          <span className="inline-flex w-fit rounded-full bg-neutral-100 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-neutral-600">
                            Последняя аренда: {lastRentedBadge}
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
                      <span className="min-w-0 truncate font-mono text-xs leading-tight text-neutral-800 tabular-nums" title={acc.steamId || ""}>
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
                  {inventoryAccounts.length === 0 && (
                    <div className="rounded-xl border border-dashed border-neutral-200 bg-neutral-50 px-4 py-6 text-center text-sm text-neutral-500">
                      {emptyAccountMessage}
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>

        <div className="min-h-[880px] rounded-2xl border border-neutral-200 bg-white p-6 shadow-sm flex flex-col">
          <div className="mb-4 flex items-center justify-between">
            <h3 className="text-lg font-semibold text-neutral-900">Активные аренды</h3>
            <button className="rounded-lg border border-neutral-200 bg-neutral-50 px-3 py-2 text-xs text-neutral-600">Статус</button>
          </div>
          <div className="flex-1 min-h-0 overflow-x-hidden">
            <div className="flex h-full min-w-0 flex-col">
              <div className="mt-3 list-scroll dashboard-list-scroll flex-1 min-h-0">
                <div
                  className="sticky top-0 z-10 grid gap-4 bg-white px-6 py-2 text-xs font-semibold text-neutral-500"
                  style={{ gridTemplateColumns: RENTALS_GRID }}
                >
                  <span>ID</span>
                  <span>Аккаунт</span>
                  <span>Покупатель</span>
                  <span>Начало</span>
                  <span>Осталось</span>
                  <span>Время матча</span>
                  <span>Герой</span>
                  <span className="text-center">Статус</span>
                </div>
                <div className="mt-3 space-y-3">
                  {filteredRentals.map((row, idx) => {
                    const isSelected = selectedRowKey === row.rowKey;
                    const pill = statusPill(row.status);
                  const account = accountById.get(row.id);
                  const workspaceLabel = resolveWorkspaceName(
                    row.workspaceId ?? account?.workspaceId,
                    row.workspaceName ?? account?.workspaceName,
                    workspaces,
                  );
                  const workspaceRecord = row.workspaceId
                    ? workspaces.find((item) => item.id === row.workspaceId)
                    : workspaces.find((item) => item.is_default) ?? null;
                  const workspaceBadge = workspaceRecord?.is_default
                    ? `${workspaceLabel} (По умолчанию)`
                    : workspaceLabel;
                  return (
                    <motion.div
                      key={row.rowKey}
                      role="button"
                      tabIndex={0}
                      onKeyDown={(event) => {
                        if (event.key === "Enter" || event.key === " ") {
                          event.preventDefault();
                          setSelectedRowKey((prev) =>
                            prev && prev === row.rowKey ? null : row.rowKey
                          );
                        }
                      }}
                      onClick={() =>
                        setSelectedRowKey((prev) =>
                          prev && prev === row.rowKey ? null : row.rowKey
                        )
                      }
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0, transition: { duration: 0.25, delay: idx * 0.03, ease: EASE } }}
                      className={`grid items-center gap-4 rounded-xl border px-6 py-4 text-sm shadow-[0_4px_18px_-14px_rgba(0,0,0,0.18)] transition ${
                        isSelected
                          ? "border-neutral-900/20 bg-white ring-2 ring-neutral-900/10"
                          : "border-neutral-100 bg-neutral-50 hover:border-neutral-200"
                      } cursor-pointer`}
                      style={{ gridTemplateColumns: RENTALS_GRID }}
                    >
                      <span className="min-w-0 truncate font-semibold text-neutral-900">{row.id}</span>
                      <div className="min-w-0">
                        <div className="truncate text-neutral-800">{row.account}</div>
                        <span className="mt-1 inline-flex w-fit rounded-full bg-neutral-100 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-neutral-600">
                          {workspaceBadge}
                        </span>
                      </div>
                      <button
                        type="button"
                        className="min-w-0 truncate text-left text-neutral-700 hover:text-neutral-900"
                        onClick={(event) => {
                          event.stopPropagation();
                          if (row.buyer) {
                            setChatTarget({
                              buyer: row.buyer,
                              workspaceId: row.workspaceId ?? account?.workspaceId ?? null,
                            });
                          }
                        }}
                      >
                        {row.buyer || "-"}
                      </button>
                      <span className="min-w-0 truncate text-neutral-600">{row.started}</span>
                      <span className="min-w-0 truncate font-mono tabular-nums text-neutral-900">
                        {getCountdownLabel(accountById.get(row.id), row.timeLeft, now)}
                      </span>
                      <span className="min-w-0 truncate font-mono tabular-nums text-neutral-900">
                        {getMatchTimeLabel(row, now)}
                      </span>
                      <span className="min-w-0 truncate text-neutral-700">{row.hero}</span>
                      <div className="flex items-center justify-center">
                        <span className={`inline-flex w-fit rounded-full px-3 py-1 text-xs font-semibold ${pill.className}`}>
                          {pill.label}
                        </span>
                      </div>
                    </motion.div>
                  );
                  })}
                  {filteredRentals.length === 0 && (
                    <div className="rounded-xl border border-dashed border-neutral-200 bg-neutral-50 px-4 py-6 text-center text-sm text-neutral-500">
                      {emptyRentalMessage}
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        {renderAccountActionsPanel()}
        {renderRentalActionsPanel()}
      </div>
      <BuyerChatPanel
        open={!!chatTarget}
        buyer={chatTarget?.buyer}
        workspaceId={chatTarget?.workspaceId ?? workspaceId}
        onClose={() => setChatTarget(null)}
      />
    </div>
  );
};

export default DashboardPage;
