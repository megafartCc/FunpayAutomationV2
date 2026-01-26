import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { api, WorkspaceItem } from "../services/api";

type WorkspaceContextValue = {
  workspaces: WorkspaceItem[];
  loading: boolean;
  selectedId: number | "all";
  setSelectedId: (value: number | "all") => void;
  refresh: () => Promise<void>;
};

const WorkspaceContext = createContext<WorkspaceContextValue | undefined>(undefined);

const STORAGE_KEY = "funpay.selectedWorkspace";

const normalizeSelected = (value: number | "all", workspaces: WorkspaceItem[]) => {
  if (value === "all") return "all";
  const exists = workspaces.some((item) => item.id === value);
  if (exists) return value;
  const defaultWs = workspaces.find((item) => item.is_default);
  return defaultWs ? defaultWs.id : "all";
};

export const WorkspaceProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [workspaces, setWorkspaces] = useState<WorkspaceItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedId, setSelectedIdState] = useState<number | "all">("all");

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.listWorkspaces();
      const items = res.items || [];
      setWorkspaces(items);
      setSelectedIdState((prev) => normalizeSelected(prev, items));
    } catch {
      setWorkspaces([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    if (stored && stored !== "all") {
      const id = Number(stored);
      if (Number.isFinite(id)) {
        setSelectedIdState(id);
      }
    }
    void refresh();
  }, [refresh]);

  const setSelectedId = useCallback((value: number | "all") => {
    setSelectedIdState(value);
    window.localStorage.setItem(STORAGE_KEY, String(value));
  }, []);

  const value = useMemo(
    () => ({
      workspaces,
      loading,
      selectedId,
      setSelectedId,
      refresh,
    }),
    [workspaces, loading, selectedId, setSelectedId, refresh],
  );

  return <WorkspaceContext.Provider value={value}>{children}</WorkspaceContext.Provider>;
};

export const useWorkspace = () => {
  const ctx = useContext(WorkspaceContext);
  if (!ctx) throw new Error("useWorkspace must be used within WorkspaceProvider");
  return ctx;
};
