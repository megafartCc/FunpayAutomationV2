import React, { useCallback, useEffect, useMemo, useState } from "react";

import { api, NotificationItem } from "../../services/api";
import { useWorkspace } from "../../context/WorkspaceContext";

type NotificationsPageProps = {
  onToast?: (message: string, isError?: boolean) => void;
};

const NOTIFICATIONS_GRID =
  "minmax(180px,1.3fr) minmax(120px,0.7fr) minmax(260px,1.6fr) minmax(180px,1fr) minmax(140px,0.9fr) minmax(160px,1fr) minmax(160px,0.9fr)";

const formatMoscowDateTime = (value?: string | number | null) => {
  if (value === null || value === undefined || value === "") return "-";
  const ts = Date.parse(String(value));
  if (Number.isNaN(ts)) return String(value);
  return new Date(ts).toLocaleString("ru-RU", { timeZone: "Europe/Moscow" });
};

const statusPill = (status?: string | null) => {
  const normalized = (status || "").toLowerCase();
  if (normalized === "ok" || normalized === "success") {
    return { label: "OK", className: "bg-emerald-50 text-emerald-700" };
  }
  if (normalized === "failed" || normalized === "error") {
    return { label: "Ошибка", className: "bg-rose-50 text-rose-700" };
  }
  if (normalized === "warning") {
    return { label: "Предупреждение", className: "bg-amber-50 text-amber-700" };
  }
  if (normalized === "info") {
    return { label: "Инфо", className: "bg-sky-50 text-sky-700" };
  }
  return { label: status || "-", className: "bg-neutral-100 text-neutral-600" };
};

const eventLabel = (eventType?: string | null) => {
  const normalized = (eventType || "").toLowerCase();
  if (normalized === "purchase") return "Покупка";
  if (normalized === "deauthorize") return "Деавторизация Steam";
  if (normalized === "rental_expired") return "Аренда истекла";
  if (normalized === "replacement") return "Замена";
  return eventType || "-";
};

const formatWorkspaceLabel = (
  workspaceId: number | null | undefined,
  workspaceName: string | null | undefined,
) => {
  if (!workspaceId) return "Глобально";
  if (workspaceName) return `${workspaceName} (ID ${workspaceId})`;
  return `Рабочее пространство ${workspaceId}`;
};

