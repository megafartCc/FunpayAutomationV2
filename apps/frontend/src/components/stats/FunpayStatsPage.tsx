import React from "react";

type Stat = { label: string; value: string | number };

type StatCardProps = Stat;

const StatCard: React.FC<StatCardProps> = ({ label, value }) => (
  <div className="rounded-2xl border border-neutral-200 bg-white px-6 py-5 shadow-sm">
    <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-neutral-500">{label}</p>
    <div className="mt-2 text-3xl font-semibold text-neutral-900">{value}</div>
  </div>
);

const blankCard = (className = "", minHeight = 260) => (
  <div
    className={`rounded-2xl border border-neutral-200 bg-white shadow-sm ${className}`}
    style={{ minHeight }}
  />
);

const FunpayStatsPage: React.FC = () => {
  const stats: Stat[] = [
    { label: "Total accounts", value: 128 },
    { label: "Active rentals", value: 18 },
    { label: "Available", value: 62 },
    { label: "Orders (24h)", value: 34 },
  ];

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold text-neutral-900">Funpay Statistics</h1>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {stats.map((item) => (
          <StatCard key={item.label} label={item.label} value={item.value} />
        ))}
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <div className="lg:col-span-2">{blankCard("p-0", 320)}</div>
        <div>{blankCard("p-0", 320)}</div>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <div className="lg:col-span-2">{blankCard("p-0", 240)}</div>
        <div>{blankCard("p-0", 240)}</div>
      </div>
    </div>
  );
};

export default FunpayStatsPage;
