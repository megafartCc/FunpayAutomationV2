import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { api, ChatItem, ChatMessageItem } from "../../services/api";
import { useWorkspace } from "../../context/WorkspaceContext";

const formatTime = (value?: string | null) => {
  if (!value) return "";
  const dt = new Date(value);
  if (Number.isNaN(dt.getTime())) return value;
  return dt.toLocaleString();
};

const CHAT_CACHE_VERSION = "v1";
const CHAT_LIST_CACHE_TTL_MS = 30_000;
const CHAT_HISTORY_CACHE_TTL_MS = 90_000;

type CacheEnvelope<T> = {
  ts: number;
  items: T[];
};

const chatListCacheKey = (workspaceId: number) => `chat:list:${CHAT_CACHE_VERSION}:${workspaceId}`;
const chatHistoryCacheKey = (workspaceId: number, chatId: number) =>
  `chat:history:${CHAT_CACHE_VERSION}:${workspaceId}:${chatId}`;

const readCache = <T,>(key: string, ttlMs: number): T[] | null => {
  try {
    const raw = window.localStorage.getItem(key);
    if (!raw) return null;
    const payload = JSON.parse(raw) as CacheEnvelope<T>;
    if (!payload || typeof payload.ts !== "number" || !Array.isArray(payload.items)) return null;
    if (Date.now() - payload.ts > ttlMs) return null;
    return payload.items;
  } catch {
    return null;
  }
};

const writeCache = <T,>(key: string, items: T[]) => {
  try {
    const payload: CacheEnvelope<T> = { ts: Date.now(), items };
    window.localStorage.setItem(key, JSON.stringify(payload));
  } catch {
    // ignore cache errors
  }
};

const getLastServerMessageId = (items: ChatMessageItem[]) => {
  for (let i = items.length - 1; i >= 0; i -= 1) {
    const item = items[i];
    if (item.message_type === "pending") continue;
    if (typeof item.id === "number" && item.id > 0) return item.id;
  }
  return 0;
};

const stripPendingIfConfirmed = (items: ChatMessageItem[], incoming: ChatMessageItem[]) => {
  if (!incoming.length) return items;
  const incomingText = new Set(
    incoming
      .filter((msg) => msg.by_bot || msg.author === "You")
      .map((msg) => (msg.text || "").trim())
      .filter(Boolean),
  );
  if (!incomingText.size) return items;
  return items.filter(
    (msg) => msg.message_type !== "pending" || !incomingText.has((msg.text || "").trim()),
  );
};

const dedupeMessages = (items: ChatMessageItem[]) => {
  const seen = new Set<string>();
  const result: ChatMessageItem[] = [];
  for (const item of items) {
    const key = item.message_id && item.message_id > 0 ? `m:${item.message_id}` : `id:${item.id}`;
    if (seen.has(key)) continue;
    seen.add(key);
    result.push(item);
  }
  return result;
};

const parseChatTime = (value?: string | null) => {
  if (!value) return 0;
  const dt = new Date(value);
  if (Number.isNaN(dt.getTime())) return 0;
  return dt.getTime();
};

const getMaxChatTime = (items: ChatItem[]) =>
  items.reduce((max, item) => Math.max(max, parseChatTime(item.last_message_time)), 0);

const mergeChatUpdates = (prev: ChatItem[], incoming: ChatItem[]) => {
  if (!incoming.length) return prev;
  const updatedIds = new Set<number>();
  for (const chat of incoming) {
    updatedIds.add(chat.chat_id);
  }
  const updated = incoming
    .slice()
    .sort((a, b) => parseChatTime(b.last_message_time) - parseChatTime(a.last_message_time));
  const remaining = prev.filter((chat) => !updatedIds.has(chat.chat_id));
  return [...updated, ...remaining];
};

