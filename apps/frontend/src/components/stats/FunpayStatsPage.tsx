import React from "react";

type Stat = { label: string; value: string | number; delta?: string; deltaTone?: "up" | "down"; icon: React.ReactNode };

type StatCardProps = Stat;

const StatCard: React.FC<StatCardProps> = ({ label, value, delta, deltaTone, icon }) => (
  <div className="flex items-start justify-between rounded-2xl border border-neutral-200 bg-white px-5 py-4 shadow-sm" style={{ minHeight: 110 }}>
    <div className="flex gap-3">
      <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-neutral-100 text-neutral-700">{icon}</div>
      <div className="flex flex-col">
        <p className="text-sm font-semibold text-neutral-900">{label}</p>
        <p className="mt-1 text-2xl font-semibold text-neutral-900">{value}</p>
      </div>
    </div>
    {delta ? (
      <span
        className={`rounded-full px-3 py-1 text-xs font-semibold ${
          deltaTone === "down" ? "bg-rose-50 text-rose-600" : "bg-emerald-50 text-emerald-600"
        }`}
      >
        {delta}
      </span>
    ) : null}
  </div>
);

const blankCard = (minHeight = 260) => (
  <div className="rounded-2xl border border-neutral-200 bg-white shadow-sm" style={{ minHeight }} />
);

const FunpayStatsPage: React.FC = () => {
  const stats: Stat[] = [
    {
      label: "Total accounts",
      value: 128,
      delta: "+12%",
      deltaTone: "up",
      icon: (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M17 21v-2a4 4 0 0 0-4-4H7a4 4 0 0 0-4 4v2" />
          <circle cx="9" cy="7" r="4" />
          <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
          <path d="M16 3.13a4 4 0 0 1 0 7.75" />
        </svg>
      ),
    },
    {
      label: "Active rentals",
      value: 18,
      delta: "+3%",
      deltaTone: "up",
      icon: (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M17 21v-2a4 4 0 0 0-4-4H7a4 4 0 0 0-4 4v2" />
          <circle cx="9" cy="7" r="4" />
          <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
          <path d="M16 3.13a4 4 0 0 1 0 7.75" />
        </svg>
      ),
    },
    {
      label: "Available",
      value: 62,
      delta: "+6%",
      deltaTone: "up",
      icon: (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M3 3h7v7H3zM14 3h7v7h-7zM14 14h7v7h-7zM3 14h7v7H3z" />
        </svg>
      ),
    },
    {
      label: "Orders (24h)",
      value: 34,
      delta: "+2%",
      deltaTone: "up",
      icon: (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M12 1v22M5 6h8a3 3 0 0 1 0 6H7a3 3 0 0 0 0 6h8" />
        </svg>
      ),
    },
  ];

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold text-neutral-900">Funpay Statistics</h1>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {stats.map((item) => (
          <StatCard key={item.label} {...item} />
        ))}
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <div className="lg:col-span-2">{blankCard(320)}</div>
        <div>{blankCard(320)}</div>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <div className="lg:col-span-2">{blankCard(240)}</div>
        <div>{blankCard(240)}</div>
      </div>
    </div>
  );
};

export default FunpayStatsPage;
