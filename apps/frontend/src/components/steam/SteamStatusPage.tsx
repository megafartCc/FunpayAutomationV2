import React, { useEffect, useMemo, useState } from "react";
import { motion } from "framer-motion";

import { api, SteamBridgeAccount, SteamPresenceAccount } from "../../services/api";
import { useWorkspace } from "../../context/WorkspaceContext";
import { useI18n } from "../../i18n/useI18n";

type SteamStatusPageProps = {
  onToast?: (message: string, isError?: boolean) => void;
};

const formatDateTime = (value?: string | null) => {
  if (!value) return "-";
  const normalized = value.includes("T") ? value : value.replace(" ", "T");
  const parsed = new Date(normalized);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleString();
};

const bridgeStatusMeta = (status?: string) => {
  const normalized = (status || "").toLowerCase();
  if (normalized.includes("online")) {
    return {
      label: "Online",
      className:
        "border border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-500/40 dark:bg-emerald-500/15 dark:text-emerald-200",
    };
  }
  if (normalized.includes("connect")) {
    return {
      label: "Connecting",
      className:
        "border border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-500/40 dark:bg-amber-500/15 dark:text-amber-200",
    };
  }
  if (normalized.includes("error")) {
    return {
      label: "Error",
      className:
        "border border-rose-200 bg-rose-50 text-rose-700 dark:border-rose-500/40 dark:bg-rose-500/15 dark:text-rose-200",
    };
  }
  return {
    label: "Offline",
    className:
      "border border-rose-200 bg-rose-50 text-rose-700 dark:border-rose-500/40 dark:bg-rose-500/15 dark:text-rose-200",
  };
};

const presenceMeta = (status?: string) => {
  const normalized = (status || "").toLowerCase();
  if (normalized.includes("match"))
    return {
      label: "In match",
      className:
        "border border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-500/40 dark:bg-emerald-500/15 dark:text-emerald-200",
    };
  if (normalized.includes("game"))
    return {
      label: "In game",
      className:
        "border border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-500/40 dark:bg-amber-500/15 dark:text-amber-200",
    };
  if (normalized.includes("demo"))
    return {
      label: "Demo",
      className:
        "border border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-500/40 dark:bg-amber-500/15 dark:text-amber-200",
    };
  if (normalized.includes("bot"))
    return {
      label: "Bot match",
      className:
        "border border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-500/40 dark:bg-amber-500/15 dark:text-amber-200",
    };
  if (normalized.includes("custom"))
    return {
      label: "Custom",
      className:
        "border border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-500/40 dark:bg-amber-500/15 dark:text-amber-200",
    };
  if (!normalized || normalized.includes("off"))
    return {
      label: "Offline",
      className:
        "border border-rose-200 bg-rose-50 text-rose-700 dark:border-rose-500/40 dark:bg-rose-500/15 dark:text-rose-200",
    };
  return {
    label: status || "Unknown",
    className:
      "border border-neutral-200 bg-neutral-100 text-neutral-700 dark:border-neutral-500/40 dark:bg-neutral-500/10 dark:text-neutral-200",
  };
};

