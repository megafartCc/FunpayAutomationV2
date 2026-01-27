import React, { useEffect, useMemo, useState } from "react";
import { api, AccountItem, LotItem } from "../../services/api";
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

  const accountOptions = useMemo(
    () =>
      accounts.map((acc) => {
        const hasWorkspace = Boolean(acc.workspace_name || acc.workspace_id);
        const workspaceLabel = hasWorkspace
          ? `• ${acc.workspace_name || `ID ${acc.workspace_id}`}`
          : "";
        return {
          id: acc.id,
          label: `${acc.account_name} (ID ${acc.id}) ${workspaceLabel}`.trim(),
        };
      }),
    [accounts],
  );

  const currentWorkspaceLabel = useMemo(() => {
    if (selectedWorkspaceId === "all") return "Pick a workspace";
    const match = workspaces.find((w) => w.id === selectedWorkspaceId);
    return match ? match.name : "Workspace";
  }, [selectedWorkspaceId, workspaces]);

  useEffect(() => {
    if (selectedWorkspaceId === "all") {
      setStatus({ message: "Select a workspace to edit lots.", isError: true });
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
    if (selectedWorkspaceId === "all") {
      setStatus({ message: "Select a workspace first.", isError: true });
      return;
    }
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
        workspace_id: selectedWorkspaceId as number,
        lot_number: number,
        account_id: account,
        lot_url: lotUrl.trim(),
      });
      setLots((prev) => {
        const next = prev.filter((item) => !(item.lot_number === created.lot_number));
        next.unshift(created);
        return next;
      });
      setLotNumber("");
      setAccountId("");
      setLotUrl("");
      setStatus({ message: "Lot saved." });
    } catch (err) {
      setStatus({
        message: (err as { message?: string })?.message || "Failed to save lot.",
        isError: true,
      });
    }
  };

  const handleDelete = async (lotNum: number) => {
    if (selectedWorkspaceId === "all") {
      setStatus({ message: "Select a workspace first.", isError: true });
      return;
    }
    try {
      await api.deleteLot(lotNum, selectedWorkspaceId as number);
      setLots((prev) => prev.filter((item) => item.lot_number !== lotNum));
    } catch (err) {
      setStatus({
        message: (err as { message?: string })?.message || "Failed to delete lot.",
        isError: true,
      });
    }
  };

  return (
    <div className="space-y-6">
      <div className="rounded-2xl border border-neutral-200 bg-white p-6 shadow-sm shadow-neutral-200/70">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h3 className="text-lg font-semibold text-neutral-900">Lots mapping</h3>
            <p className="text-sm text-neutral-500">Workspace-specific. Used by !сток and automation.</p>
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
                <th className="px-3 py-2 text-left">Lot URL</th>
                <th className="px-3 py-2"></th>
              </tr>
            </thead>
            <tbody>
              {lots.length ? (
                lots.map((lot) => (
                  <tr key={lot.lot_number} className="bg-neutral-50">
                    <td className="rounded-l-xl px-3 py-3 font-semibold text-neutral-900">#{lot.lot_number}</td>
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
                  <td
                    colSpan={4}
                    className="rounded-xl border border-dashed border-neutral-200 bg-neutral-50 px-4 py-6 text-center text-sm text-neutral-500"
                  >
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