const ChatsPage: React.FC = () => {
  const { selectedId: selectedWorkspaceId } = useWorkspace();
  const workspaceId = selectedWorkspaceId === "all" ? null : (selectedWorkspaceId as number);

  const [searchParams] = useSearchParams();
  const queryFromUrl = searchParams.get("q") || "";
  const [chatSearch, setChatSearch] = useState(queryFromUrl);
  const [chats, setChats] = useState<ChatItem[]>([]);
  const [chatListLoading, setChatListLoading] = useState(false);
  const [chatLoading, setChatLoading] = useState(false);
  const [selectedChatId, setSelectedChatId] = useState<number | null>(null);
  const [messages, setMessages] = useState<ChatMessageItem[]>([]);
  const [draft, setDraft] = useState("");
  const [status, setStatus] = useState<string | null>(null);
  const messagesRef = useRef<ChatMessageItem[]>([]);
  const listSinceRef = useRef<string | null>(null);
  const hasLoadedChatsRef = useRef(false);
  const historyRequestRef = useRef<{ seq: number; chatId: number | null }>({ seq: 0, chatId: null });

  useEffect(() => {
    messagesRef.current = messages;
  }, [messages]);

  useEffect(() => {
    listSinceRef.current = null;
    hasLoadedChatsRef.current = false;
  }, [workspaceId]);

  useEffect(() => {
    setChatSearch(queryFromUrl);
  }, [queryFromUrl]);

  const ensureSelection = useCallback((items: ChatItem[]) => {
    setSelectedChatId((current) => {
      if (!items.length) return null;
      if (current && items.some((chat) => chat.chat_id === current)) return current;
      return items[0]?.chat_id ?? null;
    });
  }, []);

  const loadChats = useCallback(
    async (query?: string, options?: { silent?: boolean; incremental?: boolean }) => {
      if (!workspaceId) {
        setChats([]);
        setSelectedChatId(null);
        setMessages([]);
        setStatus("Select a workspace to view chats.");
        listSinceRef.current = null;
        hasLoadedChatsRef.current = false;
        return;
      }
      const trimmedQuery = query?.trim() || "";
      const cacheKey = trimmedQuery ? null : chatListCacheKey(workspaceId);
      const cached = cacheKey ? readCache<ChatItem>(cacheKey, CHAT_LIST_CACHE_TTL_MS) : null;
      if (cached && !hasLoadedChatsRef.current) {
        setChats(cached);
        setStatus(null);
        ensureSelection(cached);
        hasLoadedChatsRef.current = true;
        const cachedMax = getMaxChatTime(cached);
        if (cachedMax > 0) {
          listSinceRef.current = new Date(cachedMax).toISOString();
        }
      }
      const canIncremental = Boolean(options?.incremental && !trimmedQuery && listSinceRef.current);
      const silent = options?.silent || Boolean(cached) || (options?.incremental && hasLoadedChatsRef.current);
      if (!silent) {
        setChatListLoading(true);
      }
      try {
        const since = canIncremental ? listSinceRef.current || undefined : undefined;
        const res = await api.listChats(workspaceId, trimmedQuery || undefined, 300, since);
        const items = res.items || [];
        if (canIncremental) {
          if (items.length) {
            setChats((prev) => {
              const merged = mergeChatUpdates(prev, items);
              if (cacheKey) {
                writeCache(cacheKey, merged);
              }
              ensureSelection(merged);
              return merged;
            });
            const nextMax = getMaxChatTime(items);
            if (nextMax > 0) {
              const currentMax = listSinceRef.current ? Date.parse(listSinceRef.current) : 0;
              const finalMax = Math.max(currentMax, nextMax);
              listSinceRef.current = new Date(finalMax).toISOString();
            }
          }
          return;
        }
        setChats(items);
        setStatus(null);
        ensureSelection(items);
        hasLoadedChatsRef.current = true;
        const maxTs = getMaxChatTime(items);
        if (maxTs > 0) {
          listSinceRef.current = new Date(maxTs).toISOString();
        }
        if (cacheKey) {
          writeCache(cacheKey, items);
        }
      } catch (err) {
        if (!silent) {
          const message = (err as { message?: string })?.message || "Failed to load chats.";
          setStatus(message);
        }
      } finally {
        if (!silent) {
          setChatListLoading(false);
        }
      }
    },
    [workspaceId, ensureSelection],
  );

  const loadHistory = useCallback(
    async (chatId: number | null, options?: { silent?: boolean; incremental?: boolean }) => {
      if (!workspaceId || !chatId) {
        setMessages([]);
        historyRequestRef.current = { seq: historyRequestRef.current.seq + 1, chatId: null };
        return;
      }
      const seq = historyRequestRef.current.seq + 1;
      historyRequestRef.current = { seq, chatId };

      const cacheKey = chatHistoryCacheKey(workspaceId, chatId);
      const cached = options?.incremental ? null : readCache<ChatMessageItem>(cacheKey, CHAT_HISTORY_CACHE_TTL_MS);
      if (cached) {
        setMessages(cached);
      } else if (!options?.incremental) {
        setMessages([]);
      }
      const silent = options?.silent || Boolean(cached) || options?.incremental;
      if (!silent) {
        setChatLoading(true);
      }
      try {
        const baseItems = cached ?? messagesRef.current;
        const lastServerId = getLastServerMessageId(baseItems);
        if ((options?.incremental || cached) && lastServerId > 0) {
          const res = await api.getChatHistory(chatId, workspaceId, 200, lastServerId);
          const incoming = res.items || [];
          if (historyRequestRef.current.seq !== seq || historyRequestRef.current.chatId !== chatId) return;
          if (incoming.length) {
            const cleaned = stripPendingIfConfirmed(messagesRef.current, incoming);
            const merged = dedupeMessages([...cleaned, ...incoming]);
            setMessages(merged);
            writeCache(cacheKey, merged.slice(-100));
          }
          setChats((prev) =>
            prev.map((chat) => (chat.chat_id === chatId ? { ...chat, unread: 0 } : chat)),
          );
          return;
        }
        const res = await api.getChatHistory(chatId, workspaceId, 300);
        const items = res.items || [];
        if (historyRequestRef.current.seq !== seq || historyRequestRef.current.chatId !== chatId) return;
        setMessages(items);
        writeCache(cacheKey, items.slice(-100));
        setChats((prev) =>
          prev.map((chat) => (chat.chat_id === chatId ? { ...chat, unread: 0 } : chat)),
        );
      } catch (err) {
        if (!silent && historyRequestRef.current.seq === seq && historyRequestRef.current.chatId === chatId) {
          const message = (err as { message?: string })?.message || "Failed to load chat history.";
          setStatus(message);
        }
      } finally {
        if (!silent && historyRequestRef.current.seq === seq && historyRequestRef.current.chatId === chatId) {
          setChatLoading(false);
        }
      }
    },
    [workspaceId],
  );

  useEffect(() => {
    void loadChats(chatSearch);
  }, [loadChats, workspaceId]);

  useEffect(() => {
    const handle = window.setTimeout(() => {
      void loadChats(chatSearch);
    }, 350);
    return () => window.clearTimeout(handle);
  }, [chatSearch, loadChats]);

  useEffect(() => {
    if (!workspaceId) return undefined;
    if (chatSearch.trim()) return undefined;
    const handle = window.setInterval(() => {
      void loadChats(chatSearch, { silent: true, incremental: true });
    }, 12_000);
    return () => window.clearInterval(handle);
  }, [workspaceId, chatSearch, loadChats]);

  useEffect(() => {
    void loadHistory(selectedChatId);
  }, [selectedChatId, loadHistory]);

  useEffect(() => {
    if (!workspaceId || !selectedChatId) return undefined;
    const handle = window.setInterval(() => {
      void loadHistory(selectedChatId, { silent: true, incremental: true });
    }, 6_000);
    return () => window.clearInterval(handle);
  }, [workspaceId, selectedChatId, loadHistory]);

  const selectedChat = useMemo(
    () => chats.find((chat) => chat.chat_id === selectedChatId) || null,
    [chats, selectedChatId],
  );

  const handleSelectChat = (chatId: number) => {
    setSelectedChatId(chatId);
  };

  const handleSend = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!selectedChatId) return;
    if (!workspaceId) return;
    const text = draft.trim();
    if (!text) return;
    const optimistic: ChatMessageItem = {
      id: Date.now(),
      message_id: 0,
      chat_id: selectedChatId,
      author: "You",
      text,
      sent_time: new Date().toISOString(),
      by_bot: 1,
      message_type: "pending",
      workspace_id: workspaceId,
    };
    const historyKey = chatHistoryCacheKey(workspaceId, selectedChatId);
    setMessages((prev) => {
      const next = [...prev, optimistic];
      writeCache(historyKey, next.slice(-100));
      return next;
    });
    setDraft("");
    try {
      await api.sendChatMessage(selectedChatId, text, workspaceId);
      setChats((prev) => {
        const next = prev.map((chat) =>
          chat.chat_id === selectedChatId
            ? {
                ...chat,
                last_message_text: text,
                last_message_time: new Date().toISOString(),
                unread: 0,
              }
            : chat,
        );
        writeCache(chatListCacheKey(workspaceId), next);
        return next;
      });
    } catch (err) {
      const message = (err as { message?: string })?.message || "Failed to send message.";
      setStatus(message);
    }
  };

  return (
    <div className="space-y-6">
      <div className="rounded-2xl border border-neutral-200 bg-white p-6 shadow-sm shadow-neutral-200/70">
        <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
          <div>
            <h3 className="text-lg font-semibold text-neutral-900">Chats</h3>
            <p className="text-sm text-neutral-500">Workspace scoped chat inbox.</p>
          </div>
          <button
            className="rounded-lg border border-neutral-200 bg-neutral-50 px-3 py-2 text-xs text-neutral-600"
            onClick={() => loadChats(chatSearch, { silent: true, incremental: !chatSearch.trim() })}
          >
            Refresh
          </button>
        </div>
        {status ? (
          <div className="mb-4 rounded-xl border border-neutral-200 bg-neutral-50 px-4 py-3 text-sm text-neutral-600">
            {status}
          </div>
        ) : null}

        <div className="grid gap-6 lg:grid-cols-[320px_1fr]">
          <div className="rounded-xl border border-neutral-200 bg-neutral-50 p-4">
            <div className="flex items-center gap-2">
              <input
                className="w-full rounded-lg border border-neutral-200 bg-white px-3 py-2 text-sm text-neutral-700 outline-none placeholder:text-neutral-400"
                placeholder="Search chats"
                value={chatSearch}
                onChange={(event) => setChatSearch(event.target.value)}
              />
              <button
                className="rounded-lg border border-neutral-200 bg-white px-3 py-2 text-xs font-semibold text-neutral-600"
                type="button"
                onClick={() => loadChats(chatSearch)}
              >
                Update
              </button>
            </div>
            <div className="mt-4 max-h-[520px] space-y-2 overflow-y-auto pr-1">
              {chatListLoading ? (
                <div className="rounded-xl border border-dashed border-neutral-200 bg-white px-4 py-6 text-center text-sm text-neutral-500">
                  Loading chats...
                </div>
              ) : chats.length ? (
                chats.map((chat) => {
                  const isActive = chat.chat_id === selectedChatId;
                  return (
                    <button
                      key={chat.chat_id}
                      type="button"
                      onClick={() => handleSelectChat(chat.chat_id)}
                      className={`w-full rounded-xl border px-3 py-3 text-left transition ${
                        isActive
                          ? "border-neutral-900 bg-neutral-900 text-white"
                          : "border-neutral-200 bg-white text-neutral-700 hover:border-neutral-300"
                      }`}
                    >
                      <div className="flex items-center justify-between gap-3">
                        <div className="truncate text-sm font-semibold">
                          {chat.name || "Buyer"}
                        </div>
                        <span className={`text-[11px] ${isActive ? "text-neutral-200" : "text-neutral-400"}`}>
                          {formatTime(chat.last_message_time)}
                        </span>
                      </div>
                      <p className={`mt-2 truncate text-xs ${isActive ? "text-neutral-300" : "text-neutral-500"}`}>
                        {chat.last_message_text || "No messages yet."}
                      </p>
                      <div className="mt-2 flex flex-wrap gap-2">
                        {chat.unread ? (
                          <span
                            className={`inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-semibold ${
                              isActive ? "bg-white/10 text-white" : "bg-amber-100 text-amber-700"
                            }`}
                          >
                            New
                          </span>
                        ) : null}
                      </div>
                    </button>
                  );
                })
              ) : (
                <div className="rounded-xl border border-dashed border-neutral-200 bg-white px-4 py-6 text-center text-sm text-neutral-500">
                  No chats found.
                </div>
              )}
            </div>
          </div>

          <div className="flex flex-col gap-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <div className="text-lg font-semibold text-neutral-900">
                  {selectedChat ? selectedChat.name : "Select a chat"}
                </div>
                <div className="text-xs text-neutral-500">
                  {selectedChat ? `Chat ID: ${selectedChat.id}` : "Pick a buyer to open the conversation."}
                </div>
              </div>
              <button
                className="rounded-lg border border-neutral-200 bg-white px-3 py-2 text-xs font-semibold text-neutral-600"
                type="button"
                onClick={() => loadHistory(selectedChatId)}
              >
                Load history
              </button>
            </div>

            <div className="flex-1 space-y-3 overflow-y-auto rounded-xl border border-neutral-200 bg-neutral-50 p-4">
              {chatLoading ? (
                <div className="rounded-xl border border-dashed border-neutral-200 bg-white px-4 py-6 text-center text-sm text-neutral-500">
                  Loading messages...
                </div>
              ) : messages.length ? (
                messages.map((message) => {
                  const isBot = Boolean(message.by_bot);
                  return (
                    <div
                      key={`${message.id}-${message.message_id}`}
                      className={`max-w-[78%] rounded-xl border px-3 py-2 text-sm ${
                        isBot
                          ? "ml-auto border-neutral-900 bg-neutral-900 text-white"
                          : "border-neutral-200 bg-white text-neutral-700"
                      }`}
                    >
                      <div className={`text-[11px] ${isBot ? "text-neutral-200" : "text-neutral-400"}`}>
                        {[message.author, message.message_type, formatTime(message.sent_time)].filter(Boolean).join(" | ")}
                      </div>
                      <div className="mt-2 whitespace-pre-wrap">{message.text || "(empty)"}</div>
                    </div>
                  );
                })
              ) : selectedChatId ? (
                <div className="rounded-xl border border-dashed border-neutral-200 bg-white px-4 py-6 text-center text-sm text-neutral-500">
                  No stored messages yet. New messages will appear automatically.
                </div>
              ) : (
                <div className="rounded-xl border border-dashed border-neutral-200 bg-white px-4 py-6 text-center text-sm text-neutral-500">
                  Select a chat to view messages.
                </div>
              )}
            </div>

            <form className="flex flex-col gap-3 sm:flex-row" onSubmit={handleSend}>
              <textarea
                className="min-h-[88px] w-full rounded-xl border border-neutral-200 bg-white px-3 py-2 text-sm text-neutral-700 outline-none placeholder:text-neutral-400"
                placeholder={selectedChat ? "Type a message..." : "Select a chat first"}
                value={draft}
                onChange={(event) => setDraft(event.target.value)}
                disabled={!selectedChat}
              />
              <button
                className="h-[48px] rounded-xl bg-neutral-900 px-4 text-sm font-semibold text-white transition hover:bg-neutral-800 disabled:cursor-not-allowed disabled:bg-neutral-300"
                type="submit"
                disabled={!selectedChat || !draft.trim()}
              >
                Send
              </button>
            </form>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ChatsPage;
