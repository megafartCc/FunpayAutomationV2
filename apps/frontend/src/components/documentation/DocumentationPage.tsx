import React from "react";

const quickSteps = [
  {
    title: "Создайте рабочее пространство",
    description: "Перейдите в Настройки → добавьте рабочее пространство и укажите платформу (FunPay / PlayerOk).",
  },
  {
    title: "Добавьте аккаунт",
    description: "Откройте “Добавить аккаунт” и сохраните Steam-аккаунт, который будете сдавать в аренду.",
  },
  {
    title: "Привяжите лот",
    description: "В разделе “Лоты” выберите рабочее пространство, укажите номер лота, аккаунт и ссылку на лот.",
  },
  {
    title: "Проверьте инвентарь",
    description: "В Инвентаре проверьте статус лота и убедитесь, что нужный аккаунт привязан.",
  },
];

const workspaceSteps = [
  "Откройте Настройки и добавьте рабочее пространство с названием, платформой и ключом.",
  "Выберите рабочее пространство в шапке, чтобы работать с его лотами и чатами.",
  "Если у вас несколько пространств, используйте переключатель, чтобы быстро менять контекст.",
];

const lotSteps = [
  "Откройте “Лоты” и выберите нужное рабочее пространство.",
  "Введите номер лота, выберите аккаунт и вставьте ссылку на лот.",
  "Сохраните — лот появится в списке и будет использоваться для команд вроде !сток.",
];

const multiMappingSteps = [
  "Создайте один Steam-аккаунт в “Добавить аккаунт” (он будет общим).",
  "Переключитесь на рабочее пространство A и создайте лот с этим аккаунтом и своей ссылкой.",
  "Переключитесь на рабочее пространство B и снова создайте лот с тем же аккаунтом, но другой ссылкой.",
  "Проверьте Инвентарь: один аккаунт будет показывать привязку к разным лотам по каждому workspace.",
];

const botFlow = [
  {
    title: "1. Подготовьте базу",
    description:
      "Сначала создайте рабочие пространства, добавьте аккаунты и привяжите лоты. Без лотов бот не сможет отдавать аккаунты.",
  },
  {
    title: "2. Следите за заказами",
    description:
      "В “Истории заказов” и “Чатах” отслеживайте новые покупки. Все ключевые действия бот ведёт по рабочему пространству.",
  },
  {
    title: "3. Используйте команды",
    description:
      "Проверяйте склад командой !сток, выдавайте замену через !лпзамена (с лимитом 1/час на покупателя).",
  },
  {
    title: "4. Проверяйте статус",
    description:
      "В Инвентаре виден статус привязки лота, а в Лотах — актуальные ссылки и номера.",
  },
];

const screenshotPlaceholders = [
  {
    title: "Лоты: создание привязки",
    description: "Покажите форму с номером лота, аккаунтом и ссылкой.",
  },
  {
    title: "Инвентарь: статус лота",
    description: "Покажите, что аккаунт отмечен как привязанный к лоту.",
  },
  {
    title: "Настройки: рабочие пространства",
    description: "Покажите список пространств и переключатель по умолчанию.",
  },
];

