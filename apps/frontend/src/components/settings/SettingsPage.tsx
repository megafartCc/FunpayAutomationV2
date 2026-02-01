import React, { useEffect, useMemo, useState } from "react";

import { api, TelegramStatus, WorkspaceItem, WorkspaceProxyCheck, WorkspaceStatusItem } from "../../services/api";
import { useWorkspace } from "../../context/WorkspaceContext";

type SettingsPageProps = {
  onToast?: (message: string, isError?: boolean) => void;
};

const ensureProxyScheme = (value: string) => {
  const trimmed = value.trim();
  if (!trimmed) return "";
  if (trimmed.includes("://")) return trimmed;
  return `socks5://${trimmed}`;
};

const mergeProxyCredentials = (base: string, username: string, password: string) => {
  const trimmed = ensureProxyScheme(base);
  if (!trimmed) return "";
  if (!username && !password) return trimmed;
  try {
    const parsed = new URL(trimmed);
    parsed.username = username || "";
    parsed.password = password || "";
    return parsed.toString();
  } catch {
    return trimmed;
  }
};

const splitProxyCredentials = (raw: string) => {
  if (!raw) return { base: "", username: "", password: "" };
  const normalized = ensureProxyScheme(raw);
  try {
    const parsed = new URL(normalized);
    const username = decodeURIComponent(parsed.username || "");
    const password = decodeURIComponent(parsed.password || "");
    parsed.username = "";
    parsed.password = "";
    const base = parsed.toString().replace(/\/$/, "");
    return { base, username, password };
  } catch {
    return { base: raw, username: "", password: "" };
  }
};

const statusKey = (workspaceId: number | null | undefined, platform?: string | null) =>
  `${workspaceId ?? "none"}:${(platform || "funpay").toLowerCase()}`;
const normalizeStatus = (value?: string | null) => (value || "").toLowerCase();
const parseUpdatedAt = (value?: string | null) => {
  if (!value) return null;
  const normalized = value.includes("T") ? value : value.replace(" ", "T");
  const parsed = new Date(normalized);
  if (Number.isNaN(parsed.getTime())) return null;
  return parsed;
};
const isStatusStale = (status?: WorkspaceStatusItem | null) => {
  const updated = parseUpdatedAt(status?.updated_at);
  if (!updated) return false;
  return Date.now() - updated.getTime() > 2 * 60 * 1000;
};
const resolveStatusMeta = (status?: WorkspaceStatusItem | null) => {
  if (!status) {
    return {
      label: "No status",
      className: "border-neutral-200 bg-white text-neutral-500",
    };
  }
  const normalized = normalizeStatus(status.status);
  if (isStatusStale(status) && ["ok", "online", "connected", "warning", "degraded"].includes(normalized)) {
    return {
      label: "Offline",
      className: "border-rose-200 bg-rose-50 text-rose-700",
    };
  }
  if (["ok", "online", "connected"].includes(normalized)) {
    return {
      label: "Online",
      className: "border-emerald-200 bg-emerald-50 text-emerald-700",
    };
  }
  if (["warning", "degraded"].includes(normalized)) {
    return {
      label: "Degraded",
      className: "border-amber-200 bg-amber-50 text-amber-700",
    };
  }
  if (["unauthorized", "auth", "auth_required", "forbidden"].includes(normalized)) {
    return {
      label: "Auth required",
      className: "border-rose-200 bg-rose-50 text-rose-700",
    };
  }
  if (["offline"].includes(normalized)) {
    return {
      label: "Offline",
      className: "border-rose-200 bg-rose-50 text-rose-700",
    };
  }
  if (["error", "failed"].includes(normalized)) {
    return {
      label: "Error",
      className: "border-rose-200 bg-rose-50 text-rose-700",
    };
  }
  return {
    label: normalized ? normalized : "Unknown",
    className: "border-neutral-200 bg-white text-neutral-500",
  };
};

