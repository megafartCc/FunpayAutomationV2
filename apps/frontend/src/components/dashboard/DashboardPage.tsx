import React from "react";

type DeltaTone = "up" | "down";

type StatCardProps = {
  label: string;
  value: string | number;
  delta?: string;
  deltaTone?: DeltaTone;
  icon: React.ReactNode;
};

const CardUsersIcon = () => (
  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
    <path
      d="M21 19.9999C21 18.2583 19.3304 16.7767 17 16.2275M15 20C15 17.7909 12.3137 16 9 16C5.68629 16 3 17.7909 3 20M15 13C17.2091 13 19 11.2091 19 9C19 6.79086 17.2091 5 15 5M9 13C6.79086 13 5 11.2091 5 9C5 6.79086 6.79086 5 9 5C11.2091 5 13 6.79086 13 9C13 11.2091 11.2091 13 9 13Z"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
  </svg>
);

const CardCloudCheckIcon = () => (
  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
    <path
      d="M15 11L11 15L9 13M23 15C23 12.7909 21.2091 11 19 11C18.9764 11 18.9532 11.0002 18.9297 11.0006C18.4447 7.60802 15.5267 5 12 5C9.20335 5 6.79019 6.64004 5.66895 9.01082C3.06206 9.18144 1 11.3498 1 13.9999C1 16.7613 3.23858 19.0001 6 19.0001L19 19C21.2091 19 23 17.2091 23 15Z"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
  </svg>
);

const CardBarsIcon = () => (
  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
    <path
      d="M19.5 5.5V18.5M12 3.5V18.5M4.5 9.5V18.5M22 18.5H2"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
  </svg>
);

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
    { label: "Total Accounts", value: 20, delta: "+12%", deltaTone: "up", icon: <CardUsersIcon /> },
    { label: "Active Rentals", value: 0, delta: "-3%", deltaTone: "down", icon: <CardUsersIcon /> },
    { label: "Free Accounts", value: 20, delta: "+6%", deltaTone: "up", icon: <CardCloudCheckIcon /> },
    { label: "Past 24h", value: 0, delta: "+2%", deltaTone: "up", icon: <CardBarsIcon /> },
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
