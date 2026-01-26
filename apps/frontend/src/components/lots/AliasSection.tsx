import React, { useMemo, useState } from "react";
import { api, LotAliasItem } from "../../services/api";
import { useWorkspace } from "../../context/WorkspaceContext";

type Props = {
  aliases: LotAliasItem[];
  onCreated: (alias: LotAliasItem) => void;
  onDeleted: (id: number) => void;
  loading?: boolean;
};

const AliasSection: React.FC<Props> = ({ aliases, onCreated, onDeleted, loading }) => {
  const { selectedId: selectedWorkspaceId, workspaces } = useWorkspace();
  const [lotNumber, setLotNumber] = useState("");
  const [url, setUrl] = useState("");
  const [status, setStatus] = useState<{ message: string; isError?: boolean } | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const workspaceLabel = useMemo(() => {
    if (selectedWorkspaceId === "all") return "All workspaces";
    const found = workspaces.find((w) => w.id === selectedWorkspaceId);
    if (found) return found.is_default ? `${found.name} (Default)` : found.name;
    return "Workspace";
  }, [selectedWorkspaceId, workspaces]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setStatus(null);
    const num = Number(lotNumber);
    if (!num) {
      setStatus({ message: "Enter lot number.", isError: true });
      return;
    }
    if (!url.trim()) {
      setStatus({ message: "Enter FunPay URL.", isError: true });
      return;
    }
    if (selectedWorkspaceId === "all") {
      setStatus({ message: "Select a workspace to add alias.", isError: true });
      return;
    }
    setSubmitting(true);
    try {
      const created = await api.createLotAlias({
        lot_number: num,
        funpay_url: url.trim(),
        workspace_id: selectedWorkspaceId as number,
      });
      onCreated(created);
      setLotNumber("");
      setUrl("");
      setStatus({ message: "Alias added." });
    } catch (err) {
      setStatus({
        message: (err as { message?: string })?.message || "Failed to add alias.",
        isError: true,
      });
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (id: number) => {
    try {
      if (selectedWorkspaceId === "all") {
        setStatus({ message: "Select a workspace to delete alias.", isError: true });
        return;
      }
      await api.deleteLotAlias(id, selectedWorkspaceId as number);
      onDeleted(id);
    } catch (err) {
      setStatus({
        message: (err as { message?: string })?.message || "Failed to delete alias.",
        isError: true,
      });
    }
  };

  return (
    <div className="rounded-2xl border border-neutral-200 bg-white p-6 shadow-sm shadow-neutral-200/70 space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h3 className="text-lg font-semibold text-neutral-900">Lot aliases</h3>
          <p className="text-sm text-neutral-500">Add multiple FunPay URLs for the same #lot.</p>
        </div>
        <div className="flex items-center gap-2 rounded-lg border border-neutral-200 bg-neutral-50 px-3 py-2 text-[11px] font-semibold text-neutral-600">
          <span className="uppercase tracking-wide text-neutral-500">Workspace</span>
          <span className="text-xs font-semibold text-neutral-700">{workspaceLabel}</span>
        </div>
      </div>

      {status ? (
        <div
          className={`rounded-xl border px-4 py-3 text-sm ${
            status.isError
              ? "border-red-200 bg-red-50 text-red-700"
              : "border-emerald-200 bg-emerald-50 text-emerald-700"
          }`}
        >
          {status.message}
        </div>
      ) : null}

      <form className="grid gap-4 lg:grid-cols-[140px_1fr_auto]" onSubmit={handleSubmit}>
        <div className="space-y-2">
          <label className="text-xs font-semibold uppercase tracking-wide text-neutral-500">Lot number</label>
          <input
            className="w-full rounded-lg border border-neutral-200 bg-white px-3 py-3 text-sm text-neutral-900 shadow-sm outline-none focus:border-neutral-400"
            type="number"
            min={1}
            value={lotNumber}
            onChange={(e) => setLotNumber(e.target.value)}
            required
          />
        </div>
        <div className="space-y-2">
          <label className="text-xs font-semibold uppercase tracking-wide text-neutral-500">FunPay URL</label>
          <input
            className="w-full rounded-lg border border-neutral-200 bg-white px-3 py-3 text-sm text-neutral-900 shadow-sm outline-none focus:border-neutral-400"
            type="url"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="https://funpay.com/lots/offer?id=..."
            required
          />
        </div>
        <div className="flex items-end">
          <button
            className="rounded-lg bg-neutral-900 px-4 py-3 text-sm font-semibold text-white shadow-sm transition hover:bg-neutral-800 disabled:opacity-70"
            type="submit"
            disabled={submitting}
          >
            {submitting ? "Saving..." : "Add"}
          </button>
        </div>
      </form>

      <div className="overflow-x-auto">
        <table className="min-w-[520px] w-full border-separate border-spacing-y-2 text-sm">
          <thead className="text-xs uppercase tracking-wide text-neutral-500">
            <tr>
              <th className="px-3 py-2 text-left">Lot</th>
              <th className="px-3 py-2 text-left">URL</th>
              <th className="px-3 py-2"></th>
            </tr>
          </thead>
          <tbody>
            {aliases.length ? (
              aliases.map((alias) => (
                <tr key={alias.id} className="bg-neutral-50">
                  <td className="rounded-l-xl px-3 py-3 font-semibold text-neutral-900">#{alias.lot_number}</td>
                  <td className="px-3 py-3 text-neutral-700">
                    <a className="text-emerald-600 hover:underline" href={alias.funpay_url} target="_blank" rel="noreferrer">
                      {alias.funpay_url}
                    </a>
                  </td>
                  <td className="rounded-r-xl px-3 py-3 text-right">
                    <button
                      className="rounded-lg border border-neutral-200 px-3 py-2 text-xs font-semibold text-neutral-600 hover:bg-neutral-100"
                      type="button"
                      onClick={() => handleDelete(alias.id)}
                    >
                      Delete
                    </button>
                  </td>
                </tr>
              ))
            ) : (
              <tr>
                <td
                  colSpan={3}
                  className="rounded-xl border border-dashed border-neutral-200 bg-neutral-50 px-4 py-6 text-center text-sm text-neutral-500"
                >
                  {loading ? "Loading aliases..." : "No aliases yet."}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default AliasSection;
