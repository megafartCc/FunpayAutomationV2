import React from "react";

type StatCardProps = {
  label: string;
  value: string | number;
  delta?: string;
};

const StatCard: React.FC<StatCardProps> = ({ label, value, delta }) => (
  <div className="rounded-2xl border border-neutral-200 bg-white p-5 shadow-sm">
    <p className="text-xs font-semibold uppercase tracking-wide text-neutral-500">{label}</p>
    <div className="mt-2 flex items-baseline gap-2">
      <span className="text-3xl font-semibold text-neutral-900">{value}</span>
      {delta ? <span className="text-xs font-semibold text-emerald-600">{delta}</span> : null}
    </div>
  </div>
);

const QuickAction: React.FC<{ label: string }> = ({ label }) => (
  <button className="rounded-xl border border-neutral-200 bg-white px-4 py-3 text-sm font-semibold text-neutral-800 shadow-sm transition hover:-translate-y-0.5 hover:shadow-md">
    {label}
  </button>
);

const ListCard: React.FC<{ title: string; children: React.ReactNode }> = ({ title, children }) => (
  <div className="rounded-2xl border border-neutral-200 bg-white p-5 shadow-sm">
    <div className="mb-4 flex items-center justify-between">
      <p className="text-sm font-semibold text-neutral-900">{title}</p>
    </div>
    {children}
  </div>
);

const mockRentals = [
  { user: "megaflickX", game: "Dota 2", hours: "0.9h left", status: "Active" },
  { user: "Micronize", game: "Dota 2", hours: "3.4h left", status: "Active" },
  { user: "Savisa159", game: "CS2", hours: "done", status: "Closed" },
];

const mockTimeline = [
  { time: "20:24", text: "Buyer megaflickX paid order #TKZHUPX5" },
  { time: "20:29", text: "Auto-reply sent with stock list" },
  { time: "20:37", text: "User Micronize: «?? ??????»" },
];

const mockHealth = [
  { label: "FunPay API", status: "OK" },
  { label: "MySQL", status: "OK" },
  { label: "Railway Worker", status: "OK" },
];

const DashboardPage: React.FC = () => {
  return (
    <div className="space-y-6">
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Revenue (24h)" value="$742" delta="+12%" />
        <StatCard label="Active rentals" value="18" delta="+3" />
        <StatCard label="Lots online" value="42" />
        <StatCard label="Support tickets" value="2 open" />
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <div className="lg:col-span-2 rounded-2xl border border-neutral-200 bg-white p-6 shadow-sm">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="text-sm font-semibold text-neutral-900">Today’s flow</p>
              <p className="text-xs text-neutral-500">Orders, rentals, chats</p>
            </div>
            <div className="flex flex-wrap gap-2">
              <QuickAction label="Raise lots" />
              <QuickAction label="Sync inventory" />
              <QuickAction label="Refresh sessions" />
            </div>
          </div>
          <div className="mt-6 grid gap-3 md:grid-cols-3">
            <div className="rounded-xl bg-gradient-to-br from-neutral-900 to-neutral-700 p-4 text-white shadow-sm">
              <p className="text-xs uppercase tracking-wide text-neutral-200">Orders</p>
              <p className="mt-2 text-3xl font-semibold">12</p>
              <p className="text-xs text-neutral-300">3 pending confirmation</p>
            </div>
            <div className="rounded-xl bg-gradient-to-br from-indigo-500 to-indigo-700 p-4 text-white shadow-sm">
              <p className="text-xs uppercase tracking-wide text-indigo-100">Chats</p>
              <p className="mt-2 text-3xl font-semibold">27</p>
              <p className="text-xs text-indigo-100">5 unread</p>
            </div>
            <div className="rounded-xl bg-gradient-to-br from-emerald-500 to-emerald-700 p-4 text-white shadow-sm">
              <p className="text-xs uppercase tracking-wide text-emerald-100">Auto actions</p>
              <p className="mt-2 text-3xl font-semibold">34</p>
              <p className="text-xs text-emerald-100">today</p>
            </div>
          </div>
        </div>

        <ListCard title="System health">
          <ul className="space-y-3">
            {mockHealth.map((item) => (
              <li key={item.label} className="flex items-center justify-between rounded-xl border border-neutral-100 px-3 py-2">
                <div className="text-sm font-semibold text-neutral-800">{item.label}</div>
                <span className="rounded-full bg-emerald-50 px-3 py-1 text-xs font-semibold text-emerald-700">
                  {item.status}
                </span>
              </li>
            ))}
          </ul>
        </ListCard>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <ListCard title="Active rentals">
          <div className="space-y-3">
            {mockRentals.map((item) => (
              <div key={item.user + item.game} className="flex items-center justify-between rounded-xl bg-neutral-50 px-3 py-2">
                <div>
                  <p className="text-sm font-semibold text-neutral-900">{item.user}</p>
                  <p className="text-xs text-neutral-500">{item.game}</p>
                </div>
                <div className="text-xs font-semibold text-neutral-600">{item.hours}</div>
                <span className="rounded-full bg-emerald-50 px-2 py-1 text-[11px] font-semibold text-emerald-700">
                  {item.status}
                </span>
              </div>
            ))}
          </div>
        </ListCard>

        <ListCard title="Recent events">
          <ol className="space-y-3">
            {mockTimeline.map((item, idx) => (
              <li key={idx} className="flex items-start gap-3">
                <div className="mt-1 h-2 w-2 rounded-full bg-neutral-400" />
                <div>
                  <p className="text-xs font-semibold text-neutral-500">{item.time}</p>
                  <p className="text-sm text-neutral-900">{item.text}</p>
                </div>
              </li>
            ))}
          </ol>
        </ListCard>
      </div>
    </div>
  );
};

export default DashboardPage;