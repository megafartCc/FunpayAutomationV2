import React from "react";

type StatCardProps = {
  label: string;
  value: string | number;
  delta?: string;
  icon: React.ReactNode;
  deltaTone?: "up" | "down";
};

const StatCard: React.FC<StatCardProps> = ({ label, value, delta, icon, deltaTone }) => (
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

const PlaceholderPanel: React.FC<{ minHeight: number; title: string }> = ({ minHeight, title }) => (
  <div className="rounded-2xl border border-neutral-200 bg-white p-6 shadow-sm" style={{ minHeight }}>
    <div className="text-base font-semibold text-neutral-900">{title}</div>
  </div>
);

const ShortPanel: React.FC<{ title: string; helper?: string; minHeight?: number }> = ({ title, helper, minHeight = 140 }) => (
  <div className="rounded-2xl border border-neutral-200 bg-white p-5 shadow-sm" style={{ minHeight }}>
    <div className="mb-3 flex items-center justify-between text-base font-semibold text-neutral-900">
      <span>{title}</span>
      {helper ? <span className="text-[12px] font-semibold text-neutral-500">{helper}</span> : null}
    </div>
    <div className="rounded-xl border border-dashed border-neutral-200 bg-neutral-50/60 px-4 py-6 text-center text-xs text-neutral-400" />
  </div>
);

const DashboardPage: React.FC = () => {
  const statCards: StatCardProps[] = [
    {
      label: "Revenue (24h)",
      value: "$742",
      delta: "+12%",
      deltaTone: "up",
      icon: (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M12 1v22M5 6h8a3 3 0 0 1 0 6H7a3 3 0 0 0 0 6h8" />
        </svg>
      ),
    },
    {
      label: "Active rentals",
      value: 18,
      delta: "+3",
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
      label: "Lots online",
      value: 42,
      delta: "+6%",
      deltaTone: "up",
      icon: (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M3 3h7v7H3zM14 3h7v7h-7zM14 14h7v7h-7zM3 14h7v7H3z" />
        </svg>
      ),
    },
    {
      label: "Support tickets",
      value: "2 open",
      delta: "+2%",
      deltaTone: "up",
      icon: (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
        </svg>
      ),
    },
  ];

  return (
    <div className="space-y-6">
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {statCards.map((card) => (
          <StatCard key={card.label} {...card} />
        ))}
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <PlaceholderPanel minHeight={880} title="Inventory" />
        <PlaceholderPanel minHeight={880} title="Active rentals" />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <ShortPanel title="Account actions" helper="Select an account" minHeight={180} />
        <ShortPanel title="Rental actions" helper="Select a rental" minHeight={180} />
      </div>
    </div>
  );
};

export default DashboardPage;
