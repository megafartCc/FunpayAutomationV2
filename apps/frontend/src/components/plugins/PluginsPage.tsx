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
  const [syncOpen, setSyncOpen] = useState(false);
  const [syncInput, setSyncInput] = useState("");
  const [syncSaving, setSyncSaving] = useState(false);

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

  const parseSyncPayload = (raw: string): FunpayCategoryItem[] => {
    const parsed = JSON.parse(raw);
    const items = Array.isArray(parsed) ? parsed : parsed?.items;
    if (!Array.isArray(items)) {
      throw new Error("Invalid JSON format.");
    }
    return items
      .map((item) => ({
        id: Number(item?.id),
        name: String(item?.name || ""),
        game: item?.game ?? null,
        category: item?.category ?? null,
        server: item?.server ?? null,
      }))
      .filter((item) => Number.isFinite(item.id) && item.name.trim().length > 0);
  };

  const handleSyncImport = async () => {
    if (syncSaving) return;
    setSyncSaving(true);
    try {
      const items = parseSyncPayload(syncInput);
      const res = await api.cacheFunpayCategories(items);
      setCategories(res.items || []);
      setSyncInput("");
      setSyncOpen(false);
      onToast?.("FunPay categories synced.");
    } catch (err) {
      const message = (err as { message?: string })?.message || "Failed to sync categories.";
      onToast?.(message, true);
    } finally {
      setSyncSaving(false);
    }
  };

  const syncScript = useMemo(
    () => `(async () => {
  const urls = ["/en/lots/", "/lots/", "/en/", "/"];
  const seen = new Map();

  const parse = (html) => {
    const doc = new DOMParser().parseFromString(html, "text/html");
    doc.querySelectorAll(".promo-game-item").forEach((block) => {
      const gameEl = block.querySelector(".game-title a, .game-title");
      const gameName = (gameEl?.textContent || "Unknown game").trim();
      const serverLabels = {};
      block.querySelectorAll("button[data-id]").forEach((btn) => {
        const id = btn.getAttribute("data-id")?.trim();
        if (id) serverLabels[id] = (btn.textContent || "").trim();
      });
      block.querySelectorAll("ul.list-inline[data-id]").forEach((ul) => {
        const dataId = ul.getAttribute("data-id")?.trim();
        const server = dataId ? (serverLabels[dataId] || "") : "";
        const gameLabel = server ? \`\${gameName} (\${server})\` : gameName;
        ul.querySelectorAll("a[href*='/lots/']").forEach((a) => {
          const href = a.getAttribute("href") || "";
          const m = href.match(/\\/lots\\/(\\d+)/);
          if (!m) return;
          const id = Number(m[1]);
          const category = ((a.textContent || "").trim() || \`Category \${id}\`);
          if (!seen.has(id)) {
            seen.set(id, { id, name: \`\${gameLabel} - \${category}\`, game: gameLabel, category, server: server || null });
          }
        });
      });
    });
    doc.querySelectorAll("a[href*='/lots/']").forEach((a) => {
      const href = a.getAttribute("href") || "";
      const m = href.match(/\\/lots\\/(\\d+)/);
      if (!m) return;
      const id = Number(m[1]);
      if (seen.has(id)) return;
      const category = ((a.textContent || "").trim() || \`Category \${id}\`);
      let gameLabel = "Unknown game";
      const block = a.closest(".promo-game-item");
      if (block) {
        const gEl = block.querySelector(".game-title a, .game-title");
        gameLabel = (gEl?.textContent || "").trim() || gameLabel;
      }
      seen.set(id, { id, name: \`\${gameLabel} - \${category}\`, game: gameLabel, category, server: null });
    });
  };

  for (const path of urls) {
    try {
      const r = await fetch(path, { credentials: "include" });
      const html = await r.text();
      parse(html);
    } catch (e) {
      console.warn("Fetch failed", path, e?.message || e);
    }
  }

  const gamesWithCats = new Set(
    [...seen.values()].filter((v) => v.category && v.game).map((v) => v.game.trim())
  );
  for (const [id, v] of [...seen.entries()]) {
    const g = (v.game || "").trim();
    if (gamesWithCats.has(g) && (!v.category || v.category === v.name)) {
      seen.delete(id);
    }
  }

  const rows = [...seen.values()].sort((a, b) => {
    const gA = (a.game || "");
    const gB = (b.game || "");
    const cA = (a.category || a.name || "");
    const cB = (b.category || b.name || "");
    return gA.localeCompare(gB) || cA.localeCompare(cB) || (a.id - b.id);
  });

  const payload = JSON.stringify(rows, null, 2);
  if (navigator?.clipboard?.writeText) {
    await navigator.clipboard.writeText(payload);
    console.log("Copied categories JSON to clipboard");
  } else {
    console.log(payload);
  }
})();`,
    [],
  );

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
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  onClick={() => setSyncOpen(true)}
                  className="rounded-lg border border-neutral-200 bg-white px-3 py-1.5 text-xs font-semibold text-neutral-600 transition hover:bg-neutral-100"
                >
                  Sync from FunPay
                </button>
                <button
                  type="button"
                  onClick={loadCategories}
                  disabled={categoriesLoading}
                  className="rounded-lg border border-neutral-200 bg-white px-3 py-1.5 text-xs font-semibold text-neutral-600 transition hover:bg-neutral-100 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {categoriesLoading ? "Refreshing..." : "Refresh categories"}
                </button>
              </div>
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

      {syncOpen && (
        <div className="fixed inset-0 z-40 flex items-center justify-center bg-neutral-900/40 p-4">
          <div className="w-full max-w-2xl rounded-2xl border border-neutral-200 bg-white p-6 shadow-xl">
            <div className="flex items-start justify-between gap-4">
              <div>
                <div className="text-lg font-semibold text-neutral-900">Sync FunPay categories</div>
                <div className="text-xs text-neutral-500">
                  Run the script on FunPay in your browser, then paste the JSON output below.
                </div>
              </div>
              <button
                type="button"
                onClick={() => setSyncOpen(false)}
                className="rounded-full border border-neutral-200 px-2 py-1 text-xs text-neutral-500 hover:text-neutral-800"
              >
                Close
              </button>
            </div>

            <div className="mt-4 rounded-xl border border-neutral-200 bg-neutral-50 p-3 text-xs text-neutral-600">
              <div className="mb-2 font-semibold text-neutral-800">Run in FunPay console</div>
              <pre className="max-h-56 overflow-auto whitespace-pre-wrap rounded-lg bg-white p-3 text-[11px] text-neutral-700">
                {syncScript}
              </pre>
              <div className="mt-2 flex flex-wrap gap-2">
                <button
                  type="button"
                  onClick={async () => {
                    try {
                      await navigator.clipboard.writeText(syncScript);
                      onToast?.("Script copied to clipboard.");
                    } catch {
                      onToast?.("Copy failed. Select and copy manually.", true);
                    }
                  }}
                  className="rounded-lg border border-neutral-200 bg-white px-3 py-1.5 text-xs font-semibold text-neutral-600 hover:bg-neutral-100"
                >
                  Copy script
                </button>
                <span className="text-xs text-neutral-500">
                  Open FunPay → DevTools Console → paste and run.
                </span>
              </div>
            </div>

            <div className="mt-4">
              <label className="text-xs font-semibold text-neutral-600">Paste categories JSON</label>
              <textarea
                value={syncInput}
                onChange={(e) => setSyncInput(e.target.value)}
                rows={6}
                className="mt-2 w-full rounded-lg border border-neutral-200 bg-white px-3 py-2 text-xs text-neutral-700 outline-none"
                placeholder='Paste JSON array from FunPay console...'
              />
            </div>

            <div className="mt-4 flex flex-wrap items-center justify-end gap-2">
              <button
                type="button"
                onClick={() => setSyncOpen(false)}
                className="rounded-lg border border-neutral-200 bg-white px-3 py-1.5 text-xs font-semibold text-neutral-600 hover:bg-neutral-100"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleSyncImport}
                disabled={syncSaving || !syncInput.trim()}
                className="rounded-lg bg-neutral-900 px-4 py-1.5 text-xs font-semibold text-white hover:bg-neutral-800 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {syncSaving ? "Saving..." : "Save categories"}
              </button>
            </div>
          </div>
        </div>
      )}

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
