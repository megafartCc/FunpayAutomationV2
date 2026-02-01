import React, { useCallback, useEffect, useMemo, useState } from "react";
import { useWorkspace } from "../../context/WorkspaceContext";
import { useI18n } from "../../i18n/useI18n";

type PluginsPageProps = {
  onToast?: (message: string, isError?: boolean) => void;
};

type AutoRaiseConfig = {
  enabled: boolean;
  allWorkspaces: boolean;
  intervalMinutes: number;
  workspaces: Record<number, boolean>;
};

const STORAGE_KEY = "funpay.plugins.autoRaise";
const MIN_INTERVAL = 15;
const MAX_INTERVAL = 720;
const INTERVAL_STEP = 15;

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

const PluginsPage: React.FC<PluginsPageProps> = () => {
  const { workspaces } = useWorkspace();
  const { t } = useI18n();

  const [enabled, setEnabled] = useState(false);
  const [allWorkspaces, setAllWorkspaces] = useState(true);
  const [intervalMinutes, setIntervalMinutes] = useState(120);
  const [workspaceEnabled, setWorkspaceEnabled] = useState<Record<number, boolean>>({});

  useEffect(() => {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return;
    try {
      const parsed = JSON.parse(raw) as Partial<AutoRaiseConfig>;
      if (typeof parsed.enabled === "boolean") setEnabled(parsed.enabled);
      if (typeof parsed.allWorkspaces === "boolean") setAllWorkspaces(parsed.allWorkspaces);
      if (typeof parsed.intervalMinutes === "number") setIntervalMinutes(clampInterval(parsed.intervalMinutes));
      if (parsed.workspaces && typeof parsed.workspaces === "object") {
        setWorkspaceEnabled(parsed.workspaces as Record<number, boolean>);
      }
    } catch {
      // ignore invalid storage
    }
  }, []);

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
    const payload: AutoRaiseConfig = {
      enabled,
      allWorkspaces,
      intervalMinutes,
      workspaces: workspaceEnabled,
    };
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(payload));
  }, [enabled, allWorkspaces, intervalMinutes, workspaceEnabled]);

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
  };

  return (
    <div className="space-y-6">
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
          />
          <Switch
            checked={allWorkspaces}
            onChange={() => setAllWorkspaces((prev) => !prev)}
            label={t("plugins.autoRaise.allWorkspacesTitle")}
            description={t("plugins.autoRaise.allWorkspacesDesc")}
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
              className="w-full accent-neutral-900"
            />
            <input
              type="number"
              min={MIN_INTERVAL}
              max={MAX_INTERVAL}
              step={INTERVAL_STEP}
              value={intervalMinutes}
              onChange={(event) => handleIntervalChange(Number(event.target.value))}
              className="w-24 rounded-lg border border-neutral-200 bg-white px-2 py-1 text-xs text-neutral-700"
            />
          </div>
          <div className="mt-2 flex items-center justify-between text-[11px] text-neutral-400">
            <span>{t("plugins.autoRaise.intervalMin")}</span>
            <span>{t("plugins.autoRaise.intervalMax")}</span>
          </div>
        </div>

        <div className="mt-4 flex flex-wrap items-center justify-between gap-3 text-xs text-neutral-500">
          <span>{t("plugins.autoRaise.localNotice")}</span>
          <button
            type="button"
            onClick={handleReset}
            className="rounded-lg border border-neutral-200 bg-white px-3 py-2 text-xs font-semibold text-neutral-600 transition hover:border-neutral-300"
          >
            {t("plugins.autoRaise.reset")}
          </button>
        </div>
      </div>

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
                      disabled={allWorkspaces}
                      onClick={() =>
                        setWorkspaceEnabled((prev) => ({
                          ...prev,
                          [ws.id]: !(prev[ws.id] ?? true),
                        }))
                      }
                      className={`relative inline-flex h-5 w-9 items-center rounded-full border transition ${
                        wsEnabled ? "border-emerald-500 bg-emerald-500" : "border-neutral-300 bg-white"
                      } ${allWorkspaces ? "cursor-not-allowed opacity-60" : "cursor-pointer"}`}
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
    </div>
  );
};

export default PluginsPage;
