import React, { useState } from "react";

type TemplateField = {
  id: string;
  label: string;
  helper: string;
  value: string;
  rows?: number;
};

const BotCustomizationPage: React.FC = () => {
  const [greetingEnabled, setGreetingEnabled] = useState(true);
  const [autoTipsEnabled, setAutoTipsEnabled] = useState(true);
  const [rateLimitEnabled, setRateLimitEnabled] = useState(true);
  const [replacementNoticeEnabled, setReplacementNoticeEnabled] = useState(true);
  const [adminHelpEnabled, setAdminHelpEnabled] = useState(true);

  const [templates, setTemplates] = useState<TemplateField[]>([
    {
      id: "greeting",
      label: "Greeting message",
      helper: "Sent when a buyer opens chat for the first time.",
      value: "Привет! Я бот поддержки. Напишите !акк для данных аккаунта или !код для Steam Guard.",
      rows: 3,
    },
    {
      id: "replacement-rate",
      label: "Replacement rate limit notice",
      helper: "Reply when the buyer exceeds replacement limits.",
      value: "Лимит: 1 замена в час. Если нужна дополнительная замена — напишите !админ.",
      rows: 2,
    },
    {
      id: "blacklist",
      label: "Blacklist warning",
      helper: "Shown when a buyer is blocked.",
      value: "Вы в черном списке. Для разблокировки обратитесь к администратору.",
      rows: 2,
    },
    {
      id: "permanent-blacklist",
      label: "Permanent blacklist warning",
      helper: "Shown when the buyer is permanently blocked.",
      value: "Вы в постоянном черном списке. Доступ заблокирован без компенсации.",
      rows: 2,
    },
    {
      id: "replacement-success",
      label: "Replacement success header",
      helper: "Header shown before new account details.",
      value: "✅ Замена выполнена. Новый аккаунт:",
      rows: 2,
    },
  ]);

  const updateTemplate = (id: string, value: string) => {
    setTemplates((prev) => prev.map((item) => (item.id === id ? { ...item, value } : item)));
  };

  return (
    <div className="space-y-6">
      <div className="rounded-2xl border border-neutral-200 bg-white p-6 shadow-sm shadow-neutral-200/70">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <h3 className="text-lg font-semibold text-neutral-900">Bot Customization</h3>
            <p className="text-sm text-neutral-500">
              Настройте ответы бота, лимиты и уведомления. Можно подготовить текст и включать/выключать блоки.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <button className="rounded-lg border border-neutral-200 bg-white px-4 py-2 text-xs font-semibold text-neutral-700">
              Preview
            </button>
            <button className="rounded-lg bg-neutral-900 px-4 py-2 text-xs font-semibold text-white">
              Save changes
            </button>
          </div>
        </div>
        <div className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {[
            { label: "Greeting", value: greetingEnabled, onChange: setGreetingEnabled },
            { label: "Auto tips", value: autoTipsEnabled, onChange: setAutoTipsEnabled },
            { label: "Rate limits", value: rateLimitEnabled, onChange: setRateLimitEnabled },
            { label: "Replacement notices", value: replacementNoticeEnabled, onChange: setReplacementNoticeEnabled },
            { label: "Admin help prompts", value: adminHelpEnabled, onChange: setAdminHelpEnabled },
          ].map((item) => (
            <label
              key={item.label}
              className="flex items-center justify-between gap-3 rounded-xl border border-neutral-200 bg-neutral-50 px-4 py-3 text-sm text-neutral-700"
            >
              <span className="font-semibold">{item.label}</span>
              <input
                type="checkbox"
                checked={item.value}
                onChange={(event) => item.onChange(event.target.checked)}
                className="h-4 w-4 rounded border-neutral-300 text-neutral-900"
              />
            </label>
          ))}
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-[1.2fr_0.8fr]">
        <div className="rounded-2xl border border-neutral-200 bg-white p-6 shadow-sm shadow-neutral-200/70">
          <div className="mb-4">
            <h4 className="text-base font-semibold text-neutral-900">Response templates</h4>
            <p className="text-xs text-neutral-500">Тексты можно адаптировать под ваш стиль общения.</p>
          </div>
          <div className="space-y-4">
            {templates.map((item) => (
              <div key={item.id} className="rounded-xl border border-neutral-200 bg-neutral-50 p-4">
                <div className="flex items-center justify-between">
                  <div className="text-sm font-semibold text-neutral-800">{item.label}</div>
                  <span className="text-[10px] uppercase tracking-wide text-neutral-400">Template</span>
                </div>
                <p className="mt-1 text-xs text-neutral-500">{item.helper}</p>
                <textarea
                  value={item.value}
                  onChange={(event) => updateTemplate(item.id, event.target.value)}
                  rows={item.rows ?? 3}
                  className="mt-3 w-full rounded-lg border border-neutral-200 bg-white px-3 py-2 text-sm text-neutral-700 outline-none"
                />
              </div>
            ))}
          </div>
        </div>

        <div className="space-y-6">
          <div className="rounded-2xl border border-neutral-200 bg-white p-6 shadow-sm shadow-neutral-200/70">
            <h4 className="text-base font-semibold text-neutral-900">Quick tips</h4>
            <ul className="mt-3 space-y-2 text-sm text-neutral-600">
              <li>• Добавьте в тексты команды, которые вы реально используете (!код, !акк, !админ).</li>
              <li>• Уточняйте лимиты: например, 1 замена в час на одного покупателя.</li>
              <li>• Используйте emoji в важных уведомлениях, чтобы выделить их в чате.</li>
              <li>• Для постоянного бана опишите причину и что делать дальше.</li>
            </ul>
          </div>

          <div className="rounded-2xl border border-neutral-200 bg-white p-6 shadow-sm shadow-neutral-200/70">
            <h4 className="text-base font-semibold text-neutral-900">Admin escalation</h4>
            <p className="mt-2 text-xs text-neutral-500">
              Что писать, если нужна ручная помощь администратора.
            </p>
            <textarea
              value="Если требуется ручная проверка или вторая замена — напишите !админ, мы подключимся."
              readOnly
              rows={4}
              className="mt-3 w-full rounded-lg border border-neutral-200 bg-neutral-50 px-3 py-2 text-sm text-neutral-600"
            />
            <button className="mt-3 w-full rounded-lg border border-neutral-200 bg-white px-4 py-2 text-sm font-semibold text-neutral-700">
              Copy text
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default BotCustomizationPage;
