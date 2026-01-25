import React, { useState } from "react";

type TopBarProps = {
  title: string;
  userInitial: string;
  onLogout: () => Promise<void>;
};

const TopBar: React.FC<TopBarProps> = ({ title, userInitial, onLogout }) => {
  const [menuOpen, setMenuOpen] = useState(false);
  const [workspace, setWorkspace] = useState("all");

  return (
    <header className="sticky top-0 z-10 flex items-center justify-between border-b border-neutral-200 bg-white px-10 py-4">
      <h1 className="text-xl font-semibold text-neutral-900">{title}</h1>

      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2 rounded-lg border border-neutral-200 bg-neutral-50 px-3 py-2 text-xs font-semibold text-neutral-600 shadow-sm shadow-neutral-200">
          <span className="hidden sm:inline text-[11px] uppercase tracking-wide text-neutral-500">Workspace</span>
          <select
            className="bg-transparent text-sm font-semibold text-neutral-700 outline-none"
            value={workspace}
            onChange={(event) => setWorkspace(event.target.value)}
          >
            <option value="all">All workspaces</option>
            <option value="default">Default (Default)</option>
          </select>
          <button
            type="button"
            className="rounded-md border border-neutral-200 bg-white px-2 py-1 text-[11px] font-semibold text-neutral-600 transition hover:bg-neutral-100"
          >
            Manage
          </button>
        </div>

        <label className="relative flex h-11 w-72 items-center gap-3 rounded-lg border border-neutral-200 bg-neutral-50 px-4 text-sm text-neutral-500 shadow-sm shadow-neutral-200">
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