const SettingsPage: React.FC<SettingsPageProps> = ({ onToast }) => {
  const { visibleWorkspaces, loading, refresh, selectedPlatform } = useWorkspace();
  const [keyActionBusy, setKeyActionBusy] = useState(false);
  const [newName, setNewName] = useState("");
  const [newPlatform, setNewPlatform] = useState<"funpay" | "playerok">("funpay");
  const [newKey, setNewKey] = useState("");
  const [newProxyUrl, setNewProxyUrl] = useState("");
  const [newProxyUsername, setNewProxyUsername] = useState("");
  const [newProxyPassword, setNewProxyPassword] = useState("");
  const [newDefault, setNewDefault] = useState(false);

  const [editingId, setEditingId] = useState<number | null>(null);
  const [editName, setEditName] = useState("");
  const [editKey, setEditKey] = useState("");
  const [editProxyUrl, setEditProxyUrl] = useState("");
  const [editProxyUsername, setEditProxyUsername] = useState("");
  const [editProxyPassword, setEditProxyPassword] = useState("");
  const [proxyChecks, setProxyChecks] = useState<Record<number, WorkspaceProxyCheck & { status: string }>>({});
  const [workspaceStatuses, setWorkspaceStatuses] = useState<Record<string, WorkspaceStatusItem>>({});
  const [statusError, setStatusError] = useState<string | null>(null);
  const [telegramStatus, setTelegramStatus] = useState<TelegramStatus | null>(null);
  const [telegramLink, setTelegramLink] = useState("");
  const [telegramBusy, setTelegramBusy] = useState(false);

  const platformCopy = useMemo(
    () => ({
      funpay: {
        keyLabel: "FunPay golden key",
        keyPlaceholder: "Golden key",
        keyHelper: "Required to authenticate with FunPay.",
      },
      playerok: {
        keyLabel: "PlayerOk cookies JSON",
        keyPlaceholder: "Paste cookies JSON array from your browser",
        keyHelper: "Paste the JSON array of cookies exported from your logged-in PlayerOk session.",
      },
    }),
    [],
  );

  const isEditing = (id: number) => editingId === id;

  const resetCreateForm = () => {
    setNewName("");
    setNewPlatform("funpay");
    setNewKey("");
    setNewProxyUrl("");
    setNewProxyUsername("");
    setNewProxyPassword("");
    setNewDefault(false);
  };

  const refreshTelegramStatus = async () => {
    try {
      const status = await api.getTelegramStatus();
      setTelegramStatus(status);
    } catch {
      setTelegramStatus(null);
    }
  };

  useEffect(() => {
    refreshTelegramStatus();
  }, []);

  const handleGenerateTelegramLink = async () => {
    if (telegramBusy) return;
    setTelegramBusy(true);
    try {
      const status = await api.createTelegramToken();
      setTelegramStatus(status);
      setTelegramLink(status.start_url || "");
      onToast?.("Telegram link generated.");
    } catch (err) {
      onToast?.((err as { message?: string })?.message || "Failed to generate Telegram link.", true);
    } finally {
      setTelegramBusy(false);
    }
  };

  const handleDisconnectTelegram = async () => {
    if (telegramBusy) return;
    setTelegramBusy(true);
    try {
      const status = await api.disconnectTelegram();
      setTelegramStatus(status);
      setTelegramLink("");
      onToast?.("Telegram disconnected.");
    } catch (err) {
      onToast?.((err as { message?: string })?.message || "Failed to disconnect Telegram.", true);
    } finally {
      setTelegramBusy(false);
    }
  };

  const handleCopyTelegramLink = async () => {
    if (!telegramLink) return;
    try {
      await navigator.clipboard.writeText(telegramLink);
      onToast?.("Link copied to clipboard.");
    } catch {
      onToast?.("Unable to copy link.", true);
    }
  };

  const startEdit = (item: WorkspaceItem) => {
    const parsed = splitProxyCredentials(item.proxy_url || "");
    setEditingId(item.id);
    setEditName(item.name || "");
    setEditKey("");
    setEditProxyUrl(parsed.base);
    setEditProxyUsername(parsed.username);
    setEditProxyPassword(parsed.password);
  };

  const cancelEdit = () => {
    setEditingId(null);
    setEditName("");
    setEditKey("");
    setEditProxyUrl("");
    setEditProxyUsername("");
    setEditProxyPassword("");
  };

  const handleCreate = async () => {
    if (keyActionBusy) return;
    if (!newName.trim() || !newKey.trim() || !newProxyUrl.trim()) {
      onToast?.("Workspace name, golden key, and proxy are required.", true);
      return;
    }
    const proxyUrl = mergeProxyCredentials(newProxyUrl, newProxyUsername, newProxyPassword);
    if (!proxyUrl) {
      onToast?.("Proxy URL is required for every workspace.", true);
      return;
    }
    setKeyActionBusy(true);
    try {
      await api.createWorkspace({
        name: newName.trim(),
        platform: newPlatform,
        golden_key: newKey.trim(),
        proxy_url: proxyUrl.trim(),
        is_default: newDefault,
      });
      onToast?.("Workspace added.");
      resetCreateForm();
      await refresh();
    } catch (err) {
      onToast?.((err as { message?: string })?.message || "Failed to create workspace.", true);
    } finally {
      setKeyActionBusy(false);
    }
  };

  const handleSaveEdit = async () => {
    if (keyActionBusy || editingId === null) return;
    const payload: { name?: string; golden_key?: string; proxy_url?: string } = {};
    if (editName.trim()) payload.name = editName.trim();
    if (editKey.trim()) payload.golden_key = editKey.trim();
    if (editProxyUrl.trim()) {
      const proxyUrl = mergeProxyCredentials(editProxyUrl, editProxyUsername, editProxyPassword);
      payload.proxy_url = proxyUrl.trim();
    }
    if (!Object.keys(payload).length) {
      onToast?.("No changes to save.", true);
      return;
    }
    setKeyActionBusy(true);
    try {
      await api.updateWorkspace(editingId, payload);
      onToast?.("Workspace updated.");
      cancelEdit();
      await refresh();
    } catch (err) {
      onToast?.((err as { message?: string })?.message || "Failed to update workspace.", true);
    } finally {
      setKeyActionBusy(false);
    }
  };

  const handleDelete = async (id: number) => {
    if (keyActionBusy) return;
    setKeyActionBusy(true);
    try {
      await api.deleteWorkspace(id);
      onToast?.("Workspace removed.");
      await refresh();
    } catch (err) {
      onToast?.((err as { message?: string })?.message || "Failed to remove workspace.", true);
    } finally {
      setKeyActionBusy(false);
    }
  };

  const handleSetDefault = async (id: number) => {
    if (keyActionBusy) return;
    setKeyActionBusy(true);
    try {
      await api.setDefaultWorkspace(id);
      onToast?.("Default workspace updated.");
      await refresh();
    } catch (err) {
      onToast?.((err as { message?: string })?.message || "Failed to update default.", true);
    } finally {
      setKeyActionBusy(false);
    }
  };

  const handleCheckProxy = async (id: number) => {
    if (proxyChecks[id]?.status === "loading") return;
    setProxyChecks((prev) => ({ ...prev, [id]: { status: "loading", ok: false } }));
    try {
      const result = await api.checkWorkspaceProxy(id);
      const status = result.ok ? "success" : "error";
      setProxyChecks((prev) => ({
        ...prev,
        [id]: {
          ...result,
          status,
        },
      }));
      if (!result.ok) {
        onToast?.(result.error || "Proxy check failed.", true);
      } else {
        onToast?.("Proxy check passed.");
      }
    } catch (err) {
      const message = (err as { message?: string })?.message || "Failed to check proxy.";
      setProxyChecks((prev) => ({
        ...prev,
        [id]: { status: "error", ok: false, error: message },
      }));
      onToast?.(message, true);
    }
  };

  const workspaceList = useMemo(() => visibleWorkspaces || [], [visibleWorkspaces]);

  useEffect(() => {
    let isMounted = true;
    const loadStatuses = async () => {
      try {
        const platform = selectedPlatform === "all" ? undefined : selectedPlatform;
        const res = await api.listWorkspaceStatuses(undefined, platform);
        if (!isMounted) return;
        const map: Record<string, WorkspaceStatusItem> = {};
        (res.items || []).forEach((item) => {
          const key = statusKey(item.workspace_id ?? null, item.platform);
          if (!map[key]) {
            map[key] = item;
          }
        });
        setWorkspaceStatuses(map);
        setStatusError(null);
      } catch {
        if (isMounted) {
          setStatusError("Failed to load status.");
        }
      }
    };
    void loadStatuses();
    const handle = window.setInterval(loadStatuses, 20_000);
    return () => {
      isMounted = false;
      window.clearInterval(handle);
    };
  }, [selectedPlatform]);

  return (
    <div className="grid gap-6">
      <div className="rounded-2xl border border-neutral-200 bg-white p-6 shadow-sm shadow-neutral-200/70 max-h-[calc(100vh-260px)] flex flex-col">
        <div className="mb-4">
          <h3 className="text-lg font-semibold text-neutral-900">Workspaces</h3>
          <p className="text-xs text-neutral-500">
            Connect multiple platform workspaces and switch between them without leaving the dashboard.
          </p>
        </div>
        <div className="rounded-xl border border-neutral-200 bg-neutral-50 p-4">
          <div className="mb-3 text-sm font-semibold text-neutral-800">Add workspace</div>
          <div className="grid gap-3 md:grid-cols-2">
            <input
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              placeholder="Workspace name (e.g. Seller A)"
              className="w-full rounded-lg border border-neutral-200 bg-white px-3 py-2 text-sm text-neutral-700 outline-none placeholder:text-neutral-400"
            />
            <select
              value={newPlatform}
              onChange={(e) => setNewPlatform(e.target.value as "funpay" | "playerok")}
              className="w-full rounded-lg border border-neutral-200 bg-white px-3 py-2 text-sm text-neutral-700 outline-none"
            >
              <option value="funpay">FunPay</option>
              <option value="playerok">PlayerOk</option>
            </select>
            <div className="grid gap-2 md:col-span-2">
              <label className="text-[11px] font-semibold uppercase tracking-wide text-neutral-500">
                {platformCopy[newPlatform].keyLabel}
              </label>
              {newPlatform === "playerok" ? (
                <textarea
                  value={newKey}
                  onChange={(e) => setNewKey(e.target.value)}
                  placeholder={platformCopy[newPlatform].keyPlaceholder}
                  rows={3}
                  className="w-full rounded-lg border border-neutral-200 bg-white px-3 py-2 text-sm text-neutral-700 outline-none placeholder:text-neutral-400"
                />
              ) : (
                <input
                  value={newKey}
                  onChange={(e) => setNewKey(e.target.value)}
                  placeholder={platformCopy[newPlatform].keyPlaceholder}
                  type="password"
                  className="w-full rounded-lg border border-neutral-200 bg-white px-3 py-2 text-sm text-neutral-700 outline-none placeholder:text-neutral-400"
                />
              )}
              <p className="text-[11px] text-neutral-500">{platformCopy[newPlatform].keyHelper}</p>
            </div>
          </div>
          <div className="grid gap-3">
            <input
              value={newProxyUrl}
              onChange={(e) => setNewProxyUrl(e.target.value)}
              placeholder="Proxy URL (e.g. socks5://host:port[:user:pass])"
              className="w-full rounded-lg border border-neutral-200 bg-white px-3 py-2 text-sm text-neutral-700 outline-none placeholder:text-neutral-400"
            />
            <div className="grid gap-3 md:grid-cols-2">
              <input
                value={newProxyUsername}
                onChange={(e) => setNewProxyUsername(e.target.value)}
                placeholder="Proxy username (optional)"
                className="w-full rounded-lg border border-neutral-200 bg-white px-3 py-2 text-sm text-neutral-700 outline-none placeholder:text-neutral-400"
              />
              <input
                value={newProxyPassword}
                onChange={(e) => setNewProxyPassword(e.target.value)}
                placeholder="Proxy password (optional)"
                type="password"
                className="w-full rounded-lg border border-neutral-200 bg-white px-3 py-2 text-sm text-neutral-700 outline-none placeholder:text-neutral-400"
              />
            </div>
            <p className="text-[11px] text-neutral-500">
              Proxy is required for every workspace. Bots will not start without it.
            </p>
          </div>
          <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
            <label className="flex items-center gap-2 text-xs font-semibold text-neutral-600">
              <input
                type="checkbox"
                checked={newDefault}
                onChange={(e) => setNewDefault(e.target.checked)}
                className="h-4 w-4 rounded border-neutral-300 text-neutral-900"
              />
              Make default
            </label>
            <button
              onClick={handleCreate}
              disabled={keyActionBusy || !newKey.trim() || !newProxyUrl.trim() || !newName.trim()}
              className="rounded-lg bg-neutral-900 px-4 py-2 text-xs font-semibold text-white transition hover:bg-neutral-800 disabled:cursor-not-allowed disabled:bg-neutral-300"
            >
              Add workspace
            </button>
          </div>
        </div>
        <div className="mt-4 space-y-3 overflow-y-auto pr-1">
          {loading ? (
            <div className="rounded-xl border border-dashed border-neutral-200 bg-neutral-50 px-4 py-6 text-center text-sm text-neutral-500">
              Loading workspaces...
            </div>
          ) : workspaceList.length ? (
            workspaceList.map((item) => {
              const editing = isEditing(item.id);
              const proxyCheck = proxyChecks[item.id];
              return (
                <div key={item.id} className="rounded-xl border border-neutral-200 bg-white p-4">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                  <div className="flex items-center gap-2 text-sm font-semibold text-neutral-900">
                    <span>{item.name}</span>
                    <span className="rounded-full border border-neutral-200 bg-neutral-50 px-2 py-0.5 text-[10px] font-semibold uppercase text-neutral-600">
                      {item.platform || "funpay"}
                    </span>
                    {(() => {
                      const status = workspaceStatuses[statusKey(item.id, item.platform)];
                      const meta = resolveStatusMeta(status);
                      const updatedAt = parseUpdatedAt(status?.updated_at);
                      const updatedLabel = updatedAt ? `Updated ${updatedAt.toLocaleString()}` : "";
                      const titleParts = [
                        status?.message || (status?.status ? `Status: ${status.status}` : ""),
                        updatedLabel,
                        statusError ? statusError : "",
                      ].filter(Boolean);
                      const title = titleParts.length ? titleParts.join(" | ") : "No status yet.";
                      return (
                        <span
                          title={title}
                          className={`rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase ${meta.className}`}
                        >
                          {meta.label}
                        </span>
                      );
                    })()}
                  </div>
                  <div className="text-xs text-neutral-500">
                        {item.is_default ? "Default workspace" : "Workspace"}
                        {item.created_at ? ` Â· Added ${new Date(item.created_at).toLocaleDateString()}` : ""}
                        {item.key_hint ? ` Â· Key ${item.key_hint}` : ""}
                      </div>
                    </div>
                    <div className="flex flex-wrap items-center gap-2">
                      {!item.is_default && (
                        <button
                          onClick={() => handleSetDefault(item.id)}
                          className="rounded-lg border border-neutral-200 px-3 py-1 text-xs font-semibold text-neutral-600"
                        >
                          Set default
                        </button>
                      )}
                      <button
                        onClick={() => handleCheckProxy(item.id)}
                        disabled={proxyCheck?.status === "loading"}
                        className="rounded-lg border border-neutral-200 px-3 py-1 text-xs font-semibold text-neutral-600 disabled:cursor-not-allowed disabled:opacity-60"
                      >
                        {proxyCheck?.status === "loading" ? "Checking..." : "Check proxy"}
                      </button>
                      <button
                        onClick={() => (editing ? cancelEdit() : startEdit(item))}
                        className="rounded-lg border border-neutral-200 px-3 py-1 text-xs font-semibold text-neutral-600"
                      >
                        {editing ? "Close" : "Edit"}
                      </button>
                      <button
                        onClick={() => handleDelete(item.id)}
                        className="rounded-lg border border-rose-200 px-3 py-1 text-xs font-semibold text-rose-600"
                      >
                        Remove
                      </button>
                    </div>
                  </div>
                  {proxyCheck?.status && proxyCheck.status !== "loading" && (
                    <div
                      className={`mt-3 rounded-lg border px-3 py-2 text-xs ${
                        proxyCheck.ok
                          ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                          : "border-rose-200 bg-rose-50 text-rose-700"
                      }`}
                    >
                      <div className="font-semibold">
                        {proxyCheck.ok ? "Proxy looks good." : "Proxy check failed."}
                      </div>
                      <div>Before: {proxyCheck.direct_ip || "â€”"}</div>
                      <div>After: {proxyCheck.proxy_ip || "â€”"}</div>
                      {!proxyCheck.ok && proxyCheck.error ? <div>{proxyCheck.error}</div> : null}
                    </div>
                  )}
                  {editing && (
                    <div className="mt-4 space-y-3">
                      <div className="grid gap-3 md:grid-cols-2">
                        <input
                          value={editName}
                          onChange={(e) => setEditName(e.target.value)}
                          placeholder="Workspace name"
                          className="w-full rounded-lg border border-neutral-200 bg-white px-3 py-2 text-sm text-neutral-700 outline-none"
                        />
                        <div className="grid gap-2">
                          <label className="text-[11px] font-semibold uppercase tracking-wide text-neutral-500">
                            {platformCopy[(item.platform as "funpay" | "playerok") || "funpay"].keyLabel}
                          </label>
                          {item.platform === "playerok" ? (
                            <textarea
                              value={editKey}
                              onChange={(e) => setEditKey(e.target.value)}
                              placeholder="New PlayerOk cookies JSON (optional)"
                              rows={3}
                              className="w-full rounded-lg border border-neutral-200 bg-white px-3 py-2 text-sm text-neutral-700 outline-none"
                            />
                          ) : (
                            <input
                              value={editKey}
                              onChange={(e) => setEditKey(e.target.value)}
                              placeholder="New golden key (optional)"
                              type="password"
                              className="w-full rounded-lg border border-neutral-200 bg-white px-3 py-2 text-sm text-neutral-700 outline-none"
                            />
                          )}
                          {item.platform === "playerok" ? (
                            <p className="text-[11px] text-neutral-500">
                              Paste the updated cookie JSON array to re-authenticate PlayerOk.
                            </p>
                          ) : null}
                        </div>
                      </div>
                      <div className="grid gap-3">
                        <input
                          value={editProxyUrl}
                          onChange={(e) => setEditProxyUrl(e.target.value)}
                          placeholder="Proxy URL (socks5://host:port)"
                          className="w-full rounded-lg border border-neutral-200 bg-white px-3 py-2 text-sm text-neutral-700 outline-none"
                        />
                        <div className="grid gap-3 md:grid-cols-2">
                          <input
                            value={editProxyUsername}
                            onChange={(e) => setEditProxyUsername(e.target.value)}
                            placeholder="Proxy username"
                            className="w-full rounded-lg border border-neutral-200 bg-white px-3 py-2 text-sm text-neutral-700 outline-none"
                          />
                          <input
                            value={editProxyPassword}
                            onChange={(e) => setEditProxyPassword(e.target.value)}
                            placeholder="Proxy password"
                            type="password"
                            className="w-full rounded-lg border border-neutral-200 bg-white px-3 py-2 text-sm text-neutral-700 outline-none"
                          />
                        </div>
                        <p className="text-[11px] text-neutral-500">
                          Proxy must stay valid or bots will pause for this workspace.
                        </p>
                      </div>
                      <div className="flex flex-wrap items-center gap-2">
                        <button
                          onClick={handleSaveEdit}
                          className="rounded-lg bg-neutral-900 px-3 py-2 text-xs font-semibold text-white"
                        >
                          Save changes
                        </button>
                        <button
                          onClick={cancelEdit}
                          className="rounded-lg border border-neutral-200 px-3 py-2 text-xs font-semibold text-neutral-600"
                        >
                          Cancel
                        </button>
                        <button
                          onClick={() => handleCheckProxy(item.id)}
                          disabled={proxyCheck?.status === "loading"}
                          className="rounded-lg border border-neutral-200 px-3 py-2 text-xs font-semibold text-neutral-600 disabled:cursor-not-allowed disabled:opacity-60"
                        >
                          {proxyCheck?.status === "loading" ? "Checking..." : "Check proxy"}
                        </button>
                      </div>
                      {proxyCheck?.status && proxyCheck.status !== "loading" && (
                        <div
                          className={`rounded-lg border px-3 py-2 text-xs ${
                            proxyCheck.ok
                              ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                              : "border-rose-200 bg-rose-50 text-rose-700"
                          }`}
                        >
                          <div className="font-semibold">
                            {proxyCheck.ok ? "Proxy looks good." : "Proxy check failed."}
                          </div>
                          <div>Before: {proxyCheck.direct_ip || "â€”"}</div>
                          <div>After: {proxyCheck.proxy_ip || "â€”"}</div>
                          {!proxyCheck.ok && proxyCheck.error ? <div>{proxyCheck.error}</div> : null}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })
          ) : (
            <div className="rounded-xl border border-dashed border-neutral-200 bg-neutral-50 px-4 py-6 text-center text-sm text-neutral-500">
              No workspaces connected yet.
            </div>
          )}
        </div>
      </div>
      <div className="rounded-2xl border border-neutral-200 bg-white p-6 shadow-sm shadow-neutral-200/70">
        <div className="mb-4">
          <h3 className="text-lg font-semibold text-neutral-900">Telegram notifications</h3>
          <p className="text-xs text-neutral-500">
            Get an instant Telegram alert any time a buyer calls admin in any workspace, including a direct chat link.
          </p>
        </div>
        <div className="rounded-xl border border-neutral-200 bg-neutral-50 p-4 space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <div className="text-sm font-semibold text-neutral-800">Connection status</div>
              <p className="text-xs text-neutral-500">
                Secure your personal link to tie Telegram to this account.
              </p>
            </div>
            <span
              className={`rounded-full border px-3 py-1 text-xs font-semibold ${
                telegramStatus?.connected
                  ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                  : "border-neutral-200 bg-white text-neutral-600"
              }`}
            >
              {telegramStatus?.connected ? "Connected" : "Not connected"}
            </span>
          </div>
          {telegramStatus?.connected ? (
            <div className="text-xs text-neutral-500">
              Linked chat ID {telegramStatus.chat_id || "—"}.
              {telegramStatus.verified_at
                ? ` Verified ${new Date(telegramStatus.verified_at).toLocaleString()}.`
                : ""}
            </div>
          ) : (
            <div className="text-xs text-neutral-500">
              {telegramStatus?.token_hint
                ? `Last generated key ended in ${telegramStatus.token_hint}.`
                : "No Telegram link generated yet."}
            </div>
          )}
          <ol className="list-decimal pl-5 text-xs text-neutral-600 space-y-1">
            <li>Generate your personal verification link.</li>
            <li>Open it in Telegram and tap Start.</li>
            <li>Done! Admin call alerts will show up here with a chat link.</li>
          </ol>
          {telegramLink ? (
            <div className="grid gap-2">
              <label className="text-[11px] font-semibold uppercase tracking-wide text-neutral-500">
                Verification link
              </label>
              <div className="flex flex-wrap gap-2">
                <input
                  value={telegramLink}
                  readOnly
                  className="min-w-[220px] flex-1 rounded-lg border border-neutral-200 bg-white px-3 py-2 text-xs text-neutral-700"
                />
                <button
                  onClick={handleCopyTelegramLink}
                  className="rounded-lg border border-neutral-200 px-3 py-2 text-xs font-semibold text-neutral-600"
                >
                  Copy link
                </button>
                <a
                  href={telegramLink}
                  target="_blank"
                  rel="noreferrer"
                  className="rounded-lg bg-neutral-900 px-3 py-2 text-xs font-semibold text-white"
                >
                  Open Telegram
                </a>
              </div>
              <p className="text-[11px] text-neutral-500">
                Each link is unique. Generate a new one any time you need to re-connect.
              </p>
            </div>
          ) : null}
          <div className="flex flex-wrap items-center gap-2">
            <button
              onClick={handleGenerateTelegramLink}
              disabled={telegramBusy}
              className="rounded-lg bg-neutral-900 px-4 py-2 text-xs font-semibold text-white disabled:cursor-not-allowed disabled:bg-neutral-300"
            >
              {telegramBusy ? "Working..." : "Generate link"}
            </button>
            {telegramStatus?.connected ? (
              <button
                onClick={handleDisconnectTelegram}
                disabled={telegramBusy}
                className="rounded-lg border border-rose-200 px-4 py-2 text-xs font-semibold text-rose-600 disabled:cursor-not-allowed disabled:opacity-60"
              >
                Disconnect
              </button>
            ) : null}
          </div>
        </div>
      </div>
    </div>
  );
};

export default SettingsPage;
