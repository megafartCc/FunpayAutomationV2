import React, { useRef, useState } from "react";
import { api } from "../../services/api";

const AddIcon = () => (
  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" aria-hidden="true">
    <path
      d="M12 16V10M12 10L9 12M12 10L15 12M3 6V16.8C3 17.9201 3 18.4798 3.21799 18.9076C3.40973 19.2839 3.71547 19.5905 4.0918 19.7822C4.5192 20 5.07899 20 6.19691 20H17.8031C18.921 20 19.48 20 19.9074 19.7822C20.2837 19.5905 20.5905 19.2841 20.7822 18.9078C21.0002 18.48 21.0002 17.9199 21.0002 16.7998L21.0002 9.19978C21.0002 8.07967 21.0002 7.51962 20.7822 7.0918C20.5905 6.71547 20.2839 6.40973 19.9076 6.21799C19.4798 6 18.9201 6 17.8 6H12M3 6H12M3 6C3 4.89543 3.89543 4 5 4H8.67452C9.1637 4 9.40886 4 9.63904 4.05526C9.84311 4.10425 10.0379 4.18526 10.2168 4.29492C10.4186 4.41857 10.5918 4.59182 10.9375 4.9375L12 6"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
  </svg>
);

const AddAccountPage: React.FC = () => {
  const [accountName, setAccountName] = useState("");
  const [login, setLogin] = useState("");
  const [password, setPassword] = useState("");
  const [mmr, setMmr] = useState("");
  const [mafileJson, setMafileJson] = useState("");
  const [status, setStatus] = useState<{ message: string; isError?: boolean } | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      const text = typeof reader.result === "string" ? reader.result : "";
      setMafileJson(text);
    };
    reader.readAsText(file);
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setStatus(null);

    if (!accountName.trim() || !login.trim() || !password.trim()) {
      setStatus({ message: "Account name, login, and password are required.", isError: true });
      return;
    }
    if (!mafileJson.trim()) {
      setStatus({ message: "maFile JSON is required.", isError: true });
      return;
    }

    const mmrValue = mmr.trim();
    const mmrNumber = mmrValue ? Number(mmrValue) : undefined;
    if (mmrValue && Number.isNaN(mmrNumber)) {
      setStatus({ message: "MMR must be a number.", isError: true });
      return;
    }

    const payload = {
      account_name: accountName.trim(),
      login: login.trim(),
      password,
      mafile_json: mafileJson.trim(),
      mmr: mmrNumber,
      rental_duration: 1,
      rental_minutes: 0,
    };

    setSubmitting(true);
    try {
      await api.createAccount(payload);
      setStatus({ message: "Account created." });
      setAccountName("");
      setLogin("");
      setPassword("");
      setMmr("");
      setMafileJson("");
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    } catch (err) {
      setStatus({
        message: (err as { message?: string })?.message || "Failed to create account.",
        isError: true,
      });
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="rounded-2xl border border-neutral-200 bg-white p-6 shadow-sm shadow-neutral-200/70">
        <div className="flex flex-wrap items-center gap-3">
          <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-neutral-100 text-neutral-700">
            <AddIcon />
          </span>
          <div>
            <h3 className="text-lg font-semibold text-neutral-900">Add Account</h3>
            <p className="text-sm text-neutral-500">Upload Steam credentials and maFile JSON.</p>
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

        <form onSubmit={handleSubmit} className="mt-5 space-y-5">
          <div className="grid gap-4 md:grid-cols-2">
            <div className="space-y-2">
              <label className="text-xs font-semibold uppercase tracking-wide text-neutral-500">Account name</label>
              <input
                className="w-full rounded-lg border border-neutral-200 bg-white px-3 py-3 text-sm text-neutral-900 shadow-sm outline-none focus:border-neutral-400"
                value={accountName}
                onChange={(event) => setAccountName(event.target.value)}
                required
              />
            </div>
            <div className="space-y-2">
              <label className="text-xs font-semibold uppercase tracking-wide text-neutral-500">Login</label>
              <input
                className="w-full rounded-lg border border-neutral-200 bg-white px-3 py-3 text-sm text-neutral-900 shadow-sm outline-none focus:border-neutral-400"
                value={login}
                onChange={(event) => setLogin(event.target.value)}
                required
              />
            </div>
            <div className="space-y-2">
              <label className="text-xs font-semibold uppercase tracking-wide text-neutral-500">Password</label>
              <input
                type="password"
                className="w-full rounded-lg border border-neutral-200 bg-white px-3 py-3 text-sm text-neutral-900 shadow-sm outline-none focus:border-neutral-400"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                required
              />
            </div>
            <div className="space-y-2">
              <label className="text-xs font-semibold uppercase tracking-wide text-neutral-500">MMR (optional)</label>
              <input
                type="number"
                className="w-full rounded-lg border border-neutral-200 bg-white px-3 py-3 text-sm text-neutral-900 shadow-sm outline-none focus:border-neutral-400"
                value={mmr}
                onChange={(event) => setMmr(event.target.value)}
                min={0}
              />
            </div>
            <div className="space-y-2 md:col-span-2">
              <label className="text-xs font-semibold uppercase tracking-wide text-neutral-500">maFile JSON</label>
              <textarea
                className="min-h-[160px] w-full rounded-lg border border-neutral-200 bg-white px-3 py-3 text-sm text-neutral-900 shadow-sm outline-none focus:border-neutral-400"
                value={mafileJson}
                onChange={(event) => setMafileJson(event.target.value)}
                required
              />
              <div className="flex flex-wrap items-center gap-3 text-xs text-neutral-500">
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".maFile,.json,application/json"
                  className="hidden"
                  onChange={handleFileChange}
                />
                <button
                  type="button"
                  onClick={() => fileInputRef.current?.click()}
                  className="rounded-lg border border-neutral-200 px-3 py-2 text-xs font-semibold text-neutral-700 hover:bg-neutral-100"
                >
                  Upload maFile
                </button>
                <span>Paste JSON directly or upload the .maFile.</span>
              </div>
            </div>
          </div>

          <div className="flex flex-wrap gap-3">
            <button
              className="rounded-lg bg-neutral-900 px-4 py-3 text-sm font-semibold text-white shadow-sm transition hover:bg-neutral-800 disabled:opacity-60"
              type="submit"
              disabled={submitting}
            >
              {submitting ? "Creating..." : "Create account"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default AddAccountPage;