const DocumentationPage: React.FC = () => {
  return (
    <div className="space-y-8">
      <section className="rounded-2xl border border-neutral-200 bg-white p-6 shadow-sm shadow-neutral-200/70">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h2 className="text-2xl font-semibold text-neutral-900">Документация по работе с ботом</h2>
            <p className="mt-2 max-w-2xl text-sm text-neutral-500">
              Пошаговый гайд по настройке рабочих пространств, лотов и привязке Steam-аккаунтов. Используйте
              эту страницу как чек-лист при запуске новых магазинов.
            </p>
          </div>
          <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-xs font-semibold text-amber-700">
            Совет: после каждого шага проверяйте Инвентарь и Лоты, чтобы убедиться, что данные сохранены.
          </div>
        </div>
      </section>

      <section className="grid gap-4 lg:grid-cols-4">
        {quickSteps.map((step, index) => (
          <div
            key={step.title}
            className="rounded-2xl border border-neutral-200 bg-white p-5 shadow-sm shadow-neutral-200/60"
          >
            <div className="text-xs font-semibold uppercase tracking-wide text-neutral-400">Шаг {index + 1}</div>
            <div className="mt-2 text-base font-semibold text-neutral-900">{step.title}</div>
            <p className="mt-2 text-sm text-neutral-500">{step.description}</p>
          </div>
        ))}
      </section>

      <section className="grid gap-6 lg:grid-cols-2">
        <div className="rounded-2xl border border-neutral-200 bg-white p-6 shadow-sm shadow-neutral-200/60">
          <h3 className="text-lg font-semibold text-neutral-900">Рабочие пространства</h3>
          <p className="mt-2 text-sm text-neutral-500">
            Рабочее пространство = отдельный магазин/аккаунт FunPay. Все лоты, чаты и заказы привязаны к выбранному
            пространству.
          </p>
          <ul className="mt-4 space-y-3 text-sm text-neutral-600">
            {workspaceSteps.map((item) => (
              <li key={item} className="flex gap-3">
                <span className="mt-1 h-2 w-2 rounded-full bg-neutral-400" />
                <span>{item}</span>
              </li>
            ))}
          </ul>
        </div>

        <div className="rounded-2xl border border-neutral-200 bg-white p-6 shadow-sm shadow-neutral-200/60">
          <h3 className="text-lg font-semibold text-neutral-900">Лоты и привязка</h3>
          <p className="mt-2 text-sm text-neutral-500">
            Лот связывает номер лота, ссылку и конкретный Steam-аккаунт. Без привязки бот не знает, что выдавать.
          </p>
          <ol className="mt-4 space-y-3 text-sm text-neutral-600">
            {lotSteps.map((item, index) => (
              <li key={item} className="flex gap-3">
                <span className="mt-0.5 inline-flex h-6 w-6 items-center justify-center rounded-full border border-neutral-200 text-xs font-semibold text-neutral-600">
                  {index + 1}
                </span>
                <span>{item}</span>
              </li>
            ))}
          </ol>
        </div>
      </section>

      <section className="rounded-2xl border border-neutral-200 bg-white p-6 shadow-sm shadow-neutral-200/60">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h3 className="text-lg font-semibold text-neutral-900">Один Steam-аккаунт → несколько лотов</h3>
            <p className="mt-2 text-sm text-neutral-500">
              Чтобы один аккаунт использовался в разных рабочих пространствах или на разных лотах, создайте лоты
              отдельно для каждого workspace.
            </p>
          </div>
          <div className="rounded-xl border border-neutral-200 bg-neutral-50 px-3 py-2 text-xs font-semibold text-neutral-600">
            Важно: номер лота может повторяться в разных рабочих пространствах — это разные магазины.
          </div>
        </div>
        <ol className="mt-5 grid gap-3 text-sm text-neutral-600 lg:grid-cols-2">
          {multiMappingSteps.map((item, index) => (
            <li key={item} className="flex gap-3">
              <span className="mt-0.5 inline-flex h-6 w-6 items-center justify-center rounded-full border border-neutral-200 text-xs font-semibold text-neutral-600">
                {index + 1}
              </span>
              <span>{item}</span>
            </li>
          ))}
        </ol>
      </section>

      <section className="rounded-2xl border border-neutral-200 bg-white p-6 shadow-sm shadow-neutral-200/60">
        <h3 className="text-lg font-semibold text-neutral-900">Как работать с ботом: короткий сценарий</h3>
        <div className="mt-4 grid gap-4 lg:grid-cols-2">
          {botFlow.map((item) => (
            <div key={item.title} className="rounded-2xl border border-neutral-200 bg-neutral-50 p-4">
              <div className="text-sm font-semibold text-neutral-900">{item.title}</div>
              <p className="mt-2 text-sm text-neutral-600">{item.description}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="rounded-2xl border border-neutral-200 bg-white p-6 shadow-sm shadow-neutral-200/60">
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-semibold text-neutral-900">Скриншоты</h3>
          <span className="text-xs font-semibold uppercase tracking-wide text-neutral-400">Опционально</span>
        </div>
        <p className="mt-2 text-sm text-neutral-500">
          Добавьте сюда свои скриншоты интерфейса, чтобы новым операторам было проще ориентироваться.
        </p>
        <div className="mt-4 grid gap-4 lg:grid-cols-3">
          {screenshotPlaceholders.map((shot) => (
            <div
              key={shot.title}
              className="flex min-h-[160px] flex-col justify-between rounded-2xl border-2 border-dashed border-neutral-200 bg-neutral-50 p-4"
            >
              <div>
                <div className="text-sm font-semibold text-neutral-800">{shot.title}</div>
                <p className="mt-2 text-xs text-neutral-500">{shot.description}</p>
              </div>
              <span className="text-xs font-semibold text-neutral-400">Перетащите изображение сюда</span>
            </div>
          ))}
        </div>
      </section>

      <section className="rounded-2xl border border-neutral-200 bg-white p-6 shadow-sm shadow-neutral-200/60">
        <h3 className="text-lg font-semibold text-neutral-900">Частые вопросы</h3>
        <div className="mt-4 grid gap-4 lg:grid-cols-2">
          <div className="rounded-2xl border border-neutral-200 bg-neutral-50 p-4">
            <div className="text-sm font-semibold text-neutral-900">Почему лот не отображается в Инвентаре?</div>
            <p className="mt-2 text-sm text-neutral-600">
              Проверьте, что лот создан в нужном рабочем пространстве и выбран правильный аккаунт. Затем обновите
              Инвентарь.
            </p>
          </div>
          <div className="rounded-2xl border border-neutral-200 bg-neutral-50 p-4">
            <div className="text-sm font-semibold text-neutral-900">Можно ли использовать один лот везде?</div>
            <p className="mt-2 text-sm text-neutral-600">
              Лот принадлежит конкретному рабочему пространству. Для каждого магазина создавайте свою привязку, даже
              если используется тот же Steam-аккаунт.
            </p>
          </div>
        </div>
      </section>
    </div>
  );
};

export default DocumentationPage;
