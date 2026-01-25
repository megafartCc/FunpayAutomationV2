import React from "react";

type Stat = { label: string; value: string | number };
type OrderDay = { day: string; value: number };
type TopLot = { name: string; sales: number; revenue: string };
type InventoryItem = { label: string; value: number; helper: string };

const StatCard: React.FC<Stat> = ({ label, value }) => (
  <div className="rounded-2xl border border-neutral-200 bg-white px-6 py-5 shadow-sm">
    <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-neutral-500">{label}</p>
    <div className="mt-2 text-3xl font-semibold text-neutral-900">{value}</div>
  </div>
);

const FunpayStatsPage: React.FC = () => {
  const stats: Stat[] = [
    { label: "Total accounts", value: 128 },
    { label: "Active rentals", value: 18 },
    { label: "Available", value: 62 },
    { label: "Orders (24h)", value: 34 },
  ];

  const ordersPerDay: OrderDay[] = [
    { day: "Mon", value: 5 },
    { day: "Tue", value: 10 },
    { day: "Wed", value: 4 },
    { day: "Thu", value: 9 },
    { day: "Fri", value: 8 },
    { day: "Sat", value: 6 },
    { day: "Sun", value: 11 },
  ];

  const topLots: TopLot[] = [
    { name: "Dota 2 • Boost 2-3k", sales: 22, revenue: "$180" },
    { name: "Dota 2 • Account 1-1.5k MMR", sales: 14, revenue: "$126" },
    { name: "CS2 • Prime acc", sales: 7, revenue: "$98" },
  ];

  const inventory: InventoryItem[] = [
    { label: "Dota 2 lots", value: 24, helper: "8 need raising" },
    { label: "CS2 lots", value: 13, helper: "3 need raising" },
    { label: "Prime accounts", value: 7, helper: "stock OK" },
    { label: "Boost slots", value: 12, helper: "4 assigned" },
  ];

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold text-neutral-900">Funpay Statistics</h1>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {stats.map((item) => (
          <StatCard key={item.label} label={item.label} value={item.value} />
        ))}
      </div>

      <div className="grid gap-6 xl:grid-cols-3">
        <div className="xl:col-span-2 rounded-2xl border border-neutral-200 bg-white p-6 shadow-sm">
          <div className="mb-6 flex items-center justify-between">
            <div>
              <p className="text-sm font-semibold text-neutral-900">Orders per day</p>
              <p className="text-xs text-neutral-500">Last 7 days</p>
            </div>
            <span className="rounded-full bg-neutral-100 px-3 py-1 text-[11px] font-semibold text-neutral-700">+12% vs prev.</span>
          </div>
          <div className="flex items-end gap-3">
            {ordersPerDay.map((item) => {
              const width = 40 + item.value * 10; // mimic pill lengths from reference
              return (
                <div key={item.day} className="flex w-full flex-col items-center gap-2">
                  <div
                    className="h-9 rounded-full bg-gradient-to-r from-indigo-500 to-indigo-300"
                    style={{ width: `${width}px`, minWidth: `${width}px` }}
                  />
                  <p className="text-xs text-neutral-500">{item.day}</p>
                </div>
              );
            })}
          </div>
        </div>

        <div className="rounded-2xl border border-neutral-200 bg-white p-6 shadow-sm">
          <p className="text-sm font-semibold text-neutral-900">Top performing lots</p>
          <div className="mt-4 space-y-4">
            {topLots.map((lot) => (
              <div key={lot.name} className="flex items-start justify-between rounded-xl border border-neutral-100 px-3 py-2">
                <div>
                  <p className="text-sm font-semibold text-neutral-900">{lot.name}</p>
                  <p className="text-xs text-neutral-500">{lot.sales} sales</p>
                </div>
                <p className="text-sm font-semibold text-neutral-900">{lot.revenue}</p>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="grid gap-6 xl:grid-cols-3">
        <div className="xl:col-span-2 rounded-2xl border border-neutral-200 bg-white p-6 shadow-sm">
          <p className="text-sm font-semibold text-neutral-900">Chat response time</p>
          <div className="mt-4 rounded-xl bg-gradient-to-r from-emerald-500 to-emerald-300 px-6 py-5 text-white shadow-inner">
            <p className="text-[11px] uppercase tracking-[0.08em] text-emerald-100">Median</p>
            <p className="mt-1 text-4xl font-semibold">1m 42s</p>
            <p className="text-xs text-emerald-50">Across last 50 conversations</p>
          </div>
          <div className="mt-3 flex flex-wrap gap-3 text-xs text-neutral-600">
            <span className="rounded-full bg-neutral-100 px-3 py-1 font-semibold text-neutral-800">90th percentile: 3m 10s</span>
            <span className="rounded-full bg-neutral-100 px-3 py-1 font-semibold text-neutral-800">Fastest: 12s</span>
          </div>
        </div>

        <div className="rounded-2xl border border-neutral-200 bg-white p-6 shadow-sm">
          <p className="text-sm font-semibold text-neutral-900">Inventory snapshot</p>
          <div className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-2">
            {inventory.map((item) => (
              <div key={item.label} className="rounded-xl bg-neutral-50 px-4 py-3">
                <p className="text-[11px] uppercase tracking-[0.08em] text-neutral-500">{item.label}</p>
                <p className="text-2xl font-semibold text-neutral-900">{item.value}</p>
                <p className="text-xs text-neutral-500">{item.helper}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};

export default FunpayStatsPage;
