import React, { useMemo, useState } from "react";
import { useI18n } from "../../i18n/useI18n";

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

const blankCard = (minHeight = 260) => (
  <div className="rounded-2xl border border-neutral-200 bg-white shadow-sm" style={{ minHeight }} />
);

const chartBarColor = (index: number) => {
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
  trend: string;
};

const formatHours = (hours: number) => `${hours.toFixed(1)}h`;

const FunpayStatsPage: React.FC = () => {
  const { tr } = useI18n();
  const [range, setRange] = useState<"7d" | "30d" | "90d" | "all">("30d");

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

  const hourlyActivity = useMemo<ActivityPoint[]>(
    () => [
      { label: "00:00", value: 6 },
      { label: "02:00", value: 4 },
      { label: "04:00", value: 3 },
      { label: "06:00", value: 5 },
      { label: "08:00", value: 12 },
      { label: "10:00", value: 18 },
      { label: "12:00", value: 21 },
      { label: "14:00", value: 19 },
      { label: "16:00", value: 24 },
      { label: "18:00", value: 22 },
      { label: "20:00", value: 15 },
      { label: "22:00", value: 9 },
    ],
    [],
  );

  const peakHour = useMemo(() => {
    return hourlyActivity.reduce((acc, point) => (point.value > acc.value ? point : acc), hourlyActivity[0]);
  }, [hourlyActivity]);

  const summary = useMemo(
    () => ({
      orders: 312,
      avgRentalHours: 6.4,
      mostPopularBuyer: "ShadowFox",
      topBuyerOrders: 42,
      completionRate: 92,
      avgResponseMins: 18,
      activeRentals: 38,
      totalBuyers: 127,
    }),
    [],
  );

  const buyers = useMemo<BuyerStat[]>(
    () => [
      { name: "ShadowFox", orders: 42, avgHours: 7.1, trend: "+8%" },
      { name: "NightRunner", orders: 35, avgHours: 6.3, trend: "+5%" },
      { name: "Valyria", orders: 28, avgHours: 5.9, trend: "+3%" },
      { name: "MetaRush", orders: 21, avgHours: 6.8, trend: "-2%" },
      { name: "EchoWind", orders: 19, avgHours: 5.7, trend: "+1%" },
    ],
    [],
  );

  const stats: Stat[] = [
    {
      label: tr("Total orders", "Всего заказов"),
      value: summary.orders,
      delta: "+14%",
      deltaTone: "up",
      icon: <CardBarsIcon />,
    },
    {
      label: tr("Active rentals", "Активные аренды"),
      value: summary.activeRentals,
      delta: "+6%",
      deltaTone: "up",
      icon: <CardUsersIcon />,
    },
    {
      label: tr("Average rental time", "Среднее время аренды"),
      value: formatHours(summary.avgRentalHours),
      delta: "+4%",
      deltaTone: "up",
      icon: <CardCloudCheckIcon />,
    },
    {
      label: tr("Most popular buyer", "Самый частый покупатель"),
      value: summary.mostPopularBuyer,
      delta: `${summary.topBuyerOrders} ${tr("orders", "заказов")}`,
      deltaTone: "up",
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
                  className={`w-7 rounded-full ${chartBarColor(index)}`}
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
              <span>{tr("Completion rate", "Доля выполненных")}</span>
              <span className="font-semibold text-neutral-900">{summary.completionRate}%</span>
            </div>
            <div className="flex items-center justify-between">
              <span>{tr("Average response", "Среднее время ответа")}</span>
              <span className="font-semibold text-neutral-900">{summary.avgResponseMins} мин</span>
            </div>
            <div className="flex items-center justify-between">
              <span>{tr("Total buyers", "Всего покупателей")}</span>
              <span className="font-semibold text-neutral-900">{summary.totalBuyers}</span>
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
            <p className="mt-2 text-lg font-semibold text-neutral-900">{summary.mostPopularBuyer}</p>
            <p className="text-xs text-neutral-500">
              {tr("{count} orders in period", "{count} заказов за период", { count: summary.topBuyerOrders })}
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
            <button className="rounded-lg border border-neutral-200 px-3 py-1 text-xs font-semibold text-neutral-600">
              {tr("Export", "Экспорт")}
            </button>
          </div>
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
                      {tr("Avg rental", "Средняя аренда")}: {formatHours(buyer.avgHours)}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <div className="text-right">
                    <p className="text-sm font-semibold text-neutral-900">
                      {buyer.orders} {tr("orders", "заказов")}
                    </p>
                    <p className="text-xs text-neutral-500">{tr("Trend", "Тренд")}: {buyer.trend}</p>
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
        </div>
        <div className="rounded-2xl border border-neutral-200 bg-white p-5 shadow-sm">
          <h2 className="text-lg font-semibold text-neutral-900">
            {tr("Activity insights", "Инсайты активности")}
          </h2>
          <div className="mt-4 space-y-4">
            <div className="rounded-xl bg-neutral-50 p-4">
              <p className="text-xs uppercase tracking-wide text-neutral-400">{tr("Highest demand", "Пик спроса")}</p>
              <p className="mt-1 text-sm font-semibold text-neutral-900">
                {tr("16:00 - 18:00", "16:00 - 18:00")}
              </p>
              <p className="text-xs text-neutral-500">
                {tr("Most rentals are booked in the late afternoon.", "Большинство аренд бронируется во второй половине дня.")}
              </p>
            </div>
            <div className="rounded-xl bg-neutral-50 p-4">
              <p className="text-xs uppercase tracking-wide text-neutral-400">{tr("Average order value", "Средний чек")}</p>
              <p className="mt-1 text-sm font-semibold text-neutral-900">1 250 ₽</p>
              <p className="text-xs text-neutral-500">
                {tr("Up 6% compared to previous period.", "Рост на 6% по сравнению с прошлым периодом.")}
              </p>
            </div>
            <div className="rounded-xl bg-neutral-50 p-4">
              <p className="text-xs uppercase tracking-wide text-neutral-400">{tr("Queue health", "Состояние очереди")}</p>
              <p className="mt-1 text-sm font-semibold text-neutral-900">
                {tr("Stable", "Стабильно")}
              </p>
              <p className="text-xs text-neutral-500">
                {tr("Average wait time is under 10 minutes.", "Среднее ожидание — менее 10 минут.")}
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
          <button className="rounded-lg border border-neutral-200 px-3 py-1 text-xs font-semibold text-neutral-600">
            {tr("Download report", "Скачать отчет")}
          </button>
        </div>
        <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {[
            { label: tr("Mon", "Пн"), orders: 48, avg: 6.2 },
            { label: tr("Tue", "Вт"), orders: 52, avg: 6.8 },
            { label: tr("Wed", "Ср"), orders: 45, avg: 6.1 },
            { label: tr("Thu", "Чт"), orders: 60, avg: 6.5 },
            { label: tr("Fri", "Пт"), orders: 71, avg: 7.2 },
            { label: tr("Sat", "Сб"), orders: 82, avg: 7.5 },
            { label: tr("Sun", "Вс"), orders: 54, avg: 6.4 },
            { label: tr("Today", "Сегодня"), orders: 28, avg: 5.9 },
          ].map((day) => (
            <div key={day.label} className="rounded-xl border border-neutral-100 bg-neutral-50 p-4">
              <p className="text-xs font-semibold uppercase text-neutral-400">{day.label}</p>
              <p className="mt-2 text-2xl font-semibold text-neutral-900">{day.orders}</p>
              <p className="text-xs text-neutral-500">
                {tr("Avg rental", "Средняя аренда")}: {formatHours(day.avg)}
              </p>
            </div>
          ))}
        </div>
      </div>

      {blankCard(120)}
    </div>
  );
};

export default FunpayStatsPage;
