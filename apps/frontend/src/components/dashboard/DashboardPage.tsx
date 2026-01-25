import React, { useEffect, useMemo, useState } from "react";
import { motion } from "framer-motion";

import { api, AccountItem, ActiveRentalItem } from "../../services/api";

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

type AccountRow = {
  id: number;
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
};

type RentalRow = {
  id: number;
  account: string;
  buyer: string;
  started: string;
  timeLeft: string;
  matchTime: string;
  hero: string;
  status: string;
};

const INVENTORY_GRID =
  "minmax(72px,0.6fr) minmax(180px,1.4fr) minmax(140px,1fr) minmax(140px,1fr) minmax(190px,1.1fr) minmax(80px,0.6fr) minmax(110px,0.6fr)";

const RENTALS_GRID =
  "minmax(64px,0.6fr) minmax(180px,1.4fr) minmax(160px,1.1fr) minmax(140px,1fr) minmax(120px,0.8fr) minmax(110px,0.8fr) minmax(140px,1fr) minmax(110px,0.7fr)";

const mapAccount = (item: AccountItem): AccountRow => ({
  id: item.id,
  name: item.account_name,
  login: item.login,
  password: item.password || "",
  steamId: item.steam_id ?? "",
  mmr: item.mmr ?? "-",
  owner: item.owner ?? null,
  rentalStart: item.rental_start ?? null,
  rentalDuration: item.rental_duration ?? 0,
  rentalDurationMinutes: item.rental_duration_minutes ?? null,
  accountFrozen: !!item.account_frozen,
  rentalFrozen: !!item.rental_frozen,
});

const mapRental = (item: ActiveRentalItem): RentalRow => ({
  id: item.id,
  account: item.account,
  buyer: item.buyer,
  started: item.started,
  timeLeft: item.time_left,
  matchTime: item.match_time || "-",
  hero: item.hero || "-",
  status: item.status || "",
});

const formatDuration = (minutesTotal: number | null | undefined) => {
  if (!minutesTotal && minutesTotal !== 0) return "-";
  const minutes = Math.max(0, Math.floor(minutesTotal));
  const hours = Math.floor(minutes / 60);
  const rem = minutes % 60;
  return `${hours}h ${rem}m`;
};

const statusPill = (status?: string) => {
  const lower = (status || "").toLowerCase();
  if (lower.includes("frozen")) return { className: "bg-slate-100 text-slate-700", label: "Frozen" };
  if (lower.includes("match")) return { className: "bg-emerald-50 text-emerald-600", label: "In match" };
  if (lower.includes("game")) return { className: "bg-amber-50 text-amber-600", label: "In game" };
  if (lower.includes("online") || lower === "1" || lower === "true")
    return { className: "bg-emerald-50 text-emerald-600", label: "Online" };
  if (lower.includes("idle") || lower.includes("away"))
    return { className: "bg-amber-50 text-amber-600", label: "Idle" };
  if (lower.includes("off") || lower === "" || lower === "0")
    return { className: "bg-rose-50 text-rose-600", label: "Offline" };
  return { className: "bg-neutral-100 text-neutral-600", label: status || "Unknown" };
};

type DashboardPageProps = {
  onToast?: (message: string, isError?: boolean) => void;
};

