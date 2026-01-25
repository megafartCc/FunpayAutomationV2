import React, { useState } from "react";

type TopBarProps = {
  title: string;
  userInitial: string;
  onLogout: () => Promise<void>;
};

const TopBar: React.FC<TopBarProps> = ({ title, userInitial, onLogout }) => {
  const [menuOpen, setMenuOpen] = useState(false);
  const [workspaceOpen, setWorkspaceOpen] = useState(false);

  return (
    <header className="sticky top-0 z-10 flex items-center justify-between border-b border-neutral-200 bg-white px-8 py-4">
      <h1 className="text-xl font-semibold text-neutral-900">{title}</h1>

      <div className="flex items-center gap-4">
        <div className="relative">
          <div className="flex items-center gap-2 rounded-full border border-neutral-200 bg-white px-4 py-2 text-xs font-semibold text-neutral-500">
            WORKSPACE
            <button
              type="button"
              className="flex items-center gap-2 rounded-full border border-neutral-200 bg-white px-3 py-1 text-sm font-semibold text-neutral-700"
              onClick={() => setWorkspaceOpen((prev) => !prev)}
            >
              Default (Default)
              <svg viewBox="0 0 20 20" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="1.8">
                <path d="M5 8l5 5 5-5" />
              </svg>
            </button>
            <button
              type="button"
              className="rounded-full border border-neutral-200 px-3 py-1 text-xs font-semibold text-neutral-700 hover:bg-neutral-50"
            >
              Manage
            </button>
          </div>
          {workspaceOpen ? (
            <div className="absolute right-0 mt-2 w-56 rounded-2xl border border-neutral-200 bg-white p-2 text-sm shadow-lg">
              <button
                type="button"
                className="w-full rounded-xl px-3 py-2 text-left font-medium text-neutral-700 hover:bg-neutral-100"
              >
                Default (Default)
              </button>
              <button
                type="button"
                className="w-full rounded-xl px-3 py-2 text-left font-medium text-neutral-700 hover:bg-neutral-100"
              >
                Personal Workspace
              </button>
            </div>
          ) : null}
        </div>

        <div className="relative">
          <input
            className="w-60 rounded-full border border-neutral-200 bg-white px-4 py-2 text-sm text-neutral-700 placeholder:text-neutral-400 focus:border-neutral-300 focus:outline-none"
            placeholder="Search..."
          />
          <svg
            viewBox="0 0 24 24"
            className="pointer-events-none absolute right-3 top-2.5 h-5 w-5 text-neutral-400"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.8"
          >
            <circle cx="11" cy="11" r="7" />
            <path d="M20 20l-3.5-3.5" />
          </svg>
        </div>

        <div className="relative">
          <button
            type="button"
            className="grid h-10 w-10 place-items-center rounded-full bg-neutral-900 text-sm font-semibold text-white"
            onClick={() => setMenuOpen((prev) => !prev)}
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
