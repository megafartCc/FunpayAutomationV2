import React, { useMemo, useState } from "react";

import { api, WorkspaceItem, WorkspaceProxyCheck } from "../../services/api";
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

const SettingsPage: React.FC<SettingsPageProps> = ({ onToast }) => {
  const { workspaces, loading, refresh } = useWorkspace();
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

  const workspaceList = useMemo(() => workspaces || [], [workspaces]);

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
    </div>
  );
};

export default SettingsPage;
