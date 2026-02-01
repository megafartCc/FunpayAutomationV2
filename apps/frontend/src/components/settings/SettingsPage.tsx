import React, { useEffect, useMemo, useState } from "react";

import { api, TelegramStatus, WorkspaceItem, WorkspaceProxyCheck, WorkspaceStatusItem } from "../../services/api";
import { useWorkspace } from "../../context/WorkspaceContext";
import { usePreferences } from "../../context/PreferencesContext";
import { useI18n } from "../../i18n/useI18n";

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
      label: "Нет статуса",
      className: "border-neutral-200 bg-white text-neutral-500",
    };
  }
  const normalized = normalizeStatus(status.status);
  if (isStatusStale(status) && ["ok", "online", "connected", "warning", "degraded"].includes(normalized)) {
    return {
      label: "Офлайн",
      className: "border-rose-200 bg-rose-50 text-rose-700",
    };
  }
  if (["ok", "online", "connected"].includes(normalized)) {
    return {
      label: "Онлайн",
      className: "border-emerald-200 bg-emerald-50 text-emerald-700",
    };
  }
  if (["warning", "degraded"].includes(normalized)) {
    return {
      label: "Нестабильно",
      className: "border-amber-200 bg-amber-50 text-amber-700",
    };
  }
  if (["unauthorized", "auth", "auth_required", "forbidden"].includes(normalized)) {
    return {
      label: "Требуется авторизация",
      className: "border-rose-200 bg-rose-50 text-rose-700",
    };
  }
  if (["offline"].includes(normalized)) {
    return {
      label: "Офлайн",
      className: "border-rose-200 bg-rose-50 text-rose-700",
    };
  }
  if (["error", "failed"].includes(normalized)) {
    return {
      label: "Ошибка",
      className: "border-rose-200 bg-rose-50 text-rose-700",
    };
  }
  return {
    label: normalized ? normalized : "Неизвестно",
    className: "border-neutral-200 bg-white text-neutral-500",
  };
};

