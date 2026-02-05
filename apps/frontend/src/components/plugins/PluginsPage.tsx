import React, { useCallback, useEffect, useMemo, useState } from "react";
import { useWorkspace } from "../../context/WorkspaceContext";
import { useI18n } from "../../i18n/useI18n";
import { api, AutoRaiseLogItem, AutoRaiseSettings, PriceDumperResponse, RaiseCategoryItem } from "../../services/api";

type PluginsPageProps = {
  onToast?: (message: string, isError?: boolean) => void;
};

const MIN_INTERVAL = 15;
const MAX_INTERVAL = 720;
const INTERVAL_STEP = 15;
const CATEGORIES_GRID = "minmax(220px,1.5fr) minmax(200px,1fr) minmax(180px,0.9fr)";

const clampInterval = (value: number) => {
  const safe = Math.min(MAX_INTERVAL, Math.max(MIN_INTERVAL, value));
  return Math.round(safe / INTERVAL_STEP) * INTERVAL_STEP;
};

const Switch: React.FC<{
  checked: boolean;
  onChange: () => void;
  disabled?: boolean;
  label: string;
  description?: string;
}> = ({ checked, onChange, disabled, label, description }) => (
  <div className={`flex items-center justify-between gap-4 rounded-xl border border-neutral-200 bg-neutral-50 p-4 ${disabled ? "opacity-60" : ""}`}>
    <div>
      <div className="text-sm font-semibold text-neutral-900">{label}</div>
      {description ? <div className="mt-1 text-xs text-neutral-500">{description}</div> : null}
    </div>
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      onClick={disabled ? undefined : onChange}
      className={`relative inline-flex h-6 w-11 items-center rounded-full border transition ${
        checked ? "border-emerald-500 bg-emerald-500" : "border-neutral-300 bg-white"
      } ${disabled ? "cursor-not-allowed" : "cursor-pointer"}`}
    >
      <span
        className={`inline-block h-5 w-5 transform rounded-full bg-white shadow transition ${
          checked ? "translate-x-5" : "translate-x-1"
        }`}
      />
    </button>
  </div>
);

