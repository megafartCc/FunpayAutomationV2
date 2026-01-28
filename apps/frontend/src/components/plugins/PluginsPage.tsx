import React, { useCallback, useEffect, useMemo, useState } from "react";

import {
  api,
  AutoRaiseHistoryItem,
  AutoRaiseSettings,
  FunpayCategoryItem,
} from "../../services/api";


type PluginsPageProps = {
  onToast?: (message: string, isError?: boolean) => void;
};

const defaultSettings: AutoRaiseSettings = {
  enabled: false,
  categories: [],
  interval_hours: 1,
};

const PluginsPage: React.FC<PluginsPageProps> = ({ onToast }) => {
  const [settings, setSettings] = useState<AutoRaiseSettings>(defaultSettings);
  const [draft, setDraft] = useState<AutoRaiseSettings>(defaultSettings);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const [categories, setCategories] = useState<FunpayCategoryItem[]>([]);
  const [categoryQuery, setCategoryQuery] = useState("");
  const [categoriesLoading, setCategoriesLoading] = useState(false);

  const [history, setHistory] = useState<AutoRaiseHistoryItem[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);

  const normalizeDraft = useCallback((next: AutoRaiseSettings) => {
    const unique = Array.from(new Set(next.categories || [])).sort((a, b) => a - b);
    return {
      ...next,
      interval_hours: Math.min(6, Math.max(1, Number(next.interval_hours) || 1)),
      categories: unique,
    };
  }, []);

  const loadSettings = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.getAutoRaiseSettings();
      const normalized = normalizeDraft(res);
      setSettings(normalized);
      setDraft(normalized);
    } catch (err) {
      const message = (err as { message?: string })?.message || "Failed to load auto raise settings.";
      onToast?.(message, true);
    } finally {
      setLoading(false);
    }
  }, [normalizeDraft, onToast]);

  const loadCategories = useCallback(async () => {
    setCategoriesLoading(true);
    try {
      const res = await api.listFunpayCategories();
      setCategories(res.items || []);
    } catch (err) {
      const message = (err as { message?: string })?.message || "Failed to load FunPay categories.";
      onToast?.(message, true);
    } finally {
      setCategoriesLoading(false);
    }
  }, [onToast]);

  const loadHistory = useCallback(async () => {
    setHistoryLoading(true);
    try {
      const res = await api.listAutoRaiseHistory(200);
      setHistory(res.items || []);
    } catch (err) {
      const message = (err as { message?: string })?.message || "Failed to load auto raise history.";
      onToast?.(message, true);
    } finally {
      setHistoryLoading(false);
    }
  }, [onToast]);

  useEffect(() => {
    void loadSettings();
    void loadCategories();
    void loadHistory();
  }, [loadSettings, loadCategories, loadHistory]);

  const dirty = useMemo(() => JSON.stringify(settings) !== JSON.stringify(draft), [settings, draft]);

  const toggleCategory = (categoryId: number) => {
    setDraft((prev) => {
      const selected = new Set(prev.categories || []);
      if (selected.has(categoryId)) {
        selected.delete(categoryId);
      } else {
        selected.add(categoryId);
      }
      return normalizeDraft({ ...prev, categories: Array.from(selected) });
    });
  };

  const handleSave = async () => {
    if (saving) return;
    setSaving(true);
    try {
      const payload = normalizeDraft(draft);
      const res = await api.updateAutoRaiseSettings(payload);
      const normalized = normalizeDraft(res);
      setSettings(normalized);
      setDraft(normalized);
      onToast?.("Auto raise settings saved.");
    } catch (err) {
      const message = (err as { message?: string })?.message || "Failed to update auto raise settings.";
      onToast?.(message, true);
    } finally {
      setSaving(false);
    }
  };

  const handleReset = () => {
    setDraft(settings);
  };

  const filteredCategories = useMemo(() => {
    const query = categoryQuery.trim().toLowerCase();
    if (!query) return categories;
    return categories.filter((item) => {
      const name = (item.name || "").toLowerCase();
      const game = (item.game || "").toLowerCase();
      const category = (item.category || "").toLowerCase();
      return name.includes(query) || game.includes(query) || category.includes(query);
    });
  }, [categories, categoryQuery]);

  const selectedCount = draft.categories.length;

  const formatTimestamp = (value?: string | null) => {
    if (!value) return "-";
    const parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) return value;
    return parsed.toLocaleString();
  };

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,1.1fr)_minmax(0,0.9fr)]">
      <div className="rounded-2xl border border-neutral-200 bg-white p-6 shadow-sm shadow-neutral-200/70">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h3 className="text-lg font-semibold text-neutral-900">Auto Raise</h3>
            <p className="text-xs text-neutral-500">
              Applies to all FunPay workspaces. Raises lots sequentially with your chosen interval.
            </p>
          </div>
          <label className="flex items-center gap-2 text-xs font-semibold text-neutral-600">
            <input
              type="checkbox"
              className="h-4 w-4 rounded border-neutral-300 text-neutral-900"
              checked={draft.enabled}
              onChange={(e) => setDraft((prev) => ({ ...prev, enabled: e.target.checked }))}
              disabled={loading}
            />
            Enabled
          </label>
        </div>

        <div className="mt-5 grid gap-4">
          <div className="rounded-xl border border-neutral-200 bg-neutral-50 p-4">
            <div className="flex items-center justify-between gap-3">
              <div>
                <div className="text-sm font-semibold text-neutral-900">Interval between workspaces</div>
                <div className="text-xs text-neutral-500">Wait time before the next workspace raise.</div>
              </div>
              <div className="rounded-full border border-neutral-200 bg-white px-3 py-1 text-xs font-semibold text-neutral-700">
                {draft.interval_hours}h
              </div>
            </div>
            <input
              type="range"
              min={1}
              max={6}
              step={1}
              value={draft.interval_hours}
              onChange={(e) =>
                setDraft((prev) => ({
                  ...prev,
                  interval_hours: Number(e.target.value),
                }))
              }
              className="mt-4 w-full accent-neutral-900"
            />
          </div>

          <div className="rounded-xl border border-neutral-200 bg-neutral-50 p-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <div className="text-sm font-semibold text-neutral-900">FunPay categories</div>
                <div className="text-xs text-neutral-500">
                  Search and select the categories to auto raise. ({selectedCount} selected)
                </div>
              </div>
              <button
                type="button"
                onClick={loadCategories}
                disabled={categoriesLoading}
                className="rounded-lg border border-neutral-200 bg-white px-3 py-1.5 text-xs font-semibold text-neutral-600 transition hover:bg-neutral-100 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {categoriesLoading ? "Refreshing..." : "Refresh categories"}
              </button>
            </div>
            <div className="mt-3">
              <input
                type="search"
                value={categoryQuery}
                onChange={(e) => setCategoryQuery(e.target.value)}
                placeholder="Search categories or games..."
                className="w-full rounded-lg border border-neutral-200 bg-white px-3 py-2 text-sm text-neutral-700 outline-none placeholder:text-neutral-400"
              />
            </div>
            <div className="mt-3 max-h-64 space-y-2 overflow-y-auto pr-1">
              {categoriesLoading ? (
                <div className="rounded-lg border border-dashed border-neutral-200 bg-white px-3 py-6 text-center text-xs text-neutral-500">
                  Resolving categories from FunPay...
                </div>
              ) : filteredCategories.length ? (
                filteredCategories.map((item) => {
                  const checked = draft.categories.includes(item.id);
                  return (
                    <label
                      key={item.id}
                      className={`flex items-start gap-3 rounded-lg border px-3 py-2 text-sm transition ${
                        checked ? "border-neutral-900 bg-white" : "border-neutral-200 bg-white"
                      }`}
                    >
                      <input
                        type="checkbox"
                        className="mt-1 h-4 w-4 rounded border-neutral-300 text-neutral-900"
                        checked={checked}
                        onChange={() => toggleCategory(item.id)}
                      />
                      <div>
                        <div className="text-sm font-semibold text-neutral-800">{item.name}</div>
                        <div className="text-xs text-neutral-500">ID {item.id}</div>
                      </div>
                    </label>
                  );
                })
              ) : (
                <div className="rounded-lg border border-dashed border-neutral-200 bg-white px-3 py-6 text-center text-xs text-neutral-500">
                  No categories found. Try refreshing.
                </div>
              )}
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <button
              type="button"
              onClick={handleSave}
              disabled={!dirty || saving}
              className="rounded-lg bg-neutral-900 px-4 py-2 text-xs font-semibold text-white transition hover:bg-neutral-800 disabled:cursor-not-allowed disabled:bg-neutral-300"
            >
              {saving ? "Saving..." : "Save changes"}
            </button>
            <button
              type="button"
              onClick={handleReset}
              disabled={!dirty || saving}
              className="rounded-lg border border-neutral-200 px-4 py-2 text-xs font-semibold text-neutral-600 transition hover:bg-neutral-100 disabled:cursor-not-allowed disabled:opacity-60"
            >
              Reset
            </button>
            {loading ? (
              <span className="text-xs text-neutral-400">Loading settings...</span>
            ) : null}
          </div>
        </div>
      </div>

      <div className="rounded-2xl border border-neutral-200 bg-white p-6 shadow-sm shadow-neutral-200/70">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-lg font-semibold text-neutral-900">Auto Raise history</h3>
            <p className="text-xs text-neutral-500">Latest runs across all FunPay workspaces.</p>
          </div>
          <button
            type="button"
            onClick={loadHistory}
            disabled={historyLoading}
            className="rounded-lg border border-neutral-200 bg-white px-3 py-1.5 text-xs font-semibold text-neutral-600 transition hover:bg-neutral-100 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {historyLoading ? "Refreshing..." : "Refresh"}
          </button>
        </div>
        <div className="mt-4 space-y-3 max-h-[520px] overflow-y-auto pr-1">
          {historyLoading ? (
            <div className="rounded-lg border border-dashed border-neutral-200 bg-neutral-50 px-4 py-6 text-center text-xs text-neutral-500">
              Loading history...
            </div>
          ) : history.length ? (
            history.map((item) => (
              <div key={item.id} className="rounded-xl border border-neutral-200 bg-white p-3">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <div className="text-sm font-semibold text-neutral-800">
                      {item.category_name || "Category"}
                    </div>
                    <div className="text-xs text-neutral-500">
                      {item.workspace_name || "Workspace"}{item.category_id ? ` - ID ${item.category_id}` : ""}
                    </div>
                  </div>
                  <span
                    className={`rounded-full px-2 py-0.5 text-[11px] font-semibold uppercase ${
                      item.status === "ok"
                        ? "bg-emerald-100 text-emerald-700"
                        : "bg-rose-100 text-rose-700"
                    }`}
                  >
                    {item.status}
                  </span>
                </div>
                {item.message ? <div className="mt-2 text-xs text-neutral-600">{item.message}</div> : null}
                <div className="mt-2 text-[11px] text-neutral-400">{formatTimestamp(item.created_at)}</div>
              </div>
            ))
          ) : (
            <div className="rounded-lg border border-dashed border-neutral-200 bg-neutral-50 px-4 py-6 text-center text-xs text-neutral-500">
              No auto raise activity yet.
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default PluginsPage;
