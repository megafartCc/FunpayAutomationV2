import React from "react";

type Stat = { label: string; value: string | number };

const StatCard: React.FC<Stat> = ({ label, value }) => (
  <div className="rounded-2xl border border-neutral-200 bg-white p-5 shadow-sm">
    <p className="text-xs font-semibold uppercase tracking-wide text-neutral-500">{label}</p>
    <div className="mt-2 text-3xl font-semibold text-neutral-900">{value}</div>
  </div>
);

const bars = [
  { label: "Mon", value: 6 },
  { label: "Tue", value: 9 },
  { label: "Wed", value: 4 },
  { label: "Thu", value: 11 },
  { label: "Fri", value: 8 },
  { label: "Sat", value: 5 },
  { label: "Sun", value: 7 },
];

const topLots = [
  { name: "Dota 2 · Boost 2-3k", sales: 22, revenue: "$180" },
  { name: "Dota 2 · Account 1-1.5k MMR", sales: 14, revenue: "$126" },
  { name: "CS2 · Prime acc", sales: 7, revenue: "$98" },
];

const FunpayStatsPage: React.FC = () => {
  const stats: Stat[] = [
    { label: "Total accounts", value: 128 },
    { label: "Active rentals", value: 18 },
    { label: "Available", value: 62 },
    { label: "Orders (24h)", value: 34 },
  ];

  return (
    <div className="space-y-6">
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {stats.map((s) => (
          <StatCard key={s.label} label={s.label} value={s.value} />
        ))}
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <div className="lg:col-span-2 rounded-2xl border border-neutral-200 bg-white p-6 shadow-sm">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-semibold text-neutral-900">Orders per day</p>
              <p className="text-xs text-neutral-500">Last 7 days</p>
            </div>
            <span className="rounded-full bg-neutral-100 px-3 py-1 text-xs font-semibold text-neutral-700">+12% vs prev.</span>
          </div>
          <div className="mt-6 grid grid-cols-7 items-end gap-3">
            {bars.map((bar) => (
              <div key={bar.label} className="flex flex-col items-center gap-2">
                <div
                  className="w-full rounded-full bg-gradient-to-t from-indigo-500 to-indigo-300"
                  style={{ height: `${bar.value * 8}px` }}
                />
                <p className="text-xs text-neutral-500">{bar.label}</p>
              </div>
            ))}
          </div>
        </div>

        <div className="rounded-2xl border border-neutral-200 bg-white p-6 shadow-sm">
          <p className="text-sm font-semibold text-neutral-900">Top performing lots</p>
          <div className="mt-4 space-y-3">
            {topLots.map((lot) => (
              <div key={lot.name} className="rounded-xl border border-neutral-100 px-3 py-2">
                <p className="text-sm font-semibold text-neutral-900">{lot.name}</p>
                <div className="mt-1 flex items-center justify-between text-xs text-neutral-600">
                  <span>{lot.sales} sales</span>
                  <span className="font-semibold text-neutral-800">{lot.revenue}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <div className="rounded-2xl border border-neutral-200 bg-white p-6 shadow-sm">
          <p className="text-sm font-semibold text-neutral-900">Chat response time</p>
          <div className="mt-4 h-28 rounded-xl bg-gradient-to-r from-emerald-500 to-emerald-300 px-5 py-4 text-white shadow-inner">
            <p className="text-xs uppercase tracking-wide text-emerald-100">Median</p>
            <p className="text-3xl font-semibold">1m 42s</p>
            <p className="text-xs text-emerald-50">Across last 50 conversations</p>
          </div>
          <div className="mt-3 flex gap-3 text-xs text-neutral-600">
            <span className="rounded-full bg-neutral-100 px-3 py-1 font-semibold text-neutral-800">90th percentile: 3m 10s</span>
            <span className="rounded-full bg-neutral-100 px-3 py-1 font-semibold text-neutral-800">Fastest: 12s</span>
          </div>
        </div>

        <div className="rounded-2xl border border-neutral-200 bg-white p-6 shadow-sm">
          <p className="text-sm font-semibold text-neutral-900">Inventory snapshot</p>
          <div className="mt-4 grid grid-cols-2 gap-3 text-sm text-neutral-800">
            <div className="rounded-xl bg-neutral-50 px-3 py-3">
              <p className="text-xs uppercase tracking-wide text-neutral-500">Dota 2 lots</p>
              <p className="text-2xl font-semibold">24</p>
              <p className="text-xs text-neutral-500">8 need raising</p>
            </div>
            <div className="rounded-xl bg-neutral-50 px-3 py-3">
              <p className="text-xs uppercase tracking-wide text-neutral-500">CS2 lots</p>
              <p className="text-2xl font-semibold">13</p>
              <p className="text-xs text-neutral-500">3 need raising</p>
            </div>
            <div className="rounded-xl bg-neutral-50 px-3 py-3">
              <p className="text-xs uppercase tracking-wide text-neutral-500">Prime accounts</p>
              <p className="text-2xl font-semibold">7</p>
              <p className="text-xs text-neutral-500">stock OK</p>
            </div>
            <div className="rounded-xl bg-neutral-50 px-3 py-3">
              <p className="text-xs uppercase tracking-wide text-neutral-500">Boost slots</p>
              <p className="text-2xl font-semibold">12</p>
              <p className="text-xs text-neutral-500">4 assigned</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default FunpayStatsPage;