const PluginsPage: React.FC<PluginsPageProps> = ({ onToast }) => {
  const { workspaces } = useWorkspace();
  const { t } = useI18n();

  const [selectedPlugin, setSelectedPlugin] = useState<"auto_raise" | "price_dumper">("auto_raise");
  const [scrapeUrl, setScrapeUrl] = useState("https://funpay.com/lots/81/");
  const [scrapeBusy, setScrapeBusy] = useState(false);
  const [scrapeResult, setScrapeResult] = useState<PriceDumperResponse | null>(null);
  const [scrapeError, setScrapeError] = useState<string | null>(null);

  const [enabled, setEnabled] = useState(false);
  const [allWorkspaces, setAllWorkspaces] = useState(true);
  const [intervalMinutes, setIntervalMinutes] = useState(120);
  const [workspaceEnabled, setWorkspaceEnabled] = useState<Record<number, boolean>>({});
  const [categories, setCategories] = useState<RaiseCategoryItem[]>([]);
  const [categoriesLoading, setCategoriesLoading] = useState(false);
  const [categoriesError, setCategoriesError] = useState<string | null>(null);
  const [settingsLoaded, setSettingsLoaded] = useState(false);
  const [settingsLoading, setSettingsLoading] = useState(false);
  const [settingsSaving, setSettingsSaving] = useState(false);
  const [settingsError, setSettingsError] = useState<string | null>(null);
  const [logs, setLogs] = useState<AutoRaiseLogItem[]>([]);
  const [logsLoading, setLogsLoading] = useState(false);
  const [logsError, setLogsError] = useState<string | null>(null);

  const workspaceMap = useMemo(() => {
    const map = new Map<number, string>();
    workspaces.forEach((ws) => map.set(ws.id, ws.name));
    return map;
  }, [workspaces]);

  const selectedWorkspaceLabel = useMemo(() => t("common.allWorkspaces"), [t]);

  const loadSettings = useCallback(async () => {
    setSettingsLoading(true);
    setSettingsError(null);
    try {
      const res = await api.getAutoRaiseSettings();
      setEnabled(Boolean(res.enabled));
      setAllWorkspaces(Boolean(res.all_workspaces));
      setIntervalMinutes(clampInterval(res.interval_minutes));
      setWorkspaceEnabled(res.workspaces || {});
      setSettingsLoaded(true);
    } catch (err) {
      const message = (err as { message?: string })?.message;
      setSettingsError(message || t("plugins.autoRaise.manualError"));
      onToast?.(message || t("plugins.autoRaise.manualError"), true);
      setSettingsLoaded(true);
    } finally {
      setSettingsLoading(false);
    }
  }, [onToast, t]);

  useEffect(() => {
    void loadSettings();
  }, [loadSettings]);

  useEffect(() => {
    setWorkspaceEnabled((prev) => {
      const next: Record<number, boolean> = {};
      workspaces.forEach((ws) => {
        next[ws.id] = prev[ws.id] ?? true;
      });
      return next;
    });
  }, [workspaces]);

  useEffect(() => {
    if (!settingsLoaded) return;
    const payload: AutoRaiseSettings = {
      enabled,
      all_workspaces: allWorkspaces,
      interval_minutes: intervalMinutes,
      workspaces: workspaceEnabled,
    };
    const handle = window.setTimeout(async () => {
      setSettingsSaving(true);
      try {
        await api.saveAutoRaiseSettings(payload);
        setSettingsError(null);
      } catch (err) {
        const message = (err as { message?: string })?.message || t("plugins.autoRaise.manualError");
        setSettingsError(message);
        onToast?.(message, true);
      } finally {
        setSettingsSaving(false);
      }
    }, 500);
    return () => window.clearTimeout(handle);
  }, [enabled, allWorkspaces, intervalMinutes, workspaceEnabled, settingsLoaded, onToast, t]);

  const loadCategories = useCallback(async () => {
    setCategoriesLoading(true);
    setCategoriesError(null);
    try {
      const res = await api.listRaiseCategories(null);
      setCategories(res.items || []);
    } catch (err) {
      const message = (err as { message?: string })?.message;
      setCategoriesError(message || t("plugins.autoRaise.parsedError"));
    } finally {
      setCategoriesLoading(false);
    }
  }, [t]);

  useEffect(() => {
    void loadCategories();
  }, [loadCategories]);

  const loadLogs = useCallback(async () => {
    setLogsLoading(true);
    setLogsError(null);
    try {
      const res = await api.listAutoRaiseLogs(null, 200);
      setLogs(res.items || []);
    } catch (err) {
      const message = (err as { message?: string })?.message;
      setLogsError(message || t("plugins.autoRaise.logsError"));
    } finally {
      setLogsLoading(false);
    }
  }, [t]);

  useEffect(() => {
    void loadLogs();
  }, [loadLogs]);

  const handleManualRaise = async () => {
    try {
      const res = await api.requestAutoRaise(null);
      const message = t("plugins.autoRaise.manualSuccess", { count: res.created });
      onToast?.(message);
      void loadLogs();
    } catch (err) {
      const message = (err as { message?: string })?.message || t("plugins.autoRaise.manualError");
      onToast?.(message, true);
    }
  };

  const sortedCategories = useMemo(() => {
    const items = [...categories];
    items.sort((a, b) => {
      const aWs = a.workspace_id ?? 0;
      const bWs = b.workspace_id ?? 0;
      if (aWs !== bWs) return aWs - bWs;
      return a.category_name.localeCompare(b.category_name);
    });
    return items;
  }, [categories]);

  const intervalLabel = useMemo(() => {
    const hours = Math.floor(intervalMinutes / 60);
    const minutes = intervalMinutes % 60;
    const hoursLabel = t("common.hoursShort");
    const minutesLabel = t("common.minutesShort");
    if (hours && minutes) return `${hours}${hoursLabel} ${minutes}${minutesLabel}`;
    if (hours) return `${hours}${hoursLabel}`;
    return `${minutes}${minutesLabel}`;
  }, [intervalMinutes, t]);

  const handleIntervalChange = useCallback((value: number) => {
    setIntervalMinutes(clampInterval(value));
  }, []);

  const formatLogTimestamp = useCallback((value?: string | null) => {
    if (!value) return "--";
    const ts = Date.parse(String(value));
    if (Number.isNaN(ts)) return String(value);
    const formatted = new Date(ts).toLocaleString("ru-RU", { timeZone: "Europe/Moscow" });
    const parts = formatted.split(", ");
    if (parts.length !== 2) return formatted;
    const [datePart, timePart] = parts;
    const dateBits = datePart.split(".");
    if (dateBits.length !== 3) return `${datePart} ${timePart}`;
    const [day, month, year] = dateBits;
    return `${day}.${month}.${year.slice(-2)} ${timePart}`;
  }, []);

  const formatLogLevel = useCallback((level?: string | null) => {
    const normalized = (level || "").toLowerCase();
    if (normalized.startsWith("warn")) return "W";
    if (normalized.startsWith("err") || normalized.startsWith("fail")) return "E";
    if (normalized.startsWith("debug")) return "D";
    return "I";
  }, []);

  const handleReset = () => {
    setEnabled(false);
    setAllWorkspaces(true);
    setIntervalMinutes(120);
    setWorkspaceEnabled((prev) => {
      const next: Record<number, boolean> = {};
      Object.keys(prev).forEach((id) => {
        next[Number(id)] = true;
      });
      return next;
    });
    setSettingsError(null);
  };

  const handleScrape = async () => {
    if (!scrapeUrl.trim()) {
      onToast?.("Введите ссылку на лот FunPay.", true);
      return;
    }
    setScrapeBusy(true);
    setScrapeError(null);
    try {
      const result = await api.scrapePriceDumper(scrapeUrl.trim());
      setScrapeResult(result);
      onToast?.("Цены и описание загружены.");
    } catch (err) {
      const message = (err as { message?: string })?.message || "Не удалось собрать данные.";
      setScrapeError(message);
      onToast?.(message, true);
    } finally {
      setScrapeBusy(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="rounded-2xl border border-neutral-200 bg-white p-6 shadow-sm shadow-neutral-200/70">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h3 className="text-lg font-semibold text-neutral-900">AI Analytics Plugins</h3>
            <p className="text-sm text-neutral-500">
              Выберите плагин и запускайте аналитику по рынку FunPay.
            </p>
          </div>
          <span className="rounded-full bg-neutral-100 px-3 py-1 text-xs font-semibold text-neutral-600">
            {selectedPlugin === "price_dumper" ? "Price Dumper AI Analytics" : t("plugins.autoRaise.title")}
          </span>
        </div>

        <div className="mt-4 grid gap-4 lg:grid-cols-[1.1fr,1.9fr]">
          <div className="rounded-xl border border-neutral-200 bg-neutral-50 p-4">
            <div className="text-sm font-semibold text-neutral-900">Плагины</div>
            <div className="mt-3 space-y-2">
              {[
                {
                  id: "auto_raise",
                  label: t("plugins.autoRaise.title"),
                  desc: t("plugins.autoRaise.desc"),
                },
                {
                  id: "price_dumper",
                  label: "Price Dumper AI Analytics",
                  desc: "Сбор цен и описаний лотов для оценки рынка.",
                },
              ].map((plugin) => {
                const isActive = selectedPlugin === plugin.id;
                return (
                  <button
                    key={plugin.id}
                    type="button"
                    onClick={() => setSelectedPlugin(plugin.id as "auto_raise" | "price_dumper")}
                    className={`w-full rounded-lg border px-3 py-3 text-left transition ${
                      isActive
                        ? "border-neutral-900 bg-white shadow-sm"
                        : "border-neutral-200 bg-white hover:border-neutral-300"
                    }`}
                  >
                    <div className="text-sm font-semibold text-neutral-900">{plugin.label}</div>
                    <div className="mt-1 text-xs text-neutral-500">{plugin.desc}</div>
                  </button>
                );
              })}
            </div>
          </div>

          <div className="rounded-xl border border-neutral-200 bg-neutral-50 p-4">
            {selectedPlugin === "price_dumper" ? (
              <div className="space-y-4">
                <div>
                  <div className="text-sm font-semibold text-neutral-900">Price Dumper AI Analytics</div>
                  <p className="mt-1 text-xs text-neutral-500">
                    Укажите ссылку на лот FunPay и запустите сбор цен/описаний.
                  </p>
                </div>
                <div className="grid gap-3 md:grid-cols-[1fr,auto]">
                  <input
                    value={scrapeUrl}
                    onChange={(event) => setScrapeUrl(event.target.value)}
                    className="w-full rounded-lg border border-neutral-200 bg-white px-3 py-2 text-sm text-neutral-700 outline-none"
                    placeholder="https://funpay.com/lots/81/"
                  />
                  <button
                    type="button"
                    onClick={handleScrape}
                    disabled={scrapeBusy}
                    className="rounded-lg bg-neutral-900 px-4 py-2 text-sm font-semibold text-white transition hover:bg-neutral-800 disabled:cursor-not-allowed disabled:bg-neutral-400"
                  >
                    {scrapeBusy ? "Сбор..." : "Собрать цены"}
                  </button>
                </div>
                {scrapeError ? (
                  <div className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-3 text-xs text-rose-600">
                    {scrapeError}
                  </div>
                ) : null}
                {scrapeResult ? (
                  <div className="rounded-xl border border-neutral-200 bg-white p-4">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div>
                        <div className="text-sm font-semibold text-neutral-900">
                          {scrapeResult.title || "Лот FunPay"}
                        </div>
                        <div className="text-xs text-neutral-400">{scrapeResult.url}</div>
                      </div>
                      <span className="rounded-full bg-neutral-100 px-3 py-1 text-xs font-semibold text-neutral-600">
                        {scrapeResult.prices.length} цен
                      </span>
                    </div>
                    {scrapeResult.description ? (
                      <p className="mt-3 text-xs text-neutral-600">{scrapeResult.description}</p>
                    ) : (
                      <p className="mt-3 text-xs text-neutral-400">Описание не найдено.</p>
                    )}
                    <div className="mt-4 rounded-lg border border-neutral-100 bg-neutral-50 p-3">
                      <div className="text-xs font-semibold text-neutral-500">Лоты аренды</div>
                      <div className="mt-2 space-y-1 text-sm text-neutral-900">
                        {scrapeResult.items?.length ? (
                          scrapeResult.items.map((item, idx) => (
                            <div key={`${item.title}-${idx}`} className="flex items-center justify-between gap-3">
                              <span className="min-w-0 truncate">
                                {item.title || scrapeResult.labels?.[idx] || `Лот ${idx + 1}`}
                              </span>
                              <span className="whitespace-nowrap font-semibold">
                                {item.price.toLocaleString("ru-RU")} {item.currency || scrapeResult.currency || "₽"}
                              </span>
                            </div>
                          ))
                        ) : (
                          <div className="text-xs text-neutral-400">Лоты аренды не найдены.</div>
                        )}
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="rounded-lg border border-dashed border-neutral-200 bg-white px-3 py-3 text-xs text-neutral-500">
                    Нажмите “Собрать цены”, чтобы увидеть результат.
                  </div>
                )}
              </div>
            ) : (
              <div className="space-y-2 text-sm text-neutral-600">
                <div className="font-semibold text-neutral-900">{t("plugins.autoRaise.title")}</div>
                <div>{t("plugins.autoRaise.desc")}</div>
                <div className="text-xs text-neutral-500">
                  Настройки автоподъёма доступны ниже на странице.
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {selectedPlugin === "auto_raise" ? (
      <div className="rounded-2xl border border-neutral-200 bg-white p-6 shadow-sm shadow-neutral-200/70">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h3 className="text-lg font-semibold text-neutral-900">{t("plugins.autoRaise.title")}</h3>
            <p className="text-sm text-neutral-500">{t("plugins.autoRaise.desc")}</p>
          </div>
          <span
            className={`rounded-full px-3 py-1 text-xs font-semibold ${
              enabled ? "bg-emerald-50 text-emerald-700" : "bg-neutral-100 text-neutral-600"
            }`}
          >
            {enabled ? t("plugins.autoRaise.statusEnabled") : t("plugins.autoRaise.statusDisabled")}
          </span>
        </div>

        <div className="mt-5 grid gap-4 md:grid-cols-2">
          <Switch
            checked={enabled}
            onChange={() => setEnabled((prev) => !prev)}
            label={t("plugins.autoRaise.toggleTitle")}
            description={t("plugins.autoRaise.toggleDesc")}
            disabled={settingsLoading}
          />
          <Switch
            checked={allWorkspaces}
            onChange={() => setAllWorkspaces((prev) => !prev)}
            label={t("plugins.autoRaise.allWorkspacesTitle")}
            description={t("plugins.autoRaise.allWorkspacesDesc")}
            disabled={settingsLoading}
          />
        </div>

        <div className="mt-4 rounded-xl border border-neutral-200 bg-neutral-50 p-4">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <div className="text-sm font-semibold text-neutral-900">{t("plugins.autoRaise.intervalTitle")}</div>
              <div className="mt-1 text-xs text-neutral-500">{t("plugins.autoRaise.intervalDesc")}</div>
            </div>
            <span className="rounded-full bg-white px-3 py-1 text-xs font-semibold text-neutral-700">
              {intervalLabel}
            </span>
          </div>
          <div className="mt-4 flex items-center gap-3">
            <input
              type="range"
              min={MIN_INTERVAL}
              max={MAX_INTERVAL}
              step={INTERVAL_STEP}
              value={intervalMinutes}
              onChange={(event) => handleIntervalChange(Number(event.target.value))}
              disabled={settingsLoading}
              className="w-full accent-neutral-900"
            />
            <input
              type="number"
              min={MIN_INTERVAL}
              max={MAX_INTERVAL}
              step={INTERVAL_STEP}
              value={intervalMinutes}
              onChange={(event) => handleIntervalChange(Number(event.target.value))}
              disabled={settingsLoading}
              className="w-24 rounded-lg border border-neutral-200 bg-white px-2 py-1 text-xs text-neutral-700"
            />
          </div>
          <div className="mt-2 flex items-center justify-between text-[11px] text-neutral-400">
            <span>{t("plugins.autoRaise.intervalMin")}</span>
            <span>{t("plugins.autoRaise.intervalMax")}</span>
          </div>
        </div>

        <div className="mt-4 flex flex-wrap items-center justify-between gap-3 text-xs text-neutral-500">
          <span>
            {t("plugins.autoRaise.localNotice")}
            {settingsSaving ? ` • ${t("common.saving")}` : ""}
          </span>
          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={handleManualRaise}
              className="rounded-lg border border-neutral-200 bg-white px-3 py-2 text-xs font-semibold text-neutral-600 transition hover:border-neutral-300"
            >
              {t("plugins.autoRaise.manualRaise")}
            </button>
            <button
              type="button"
              onClick={handleReset}
              className="rounded-lg border border-neutral-200 bg-white px-3 py-2 text-xs font-semibold text-neutral-600 transition hover:border-neutral-300"
            >
              {t("plugins.autoRaise.reset")}
            </button>
          </div>
        </div>
        {settingsError ? <div className="mt-2 text-xs text-rose-500">{settingsError}</div> : null}
      </div>
      ) : null}

      {selectedPlugin === "auto_raise" ? (
      <div className="rounded-2xl border border-neutral-200 bg-white p-6 shadow-sm shadow-neutral-200/70">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h3 className="text-lg font-semibold text-neutral-900">{t("plugins.autoRaise.workspacesTitle")}</h3>
            <p className="text-sm text-neutral-500">{t("plugins.autoRaise.workspacesDesc")}</p>
          </div>
          {allWorkspaces ? (
            <span className="text-xs text-neutral-500">{t("plugins.autoRaise.allWorkspacesNote")}</span>
          ) : null}
        </div>

        {workspaces.length === 0 ? (
          <div className="mt-4 rounded-xl border border-dashed border-neutral-200 bg-neutral-50 px-4 py-6 text-center text-sm text-neutral-500">
            {t("plugins.autoRaise.empty")}
          </div>
        ) : (
          <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {workspaces.map((ws) => {
              const wsEnabled = allWorkspaces ? enabled : workspaceEnabled[ws.id] ?? true;
              return (
                <div key={ws.id} className="rounded-xl border border-neutral-200 bg-neutral-50 p-4">
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <div className="text-sm font-semibold text-neutral-900">{ws.name}</div>
                      <div className="mt-1 text-xs text-neutral-500">
                        ID {ws.id} | {(ws.platform || "funpay").toUpperCase()}
                        {ws.is_default ? ` | ${t("common.default")}` : ""}
                      </div>
                    </div>
                    <span
                      className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${
                        wsEnabled ? "bg-emerald-50 text-emerald-700" : "bg-neutral-100 text-neutral-500"
                      }`}
                    >
                      {wsEnabled ? t("plugins.autoRaise.statusEnabled") : t("plugins.autoRaise.statusDisabled")}
                    </span>
                  </div>
                  <div className="mt-3 flex items-center justify-between gap-3">
                    <span className="text-xs text-neutral-500">
                      {wsEnabled ? t("plugins.autoRaise.enable") : t("plugins.autoRaise.disable")}
                    </span>
                    <button
                      type="button"
                      role="switch"
                      aria-checked={wsEnabled}
                      disabled={allWorkspaces || settingsLoading}
                      onClick={() =>
                        setWorkspaceEnabled((prev) => ({
                          ...prev,
                          [ws.id]: !(prev[ws.id] ?? true),
                        }))
                      }
                      className={`relative inline-flex h-5 w-9 items-center rounded-full border transition ${
                        wsEnabled ? "border-emerald-500 bg-emerald-500" : "border-neutral-300 bg-white"
                      } ${allWorkspaces || settingsLoading ? "cursor-not-allowed opacity-60" : "cursor-pointer"}`}
                    >
                      <span
                        className={`inline-block h-4 w-4 transform rounded-full bg-white shadow transition ${
                          wsEnabled ? "translate-x-4" : "translate-x-1"
                        }`}
                      />
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
      ) : null}

      {selectedPlugin === "auto_raise" ? (
      <div className="rounded-2xl border border-neutral-200 bg-white p-6 shadow-sm shadow-neutral-200/70">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h3 className="text-lg font-semibold text-neutral-900">{t("plugins.autoRaise.parsedTitle")}</h3>
            <p className="text-sm text-neutral-500">{t("plugins.autoRaise.parsedDesc")}</p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <span className="rounded-full bg-neutral-100 px-3 py-1 text-xs font-semibold text-neutral-600">
              {t("plugins.autoRaise.parsedCount", { count: sortedCategories.length })}
            </span>
            <button
              type="button"
              onClick={loadCategories}
              disabled={categoriesLoading}
              className={`rounded-lg border border-neutral-200 bg-neutral-50 px-3 py-2 text-xs font-semibold text-neutral-600 transition ${
                categoriesLoading ? "cursor-not-allowed opacity-60" : "hover:border-neutral-300"
              }`}
            >
              {t("plugins.autoRaise.parsedRefresh")}
            </button>
          </div>
        </div>
        <div className="mt-2 text-xs text-neutral-500">
          {t("plugins.autoRaise.parsedScope", { workspace: selectedWorkspaceLabel })}
        </div>

        <div className="mt-4 overflow-x-auto">
          <div className="min-w-[720px]">
            <div
              className="grid gap-3 px-4 text-xs font-semibold text-neutral-500"
              style={{ gridTemplateColumns: CATEGORIES_GRID }}
            >
              <span>{t("plugins.autoRaise.parsedColCategory")}</span>
              <span>{t("plugins.autoRaise.parsedColWorkspace")}</span>
              <span>{t("plugins.autoRaise.parsedColUpdated")}</span>
            </div>
            <div className="mt-3 space-y-3 overflow-y-auto overflow-x-hidden pr-1" style={{ maxHeight: "420px" }}>
              {categoriesLoading && (
                <div className="rounded-xl border border-dashed border-neutral-200 bg-neutral-50 px-4 py-6 text-center text-sm text-neutral-500">
                  {t("plugins.autoRaise.parsedLoading")}
                </div>
              )}
              {!categoriesLoading && categoriesError && (
                <div className="rounded-xl border border-rose-100 bg-rose-50 px-4 py-6 text-center text-sm text-rose-600">
                  {categoriesError}
                </div>
              )}
              {!categoriesLoading &&
                !categoriesError &&
                sortedCategories.map((category) => {
                  const workspaceLabel =
                    category.workspace_id !== null && category.workspace_id !== undefined
                      ? workspaceMap.get(category.workspace_id) ||
                        `${t("common.workspace")} ${category.workspace_id}`
                      : t("common.allWorkspaces");
                  const updatedAt = category.updated_at
                    ? new Date(category.updated_at).toLocaleString("ru-RU", { timeZone: "Europe/Moscow" })
                    : "-";
                  return (
                    <div
                      key={`${category.workspace_id ?? "all"}-${category.category_id}`}
                      className="grid items-center gap-3 rounded-xl border border-neutral-100 bg-neutral-50 px-4 py-3 text-sm shadow-[0_4px_18px_-14px_rgba(0,0,0,0.18)]"
                      style={{ gridTemplateColumns: CATEGORIES_GRID }}
                    >
                      <div className="min-w-0">
                        <div className="truncate font-semibold text-neutral-900">{category.category_name}</div>
                        <div className="text-xs text-neutral-400">ID {category.category_id}</div>
                      </div>
                      <span className="min-w-0 truncate text-xs text-neutral-600">{workspaceLabel}</span>
                      <span className="min-w-0 truncate text-xs text-neutral-500">{updatedAt}</span>
                    </div>
                  );
                })}
              {!categoriesLoading && !categoriesError && sortedCategories.length === 0 && (
                <div className="rounded-xl border border-dashed border-neutral-200 bg-neutral-50 px-4 py-6 text-center text-sm text-neutral-500">
                  {t("plugins.autoRaise.parsedEmpty")}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
      ) : null}

      {selectedPlugin === "auto_raise" ? (
      <div className="rounded-2xl border border-neutral-200 bg-white p-6 shadow-sm shadow-neutral-200/70">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h3 className="text-lg font-semibold text-neutral-900">{t("plugins.autoRaise.logsTitle")}</h3>
            <p className="text-sm text-neutral-500">{t("plugins.autoRaise.logsDesc")}</p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <span className="rounded-full bg-neutral-100 px-3 py-1 text-xs font-semibold text-neutral-600">
              {t("plugins.autoRaise.logsCount", { count: logs.length })}
            </span>
            <button
              type="button"
              onClick={loadLogs}
              disabled={logsLoading}
              className={`rounded-lg border border-neutral-200 bg-neutral-50 px-3 py-2 text-xs font-semibold text-neutral-600 transition ${
                logsLoading ? "cursor-not-allowed opacity-60" : "hover:border-neutral-300"
              }`}
            >
              {t("plugins.autoRaise.logsRefresh")}
            </button>
          </div>
        </div>

        <div className="mt-4 space-y-2 overflow-y-auto pr-1" style={{ maxHeight: "420px" }}>
          {logsLoading && (
            <div className="rounded-xl border border-dashed border-neutral-200 bg-neutral-50 px-4 py-6 text-center text-sm text-neutral-500">
              {t("plugins.autoRaise.logsLoading")}
            </div>
          )}
          {!logsLoading && logsError && (
            <div className="rounded-xl border border-rose-100 bg-rose-50 px-4 py-6 text-center text-sm text-rose-600">
              {logsError}
            </div>
          )}
          {!logsLoading &&
            !logsError &&
            logs.map((log) => {
              const level = formatLogLevel(log.level);
              const source = log.source || "auto_raise";
              const line = log.line ?? "--";
              const timeLabel = formatLogTimestamp(log.created_at);
              const wsLabel =
                log.workspace_id !== null && log.workspace_id !== undefined
                  ? workspaceMap.get(log.workspace_id) || `${t("common.workspace")} ${log.workspace_id}`
                  : t("common.allWorkspaces");
              const lineText = `[${timeLabel}][${source}][${line}]> ${level}: ${log.message}`;
              return (
                <div
                  key={log.id}
                  className="flex flex-wrap items-start justify-between gap-3 rounded-xl border border-neutral-100 bg-neutral-50 px-4 py-3 text-xs text-neutral-600"
                >
                  <span className="break-all font-mono text-[11px] text-neutral-700">{lineText}</span>
                  <span className="text-[10px] text-neutral-400">{wsLabel}</span>
                </div>
              );
            })}
          {!logsLoading && !logsError && logs.length === 0 && (
            <div className="rounded-xl border border-dashed border-neutral-200 bg-neutral-50 px-4 py-6 text-center text-sm text-neutral-500">
              {t("plugins.autoRaise.logsEmpty")}
            </div>
          )}
        </div>
      </div>
      ) : null}
    </div>
  );
};

export default PluginsPage;
