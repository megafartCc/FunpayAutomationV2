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
  mmr: item.mmr ?? "-",
  workspaceId: item.workspace_id ?? null,
  workspaceName: item.workspace_name ?? null,
  lastRentedWorkspaceId: item.last_rented_workspace_id ?? null,
  lastRentedWorkspaceName: item.last_rented_workspace_name ?? null,
  owner: item.owner ?? null,
  rentalStart: item.rental_start ?? null,
  rentalDuration: item.rental_duration ?? 0,
  rentalDurationMinutes: item.rental_duration_minutes ?? null,
  accountFrozen: !!item.account_frozen,
  rentalFrozen: !!item.rental_frozen,
  lowPriority: !!item.low_priority,
});

type InventoryPageProps = {
  onToast?: (message: string, isError?: boolean) => void;
};

const formatDuration = (minutesTotal: number | null | undefined) => {
  if (!minutesTotal && minutesTotal !== 0) return "-";
  const minutes = Math.max(0, Math.floor(minutesTotal));
  const hours = Math.floor(minutes / 60);
  const rem = minutes % 60;
  return `${hours}h ${rem}m`;
};

const stratzUrl = (steamId?: string | null) => {
  const trimmed = steamId?.trim();
  if (!trimmed) return null;
  return `https://stratz.com/search/${trimmed}`;
};

