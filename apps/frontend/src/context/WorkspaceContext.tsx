import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { api, WorkspaceItem } from "../services/api";

type WorkspaceContextValue = {
  workspaces: WorkspaceItem[];
  visibleWorkspaces: WorkspaceItem[];
  loading: boolean;
  selectedId: number | "all";
  setSelectedId: (value: number | "all") => void;
  selectedPlatform: "all" | "funpay" | "playerok";
  setSelectedPlatform: (value: "all" | "funpay" | "playerok") => void;
  refresh: () => Promise<void>;
};

const WorkspaceContext = createContext<WorkspaceContextValue | undefined>(undefined);

const STORAGE_KEY = "funpay.selectedWorkspace";
const PLATFORM_KEY = "funpay.selectedPlatform";
const PLATFORM_VALUES = ["all", "funpay", "playerok"] as const;
type PlatformFilter = (typeof PLATFORM_VALUES)[number];

const normalizeSelected = (
  value: number | "all",
  workspaces: WorkspaceItem[],
  preferDefault: boolean,
  platform: PlatformFilter,
) => {
  const scoped =
    platform === "all"
      ? workspaces
      : workspaces.filter((item) => (item.platform || "funpay") === platform);
  const hasScoped = scoped.length > 0;
  if (value === "all") {
    if (platform !== "all" && hasScoped) {
      const defaultWs = scoped.find((item) => item.is_default);
      return (defaultWs ?? scoped[0]).id;
    }
    if (preferDefault) {
      const defaultWs = scoped.find((item) => item.is_default);
      return defaultWs ? defaultWs.id : "all";
    }
    return "all";
  }
  const exists = scoped.some((item) => item.id === value);
  if (exists) return value;
  const defaultWs = scoped.find((item) => item.is_default);
  if (defaultWs) return defaultWs.id;
  if (platform !== "all" && hasScoped) return scoped[0].id;
  return "all";
};

export const WorkspaceProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [workspaces, setWorkspaces] = useState<WorkspaceItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedId, setSelectedIdState] = useState<number | "all">("all");
  const [selectedPlatform, setSelectedPlatformState] = useState<PlatformFilter>("all");

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const stored = window.localStorage.getItem(STORAGE_KEY);
      const preferDefault = stored === null;
      const res = await api.listWorkspaces();
      const items = res.items || [];
      setWorkspaces(items);
      setSelectedIdState((prev) => normalizeSelected(prev, items, preferDefault, selectedPlatform));
    } catch {
      setWorkspaces([]);
    } finally {
      setLoading(false);
    }
  }, [selectedPlatform]);

  useEffect(() => {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    if (stored && stored !== "all") {
      const id = Number(stored);
      if (Number.isFinite(id)) {
        setSelectedIdState(id);
      }
    }
    const storedPlatform = window.localStorage.getItem(PLATFORM_KEY);
    if (storedPlatform && PLATFORM_VALUES.includes(storedPlatform as PlatformFilter)) {
      setSelectedPlatformState(storedPlatform as PlatformFilter);
    }
    void refresh();
  }, [refresh]);

  const setSelectedId = useCallback((value: number | "all") => {
    setSelectedIdState(value);
    window.localStorage.setItem(STORAGE_KEY, String(value));
  }, []);

  const setSelectedPlatform = useCallback(
    (value: PlatformFilter) => {
      setSelectedPlatformState(value);
      window.localStorage.setItem(PLATFORM_KEY, value);
      setSelectedIdState((prev) => normalizeSelected(prev, workspaces, true, value));
    },
    [workspaces],
  );

  const visibleWorkspaces = useMemo(
    () =>
      selectedPlatform === "all"
        ? workspaces
        : workspaces.filter((item) => (item.platform || "funpay") === selectedPlatform),
    [workspaces, selectedPlatform],
  );

  const value = useMemo(
    () => ({
      workspaces,
      visibleWorkspaces,
      loading,
      selectedId,
      setSelectedId,
      selectedPlatform,
      setSelectedPlatform,
      refresh,
    }),
    [workspaces, visibleWorkspaces, loading, selectedId, setSelectedId, selectedPlatform, setSelectedPlatform, refresh],
  );

  return <WorkspaceContext.Provider value={value}>{children}</WorkspaceContext.Provider>;
};

export const useWorkspace = () => {
  const ctx = useContext(WorkspaceContext);
  if (!ctx) throw new Error("useWorkspace must be used within WorkspaceProvider");
  return ctx;
};
