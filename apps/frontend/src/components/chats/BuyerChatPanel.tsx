import React, { useEffect, useMemo, useRef, useState } from "react";

import { api } from "../../services/api";
import type { ChatItem, ChatMessageItem } from "../../services/api";

type BuyerChatPanelProps = {
  open: boolean;
  buyer?: string | null;
  workspaceId?: number | null;
  onClose: () => void;
};

const normalizeBuyer = (value?: string | null) => (value || "").trim().toLowerCase();

const formatTime = (value?: string | number | null) => {
  if (!value) return "";
  const raw = String(value).trim();
  if (!raw) return "";
  const normalized = /[zZ]|[+-]\d{2}:?\d{2}$/.test(raw) ? raw : raw.replace(" ", "T");
  const ts = Date.parse(normalized);
  if (Number.isNaN(ts)) return raw;
  return new Date(ts).toLocaleString("ru-RU", { timeZone: "Europe/Moscow" });
};

const BuyerChatPanel: React.FC<BuyerChatPanelProps> = ({ open, buyer, workspaceId, onClose }) => {
  const [chat, setChat] = useState<ChatItem | null>(null);
  const [messages, setMessages] = useState<ChatMessageItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [sendBusy, setSendBusy] = useState(false);
  const [draft, setDraft] = useState("");
  const [error, setError] = useState<string | null>(null);
  const messageEndRef = useRef<HTMLDivElement | null>(null);
  const requestRef = useRef(0);

  const normalizedBuyer = useMemo(() => normalizeBuyer(buyer), [buyer]);

  useEffect(() => {
    if (!open) return;
    if (!normalizedBuyer) {
      setChat(null);
      setMessages([]);
      setError(null);
      return;
    }
    if (!workspaceId) {
      setChat(null);
      setMessages([]);
      setError("Выберите рабочее пространство, чтобы открыть чат.");
      return;
    }
    let cancelled = false;
    const requestId = requestRef.current + 1;
    requestRef.current = requestId;
    setLoading(true);
    setError(null);
    setChat(null);
    setMessages([]);
    const load = async () => {
      try {
        const res = await api.listChats(workspaceId, buyer || undefined, 50);
        if (cancelled || requestRef.current !== requestId) return;
        const exact =
          res.items.find((item) => normalizeBuyer(item.name) === normalizedBuyer) ?? res.items[0] ?? null;
        setChat(exact ?? null);
        if (!exact) {
          setLoading(false);
          return;
        }
        setHistoryLoading(true);
        const history = await api.getChatHistory(exact.chat_id, workspaceId, 120);
        if (cancelled || requestRef.current !== requestId) return;
        setMessages(history.items);
        setHistoryLoading(false);
        setLoading(false);
      } catch (err) {
        if (cancelled || requestRef.current !== requestId) return;
        setError("Не удалось загрузить чат.");
        setLoading(false);
        setHistoryLoading(false);
      }
    };
    void load();
    return () => {
      cancelled = true;
    };
  }, [open, normalizedBuyer, buyer, workspaceId]);

  useEffect(() => {
    if (!open) return;
    messageEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, open]);

  const handleSend = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!chat || !draft.trim() || sendBusy) return;
    const text = draft.trim();
    const optimistic: ChatMessageItem = {
      id: Date.now(),
      message_id: 0,
      chat_id: chat.chat_id,
      author: "You",
      text,
      sent_time: new Date().toISOString(),
      by_bot: 1,
      message_type: "pending",
    };
    setMessages((prev) => [...prev, optimistic]);
    setDraft("");
    setSendBusy(true);
    try {
      await api.sendChatMessage(chat.chat_id, text, workspaceId);
    } catch {
      setError("Сообщение не отправлено.");
    } finally {
      setSendBusy(false);
    }
  };

  if (!open) return null;

  return (
    <>
      <div className="fixed inset-0 z-40 bg-neutral-900/40" onClick={onClose} />
      <aside className="fixed right-0 top-0 z-50 flex h-full w-full max-w-md flex-col border-l border-neutral-200 bg-white shadow-xl">
        <div className="flex items-center justify-between border-b border-neutral-200 px-5 py-4">
          <div>
            <div className="text-xs font-semibold uppercase tracking-wide text-neutral-400">Чат покупателя</div>
            <div className="text-base font-semibold text-neutral-900">{buyer || "Покупатель"}</div>
            {chat?.chat_id ? (
              <div className="text-xs text-neutral-500">ID чата: {chat.chat_id}</div>
            ) : (
              <div className="text-xs text-neutral-400">Чат пока не найден.</div>
            )}
          </div>
          <button
            type="button"
            className="rounded-full border border-neutral-200 px-3 py-1 text-xs font-semibold text-neutral-600 hover:bg-neutral-50"
            onClick={onClose}
          >
            Закрыть
          </button>
        </div>
        <div className="flex min-h-0 flex-1 flex-col gap-3 px-5 py-4">
          {loading || historyLoading ? (
            <div className="rounded-xl border border-dashed border-neutral-200 bg-white px-4 py-6 text-center text-sm text-neutral-500">
              Загружаем переписку...
            </div>
          ) : error ? (
            <div className="rounded-xl border border-dashed border-rose-200 bg-rose-50 px-4 py-6 text-center text-sm text-rose-600">
              {error}
            </div>
          ) : messages.length ? (
            <div className="flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto pr-1">
              {messages.map((message) => {
                const isBot = Boolean(message.by_bot);
                return (
                  <div
                    key={`${message.id}-${message.message_id}`}
                    className={`w-fit max-w-[80%] rounded-xl border px-3 py-2 text-sm break-words ${
                      isBot
                        ? "ml-auto self-end border-neutral-900 bg-neutral-900 text-white"
                        : "self-start border-neutral-200 bg-white text-neutral-700"
                    }`}
                  >
                    <div className={`text-[11px] ${isBot ? "text-neutral-200" : "text-neutral-400"}`}>
                      {[message.author, message.message_type, formatTime(message.sent_time)].filter(Boolean).join(" | ")}
                    </div>
                    <div className="mt-2 whitespace-pre-wrap break-words">{message.text || "(пусто)"}</div>
                  </div>
                );
              })}
              <div ref={messageEndRef} />
            </div>
          ) : chat ? (
            <div className="rounded-xl border border-dashed border-neutral-200 bg-white px-4 py-6 text-center text-sm text-neutral-500">
              Пока нет сообщений.
            </div>
          ) : (
            <div className="rounded-xl border border-dashed border-neutral-200 bg-white px-4 py-6 text-center text-sm text-neutral-500">
              Чат для этого покупателя не найден.
            </div>
          )}
          <form className="mt-auto flex flex-col gap-3" onSubmit={handleSend}>
            <textarea
              className="min-h-[90px] w-full rounded-xl border border-neutral-200 bg-white px-3 py-2 text-sm text-neutral-700 outline-none placeholder:text-neutral-400"
              placeholder={chat ? "Напишите сообщение..." : "Сначала выберите чат"}
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              disabled={!chat}
            />
            <button
              className="h-[46px] rounded-xl bg-neutral-900 px-4 text-sm font-semibold text-white transition hover:bg-neutral-800 disabled:cursor-not-allowed disabled:bg-neutral-300"
              type="submit"
              disabled={!chat || !draft.trim() || sendBusy}
            >
              Отправить
            </button>
          </form>
        </div>
      </aside>
    </>
  );
};

export default BuyerChatPanel;
