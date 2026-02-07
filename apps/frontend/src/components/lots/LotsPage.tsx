import React, { useEffect, useMemo, useState } from "react";
import { api, AccountItem, LotItem, LotEditPreview } from "../../services/api";
import { useWorkspace } from "../../context/WorkspaceContext";

const LotsPage: React.FC = () => {
  const { selectedId: selectedWorkspaceId, workspaces } = useWorkspace();
  const [accounts, setAccounts] = useState<AccountItem[]>([]);
  const [lots, setLots] = useState<LotItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [status, setStatus] = useState<{ message: string; isError?: boolean } | null>(null);

  const [lotNumber, setLotNumber] = useState("");
  const [accountId, setAccountId] = useState("");
  const [lotUrl, setLotUrl] = useState("");
  const [syncingLot, setSyncingLot] = useState<number | null>(null);
  const [syncingAll, setSyncingAll] = useState(false);
  const [editingLot, setEditingLot] = useState<LotItem | null>(null);
  const [editPreview, setEditPreview] = useState<LotEditPreview | null>(null);
  const [editLoading, setEditLoading] = useState(false);
  const [editSaving, setEditSaving] = useState(false);
  const [editError, setEditError] = useState<string | null>(null);
  const [editPrice, setEditPrice] = useState("");
  const [editAmount, setEditAmount] = useState("");
  const [editActive, setEditActive] = useState(true);
  const [editOriginalActive, setEditOriginalActive] = useState<boolean | null>(null);
  const [editSummaryRu, setEditSummaryRu] = useState("");
  const [editSummaryEn, setEditSummaryEn] = useState("");
  const [editDescRu, setEditDescRu] = useState("");
  const [editDescEn, setEditDescEn] = useState("");
  const [editRawFields, setEditRawFields] = useState("");
  const [showAdvanced, setShowAdvanced] = useState(false);

  const hasFlag = (value?: number | string | null) => {
    if (value === null || value === undefined) return false;
    const parsed = Number(value);
    if (Number.isNaN(parsed)) return false;
    return parsed > 0;
  };

  const lotStatus = (account?: AccountItem | null) => {
    if (!account) return { label: "—", className: "bg-neutral-100 text-neutral-500" };
    const state = (account.state || "").toLowerCase();
    if (hasFlag(account.low_priority) || state.includes("low")) {
      return { label: "Низкий приоритет", className: "bg-rose-50 text-rose-600" };
    }
    if (hasFlag(account.account_frozen) || state.includes("frozen")) {
      return { label: "Заморожен", className: "bg-rose-50 text-rose-700" };
    }
    if (hasFlag(account.rental_frozen)) {
      return { label: "Заморожено", className: "bg-slate-100 text-slate-700" };
    }
    if ((account.owner || "").trim() || state.includes("rented")) {
      return { label: "В аренде", className: "bg-amber-50 text-amber-700" };
    }
    return { label: "Свободен", className: "bg-emerald-50 text-emerald-700" };
  };

  const accountStatusLabel = (account?: AccountItem | null) => {
    if (!account) return "Без статуса";
    const state = (account.state || "").toLowerCase();
    if (hasFlag(account.low_priority) || state.includes("low")) return "Низкий приоритет";
    if (hasFlag(account.account_frozen) || state.includes("frozen")) return "Заморожен";
    if (hasFlag(account.rental_frozen)) return "Аренда заморожена";
    if ((account.owner || "").trim() || state.includes("rented")) return "В аренде";
    return "Свободен";
  };

  const workspaceLabel = (account: AccountItem) => {
    const base = account.workspace_name || (account.workspace_id ? `ID ${account.workspace_id}` : null);
    if (!base) return "";
    return `Основное: ${base}`;
  };

  const lastRentedLabel = (account: AccountItem) => {
    const base =
      account.last_rented_workspace_name ||
      (account.last_rented_workspace_id ? `ID ${account.last_rented_workspace_id}` : null);
    if (!base) return "";
    return `Последнее: ${base}`;
  };

  const accountById = useMemo(() => new Map(accounts.map((acc) => [acc.id, acc])), [accounts]);

  const accountOptions = useMemo(
    () =>
      accounts.map((acc) => {
        const loginLabel = acc.login ? `Логин: ${acc.login}` : "";
        const details = [
          loginLabel,
          accountStatusLabel(acc),
          [workspaceLabel(acc), lastRentedLabel(acc)].filter(Boolean).join(", "),
        ]
          .filter(Boolean)
          .join(" | ");
        return { id: acc.id, label: `ID ${acc.id}${details ? ` | ${details}` : ""}` };
      }),
    [accounts],
  );

  const currentWorkspaceLabel = useMemo(() => {
    if (selectedWorkspaceId === "all") return "Выберите рабочее пространство";
    const match = workspaces.find((w) => w.id === selectedWorkspaceId);
    return match ? match.name : "Рабочее пространство";
  }, [selectedWorkspaceId, workspaces]);

  useEffect(() => {
    if (selectedWorkspaceId === "all") {
      setStatus({ message: "Выберите рабочее пространство, чтобы редактировать лоты.", isError: true });
      setAccounts([]);
      setLots([]);
      setLoading(false);
      return;
    }
    let mounted = true;
    setLoading(true);
    Promise.all([api.listAccounts(), api.listLots(selectedWorkspaceId as number)])
      .then(([accountsRes, lotsRes]) => {
        if (!mounted) return;
        setAccounts(accountsRes.items || []);
        setLots(lotsRes.items || []);
        setStatus(null);
      })
      .catch((err) => {
        if (!mounted) return;
        setStatus({ message: (err as { message?: string })?.message || "Не удалось загрузить лоты.", isError: true });
      })
      .finally(() => {
        if (!mounted) return;
        setLoading(false);
      });
    return () => {
      mounted = false;
    };
  }, [selectedWorkspaceId]);

  const handleCreate = async (event: React.FormEvent) => {
    event.preventDefault();
    if (selectedWorkspaceId === "all") return;
    const number = Number(lotNumber);
    const account = Number(accountId);
    if (!number || !account) {
      setStatus({ message: "Укажите номер лота и аккаунт.", isError: true });
      return;
    }
    try {
      const created = await api.createLot({
        workspace_id: selectedWorkspaceId as number,
        lot_number: number,
        account_id: account,
        ...(lotUrl.trim() ? { lot_url: lotUrl.trim() } : {}),
      });
      setLots((prev) => [created, ...prev.filter((item) => item.lot_number !== created.lot_number)]);
      setLotNumber("");
      setAccountId("");
      setLotUrl("");
      setStatus({ message: "Лот сохранён." });
    } catch (err) {
      setStatus({ message: (err as { message?: string })?.message || "Не удалось сохранить лот.", isError: true });
    }
  };

  const handleDelete = async (lotNum: number) => {
    if (selectedWorkspaceId === "all") return;
    try {
      await api.deleteLot(lotNum, selectedWorkspaceId as number);
      setLots((prev) => prev.filter((item) => item.lot_number !== lotNum));
    } catch (err) {
      setStatus({ message: (err as { message?: string })?.message || "Не удалось удалить лот.", isError: true });
    }
  };

  const handleSyncTitle = async (lotNum: number) => {
    if (selectedWorkspaceId === "all") return;
    setSyncingLot(lotNum);
    try {
      const result = await api.syncLotTitle(lotNum, selectedWorkspaceId as number);
      setStatus({ message: result.updated ? "Заголовок обновлён." : "Изменений нет." });
    } catch (err) {
      setStatus({ message: (err as { message?: string })?.message || "Не удалось синхронизировать заголовок.", isError: true });
    } finally {
      setSyncingLot(null);
    }
  };

  const handleSyncAllTitles = async () => {
    if (selectedWorkspaceId === "all") return;
    setSyncingAll(true);
    try {
      const result = await api.syncLotTitles(selectedWorkspaceId as number);
      setStatus({ message: `Синхронизация: обновлено ${result.updated}/${result.total}, ошибок ${result.failed}.` });
    } catch (err) {
      setStatus({ message: (err as { message?: string })?.message || "Не удалось синхронизировать заголовки.", isError: true });
    } finally {
      setSyncingAll(false);
    }
  };

  const resetEditState = () => {
    setEditPreview(null);
    setEditError(null);
    setEditPrice("");
    setEditAmount("");
    setEditActive(true);
    setEditOriginalActive(null);
    setEditSummaryRu("");
    setEditSummaryEn("");
    setEditDescRu("");
    setEditDescEn("");
    setEditRawFields("");
    setShowAdvanced(false);
  };

  const handleOpenEdit = async (lot: LotItem) => {
    if (selectedWorkspaceId === "all") return;
    setEditingLot(lot);
    resetEditState();
    setEditLoading(true);
    try {
      const snapshot = await api.getLotEditSnapshot(lot.lot_number, selectedWorkspaceId as number);
      setEditPrice(snapshot.price !== null && snapshot.price !== undefined ? String(snapshot.price) : "");
      setEditAmount(snapshot.amount !== null && snapshot.amount !== undefined ? String(snapshot.amount) : "");
      setEditActive(!!snapshot.active);
      setEditOriginalActive(!!snapshot.active);
      setEditSummaryRu(snapshot.summary_ru || "");
      setEditSummaryEn(snapshot.summary_en || "");
      setEditDescRu(snapshot.desc_ru || "");
      setEditDescEn(snapshot.desc_en || "");
      setEditRawFields(JSON.stringify(snapshot.raw_fields ?? {}, null, 2));
    } catch (err) {
      setEditError((err as { message?: string })?.message || "Не удалось загрузить лот.");
    } finally {
      setEditLoading(false);
    }
  };

  const parseRawFields = () => {
    const raw = editRawFields.trim();
    if (!raw) return null;
    let parsed: unknown;
    try {
      parsed = JSON.parse(raw);
    } catch (err) {
      throw new Error("Некорректный JSON в расширенных полях.");
    }
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
      throw new Error("Расширенные поля должны быть JSON-объектом.");
    }
    return parsed as Record<string, unknown>;
  };

  const buildEditPayload = () => {
    const priceValue = editPrice.trim();
    const amountValue = editAmount.trim();
    const priceNumber = priceValue ? Number(priceValue) : null;
    const amountNumber = amountValue ? Number(amountValue) : null;
    if (priceValue && Number.isNaN(priceNumber)) {
      throw new Error("Цена должна быть числом.");
    }
    if (amountValue && Number.isNaN(amountNumber)) {
      throw new Error("Количество должно быть числом.");
    }
    const activeChanged =
      editOriginalActive === null ? true : editActive !== editOriginalActive;
    const rawFields = parseRawFields();
    return {
      price: priceNumber,
      amount: amountNumber,
      active: activeChanged ? editActive : null,
      summary_ru: editSummaryRu,
      summary_en: editSummaryEn,
      desc_ru: editDescRu,
      desc_en: editDescEn,
      raw_fields: rawFields,
    };
  };

  const handlePreviewEdit = async () => {
    if (!editingLot) return;
    setEditError(null);
    try {
      const payload = buildEditPayload();
      const preview = await api.previewLotEdit(editingLot.lot_number, payload, selectedWorkspaceId as number);
      setEditPreview(preview);
    } catch (err) {
      setEditError((err as { message?: string })?.message || "Не удалось получить предпросмотр.");
    }
  };

  const handleSaveEdit = async () => {
    if (!editingLot) return;
    setEditError(null);
    setEditSaving(true);
    try {
      const payload = buildEditPayload();
      await api.saveLotEdit(editingLot.lot_number, payload, selectedWorkspaceId as number);
      setStatus({ message: "Лот обновлён." });
      setEditingLot(null);
      resetEditState();
    } catch (err) {
      setEditError((err as { message?: string })?.message || "Не удалось сохранить лот.");
    } finally {
      setEditSaving(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="rounded-2xl border border-neutral-200 bg-white p-6 shadow-sm shadow-neutral-200/70">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h3 className="text-lg font-semibold text-neutral-900">Привязка лотов</h3>
            <p className="text-sm text-neutral-500">Список лотов и синхронизация заголовков на FunPay.</p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <button className="rounded-lg border border-neutral-200 bg-white px-4 py-2 text-xs font-semibold text-neutral-600 hover:bg-neutral-100 disabled:opacity-60" type="button" onClick={handleSyncAllTitles} disabled={syncingAll || selectedWorkspaceId === "all" || lots.length === 0}>
              {syncingAll ? "Синхр. все..." : "Синхр. все заголовки"}
            </button>
            <div className="flex items-center gap-2 rounded-lg border border-neutral-200 bg-neutral-50 px-3 py-2 text-[11px] font-semibold text-neutral-600">
              <span className="uppercase tracking-wide text-neutral-500">Рабочее пространство</span>
              <span className="text-xs font-semibold text-neutral-700">{currentWorkspaceLabel}</span>
            </div>
          </div>
        </div>

        {status ? <div className={`mt-4 rounded-xl border px-4 py-3 text-sm ${status.isError ? "border-red-200 bg-red-50 text-red-700" : "border-emerald-200 bg-emerald-50 text-emerald-700"}`}>{status.message}</div> : null}

        <form className="mt-5 grid gap-4 lg:grid-cols-[140px_1fr_1fr_auto]" onSubmit={handleCreate}>
          <input className="rounded-lg border border-neutral-200 bg-white px-3 py-3 text-sm" type="number" min={1} value={lotNumber} onChange={(e) => setLotNumber(e.target.value)} placeholder="Номер лота" required />
          <select className="rounded-lg border border-neutral-200 bg-white px-3 py-3 text-sm" value={accountId} onChange={(e) => setAccountId(e.target.value)} required>
            <option value="">Выберите аккаунт</option>
            {accountOptions.map((item) => (
              <option key={item.id} value={item.id}>{item.label}</option>
            ))}
          </select>
          <input className="rounded-lg border border-neutral-200 bg-white px-3 py-3 text-sm" type="url" value={lotUrl} onChange={(e) => setLotUrl(e.target.value)} placeholder="Оставьте пустым для автозаполнения по номеру" />
          <p className="text-xs text-neutral-500">Если ссылку не указать, она создастся автоматически: https://funpay.com/lots/offer?id=НОМЕР.</p>
          <button className="rounded-lg bg-neutral-900 px-4 py-3 text-sm font-semibold text-white hover:bg-neutral-800" type="submit">Сохранить</button>
        </form>

        <div className="mt-6 overflow-x-auto">
          <table className="min-w-[640px] w-full border-separate border-spacing-y-2 text-sm">
            <thead className="text-xs uppercase tracking-wide text-neutral-500">
              <tr>
                <th className="px-3 py-2 text-left">Лот</th>
                <th className="px-3 py-2 text-left">Аккаунт</th>
                <th className="px-3 py-2 text-left">Статус</th>
                <th className="px-3 py-2 text-left">Ссылка</th>
                <th className="px-3 py-2 text-left">Действия</th>
              </tr>
            </thead>
            <tbody>
              {lots.length ? lots.map((lot) => {
                const account = accountById.get(lot.account_id);
                const statusInfo = lotStatus(account ?? null);
                return (
                  <tr key={lot.lot_number} className="bg-neutral-50">
                    <td className="rounded-l-xl px-3 py-3 font-semibold text-neutral-900">#{lot.lot_number}</td>
                    <td className="px-3 py-3 text-neutral-700">{lot.account_name ?? "-"} (ID {lot.account_id})</td>
                    <td className="px-3 py-3"><span className={`inline-flex rounded-full px-3 py-1 text-xs font-semibold ${statusInfo.className}`}>{statusInfo.label}</span></td>
                    <td className="px-3 py-3">{lot.lot_url ? <a className="text-emerald-600 hover:underline" href={lot.lot_url} target="_blank" rel="noreferrer">{lot.lot_url}</a> : "-"}</td>
                    <td className="rounded-r-xl px-3 py-3 text-right">
                      <div className="flex items-center justify-end gap-2">
                        <button className="rounded-lg border border-neutral-200 px-3 py-2 text-xs font-semibold text-neutral-600 hover:bg-neutral-100" type="button" onClick={() => handleOpenEdit(lot)}>Редактировать</button>
                        <button className="rounded-lg border border-neutral-200 px-3 py-2 text-xs font-semibold text-neutral-600 hover:bg-neutral-100 disabled:opacity-60" type="button" onClick={() => handleSyncTitle(lot.lot_number)} disabled={syncingLot === lot.lot_number}>{syncingLot === lot.lot_number ? "Синхр..." : "Синхр. заголовок"}</button>
                        <button className="rounded-lg border border-neutral-200 px-3 py-2 text-xs font-semibold text-neutral-600 hover:bg-neutral-100" type="button" onClick={() => handleDelete(lot.lot_number)}>Удалить</button>
                      </div>
                    </td>
                  </tr>
                );
              }) : (
                <tr><td colSpan={5} className="rounded-xl border border-dashed border-neutral-200 bg-neutral-50 px-4 py-6 text-center text-sm text-neutral-500">{loading ? "Загружаем лоты..." : "Лоты ещё не настроены."}</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {editingLot && (
        <div className="fixed inset-0 z-50 flex items-center justify-center px-4 py-6">
          <div
            className="absolute inset-0 bg-neutral-900/40"
            onClick={() => {
              if (!editSaving) {
                setEditingLot(null);
                resetEditState();
              }
            }}
          />
          <div className="relative z-10 w-full max-w-3xl rounded-2xl border border-neutral-200 bg-white p-6 shadow-xl">
            <div className="flex items-start justify-between gap-4">
              <div>
                <h3 className="text-lg font-semibold text-neutral-900">
                  Редактирование лота #{editingLot.lot_number}
                </h3>
                <p className="text-sm text-neutral-500">
                  Изменения применяются к FunPay через offerSave. Активные лоты будут повторно активированы.
                </p>
              </div>
              <button
                type="button"
                className="rounded-lg border border-neutral-200 px-3 py-1 text-xs font-semibold text-neutral-600 hover:bg-neutral-100"
                onClick={() => {
                  if (!editSaving) {
                    setEditingLot(null);
                    resetEditState();
                  }
                }}
              >
                Закрыть
              </button>
            </div>

            {editError ? (
              <div className="mt-4 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
                {editError}
              </div>
            ) : null}

            {editLoading ? (
              <div className="mt-6 text-sm text-neutral-500">Загрузка лота...</div>
            ) : (
              <div className="mt-5 grid gap-4">
                <div className="grid gap-4 md:grid-cols-3">
                  <div className="space-y-2">
                    <label className="text-xs font-semibold uppercase tracking-wide text-neutral-500">Цена</label>
                    <input
                      type="number"
                      step="0.01"
                      className="w-full rounded-lg border border-neutral-200 bg-white px-3 py-2 text-sm text-neutral-900 outline-none focus:border-neutral-400"
                      value={editPrice}
                      onChange={(e) => setEditPrice(e.target.value)}
                    />
                  </div>
                  <div className="space-y-2">
                    <label className="text-xs font-semibold uppercase tracking-wide text-neutral-500">Количество</label>
                    <input
                      type="number"
                      min={1}
                      className="w-full rounded-lg border border-neutral-200 bg-white px-3 py-2 text-sm text-neutral-900 outline-none focus:border-neutral-400"
                      value={editAmount}
                      onChange={(e) => setEditAmount(e.target.value)}
                    />
                  </div>
                  <div className="flex items-center gap-2 pt-6">
                    <input
                      id="lot-active"
                      type="checkbox"
                      checked={editActive}
                      onChange={(e) => setEditActive(e.target.checked)}
                    />
                    <label htmlFor="lot-active" className="text-sm font-semibold text-neutral-700">
                      Лот активен
                    </label>
                  </div>
                </div>

                <div className="grid gap-4 md:grid-cols-2">
                  <div className="space-y-2">
                    <label className="text-xs font-semibold uppercase tracking-wide text-neutral-500">
                      Заголовок RU
                    </label>
                    <input
                      className="w-full rounded-lg border border-neutral-200 bg-white px-3 py-2 text-sm text-neutral-900 outline-none focus:border-neutral-400"
                      value={editSummaryRu}
                      onChange={(e) => setEditSummaryRu(e.target.value)}
                    />
                  </div>
                  <div className="space-y-2">
                    <label className="text-xs font-semibold uppercase tracking-wide text-neutral-500">
                      Заголовок EN
                    </label>
                    <input
                      className="w-full rounded-lg border border-neutral-200 bg-white px-3 py-2 text-sm text-neutral-900 outline-none focus:border-neutral-400"
                      value={editSummaryEn}
                      onChange={(e) => setEditSummaryEn(e.target.value)}
                    />
                  </div>
                </div>

                <div className="grid gap-4 md:grid-cols-2">
                  <div className="space-y-2">
                    <label className="text-xs font-semibold uppercase tracking-wide text-neutral-500">
                      Описание RU
                    </label>
                    <textarea
                      className="min-h-[120px] w-full rounded-lg border border-neutral-200 bg-white px-3 py-2 text-sm text-neutral-900 outline-none focus:border-neutral-400"
                      value={editDescRu}
                      onChange={(e) => setEditDescRu(e.target.value)}
                    />
                  </div>
                  <div className="space-y-2">
                    <label className="text-xs font-semibold uppercase tracking-wide text-neutral-500">
                      Описание EN
                    </label>
                    <textarea
                      className="min-h-[120px] w-full rounded-lg border border-neutral-200 bg-white px-3 py-2 text-sm text-neutral-900 outline-none focus:border-neutral-400"
                      value={editDescEn}
                      onChange={(e) => setEditDescEn(e.target.value)}
                    />
                  </div>
                </div>

                <div className="rounded-xl border border-neutral-200 bg-neutral-50 p-4">
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <div className="text-sm font-semibold text-neutral-800">Все поля лота (JSON)</div>
                      <div className="text-xs text-neutral-500">
                        Полный набор полей формы FunPay. Редактируйте аккуратно.
                      </div>
                    </div>
                    <button
                      type="button"
                      onClick={() => setShowAdvanced((prev) => !prev)}
                      className="rounded-lg border border-neutral-200 px-3 py-1 text-xs font-semibold text-neutral-600 hover:bg-neutral-100"
                    >
                      {showAdvanced ? "Скрыть" : "Показать"}
                    </button>
                  </div>
                  {showAdvanced ? (
                    <textarea
                      className="mt-3 min-h-[180px] w-full rounded-lg border border-neutral-200 bg-white px-3 py-2 text-xs font-mono text-neutral-800 outline-none focus:border-neutral-400"
                      value={editRawFields}
                      onChange={(e) => setEditRawFields(e.target.value)}
                    />
                  ) : null}
                </div>

                <div className="rounded-xl border border-neutral-200 bg-neutral-50 p-4">
                  <div className="flex items-center justify-between gap-3">
                    <div className="text-sm font-semibold text-neutral-800">Предпросмотр изменений</div>
                    <button
                      type="button"
                      onClick={handlePreviewEdit}
                      className="rounded-lg border border-neutral-200 px-3 py-1 text-xs font-semibold text-neutral-600 hover:bg-neutral-100"
                    >
                      Предпросмотр
                    </button>
                  </div>
                  {editPreview ? (
                    <div className="mt-3 space-y-2 text-xs text-neutral-600">
                      {editPreview.changes.length ? (
                        editPreview.changes.map((change, idx) => (
                          <div key={`change-${idx}`} className="flex flex-wrap gap-2">
                            <span className="font-semibold">{change.field}:</span>
                            <span className="text-neutral-500">{String(change.from ?? "")}</span>
                            <span className="text-neutral-400">→</span>
                            <span className="text-neutral-900">{String(change.to ?? "")}</span>
                          </div>
                        ))
                      ) : (
                        <div>Изменений нет.</div>
                      )}
                    </div>
                  ) : (
                    <div className="mt-2 text-xs text-neutral-500">Нажмите «Предпросмотр».</div>
                  )}
                </div>

                <div className="flex flex-wrap gap-3">
                  <button
                    type="button"
                    onClick={handleSaveEdit}
                    disabled={editSaving}
                    className="rounded-lg bg-neutral-900 px-4 py-2 text-sm font-semibold text-white hover:bg-neutral-800 disabled:opacity-60"
                  >
                    {editSaving ? "Сохраняем..." : "Сохранить"}
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setEditingLot(null);
                      resetEditState();
                    }}
                    className="rounded-lg border border-neutral-200 px-4 py-2 text-sm font-semibold text-neutral-600 hover:bg-neutral-100"
                  >
                    Отмена
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default LotsPage;
