import React, { useCallback, useEffect, useMemo, useState } from "react";
import { motion } from "framer-motion";

import { api, AccountItem } from "../../services/api";
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

const GRID =
  "minmax(72px,0.6fr) minmax(200px,1.4fr) minmax(150px,1fr) minmax(150px,1fr) minmax(110px,0.6fr) minmax(200px,1fr) minmax(140px,0.8fr)";
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

const LowPriorityAccountsPage: React.FC<LowPriorityAccountsPageProps> = ({ onToast }) => {
  const { selectedId: selectedWorkspaceId, workspaces } = useWorkspace();
  const isAllWorkspaces = selectedWorkspaceId === "all";
  const workspaceId = isAllWorkspaces ? null : (selectedWorkspaceId as number);

  const [accounts, setAccounts] = useState<AccountRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [query, setQuery] = useState("");
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [actionBusy, setActionBusy] = useState(false);

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

  useEffect(() => {
    void loadAccounts();
  }, [loadAccounts]);

  useEffect(() => {
    if (selectedId && !accounts.some((acc) => acc.id === selectedId)) {
      setSelectedId(null);
    }
  }, [accounts, selectedId]);

  const filtered = useMemo(() => {
    const trimmed = query.trim().toLowerCase();
    if (!trimmed) return accounts;
    return accounts.filter((acc) => {
      const haystack = [
        acc.name,
        acc.login,
        acc.owner,
        acc.workspaceName,
        acc.lastRentedWorkspaceName,
        acc.workspaceId ? String(acc.workspaceId) : null,
        acc.id ? String(acc.id) : null,
      ]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();
      return haystack.includes(trimmed);
    });
  }, [accounts, query]);

  const selectedAccount = useMemo(
    () => accounts.find((acc) => acc.id === selectedId) ?? null,
    [accounts, selectedId],
  );

  const totalCount = accounts.length;
  const rentedCount = accounts.filter((acc) => acc.owner).length;

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
          <div className="text-xs font-semibold uppercase tracking-wide text-neutral-500">Still rented</div>
          <div className="mt-2 text-2xl font-semibold text-neutral-900">{rentedCount}</div>
          <div className="mt-1 text-xs text-neutral-500">Accounts with active owners.</div>
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
              onClick={() => loadAccounts()}
              className="rounded-lg border border-neutral-200 bg-neutral-50 px-3 py-2 text-xs text-neutral-600"
              disabled={loading}
            >
              Refresh
            </button>
          </div>
          <div className="mt-4 flex flex-wrap items-center gap-3">
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search by account, login, owner, workspace..."
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
              <span>Owner</span>
              <span>MMR</span>
              <span>Workspace</span>
              <span>Actions</span>
            </div>
            <div className="max-h-[520px] overflow-y-auto">
              {loading ? (
                <div className="px-4 py-8 text-center text-sm text-neutral-500">Loading low priority accounts...</div>
              ) : filtered.length ? (
                filtered.map((acc) => {
                  const isActive = acc.id === selectedId;
                  const workspaceLabel = formatWorkspaceLabel(acc.workspaceId, acc.workspaceName, workspaces);
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
                      <span className="truncate text-xs text-neutral-500">{acc.owner || "-"}</span>
                      <span className="text-xs text-neutral-500">{acc.mmr}</span>
                      <span className="truncate text-xs text-neutral-500">{workspaceLabel}</span>
                      <div className="flex justify-end">
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
                <div className="mt-3 grid gap-1 text-xs text-neutral-600">
                  <span>Login: {selectedAccount.login || "-"}</span>
                  <span>Owner: {selectedAccount.owner || "-"}</span>
                  <span>MMR: {selectedAccount.mmr}</span>
                  <span>
                    Workspace:{" "}
                    {formatWorkspaceLabel(
                      selectedAccount.workspaceId,
                      selectedAccount.workspaceName,
                      workspaces,
                    )}
                  </span>
                  <span>
                    Last rented:{" "}
                    {selectedAccount.lastRentedWorkspaceId
                      ? formatWorkspaceLabel(
                          selectedAccount.lastRentedWorkspaceId,
                          selectedAccount.lastRentedWorkspaceName,
                          workspaces,
                        )
                      : "-"}
                  </span>
                  <span>Rental start: {selectedAccount.rentalStart || "-"}</span>
                  <span>
                    Duration: {formatDuration(selectedAccount.rentalDurationMinutes)}
                  </span>
                </div>
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
              Select an account to restore it.
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default LowPriorityAccountsPage;
