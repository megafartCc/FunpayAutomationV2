import React, { useEffect, useMemo, useState } from "react";
import { api, AccountItem, FunPayLotDetails, LotItem } from "../../services/api";
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
  const [editingLot, setEditingLot] = useState<number | null>(null);
  const [displayName, setDisplayName] = useState("");
  const [syncingLot, setSyncingLot] = useState<number | null>(null);
  const [syncingAll, setSyncingAll] = useState(false);

  const [manualLotId, setManualLotId] = useState<number | null>(null);
  const [manualLot, setManualLot] = useState<FunPayLotDetails | null>(null);
  const [manualTitle, setManualTitle] = useState("");
  const [manualDescription, setManualDescription] = useState("");
  const [manualPrice, setManualPrice] = useState("");
  const [manualActive, setManualActive] = useState(true);
  const [manualLoading, setManualLoading] = useState(false);
  const [manualSaving, setManualSaving] = useState(false);
  const [manualAutoPricing, setManualAutoPricing] = useState(false);

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
        const details = [accountStatusLabel(acc), [workspaceLabel(acc), lastRentedLabel(acc)].filter(Boolean).join(", ")]
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
      setManualLotId(null);
      setManualLot(null);
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

  const openManualPanel = async (lotNum: number) => {
    if (selectedWorkspaceId === "all") return;
    setManualLotId(lotNum);
    setManualLoading(true);
    try {
      const details = await api.getFunPayLotDetails(lotNum, selectedWorkspaceId as number);
      setManualLot(details);
      setManualTitle(details.title || "");
      setManualDescription(details.description || "");
      setManualPrice(details.price !== null && details.price !== undefined ? String(details.price) : "");
      setManualActive(Boolean(details.active));
    } catch (err) {
      setStatus({ message: (err as { message?: string })?.message || "Не удалось получить данные лота.", isError: true });
    } finally {
      setManualLoading(false);
    }
  };

  const handleSaveManual = async () => {
    if (selectedWorkspaceId === "all" || manualLotId === null) return;
    const price = manualPrice.trim() === "" ? null : Number(manualPrice);
    if (price !== null && Number.isNaN(price)) {
      setStatus({ message: "Цена должна быть числом.", isError: true });
      return;
    }
    setManualSaving(true);
    try {
      const updated = await api.updateFunPayLotDetails(
        manualLotId,
        { title: manualTitle, description: manualDescription, price, active: manualActive },
        selectedWorkspaceId as number,
      );
      setManualLot(updated);
      setStatus({ message: `Лот #${manualLotId} обновлён.` });
    } catch (err) {
      setStatus({ message: (err as { message?: string })?.message || "Не удалось обновить лот.", isError: true });
    } finally {
      setManualSaving(false);
    }
  };

  const handleManualAutoPrice = async () => {
    if (selectedWorkspaceId === "all" || manualLotId === null) return;
    const price = Number(manualPrice);
    if (Number.isNaN(price)) {
      setStatus({ message: "Введите цену для ручного авто-прайса.", isError: true });
      return;
    }
    setManualAutoPricing(true);
    try {
      const result = await api.manualAutoPriceLot({ lot_number: manualLotId, price }, selectedWorkspaceId as number);
      await openManualPanel(manualLotId);
      setStatus({ message: result.changed ? "Цена обновлена." : "Цена уже актуальна." });
    } catch (err) {
      setStatus({ message: (err as { message?: string })?.message || "Не удалось применить авто-прайс.", isError: true });
    } finally {
      setManualAutoPricing(false);
    }
  };

  const startEdit = (lot: LotItem) => {
    setEditingLot(lot.lot_number);
    setDisplayName(lot.display_name || "");
  };

  const handleSaveDisplay = async () => {
    if (selectedWorkspaceId === "all" || editingLot === null) return;
    try {
      const updated = await api.updateLot(editingLot, { display_name: displayName || null }, selectedWorkspaceId as number);
      setLots((prev) => prev.map((item) => (item.lot_number === editingLot ? { ...item, ...updated } : item)));
      setStatus({ message: "Название лота обновлено." });
      setEditingLot(null);
      setDisplayName("");
    } catch (err) {
      setStatus({ message: (err as { message?: string })?.message || "Не удалось обновить лот.", isError: true });
    }
  };

  const handleCreate = async (event: React.FormEvent) => {
    event.preventDefault();
    if (selectedWorkspaceId === "all") return;
    const number = Number(lotNumber);
    const account = Number(accountId);
    if (!number || !account || !lotUrl.trim()) {
      setStatus({ message: "Укажите номер лота, аккаунт и ссылку.", isError: true });
      return;
    }
    try {
      const created = await api.createLot({ workspace_id: selectedWorkspaceId as number, lot_number: number, account_id: account, lot_url: lotUrl.trim() });
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
      if (manualLotId === lotNum) {
        setManualLotId(null);
        setManualLot(null);
      }
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

  return (
    <div className="space-y-6">
      <div className="rounded-2xl border border-neutral-200 bg-white p-6 shadow-sm shadow-neutral-200/70">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h3 className="text-lg font-semibold text-neutral-900">Привязка лотов</h3>
            <p className="text-sm text-neutral-500">Список лотов и ручное управление параметрами на FunPay.</p>
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
          <input className="rounded-lg border border-neutral-200 bg-white px-3 py-3 text-sm" type="url" value={lotUrl} onChange={(e) => setLotUrl(e.target.value)} placeholder="https://funpay.com/lots/offer?id=..." required />
          <button className="rounded-lg bg-neutral-900 px-4 py-3 text-sm font-semibold text-white hover:bg-neutral-800" type="submit">Сохранить</button>
        </form>

        <div className="mt-6 overflow-x-auto">
          <table className="min-w-[640px] w-full border-separate border-spacing-y-2 text-sm">
            <thead className="text-xs uppercase tracking-wide text-neutral-500">
              <tr>
                <th className="px-3 py-2 text-left">Лот</th><th className="px-3 py-2 text-left">Аккаунт</th><th className="px-3 py-2 text-left">Статус</th><th className="px-3 py-2 text-left">Ссылка</th><th className="px-3 py-2 text-left">Отображаемое имя</th><th className="px-3 py-2"></th>
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
                    <td className="px-3 py-3">
                      <div className="flex items-center gap-2">
                        <input className="w-48 rounded-lg border border-neutral-200 bg-white px-3 py-2 text-xs" value={editingLot === lot.lot_number ? displayName : lot.display_name || ""} onFocus={() => startEdit(lot)} onChange={(e) => { if (editingLot !== lot.lot_number) startEdit(lot); setDisplayName(e.target.value); }} />
                        <button className="rounded-lg border border-neutral-200 px-3 py-2 text-xs font-semibold text-neutral-600 hover:bg-neutral-100 disabled:opacity-60" type="button" onClick={handleSaveDisplay} disabled={editingLot !== lot.lot_number}>Сохранить</button>
                      </div>
                    </td>
                    <td className="rounded-r-xl px-3 py-3 text-right">
                      <div className="flex items-center justify-end gap-2">
                        <button className="rounded-lg border border-neutral-200 px-3 py-2 text-xs font-semibold text-neutral-600 hover:bg-neutral-100 disabled:opacity-60" type="button" onClick={() => handleSyncTitle(lot.lot_number)} disabled={syncingLot === lot.lot_number}>{syncingLot === lot.lot_number ? "Синхр..." : "Синхр. заголовок"}</button>
                        <button className="rounded-lg border border-neutral-200 px-3 py-2 text-xs font-semibold text-neutral-600 hover:bg-neutral-100" type="button" onClick={() => openManualPanel(lot.lot_number)}>Ручное</button>
                        <button className="rounded-lg border border-neutral-200 px-3 py-2 text-xs font-semibold text-neutral-600 hover:bg-neutral-100" type="button" onClick={() => handleDelete(lot.lot_number)}>Удалить</button>
                      </div>
                    </td>
                  </tr>
                );
              }) : (
                <tr><td colSpan={6} className="rounded-xl border border-dashed border-neutral-200 bg-neutral-50 px-4 py-6 text-center text-sm text-neutral-500">{loading ? "Загружаем лоты..." : "Лоты ещё не настроены."}</td></tr>
              )}
            </tbody>
          </table>
        </div>

        {manualLotId !== null ? (
          <div className="mt-6 rounded-xl border border-neutral-200 bg-neutral-50 p-4">
            <div className="mb-3 flex items-center justify-between gap-2">
              <h4 className="text-sm font-semibold text-neutral-800">Ручное управление лотом #{manualLotId}</h4>
              <button className="rounded-lg border border-neutral-200 bg-white px-3 py-2 text-xs font-semibold text-neutral-600 hover:bg-neutral-100" type="button" onClick={() => openManualPanel(manualLotId)} disabled={manualLoading}>{manualLoading ? "Загрузка..." : "Обновить"}</button>
            </div>
            {manualLot ? (
              <div className="grid gap-3">
                <input className="rounded-lg border border-neutral-200 bg-white px-3 py-2 text-sm text-neutral-900" value={manualTitle} onChange={(e) => setManualTitle(e.target.value)} placeholder="Заголовок" />
                <textarea className="min-h-[120px] rounded-lg border border-neutral-200 bg-white px-3 py-2 text-sm text-neutral-900" value={manualDescription} onChange={(e) => setManualDescription(e.target.value)} placeholder="Описание" />
                <div className="grid gap-3 md:grid-cols-3">
                  <input className="rounded-lg border border-neutral-200 bg-white px-3 py-2 text-sm text-neutral-900" value={manualPrice} onChange={(e) => setManualPrice(e.target.value)} placeholder="Цена" />
                  <label className="inline-flex items-center gap-2 text-sm text-neutral-700"><input type="checkbox" checked={manualActive} onChange={(e) => setManualActive(e.target.checked)} /> Лот активен</label>
                </div>
                <div className="flex flex-wrap gap-2">
                  <button className="rounded-lg bg-neutral-900 px-4 py-2 text-xs font-semibold text-white hover:bg-neutral-800 disabled:opacity-60" type="button" onClick={handleSaveManual} disabled={manualSaving}>{manualSaving ? "Сохраняем..." : "Сохранить изменения"}</button>
                  <button className="rounded-lg border border-neutral-200 bg-white px-4 py-2 text-xs font-semibold text-neutral-700 hover:bg-neutral-100 disabled:opacity-60" type="button" onClick={handleManualAutoPrice} disabled={manualAutoPricing}>{manualAutoPricing ? "Запуск..." : "Ручной авто-прайс"}</button>
                </div>
                <div className="text-xs text-neutral-500">Текущие данные: цена {manualLot.price ?? "—"}, активен: {manualLot.active ? "да" : "нет"}</div>
              </div>
            ) : <p className="text-sm text-neutral-500">Загрузка данных лота...</p>}
          </div>
        ) : null}
      </div>
    </div>
  );
};

export default LotsPage;