const SettingsPage: React.FC<SettingsPageProps> = ({ onToast }) => {
  const { visibleWorkspaces, loading, refresh, selectedPlatform } = useWorkspace();
  const { theme, setTheme, language, setLanguage } = usePreferences();
  const { t } = useI18n();
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
        keyLabel: "Золотой ключ FunPay",
        keyPlaceholder: "Золотой ключ",
        keyHelper: "Требуется для авторизации в FunPay.",
      },
      playerok: {
        keyLabel: "JSON-куки PlayerOk",
        keyPlaceholder: "Вставьте JSON-массив куки из браузера",
        keyHelper: "Вставьте JSON-массив куки, экспортированный из вашей авторизованной сессии PlayerOk.",
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
      onToast?.("Ссылка Telegram создана.");
    } catch (err) {
      onToast?.((err as { message?: string })?.message || "Не удалось создать ссылку Telegram.", true);
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
      onToast?.("Telegram отключён.");
    } catch (err) {
      onToast?.((err as { message?: string })?.message || "Не удалось отключить Telegram.", true);
    } finally {
      setTelegramBusy(false);
    }
  };

  const handleCopyTelegramLink = async () => {
    if (!telegramLink) return;
    try {
      await navigator.clipboard.writeText(telegramLink);
      onToast?.("Ссылка скопирована в буфер обмена.");
    } catch {
      onToast?.("Не удалось скопировать ссылку.", true);
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
      onToast?.("Требуются название рабочего пространства, золотой ключ и прокси.", true);
      return;
    }
    const proxyUrl = mergeProxyCredentials(newProxyUrl, newProxyUsername, newProxyPassword);
    if (!proxyUrl) {
      onToast?.("Для каждого рабочего пространства требуется URL прокси.", true);
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
      onToast?.("Рабочее пространство добавлено.");
      resetCreateForm();
      await refresh();
    } catch (err) {
      onToast?.((err as { message?: string })?.message || "Не удалось создать рабочее пространство.", true);
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
      onToast?.("Нет изменений для сохранения.", true);
      return;
    }
    setKeyActionBusy(true);
    try {
      await api.updateWorkspace(editingId, payload);
      onToast?.("Рабочее пространство обновлено.");
      cancelEdit();
      await refresh();
    } catch (err) {
      onToast?.((err as { message?: string })?.message || "Не удалось обновить рабочее пространство.", true);
    } finally {
      setKeyActionBusy(false);
    }
  };

  const handleDelete = async (id: number) => {
    if (keyActionBusy) return;
    setKeyActionBusy(true);
    try {
      await api.deleteWorkspace(id);
      onToast?.("Рабочее пространство удалено.");
      await refresh();
    } catch (err) {
      onToast?.((err as { message?: string })?.message || "Не удалось удалить рабочее пространство.", true);
    } finally {
      setKeyActionBusy(false);
    }
  };

  const handleSetDefault = async (id: number) => {
    if (keyActionBusy) return;
    setKeyActionBusy(true);
    try {
      await api.setDefaultWorkspace(id);
      onToast?.("Рабочее пространство по умолчанию обновлено.");
      await refresh();
    } catch (err) {
      onToast?.((err as { message?: string })?.message || "Не удалось обновить значение по умолчанию.", true);
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
        onToast?.(result.error || "Проверка прокси не прошла.", true);
      } else {
        onToast?.("Проверка прокси прошла.");
      }
    } catch (err) {
      const message = (err as { message?: string })?.message || "Не удалось проверить прокси.";
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
          setStatusError("Не удалось загрузить статус.");
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
      <div className="rounded-2xl border border-neutral-200 bg-white p-6 shadow-sm shadow-neutral-200/70">
        <div className="mb-4">
          <h3 className="text-lg font-semibold text-neutral-900">{t("settings.appearanceTitle")}</h3>
          <p className="text-xs text-neutral-500">{t("settings.appearanceDesc")}</p>
        </div>
        <div className="grid gap-4 md:grid-cols-2">
          <div className="space-y-2">
            <label className="text-[11px] font-semibold uppercase tracking-wide text-neutral-500">
              {t("settings.themeLabel")}
            </label>
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                onClick={() => setTheme("light")}
                className={`rounded-lg border px-3 py-2 text-xs font-semibold transition ${
                  theme === "light"
                    ? "border-amber-300 bg-amber-50 text-amber-700"
                    : "border-neutral-200 bg-white text-neutral-600 hover:border-neutral-300"
                }`}
              >
                {t("settings.themeLight")}
              </button>
              <button
                type="button"
                onClick={() => setTheme("dark")}
                className={`rounded-lg border px-3 py-2 text-xs font-semibold transition ${
                  theme === "dark"
                    ? "border-amber-300 bg-amber-50 text-amber-700"
                    : "border-neutral-200 bg-white text-neutral-600 hover:border-neutral-300"
                }`}
              >
                {t("settings.themeDark")}
              </button>
            </div>
          </div>
          <div className="space-y-2">
            <label className="text-[11px] font-semibold uppercase tracking-wide text-neutral-500">
              {t("settings.languageLabel")}
            </label>
            <select
              value={language}
              onChange={(event) => setLanguage(event.target.value as "en" | "ru")}
              className="w-full rounded-lg border border-neutral-200 bg-white px-3 py-2 text-sm text-neutral-700 outline-none"
            >
              <option value="en">{t("settings.languageEnglish")}</option>
              <option value="ru">{t("settings.languageRussian")}</option>
            </select>
          </div>
        </div>
      </div>
      <div className="rounded-2xl border border-neutral-200 bg-white p-6 shadow-sm shadow-neutral-200/70 max-h-[calc(100vh-260px)] flex flex-col">
        <div className="mb-4">
          <h3 className="text-lg font-semibold text-neutral-900">Рабочие пространства</h3>
          <p className="text-xs text-neutral-500">Подключайте несколько рабочих пространств платформ и переключайтесь между ними, не покидая панель.</p>
        </div>
        <div className="rounded-xl border border-neutral-200 bg-neutral-50 p-4">
          <div className="mb-3 text-sm font-semibold text-neutral-800">Добавить рабочее пространство</div>
          <div className="grid gap-3 md:grid-cols-2">
            <input
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              placeholder="Название рабочего пространства (например, Seller A)"
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
              placeholder="URL прокси (например, socks5://host:port[:user:pass])"
              className="w-full rounded-lg border border-neutral-200 bg-white px-3 py-2 text-sm text-neutral-700 outline-none placeholder:text-neutral-400"
            />
            <div className="grid gap-3 md:grid-cols-2">
              <input
                value={newProxyUsername}
                onChange={(e) => setNewProxyUsername(e.target.value)}
                placeholder="Логин прокси (необязательно)"
                className="w-full rounded-lg border border-neutral-200 bg-white px-3 py-2 text-sm text-neutral-700 outline-none placeholder:text-neutral-400"
              />
              <input
                value={newProxyPassword}
                onChange={(e) => setNewProxyPassword(e.target.value)}
                placeholder="Пароль прокси (необязательно)"
                type="password"
                className="w-full rounded-lg border border-neutral-200 bg-white px-3 py-2 text-sm text-neutral-700 outline-none placeholder:text-neutral-400"
              />
            </div>
            <p className="text-[11px] text-neutral-500">
              Прокси нужен для каждого рабочего пространства. Боты не запустятся без него.
            </p>
          </div>
          <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
            <label className="flex items-center gap-2 text-xs font-semibold text-neutral-600">
              <input
                type="checkbox"
                checked={newDefault}
                onChange={(event) => setNewDefault(event.target.checked)}
              />
              Сделать по умолчанию
            </label>
            <button
              onClick={handleCreate}
              disabled={keyActionBusy || !newKey.trim() || !newProxyUrl.trim() || !newName.trim()}
              className="rounded-lg bg-neutral-900 px-4 py-2 text-xs font-semibold text-white transition hover:bg-neutral-800 disabled:cursor-not-allowed disabled:bg-neutral-300"
            >Добавить рабочее пространство</button>
          </div>
        </div>
        <div className="mt-4 space-y-3 overflow-y-auto pr-1">
          {loading ? (
            <div className="rounded-xl border border-dashed border-neutral-200 bg-neutral-50 px-4 py-6 text-center text-sm text-neutral-500">
              Загрузка рабочих пространств...
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
                      const updatedLabel = updatedAt ? `Обновлено ${updatedAt.toLocaleString()}` : "";
                      const titleParts = [
                        status?.message || (status?.status ? `Статус: ${status.status}` : ""),
                        updatedLabel,
                        statusError ? statusError : "",
                      ].filter(Boolean);
                      const title = titleParts.length ? titleParts.join(" | ") : "Статуса пока нет.";
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
                        {item.is_default ? "Рабочее пространство по умолчанию" : "Рабочее пространство"}
                        {item.created_at ? ` · Добавлено ${new Date(item.created_at).toLocaleDateString()}` : ""}
                        {item.key_hint ? ` · Ключ ${item.key_hint}` : ""}
                      </div>
                    </div>
                    <div className="flex flex-wrap items-center gap-2">
                      {!item.is_default && (
                        <button
                          onClick={() => handleSetDefault(item.id)}
                          className="rounded-lg border border-neutral-200 px-3 py-1 text-xs font-semibold text-neutral-600"
                        >
                          Сделать по умолчанию
                        </button>
                      )}
                      <button
                        onClick={() => handleCheckProxy(item.id)}
                        disabled={proxyCheck?.status === "loading"}
                        className="rounded-lg border border-neutral-200 px-3 py-1 text-xs font-semibold text-neutral-600 disabled:cursor-not-allowed disabled:opacity-60"
                      >
                        {proxyCheck?.status === "loading" ? "Проверяем..." : "Проверить прокси"}
                      </button>
                      <button
                        onClick={() => (editing ? cancelEdit() : startEdit(item))}
                        className="rounded-lg border border-neutral-200 px-3 py-1 text-xs font-semibold text-neutral-600"
                      >
                        {editing ? "Закрыть" : "Редактировать"}
                      </button>
                      <button
                        onClick={() => handleDelete(item.id)}
                        className="rounded-lg border border-rose-200 px-3 py-1 text-xs font-semibold text-rose-600"
                      >
                        Удалить
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
                        {proxyCheck.ok ? "Прокси работает." : "Проверка прокси не прошла."}
                      </div>
                      <div>До: {proxyCheck.direct_ip || "?"}</div>
                      <div>После: {proxyCheck.proxy_ip || "?"}</div>
                      {!proxyCheck.ok && proxyCheck.error ? <div>{proxyCheck.error}</div> : null}
                    </div>
                  )}
                  {editing && (
                    <div className="mt-4 space-y-3">
                      <div className="grid gap-3 md:grid-cols-2">
                        <input
                          value={editName}
                          onChange={(e) => setEditName(e.target.value)}
                          placeholder="Название рабочего пространства"
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
                              placeholder="Новый JSON-куки PlayerOk (необязательно)"
                              rows={3}
                              className="w-full rounded-lg border border-neutral-200 bg-white px-3 py-2 text-sm text-neutral-700 outline-none"
                            />
                          ) : (
                            <input
                              value={editKey}
                              onChange={(e) => setEditKey(e.target.value)}
                              placeholder="Новый золотой ключ (необязательно)"
                              type="password"
                              className="w-full rounded-lg border border-neutral-200 bg-white px-3 py-2 text-sm text-neutral-700 outline-none"
                            />
                          )}
                          {item.platform === "playerok" ? (
                            <p className="text-[11px] text-neutral-500">
                              Вставьте обновлённый JSON-массив куки, чтобы повторно авторизовать PlayerOk.
                            </p>
                          ) : null}
                        </div>
                      </div>
                      <div className="grid gap-3">
                        <input
                          value={editProxyUrl}
                          onChange={(e) => setEditProxyUrl(e.target.value)}
                          placeholder="URL прокси (socks5://host:port)"
                          className="w-full rounded-lg border border-neutral-200 bg-white px-3 py-2 text-sm text-neutral-700 outline-none"
                        />
                        <div className="grid gap-3 md:grid-cols-2">
                          <input
                            value={editProxyUsername}
                            onChange={(e) => setEditProxyUsername(e.target.value)}
                            placeholder="Логин прокси"
                            className="w-full rounded-lg border border-neutral-200 bg-white px-3 py-2 text-sm text-neutral-700 outline-none"
                          />
                          <input
                            value={editProxyPassword}
                            onChange={(e) => setEditProxyPassword(e.target.value)}
                            placeholder="Пароль прокси"
                            type="password"
                            className="w-full rounded-lg border border-neutral-200 bg-white px-3 py-2 text-sm text-neutral-700 outline-none"
                          />
                        </div>
                        <p className="text-[11px] text-neutral-500">
                          Прокси должен оставаться действительным, иначе боты будут паузированы для этого пространства.
                        </p>
                      </div>
                      <div className="flex flex-wrap items-center gap-2">
                        <button
                          onClick={handleSaveEdit}
                          className="rounded-lg bg-neutral-900 px-3 py-2 text-xs font-semibold text-white"
                        >
                          Сохранить изменения
                        </button>
                        <button
                          onClick={cancelEdit}
                          className="rounded-lg border border-neutral-200 px-3 py-2 text-xs font-semibold text-neutral-600"
                        >
                          Отмена
                        </button>
                        <button
                          onClick={() => handleCheckProxy(item.id)}
                          disabled={proxyCheck?.status === "loading"}
                          className="rounded-lg border border-neutral-200 px-3 py-2 text-xs font-semibold text-neutral-600 disabled:cursor-not-allowed disabled:opacity-60"
                        >
                          {proxyCheck?.status === "loading" ? "Проверяем..." : "Проверить прокси"}
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
                            {proxyCheck.ok ? "Прокси работает." : "Проверка прокси не прошла."}
                          </div>
                          <div>До: {proxyCheck.direct_ip || "?"}</div>
                          <div>После: {proxyCheck.proxy_ip || "?"}</div>
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
              Рабочие пространства ещё не подключены.
            </div>
          )}
        </div>
      </div>
      <div className="rounded-2xl border border-neutral-200 bg-white p-6 shadow-sm shadow-neutral-200/70">
        <div className="mb-4">
          <h3 className="text-lg font-semibold text-neutral-900">Уведомления Telegram</h3>
          <p className="text-xs text-neutral-500">
            Получайте мгновенное уведомление в Telegram, когда покупатель вызывает админа в любом рабочем пространстве, включая прямую ссылку на чат.
          </p>
        </div>
        <div className="rounded-xl border border-neutral-200 bg-neutral-50 p-4 space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <div className="text-sm font-semibold text-neutral-800">Статус подключения</div>
              <p className="text-xs text-neutral-500">
                Закрепите личную ссылку, чтобы связать Telegram с этим аккаунтом.
              </p>
            </div>
            <span
              className={`rounded-full border px-3 py-1 text-xs font-semibold ${
                telegramStatus?.connected
                  ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                  : "border-neutral-200 bg-white text-neutral-600"
              }`}
            >
              {telegramStatus?.connected ? "Подключено" : "Не подключено"}
            </span>
          </div>
          {telegramStatus?.connected ? (
            <div className="text-xs text-neutral-500">
              Привязан ID чата {telegramStatus.chat_id || "—"}.
              {telegramStatus.verified_at
                ? ` Проверено ${new Date(telegramStatus.verified_at).toLocaleString()}.`
                : ""}
            </div>
          ) : (
            <div className="text-xs text-neutral-500">
              {telegramStatus?.token_hint
                ? `Последний сгенерированный ключ оканчивается на ${telegramStatus.token_hint}.`
                : "Ссылка Telegram ещё не создана."}
            </div>
          )}
          <ol className="list-decimal pl-5 text-xs text-neutral-600 space-y-1">
            <li>Сгенерируйте личную ссылку для подтверждения.</li>
            <li>Откройте её в Telegram и нажмите Start.</li>
            <li>Готово! Здесь появятся оповещения о вызове админа с ссылкой на чат.</li>
          </ol>
          {telegramLink ? (
            <div className="grid gap-2">
              <label className="text-[11px] font-semibold uppercase tracking-wide text-neutral-500">
                Ссылка для подтверждения
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
                  Скопировать ссылку
                </button>
                <a
                  href={telegramLink}
                  target="_blank"
                  rel="noreferrer"
                  className="rounded-lg bg-neutral-900 px-3 py-2 text-xs font-semibold text-white"
                >
                  Открыть Telegram
                </a>
              </div>
              <p className="text-[11px] text-neutral-500">
                Каждая ссылка уникальна. Создавайте новую, когда нужно переподключиться.
              </p>
            </div>
          ) : null}
          <div className="flex flex-wrap items-center gap-2">
            <button
              onClick={handleGenerateTelegramLink}
              disabled={telegramBusy}
              className="rounded-lg bg-neutral-900 px-4 py-2 text-xs font-semibold text-white disabled:cursor-not-allowed disabled:bg-neutral-300"
            >
              {telegramBusy ? "Работаем..." : "Создать ссылку"}
            </button>
            {telegramStatus?.connected ? (
              <button
                onClick={handleDisconnectTelegram}
                disabled={telegramBusy}
                className="rounded-lg border border-rose-200 px-4 py-2 text-xs font-semibold text-rose-600 disabled:cursor-not-allowed disabled:opacity-60"
              >
                Отключить
              </button>
            ) : null}
          </div>
        </div>
      </div>
    </div>
  );
};

export default SettingsPage;

