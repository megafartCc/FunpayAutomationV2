import React, { useCallback, useEffect, useMemo, useState } from "react";

import { api, BlacklistEntry, BlacklistLog } from "../../services/api";
import { useWorkspace } from "../../context/WorkspaceContext";

type BlacklistPageProps = {
  onToast?: (message: string, isError?: boolean) => void;
};

const BLACKLIST_GRID =
  "40px minmax(180px,1.2fr) minmax(240px,1.6fr) minmax(160px,0.9fr) minmax(140px,0.8fr)";

const formatDate = (value?: string | null) => {
  if (!value) return "-";
  const dt = new Date(value);
  if (Number.isNaN(dt.getTime())) return value;
  return dt.toLocaleString();
};

const BlacklistPage: React.FC<BlacklistPageProps> = ({ onToast }) => {
  const { selectedId: selectedWorkspaceId } = useWorkspace();
  const workspaceId = selectedWorkspaceId === "all" ? null : (selectedWorkspaceId as number);
  const locked = selectedWorkspaceId === "all";

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

  const resolveOrderOwner = useCallback(
    async (orderId: string) => {
      if (locked || !workspaceId) {
        onToast?.("Select a workspace to manage the blacklist.", true);
        return null;
      }
      const trimmed = orderId.trim();
      if (!trimmed) {
        onToast?.("Enter an order ID first.", true);
        return null;
      }
      setBlacklistResolving(true);
      try {
        const res = await api.resolveOrder(trimmed, workspaceId);
        if (!res?.owner) {
          onToast?.("Buyer not found for this order yet.", true);
          return null;
        }
        setBlacklistOwner(res.owner);
        onToast?.(`Buyer found: ${res.owner}`);
        return res.owner;
      } catch (err) {
        const message = (err as { message?: string })?.message || "Order lookup failed.";
        onToast?.(message, true);
        return null;
      } finally {
        setBlacklistResolving(false);
      }
    },
    [locked, workspaceId, onToast],
  );

  const loadBlacklist = useCallback(async () => {
    if (!workspaceId) {
      setBlacklistEntries([]);
      setBlacklistSelected([]);
      return;
    }
    setBlacklistLoading(true);
    try {
      const res = await api.listBlacklist(workspaceId, blacklistQuery.trim() || undefined);
      setBlacklistEntries(res.items || []);
      setBlacklistSelected((prev) => prev.filter((owner) => res.items.some((entry) => entry.owner === owner)));
    } catch (err) {
      const message = (err as { message?: string })?.message || "Failed to load blacklist.";
      onToast?.(message, true);
    } finally {
      setBlacklistLoading(false);
    }
  }, [workspaceId, blacklistQuery, onToast]);

  const loadBlacklistLogs = useCallback(async () => {
    if (!workspaceId) {
      setBlacklistLogs([]);
      return;
    }
    setBlacklistLogsLoading(true);
    try {
      const res = await api.listBlacklistLogs(workspaceId, 200);
      setBlacklistLogs(res.items || []);
    } catch (err) {
      const message = (err as { message?: string })?.message || "Failed to load blacklist activity.";
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
    if (locked || !workspaceId) {
      onToast?.("Select a workspace to manage the blacklist.", true);
      return;
    }
    let owner = blacklistOwner.trim();
    const orderId = blacklistOrderId.trim();
    if (!owner && !orderId) {
      onToast?.("Enter a buyer username or order ID.", true);
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
        workspaceId,
      );
      setBlacklistOwner("");
      setBlacklistOrderId("");
      setBlacklistReason("");
      setBlacklistEntries((prev) => [entry, ...prev.filter((item) => item.id !== entry.id)]);
      onToast?.("User added to blacklist.");
      await loadBlacklist();
      await loadBlacklistLogs();
    } catch (err) {
      const message = (err as { message?: string })?.message || "Failed to add user to blacklist.";
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
    if (locked || !workspaceId) {
      onToast?.("Select a workspace to manage the blacklist.", true);
      return;
    }
    const owner = blacklistEditOwner.trim();
    if (!owner) {
      onToast?.("Owner cannot be empty.", true);
      return;
    }
    try {
      const entry = await api.updateBlacklist(
        Number(blacklistEditingId),
        { owner, reason: blacklistEditReason.trim() || null },
        workspaceId,
      );
      onToast?.("Blacklist entry updated.");
      cancelEditBlacklist();
      setBlacklistEntries((prev) => prev.map((item) => (item.id === entry.id ? entry : item)));
      await loadBlacklistLogs();
    } catch (err) {
      const message = (err as { message?: string })?.message || "Failed to update blacklist entry.";
      onToast?.(message, true);
    }
  };

  const handleRemoveSelected = async () => {
    if (!blacklistSelected.length) {
      onToast?.("Select users to unblacklist.", true);
      return;
    }
    if (locked || !workspaceId) {
      onToast?.("Select a workspace to manage the blacklist.", true);
      return;
    }
    try {
      await api.removeBlacklist(blacklistSelected, workspaceId);
      onToast?.("Selected users removed from blacklist.");
      setBlacklistSelected([]);
      await loadBlacklist();
      await loadBlacklistLogs();
    } catch (err) {
      const message = (err as { message?: string })?.message || "Failed to unblacklist users.";
      onToast?.(message, true);
    }
  };

  const handleClearBlacklist = async () => {
    if (!blacklistEntries.length) {
      onToast?.("Blacklist is already empty.", true);
      return;
    }
    if (locked || !workspaceId) {
      onToast?.("Select a workspace to manage the blacklist.", true);
      return;
    }
    if (!window.confirm("Remove everyone from the blacklist?")) return;
    try {
      await api.clearBlacklist(workspaceId);
      onToast?.("Blacklist cleared.");
      setBlacklistSelected([]);
      await loadBlacklist();
      await loadBlacklistLogs();
    } catch (err) {
      const message = (err as { message?: string })?.message || "Failed to clear blacklist.";
      onToast?.(message, true);
    }
  };

  const allBlacklistSelected =
    blacklistEntries.length > 0 && blacklistSelected.length === blacklistEntries.length;
  const totalBlacklisted = useMemo(() => blacklistEntries.length, [blacklistEntries]);

  return (
    <div className="space-y-6">
      <div className="rounded-2xl border border-neutral-200 bg-white p-6 shadow-sm shadow-neutral-200/70">
        <div className="mb-5 flex flex-wrap items-center justify-between gap-4">
          <div>
            <h3 className="text-lg font-semibold text-neutral-900">Blacklist</h3>
            <p className="text-sm text-neutral-500">
              Block buyers from renting and send a penalty payment notice.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-xs rounded-full bg-neutral-100 px-3 py-1 font-semibold text-neutral-600">
              {totalBlacklisted} blocked
            </span>
            <button
              onClick={() => loadBlacklist()}
              className="rounded-lg border border-neutral-200 bg-neutral-50 px-3 py-2 text-xs text-neutral-600"
            >
              Refresh
            </button>
          </div>
        </div>
        <div className="grid gap-4 lg:grid-cols-[1.15fr_1fr]">
          <div className="rounded-xl border border-neutral-200 bg-neutral-50 p-4">
            <div className="mb-2 text-sm font-semibold text-neutral-800">Add to blacklist</div>
            {locked && (
              <div className="mb-3 rounded-lg border border-dashed border-neutral-200 bg-neutral-50 px-3 py-2 text-xs text-neutral-500">
                Select a workspace to add or edit blacklist entries.
              </div>
            )}
            <div className="space-y-3">
              <div className="grid gap-3 md:grid-cols-[1fr_auto]">
                <input
                  value={blacklistOrderId}
                  onChange={(e) => setBlacklistOrderId(e.target.value)}
                  placeholder="Order ID (optional)"
                  disabled={locked || blacklistResolving}
                  className="w-full rounded-lg border border-neutral-200 bg-white px-3 py-2 text-sm text-neutral-700 outline-none placeholder:text-neutral-400"
                />
                <button
                  onClick={handleResolveBlacklistOrder}
                  disabled={locked || blacklistResolving}
                  className="rounded-lg border border-neutral-200 bg-white px-3 py-2 text-xs font-semibold text-neutral-700 transition hover:bg-neutral-100 disabled:cursor-not-allowed disabled:text-neutral-400"
                >
                  Find buyer
                </button>
              </div>
              <input
                value={blacklistOwner}
                onChange={(e) => setBlacklistOwner(e.target.value)}
                placeholder="Buyer username"
                disabled={locked}
                className="w-full rounded-lg border border-neutral-200 bg-white px-3 py-2 text-sm text-neutral-700 outline-none placeholder:text-neutral-400"
              />
              <input
                value={blacklistReason}
                onChange={(e) => setBlacklistReason(e.target.value)}
                placeholder="Reason (optional)"
                disabled={locked}
                className="w-full rounded-lg border border-neutral-200 bg-white px-3 py-2 text-sm text-neutral-700 outline-none placeholder:text-neutral-400"
              />
              <button
                onClick={handleAddBlacklist}
                disabled={locked || blacklistResolving || (!blacklistOwner.trim() && !blacklistOrderId.trim())}
                className="w-full rounded-lg bg-neutral-900 px-4 py-2 text-sm font-semibold text-white transition hover:bg-neutral-800 disabled:cursor-not-allowed disabled:bg-neutral-300"
              >
                {blacklistResolving ? "Resolving..." : "Add user"}
              </button>
            </div>
          </div>
          <div className="rounded-xl border border-neutral-200 bg-neutral-50 p-4">
            <div className="mb-2 text-sm font-semibold text-neutral-800">Manage</div>
            <input
              value={blacklistQuery}
              onChange={(e) => setBlacklistQuery(e.target.value)}
              placeholder="Search by buyer"
              type="search"
              disabled={locked}
              className="w-full rounded-lg border border-neutral-200 bg-white px-3 py-2 text-sm text-neutral-700 outline-none placeholder:text-neutral-400"
            />
            <div className="mt-3 flex flex-wrap gap-2">
              <button
                onClick={handleRemoveSelected}
                disabled={locked || !blacklistSelected.length}
                className="rounded-lg border border-neutral-200 bg-white px-3 py-2 text-xs font-semibold text-neutral-700 transition hover:bg-neutral-100 disabled:cursor-not-allowed disabled:text-neutral-400"
              >
                Unblacklist selected
              </button>
              <button
                onClick={handleClearBlacklist}
                disabled={locked || !blacklistEntries.length}
                className="rounded-lg border border-neutral-200 bg-white px-3 py-2 text-xs font-semibold text-neutral-700 transition hover:bg-neutral-100 disabled:cursor-not-allowed disabled:text-neutral-400"
              >
                Unblacklist all
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
                <span>Buyer</span>
                <span>Reason</span>
                <span>Added</span>
                <span>Actions</span>
              </div>
              <div className="divide-y divide-neutral-100 overflow-x-hidden">
                {blacklistLoading ? (
                  <div className="px-6 py-6 text-center text-sm text-neutral-500">
                    Loading blacklist...
                  </div>
                ) : blacklistEntries.length ? (
                  blacklistEntries.map((entry, idx) => {
                    const isSelected = blacklistSelected.includes(entry.owner);
                    const isEditing =
                      blacklistEditingId !== null &&
                      entry.id !== undefined &&
                      String(blacklistEditingId) === String(entry.id);
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
                          <span className="min-w-0 truncate font-semibold text-neutral-900">
                            {entry.owner}
                          </span>
                        )}
                        {isEditing ? (
                          <input
                            value={blacklistEditReason}
                            onChange={(e) => setBlacklistEditReason(e.target.value)}
                            placeholder="Reason (optional)"
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
                                Save
                              </button>
                              <button
                                onClick={cancelEditBlacklist}
                                className="rounded-lg border border-neutral-200 px-3 py-1 text-xs font-semibold text-neutral-600"
                              >
                                Cancel
                              </button>
                            </>
                          ) : (
                            <button
                              onClick={() => startEditBlacklist(entry)}
                              className="rounded-lg border border-neutral-200 px-3 py-1 text-xs font-semibold text-neutral-600"
                            >
                              Edit
                            </button>
                          )}
                        </div>
                      </div>
                    );
                  })
                ) : (
                  <div className="px-6 py-6 text-center text-sm text-neutral-500">Blacklist is empty.</div>
                )}
              </div>
            </div>
          </div>
        </div>
        <div className="mt-5 rounded-2xl border border-neutral-200 bg-white p-4">
          <div className="mb-3 flex items-center justify-between">
            <div>
              <div className="text-sm font-semibold text-neutral-900">Activity</div>
              <div className="text-xs text-neutral-500">Latest blacklist / unblacklist events.</div>
            </div>
            <button
              onClick={() => loadBlacklistLogs()}
              disabled={locked || blacklistLogsLoading}
              className="rounded-lg border border-neutral-200 bg-white px-3 py-2 text-xs font-semibold text-neutral-700 transition hover:bg-neutral-100 disabled:cursor-not-allowed disabled:text-neutral-400"
            >
              Refresh
            </button>
          </div>
          {blacklistLogsLoading ? (
            <div className="py-4 text-sm text-neutral-500">Loading activity...</div>
          ) : blacklistLogs.length === 0 ? (
            <div className="py-4 text-sm text-neutral-500">No activity yet.</div>
          ) : (
            <div className="space-y-2">
              {blacklistLogs.map((log, idx) => {
                const action = (log.action || "").toLowerCase();
                const badge =
                  action === "add"
                    ? { label: "Added", className: "bg-blue-100 text-blue-700" }
                    : action.includes("unblacklist")
                      ? { label: "Unblocked", className: "bg-green-100 text-green-700" }
                      : action === "blocked_order"
                        ? { label: "Blocked order", className: "bg-red-100 text-red-700" }
                        : action === "blacklist_comp"
                          ? { label: "Payment", className: "bg-amber-100 text-amber-700" }
                          : action === "update"
                            ? { label: "Updated", className: "bg-neutral-100 text-neutral-700" }
                            : action === "clear_all"
                              ? { label: "Cleared", className: "bg-neutral-100 text-neutral-700" }
                              : { label: action || "Event", className: "bg-neutral-100 text-neutral-700" };
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
