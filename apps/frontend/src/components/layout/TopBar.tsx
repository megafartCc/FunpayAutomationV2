import React, { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useWorkspace } from "../../context/WorkspaceContext";

type TopBarProps = {
  title: string;
  userInitial: string;
  onLogout: () => Promise<void>;
  hideWorkspaceControls?: boolean;
};

const TopBar: React.FC<TopBarProps> = ({ title, userInitial, onLogout, hideWorkspaceControls = false }) => {
  const [menuOpen, setMenuOpen] = useState(false);
  const navigate = useNavigate();
  const { workspaces, visibleWorkspaces, loading, selectedId, setSelectedId, selectedPlatform, setSelectedPlatform } =
    useWorkspace();

  const selectedLabel = useMemo(() => {
    if (selectedId === "all") return "All workspaces";
    const match = visibleWorkspaces.find((item) => item.id === selectedId);
    if (!match) {
      const fallback = visibleWorkspaces.find((item) => item.is_default) || workspaces.find((item) => item.is_default);
      return fallback ? `${fallback.name} (Default)` : "Workspace";
    }
    return match.is_default ? `${match.name} (Default)` : match.name;
  }, [selectedId, visibleWorkspaces, workspaces]);

  return (
    <header className="sticky top-0 z-10 flex items-center justify-between border-b border-neutral-200 bg-white px-8 py-4">
      <h1 className="text-xl font-semibold text-neutral-900">{title}</h1>

        <div className="flex items-center gap-4">
          {!hideWorkspaceControls ? (
            <>
              <div className="flex h-10 items-center gap-1 rounded-lg border border-neutral-200 bg-neutral-50 px-1 text-xs font-semibold text-neutral-600 shadow-sm shadow-neutral-200">
                {[
                  { key: "all", label: "All" },
                  { key: "funpay", label: "FunPay" },
                  { key: "playerok", label: "PlayerOk" },
                ].map((item) => (
                  <button
                    key={item.key}
                    type="button"
                    className={`flex h-8 items-center justify-center rounded-md px-3 text-[11px] font-semibold leading-none transition ${
                      selectedPlatform === item.key
                        ? "bg-neutral-900 text-white"
                        : "text-neutral-600 hover:bg-neutral-100"
                    }`}
                    onClick={() => setSelectedPlatform(item.key as "all" | "funpay" | "playerok")}
                  >
                    {item.label}
                  </button>
                ))}
              </div>
              <div className="flex h-10 items-center gap-2 rounded-lg border border-neutral-200 bg-neutral-50 px-3 text-xs font-semibold text-neutral-600 shadow-sm shadow-neutral-200">
                <span className="hidden sm:inline text-[11px] uppercase tracking-wide text-neutral-500">Workspace</span>
                <select
                  className="h-8 bg-transparent text-sm font-semibold leading-none text-neutral-700 outline-none"
                  value={
                    selectedId === "all"
                      ? selectedPlatform === "all"
                        ? "all"
                        : String(visibleWorkspaces[0]?.id ?? "all")
                      : String(selectedId)
                  }
                  onChange={(event) => {
                    const value = event.target.value;
                    if (value === "all") {
                      setSelectedId("all");
                    } else {
                      const id = Number(value);
                      if (!Number.isNaN(id)) setSelectedId(id);
                    }
                  }}
                  disabled={loading}
                >
                  {selectedPlatform === "all" ? <option value="all">All workspaces</option> : null}
                  {visibleWorkspaces.map((item) => (
                    <option key={item.id} value={String(item.id)}>
                      {item.is_default ? `${item.name} (Default)` : item.name}
                    </option>
                  ))}
                </select>
                <button
                  type="button"
                  className="flex h-8 items-center justify-center rounded-md border border-neutral-200 bg-white px-3 text-[11px] font-semibold text-neutral-600 transition hover:bg-neutral-100"
                  onClick={() => navigate("/settings")}
                >
                  {selectedLabel ? "Manage" : "Manage"}
                </button>
              </div>
            </>
          ) : null}

        <label className="relative flex h-10 w-72 items-center gap-3 rounded-lg border border-neutral-200 bg-neutral-50 px-4 text-sm text-neutral-500 shadow-sm shadow-neutral-200">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path
              d="M11 19C15.4183 19 19 15.4183 19 11C19 6.58172 15.4183 3 11 3C6.58172 3 3 6.58172 3 11C3 15.4183 6.58172 19 11 19Z"
              stroke="#9CA3AF"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
            <path d="M21 21L16.65 16.65" stroke="#9CA3AF" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          <input
            type="search"
            placeholder="Search..."
            className="w-full bg-transparent text-neutral-700 placeholder:text-neutral-400 outline-none"
          />
        </label>

        <button
          type="button"
          className="flex h-10 w-10 items-center justify-center rounded-full border border-neutral-200 bg-white text-neutral-700 shadow-sm transition hover:bg-neutral-100"
          onClick={() => navigate("/notifications")}
          aria-label="Notifications"
          title="Notifications"
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path
              d="M15 17V18C15 19.6569 13.6569 21 12 21C10.3431 21 9 19.6569 9 18V17M15 17H9M15 17H18.5905C18.973 17 19.1652 17 19.3201 16.9478C19.616 16.848 19.8475 16.6156 19.9473 16.3198C19.9997 16.1643 19.9997 15.9715 19.9997 15.5859C19.9997 15.4172 19.9995 15.3329 19.9863 15.2524C19.9614 15.1004 19.9024 14.9563 19.8126 14.8312C19.7651 14.7651 19.7048 14.7048 19.5858 14.5858L19.1963 14.1963C19.0706 14.0706 19 13.9001 19 13.7224V10C19 6.134 15.866 2.99999 12 3C8.13401 3.00001 5 6.13401 5 10V13.7224C5 13.9002 4.92924 14.0706 4.80357 14.1963L4.41406 14.5858C4.29476 14.7051 4.23504 14.765 4.1875 14.8312C4.09766 14.9564 4.03815 15.1004 4.0132 15.2524C4 15.3329 4 15.4172 4 15.586C4 15.9715 4 16.1642 4.05245 16.3197C4.15225 16.6156 4.3848 16.848 4.68066 16.9478C4.83556 17 5.02701 17 5.40956 17H9"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </button>

        <div className="relative">
          <button
            type="button"
            className="flex h-10 w-10 items-center justify-center rounded-full bg-neutral-900 text-sm font-semibold text-white shadow-sm"
            onClick={() => setMenuOpen((prev) => !prev)}
            aria-label="Profile"
            title="Profile"
          >
            {userInitial}
          </button>
          {menuOpen ? (
            <div className="absolute right-0 mt-2 w-44 rounded-2xl border border-neutral-200 bg-white p-2 text-sm shadow-lg">
              <button
                type="button"
                className="w-full rounded-xl px-3 py-2 text-left font-medium text-neutral-700 hover:bg-neutral-100"
              >
                Profile
              </button>
              <button
                type="button"
                className="w-full rounded-xl px-3 py-2 text-left font-medium text-neutral-700 hover:bg-neutral-100"
                onClick={onLogout}
              >
                Log out
              </button>
            </div>
          ) : null}
        </div>
      </div>
    </header>
  );
};

export default TopBar;
