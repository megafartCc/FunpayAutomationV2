import React, { useCallback, useEffect, useMemo, useState } from "react";
import {
  BarElement,
  CategoryScale,
  Chart as ChartJS,
  Filler,
  LinearScale,
  Legend as ChartLegend,
  LineElement,
  PointElement,
  Tooltip as ChartTooltip,
} from "chart.js";
import { Bar as ChartBar, Line as ChartLine } from "react-chartjs-2";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { useI18n } from "../../i18n/useI18n";
import {
  api,
  ActiveRentalItem,
  NotificationItem,
  OrderHistoryItem,
  PriceDumperHistoryItem,
  RentalsHeatmapResponse,
} from "../../services/api";
import { useWorkspace } from "../../context/WorkspaceContext";

ChartJS.register(
  CategoryScale,
  LinearScale,
  BarElement,
  LineElement,
  PointElement,
  Filler,
  ChartTooltip,
  ChartLegend,
);

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

type ActivityPoint = {
  label: string;
  value: number;
};

type DailyStat = {
  key: string;
  label: string;
  orders: number;
  avg: number;
};

type BuyerStat = {
  name: string;
  orders: number;
  avgHours: number;
};

type RevenuePoint = {
  key: string;
  label: string;
  revenue: number;
  orders: number;
};

type AccountStat = {
  name: string;
  orders: number;
  revenue: number;
  hours: number;
};

const formatHoursLabel = (hours: number) => `${hours.toFixed(1)}h`;
const formatCurrency = (value: number) => `${Math.round(value).toLocaleString("ru-RU")} ₽`;

