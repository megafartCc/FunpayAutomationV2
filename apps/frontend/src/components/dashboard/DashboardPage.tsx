import React from "react";

type StatCardProps = {
  label: string;
  value: string | number;
  delta?: string;
};

const StatCard: React.FC<StatCardProps> = ({ label, value, delta }) => (
  <div className="rounded-2xl border border-neutral-200 bg-white px-6 py-5 shadow-sm">
    <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-neutral-500">{label}</p>
    <div className="mt-2 flex items-baseline gap-2">
      <span className="text-3xl font-semibold text-neutral-900">{value}</span>
      {delta ? <span className="text-xs font-semibold text-emerald-600">{delta}</span> : null}
    </div>
  </div>
);

const PlaceholderPanel: React.FC<{ minHeight: number }> = ({ minHeight }) => (
  <div className="rounded-2xl border border-neutral-200 bg-white p-6 shadow-sm" style={{ minHeight }} />
);

const ShortPanel: React.FC<{ title: string; helper?: string }> = ({ title, helper }) => (
  <div className="rounded-2xl border border-neutral-200 bg-white p-5 shadow-sm">
    <div className="mb-3 flex items-center justify-between text-sm font-semibold text-neutral-900">
      <span>{title}</span>
      {helper ? <span className="text-[11px] font-semibold text-neutral-500">{helper}</span> : null}
    </div>
    <div className="rounded-xl border border-dashed border-neutral-200 bg-neutral-50/60 px-4 py-4 text-center text-xs text-neutral-400">
      {/* placeholder area */}
    </div>
  </div>
);

const DashboardPage: React.FC = () => {
  return (
    <div className="space-y-6">
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Revenue (24h)" value="$742" delta="+12%" />
        <StatCard label="Active rentals" value="18" delta="+3" />
        <StatCard label="Lots online" value="42" />
        <StatCard label="Support tickets" value="2 open" />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <PlaceholderPanel minHeight={720} />
        <PlaceholderPanel minHeight={720} />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <ShortPanel title="Account actions" helper="Select an account" />
        <ShortPanel title="Rental actions" helper="Select a rental" />
      </div>
    </div>
  );
};

export default DashboardPage;
