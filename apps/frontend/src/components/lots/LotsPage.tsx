import React, { useEffect, useMemo, useState } from "react";
import { api, AccountItem, LotItem, LotAliasItem } from "../../services/api";
import { useWorkspace } from "../../context/WorkspaceContext";

const LotsPage: React.FC = () => {
  const [accounts, setAccounts] = useState<AccountItem[]>([]);
  const [lots, setLots] = useState<LotItem[]>([]);
  const [aliases, setAliases] = useState<LotAliasItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [status, setStatus] = useState<{ message: string; isError?: boolean } | null>(null);
  const { selectedId: selectedWorkspaceId, workspaces } = useWorkspace();

  const [lotNumber, setLotNumber] = useState("");
  const [accountId, setAccountId] = useState("");
  const [lotUrl, setLotUrl] = useState("");
  const [editingLot, setEditingLot] = useState<number | null>(null);
  const [urlsInput, setUrlsInput] = useState("");
  const [isGlobal, setIsGlobal] = useState(false);

  const accountOptions = useMemo(() => {
    return accounts.map((acc) => ({
      id: acc.id,
      label: `${acc.account_name} (ID ${acc.id})`,
    }));
  }, [accounts]);

  const currentWorkspaceLabel = useMemo(() => {
    if (selectedWorkspaceId === "all") return "All workspaces";
    const match = workspaces.find((item) => item.id === selectedWorkspaceId);
    if (match) return match.is_default ? `${match.name} (Default)` : match.name;
    const fallback = workspaces.find((item) => item.is_default);
    return fallback ? `${fallback.name} (Default)` : "Workspace";
  }, [selectedWorkspaceId, workspaces]);

  useEffect(() => {
    let mounted = true;
    const workspaceId = selectedWorkspaceId === "all" ? undefined : selectedWorkspaceId;
    Promise.all([
      api.listAccounts(typeof workspaceId === "number" ? workspaceId : undefined),
      api.listLots(typeof workspaceId === "number" ? workspaceId : undefined),
      api.listLotAliases(typeof workspaceId === "number" ? workspaceId : undefined),
    ])
      .then(([accountsRes, lotsRes, aliasRes]) => {
        if (!mounted) return;
        setAccounts(accountsRes.items || []);
        setLots(lotsRes.items || []);
        setAliases(aliasRes.items || []);
      })
      .catch((err) => {
        if (!mounted) return;
      setStatus({
        message: (err as { message?: string })?.message || "Failed to load lots.",
        isError: true,
      });
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
    setStatus(null);
    const number = Number(lotNumber);
    const account = Number(accountId);
    if (!number || !account) {
      setStatus({ message: "Provide lot number and account.", isError: true });
      return;
    }
    if (!lotUrl.trim()) {
      setStatus({ message: "Lot URL is required.", isError: true });
      return;
    }
    try {
      const created = await api.createLot({
        workspace_id: isGlobal || selectedWorkspaceId === "all" ? null : selectedWorkspaceId,
        lot_number: number,
        account_id: account,
        lot_url: lotUrl.trim(),
      });
      setLots((prev) => {
        const next = prev.filter(
          (item) => !(item.lot_number === created.lot_number && item.workspace_id === created.workspace_id),
        );
        next.unshift(created);
        return next;
      });
      setLotNumber("");
      setAccountId("");
      setLotUrl("");
      setIsGlobal(false);
    setStatus({ message: "Lot saved." });
  } catch (err) {
    setStatus({
      message: (err as { message?: string })?.message || "Failed to save lot.",
      isError: true,
    });
  }
};

const handleDelete = async (lotNum: number) => {
    try {
      const workspaceId = selectedWorkspaceId === "all" ? undefined : selectedWorkspaceId;
      await api.deleteLot(lotNum, typeof workspaceId === "number" ? workspaceId : undefined);
      setLots((prev) => prev.filter((item) => item.lot_number !== lotNum));
    } catch (err) {
      setStatus({
        message: (err as { message?: string })?.message || "Failed to delete lot.",
        isError: true,
      });
    }
  };

  const aliasesByLot = useMemo(() => {
    const map: Record<number, string[]> = {};
    aliases.forEach((a) => {
      if (!map[a.lot_number]) map[a.lot_number] = [];
      map[a.lot_number].push(a.funpay_url);
    });
    return map;
  }, [aliases]);

  const startEditUrls = (lotNum: number) => {
    setEditingLot(lotNum);
    const current = aliasesByLot[lotNum] || [];
    setUrlsInput(current.join(", "));
  };

  const handleSaveUrls = async (lotNum: number) => {
    if (selectedWorkspaceId === "all") {
      setStatus({ message: "Pick a workspace to edit URLs.", isError: true });
      return;
    }
    const urls = urlsInput
      .split(/[\n,]+/)
      .map((u) => u.trim())
      .filter((u) => u.length > 0);
    try {
      const res = await api.replaceLotAliases({
        lot_number: lotNum,
        urls,
        workspace_id: selectedWorkspaceId,
      });
      setAliases((prev) => {
        // replace aliases for this lot with returned ones, keep others
        const others = prev.filter((a) => a.lot_number !== lotNum);
        return [...others, ...(res.items || [])];
      });
      setEditingLot(null);
      setStatus({ message: "URLs updated." });
    } catch (err) {
      setStatus({
        message: (err as { message?: string })?.message || "Failed to save URLs.",
        isError: true,
      });
    }
  };

  const cancelEdit = () => {
    setEditingLot(null);
    setUrlsInput("");
  };

  return (
    <div className="space-y-6">
      <div className="rounded-2xl border border-neutral-200 bg-white p-6 shadow-sm shadow-neutral-200/70">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h3 className="text-lg font-semibold text-neutral-900">Lots mapping</h3>
            <p className="text-sm text-neutral-500">
              Map FunPay lot numbers to accounts. Used by !сток and automation.
            </p>
          </div>
        
          <div className="flex items-center gap-2 rounded-lg border border-neutral-200 bg-neutral-50 px-3 py-2 text-[11px] font-semibold text-neutral-600">
            <span className="uppercase tracking-wide text-neutral-500">Workspace</span>
            <span className="text-xs font-semibold text-neutral-700">{currentWorkspaceLabel}</span>
          </div>
</div>

        {status ? (
          <div
            className={`mt-4 rounded-xl border px-4 py-3 text-sm ${
              status.isError
                ? "border-red-200 bg-red-50 text-red-700"
                : "border-emerald-200 bg-emerald-50 text-emerald-700"
            }`}
          >
            {status.message}
          </div>
        ) : null}

        <form className="mt-5 grid gap-4 lg:grid-cols-[140px_1fr_1fr_auto]" onSubmit={handleCreate}>
          <div className="space-y-2">
            <label className="text-xs font-semibold uppercase tracking-wide text-neutral-500">Lot number</label>
            <input
              className="w-full rounded-lg border border-neutral-200 bg-white px-3 py-3 text-sm text-neutral-900 shadow-sm outline-none focus:border-neutral-400"
              type="number"
              min={1}
              value={lotNumber}
              onChange={(event) => setLotNumber(event.target.value)}
              required
            />
          </div>
          <div className="space-y-2">
            <label className="text-xs font-semibold uppercase tracking-wide text-neutral-500">Account</label>
            <select
              className="w-full rounded-lg border border-neutral-200 bg-white px-3 py-3 text-sm text-neutral-900 shadow-sm outline-none focus:border-neutral-400"
              value={accountId}
              onChange={(event) => setAccountId(event.target.value)}
              required
            >
              <option value="">Select an account</option>
              {accountOptions.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.label}
                </option>
              ))}
            </select>
          </div>
          <div className="space-y-2">
            <label className="text-xs font-semibold uppercase tracking-wide text-neutral-500">Lot URL</label>
            <input
              className="w-full rounded-lg border border-neutral-200 bg-white px-3 py-3 text-sm text-neutral-900 shadow-sm outline-none focus:border-neutral-400"
              type="url"
              value={lotUrl}
              onChange={(event) => setLotUrl(event.target.value)}
              placeholder="https://funpay.com/lots/offer?id=..."
              required
            />
          </div>
          <div className="flex items-end gap-3">
            <label className="flex items-center gap-2 text-sm font-semibold text-neutral-700">
              <input
                type="checkbox"
                checked={isGlobal || selectedWorkspaceId === "all"}
                onChange={(e) => setIsGlobal(e.target.checked)}
                disabled={selectedWorkspaceId === "all"}
              />
              Global mapping (shared pool)
            </label>
          </div>
          <div className="flex items-end">
            <button
              className="rounded-lg bg-neutral-900 px-4 py-3 text-sm font-semibold text-white shadow-sm transition hover:bg-neutral-800"
              type="submit"
            >
              Save
            </button>
          </div>
        </form>

        <div className="mt-6 overflow-x-auto">
          <table className="min-w-[640px] w-full border-separate border-spacing-y-2 text-sm">
            <thead className="text-xs uppercase tracking-wide text-neutral-500">
              <tr>
                <th className="px-3 py-2 text-left">Lot</th>
                <th className="px-3 py-2 text-left">Account</th>
                <th className="px-3 py-2 text-left">Primary URL</th>
                <th className="px-3 py-2 text-left">Scope</th>
                <th className="px-3 py-2 text-left">URLs (comma-separated)</th>
                <th className="px-3 py-2"></th>
              </tr>
            </thead>
            <tbody>
              {lots.length ? (
                lots.map((lot) => (
                  <tr key={lot.lot_number} className="bg-neutral-50">
                    <td className="rounded-l-xl px-3 py-3 font-semibold text-neutral-900">
                      #{lot.lot_number}
                    </td>
                    <td className="px-3 py-3 text-neutral-700">
                      {lot.account_name} (ID {lot.account_id})
                    </td>
                    <td className="px-3 py-3 text-neutral-700">
                      {lot.lot_url ? (
                        <a className="text-emerald-600 hover:underline" href={lot.lot_url} target="_blank" rel="noreferrer">
                          {lot.lot_url}
                        </a>
                      ) : (
                        "-"
                      )}
                    </td>
                    <td className="px-3 py-3 text-neutral-700">
                      {lot.workspace_id ? "Workspace" : "Global"}
                    </td>
                    <td className="px-3 py-3 text-neutral-700 align-top">
                      {editingLot === lot.lot_number ? (
                        <div className="space-y-2">
                          <textarea
                            className="w-full rounded-lg border border-neutral-200 bg-white px-3 py-2 text-sm text-neutral-900 shadow-sm outline-none focus:border-neutral-400"
                            rows={2}
                            value={urlsInput}
                            onChange={(e) => setUrlsInput(e.target.value)}
                            placeholder="https://funpay.com/lots/offer?id=..., https://funpay.com/lots/offer?id=..."
                          />
                          <div className="flex gap-2">
                            <button
                              type="button"
                              className="rounded-lg bg-neutral-900 px-3 py-2 text-xs font-semibold text-white hover:bg-neutral-800"
                              onClick={() => handleSaveUrls(lot.lot_number)}
                            >
                              Save URLs
                            </button>
                            <button
                              type="button"
                              className="rounded-lg border border-neutral-200 px-3 py-2 text-xs font-semibold text-neutral-600 hover:bg-neutral-100"
                              onClick={cancelEdit}
                            >
                              Cancel
                            </button>
                          </div>
                        </div>
                      ) : (
                        <div className="flex flex-col gap-1">
                          <div className="text-xs text-neutral-500">
                            {aliasesByLot[lot.lot_number]?.length
                              ? `${aliasesByLot[lot.lot_number].length} URL${aliasesByLot[lot.lot_number].length > 1 ? "s" : ""}`
                              : "No aliases"}
                          </div>
                          {aliasesByLot[lot.lot_number]?.[0] ? (
                            <span className="truncate text-neutral-700">{aliasesByLot[lot.lot_number][0]}</span>
                          ) : null}
                          <button
                            type="button"
                            className="w-fit rounded-lg border border-neutral-200 px-3 py-1 text-xs font-semibold text-neutral-600 hover:bg-neutral-100"
                            onClick={() => startEditUrls(lot.lot_number)}
                          >
                            Edit URLs
                          </button>
                        </div>
                      )}
                    </td>
                    <td className="rounded-r-xl px-3 py-3 text-right">
                      <button
                        className="rounded-lg border border-neutral-200 px-3 py-2 text-xs font-semibold text-neutral-600 hover:bg-neutral-100"
                        type="button"
                        onClick={() => handleDelete(lot.lot_number)}
                      >
                        Delete
                      </button>
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={6} className="rounded-xl border border-dashed border-neutral-200 bg-neutral-50 px-4 py-6 text-center text-sm text-neutral-500">
                    {loading ? "Loading lots..." : "No lots configured yet."}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

    </div>
  );
};

export default LotsPage;
