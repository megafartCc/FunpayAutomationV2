import React, { useEffect, useMemo, useRef, useState } from "react";
import { api } from "../../services/api";
import { useWorkspace } from "../../context/WorkspaceContext";
import { useI18n } from "../../i18n/useI18n";

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
  const [bulkMode, setBulkMode] = useState(false);
  const [bulkCredentials, setBulkCredentials] = useState("");
  const [bulkStatus, setBulkStatus] = useState<{ message: string; isError?: boolean } | null>(null);
  const [bulkSubmitting, setBulkSubmitting] = useState(false);
  const [bulkMafileMap, setBulkMafileMap] = useState<Record<string, string>>({});
  const [bulkMafileErrors, setBulkMafileErrors] = useState<string[]>([]);
  const { visibleWorkspaces, selectedId } = useWorkspace();
  const { tr } = useI18n();
  const defaultWorkspaceId = useMemo(() => {
    const def = visibleWorkspaces.find((item) => item.is_default);
    return def?.id ?? (visibleWorkspaces[0]?.id ?? null);
  }, [visibleWorkspaces]);
  const [workspaceId, setWorkspaceId] = useState<number | null>(null);
  const [status, setStatus] = useState<{ message: string; isError?: boolean } | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const bulkMafileInputRef = useRef<HTMLInputElement | null>(null);

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

  const extractMafileLogin = (raw: string, fallbackName: string) => {
    try {
      const data = JSON.parse(raw);
      const direct =
        data?.account_name ??
        data?.AccountName ??
        data?.accountName ??
        data?.login ??
        data?.Login ??
        data?.steam_login ??
        data?.SteamLogin ??
        data?.Session?.AccountName ??
        data?.Session?.account_name;
      if (direct) return String(direct).trim();
    } catch {
      return fallbackName;
    }
    return fallbackName;
  };

  const handleBulkMafileChange = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(event.target.files ?? []);
    if (!files.length) return;
    const map: Record<string, string> = {};
    const errors: string[] = [];
    for (const file of files) {
      try {
        const text = await file.text();
        const fallback = file.name.replace(/\.(mafile|json)$/i, "").trim();
        const loginKey = extractMafileLogin(text, fallback);
        if (!loginKey) {
          errors.push(`${file.name}: ${tr("login not found", "логин не найден")}`);
          continue;
        }
        map[loginKey.toLowerCase()] = text;
      } catch {
        errors.push(`${file.name}: ${tr("failed to read", "не удалось прочитать")}`);
      }
    }
    setBulkMafileMap(map);
    setBulkMafileErrors(errors);
  };

  useEffect(() => {
    if (selectedId !== "all") {
      setWorkspaceId(selectedId);
      return;
    }
    if (defaultWorkspaceId) {
      setWorkspaceId(defaultWorkspaceId);
    }
  }, [selectedId, defaultWorkspaceId]);

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setStatus(null);

    if (!accountName.trim() || !login.trim() || !password.trim()) {
      setStatus({ message: tr("Account name, login, and password are required.", "Название аккаунта, логин и пароль обязательны."), isError: true });
      return;
    }
    if (!workspaceId) {
      setStatus({ message: tr("Select a workspace for this account.", "Выберите рабочее пространство для этого аккаунта."), isError: true });
      return;
    }
    if (!mafileJson.trim()) {
      setStatus({ message: tr("maFile JSON is required.", "Нужен JSON maFile."), isError: true });
      return;
    }

    const mmrValue = mmr.trim();
    const mmrNumber = mmrValue ? Number(mmrValue) : undefined;
    if (mmrValue && Number.isNaN(mmrNumber)) {
      setStatus({ message: tr("MMR must be a number.", "MMR должен быть числом."), isError: true });
      return;
    }

    const payload = {
      workspace_id: workspaceId,
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
      setStatus({ message: tr("Account created.", "Аккаунт создан.") });
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
        message: (err as { message?: string })?.message || tr("Failed to create account.", "Не удалось создать аккаунт."),
        isError: true,
      });
    } finally {
      setSubmitting(false);
    }
  };

  const parseCredentials = (raw: string) => {
    const lines = raw
      .split(/\r?\n/)
      .map((line) => line.trim())
      .filter((line) => line && !line.startsWith("#"));
    const parsed: { login: string; password: string; accountName: string }[] = [];
    for (const line of lines) {
      const match = line.match(/^([^:;|\t]+)[:;|\t](.+)$/);
      if (!match) continue;
      const loginValue = match[1].trim();
      const rest = match[2].trim();
      if (!loginValue || !rest) continue;
      const accountName = loginValue;
      parsed.push({ login: loginValue, password: rest, accountName });
    }
    return parsed;
  };

  const handleBulkSubmit = async () => {
    setBulkStatus(null);
    if (!workspaceId) {
      setBulkStatus({
        message: tr("Select a workspace for these accounts.", "Выберите рабочее пространство для этих аккаунтов."),
        isError: true,
      });
      return;
    }
    const entries = parseCredentials(bulkCredentials);
    if (!entries.length) {
      setBulkStatus({
        message: tr(
          "Paste credentials in the format login:password, one per line.",
          "Вставьте логин:пароль, по одному на строку.",
        ),
        isError: true,
      });
      return;
    }
    if (!Object.keys(bulkMafileMap).length) {
      setBulkStatus({
        message: tr("Upload maFiles to match by login.", "Загрузите maFile'ы для сопоставления по логину."),
        isError: true,
      });
      return;
    }

    const toCreate: typeof entries = [];
    const missing: string[] = [];
    for (const entry of entries) {
      const mafile = bulkMafileMap[entry.login.toLowerCase()];
      if (!mafile) {
        missing.push(entry.login);
        continue;
      }
      toCreate.push(entry);
    }
    if (!toCreate.length) {
      setBulkStatus({
        message: tr("No accounts matched maFiles.", "Нет совпавших maFile по логинам."),
        isError: true,
      });
      return;
    }

    setBulkSubmitting(true);
    let created = 0;
    let failed = 0;
    for (const entry of toCreate) {
      try {
        await api.createAccount({
          workspace_id: workspaceId,
          account_name: entry.accountName,
          login: entry.login,
          password: entry.password,
          mafile_json: bulkMafileMap[entry.login.toLowerCase()],
          mmr: undefined,
          rental_duration: 1,
          rental_minutes: 0,
        });
        created += 1;
      } catch {
        failed += 1;
      }
    }

    const missingLabel = missing.length ? ` ${tr("Missing maFiles:", "Нет maFile:")} ${missing.join(", ")}` : "";
    setBulkStatus({
      message: tr(
        `Created ${created}, failed ${failed}.${missingLabel}`,
        `Создано ${created}, ошибок ${failed}.${missingLabel}`,
      ),
      isError: failed > 0,
    });
    setBulkSubmitting(false);
  };

  return (
    <div className="space-y-6">
      <div className="rounded-2xl border border-neutral-200 bg-white p-6 shadow-sm shadow-neutral-200/70">
        <div className="flex flex-wrap items-center gap-3">
          <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-neutral-100 text-neutral-700">
            <AddIcon />
          </span>
          <div>
            <h3 className="text-lg font-semibold text-neutral-900">{tr("Add Account", "Добавить аккаунт")}</h3>
            <p className="text-sm text-neutral-500">{tr("Upload Steam credentials and maFile JSON.", "Загрузите Steam-данные и JSON maFile.")}</p>
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
            <div className="space-y-2 md:col-span-2">
              <label className="text-xs font-semibold uppercase tracking-wide text-neutral-500">{tr("Workspace", "Рабочее пространство")}</label>
              <select
                value={workspaceId ?? ""}
                onChange={(event) => setWorkspaceId(Number(event.target.value))}
                className="w-full rounded-lg border border-neutral-200 bg-white px-3 py-3 text-sm text-neutral-900 shadow-sm outline-none focus:border-neutral-400"
              >
                <option value="">{tr("Select workspace", "Выберите пространство")}</option>
                {visibleWorkspaces.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.is_default ? `${item.name} (${tr("Default", "По умолчанию")})` : item.name}
                  </option>
                ))}
              </select>
            </div>
            <div className="space-y-2">
              <label className="text-xs font-semibold uppercase tracking-wide text-neutral-500">{tr("Account name", "Название аккаунта")}</label>
              <input
                className="w-full rounded-lg border border-neutral-200 bg-white px-3 py-3 text-sm text-neutral-900 shadow-sm outline-none focus:border-neutral-400"
                value={accountName}
                onChange={(event) => setAccountName(event.target.value)}
                required
              />
            </div>
            <div className="space-y-2">
              <label className="text-xs font-semibold uppercase tracking-wide text-neutral-500">{tr("Login", "Логин")}</label>
              <input
                className="w-full rounded-lg border border-neutral-200 bg-white px-3 py-3 text-sm text-neutral-900 shadow-sm outline-none focus:border-neutral-400"
                value={login}
                onChange={(event) => setLogin(event.target.value)}
                required
              />
            </div>
            <div className="space-y-2">
              <label className="text-xs font-semibold uppercase tracking-wide text-neutral-500">{tr("Password", "Пароль")}</label>
              <input
                type="password"
                className="w-full rounded-lg border border-neutral-200 bg-white px-3 py-3 text-sm text-neutral-900 shadow-sm outline-none focus:border-neutral-400"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                required
              />
            </div>
            <div className="space-y-2">
              <label className="text-xs font-semibold uppercase tracking-wide text-neutral-500">{tr("MMR (optional)", "MMR (необязательно)")}</label>
              <input
                type="number"
                className="w-full rounded-lg border border-neutral-200 bg-white px-3 py-3 text-sm text-neutral-900 shadow-sm outline-none focus:border-neutral-400"
                value={mmr}
                onChange={(event) => setMmr(event.target.value)}
                min={0}
              />
            </div>
            <div className="space-y-2 md:col-span-2">
              <label className="text-xs font-semibold uppercase tracking-wide text-neutral-500">{tr("maFile JSON", "JSON maFile")}</label>
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
                  {tr("Upload maFile", "Загрузить maFile")}
                </button>
                <span>{tr("Paste JSON directly or upload the .maFile.", "Вставьте JSON напрямую или загрузите .maFile.")}</span>
              </div>
            </div>
          </div>

          <div className="flex flex-wrap gap-3">
            <button
              className="rounded-lg bg-neutral-900 px-4 py-3 text-sm font-semibold text-white shadow-sm transition hover:bg-neutral-800 disabled:opacity-60"
              type="submit"
              disabled={submitting}
            >
              {submitting ? tr("Creating...", "Создаём...") : tr("Create account", "Создать аккаунт")}
            </button>
            <button
              type="button"
              onClick={() => setBulkMode((prev) => !prev)}
              className="rounded-lg border border-neutral-200 px-4 py-3 text-sm font-semibold text-neutral-700 transition hover:bg-neutral-100"
            >
              {bulkMode ? tr("Hide bulk upload", "Скрыть массовую загрузку") : tr("Bulk upload", "Массовая загрузка")}
            </button>
          </div>
        </form>
      </div>

      {bulkMode && (
        <div className="rounded-2xl border border-neutral-200 bg-white p-6 shadow-sm shadow-neutral-200/70">
          <div className="mb-4">
            <h3 className="text-lg font-semibold text-neutral-900">
              {tr("Bulk upload accounts", "Массовая загрузка аккаунтов")}
            </h3>
            <p className="text-sm text-neutral-500">
              {tr(
                "Paste login:password per line and upload maFiles. Account name defaults to login.",
                "Вставьте логин:пароль построчно и загрузите maFile. Название аккаунта = логин.",
              )}
            </p>
          </div>

          {bulkStatus ? (
            <div
              className={`mb-4 rounded-xl border px-4 py-3 text-sm ${
                bulkStatus.isError
                  ? "border-red-200 bg-red-50 text-red-700"
                  : "border-emerald-200 bg-emerald-50 text-emerald-700"
              }`}
            >
              {bulkStatus.message}
            </div>
          ) : null}

          <div className="grid gap-4">
            <textarea
              className="min-h-[140px] w-full rounded-lg border border-neutral-200 bg-white px-3 py-3 text-sm text-neutral-900 shadow-sm outline-none focus:border-neutral-400"
              placeholder={tr("login:password (one per line)", "логин:пароль (по одному на строку)")}
              value={bulkCredentials}
              onChange={(event) => setBulkCredentials(event.target.value)}
            />
            <div className="flex flex-wrap items-center gap-3 text-xs text-neutral-500">
              <input
                ref={bulkMafileInputRef}
                type="file"
                multiple
                accept=".maFile,.json,application/json"
                className="hidden"
                onChange={handleBulkMafileChange}
              />
              <button
                type="button"
                onClick={() => bulkMafileInputRef.current?.click()}
                className="rounded-lg border border-neutral-200 px-3 py-2 text-xs font-semibold text-neutral-700 hover:bg-neutral-100"
              >
                {tr("Upload maFiles", "Загрузить maFile")}
              </button>
              <span>
                {tr(
                  `Matched maFiles: ${Object.keys(bulkMafileMap).length}`,
                  `Совпадений maFile: ${Object.keys(bulkMafileMap).length}`,
                )}
              </span>
            </div>
            {bulkMafileErrors.length ? (
              <div className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-700">
                {bulkMafileErrors.join("; ")}
              </div>
            ) : null}
            <div className="flex flex-wrap gap-3">
              <button
                type="button"
                onClick={handleBulkSubmit}
                disabled={bulkSubmitting}
                className="rounded-lg bg-neutral-900 px-4 py-3 text-sm font-semibold text-white shadow-sm transition hover:bg-neutral-800 disabled:opacity-60"
              >
                {bulkSubmitting ? tr("Uploading...", "Загружаем...") : tr("Create accounts", "Создать аккаунты")}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default AddAccountPage;