const InventoryPage: React.FC<InventoryPageProps> = ({ onToast }) => {
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
  const { workspaces } = useWorkspace();

  const resolveWorkspaceName = (workspaceName?: string | null, workspaceId?: number | null) => {
    if (workspaceName) return workspaceName;
    if (workspaceId) {
      const match = workspaces.find((item) => item.id === workspaceId);
      if (match?.name) return match.name;
    }
    const fallback = workspaces.find((item) => item.is_default);
    if (fallback?.name) return fallback.name;
    if (workspaceId) return `Workspace ${workspaceId}`;
    return "Workspace";
  };

  const formatWorkspaceLabel = (workspaceName?: string | null, workspaceId?: number | null) => {
    const label = resolveWorkspaceName(workspaceName, workspaceId);
    return workspaceId ? `${label} (ID ${workspaceId})` : label;
  };

  const selectedAccount = useMemo(
    () => accounts.find((acc) => acc.id === selectedId) ?? null,
    [accounts, selectedId],
  );

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
      setError((err as { message?: string })?.message || "Failed to load accounts.");
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
    ? "Loading accounts..."
    : error
      ? `Failed to load accounts: ${error}`
      : "No accounts loaded yet.";

  const handleAssignAccount = async () => {
    if (!selectedAccount) {
      onToast?.("Select an account first.", true);
      return;
    }
    if (accountActionBusy) return;
    if (selectedAccount.lowPriority) {
      onToast?.("Remove low priority before assigning a buyer.", true);
      return;
    }
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
      const workspaceId =
        selectedAccount.workspaceId ?? selectedAccount.lastRentedWorkspaceId ?? undefined;
      await api.assignAccount(selectedAccount.id, owner, workspaceId);
      onToast?.("Rental assigned.");
      setAssignOwner("");
      await loadAccounts();
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
    if (
      accountEditWorkspaceId !== null &&
      accountEditWorkspaceId !== (selectedAccount.workspaceId ?? null)
    ) {
      payload.workspace_id = accountEditWorkspaceId;
    }

    if (!Object.keys(payload).length) {
      onToast?.("No changes to save.", true);
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
      const message = (err as { message?: string })?.message || "Failed to update account.";
      onToast?.(message, true);
    } finally {
      setAccountActionBusy(false);
    }
  };

  const handleToggleAccountFreeze = async (nextFrozen: boolean) => {
    if (!selectedAccount) {
      onToast?.("Select an account first.", true);
      return;
    }
    if (accountControlBusy) return;
    setAccountControlBusy(true);
    try {
      const workspaceId =
        selectedAccount.workspaceId ?? selectedAccount.lastRentedWorkspaceId ?? undefined;
      await api.freezeAccount(selectedAccount.id, nextFrozen, workspaceId);
      onToast?.(nextFrozen ? "Account frozen." : "Account unfrozen.");
      await loadAccounts();
    } catch (err) {
      const message = (err as { message?: string })?.message || "Failed to update freeze state.";
      onToast?.(message, true);
    } finally {
      setAccountControlBusy(false);
    }
  };

  const handleToggleLowPriority = async (nextLowPriority: boolean) => {
    if (!selectedAccount) {
      onToast?.("Select an account first.", true);
      return;
    }
    if (accountControlBusy) return;
    setAccountControlBusy(true);
    try {
      const workspaceId =
        selectedAccount.workspaceId ?? selectedAccount.lastRentedWorkspaceId ?? undefined;
      await api.setLowPriority(selectedAccount.id, nextLowPriority, workspaceId);
      onToast?.(nextLowPriority ? "Marked as low priority." : "Low priority removed.");
      await loadAccounts();
    } catch (err) {
      const message = (err as { message?: string })?.message || "Failed to update low priority.";
      onToast?.(message, true);
    } finally {
      setAccountControlBusy(false);
    }
  };

  const handleDeleteAccount = async () => {
    if (!selectedAccount) {
      onToast?.("Select an account first.", true);
      return;
    }
    if (accountControlBusy) return;
    if (!window.confirm(`Delete ${selectedAccount.name}?`)) return;
    setAccountControlBusy(true);
    try {
      const workspaceId =
        selectedAccount.workspaceId ?? selectedAccount.lastRentedWorkspaceId ?? undefined;
      await api.deleteAccount(selectedAccount.id, workspaceId);
      onToast?.("Account deleted.");
      await loadAccounts();
    } catch (err) {
      const message = (err as { message?: string })?.message || "Failed to delete account.";
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
          <span className="text-xs text-neutral-500">{selectedAccount ? "Ready" : "Select an account"}</span>
        </div>
        {selectedAccount ? (
          (() => {
            const rented = !!selectedAccount.owner;
            const frozen = !!selectedAccount.accountFrozen;
            const lowPriority = !!selectedAccount.lowPriority;
            const stateLabel = lowPriority ? "Low Priority" : frozen ? "Frozen" : rented ? "Rented out" : "Available";
            const stateClass = lowPriority
              ? "bg-rose-50 text-rose-600"
              : frozen
                ? "bg-slate-100 text-slate-700"
                : rented
                  ? "bg-amber-50 text-amber-700"
                  : "bg-emerald-50 text-emerald-600";
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
                        Selected account
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
                    <span>Owner: {ownerLabel}</span>
                    <span>Home workspace: {formatWorkspaceLabel(selectedAccount.workspaceName, selectedAccount.workspaceId)}</span>
                    <span>
                      Last rented:{" "}
                      {selectedAccount.lastRentedWorkspaceId
                        ? formatWorkspaceLabel(
                            selectedAccount.lastRentedWorkspaceName,
                            selectedAccount.lastRentedWorkspaceId,
                          )
                        : "-"}
                    </span>
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
                        {lowPriority
                          ? "Remove low priority before assigning a buyer."
                          : frozen
                            ? "Unfreeze the account before assigning a buyer."
                            : "Release the account first."}
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
                        value={accountEditWorkspaceId ?? ""}
                        onChange={(event) => {
                          const value = event.target.value;
                          setAccountEditWorkspaceId(value ? Number(value) : null);
                        }}
                        className="w-full rounded-lg border border-neutral-200 bg-white px-3 py-2 text-sm text-neutral-700 outline-none"
                      >
                        <option value="">Select workspace</option>
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

  const renderInventoryActionsPanel = () => {
    const frozen = !!selectedAccount?.accountFrozen;
    const lowPriority = !!selectedAccount?.lowPriority;
    return (
      <div className="rounded-2xl border border-neutral-200 bg-white p-6 shadow-sm shadow-neutral-200/70">
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-lg font-semibold text-neutral-900">Account controls</h3>
          <span className="text-xs text-neutral-500">{selectedAccount ? "Ready" : "Select an account"}</span>
        </div>
        {selectedAccount ? (
          <div className="space-y-4">
            <div className="rounded-xl border border-neutral-200 bg-neutral-50 p-4">
              <div className="mb-2 text-sm font-semibold text-neutral-800">Freeze account</div>
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
                {frozen ? "Unfreeze account" : "Freeze account"}
              </button>
            </div>
            <div className="rounded-xl border border-neutral-200 bg-neutral-50 p-4">
              <div className="mb-2 text-sm font-semibold text-neutral-800">Low priority</div>
              <p className="text-xs text-neutral-500">
                Low priority accounts are excluded from auto-assign and stock lists until restored.
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
                {lowPriority ? "Remove low priority" : "Mark low priority"}
              </button>
            </div>
            <div className="rounded-xl border border-neutral-200 bg-neutral-50 p-4">
              <div className="mb-2 text-sm font-semibold text-neutral-800">Delete account</div>
              <p className="text-xs text-neutral-500">Removes the account and its lot mapping.</p>
              <button
                onClick={handleDeleteAccount}
                disabled={accountControlBusy}
                className="mt-3 w-full rounded-lg border border-rose-200 bg-rose-50 px-4 py-2 text-sm font-semibold text-rose-700 transition hover:bg-rose-100 disabled:cursor-not-allowed disabled:opacity-60"
              >
                Delete account
              </button>
            </div>
          </div>
        ) : (
          <div className="rounded-xl border border-dashed border-neutral-200 bg-neutral-50 px-4 py-6 text-center text-sm text-neutral-500">
            Select an account to manage freeze & deletion.
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="space-y-6">
      <div className="grid gap-6 xl:grid-cols-[minmax(0,1.55fr)_minmax(0,1fr)]">
        <div className="rounded-2xl border border-neutral-200 bg-white p-6 shadow-sm shadow-neutral-200/70">
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
            <div>
              <h3 className="text-lg font-semibold text-neutral-900">Inventory</h3>
              <p className="text-xs text-neutral-500">Select an account to manage rentals.</p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <div className="flex items-center gap-2 rounded-full bg-neutral-100 px-3 py-1 text-xs font-semibold text-neutral-600">
                <span className="uppercase tracking-wide text-neutral-500">Scope</span>
                <span className="font-semibold text-neutral-700">All platforms + workspaces</span>
              </div>
              {selectedAccount ? (
                <span className="text-xs rounded-full bg-neutral-100 px-3 py-1 font-semibold text-neutral-600">
                  Selected ID {selectedAccount.id ?? "-"}
                </span>
              ) : (
                <span className="text-xs rounded-full bg-neutral-100 px-3 py-1 font-semibold text-neutral-600">
                  No account selected
                </span>
              )}
            </div>
          </div>
          <div className="overflow-x-hidden">
            <div className="min-w-0">
              <div className="grid gap-3 px-6 text-xs font-semibold text-neutral-500" style={{ gridTemplateColumns: INVENTORY_GRID }}>
                <span>ID</span>
                <span>Name</span>
                <span>Login</span>
                <span>Password</span>
                <span>Steam ID</span>
                <span>MMR</span>
                <span className="text-center">State</span>
              </div>
              <div className="mt-3 space-y-3 overflow-y-auto overflow-x-hidden pr-1" style={{ maxHeight: "640px" }}>
                {accounts.map((acc, idx) => {
                  const rented = !!acc.owner;
                  const frozen = !!acc.accountFrozen;
                  const lowPriority = !!acc.lowPriority;
                  const stateLabel = lowPriority ? "Low Priority" : frozen ? "Frozen" : rented ? "Rented out" : "Available";
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
                          <span className="inline-flex w-fit rounded-full bg-neutral-100 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-neutral-600">
                            Home: {formatWorkspaceLabel(acc.workspaceName, acc.workspaceId)}
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
                {accounts.length === 0 && (
                  <div className="rounded-xl border border-dashed border-neutral-200 bg-neutral-50 px-4 py-6 text-center text-sm text-neutral-500">
                    {emptyMessage}
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
        <div className="mt-6 grid gap-6 lg:grid-cols-2">
          {renderAccountActionsPanel("Account actions")}
          {renderInventoryActionsPanel()}
        </div>
      </div>
    </div>
  );
};

export default InventoryPage;
