import React, { useCallback, useEffect, useMemo, useState } from "react";
import { useI18n } from "../../i18n/useI18n";
import { api, ActiveRentalItem, OrderHistoryItem } from "../../services/api";
import { useWorkspace } from "../../context/WorkspaceContext";

type DeltaTone = "up" | "down";

type Stat = { label: string; value: string | number; delta?: string; deltaTone?: DeltaTone; icon: React.ReactNode };

type StatCardProps = Stat;

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

const getChartBarColor = (index: number) => {
  if (index % 6 === 0) return "bg-indigo-500";
  if (index % 6 === 1) return "bg-sky-500";
  if (index % 6 === 2) return "bg-emerald-500";
  if (index % 6 === 3) return "bg-amber-500";
  if (index % 6 === 4) return "bg-rose-500";
  return "bg-violet-500";
};

type ActivityPoint = {
  label: string;
  value: number;
};

type BuyerStat = {
  name: string;
  orders: number;
  avgHours: number;
};

const formatHoursLabel = (hours: number) => `${hours.toFixed(1)}h`;

const FunpayStatsPage: React.FC = () => {
  const { tr } = useI18n();
  const { selectedId } = useWorkspace();
  const [range, setRange] = useState<"7d" | "30d" | "90d" | "all">("30d");
  const [orders, setOrders] = useState<OrderHistoryItem[]>([]);
  const [activeRentals, setActiveRentals] = useState<ActiveRentalItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  const workspaceId = selectedId === "all" ? undefined : selectedId;

  const loadStats = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [ordersRes, rentalsRes] = await Promise.all([
        api.listOrdersHistory(workspaceId ?? null, "", 500),
        api.listActiveRentals(workspaceId),
      ]);
      setOrders(ordersRes.items || []);
      setActiveRentals(rentalsRes.items || []);
      setLastUpdated(new Date());
    } catch (err) {
      const message =
        (err as { message?: string })?.message ||
        tr("Failed to load statistics.", "Не удалось загрузить статистику.");
      setError(message);
    } finally {
      setLoading(false);
    }
  }, [workspaceId, tr]);

  useEffect(() => {
    void loadStats();
    const interval = window.setInterval(() => {
      void loadStats();
    }, 30000);
    return () => window.clearInterval(interval);
  }, [loadStats]);

  const rangeLabel = useMemo(() => {
    switch (range) {
      case "7d":
        return tr("Last 7 days", "Последние 7 дней");
      case "90d":
        return tr("Last 90 days", "Последние 90 дней");
      case "all":
        return tr("All time", "За все время");
      default:
        return tr("Last 30 days", "Последние 30 дней");
    }
  }, [range, tr]);

  const rangeCutoff = useMemo(() => {
    if (range === "all") return null;
    const days = range === "7d" ? 7 : range === "90d" ? 90 : 30;
    const cutoff = new Date();
    cutoff.setDate(cutoff.getDate() - days);
    return cutoff;
  }, [range]);

  const ordersInRange = useMemo(() => {
    if (!rangeCutoff) return orders;
    return orders.filter((order) => {
      if (!order.created_at) return false;
      const dt = new Date(order.created_at);
      if (Number.isNaN(dt.getTime())) return false;
      return dt >= rangeCutoff;
    });
  }, [orders, rangeCutoff]);

  const buyers = useMemo<BuyerStat[]>(() => {
    const map = new Map<string, { orders: number; totalMinutes: number; minutesCount: number }>();
    ordersInRange.forEach((order) => {
      const buyer = order.buyer || tr("Unknown", "Неизвестно");
      const entry = map.get(buyer) ?? { orders: 0, totalMinutes: 0, minutesCount: 0 };
      entry.orders += 1;
      if (order.rental_minutes) {
        entry.totalMinutes += order.rental_minutes;
        entry.minutesCount += 1;
      }
      map.set(buyer, entry);
    });
    return Array.from(map.entries())
      .map(([name, stats]) => ({
        name,
        orders: stats.orders,
        avgHours: stats.minutesCount ? stats.totalMinutes / 60 / stats.minutesCount : 0,
      }))
      .sort((a, b) => b.orders - a.orders)
      .slice(0, 5);
  }, [ordersInRange, tr]);

  const avgRentalHours = useMemo(() => {
    const minutes = ordersInRange.map((order) => order.rental_minutes || 0).filter((value) => value > 0);
    if (!minutes.length) return 0;
    return minutes.reduce((sum, value) => sum + value, 0) / 60 / minutes.length;
  }, [ordersInRange]);

  const averageOrderValue = useMemo(() => {
    const values = ordersInRange
      .map((order) => (typeof order.price === "number" ? order.price : order.amount ?? 0))
      .filter((value) => value > 0);
    if (!values.length) return 0;
    return values.reduce((sum, value) => sum + value, 0) / values.length;
  }, [ordersInRange]);

  const totalBuyers = useMemo(() => {
    const set = new Set(ordersInRange.map((order) => order.buyer).filter(Boolean));
    return set.size;
  }, [ordersInRange]);

  const hourlyActivity = useMemo<ActivityPoint[]>(() => {
    const buckets = Array.from({ length: 12 }, (_, idx) => ({
      label: `${String(idx * 2).padStart(2, "0")}:00`,
      value: 0,
    }));
    ordersInRange.forEach((order) => {
      if (!order.created_at) return;
      const dt = new Date(order.created_at);
      if (Number.isNaN(dt.getTime())) return;
      const bucket = Math.floor(dt.getHours() / 2);
      buckets[bucket].value += 1;
    });
    return buckets;
  }, [ordersInRange]);

  const peakHour = useMemo(() => {
    if (!hourlyActivity.length) return { label: "--:--", value: 0 };
    return hourlyActivity.reduce((acc, point) => (point.value > acc.value ? point : acc), hourlyActivity[0]);
  }, [hourlyActivity]);

  const peakRangeLabel = useMemo(() => {
    if (peakHour.label === "--:--") return "--";
    const start = Number.parseInt(peakHour.label.slice(0, 2), 10);
    if (Number.isNaN(start)) return "--";
    const end = (start + 1) % 24;
    const startLabel = String(start).padStart(2, "0");
    const endLabel = String(end).padStart(2, "0");
    return `${startLabel}:00 - ${endLabel}:59`;
  }, [peakHour.label]);

  const weeklyOverview = useMemo(() => {
    const now = new Date();
    const days = Array.from({ length: 7 }, (_, idx) => {
      const date = new Date(now);
      date.setDate(now.getDate() - (6 - idx));
      const key = date.toISOString().slice(0, 10);
      return { key, label: date.toLocaleDateString(undefined, { weekday: "short" }) };
    });
    const map = new Map<string, { orders: number; totalMinutes: number; countMinutes: number }>();
    ordersInRange.forEach((order) => {
      if (!order.created_at) return;
      const dt = new Date(order.created_at);
      if (Number.isNaN(dt.getTime())) return;
      const key = dt.toISOString().slice(0, 10);
      const entry = map.get(key) ?? { orders: 0, totalMinutes: 0, countMinutes: 0 };
      entry.orders += 1;
      if (order.rental_minutes) {
        entry.totalMinutes += order.rental_minutes;
        entry.countMinutes += 1;
      }
      map.set(key, entry);
    });
    return days.map((day) => {
      const stats = map.get(day.key);
      return {
        label: day.label,
        orders: stats?.orders ?? 0,
        avg: stats?.countMinutes ? stats.totalMinutes / 60 / stats.countMinutes : 0,
      };
    });
  }, [ordersInRange]);

  const mostPopularBuyer = buyers[0]?.name || tr("No data", "Нет данных");
  const topBuyerOrders = buyers[0]?.orders ?? 0;

  const stats: Stat[] = [
    {
      label: tr("Total orders", "Всего заказов"),
      value: ordersInRange.length,
      icon: <CardBarsIcon />,
    },
    {
      label: tr("Active rentals", "Активные аренды"),
      value: activeRentals.length,
      icon: <CardUsersIcon />,
    },
    {
      label: tr("Average rental time", "Среднее время аренды"),
      value: avgRentalHours ? formatHoursLabel(avgRentalHours) : "-",
      icon: <CardCloudCheckIcon />,
    },
    {
      label: tr("Most popular buyer", "Самый частый покупатель"),
      value: mostPopularBuyer,
      delta: topBuyerOrders ? `${topBuyerOrders} ${tr("orders", "заказов")}` : undefined,
      icon: <CardUsersIcon />,
    },
  ];

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-neutral-900">{tr("Funpay Statistics", "Статистика FunPay")}</h1>
          <p className="text-sm text-neutral-500">
            {tr(
              "Rental activity, buyer trends, and performance insights.",
              "Активность аренд, тренды покупателей и ключевые показатели.",
            )}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <div className="flex flex-wrap items-center gap-2 rounded-xl border border-neutral-200 bg-white p-2 shadow-sm">
            {(
              [
                { key: "7d", label: tr("7d", "7д") },
                { key: "30d", label: tr("30d", "30д") },
                { key: "90d", label: tr("90d", "90д") },
                { key: "all", label: tr("All", "Все") },
              ] as const
            ).map((item) => (
              <button
                key={item.key}
                onClick={() => setRange(item.key)}
                className={`rounded-lg px-3 py-1 text-xs font-semibold transition ${
                  range === item.key
                    ? "bg-neutral-900 text-white"
                    : "bg-neutral-100 text-neutral-600 hover:bg-neutral-200"
                }`}
              >
                {item.label}
              </button>
            ))}
          </div>
          <button
            onClick={() => loadStats()}
            className="rounded-lg border border-neutral-200 bg-white px-3 py-2 text-xs font-semibold text-neutral-600 shadow-sm hover:bg-neutral-50"
          >
            {tr("Refresh", "Обновить")}
          </button>
        </div>
      </div>

      {error ? (
        <div className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
          {error}
        </div>
      ) : null}

      <div className="flex flex-wrap items-center gap-3 text-xs text-neutral-500">
        <span className="rounded-full bg-neutral-100 px-3 py-1 font-semibold text-neutral-600">{rangeLabel}</span>
        <span>
          {tr("Last update:", "Обновлено:")}{" "}
          {lastUpdated ? lastUpdated.toLocaleTimeString() : tr("Loading...", "Загрузка...")}
        </span>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {stats.map((item) => (
          <StatCard key={item.label} {...item} />
        ))}
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <div className="lg:col-span-2 rounded-2xl border border-neutral-200 bg-white p-5 shadow-sm">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 className="text-lg font-semibold text-neutral-900">
                {tr("Rental activity by time", "Активность аренд по времени")}
              </h2>
              <p className="text-sm text-neutral-500">
                {tr("Peak hour: {hour}", "Пиковый час: {hour}", { hour: peakHour.label })}
              </p>
            </div>
            <span className="rounded-full bg-neutral-100 px-3 py-1 text-xs font-semibold text-neutral-600">
              {rangeLabel}
            </span>
          </div>
          <div className="mt-6 grid grid-cols-12 items-end gap-2">
            {hourlyActivity.map((point, index) => (
              <div key={point.label} className="flex flex-col items-center gap-2">
                <div className="text-[10px] font-semibold text-neutral-500">{point.value}</div>
                <div
                  className={`w-7 rounded-full ${getChartBarColor(index)}`}
                  style={{ height: `${Math.max(24, point.value * 6)}px` }}
                  title={`${point.label}: ${point.value}`}
                />
                <div className="text-[10px] text-neutral-400">{point.label}</div>
              </div>
            ))}
          </div>
        </div>
        <div className="rounded-2xl border border-neutral-200 bg-white p-5 shadow-sm">
          <h2 className="text-lg font-semibold text-neutral-900">
            {tr("Key performance", "Ключевые показатели")}
          </h2>
          <div className="mt-4 space-y-3 text-sm text-neutral-600">
            <div className="flex items-center justify-between">
              <span>{tr("Average order value", "Средний чек")}</span>
              <span className="font-semibold text-neutral-900">
                {averageOrderValue ? `${averageOrderValue.toFixed(0)} ₽` : "-"}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span>{tr("Total buyers", "Всего покупателей")}</span>
              <span className="font-semibold text-neutral-900">{totalBuyers}</span>
            </div>
            <div className="flex items-center justify-between">
              <span>{tr("Peak hour rentals", "Аренд в пик")}</span>
              <span className="font-semibold text-neutral-900">{peakHour.value}</span>
            </div>
          </div>
          <div className="mt-5 rounded-xl bg-neutral-50 p-4">
            <p className="text-xs uppercase tracking-wide text-neutral-400">
              {tr("Most popular buyer", "Самый частый покупатель")}
            </p>
            <p className="mt-2 text-lg font-semibold text-neutral-900">{mostPopularBuyer}</p>
            <p className="text-xs text-neutral-500">
              {topBuyerOrders
                ? tr("{count} orders in period", "{count} заказов за период", { count: topBuyerOrders })
                : tr("No orders for the selected range.", "Нет заказов за выбранный период.")}
            </p>
          </div>
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <div className="lg:col-span-2 rounded-2xl border border-neutral-200 bg-white p-5 shadow-sm">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 className="text-lg font-semibold text-neutral-900">
                {tr("Top buyers", "Топ покупателей")}
              </h2>
              <p className="text-sm text-neutral-500">
                {tr("Most frequent renters for the selected range.", "Самые частые арендаторы за период.")}
              </p>
            </div>
            <span className="rounded-full bg-neutral-100 px-3 py-1 text-xs font-semibold text-neutral-600">
              {tr("{count} buyers", "{count} покупателей", { count: totalBuyers })}
            </span>
          </div>
          {buyers.length ? (
            <div className="mt-4 divide-y divide-neutral-100">
              {buyers.map((buyer, idx) => (
                <div key={buyer.name} className="flex flex-wrap items-center justify-between gap-3 py-3">
                  <div className="flex items-center gap-3">
                    <div className="flex h-8 w-8 items-center justify-center rounded-full bg-neutral-100 text-xs font-semibold text-neutral-700">
                      {idx + 1}
                    </div>
                    <div>
                      <p className="text-sm font-semibold text-neutral-900">{buyer.name}</p>
                      <p className="text-xs text-neutral-500">
                        {tr("Avg rental", "Средняя аренда")}: {buyer.avgHours ? formatHoursLabel(buyer.avgHours) : "-"}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <div className="text-right">
                      <p className="text-sm font-semibold text-neutral-900">
                        {buyer.orders} {tr("orders", "заказов")}
                      </p>
                    </div>
                    <div className="h-2 w-24 rounded-full bg-neutral-100">
                      <div
                        className="h-2 rounded-full bg-neutral-900"
                        style={{ width: `${Math.min(100, buyer.orders * 2)}%` }}
                      />
                    </div>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="mt-4 rounded-xl bg-neutral-50 p-4 text-sm text-neutral-500">
              {tr("No buyers yet for the selected range.", "Пока нет покупателей за выбранный период.")}
            </div>
          )}
        </div>
        <div className="rounded-2xl border border-neutral-200 bg-white p-5 shadow-sm">
          <h2 className="text-lg font-semibold text-neutral-900">
            {tr("Activity insights", "Инсайты активности")}
          </h2>
          <div className="mt-4 space-y-4">
            <div className="rounded-xl bg-neutral-50 p-4">
              <p className="text-xs uppercase tracking-wide text-neutral-400">{tr("Highest demand", "Пик спроса")}</p>
              <p className="mt-1 text-sm font-semibold text-neutral-900">
                {peakRangeLabel}
              </p>
              <p className="text-xs text-neutral-500">
                {tr(
                  "Based on orders created during the selected range.",
                  "На основе заказов за выбранный период.",
                )}
              </p>
            </div>
            <div className="rounded-xl bg-neutral-50 p-4">
              <p className="text-xs uppercase tracking-wide text-neutral-400">{tr("Average order value", "Средний чек")}</p>
              <p className="mt-1 text-sm font-semibold text-neutral-900">
                {averageOrderValue ? `${averageOrderValue.toFixed(0)} ₽` : "-"}
              </p>
              <p className="text-xs text-neutral-500">
                {tr("Calculated from recent orders.", "Рассчитано по последним заказам.")}
              </p>
            </div>
            <div className="rounded-xl bg-neutral-50 p-4">
              <p className="text-xs uppercase tracking-wide text-neutral-400">{tr("Queue health", "Состояние очереди")}</p>
              <p className="mt-1 text-sm font-semibold text-neutral-900">
                {activeRentals.length > 0 ? tr("Active", "Активно") : tr("Quiet", "Спокойно")}
              </p>
              <p className="text-xs text-neutral-500">
                {activeRentals.length > 0
                  ? tr("Rentals are currently in progress.", "Идут активные аренды.")
                  : tr("No active rentals right now.", "Сейчас нет активных аренд.")}
              </p>
            </div>
          </div>
        </div>
      </div>

      <div className="rounded-2xl border border-neutral-200 bg-white p-5 shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold text-neutral-900">
              {tr("Orders overview", "Сводка заказов")}
            </h2>
            <p className="text-sm text-neutral-500">
              {tr("Track overall volume and average rental time by day.", "Отслеживайте объем и среднее время аренды по дням.")}
            </p>
          </div>
          <span className="rounded-full bg-neutral-100 px-3 py-1 text-xs font-semibold text-neutral-600">
            {loading ? tr("Loading...", "Загрузка...") : tr("{count} orders", "{count} заказов", { count: ordersInRange.length })}
          </span>
        </div>
        <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {weeklyOverview.map((day) => (
            <div key={day.label} className="rounded-xl border border-neutral-100 bg-neutral-50 p-4">
              <p className="text-xs font-semibold uppercase text-neutral-400">{day.label}</p>
              <p className="mt-2 text-2xl font-semibold text-neutral-900">{day.orders}</p>
              <p className="text-xs text-neutral-500">
                {tr("Avg rental", "Средняя аренда")}: {day.avg ? formatHoursLabel(day.avg) : "-"}
              </p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

export default FunpayStatsPage;