const NotificationsPage: React.FC<NotificationsPageProps> = ({ onToast }) => {
  const { selectedId: selectedWorkspaceId } = useWorkspace();
  const workspaceId = selectedWorkspaceId === "all" ? null : (selectedWorkspaceId as number);

  const [notifications, setNotifications] = useState<NotificationItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [eventFilter, setEventFilter] = useState("all");

  const loadNotifications = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.listNotifications(workspaceId ?? undefined, 300);
      setNotifications(res.items || []);
    } catch (err) {
      const message = (err as { message?: string })?.message || "Не удалось загрузить уведомления.";
      onToast?.(message, true);
    } finally {
      setLoading(false);
    }
  }, [workspaceId, onToast]);

  useEffect(() => {
    void loadNotifications();
  }, [loadNotifications]);

  const filteredNotifications = useMemo(() => {
    if (eventFilter === "all") return notifications;
    return notifications.filter((notification) => notification.event_type === eventFilter);
  }, [notifications, eventFilter]);

  const totalLabel = useMemo(
    () => `${filteredNotifications.length} событий`,
    [filteredNotifications.length],
  );

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h3 className="text-lg font-semibold text-neutral-900">Уведомления</h3>
          <p className="text-sm text-neutral-500">Покупки, деавторизация и истечение аренды в одном списке.</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <div className="flex items-center gap-2 rounded-lg border border-neutral-200 bg-neutral-50 px-3 py-2 text-xs text-neutral-600">
            <span className="font-semibold text-neutral-500">Фильтр</span>
            <select
              value={eventFilter}
              onChange={(event) => setEventFilter(event.target.value)}
              className="bg-transparent text-xs font-semibold text-neutral-700 outline-none"
            >
              <option value="all">Все события</option>
              <option value="purchase">Покупка</option>
              <option value="replacement">Замена</option>
              <option value="deauthorize">Деавторизация</option>
              <option value="rental_expired">Аренда истекла</option>
            </select>
          </div>
          <span className="rounded-full bg-neutral-100 px-3 py-1 text-xs font-semibold text-neutral-600">
            {totalLabel}
          </span>
          <button
            onClick={loadNotifications}
            className="rounded-lg border border-neutral-200 bg-neutral-50 px-3 py-2 text-xs text-neutral-600"
          >
            Обновить
          </button>
        </div>
      </div>
      <div className="rounded-2xl border border-neutral-200 bg-white p-6 shadow-sm shadow-neutral-200/70">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3 text-xs text-neutral-500">
          <span>{selectedWorkspaceId === "all" ? "Все рабочие пространства вместе." : "Фильтр по рабочему пространству."}</span>
          <span>Сначала новые события.</span>
        </div>
        <div className="overflow-x-auto">
          <div className="min-w-[980px]">
            <div
              className="grid gap-3 px-6 text-xs font-semibold text-neutral-500"
              style={{ gridTemplateColumns: NOTIFICATIONS_GRID }}
            >
              <span>Событие</span>
              <span>Статус</span>
              <span>Детали</span>
              <span>Аккаунт / Покупатель</span>
              <span>Заказ</span>
              <span>Дата</span>
              <span>Рабочее пространство</span>
            </div>
            <div className="mt-3 space-y-3 overflow-y-auto overflow-x-hidden pr-1" style={{ maxHeight: "640px" }}>
              {loading && (
                <div className="rounded-xl border border-dashed border-neutral-200 bg-neutral-50 px-4 py-6 text-center text-sm text-neutral-500">
                  Загружаем уведомления...
                </div>
              )}
              {!loading &&
                filteredNotifications.map((notification, idx) => {
                  const pill = statusPill(notification.status);
                  const details = notification.message || "-";
                  const accountLabel =
                    notification.account_name ||
                    (notification.account_id ? `Аккаунт ${notification.account_id}` : "-");
                  const ownerLabel = notification.owner || "-";
                  return (
                    <div
                      key={notification.id ?? idx}
                      className="grid items-center gap-3 rounded-xl border border-neutral-100 bg-neutral-50 px-6 py-4 text-sm shadow-[0_4px_18px_-14px_rgba(0,0,0,0.18)]"
                      style={{ gridTemplateColumns: NOTIFICATIONS_GRID }}
                    >
                      <div className="min-w-0">
                        <div className="truncate font-semibold text-neutral-900">{eventLabel(notification.event_type)}</div>
                        <div className="text-xs text-neutral-400">{notification.title}</div>
                      </div>
                      <span
                        className={`inline-flex w-fit justify-self-start rounded-full px-3 py-1 text-xs font-semibold ${pill.className}`}
                      >
                        {pill.label}
                      </span>
                      <span className="min-w-0 truncate text-xs text-neutral-600">{details}</span>
                      <div className="min-w-0">
                        <div className="truncate font-semibold text-neutral-800">{accountLabel}</div>
                        <div className="text-xs text-neutral-400">Покупатель: {ownerLabel}</div>
                      </div>
                      <span className="min-w-0 truncate font-mono text-xs text-neutral-700">
                        {notification.order_id || "-"}
                      </span>
                      <span className="min-w-0 truncate text-xs text-neutral-500">
                        {formatMoscowDateTime(notification.created_at)}
                      </span>
                      <span className="min-w-0 truncate text-xs text-neutral-600">
                        {formatWorkspaceLabel(notification.workspace_id, notification.workspace_name)}
                      </span>
                    </div>
                  );
                })}
              {!loading && filteredNotifications.length === 0 && (
                <div className="rounded-xl border border-dashed border-neutral-200 bg-neutral-50 px-4 py-6 text-center text-sm text-neutral-500">
                  Пока нет событий уведомлений.
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default NotificationsPage;
