import React from "react";

type RentalRow = {
  id: string | number;
  account: string;
  buyer: string;
  started: string;
  timeLeft: string;
  matchTime: string;
  hero: string;
  status: string;
};

const RENTALS_GRID =
  "minmax(64px,0.6fr) minmax(180px,1.4fr) minmax(160px,1.1fr) minmax(140px,1fr) minmax(120px,0.8fr) minmax(110px,0.8fr) minmax(140px,1fr) minmax(110px,0.7fr)";

const rentals: RentalRow[] = [];

const ActiveRentalsPage: React.FC = () => {
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold text-neutral-900">Active Rentals</h1>

      <div className="flex flex-wrap items-center gap-3">
        <div className="rounded-full bg-neutral-900 px-4 py-2 text-sm font-semibold text-white">
          {rentals.length} active rentals
        </div>
        <div className="text-sm text-neutral-500">Updated live every second</div>
      </div>

      <div className="rounded-2xl border border-neutral-200 bg-white p-6 shadow-sm shadow-neutral-200/70">
        <div className="overflow-x-auto">
          <div className="min-w-[1100px]">
            <div
              className="grid gap-3 px-6 text-xs font-semibold text-neutral-500"
              style={{ gridTemplateColumns: RENTALS_GRID }}
            >
              <span>ID</span>
              <span>Account</span>
              <span>Buyer</span>
              <span>Started</span>
              <span>Time Left</span>
              <span>Match Time</span>
              <span>Hero</span>
              <span>Status</span>
            </div>

            <div className="mt-3 space-y-3 overflow-y-auto overflow-x-hidden pr-1" style={{ maxHeight: "640px" }}>
              {rentals.map((row) => (
                <div
                  key={row.id}
                  className="grid items-center gap-3 rounded-xl border border-neutral-100 bg-neutral-50 px-6 py-4 text-sm"
                  style={{ gridTemplateColumns: RENTALS_GRID }}
                >
                  <span className="min-w-0 truncate font-semibold text-neutral-900">{row.id}</span>
                  <span className="min-w-0 truncate text-neutral-800">{row.account}</span>
                  <span className="min-w-0 truncate text-neutral-700">{row.buyer}</span>
                  <span className="min-w-0 truncate text-neutral-600">{row.started}</span>
                  <span className="min-w-0 truncate font-mono text-neutral-900">{row.timeLeft}</span>
                  <span className="min-w-0 truncate font-mono text-neutral-900">{row.matchTime}</span>
                  <span className="min-w-0 truncate text-neutral-700">{row.hero}</span>
                  <span className="inline-flex w-fit rounded-full bg-emerald-50 px-3 py-1 text-xs font-semibold text-emerald-600">
                    {row.status}
                  </span>
                </div>
              ))}

              {rentals.length === 0 && (
                <div className="rounded-xl border border-dashed border-neutral-200 bg-neutral-50 px-4 py-6 text-center text-sm text-neutral-500">
                  No active rentals yet.
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ActiveRentalsPage;