const SteamStatusPage: React.FC<SteamStatusPageProps> = ({ onToast }) => {
  const { selectedId } = useWorkspace();
  const { t } = useI18n();
  const workspaceId = selectedId === "all" ? null : (selectedId as number | null);
  const [bridgeAccounts, setBridgeAccounts] = useState<SteamBridgeAccount[]>([]);
  const [presenceAccounts, setPresenceAccounts] = useState<SteamPresenceAccount[]>([]);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [formLabel, setFormLabel] = useState("");
  const [formLogin, setFormLogin] = useState("");
  const [formPassword, setFormPassword] = useState("");
  const [formSecret, setFormSecret] = useState("");
  const [formDefault, setFormDefault] = useState(false);
  const [formAutoConnect, setFormAutoConnect] = useState(true);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [actionBusyId, setActionBusyId] = useState<number | null>(null);

  const stats = useMemo(() => {
    const connected = bridgeAccounts.filter((acc) => (acc.status || "").toLowerCase().includes("online")).length;
    const errors = bridgeAccounts.filter((acc) => (acc.status || "").toLowerCase().includes("error")).length;
    const missingSteam = presenceAccounts.filter((acc) => !acc.steam_id).length;
    const inMatch = presenceAccounts.filter((acc) => acc.in_match).length;
    const inGame = presenceAccounts.filter((acc) => acc.in_game).length;
    return { connected, errors, missingSteam, inMatch, inGame };
  }, [bridgeAccounts, presenceAccounts]);

  const loadData = async (refreshBridge?: boolean) => {
    setLoading(true);
    try {
      const [bridgeRes, presenceRes] = await Promise.all([
        api.listSteamBridgeAccounts(Boolean(refreshBridge)),
        api.listSteamPresenceAccounts(workspaceId),
      ]);
      setBridgeAccounts(bridgeRes.items || []);
      setPresenceAccounts(presenceRes.items || []);
    } catch (err) {
      onToast?.((err as { message?: string })?.message || "Failed to load Steam status.", true);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadData();
  }, [workspaceId]);

  const resetForm = () => {
    setFormLabel("");
    setFormLogin("");
    setFormPassword("");
    setFormSecret("");
    setFormDefault(false);
    setFormAutoConnect(true);
    setEditingId(null);
  };

  const handleSave = async () => {
    const isEditing = editingId !== null;
    if (!isEditing && (!formLogin.trim() || !formPassword.trim())) {
      onToast?.("Steam login and password are required.", true);
      return;
    }
    setSaving(true);
    try {
      if (isEditing) {
        const payload: {
          label?: string | null;
          login?: string | null;
          password?: string | null;
          shared_secret?: string | null;
          is_default?: boolean | null;
        } = {
          label: formLabel.trim() || null,
          is_default: formDefault,
        };
        if (formLogin.trim()) payload.login = formLogin.trim();
        if (formPassword.trim()) payload.password = formPassword;
        if (formSecret.trim()) payload.shared_secret = formSecret.trim();
        await api.updateSteamBridgeAccount(editingId, payload);
        if (formAutoConnect) {
          await api.connectSteamBridgeAccount(editingId);
        }
        onToast?.("Steam bridge account updated.");
      } else {
        await api.createSteamBridgeAccount({
          label: formLabel.trim() || null,
          login: formLogin.trim(),
          password: formPassword,
          shared_secret: formSecret.trim() || null,
          is_default: formDefault,
          auto_connect: formAutoConnect,
        });
        onToast?.("Steam bridge account saved.");
      }
      resetForm();
      await loadData(true);
    } catch (err) {
      onToast?.((err as { message?: string })?.message || "Failed to save Steam bridge account.", true);
    } finally {
      setSaving(false);
    }
  };

  const handleEdit = (item: SteamBridgeAccount) => {
    setEditingId(item.id);
    setFormLabel(item.label || "");
    setFormLogin("");
    setFormPassword("");
    setFormSecret("");
    setFormDefault(!!item.is_default);
    setFormAutoConnect(false);
  };

  const handleConnect = async (bridgeId: number) => {
    setActionBusyId(bridgeId);
    try {
      await api.connectSteamBridgeAccount(bridgeId);
      await loadData(true);
      onToast?.("Bridge connected.");
    } catch (err) {
      onToast?.((err as { message?: string })?.message || "Failed to connect bridge.", true);
    } finally {
      setActionBusyId(null);
    }
  };

  const handleDisconnect = async (bridgeId: number) => {
    setActionBusyId(bridgeId);
    try {
      await api.disconnectSteamBridgeAccount(bridgeId);
      await loadData(true);
      onToast?.("Bridge disconnected.");
    } catch (err) {
      onToast?.((err as { message?: string })?.message || "Failed to disconnect bridge.", true);
    } finally {
      setActionBusyId(null);
    }
  };

  const handleSetDefault = async (bridgeId: number) => {
    setActionBusyId(bridgeId);
    try {
      await api.setDefaultSteamBridgeAccount(bridgeId);
      await loadData(true);
      onToast?.("Default bridge updated.");
    } catch (err) {
      onToast?.((err as { message?: string })?.message || "Failed to update default bridge.", true);
    } finally {
      setActionBusyId(null);
    }
  };

  const handleDelete = async (bridgeId: number) => {
    setActionBusyId(bridgeId);
    try {
      await api.deleteSteamBridgeAccount(bridgeId);
      await loadData(true);
      onToast?.("Bridge account removed.");
    } catch (err) {
      onToast?.((err as { message?: string })?.message || "Failed to remove bridge.", true);
    } finally {
      setActionBusyId(null);
    }
  };

  const issues = useMemo(() => {
    const list: { title: string; detail: string }[] = [];
    if (!bridgeAccounts.length) {
      list.push({
        title: "No bridge accounts connected",
        detail: "Add a Steam login so presence tracking can start.",
      });
    } else if (!bridgeAccounts.some((acc) => (acc.status || "").toLowerCase().includes("online"))) {
      list.push({
        title: "Bridge offline",
        detail: "Connect at least one Steam bridge to receive live statuses.",
      });
    }
    if (stats.missingSteam > 0) {
      list.push({
        title: "Accounts without Steam ID",
        detail: `${stats.missingSteam} account(s) are missing Steam IDs. Update maFile or account data.`,
      });
    }
    return list;
  }, [bridgeAccounts, stats.missingSteam]);

  const positives = useMemo(() => {
    const list: { title: string; detail: string }[] = [];
    if (stats.connected > 0) {
      list.push({
        title: "Bridge online",
        detail: `${stats.connected} bridge(s) are connected and tracking presence.`,
      });
    }
    if (stats.inMatch > 0) {
      list.push({
        title: "Live matches detected",
        detail: `${stats.inMatch} rental(s) currently in a live match.`,
      });
    }
    if (presenceAccounts.length && stats.missingSteam === 0) {
      list.push({
        title: "Steam IDs complete",
        detail: "Every account has a Steam ID, so match detection is reliable.",
      });
    }
    if (!list.length) {
      list.push({
        title: "Waiting for data",
        detail: "Connect a bridge and add Steam IDs to start tracking.",
      });
    }
    return list;
  }, [presenceAccounts.length, stats.connected, stats.inMatch, stats.missingSteam]);

  return (
    <div className="grid gap-6">
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.35 }}
        className="panel"
      >
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="text-xs font-semibold uppercase tracking-wide text-neutral-500">
              Steam Status Checker
            </div>
            <h2 className="mt-2 text-2xl font-semibold text-neutral-900">
              Live Steam presence for your rentals
            </h2>
            <p className="mt-2 max-w-2xl text-sm text-neutral-600">
              Each user can connect multiple Steam accounts. The default bridge is used for match detection,
              deauthorize timing, and status panels.
            </p>
          </div>
          <div className="flex flex-wrap gap-3">
            <div className="card px-4 py-3 text-sm text-neutral-700">
              <div className="text-xs uppercase tracking-wide">Connected</div>
              <div className="text-xl font-semibold">{stats.connected}</div>
            </div>
            <div className="card px-4 py-3 text-sm text-neutral-700">
              <div className="text-xs uppercase tracking-wide">In match</div>
              <div className="text-xl font-semibold">{stats.inMatch}</div>
            </div>
            <div className="card px-4 py-3 text-sm text-neutral-700">
              <div className="text-xs uppercase tracking-wide">Errors</div>
              <div className="text-xl font-semibold">{stats.errors}</div>
            </div>
          </div>
        </div>
      </motion.div>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1.15fr)_minmax(0,0.85fr)]">
        <div className="space-y-6">
          <div className="panel">
            <div className="flex items-center justify-between gap-3">
              <div>
                <h3 className="text-lg font-semibold text-neutral-900">Bridge accounts</h3>
                <p className="text-xs text-neutral-500">
                  Connect multiple Steam accounts. The default bridge powers presence for all rental checks.
                </p>
              </div>
              <button
                type="button"
                onClick={() => loadData(true)}
                disabled={loading}
                className="rounded-lg border border-neutral-200 px-3 py-2 text-xs font-semibold text-neutral-600 disabled:opacity-60"
              >
                Refresh
              </button>
            </div>

            <div className="mt-4 grid gap-3">
              {bridgeAccounts.length ? (
                bridgeAccounts.map((item) => {
                  const meta = bridgeStatusMeta(item.status);
                  const busy = actionBusyId === item.id;
                  return (
                    <div
                      key={item.id}
                      className="rounded-xl border border-neutral-200 bg-white px-4 py-3 shadow-sm"
                    >
                      <div className="flex flex-wrap items-start justify-between gap-3">
                        <div>
                          <div className="flex items-center gap-2 text-sm font-semibold text-neutral-900">
                            <span>{item.label || `Bridge #${item.id}`}</span>
                            {item.is_default ? (
                              <span className="rounded-full bg-neutral-900 px-2 py-0.5 text-[10px] font-semibold uppercase text-white">
                                Default
                              </span>
                            ) : null}
                            <span className={`rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase ${meta.className}`}>
                              {meta.label}
                            </span>
                          </div>
                          <div className="text-xs text-neutral-500">
                            Login: {item.login_masked} | Last seen {formatDateTime(item.last_seen)}
                          </div>
                          {item.last_error ? (
                            <div className="mt-2 rounded-lg border border-neutral-200 bg-neutral-50 px-2 py-1 text-[11px] text-neutral-600">
                              {item.last_error}
                            </div>
                          ) : null}
                        </div>
                        <div className="flex flex-wrap gap-2">
                          <button
                            type="button"
                            onClick={() => handleConnect(item.id)}
                            disabled={busy}
                            className="rounded-lg bg-neutral-900 px-3 py-1.5 text-xs font-semibold text-white disabled:opacity-60"
                          >
                            Connect
                          </button>
                          <button
                            type="button"
                            onClick={() => handleDisconnect(item.id)}
                            disabled={busy}
                            className="rounded-lg border border-neutral-200 px-3 py-1.5 text-xs font-semibold text-neutral-600 disabled:opacity-60"
                          >
                            Disconnect
                          </button>
                          <button
                            type="button"
                            onClick={() => handleEdit(item)}
                            disabled={busy}
                            className="rounded-lg border border-neutral-200 px-3 py-1.5 text-xs font-semibold text-neutral-600 disabled:opacity-60"
                          >
                            Edit
                          </button>
                          {!item.is_default ? (
                            <button
                              type="button"
                              onClick={() => handleSetDefault(item.id)}
                              disabled={busy}
                              className="rounded-lg border border-neutral-200 px-3 py-1.5 text-xs font-semibold text-neutral-600 disabled:opacity-60"
                            >
                              Set default
                            </button>
                          ) : null}
                          <button
                            type="button"
                            onClick={() => handleDelete(item.id)}
                            disabled={busy}
                            className="rounded-lg border border-neutral-200 px-3 py-1.5 text-xs font-semibold text-neutral-600 disabled:opacity-60"
                          >
                            Delete
                          </button>
                        </div>
                      </div>
                    </div>
                  );
                })
              ) : (
                <div className="rounded-xl border border-dashed border-neutral-200 bg-neutral-50 px-4 py-6 text-center text-sm text-neutral-500">
                  No Steam bridge accounts yet.
                </div>
              )}
            </div>
          </div>

          <div className="panel">
            <div className="flex items-center justify-between gap-3">
              <div>
                <h3 className="text-lg font-semibold text-neutral-900">Presence overview</h3>
                <p className="text-xs text-neutral-500">
                  Real-time match status for accounts with Steam IDs.
                </p>
              </div>
              <span className="rounded-full border border-neutral-200 bg-neutral-50 px-3 py-1 text-xs font-semibold text-neutral-600">
                {presenceAccounts.length} accounts
              </span>
            </div>

            <div className="mt-4 grid gap-2 max-h-[560px] overflow-y-auto pr-2">
              {presenceAccounts.length ? (
                presenceAccounts.map((item) => {
                  const meta = presenceMeta(item.status);
                  return (
                    <div
                      key={`${item.account_id}-${item.workspace_id ?? "none"}`}
                      className="grid grid-cols-[minmax(0,1fr)_minmax(0,0.8fr)_minmax(0,0.5fr)] items-center gap-4 rounded-xl border border-neutral-200 bg-white px-4 py-3 text-sm shadow-sm"
                    >
                      <div>
                        <div className="font-semibold text-neutral-900">{item.account_name}</div>
                        <div className="text-xs text-neutral-500">
                          {item.workspace_name || t("common.workspace")} | {item.steam_id || "Steam ID missing"}
                        </div>
                      </div>
                      <div className="text-xs text-neutral-500">
                        {item.hero ? `Hero: ${item.hero}` : "-"}
                        <div>{item.match_time ? `Match: ${item.match_time}` : ""}</div>
                      </div>
                      <div className="flex items-center justify-end">
                        <span className={`rounded-full px-2 py-1 text-xs font-semibold ${meta.className}`}>
                          {meta.label}
                        </span>
                      </div>
                    </div>
                  );
                })
              ) : (
                <div className="rounded-xl border border-dashed border-neutral-200 bg-neutral-50 px-4 py-6 text-center text-sm text-neutral-500">
                  No presence data yet. Connect a bridge account and ensure Steam IDs are available.
                </div>
              )}
            </div>
          </div>
        </div>

        <div className="space-y-6">
          <div className="panel">
            <h3 className="text-lg font-semibold text-neutral-900">
              {editingId ? "Edit bridge account" : "Add bridge account"}
            </h3>
            <p className="text-xs text-neutral-500">
              Credentials are encrypted at rest. Shared secret enables 2FA.
            </p>
            {editingId ? (
              <div className="mt-2 text-[11px] text-neutral-500">
                Leave login/password/secret blank to keep the current values.
              </div>
            ) : null}
            <div className="mt-4 grid gap-3">
              <input
                value={formLabel}
                onChange={(e) => setFormLabel(e.target.value)}
                placeholder="Label (optional)"
                className="w-full rounded-lg border border-neutral-200 bg-white px-3 py-2 text-sm text-neutral-700 outline-none placeholder:text-neutral-400"
              />
              <input
                value={formLogin}
                onChange={(e) => setFormLogin(e.target.value)}
                placeholder={editingId ? "Steam login (leave blank to keep)" : "Steam login"}
                className="w-full rounded-lg border border-neutral-200 bg-white px-3 py-2 text-sm text-neutral-700 outline-none placeholder:text-neutral-400"
              />
              <input
                value={formPassword}
                onChange={(e) => setFormPassword(e.target.value)}
                placeholder={editingId ? "Steam password (leave blank to keep)" : "Steam password"}
                type="password"
                className="w-full rounded-lg border border-neutral-200 bg-white px-3 py-2 text-sm text-neutral-700 outline-none placeholder:text-neutral-400"
              />
              <input
                value={formSecret}
                onChange={(e) => setFormSecret(e.target.value)}
                placeholder={editingId ? "Shared secret (leave blank to keep)" : "Shared secret (optional)"}
                className="w-full rounded-lg border border-neutral-200 bg-white px-3 py-2 text-sm text-neutral-700 outline-none placeholder:text-neutral-400"
              />
              <label className="flex items-center gap-2 text-xs text-neutral-600">
                <input
                  type="checkbox"
                  checked={formDefault}
                  onChange={(e) => setFormDefault(e.target.checked)}
                />
                Set as default bridge
              </label>
              <label className="flex items-center gap-2 text-xs text-neutral-600">
                <input
                  type="checkbox"
                  checked={formAutoConnect}
                  onChange={(e) => setFormAutoConnect(e.target.checked)}
                />
                Connect immediately
              </label>
              <button
                type="button"
                onClick={handleSave}
                disabled={saving}
                className="rounded-lg bg-neutral-900 px-4 py-2 text-xs font-semibold text-white disabled:opacity-60"
              >
                {saving ? t("common.saving") : editingId ? "Save changes" : "Save bridge"}
              </button>
              {editingId ? (
                <button
                  type="button"
                  onClick={resetForm}
                  className="rounded-lg border border-neutral-200 px-4 py-2 text-xs font-semibold text-neutral-600"
                >
                  Cancel edit
                </button>
              ) : null}
            </div>
          </div>

          <div className="panel">
            <h3 className="text-lg font-semibold text-neutral-900">Signals</h3>
            <p className="text-xs text-neutral-500">
              Quick read on what is healthy vs what needs attention.
            </p>
            <div className="mt-4 space-y-4">
              <div>
                <div className="text-xs font-semibold uppercase tracking-wide text-neutral-500">
                  Good
                </div>
                <div className="mt-2 space-y-2">
                  {positives.map((item, idx) => (
                    <div
                      key={`${item.title}-${idx}`}
                      className="rounded-xl border border-neutral-200 bg-neutral-50 px-3 py-2 text-xs text-neutral-600"
                    >
                      <div className="font-semibold">{item.title}</div>
                      <div>{item.detail}</div>
                    </div>
                  ))}
                </div>
              </div>
              <div>
                <div className="text-xs font-semibold uppercase tracking-wide text-neutral-500">
                  Risks
                </div>
                <div className="mt-2 space-y-2">
                  {issues.length ? (
                    issues.map((issue, idx) => (
                      <div
                        key={`${issue.title}-${idx}`}
                        className="rounded-xl border border-neutral-200 bg-neutral-50 px-3 py-2 text-xs text-neutral-600"
                      >
                        <div className="font-semibold">{issue.title}</div>
                        <div>{issue.detail}</div>
                      </div>
                    ))
                  ) : (
                    <div className="rounded-xl border border-neutral-200 bg-neutral-50 px-3 py-2 text-xs text-neutral-600">
                      No risks detected right now.
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default SteamStatusPage;
