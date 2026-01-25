import React from "react";

type AccountRow = {
  id: number;
  name: string;
  login: string;
  password: string;
  steamId: string;
  mmr: number | string;
  state: string;
  label?: string;
};

const INVENTORY_GRID =
  "minmax(72px,0.6fr) minmax(180px,1.4fr) minmax(140px,1fr) minmax(140px,1fr) minmax(190px,1.1fr) minmax(80px,0.6fr) minmax(110px,0.6fr)";

const accounts: AccountRow[] = [
  {
    id: 24,
    name: "No1 dwqbvfjw0u2j",
    login: "dwqbvfjw0u2j",
    password: "********",
    steamId: "-",
    mmr: 900,
    state: "Available",
    label: "DEFAULT",
  },
  {
    id: 25,
    name: "No2 lxbvgvusku1186",
    login: "lxbvgvusku1186",
    password: "********",
    steamId: "-",
    mmr: 900,
    state: "Available",
    label: "DEFAULT",
  },
  {
    id: 26,
    name: "No3 xucrlkdm44fsvi",
    login: "xucrlkdm44fsvi",
    password: "********",
    steamId: "-",
    mmr: 900,
    state: "Available",
    label: "DEFAULT",
  },
  {
    id: 27,
    name: "No4 cexkwtmz648938",
    login: "cexkwtmz648938",
    password: "********",
    steamId: "-",
    mmr: 900,
    state: "Available",
    label: "DEFAULT",
  },
  {
    id: 28,
    name: "No5 hbqc49licejn",
    login: "hbqc49licejn",
    password: "********",
    steamId: "-",
    mmr: 900,
    state: "Available",
    label: "DEFAULT",
  },
  {
    id: 29,
    name: "No6 zvshenrq450551",
    login: "zvshenrq450551",
    password: "********",
    steamId: "-",
    mmr: 900,
    state: "Available",
    label: "DEFAULT",
  },
];

const InventoryPage: React.FC = () => {
  return (
    <div className="space-y-6">
      <div className="grid gap-6 xl:grid-cols-[minmax(0,1.55fr)_minmax(0,1fr)] items-stretch">
        <div className="rounded-2xl border border-neutral-200 bg-white p-6 shadow-sm shadow-neutral-200/70">
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="text-xs text-neutral-500">Select an account to manage rentals.</p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <div className="flex items-center gap-2 rounded-lg border border-neutral-200 bg-neutral-50 px-3 py-2 text-[11px] font-semibold text-neutral-600">
                <span className="uppercase tracking-wide text-neutral-500">Workspace</span>
                <select defaultValue="default" className="bg-transparent text-xs font-semibold text-neutral-700 outline-none">
                  <option value="default">Default</option>
                </select>
              </div>
              <span className="text-xs rounded-full bg-neutral-100 px-3 py-1 font-semibold text-neutral-600">
                No account selected
              </span>
            </div>
          </div>

          <div className="overflow-x-auto">
            <div className="min-w-[1000px]">
              <div className="grid gap-3 px-6 text-xs font-semibold text-neutral-500" style={{ gridTemplateColumns: INVENTORY_GRID }}>
                <span>ID</span>
                <span>Name</span>
                <span>Login</span>
                <span>Password</span>
                <span>Steam ID</span>
                <span>MMR</span>
                <span className="text-right">State</span>
              </div>
              <div className="mt-3 space-y-3 overflow-y-auto overflow-x-hidden pr-1" style={{ maxHeight: "640px" }}>
                {accounts.map((acc) => (
                  <div
                    key={acc.id}
                    className="grid min-w-full items-center gap-3 rounded-xl border border-neutral-100 bg-neutral-50 px-6 py-4 text-sm shadow-[0_4px_18px_-14px_rgba(0,0,0,0.18)]"
                    style={{ gridTemplateColumns: INVENTORY_GRID }}
                  >
                    <span className="min-w-0 font-semibold text-neutral-900">{acc.id}</span>
                    <div className="min-w-0">
                      <div className="truncate font-semibold leading-tight text-neutral-900">{acc.name}</div>
                      {acc.label ? (
                        <span className="mt-1 inline-flex w-fit rounded-full bg-neutral-100 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-neutral-600">
                          {acc.label}
                        </span>
                      ) : null}
                    </div>
                    <span className="min-w-0 truncate text-neutral-700">{acc.login}</span>
                    <span className="min-w-0 truncate text-neutral-700">{acc.password}</span>
                    <span className="min-w-0 truncate font-mono text-xs leading-tight text-neutral-800 tabular-nums">
                      {acc.steamId}
                    </span>
                    <span className="min-w-0 truncate text-neutral-700">{acc.mmr}</span>
                    <span className="justify-self-end rounded-full bg-emerald-50 px-3 py-1 text-xs font-semibold text-emerald-600">
                      {acc.state}
                    </span>
                  </div>
                ))}

                {accounts.length === 0 && (
                  <div className="rounded-xl border border-dashed border-neutral-200 bg-neutral-50 px-4 py-6 text-center text-sm text-neutral-500">
                    No accounts loaded yet.
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>

        <div className="grid h-full self-stretch content-stretch items-stretch gap-6 lg:grid-cols-2" style={{ gridAutoRows: "1fr" }}>
          <div className="h-full rounded-2xl border border-neutral-200 bg-white p-5 shadow-sm shadow-neutral-200/70">
            <div className="mb-3 flex items-center justify-between text-base font-semibold text-neutral-900">
              <span>Account actions</span>
              <span className="text-[12px] font-semibold text-neutral-500">Select an account</span>
            </div>
            <div className="rounded-xl border border-dashed border-neutral-200 bg-neutral-50/60 px-4 py-6 text-center text-xs text-neutral-400">
              Select an account to unlock account actions.
            </div>
          </div>
          <div className="h-full rounded-2xl border border-neutral-200 bg-white p-5 shadow-sm shadow-neutral-200/70">
            <div className="mb-3 flex items-center justify-between text-base font-semibold text-neutral-900">
              <span>Account controls</span>
              <span className="text-[12px] font-semibold text-neutral-500">Select an account</span>
            </div>
            <div className="rounded-xl border border-dashed border-neutral-200 bg-neutral-50/60 px-4 py-6 text-center text-xs text-neutral-400">
              Select an account to manage freeze &amp; deletion.
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default InventoryPage;