const FunpayStatsPage: React.FC = () => {
  const { tr } = useI18n();
  const { selectedId } = useWorkspace();
  const [range, setRange] = useState<"7d" | "30d" | "90d" | "all">("30d");
  const [orders, setOrders] = useState<OrderHistoryItem[]>([]);
  const [activeRentals, setActiveRentals] = useState<ActiveRentalItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [notifications, setNotifications] = useState<NotificationItem[]>([]);
  const [notificationsLoaded, setNotificationsLoaded] = useState(false);
  const [marketHistory, setMarketHistory] = useState<PriceDumperHistoryItem[]>([]);
  const [marketHistoryLoading, setMarketHistoryLoading] = useState(false);
  const [marketHistoryError, setMarketHistoryError] = useState<string | null>(null);
  const [marketHistoryUrl, setMarketHistoryUrl] = useState<string | null>(null);
  const [marketHistoryRefreshed, setMarketHistoryRefreshed] = useState(false);
  const [heatmap, setHeatmap] = useState<RentalsHeatmapResponse | null>(null);
  const [heatmapLoading, setHeatmapLoading] = useState(false);
  const [heatmapError, setHeatmapError] = useState<string | null>(null);

  const workspaceId = selectedId === "all" ? undefined : selectedId;

  const loadStats = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [ordersRes, rentalsRes, notificationsRes] = await Promise.all([
        api.listOrdersHistory(workspaceId ?? null, "", 500),
        api.listActiveRentals(workspaceId),
        api.listNotifications(workspaceId ?? null, 500),
      ]);
      const ordersItems = Array.isArray(ordersRes.items) ? ordersRes.items : [];
      const rentalItems = Array.isArray(rentalsRes.items) ? rentalsRes.items : [];
      const notificationItems = Array.isArray(notificationsRes.items) ? notificationsRes.items : [];
      setOrders(ordersItems.filter(Boolean));
      setActiveRentals(rentalItems.filter(Boolean));
      setNotifications(notificationItems);
      setNotificationsLoaded(true);
      setLastUpdated(new Date());
    } catch (err) {
      const message =
        (err as { message?: string })?.message ||
        tr("Failed to load statistics.", "Не удалось загрузить статистику.");
      setError(message);
      setNotificationsLoaded(true);
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

  const heatmapDays = useMemo(() => {
    if (range === "7d") return 7;
    if (range === "90d") return 90;
    if (range === "all") return 365;
    return 30;
  }, [range]);

  const loadHeatmap = useCallback(async () => {
    setHeatmapLoading(true);
    setHeatmapError(null);
    try {
      const res = await api.rentalsHeatmap(workspaceId ?? null, heatmapDays, [
        "assign",
        "replace_assign",
        "extend",
      ]);
      setHeatmap(res);
    } catch (err) {
      const message =
        (err as { message?: string })?.message ||
        tr("Failed to load heatmap.", "Не удалось загрузить тепловую карту.");
      setHeatmapError(message);
      setHeatmap(null);
    } finally {
      setHeatmapLoading(false);
    }
  }, [workspaceId, heatmapDays, tr]);

  useEffect(() => {
    void loadHeatmap();
  }, [loadHeatmap]);

  const marketHistoryDays = useMemo(() => {
    if (range === "7d") return 7;
    if (range === "90d") return 90;
    if (range === "all") return 365;
    return 30;
  }, [range]);

  const loadMarketHistory = useCallback(async () => {
    setMarketHistoryLoading(true);
    setMarketHistoryError(null);
    try {
      const res = await api.priceDumperHistory(null, marketHistoryDays);
      setMarketHistory(Array.isArray(res.items) ? res.items : []);
      setMarketHistoryUrl(res.url || null);
    } catch (err) {
      const message =
        (err as { message?: string })?.message ||
        tr("Failed to load market history.", "Не удалось загрузить историю рынка.");
      setMarketHistoryError(message);
    } finally {
      setMarketHistoryLoading(false);
    }
  }, [marketHistoryDays, tr]);

  useEffect(() => {
    void loadMarketHistory();
  }, [loadMarketHistory]);

  useEffect(() => {
    if (marketHistoryRefreshed) return;
    setMarketHistoryRefreshed(true);
    api
      .refreshPriceDumper()
      .then(() => loadMarketHistory())
      .catch(() => loadMarketHistory());
  }, [marketHistoryRefreshed, loadMarketHistory]);

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

  const dailyOverview = useMemo<DailyStat[]>(() => {
    const map = new Map<string, { orders: number; totalMinutes: number; countMinutes: number }>();
    const dates: Date[] = [];
    ordersInRange.forEach((order) => {
      if (!order.created_at) return;
      const dt = new Date(order.created_at);
      if (Number.isNaN(dt.getTime())) return;
      dates.push(dt);
      const key = new Date(dt.getFullYear(), dt.getMonth(), dt.getDate()).toISOString().slice(0, 10);
      const entry = map.get(key) ?? { orders: 0, totalMinutes: 0, countMinutes: 0 };
      entry.orders += 1;
      if (order.rental_minutes) {
        entry.totalMinutes += order.rental_minutes;
        entry.countMinutes += 1;
      }
      map.set(key, entry);
    });

    const today = new Date();
    const rangeStart = rangeCutoff
      ? new Date(rangeCutoff.getFullYear(), rangeCutoff.getMonth(), rangeCutoff.getDate())
      : dates.length
        ? new Date(Math.min(...dates.map((dt) => dt.getTime())))
        : new Date(today.getFullYear(), today.getMonth(), today.getDate());
    const end = new Date(today.getFullYear(), today.getMonth(), today.getDate());

    const results: DailyStat[] = [];
    const cursor = new Date(rangeStart);
    while (cursor <= end) {
      const key = cursor.toISOString().slice(0, 10);
      const label = cursor.toLocaleDateString(undefined, { month: "short", day: "numeric" });
      const stats = map.get(key);
      results.push({
        key,
        label,
        orders: stats?.orders ?? 0,
        avg: stats?.countMinutes ? stats.totalMinutes / 60 / stats.countMinutes : 0,
      });
      cursor.setDate(cursor.getDate() + 1);
    }
    return results;
  }, [ordersInRange, rangeCutoff]);

  const heatmapMatrix = useMemo(() => {
    const grid = Array.from({ length: 7 }, () => Array.from({ length: 24 }, () => 0));
    const maxValue = heatmap?.max ?? 0;
    (heatmap?.items || []).forEach((item) => {
      if (item.day >= 0 && item.day < 7 && item.hour >= 0 && item.hour < 24) {
        grid[item.day][item.hour] = item.count;
      }
    });
    return { grid, max: maxValue };
  }, [heatmap]);

  const heatmapDayLabels = useMemo(
    () => [
      tr("Mon", "Пн"),
      tr("Tue", "Вт"),
      tr("Wed", "Ср"),
      tr("Thu", "Чт"),
      tr("Fri", "Пт"),
      tr("Sat", "Сб"),
      tr("Sun", "Вс"),
    ],
    [tr],
  );

  const dailyRevenue = useMemo<RevenuePoint[]>(() => {
    const map = new Map<string, { revenue: number; orders: number }>();
    ordersInRange.forEach((order) => {
      if (!order.created_at) return;
      const dt = new Date(order.created_at);
      if (Number.isNaN(dt.getTime())) return;
      const key = new Date(dt.getFullYear(), dt.getMonth(), dt.getDate()).toISOString().slice(0, 10);
      const entry = map.get(key) ?? { revenue: 0, orders: 0 };
      const value = typeof order.price === "number" ? order.price : order.amount ?? 0;
      entry.revenue += value;
      entry.orders += 1;
      map.set(key, entry);
    });
    return dailyOverview.map((item) => {
      const stats = map.get(item.key);
      return {
        key: item.key,
        label: item.label,
        revenue: stats?.revenue ?? 0,
        orders: stats?.orders ?? 0,
      };
    });
  }, [dailyOverview, ordersInRange]);

  const weeklyRevenue = useMemo<RevenuePoint[]>(() => {
    const map = new Map<string, { revenue: number; orders: number; label: string }>();
    ordersInRange.forEach((order) => {
      if (!order.created_at) return;
      const dt = new Date(order.created_at);
      if (Number.isNaN(dt.getTime())) return;
      const day = dt.getDay() === 0 ? 6 : dt.getDay() - 1;
      const monday = new Date(dt.getFullYear(), dt.getMonth(), dt.getDate() - day);
      const key = monday.toISOString().slice(0, 10);
      const entry = map.get(key) ?? {
        revenue: 0,
        orders: 0,
        label: monday.toLocaleDateString(undefined, { month: "short", day: "numeric" }),
      };
      const value = typeof order.price === "number" ? order.price : order.amount ?? 0;
      entry.revenue += value;
      entry.orders += 1;
      map.set(key, entry);
    });
    return Array.from(map.entries())
      .map(([key, stats]) => ({
        key,
        label: stats.label,
        revenue: stats.revenue,
        orders: stats.orders,
      }))
      .sort((a, b) => a.key.localeCompare(b.key));
  }, [ordersInRange]);

  const refundsInRange = useMemo(() => {
    if (!notificationsLoaded) return [];
    return notifications.filter((item) => {
      if (!item.created_at) return false;
      const eventType = (item.event_type || "").toLowerCase();
      if (!eventType.startsWith("refund")) return false;
      if (item.status && item.status !== "ok") return false;
      const dt = new Date(item.created_at);
      if (Number.isNaN(dt.getTime())) return false;
      if (rangeCutoff && dt < rangeCutoff) return false;
      return true;
    });
  }, [notifications, notificationsLoaded, rangeCutoff]);

  const refundStats = useMemo(() => {
    const totalOrders = ordersInRange.length;
    const refundedOrders = Math.min(refundsInRange.length, totalOrders);
    const refundRate = totalOrders ? (refundedOrders / totalOrders) * 100 : 0;
    const refundsLoss = ordersInRange
      .filter((order) => (order.action || "").toLowerCase().includes("refund"))
      .reduce((sum, order) => sum + (order.price ?? order.amount ?? 0), 0);
    return { totalOrders, refundedOrders, refundRate, refundsLoss };
  }, [ordersInRange.length, refundsInRange.length, ordersInRange]);

  const refundPercent = useMemo(() => {
    if (!refundStats.totalOrders) return 0;
    const value = (refundStats.refundedOrders / refundStats.totalOrders) * 100;
    return Math.min(100, Math.max(0, Number.isFinite(value) ? value : 0));
  }, [refundStats.refundedOrders, refundStats.totalOrders]);
  const keptPercent = Math.max(0, 100 - refundPercent);



  const accountPopularity = useMemo<AccountStat[]>(() => {
    const map = new Map<string, { orders: number; revenue: number; minutes: number }>();
    ordersInRange.forEach((order) => {
      const name =
        order.account_name ||
        order.account_login ||
        (order.account_id ? `ID ${order.account_id}` : tr("Unknown", "Неизвестно"));
      const entry = map.get(name) ?? { orders: 0, revenue: 0, minutes: 0 };
      entry.orders += 1;
      entry.revenue += typeof order.price === "number" ? order.price : order.amount ?? 0;
      entry.minutes += order.rental_minutes ?? 0;
      map.set(name, entry);
    });
    return Array.from(map.entries())
      .map(([name, stats]) => ({
        name,
        orders: stats.orders,
        revenue: stats.revenue,
        hours: stats.minutes / 60,
      }))
      .sort((a, b) => b.orders - a.orders)
      .slice(0, 6);
  }, [ordersInRange, tr]);

  const accountPopularityChart = useMemo(() => {
    const labels = accountPopularity.map((account) => account.name);
    const values = accountPopularity.map((account) => account.orders);
    const maxValue = values.length ? Math.max(...values) : 0;
    return {
      data: {
        labels,
        datasets: [
          {
            label: tr("Orders", "Заказы"),
            data: values,
            backgroundColor: "rgba(14, 165, 233, 0.92)",
            borderRadius: 10,
            maxBarThickness: 42,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        layout: { padding: { top: 8, right: 8, bottom: 0, left: 4 } },
        scales: {
          x: {
            grid: { display: false },
            ticks: {
              color: "#94a3b8",
              font: { size: 10 },
              maxRotation: 0,
              autoSkip: false,
              callback: (value: string | number) => {
                const label = labels[Number(value)] || "";
                return label.length > 10 ? `${label.slice(0, 10)}…` : label;
              },
            },
          },
          y: {
            beginAtZero: true,
            grid: { color: "rgba(148, 163, 184, 0.2)" },
            ticks: {
              color: "#94a3b8",
              font: { size: 10 },
              precision: 0,
            },
            suggestedMax: maxValue ? Math.ceil(maxValue * 1.15) : 4,
          },
        },
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label: (context: { parsed: { y: number } }) =>
                `${tr("Orders", "Заказы")}: ${context.parsed.y}`,
            },
          },
        },
      },
    };
  }, [accountPopularity, tr]);

  const totalRevenue = useMemo(() => {
    return ordersInRange.reduce((sum, order) => {
      if (typeof order.price === "number") return sum + order.price;
      if (typeof order.amount === "number") return sum + order.amount;
      return sum;
    }, 0);
  }, [ordersInRange]);

  const totalRentalHours = useMemo(() => {
    const minutes = ordersInRange.reduce((sum, order) => sum + (order.rental_minutes || 0), 0);
    return minutes / 60;
  }, [ordersInRange]);

  const averageOrdersPerDay = useMemo(() => {
    if (!ordersInRange.length) return 0;
    if (range === "all") {
      const dates = ordersInRange
        .map((order) => order.created_at)
        .filter(Boolean)
        .map((value) => new Date(value as string))
        .filter((dt) => !Number.isNaN(dt.getTime()));
      if (!dates.length) return 0;
      const min = Math.min(...dates.map((dt) => dt.getTime()));
      const max = Math.max(...dates.map((dt) => dt.getTime()));
      const days = Math.max(1, Math.ceil((max - min) / (1000 * 60 * 60 * 24)) + 1);
      return ordersInRange.length / days;
    }
    const days = range === "7d" ? 7 : range === "90d" ? 90 : 30;
    return ordersInRange.length / days;
  }, [ordersInRange, range]);

  const mostPopularBuyer = buyers[0]?.name || tr("No data", "Нет данных");
  const topBuyerOrders = buyers[0]?.orders ?? 0;
  const topAccount = accountPopularity[0];
  const revenuePerOrder = ordersInRange.length ? totalRevenue / ordersInRange.length : 0;
  const repeatBuyersRate = totalBuyers ? ((ordersInRange.length - totalBuyers) / totalBuyers) * 100 : 0;

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
    {
      label: tr("Revenue", "Выручка"),
      value: totalRevenue ? formatCurrency(totalRevenue) : "-",
      icon: <CardBarsIcon />,
    },
    {
      label: tr("Rental hours", "Часы аренды"),
      value: totalRentalHours ? formatHoursLabel(totalRentalHours) : "-",
      icon: <CardCloudCheckIcon />,
    },
    {
      label: tr("Orders per day", "Заказов в день"),
      value: averageOrdersPerDay ? averageOrdersPerDay.toFixed(1) : "-",
      icon: <CardBarsIcon />,
    },
  ];

  const marketCurrency = useMemo(() => {
    const item = marketHistory.find((entry) => entry.currency);
    return item?.currency || "₽";
  }, [marketHistory]);

  const marketHistoryChart = useMemo(() => {
    const items = [...marketHistory];
    items.sort((a, b) => {
      const ta = Date.parse(String(a.created_at || ""));
      const tb = Date.parse(String(b.created_at || ""));
      if (Number.isNaN(ta) && Number.isNaN(tb)) return 0;
      if (Number.isNaN(ta)) return 1;
      if (Number.isNaN(tb)) return -1;
      return ta - tb;
    });
    return items.map((item, index) => {
      const ts = Date.parse(String(item.created_at || ""));
      const label = Number.isNaN(ts)
        ? String(item.created_at || index + 1)
        : new Date(ts).toLocaleDateString(undefined, { month: "short", day: "numeric" });
      return {
        label,
        avg: typeof item.avg_price === "number" ? item.avg_price : null,
        median: typeof item.median_price === "number" ? item.median_price : null,
        recommended: typeof item.recommended_price === "number" ? item.recommended_price : null,
      };
    });
  }, [marketHistory]);

  const marketHistoryLine = useMemo(() => {
    const labels = marketHistoryChart.map((item) => item.label);
    const avg = marketHistoryChart.map((item) => item.avg ?? null);
    const median = marketHistoryChart.map((item) => item.median ?? null);
    const recommended = marketHistoryChart.map((item) => item.recommended ?? null);
    return {
      data: {
        labels,
        datasets: [
          {
            label: tr("Average", "Средняя"),
            data: avg,
            borderColor: "rgba(34, 197, 94, 0.95)",
            backgroundColor: (context: { chart: { ctx: CanvasRenderingContext2D; chartArea?: { top: number; bottom: number } } }) => {
              const { chart } = context;
              const { ctx, chartArea } = chart;
              if (!chartArea) return "rgba(34, 197, 94, 0.18)";
              const gradient = ctx.createLinearGradient(0, chartArea.top, 0, chartArea.bottom);
              gradient.addColorStop(0, "rgba(34, 197, 94, 0.35)");
              gradient.addColorStop(1, "rgba(34, 197, 94, 0.04)");
              return gradient;
            },
            fill: true,
            tension: 0.35,
            pointRadius: 0,
            borderWidth: 2,
            spanGaps: true,
          },
          {
            label: tr("Median", "Медиана"),
            data: median,
            borderColor: "rgba(15, 23, 42, 0.9)",
            backgroundColor: "rgba(15, 23, 42, 0)",
            fill: false,
            tension: 0.35,
            pointRadius: 0,
            borderWidth: 2,
            spanGaps: true,
          },
          {
            label: tr("Recommended", "Рекомендованная"),
            data: recommended,
            borderColor: "rgba(249, 115, 22, 0.9)",
            backgroundColor: "rgba(249, 115, 22, 0)",
            fill: false,
            tension: 0.35,
            pointRadius: 0,
            borderWidth: 2,
            spanGaps: true,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { intersect: false, mode: "index" as const },
        scales: {
          x: {
            grid: { display: false },
            ticks: { color: "#94a3b8", font: { size: 10 }, maxRotation: 0, autoSkip: true, maxTicksLimit: 8 },
          },
          y: {
            beginAtZero: true,
            grid: { color: "rgba(148, 163, 184, 0.2)" },
            ticks: {
              color: "#94a3b8",
              font: { size: 10 },
              callback: (value: number | string) =>
                typeof value === "number" ? `${value.toLocaleString("ru-RU")} ${marketCurrency}` : value,
            },
          },
        },
        plugins: {
          legend: { display: true, labels: { color: "#94a3b8", font: { size: 10 } } },
          tooltip: {
            callbacks: {
              label: (context: { dataset: { label?: string }; parsed: { y: number } }) =>
                `${context.dataset.label ?? ""}: ${context.parsed.y.toLocaleString("ru-RU")} ${marketCurrency}`,
            },
          },
        },
      },
    };
  }, [marketHistoryChart, marketCurrency, tr]);

  const ordersByDayChart = useMemo(() => {
    const labels = dailyOverview.map((item) => item.label);
    const dates = dailyOverview.map((item) => item.key);
    const values = dailyOverview.map((item) => item.orders);
    const maxValue = values.length ? Math.max(...values) : 0;
    return {
      data: {
        labels,
        datasets: [
          {
            data: values,
            borderColor: "rgba(34, 197, 94, 0.95)",
            backgroundColor: (context: { chart: { ctx: CanvasRenderingContext2D; chartArea?: { top: number; bottom: number } } }) => {
              const { chart } = context;
              const { ctx, chartArea } = chart;
              if (!chartArea) return "rgba(34, 197, 94, 0.18)";
              const gradient = ctx.createLinearGradient(0, chartArea.top, 0, chartArea.bottom);
              gradient.addColorStop(0, "rgba(34, 197, 94, 0.45)");
              gradient.addColorStop(1, "rgba(34, 197, 94, 0.04)");
              return gradient;
            },
            fill: true,
            tension: 0.35,
            pointRadius: 0,
            borderWidth: 2,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { intersect: false, mode: "index" as const },
        scales: {
          x: {
            grid: { display: false },
            ticks: {
              color: "#94a3b8",
              font: { size: 10 },
              maxRotation: 0,
              autoSkip: true,
              maxTicksLimit: 10,
            },
          },
          y: {
            beginAtZero: true,
            grid: { color: "rgba(148, 163, 184, 0.2)" },
            ticks: { color: "#94a3b8", font: { size: 10 }, precision: 0 },
            suggestedMax: maxValue ? Math.ceil(maxValue * 1.2) : 4,
          },
        },
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              title: (items: { dataIndex: number }[]) => {
                const idx = items?.[0]?.dataIndex ?? 0;
                const value = dates[idx];
                const dt = new Date(value);
                return Number.isNaN(dt.getTime())
                  ? value
                  : dt.toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" });
              },
              label: (context: { parsed: { y: number } }) => `${tr("Orders", "Заказы")}: ${context.parsed.y}`,
            },
          },
        },
      },
    };
  }, [dailyOverview, tr]);

  const revenueFlowChart = useMemo(() => {
    const labels = dailyRevenue.map((item) => item.label);
    const values = dailyRevenue.map((item) => item.revenue);
    const maxValue = values.length ? Math.max(...values) : 0;
    return {
      data: {
        labels,
        datasets: [
          {
            data: values,
            borderColor: "rgba(16, 185, 129, 0.95)",
            backgroundColor: (context: { chart: { ctx: CanvasRenderingContext2D; chartArea?: { top: number; bottom: number } } }) => {
              const { chart } = context;
              const { ctx, chartArea } = chart;
              if (!chartArea) return "rgba(16, 185, 129, 0.18)";
              const gradient = ctx.createLinearGradient(0, chartArea.top, 0, chartArea.bottom);
              gradient.addColorStop(0, "rgba(16, 185, 129, 0.45)");
              gradient.addColorStop(1, "rgba(16, 185, 129, 0.04)");
              return gradient;
            },
            fill: true,
            tension: 0.35,
            pointRadius: 0,
            borderWidth: 2,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { intersect: false, mode: "index" as const },
        scales: {
          x: {
            grid: { display: false },
            ticks: {
              color: "#94a3b8",
              font: { size: 10 },
              maxRotation: 0,
              autoSkip: true,
              maxTicksLimit: 8,
            },
          },
          y: {
            beginAtZero: true,
            grid: { color: "rgba(148, 163, 184, 0.2)" },
            ticks: {
              color: "#94a3b8",
              font: { size: 10 },
              callback: (value: number | string) =>
                typeof value === "number" ? formatCurrency(value) : value,
            },
            suggestedMax: maxValue ? Math.ceil(maxValue * 1.2) : 4,
          },
        },
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label: (context: { parsed: { y: number } }) =>
                `${tr("Revenue", "Выручка")}: ${formatCurrency(context.parsed.y)}`,
            },
          },
        },
      },
    };
  }, [dailyRevenue, tr]);

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
        <div className="lg:col-span-2 rounded-2xl border border-neutral-200 bg-white p-5 shadow-sm flex flex-col">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 className="text-lg font-semibold text-neutral-900">
                {tr("Orders by day", "Заказы по дням")}
              </h2>
              <p className="text-sm text-neutral-500">
                {tr("Peak hour: {hour}", "Пиковый час: {hour}", { hour: peakHour.label })}
              </p>
            </div>
            <span className="rounded-full bg-neutral-100 px-3 py-1 text-xs font-semibold text-neutral-600">
              {rangeLabel}
            </span>
          </div>
          <div className="mt-4 flex-1 min-h-[240px] w-full">
            <ChartLine data={ordersByDayChart.data} options={ordersByDayChart.options} />
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
            <div className="flex items-center justify-between">
              <span>{tr("Revenue per order", "Выручка на заказ")}</span>
              <span className="font-semibold text-neutral-900">
                {revenuePerOrder ? formatCurrency(revenuePerOrder) : "-"}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span>{tr("Repeat buyers", "Повторные покупатели")}</span>
              <span className="font-semibold text-neutral-900">
                {repeatBuyersRate ? `${repeatBuyersRate.toFixed(0)}%` : "-"}
              </span>
            </div>
          </div>
          <div className="mt-5 rounded-xl border border-neutral-100 bg-neutral-50 p-4">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div>
                <p className="text-xs uppercase tracking-wide text-neutral-400">
                  {tr("Refund rate", "Доля возвратов")}
                </p>
                <p className="mt-1 text-2xl font-semibold text-neutral-900">
                  {refundStats.refundRate ? `${refundStats.refundRate.toFixed(1)}%` : "0%"}
                </p>
                <p className="text-xs text-neutral-500">
                  {refundStats.refundedOrders} / {refundStats.totalOrders} {tr("orders", "заказов")}
                </p>
                <p className="mt-2 text-xs font-semibold text-rose-600">
                  {tr("Refund loss", "Потери на возвратах")}:
                  <span className="ml-1 text-neutral-800">
                    {refundStats.refundsLoss ? formatCurrency(refundStats.refundsLoss) : "-"}
                  </span>
                </p>
              </div>
              <div className="min-w-[180px] text-right text-xs text-neutral-500">
                <div className="inline-flex items-center gap-2 rounded-full bg-rose-50 px-2.5 py-1 text-rose-700">
                  <span className="h-2.5 w-2.5 rounded-full bg-rose-500" />
                  {tr("Refunded", "Возвраты")}: {refundStats.refundedOrders}
                </div>
                <div className="mt-2 inline-flex items-center gap-2 rounded-full bg-emerald-50 px-2.5 py-1 text-emerald-700">
                  <span className="h-2.5 w-2.5 rounded-full bg-emerald-500" />
                  {tr("Kept", "Без возврата")}: {Math.max(refundStats.totalOrders - refundStats.refundedOrders, 0)}
                </div>
              </div>
            </div>
            <div className="mt-4 flex flex-wrap items-center gap-4">
              <div className="relative h-24 w-24 shrink-0">
                <div
                  className="absolute inset-0 rounded-full"
                  style={{
                    background: `conic-gradient(#ef4444 0% ${refundPercent}%, #10b981 ${refundPercent}% 100%)`,
                  }}
                />
                <div className="absolute inset-1.5 rounded-full bg-neutral-50" />
                <div className="absolute inset-0 flex flex-col items-center justify-center text-xs text-neutral-500">
                  <span className="text-lg font-semibold text-neutral-900">
                    {refundPercent.toFixed(1)}%
                  </span>
                  <span>{tr("Refunds", "Возвраты")}</span>
                </div>
              </div>
              <div className="flex-1 space-y-2 text-xs text-neutral-500">
                <div className="flex items-center justify-between gap-3">
                  <div className="inline-flex items-center gap-2 rounded-full bg-rose-50 px-2.5 py-1 text-rose-700">
                    <span className="h-2.5 w-2.5 rounded-full bg-rose-500" />
                    {tr("Refunded", "Возвраты")}
                  </div>
                  <span className="font-semibold text-neutral-700">
                    {refundStats.refundedOrders} ({refundPercent.toFixed(1)}%)
                  </span>
                </div>
                <div className="flex items-center justify-between gap-3">
                  <div className="inline-flex items-center gap-2 rounded-full bg-emerald-50 px-2.5 py-1 text-emerald-700">
                    <span className="h-2.5 w-2.5 rounded-full bg-emerald-500" />
                    {tr("Kept", "Без возврата")}
                  </div>
                  <span className="font-semibold text-neutral-700">
                    {Math.max(refundStats.totalOrders - refundStats.refundedOrders, 0)} ({keptPercent.toFixed(1)}%)
                  </span>
                </div>
              </div>
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
          <div className="mt-4 rounded-xl bg-neutral-50 p-4">
            <p className="text-xs uppercase tracking-wide text-neutral-400">
              {tr("Top account", "Топ аккаунт")}
            </p>
            <p className="mt-2 text-lg font-semibold text-neutral-900">
              {topAccount?.name ?? tr("No data", "Нет данных")}
            </p>
            <p className="text-xs text-neutral-500">
              {topAccount
                ? tr("{count} orders in period", "{count} заказов за период", { count: topAccount.orders })
                : tr("No account data for the selected range.", "Нет данных по аккаунтам за выбранный период.")}
            </p>
          </div>
        </div>
      </div>

      <div className="rounded-2xl border border-neutral-200 bg-white p-5 shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold text-neutral-900">
              {tr("Rentals heatmap", "Тепловая карта аренд")}
            </h2>
            <p className="text-sm text-neutral-500">
              {tr(
                "Orders grouped by hour and day of week.",
                "Заказы, сгруппированные по часу и дню недели.",
              )}
            </p>
          </div>
          <span className="rounded-full bg-neutral-100 px-3 py-1 text-xs font-semibold text-neutral-600">
            {rangeLabel}
          </span>
        </div>
        {heatmapError ? (
          <div className="mt-4 rounded-xl border border-rose-100 bg-rose-50 px-4 py-3 text-sm text-rose-600">
            {heatmapError}
          </div>
        ) : null}
        {heatmapLoading ? (
          <div className="mt-6 text-sm text-neutral-500">{tr("Loading...", "Загрузка...")}</div>
        ) : (
          <div className="mt-4 overflow-x-auto">
            <div className="min-w-[760px] space-y-2">
              <div
                className="grid items-center gap-1 text-[10px] text-neutral-400"
                style={{ gridTemplateColumns: "60px repeat(24, minmax(18px, 1fr))" }}
              >
                <div />
                {Array.from({ length: 24 }, (_, hour) => (
                  <div key={`h-${hour}`} className="text-center">
                    {hour % 2 === 0 ? String(hour).padStart(2, "0") : ""}
                  </div>
                ))}
              </div>
              {heatmapMatrix.grid.map((row, dayIdx) => (
                <div
                  key={`day-${dayIdx}`}
                  className="grid items-center gap-1"
                  style={{ gridTemplateColumns: "60px repeat(24, minmax(18px, 1fr))" }}
                >
                  <div className="text-xs font-semibold text-neutral-500">{heatmapDayLabels[dayIdx]}</div>
                  {row.map((count, hour) => {
                    const max = heatmapMatrix.max || 0;
                    const intensity = max > 0 ? count / max : 0;
                    const alpha = 0.08 + intensity * 0.82;
                    return (
                      <div
                        key={`cell-${dayIdx}-${hour}`}
                        title={`${heatmapDayLabels[dayIdx]} ${String(hour).padStart(2, "0")}:00 — ${count}`}
                        className="h-5 rounded-sm"
                        style={{
                          backgroundColor: `rgba(16, 185, 129, ${alpha})`,
                          border: "1px solid rgba(15, 23, 42, 0.06)",
                        }}
                      />
                    );
                  })}
                </div>
              ))}
              {!heatmapMatrix.max ? (
                <div className="text-xs text-neutral-400">{tr("No data for this range.", "Нет данных за период.")}</div>
              ) : null}
            </div>
          </div>
        )}
      </div>

      <div className="rounded-2xl border border-neutral-200 bg-white p-5 shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold text-neutral-900">
              {tr("Market price history", "История рыночных цен")}
            </h2>
            <p className="text-sm text-neutral-500">
              {tr(
                "Average, median, and recommended price snapshots (auto-updated every 60 min).",
                "Средняя, медианная и рекомендованная цена (обновление каждые 60 минут).",
              )}
            </p>
            {marketHistoryUrl ? <p className="mt-1 text-xs text-neutral-400">{marketHistoryUrl}</p> : null}
          </div>
          <span className="rounded-full bg-neutral-100 px-3 py-1 text-xs font-semibold text-neutral-600">
            {rangeLabel}
          </span>
        </div>
        {marketHistoryError ? (
          <div className="mt-4 rounded-xl border border-rose-100 bg-rose-50 px-4 py-3 text-sm text-rose-600">
            {marketHistoryError}
          </div>
        ) : null}
        {marketHistoryLoading ? (
          <div className="mt-6 text-sm text-neutral-500">{tr("Loading...", "Загрузка...")}</div>
        ) : marketHistoryChart.length ? (
          <div className="mt-4 h-[260px] w-full">
            <ChartLine data={marketHistoryLine.data} options={marketHistoryLine.options} />
          </div>
        ) : (
          <div className="mt-6 rounded-xl bg-neutral-50 p-4 text-sm text-neutral-500">
            {tr("No market history yet.", "История рынка пока пуста.")}
          </div>
        )}
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <div className="lg:col-span-2 rounded-2xl border border-neutral-200 bg-white p-5 shadow-sm flex flex-col">
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

      <div className="grid gap-4 lg:grid-cols-3">
        <div className="lg:col-span-2 rounded-2xl border border-neutral-200 bg-white p-5 shadow-sm">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 className="text-lg font-semibold text-neutral-900">
                {tr("Revenue flow", "Динамика выручки")}
              </h2>
              <p className="text-sm text-neutral-500">
                {tr("Daily earnings and order volume.", "Ежедневная выручка и объем заказов.")}
              </p>
            </div>
            <span className="rounded-full bg-emerald-50 px-3 py-1 text-xs font-semibold text-emerald-700">
              {totalRevenue ? formatCurrency(totalRevenue) : tr("No revenue", "Нет выручки")}
            </span>
          </div>
          <div className="mt-4 flex-1 min-h-[240px] w-full">
            <ChartLine data={revenueFlowChart.data} options={revenueFlowChart.options} />
          </div>
        </div>
        <div className="rounded-2xl border border-neutral-200 bg-white p-5 shadow-sm">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 className="text-lg font-semibold text-neutral-900">
                {tr("Weekly revenue", "Выручка по неделям")}
              </h2>
              <p className="text-sm text-neutral-500">
                {tr("Aggregated weekly totals.", "Суммарно по неделям.")}
              </p>
            </div>
          </div>
          <div className="mt-6 h-[260px] w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={weeklyRevenue}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                <XAxis dataKey="label" tick={{ fill: "#6b7280", fontSize: 11 }} />
                <YAxis tick={{ fill: "#6b7280", fontSize: 11 }} />
                <Tooltip
                  formatter={(value: number) => [formatCurrency(value), tr("Revenue", "Выручка")]}
                />
                <Bar dataKey="revenue" fill="#6366f1" radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      <div className="rounded-2xl border border-neutral-200 bg-white p-4 shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-base font-semibold text-neutral-900">
              {tr("Account popularity", "Популярные аккаунты")}
            </h2>
            <p className="text-xs text-neutral-500">
              {tr("Top rented accounts by orders.", "Топ аккаунтов по количеству аренд.")}
            </p>
          </div>
          <span className="rounded-full bg-neutral-100 px-2.5 py-1 text-[11px] font-semibold text-neutral-600">
            {tr("{count} accounts", "{count} аккаунтов", { count: accountPopularity.length })}
          </span>
        </div>
        <div className="mt-4 grid gap-4 lg:grid-cols-[1.6fr,1fr] items-stretch">
          <div className="flex h-full min-h-[260px] w-full">
            <div className="flex-1">
              <ChartBar data={accountPopularityChart.data} options={accountPopularityChart.options} />
            </div>
          </div>
          <div className="grid h-full content-start gap-2.5 sm:grid-cols-2 lg:grid-cols-1">
            {accountPopularity.map((account) => (
              <div key={account.name} className="rounded-xl border border-neutral-100 bg-neutral-50 p-3">
                <p className="text-[13px] font-semibold text-neutral-900">{account.name}</p>
                <div className="mt-1.5 grid gap-1 text-[11px] text-neutral-500">
                  <div className="flex items-center justify-between">
                    <span>{tr("Orders", "Заказы")}</span>
                    <span className="font-semibold text-neutral-700">{account.orders}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span>{tr("Hours", "Часы")}</span>
                    <span className="font-semibold text-neutral-700">
                      {account.hours ? formatHoursLabel(account.hours) : "-"}
                    </span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span>{tr("Revenue", "Выручка")}</span>
                    <span className="font-semibold text-neutral-700">
                      {account.revenue ? formatCurrency(account.revenue) : "-"}
                    </span>
                  </div>
                </div>
              </div>
            ))}
            {!accountPopularity.length && (
              <div className="rounded-xl border border-neutral-100 bg-neutral-50 p-3 text-xs text-neutral-500">
                {tr("No account data for the selected range.", "Нет данных по аккаунтам за выбранный период.")}
              </div>
            )}
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
          {dailyOverview.slice(-4).map((day) => (
            <div key={day.key} className="rounded-xl border border-neutral-100 bg-neutral-50 p-4">
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
