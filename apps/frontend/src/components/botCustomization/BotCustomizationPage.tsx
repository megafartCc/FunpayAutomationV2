import React, { useCallback, useEffect, useMemo, useState } from "react";

import { useI18n } from "../../i18n/useI18n";
import { api, BotCustomizationSettings } from "../../services/api";

type BotCustomizationPageProps = {
  onToast?: (message: string, isError?: boolean) => void;
};

type CommandDef = { key: keyof BotCustomizationSettings["commands"]; label: string; desc: string };
type ResponseDef = { key: keyof BotCustomizationSettings["responses"]; label: string; desc: string; rows?: number };

const BotCustomizationPage: React.FC<BotCustomizationPageProps> = ({ onToast }) => {
  const { t, tr } = useI18n();

  const [settings, setSettings] = useState<BotCustomizationSettings | null>(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const workspaceName = useMemo(() => t("common.allWorkspaces"), [t]);

  const commandDefs: CommandDef[] = useMemo(
    () => [
      { key: "stock", label: tr("Stock list", "Свободные лоты"), desc: tr("Show available accounts", "Показать свободные аккаунты") },
      { key: "account", label: tr("Account data", "Данные аккаунта"), desc: tr("Send login + password", "Отправить логин и пароль") },
      { key: "code", label: tr("Steam Guard", "Steam Guard"), desc: tr("Send Steam Guard codes", "Отправить коды Steam Guard") },
      { key: "extend", label: tr("Extend rental", "Продлить аренду"), desc: tr("Add extra hours to rental", "Добавить часы к аренде") },
      { key: "pause", label: tr("Pause rental", "Пауза аренды"), desc: tr("Freeze rental for 1 hour", "Заморозить аренду на 1 час") },
      { key: "resume", label: tr("Resume rental", "Снять паузу"), desc: tr("Resume rental early", "Снять паузу раньше") },
      { key: "admin", label: tr("Call admin", "Вызвать продавца"), desc: tr("Notify seller/admin", "Позвать продавца") },
      { key: "replace", label: tr("Replace account", "Замена аккаунта"), desc: tr("Low priority replacement", "Замена LP аккаунта") },
      { key: "cancel", label: tr("Cancel rental", "Отмена аренды"), desc: tr("Cancel rental request", "Отменить аренду") },
      { key: "bonus", label: tr("Bonus hours", "Бонусные часы"), desc: tr("Apply bonus hours", "Применить бонусные часы") },
    ],
    [tr],
  );

  const responseDefs: ResponseDef[] = useMemo(
    () => [
      {
        key: "greeting",
        label: tr("Greeting", "Приветствие"),
        desc: tr("Used for hello / start of chat", "Ответ на приветствие"),
      },
      {
        key: "small_talk",
        label: tr("Small talk", "Небольшой разговор"),
        desc: tr("Reply to questions like “how are you?”", "Ответ на “как дела?”"),
      },
      {
        key: "refund",
        label: tr("Refund response", "Ответ про возвраты"),
        desc: tr("Shown when user asks for refund", "Используется при запросе возврата"),
        rows: 3,
      },
      {
        key: "unknown",
        label: tr("Clarify", "Уточнение"),
        desc: tr("If the request is unclear", "Если запрос неясен"),
      },
      {
        key: "commands_help",
        label: tr("Commands list", "Список команд"),
        desc: tr("Use {commands} placeholder", "Можно использовать {commands}"),
        rows: 3,
      },
      {
        key: "rent_flow",
        label: tr("How to rent", "Как арендовать"),
        desc: tr("Explain the rental flow", "Инструкция аренды"),
        rows: 4,
      },
      {
        key: "pre_rent",
        label: tr("Multiple accounts", "Несколько аккаунтов"),
        desc: tr("When user wants many accounts", "Когда хотят несколько аккаунтов"),
        rows: 4,
      },
    ],
    [tr],
  );

  const loadSettings = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.getBotCustomization(null);
      setSettings(res.settings);
    } catch (err) {
      const message =
        (err as { message?: string })?.message ||
        tr("Failed to load customization.", "Не удалось загрузить настройки.");
      onToast?.(message, true);
    } finally {
      setLoading(false);
    }
  }, [tr, onToast]);

  useEffect(() => {
    void loadSettings();
  }, [loadSettings]);

  const updateSettings = (updater: (current: BotCustomizationSettings) => BotCustomizationSettings) => {
    setSettings((prev) => (prev ? updater(prev) : prev));
  };

  const handleSave = async () => {
    if (!settings) return;
    setSaving(true);
    try {
      await api.saveBotCustomization(settings, null);
      onToast?.(tr("Customization saved.", "Настройки сохранены."));
      await loadSettings();
    } catch (err) {
      const message =
        (err as { message?: string })?.message ||
        tr("Failed to save customization.", "Не удалось сохранить настройки.");
      onToast?.(message, true);
    } finally {
      setSaving(false);
    }
  };

  const handleResetDefaults = async () => {
    setSaving(true);
    try {
      await api.deleteBotCustomization(null);
      onToast?.(tr("Defaults restored.", "Настройки по умолчанию восстановлены."));
      await loadSettings();
    } catch (err) {
      const message =
        (err as { message?: string })?.message ||
        tr("Failed to reset.", "Не удалось сбросить настройки.");
      onToast?.(message, true);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="rounded-2xl border border-neutral-200 bg-white p-6 shadow-sm shadow-neutral-200/70">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h3 className="text-lg font-semibold text-neutral-900">
              {tr("Bot customization", "Кастомизация бота")}
            </h3>
            <p className="text-sm text-neutral-500">
              {tr(
                "Tune commands, AI tone, review bonuses, and blacklist rules.",
                "Настройте команды, тон ИИ, бонусы за отзывы и правила чёрного списка.",
              )}
            </p>
          </div>
          <span className="rounded-full border border-neutral-200 bg-neutral-50 px-3 py-1 text-xs font-semibold text-neutral-600">
            {workspaceName}
          </span>
        </div>
      </div>

      {loading || !settings ? (
        <div className="rounded-2xl border border-dashed border-neutral-200 bg-neutral-50 px-6 py-8 text-center text-sm text-neutral-500">
          {tr("Loading customization...", "Загружаем настройки...")}
        </div>
      ) : (
        <>
          <div className="grid gap-6 lg:grid-cols-2">
            <div className="rounded-2xl border border-neutral-200 bg-white p-6 shadow-sm shadow-neutral-200/70">
              <div className="mb-4">
                <h4 className="text-sm font-semibold text-neutral-900">
                  {tr("AI behavior", "Поведение ИИ")}
                </h4>
                <p className="text-xs text-neutral-500">
                  {tr("Define tone and smart reply settings.", "Задайте тон и параметры умных ответов.")}
                </p>
              </div>
              <div className="space-y-4">
                <label className="flex items-center justify-between gap-3 rounded-xl border border-neutral-200 bg-neutral-50 px-4 py-3 text-sm">
                  <span>{tr("Enable AI replies", "Включить ответы ИИ")}</span>
                  <input
                    type="checkbox"
                    checked={settings.ai_enabled}
                    onChange={(event) =>
                      updateSettings((current) => ({ ...current, ai_enabled: event.target.checked }))
                    }
                  />
                </label>
                <div className="grid gap-3 md:grid-cols-2">
                  <div className="space-y-2">
                    <label className="text-[11px] font-semibold uppercase tracking-wide text-neutral-500">
                      {tr("Tone", "Тон")}
                    </label>
                    <select
                      value={settings.tone}
                      onChange={(event) =>
                        updateSettings((current) => ({ ...current, tone: event.target.value }))
                      }
                      className="w-full rounded-lg border border-neutral-200 bg-white px-3 py-2 text-sm text-neutral-700"
                    >
                      <option value="friendly">{tr("Friendly", "Дружелюбный")}</option>
                      <option value="professional">{tr("Professional", "Профессиональный")}</option>
                      <option value="playful">{tr("Playful", "Легкий")}</option>
                      <option value="concise">{tr("Concise", "Краткий")}</option>
                    </select>
                  </div>
                  <div className="space-y-2">
                    <label className="text-[11px] font-semibold uppercase tracking-wide text-neutral-500">
                      {tr("AI model (optional)", "Модель ИИ (необязательно)")}
                    </label>
                    <input
                      value={settings.ai?.model || ""}
                      onChange={(event) =>
                        updateSettings((current) => ({
                          ...current,
                          ai: { ...current.ai, model: event.target.value },
                        }))
                      }
                      placeholder="llama-3.1-70b-versatile"
                      className="w-full rounded-lg border border-neutral-200 bg-white px-3 py-2 text-sm text-neutral-700"
                    />
                  </div>
                </div>
                <div className="space-y-2">
                  <label className="text-[11px] font-semibold uppercase tracking-wide text-neutral-500">
                    {tr("Persona / brand voice", "Персона / стиль")}
                  </label>
                  <textarea
                    value={settings.persona || ""}
                    onChange={(event) =>
                      updateSettings((current) => ({ ...current, persona: event.target.value }))
                    }
                    rows={3}
                    placeholder={tr("e.g. Calm, confident, helpful.", "Например: спокойный, уверенный, заботливый.")}
                    className="w-full rounded-lg border border-neutral-200 bg-white px-3 py-2 text-sm text-neutral-700"
                  />
                </div>
              </div>
            </div>

            <div className="rounded-2xl border border-neutral-200 bg-white p-6 shadow-sm shadow-neutral-200/70">
              <div className="mb-4">
                <h4 className="text-sm font-semibold text-neutral-900">
                  {tr("Reviews & blacklist", "Отзывы и чёрный список")}
                </h4>
                <p className="text-xs text-neutral-500">
                  {tr("Control review bonuses and compensation rules.", "Настройте бонусы и компенсации.")}
                </p>
              </div>
              <div className="grid gap-4">
                <div className="grid gap-3 md:grid-cols-2">
                  <div className="space-y-2">
                    <label className="text-[11px] font-semibold uppercase tracking-wide text-neutral-500">
                      {tr("Review bonus (hours)", "Бонус за отзыв (часы)")}
                    </label>
                    <input
                      type="number"
                      min={0}
                      step={1}
                      value={settings.review_bonus_hours}
                      onChange={(event) =>
                        updateSettings((current) => ({
                          ...current,
                          review_bonus_hours: Math.max(0, Number(event.target.value)),
                        }))
                      }
                      className="w-full rounded-lg border border-neutral-200 bg-white px-3 py-2 text-sm text-neutral-700"
                    />
                  </div>
                  <div className="space-y-2">
                    <label className="text-[11px] font-semibold uppercase tracking-wide text-neutral-500">
                      {tr("Compensation threshold (hours)", "Порог компенсации (часы)")}
                    </label>
                    <input
                      type="number"
                      min={1}
                      step={1}
                      value={settings.blacklist.compensation_hours}
                      onChange={(event) =>
                        updateSettings((current) => ({
                          ...current,
                          blacklist: {
                            ...current.blacklist,
                            compensation_hours: Math.max(1, Number(event.target.value)),
                          },
                        }))
                      }
                      className="w-full rounded-lg border border-neutral-200 bg-white px-3 py-2 text-sm text-neutral-700"
                    />
                  </div>
                </div>
                <div className="space-y-2">
                  <label className="text-[11px] font-semibold uppercase tracking-wide text-neutral-500">
                    {tr("Minutes per unit", "Минут за единицу")}
                  </label>
                  <input
                    type="number"
                    min={30}
                    step={10}
                    value={settings.blacklist.unit_minutes}
                    onChange={(event) =>
                      updateSettings((current) => ({
                        ...current,
                        blacklist: {
                          ...current.blacklist,
                          unit_minutes: Math.max(10, Number(event.target.value)),
                        },
                      }))
                    }
                    className="w-full rounded-lg border border-neutral-200 bg-white px-3 py-2 text-sm text-neutral-700"
                  />
                  <p className="text-[11px] text-neutral-500">
                    {tr(
                      "Used to convert paid quantity into minutes.",
                      "Используется для пересчёта количества в минуты.",
                    )}
                  </p>
                </div>
                <div className="space-y-2">
                  <label className="text-[11px] font-semibold uppercase tracking-wide text-neutral-500">
                    {tr("Permanent blacklist message", "Сообщение для перманентного бана")}
                  </label>
                  <textarea
                    value={settings.blacklist.permanent_message}
                    onChange={(event) =>
                      updateSettings((current) => ({
                        ...current,
                        blacklist: { ...current.blacklist, permanent_message: event.target.value },
                      }))
                    }
                    rows={3}
                    className="w-full rounded-lg border border-neutral-200 bg-white px-3 py-2 text-sm text-neutral-700"
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-[11px] font-semibold uppercase tracking-wide text-neutral-500">
                    {tr("Compensation message", "Сообщение о компенсации")}
                  </label>
                  <textarea
                    value={settings.blacklist.blocked_message}
                    onChange={(event) =>
                      updateSettings((current) => ({
                        ...current,
                        blacklist: { ...current.blacklist, blocked_message: event.target.value },
                      }))
                    }
                    rows={4}
                    className="w-full rounded-lg border border-neutral-200 bg-white px-3 py-2 text-sm text-neutral-700"
                  />
                  <p className="text-[11px] text-neutral-500">
                    {tr(
                      "Placeholders: {penalty}, {paid}, {remaining}, {lot}",
                      "Плейсхолдеры: {penalty}, {paid}, {remaining}, {lot}",
                    )}
                  </p>
                </div>
              </div>
            </div>
          </div>

          <div className="rounded-2xl border border-neutral-200 bg-white p-6 shadow-sm shadow-neutral-200/70">
            <div className="mb-4">
              <h4 className="text-sm font-semibold text-neutral-900">
                {tr("Command triggers", "Команды и триггеры")}
              </h4>
              <p className="text-xs text-neutral-500">
                {tr("Separate multiple aliases with commas.", "Несколько алиасов разделяйте запятыми.")}
              </p>
            </div>
            <div className="grid gap-4 md:grid-cols-2">
              {commandDefs.map((command) => (
                <div key={command.key} className="rounded-xl border border-neutral-200 bg-neutral-50 p-4">
                  <div className="text-sm font-semibold text-neutral-900">{command.label}</div>
                  <p className="text-xs text-neutral-500">{command.desc}</p>
                  <input
                    value={settings.commands[command.key]}
                    onChange={(event) =>
                      updateSettings((current) => ({
                        ...current,
                        commands: { ...current.commands, [command.key]: event.target.value },
                      }))
                    }
                    placeholder="!command, !alias"
                    className="mt-3 w-full rounded-lg border border-neutral-200 bg-white px-3 py-2 text-sm text-neutral-700"
                  />
                </div>
              ))}
            </div>
          </div>

          <div className="rounded-2xl border border-neutral-200 bg-white p-6 shadow-sm shadow-neutral-200/70">
            <div className="mb-4">
              <h4 className="text-sm font-semibold text-neutral-900">
                {tr("Response templates", "Шаблоны ответов")}
              </h4>
              <p className="text-xs text-neutral-500">
                {tr("The AI can reuse these templates when helpful.", "ИИ сможет опираться на эти ответы.")}
              </p>
            </div>
            <div className="grid gap-4 lg:grid-cols-2">
              {responseDefs.map((item) => (
                <div key={item.key} className="space-y-2 rounded-xl border border-neutral-200 bg-neutral-50 p-4">
                  <div className="text-sm font-semibold text-neutral-900">{item.label}</div>
                  <p className="text-xs text-neutral-500">{item.desc}</p>
                  <textarea
                    value={settings.responses[item.key] || ""}
                    onChange={(event) =>
                      updateSettings((current) => ({
                        ...current,
                        responses: { ...current.responses, [item.key]: event.target.value },
                      }))
                    }
                    rows={item.rows ?? 2}
                    className="w-full rounded-lg border border-neutral-200 bg-white px-3 py-2 text-sm text-neutral-700"
                  />
                </div>
              ))}
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <button
              type="button"
              onClick={handleSave}
              disabled={saving}
              className="rounded-lg bg-neutral-900 px-4 py-2 text-xs font-semibold text-white disabled:opacity-60"
            >
              {saving ? t("common.saving") : tr("Save customization", "Сохранить настройки")}
            </button>
            <button
              type="button"
              onClick={handleResetDefaults}
              disabled={saving}
              className="rounded-lg border border-neutral-200 px-4 py-2 text-xs font-semibold text-neutral-600 disabled:opacity-60"
            >
              {tr("Reset defaults", "Сбросить по умолчанию")}
            </button>
          </div>
        </>
      )}
    </div>
  );
};

export default BotCustomizationPage;
