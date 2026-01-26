import React, { useEffect, useMemo, useState } from "react";
import { motion } from "framer-motion";

import { api, ActiveRentalItem, AccountItem } from "../../services/api";

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

const RENTALS_GRID =
  "minmax(64px,0.6fr) minmax(180px,1.4fr) minmax(160px,1.1fr) minmax(140px,1fr) minmax(120px,0.8fr) minmax(110px,0.8fr) minmax(140px,1fr) minmax(110px,0.7fr)";
const EASE: [number, number, number, number] = [0.22, 1, 0.36, 1];

const statusPill = (status?: string) => {
  const lower = (status || "").toLowerCase();
  if (lower.includes("frozen")) return { className: "bg-slate-100 text-slate-700", label: "Frozen" };
  if (lower.includes("match")) return { className: "bg-emerald-50 text-emerald-600", label: "In match" };
  if (lower.includes("game")) return { className: "bg-amber-50 text-amber-600", label: "In game" };
  if (lower.includes("online") || lower === "1" || lower === "true") return { className: "bg-emerald-50 text-emerald-600", label: "Online" };
  if (lower.includes("idle") || lower.includes("away")) return { className: "bg-amber-50 text-amber-600", label: "Idle" };
  if (lower.includes("off") || lower === "" || lower === "0") return { className: "bg-rose-50 text-rose-600", label: "Offline" };
  return { className: "bg-neutral-100 text-neutral-600", label: status || "Unknown" };
};

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

type ActiveRentalsPageProps = {
  onToast?: (message: string, isError?: boolean) => void;
};

const formatDuration = (minutesTotal: number | null | undefined) => {
  if (!minutesTotal && minutesTotal !== 0) return "-";
  const minutes = Math.max(0, Math.floor(minutesTotal));
  const hours = Math.floor(minutes / 60);
  const rem = minutes % 60;
  return `${hours}h ${rem}m`;
};

const parseUtcMs = (value?: string | null) => {
  if (!value) return null;
  const normalized = value.includes("T") ? value : value.replace(" ", "T");
  const hasZone = /[zZ]|[+-]\d{2}:?\d{2}$/.test(normalized);
  const ts = Date.parse(hasZone ? normalized : `${normalized}Z`);
  return Number.isNaN(ts) ? null : ts;
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
  return `${hours} ч ${minutesLeft} мин ${seconds} сек`;
};

const ActiveRentalsPage: React.FC<ActiveRentalsPageProps> = ({ onToast }) => {
  const [rentals, setRentals] = useState<RentalRow[]>([]);
  const [accounts, setAccounts] = useState<AccountRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [now, setNow] = useState(Date.now());
  const [selectedRentalId, setSelectedRentalId] = useState<number | null>(null);
  const [assignOwner, setAssignOwner] = useState("");
  const [accountEditName, setAccountEditName] = useState("");
  const [accountEditLogin, setAccountEditLogin] = useState("");
  const [accountEditPassword, setAccountEditPassword] = useState("");
  const [accountEditMmr, setAccountEditMmr] = useState("");
  const [rentalExtendHours, setRentalExtendHours] = useState("");
  const [rentalExtendMinutes, setRentalExtendMinutes] = useState("");
  const [accountActionBusy, setAccountActionBusy] = useState(false);
  const [rentalActionBusy, setRentalActionBusy] = useState(false);

  const selectedRental = useMemo(
    () => rentals.find((row) => row.id === selectedRentalId) ?? null,
    [rentals, selectedRentalId],
  );
  const selectedAccount = useMemo(
    () => accounts.find((acc) => acc.id === selectedRentalId) ?? null,
    [accounts, selectedRentalId],
  );
  const accountById = useMemo(() => new Map(accounts.map((acc) => [acc.id, acc])), [accounts]);

  const loadRentals = async () => {
    setLoading(true);
    try {
      const res = await api.listActiveRentals();
      setRentals(res.items.map(mapRental));
    } catch {
      setRentals([]);
    } finally {
      setLoading(false);
    }
  };

  const loadAccounts = async () => {
    try {
      const res = await api.listAccounts();
      setAccounts(res.items.map(mapAccount));
    } catch {
      setAccounts([]);
    }
  };

  useEffect(() => {
    void loadRentals();
    void loadAccounts();
  }, []);

  useEffect(() => {
    const id = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(id);
  }, []);

  useEffect(() => {
    if (selectedRentalId && !rentals.some((row) => row.id === selectedRentalId)) {
      setSelectedRentalId(null);
    }
  }, [rentals, selectedRentalId]);

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
    setAccountEditMmr(selectedAccount.mmr !== "-" && selectedAccount.mmr !== undefined ? String(selectedAccount.mmr) : "");
  }, [selectedAccount]);

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
    if (!selectedAccount) {
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
    if (!selectedAccount) {
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
    if (!selectedAccount) {
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

  const renderAccountActionsPanel = (title = "Account actions") => {
    return (
      <div className="rounded-2xl border border-neutral-200 bg-white p-6 shadow-sm shadow-neutral-200/70">
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-lg font-semibold text-neutral-900">{title}</h3>
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
            const passwordChanged = accountEditPassword.trim() && accountEditPassword.trim() !== (selectedAccount.password || "");
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
                  <span>
                    Time left:{" "}
                    {selectedRental
                      ? getCountdownLabel(accountById.get(selectedRental.id), selectedRental.timeLeft, now)
                      : "-"}
                  </span>
                    <span>Match time: {selectedRental.matchTime || "-"}</span>
                    <span>Hero: {selectedRental.hero || "-"}</span>
                    <span>Workspace: Default</span>
                    <span>Started: {selectedRental.started || "-"}</span>
                    {frozen && (
                      <span className="text-rose-600">Frozen: timer paused until you unfreeze.</span>
                    )}
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
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold text-neutral-900">Active Rentals</h1>

      <div className="flex flex-wrap items-center gap-3">
        <div className="rounded-full bg-neutral-900 px-4 py-2 text-sm font-semibold text-white">
          {rentals.length} active rentals
        </div>
        <div className="text-sm text-neutral-500">Updated live every second</div>
      </div>

      <div className="rounded-2xl border border-neutral-200 bg-white p-6 shadow-sm shadow-neutral-200/70">
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
                const isSelected = selectedRentalId !== null && String(selectedRentalId) === String(row.id);
                const pill = statusPill(row.status);
                return (
                  <motion.div
                    key={row.id}
                    role="button"
                    tabIndex={0}
                    onKeyDown={(event) => {
                      if (event.key === "Enter" || event.key === " ") {
                        event.preventDefault();
                        setSelectedRentalId((prev) =>
                          prev !== null && String(prev) === String(row.id) ? null : row.id
                        );
                      }
                    }}
                    onClick={() =>
                      setSelectedRentalId((prev) => (prev !== null && String(prev) === String(row.id) ? null : row.id))
                    }
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
                    <span className="min-w-0 truncate font-mono text-neutral-900">
                      {getCountdownLabel(accountById.get(row.id), row.timeLeft, now)}
                    </span>
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
              {rentals.length === 0 && !loading && (
                <div className="rounded-xl border border-dashed border-neutral-200 bg-neutral-50 px-4 py-6 text-center text-sm text-neutral-500">
                  No active rentals yet.
                </div>
              )}
              {loading && (
                <div className="rounded-xl border border-dashed border-neutral-200 bg-neutral-50 px-4 py-6 text-center text-sm text-neutral-500">
                  Loading rentals...
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        {renderAccountActionsPanel("Account actions")}
        {renderRentalActionsPanel()}
      </div>
    </div>
  );
};

export default ActiveRentalsPage;