const DashboardPage: React.FC<DashboardPageProps> = ({ onToast }) => {
  const statCards: StatCardProps[] = [
    { label: "Total Accounts", value: 20, delta: "+12%", deltaTone: "up", icon: <CardUsersIcon /> },
    { label: "Active Rentals", value: 0, delta: "-3%", deltaTone: "down", icon: <CardUsersIcon /> },
    { label: "Free Accounts", value: 20, delta: "+6%", deltaTone: "up", icon: <CardCloudCheckIcon /> },
    { label: "Past 24h", value: 0, delta: "+2%", deltaTone: "up", icon: <CardBarsIcon /> },
  ];

  const [accounts, setAccounts] = useState<AccountRow[]>([]);
  const [rentals, setRentals] = useState<RentalRow[]>([]);
  const [loadingAccounts, setLoadingAccounts] = useState(true);
  const [loadingRentals, setLoadingRentals] = useState(true);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [assignOwner, setAssignOwner] = useState("");
  const [accountEditName, setAccountEditName] = useState("");
  const [accountEditLogin, setAccountEditLogin] = useState("");
  const [accountEditPassword, setAccountEditPassword] = useState("");
  const [accountEditMmr, setAccountEditMmr] = useState("");
  const [rentalExtendHours, setRentalExtendHours] = useState("");
  const [rentalExtendMinutes, setRentalExtendMinutes] = useState("");
  const [accountActionBusy, setAccountActionBusy] = useState(false);
  const [rentalActionBusy, setRentalActionBusy] = useState(false);

  const selectedAccount = useMemo(
    () => accounts.find((acc) => acc.id === selectedId) ?? null,
    [accounts, selectedId],
  );
  const selectedRental = useMemo(
    () => rentals.find((row) => row.id === selectedId) ?? null,
    [rentals, selectedId],
  );

  const loadAccounts = async () => {
    setLoadingAccounts(true);
    try {
      const res = await api.listAccounts();
      setAccounts((res.items || []).map(mapAccount));
    } catch {
      setAccounts([]);
    } finally {
      setLoadingAccounts(false);
    }
  };

  const loadRentals = async () => {
    setLoadingRentals(true);
    try {
      const res = await api.listActiveRentals();
      setRentals(res.items.map(mapRental));
    } catch {
      setRentals([]);
    } finally {
      setLoadingRentals(false);
    }
  };

  useEffect(() => {
    void loadAccounts();
    void loadRentals();
  }, []);

  useEffect(() => {
    if (selectedId && !accounts.some((acc) => acc.id === selectedId) && !rentals.some((r) => r.id === selectedId)) {
      setSelectedId(null);
    }
  }, [accounts, rentals, selectedId]);

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

  const emptyAccountMessage = loadingAccounts ? "Loading accounts..." : "No accounts loaded yet.";
  const emptyRentalMessage = loadingRentals ? "Loading rentals..." : "No active rentals yet.";

  const handleAssignAccount = async () => {
    if (!selectedAccount) {
      onToast?.("Select an account first.", true);
      return;
    }
    if (accountActionBusy) return;
    if (selectedAccount.accountFrozen) {
      onToast?.("Unfreeze the account before assigning a buyer.", true);
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
      await api.assignAccount(selectedAccount.id, owner);
      onToast?.("Rental assigned.");
      setAssignOwner("");
      await Promise.all([loadAccounts(), loadRentals()]);
    } catch (err) {
      const message = (err as { message?: string })?.message || "Failed to assign rental.";
      onToast?.(message, true);
    } finally {
      setAccountActionBusy(false);
    }
  };

  const handleUpdateAccount = async () => {
    if (!selectedAccount) {
      onToast?.("Select an account first.", true);
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
        onToast?.("MMR must be 0 or higher.", true);
        return;
      }
      if (String(mmr) !== String(selectedAccount.mmr ?? "")) payload.mmr = mmr;
    }

    if (!Object.keys(payload).length) {
      onToast?.("No changes to save.", true);
      return;
    }

    setAccountActionBusy(true);
    try {
      await api.updateAccount(selectedAccount.id, payload);
      onToast?.("Account updated.");
      await Promise.all([loadAccounts(), loadRentals()]);
    } catch (err) {
      const message = (err as { message?: string })?.message || "Failed to update account.";
      onToast?.(message, true);
    } finally {
      setAccountActionBusy(false);
    }
  };

  const handleExtendRental = async () => {
    if (!selectedRental || !selectedAccount) {
      onToast?.("Select a rental first.", true);
      return;
    }
    if (rentalActionBusy) return;
    const hours = Number(rentalExtendHours || 0);
    const minutes = Number(rentalExtendMinutes || 0);
    if (!Number.isFinite(hours) || !Number.isFinite(minutes) || hours < 0 || minutes < 0) {
      onToast?.("Enter valid hours and minutes.", true);
      return;
    }
    if (hours * 60 + minutes <= 0) {
      onToast?.("Extension must be greater than 0.", true);
      return;
    }
    setRentalActionBusy(true);
    try {
      await api.extendAccount(selectedAccount.id, hours, minutes);
      onToast?.("Rental extended.");
      setRentalExtendHours("");
      setRentalExtendMinutes("");
      await Promise.all([loadAccounts(), loadRentals()]);
    } catch (err) {
      const message = (err as { message?: string })?.message || "Failed to extend rental.";
      onToast?.(message, true);
    } finally {
      setRentalActionBusy(false);
    }
  };

  const handleReleaseRental = async () => {
    if (!selectedRental || !selectedAccount) {
      onToast?.("Select a rental first.", true);
      return;
    }
    if (rentalActionBusy) return;
    setRentalActionBusy(true);
    try {
      await api.releaseAccount(selectedAccount.id);
      onToast?.("Rental released.");
      await Promise.all([loadAccounts(), loadRentals()]);
    } catch (err) {
      const message = (err as { message?: string })?.message || "Failed to release rental.";
      onToast?.(message, true);
    } finally {
      setRentalActionBusy(false);
    }
  };

  const handleToggleRentalFreeze = async (nextFrozen: boolean) => {
    if (!selectedRental || !selectedAccount) {
      onToast?.("Select a rental first.", true);
      return;
    }
    if (rentalActionBusy) return;
    setRentalActionBusy(true);
    try {
      await api.freezeRental(selectedAccount.id, nextFrozen);
      onToast?.(nextFrozen ? "Rental frozen." : "Rental unfrozen.");
      await Promise.all([loadAccounts(), loadRentals()]);
    } catch (err) {
      const message = (err as { message?: string })?.message || "Failed to update rental freeze state.";
      onToast?.(message, true);
    } finally {
      setRentalActionBusy(false);
    }
  };

  const renderAccountActionsPanel = () => {
    return (
      <div className="rounded-2xl border border-neutral-200 bg-white p-6 shadow-sm shadow-neutral-200/70">
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-lg font-semibold text-neutral-900">Account actions</h3>
          <span className="text-xs text-neutral-500">{selectedAccount ? "Ready" : "Select an account"}</span>
        </div>
        {selectedAccount ? (
          (() => {
            const rented = !!selectedAccount.owner;
            const frozen = !!selectedAccount.accountFrozen;
            const stateLabel = frozen ? "Frozen" : rented ? "Rented out" : "Available";
            const stateClass = frozen
              ? "bg-slate-100 text-slate-700"
              : rented
                ? "bg-amber-50 text-amber-700"
                : "bg-emerald-50 text-emerald-600";
            const ownerLabel = selectedAccount.owner ? String(selectedAccount.owner) : "-";
            const totalMinutes =
              selectedAccount.rentalDurationMinutes ??
              (selectedAccount.rentalDuration ? selectedAccount.rentalDuration * 60 : null);
            const hoursLabel = formatDuration(totalMinutes);
            const canAssign = !selectedAccount.owner && !frozen;
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
                        Selected account
                      </div>
                      <div className="mt-1 text-sm font-semibold text-neutral-900">
                        {selectedAccount.name || "Account"}
                      </div>
                    </div>
                    <span className={`rounded-full px-3 py-1 text-xs font-semibold ${stateClass}`}>{stateLabel}</span>
                  </div>
                  <div className="mt-3 grid gap-1 text-xs text-neutral-600">
                    <span>Login: {selectedAccount.login || "-"}</span>
                    <span>Steam ID: {selectedAccount.steamId || "-"}</span>
                    <span>Owner: {ownerLabel}</span>
                    <span>Workspace: Default</span>
                    <span>Rental start: {selectedAccount.rentalStart || "-"}</span>
                    <span>Duration: {hoursLabel}</span>
                  </div>
                </div>
                <div className="rounded-xl border border-neutral-200 bg-neutral-50 p-4">
                  <div className="mb-2 text-sm font-semibold text-neutral-800">Assign rental</div>
                  <p className="text-xs text-neutral-500">The countdown starts after the buyer requests the code.</p>
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
                      Assign rental
                    </button>
                    {!canAssign && (
                      <div className="text-xs text-neutral-500">
                        {frozen ? "Unfreeze the account before assigning a buyer." : "Release the account first."}
                      </div>
                    )}
                  </div>
                </div>
                <div className="rounded-xl border border-neutral-200 bg-neutral-50 p-4">
                  <div className="mb-2 text-sm font-semibold text-neutral-800">Update account</div>
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
                        placeholder="Login"
                        className="w-full rounded-lg border border-neutral-200 bg-white px-3 py-2 text-sm text-neutral-700 outline-none placeholder:text-neutral-400"
                      />
                      <input
                        value={accountEditPassword}
                        onChange={(e) => setAccountEditPassword(e.target.value)}
                        placeholder="Password"
                        className="w-full rounded-lg border border-neutral-200 bg-white px-3 py-2 text-sm text-neutral-700 outline-none placeholder:text-neutral-400"
                      />
                    </div>
                    <div className="space-y-1">
                      <label className="text-xs font-semibold uppercase tracking-wide text-neutral-500">Workspace</label>
                      <select
                        value="default"
                        disabled
                        className="w-full rounded-lg border border-neutral-200 bg-white px-3 py-2 text-sm text-neutral-700 outline-none"
                      >
                        <option value="default">Default workspace</option>
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
                    <div className="mt-2 text-xs text-rose-500">MMR must be 0 or higher.</div>
                  )}
                  <button
                    onClick={handleUpdateAccount}
                    disabled={accountActionBusy || !hasChanges || !editMmrValid}
                    className="mt-3 w-full rounded-lg bg-neutral-900 px-4 py-2 text-sm font-semibold text-white transition hover:bg-neutral-800 disabled:cursor-not-allowed disabled:bg-neutral-300"
                  >
                    Save changes
                  </button>
                </div>
              </div>
            );
          })()
        ) : (
          <div className="rounded-xl border border-dashed border-neutral-200 bg-neutral-50 px-4 py-6 text-center text-sm text-neutral-500">
            Select an account to unlock account actions.
          </div>
        )}
      </div>
    );
  };

  const renderRentalActionsPanel = () => {
    return (
      <div className="rounded-2xl border border-neutral-200 bg-white p-6 shadow-sm shadow-neutral-200/70">
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-lg font-semibold text-neutral-900">Rental actions</h3>
          <span className="text-xs text-neutral-500">{selectedRental ? "Ready" : "Select a rental"}</span>
        </div>
        {selectedRental ? (
          (() => {
            const frozen = !!selectedAccount?.rentalFrozen;
            const pill = statusPill(frozen ? "Frozen" : selectedRental.status);
            const presenceLabel = pill.label;
            return (
              <div className="space-y-4">
                <div className="rounded-xl border border-neutral-200 bg-neutral-50 p-4">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <div className="text-xs font-semibold uppercase tracking-wide text-neutral-500">
                        Selected rental
                      </div>
                      <div className="mt-1 text-sm font-semibold text-neutral-900">
                        {selectedRental.account || "Rental"}
                      </div>
                    </div>
                    <span className={`rounded-full px-3 py-1 text-xs font-semibold ${pill.className}`}>{presenceLabel}</span>
                  </div>
                  <div className="mt-3 grid gap-1 text-xs text-neutral-600">
                    <span>Buyer: {selectedRental.buyer || "-"}</span>
                    <span>Time left: {selectedRental.timeLeft || "-"}</span>
                    <span>Match time: {selectedRental.matchTime || "-"}</span>
                    <span>Hero: {selectedRental.hero || "-"}</span>
                    <span>Workspace: Default</span>
                    <span>Started: {selectedRental.started || "-"}</span>
                    {frozen && <span className="text-rose-600">Frozen: timer paused until you unfreeze.</span>}
                  </div>
                </div>
                <div className="rounded-xl border border-neutral-200 bg-neutral-50 p-4">
                  <div className="mb-2 text-sm font-semibold text-neutral-800">Freeze rental</div>
                  <p className="text-xs text-neutral-500">Freezing pauses the timer and kicks the user from Steam.</p>
                  <button
                    onClick={() => handleToggleRentalFreeze(!frozen)}
                    disabled={rentalActionBusy}
                    className={`mt-3 w-full rounded-lg px-4 py-2 text-sm font-semibold transition disabled:cursor-not-allowed disabled:opacity-60 ${
                      frozen
                        ? "border border-emerald-200 bg-emerald-50 text-emerald-700 hover:bg-emerald-100"
                        : "border border-rose-200 bg-rose-50 text-rose-700 hover:bg-rose-100"
                    }`}
                  >
                    {frozen ? "Unfreeze rental" : "Freeze rental"}
                  </button>
                </div>
                <div className="rounded-xl border border-neutral-200 bg-neutral-50 p-4">
                  <div className="mb-2 text-sm font-semibold text-neutral-800">Extend rental</div>
                  <div className="grid grid-cols-2 gap-3">
                    <input
                      value={rentalExtendHours}
                      onChange={(e) => setRentalExtendHours(e.target.value)}
                      placeholder="Hours"
                      type="number"
                      min="0"
                      className="w-full rounded-lg border border-neutral-200 bg-white px-3 py-2 text-sm text-neutral-700 outline-none placeholder:text-neutral-400"
                    />
                    <input
                      value={rentalExtendMinutes}
                      onChange={(e) => setRentalExtendMinutes(e.target.value)}
                      placeholder="Minutes"
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
                  <div className="mb-2 text-sm font-semibold text-neutral-800">End rental</div>
                  <p className="text-xs text-neutral-500">Stops the rental and releases the account.</p>
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
            Select an active rental to unlock actions.
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

      <div className="grid gap-4 lg:grid-cols-2">
        <div className="min-h-[880px] rounded-2xl border border-neutral-200 bg-white p-6 shadow-sm">
          <div className="mb-4 flex items-center justify-between">
            <h3 className="text-lg font-semibold text-neutral-900">Inventory</h3>
          </div>
          <div className="overflow-x-auto">
            <div className="min-w-[1000px]">
              <div className="grid gap-3 px-6 text-xs font-semibold text-neutral-500" style={{ gridTemplateColumns: INVENTORY_GRID }}>
                <span>ID</span>
                <span>Name</span>
                <span>Login</span>
                <span>Password</span>
                <span>Steam ID</span>
                <span>MMR</span>
                <span className="text-right">State</span>
              </div>
              <div className="mt-3 space-y-3 overflow-y-auto overflow-x-hidden pr-1" style={{ maxHeight: "640px" }}>
                {accounts.map((acc, idx) => {
                  const rented = !!acc.owner;
                  const frozen = !!acc.accountFrozen;
                  const stateLabel = frozen ? "Frozen" : rented ? "Rented out" : "Available";
                  const stateClass = frozen
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
                      onClick={() => setSelectedId((prev) => (prev !== null && String(prev) === String(rowId) ? null : rowId))}
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0, transition: { duration: 0.25, delay: idx * 0.03, ease: EASE } }}
                      className={`grid min-w-full items-center gap-3 rounded-xl border px-6 py-4 text-sm shadow-[0_4px_18px_-14px_rgba(0,0,0,0.18)] transition ${
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
                        <span className="mt-1 inline-flex w-fit rounded-full bg-neutral-100 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-neutral-600">
                          Default
                        </span>
                      </div>
                      <span className="min-w-0 truncate text-neutral-700" title={acc.login || ""}>
                        {acc.login || ""}
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
                      <span className={`justify-self-end rounded-full px-3 py-1 text-xs font-semibold ${stateClass}`}>
                        {stateLabel}
                      </span>
                    </motion.div>
                  );
                })}
                {accounts.length === 0 && (
                  <div className="rounded-xl border border-dashed border-neutral-200 bg-neutral-50 px-4 py-6 text-center text-sm text-neutral-500">
                    {emptyAccountMessage}
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>

        <div className="min-h-[880px] rounded-2xl border border-neutral-200 bg-white p-6 shadow-sm">
          <div className="mb-4 flex items-center justify-between">
            <h3 className="text-lg font-semibold text-neutral-900">Active rentals</h3>
            <button className="rounded-lg border border-neutral-200 bg-neutral-50 px-3 py-2 text-xs text-neutral-600">Status</button>
          </div>
          <div className="overflow-x-auto">
            <div className="min-w-[1100px]">
              <div className="grid gap-3 px-6 text-xs font-semibold text-neutral-500" style={{ gridTemplateColumns: RENTALS_GRID }}>
                <span>ID</span>
                <span>Account</span>
                <span>Buyer</span>
                <span>Started</span>
                <span>Time Left</span>
                <span>Match Time</span>
                <span>Hero</span>
                <span>Status</span>
              </div>
              <div className="mt-3 space-y-3 overflow-y-auto overflow-x-hidden pr-1" style={{ maxHeight: "640px" }}>
                {rentals.map((row, idx) => {
                  const isSelected = selectedId !== null && String(selectedId) === String(row.id);
                  const pill = statusPill(row.status);
                  return (
                    <motion.div
                      key={row.id}
                      role="button"
                      tabIndex={0}
                      onKeyDown={(event) => {
                        if (event.key === "Enter" || event.key === " ") {
                          event.preventDefault();
                          setSelectedId((prev) => (prev !== null && String(prev) === String(row.id) ? null : row.id));
                        }
                      }}
                      onClick={() => setSelectedId((prev) => (prev !== null && String(prev) === String(row.id) ? null : row.id))}
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0, transition: { duration: 0.25, delay: idx * 0.03, ease: EASE } }}
                      className={`grid items-center gap-3 rounded-xl border px-6 py-4 text-sm shadow-[0_4px_18px_-14px_rgba(0,0,0,0.18)] transition ${
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
                          Default
                        </span>
                      </div>
                      <span className="min-w-0 truncate text-neutral-700">{row.buyer}</span>
                      <span className="min-w-0 truncate text-neutral-600">{row.started}</span>
                      <span className="min-w-0 truncate font-mono text-neutral-900">{row.timeLeft}</span>
                      <span className="min-w-0 truncate font-mono text-neutral-900">{row.matchTime}</span>
                      <span className="min-w-0 truncate text-neutral-700">{row.hero}</span>
                      <div className="flex items-center gap-2">
                        <span className={`inline-flex w-fit justify-self-start rounded-full px-3 py-1 text-xs font-semibold ${pill.className}`}>
                          {pill.label}
                        </span>
                      </div>
                    </motion.div>
                  );
                })}
                {rentals.length === 0 && (
                  <div className="rounded-xl border border-dashed border-neutral-200 bg-neutral-50 px-4 py-6 text-center text-sm text-neutral-500">
                    {emptyRentalMessage}
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        {renderAccountActionsPanel()}
        {renderRentalActionsPanel()}
      </div>
    </div>
  );
};

export default DashboardPage;
