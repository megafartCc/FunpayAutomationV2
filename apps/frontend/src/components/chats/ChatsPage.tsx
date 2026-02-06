import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";

import { api } from "../../services/api";
import type { ActiveRentalItem, ChatItem, ChatMessageItem } from "../../services/api";
import { useWorkspace } from "../../context/WorkspaceContext";

const normalizeUtcTime = (raw: string) => {
  const trimmed = raw.trim();
  if (!trimmed) return trimmed;
  if (/[zZ]|[+-]\d{2}:?\d{2}$/.test(trimmed)) return trimmed;
  if (/^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}/.test(trimmed)) {
    return `${trimmed.replace(" ", "T")}Z`;
  }
  return trimmed;
};

const parseUtcTimestamp = (value?: string | number | null) => {
  if (value === null || value === undefined || value === "") return null;
  const raw = String(value);
  const normalized = normalizeUtcTime(raw);
  const ts = Date.parse(normalized);
  if (Number.isNaN(ts)) return null;
  return new Date(ts);
};

const formatTime = (value?: string | number | null) => {
  const dt = parseUtcTimestamp(value);
  if (!dt) return value ? String(value) : "";
  return dt.toLocaleString("ru-RU", { timeZone: "Europe/Moscow" });
};

const isAdminCommand = (text?: string | null, byBot?: number | null) => {
  if (!text || byBot) return false;
  const lowered = text.toLowerCase();
  return lowered.includes("!админ") || lowered.includes("!admin");
};

const normalizeBuyer = (value?: string | null) => (value || "").trim().toLowerCase();

const ADMIN_REPLACE_LABEL = "Заменить аккаунт (админ)";

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
  const dt = parseUtcTimestamp(value);
  return dt ? dt.getTime() : 0;
};

const statusPill = (status?: string | null) => {
  const lower = (status || "").toLowerCase();
  if (lower.includes("frozen")) return { className: "bg-slate-100 text-slate-700", label: "Заморожено" };
  if (lower.includes("demo")) return { className: "bg-amber-50 text-amber-700", label: "Демо герой" };
  if (lower.includes("bot")) return { className: "bg-amber-50 text-amber-700", label: "Матч с ботом" };
  if (lower.includes("custom"))
    return { className: "bg-amber-50 text-amber-600", label: "Кастомная игра" };
  if (lower.includes("match")) return { className: "bg-emerald-50 text-emerald-600", label: "В матче" };
  if (lower.includes("game")) return { className: "bg-amber-50 text-amber-600", label: "В игре" };
  if (lower.includes("online") || lower === "1" || lower === "true") return { className: "bg-emerald-50 text-emerald-600", label: "Онлайн" };
  if (lower.includes("idle") || lower.includes("away")) return { className: "bg-amber-50 text-amber-600", label: "Неактивен" };
  if (lower.includes("off") || lower === "" || lower === "0") return { className: "bg-rose-50 text-rose-600", label: "Оффлайн" };
  return { className: "bg-neutral-100 text-neutral-600", label: status || "Неизвестно" };
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
  const { chatId: chatIdParam } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const { selectedId: selectedWorkspaceId } = useWorkspace();
  const workspaceId = selectedWorkspaceId === "all" ? null : (selectedWorkspaceId as number);
  const routeChatId = useMemo(() => {
    if (!chatIdParam) return null;
    const parsed = Number(chatIdParam);
    return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
  }, [chatIdParam]);

  const [chatSearch, setChatSearch] = useState(() => {
    if (typeof window === "undefined") return "";
    const params = new URLSearchParams(window.location.search || "");
    return params.get("q") || "";
  });
  const [chats, setChats] = useState<ChatItem[]>([]);
  const [chatListLoading, setChatListLoading] = useState(false);
  const [chatLoading, setChatLoading] = useState(false);
  const [selectedChatId, setSelectedChatId] = useState<number | null>(() => routeChatId);
  const [messages, setMessages] = useState<ChatMessageItem[]>([]);
  const [draft, setDraft] = useState("");
  const [status, setStatus] = useState<string | null>(null);
  const [rentals, setRentals] = useState<ActiveRentalItem[]>([]);
  const [rentalsLoading, setRentalsLoading] = useState(false);
  const [selectedRentalId, setSelectedRentalId] = useState<number | null>(null);
  const [extendHours, setExtendHours] = useState("");
  const [extendMinutes, setExtendMinutes] = useState("");
  const [rentalActionBusy, setRentalActionBusy] = useState(false);
  const [mobileView, setMobileView] = useState<"list" | "chat" | "actions">("list");
  const messagesRef = useRef<ChatMessageItem[]>([]);
  const listSinceRef = useRef<string | null>(null);
  const hasLoadedChatsRef = useRef(false);
  const historyRequestRef = useRef<{ seq: number; chatId: number | null }>({ seq: 0, chatId: null });
  const historyCacheRef = useRef<Map<number, ChatMessageItem[]>>(new Map());
  const historyCacheTimeRef = useRef<Map<number, number>>(new Map());
  const messageListRef = useRef<HTMLDivElement | null>(null);
  const messageEndRef = useRef<HTMLDivElement | null>(null);
  const keepScrollPinnedRef = useRef(true);
  const pendingScrollRef = useRef(false);

  const syncChatRoute = useCallback(
    (chatId: number | null) => {
      if (!chatId) return;
      const nextPath = `/chats/${chatId}${location.search}`;
      if (location.pathname === `/chats/${chatId}`) return;
      navigate(nextPath);
    },
    [navigate, location.pathname, location.search],
  );

  useEffect(() => {
    messagesRef.current = messages;
  }, [messages]);

  useEffect(() => {
    if (!routeChatId) return;
    setSelectedChatId(routeChatId);
  }, [routeChatId]);

  useEffect(() => {
    if (selectedChatId) {
      setMobileView("chat");
    }
  }, [selectedChatId]);

  useEffect(() => {
    listSinceRef.current = null;
    hasLoadedChatsRef.current = false;
    historyCacheRef.current.clear();
    historyCacheTimeRef.current.clear();
  }, [workspaceId]);

  useEffect(() => {
    const handlePopState = () => {
      const params = new URLSearchParams(window.location.search || "");
      setChatSearch(params.get("q") || "");
    };
    window.addEventListener("popstate", handlePopState);
    return () => window.removeEventListener("popstate", handlePopState);
  }, []);

  const ensureSelection = useCallback((items: ChatItem[]) => {
    setSelectedChatId((current) => {
      if (!items.length) return null;

      // Keep the user's current pick even while routing/caching catches up.
      if (current && items.some((chat) => chat.chat_id === current)) return current;

      // If router param matches the refreshed list, honor it next.
      if (routeChatId && items.some((chat) => chat.chat_id === routeChatId)) return routeChatId;

      // Fallback: first chat in list.
      return items[0]?.chat_id ?? null;
    });
  }, [routeChatId]);

  const updateChatPreview = useCallback(
    (chatId: number, items: ChatMessageItem[]) => {
      if (!items.length) return;
      const last = items[items.length - 1];
      if (!last) return;
      setChats((prev) => {
        const next = prev.map((chat) =>
          chat.chat_id === chatId
            ? {
                ...chat,
                last_message_text: last.text || chat.last_message_text,
                last_message_time: last.sent_time || chat.last_message_time,
                unread: 0,
              }
            : chat,
        );
        if (workspaceId && !chatSearch.trim()) {
          writeCache(chatListCacheKey(workspaceId), next);
        }
        return next;
      });
    },
    [workspaceId, chatSearch],
  );

  const loadChats = useCallback(
    async (query?: string, options?: { silent?: boolean; incremental?: boolean }) => {
      if (!workspaceId) {
        setChats([]);
        setSelectedChatId(null);
        setMessages([]);
        setStatus("Выберите рабочее пространство, чтобы открыть чаты.");
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
          const message = (err as { message?: string })?.message || "Не удалось загрузить чаты.";
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

  const persistHistoryCache = useCallback(
    (chatId: number, items: ChatMessageItem[]) => {
      historyCacheRef.current.set(chatId, items);
      historyCacheTimeRef.current.set(chatId, Date.now());
      if (workspaceId) {
        const cacheKey = chatHistoryCacheKey(workspaceId, chatId);
        writeCache(cacheKey, items.slice(-100));
      }
    },
    [workspaceId],
  );

  const loadHistory = useCallback(
    async (
      chatId: number | null,
      options?: { silent?: boolean; incremental?: boolean; updateView?: boolean },
    ) => {
      if (!workspaceId || !chatId) {
        if (options?.updateView !== false) {
          setMessages([]);
          historyRequestRef.current = { seq: historyRequestRef.current.seq + 1, chatId: null };
        }
        return;
      }
      const seq = historyRequestRef.current.seq + 1;
      historyRequestRef.current = { seq, chatId };

      const cacheKey = chatHistoryCacheKey(workspaceId, chatId);
      const memoryCached = options?.incremental ? null : historyCacheRef.current.get(chatId) || null;
      const cached =
        memoryCached ?? (options?.incremental ? null : readCache<ChatMessageItem>(cacheKey, CHAT_HISTORY_CACHE_TTL_MS));
      const shouldUpdateView = options?.updateView !== false;
      if (cached) {
        persistHistoryCache(chatId, cached);
        if (shouldUpdateView) {
          setMessages(cached);
          updateChatPreview(chatId, cached);
        }
      } else if (!options?.incremental && shouldUpdateView) {
        setMessages([]);
      }
      const silent = options?.silent || !shouldUpdateView || Boolean(cached) || options?.incremental;
      if (!silent && shouldUpdateView) {
        setChatLoading(true);
      }
      try {
        const baseItems =
          cached ?? historyCacheRef.current.get(chatId) ?? (shouldUpdateView ? messagesRef.current : []);
        const lastServerId = getLastServerMessageId(baseItems);
        if ((options?.incremental || cached) && lastServerId > 0) {
          const res = await api.getChatHistory(chatId, workspaceId, 200, lastServerId);
          const incoming = res.items || [];
          if (historyRequestRef.current.seq !== seq || historyRequestRef.current.chatId !== chatId) return;
          if (incoming.length) {
            const cleaned = stripPendingIfConfirmed(baseItems, incoming);
            const merged = dedupeMessages([...cleaned, ...incoming]);
            persistHistoryCache(chatId, merged);
            if (shouldUpdateView) {
              setMessages(merged);
              updateChatPreview(chatId, merged);
            }
          }
          if (shouldUpdateView) {
            setChats((prev) =>
              prev.map((chat) =>
                chat.chat_id === chatId
                  ? { ...chat, unread: 0, admin_unread_count: 0, admin_requested: 0 }
                  : chat,
              ),
            );
          }
          return;
        }
        const res = await api.getChatHistory(chatId, workspaceId, 300);
        const items = res.items || [];
        if (historyRequestRef.current.seq !== seq || historyRequestRef.current.chatId !== chatId) return;
        persistHistoryCache(chatId, items);
        if (shouldUpdateView) {
          setMessages(items);
          updateChatPreview(chatId, items);
          setChats((prev) =>
            prev.map((chat) =>
              chat.chat_id === chatId
                ? { ...chat, unread: 0, admin_unread_count: 0, admin_requested: 0 }
                : chat,
            ),
          );
        }
      } catch (err) {
        if (!silent && historyRequestRef.current.seq === seq && historyRequestRef.current.chatId === chatId) {
          const message = (err as { message?: string })?.message || "Не удалось загрузить историю чата.";
          setStatus(message);
        }
      } finally {
        if (!silent && shouldUpdateView && historyRequestRef.current.seq === seq && historyRequestRef.current.chatId === chatId) {
          setChatLoading(false);
        }
      }
    },
    [persistHistoryCache, workspaceId],
  );

  const loadRentals = useCallback(
    async (silent = false) => {
      if (!workspaceId) {
        setRentals([]);
        return;
      }
      if (!silent) setRentalsLoading(true);
      try {
        const res = await api.listActiveRentals(workspaceId);
        setRentals(res.items || []);
      } catch {
        setRentals([]);
      } finally {
        if (!silent) setRentalsLoading(false);
      }
    },
    [workspaceId],
  );

  useEffect(() => {
    void loadRentals();
  }, [loadRentals]);

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
    if (!workspaceId) return undefined;
    const handle = window.setInterval(() => {
      void loadRentals(true);
    }, 15_000);
    return () => window.clearInterval(handle);
  }, [workspaceId, loadRentals]);

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

  useEffect(() => {
    if (!workspaceId) return undefined;
    const handle = window.setInterval(() => {
      const cachedIds = Array.from(historyCacheRef.current.keys());
      if (!cachedIds.length) return;
      cachedIds.forEach((chatId) => {
        if (chatId === selectedChatId) return;
        void loadHistory(chatId, { silent: true, incremental: true, updateView: false });
      });
    }, 10_000);
    return () => window.clearInterval(handle);
  }, [workspaceId, selectedChatId, loadHistory]);

  useEffect(() => {
    if (!selectedChatId) return;
    pendingScrollRef.current = true;
  }, [selectedChatId]);

  useEffect(() => {
    if (!messageListRef.current || !messageEndRef.current) return;
    if (!messages.length) return;
    if (pendingScrollRef.current || keepScrollPinnedRef.current) {
      pendingScrollRef.current = false;
      messageEndRef.current.scrollIntoView({ block: "end" });
    }
  }, [messages, selectedChatId]);

  const selectedChat = useMemo(
    () => chats.find((chat) => chat.chat_id === selectedChatId) || null,
    [chats, selectedChatId],
  );

  const rentalsByBuyer = useMemo(() => {
    const map = new Map<string, number>();
    rentals.forEach((item) => {
      const key = normalizeBuyer(item.buyer);
      if (!key) return;
      map.set(key, (map.get(key) ?? 0) + 1);
    });
    return map;
  }, [rentals]);

  const buyerKey = useMemo(() => normalizeBuyer(selectedChat?.name), [selectedChat]);
  const rentalsForBuyer = useMemo(() => {
    if (!buyerKey) return [];
    return rentals.filter((item) => normalizeBuyer(item.buyer) === buyerKey);
  }, [rentals, buyerKey]);

  const selectedRental = useMemo(
    () => rentalsForBuyer.find((item) => item.id === selectedRentalId) || null,
    [rentalsForBuyer, selectedRentalId],
  );

  useEffect(() => {
    if (!rentalsForBuyer.length) {
      setSelectedRentalId(null);
      return;
    }
    if (selectedRentalId && rentalsForBuyer.some((item) => item.id === selectedRentalId)) return;
    setSelectedRentalId(rentalsForBuyer[0]?.id ?? null);
  }, [rentalsForBuyer, selectedRentalId]);

  const handleSelectChat = (chatId: number) => {
    setSelectedChatId(chatId);
    setMobileView("chat");
    pendingScrollRef.current = true;
    keepScrollPinnedRef.current = true;
    syncChatRoute(chatId);
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
      const message = (err as { message?: string })?.message || "Не удалось отправить сообщение.";
      setStatus(message);
    }
  };

  const handleExtendRental = async () => {
    if (!selectedRental) {
      setStatus("Сначала выберите активную аренду.");
      return;
    }
    if (!workspaceId) return;
    if (rentalActionBusy) return;
    const hours = Number(extendHours || 0);
    const minutes = Number(extendMinutes || 0);
    if (!Number.isFinite(hours) || !Number.isFinite(minutes) || hours < 0 || minutes < 0) {
      setStatus("Введите корректные часы и минуты.");
      return;
    }
    if (hours * 60 + minutes <= 0) {
      setStatus("Продление должно быть больше 0.");
      return;
    }
    setRentalActionBusy(true);
    try {
      await api.extendAccount(selectedRental.id, hours, minutes, workspaceId);
      setExtendHours("");
      setExtendMinutes("");
      await loadRentals(true);
    } catch (err) {
      const message = (err as { message?: string })?.message || "Не удалось продлить аренду.";
      setStatus(message);
    } finally {
      setRentalActionBusy(false);
    }
  };

  const handleReleaseRental = async () => {
    if (!selectedRental) {
      setStatus("Сначала выберите активную аренду.");
      return;
    }
    if (!workspaceId) return;
    if (rentalActionBusy) return;
    setRentalActionBusy(true);
    try {
      await api.releaseAccount(selectedRental.id, workspaceId);
      await loadRentals(true);
    } catch (err) {
      const message = (err as { message?: string })?.message || "Не удалось завершить аренду.";
      setStatus(message);
    } finally {
      setRentalActionBusy(false);
    }
  };

  const handleRefundRental = async () => {
    if (!selectedRental) {
      setStatus("Сначала выберите активную аренду.");
      return;
    }
    if (!selectedRental.buyer) {
      setStatus("Не удалось определить покупателя для возврата.");
      return;
    }
    if (!workspaceId) return;
    if (rentalActionBusy) return;
    const ok = window.confirm(`Вернуть средства по последнему заказу покупателя ${selectedRental.buyer}?`);
    if (!ok) return;
    setRentalActionBusy(true);
    try {
      const res = await api.refundOrder({
        owner: selectedRental.buyer,
        account_id: selectedRental.id,
        workspace_id: workspaceId,
      });
      setStatus(`Возврат оформлен для заказа #${res.order_id}.`);
      await loadRentals(true);
    } catch (err) {
      const message = (err as { message?: string })?.message || "Не удалось оформить возврат.";
      setStatus(message);
    } finally {
      setRentalActionBusy(false);
    }
  };

  const handleSetFreeze = async (nextFrozen: boolean) => {
    if (!selectedRental) {
      setStatus("Сначала выберите активную аренду.");
      return;
    }
    if (!workspaceId) return;
    if (rentalActionBusy) return;
    setRentalActionBusy(true);
    try {
      await api.freezeRental(selectedRental.id, nextFrozen, workspaceId);
      await loadRentals(true);
    } catch (err) {
      const message = (err as { message?: string })?.message || "Не удалось обновить статус заморозки.";
      setStatus(message);
    } finally {
      setRentalActionBusy(false);
    }
  };

  const handleReplaceRental = async () => {
    if (!workspaceId) {
      setStatus("Выберите рабочее пространство, чтобы заменить аренду.");
      return;
    }
    if (!selectedRental) {
      setStatus("Сначала выберите активную аренду.");
      return;
    }
    if (rentalActionBusy) return;
    setRentalActionBusy(true);
    try {
      await api.replaceRental(selectedRental.id, workspaceId);
      await loadRentals(true);
      if (selectedChatId) {
        await loadHistory(selectedChatId, { silent: true });
      }
    } catch (err) {
      const message = (err as { message?: string })?.message || "Не удалось заменить аренду.";
      setStatus(message);
    } finally {
      setRentalActionBusy(false);
    }
  };

  return (
    <div className="flex h-full min-h-0 flex-col gap-6">
      <div className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-2xl border border-neutral-200 bg-white p-4 shadow-sm shadow-neutral-200/70 sm:p-6">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <div>
            <h3 className="text-lg font-semibold text-neutral-900">Чаты</h3>
            <p className="text-sm text-neutral-500">Чаты выбранного рабочего пространства.</p>
          </div>
          <button
            className="rounded-lg border border-neutral-200 bg-neutral-50 px-3 py-2 text-xs text-neutral-600"
            onClick={() => loadChats(chatSearch, { silent: true, incremental: !chatSearch.trim() })}
          >
            Обновить
          </button>
        </div>
        <div className="mb-4 flex flex-wrap gap-2 lg:hidden">
          {(
            [
              { key: "list", label: "Список чатов" },
              { key: "chat", label: "Сообщения" },
              { key: "actions", label: "Действия" },
            ] as const
          ).map((item) => (
            <button
              key={item.key}
              type="button"
              className={`rounded-full px-3 py-1.5 text-xs font-semibold transition ${
                mobileView === item.key
                  ? "bg-neutral-900 text-white"
                  : "border border-neutral-200 bg-white text-neutral-600 hover:bg-neutral-50"
              }`}
              onClick={() => setMobileView(item.key)}
            >
              {item.label}
            </button>
          ))}
        </div>
        {status ? (
          <div className="mb-4 rounded-xl border border-neutral-200 bg-neutral-50 px-4 py-3 text-sm text-neutral-600">
            {status}
          </div>
        ) : null}

        <div className="grid min-h-0 flex-1 gap-4 lg:grid-cols-[320px_minmax(0,1fr)_320px] lg:gap-6">
          <div
            className={`min-h-0 flex-col rounded-xl border border-neutral-200 bg-neutral-50 p-4 ${
              mobileView === "list" ? "flex" : "hidden"
            } lg:flex`}
          >
            <div className="flex items-center gap-2">
              <input
                className="w-full rounded-lg border border-neutral-200 bg-white px-3 py-2 text-sm text-neutral-700 outline-none placeholder:text-neutral-400"
                placeholder="Поиск чатов"
                value={chatSearch}
                onChange={(event) => setChatSearch(event.target.value)}
              />
              <button
                className="rounded-lg border border-neutral-200 bg-white px-3 py-2 text-xs font-semibold text-neutral-600"
                type="button"
                onClick={() => loadChats(chatSearch)}
              >
                Обновить
              </button>
            </div>
            <div className="mt-4 flex-1 space-y-2 overflow-y-auto pr-1">
              {chatListLoading ? (
                <div className="rounded-xl border border-dashed border-neutral-200 bg-white px-4 py-6 text-center text-sm text-neutral-500">
                  Загружаем чаты...
                </div>
              ) : chats.length ? (
                chats.map((chat) => {
                  const isActive = chat.chat_id === selectedChatId;
                  const adminCount = Number(chat.admin_unread_count || 0);
                  const hasAdmin = adminCount > 0 || Boolean(chat.admin_requested);
                  const unreadCount = Number(chat.unread || 0);
                  const rentalCount = chat.name ? rentalsByBuyer.get(normalizeBuyer(chat.name)) ?? 0 : 0;
                  return (
                    <button
                      key={chat.chat_id}
                      type="button"
                      onClick={() => handleSelectChat(chat.chat_id)}
                      className={`w-full rounded-xl border px-3 py-3 text-left transition ${
                        isActive
                          ? "border-neutral-900 bg-neutral-900 text-white"
                          : hasAdmin
                            ? "border-rose-200 bg-rose-50 text-rose-800 hover:border-rose-300"
                            : "border-neutral-200 bg-white text-neutral-700 hover:border-neutral-300"
                      }`}
                    >
                      <div className="flex items-center justify-between gap-3">
                        <div className="truncate text-sm font-semibold">{chat.name || "Покупатель"}</div>
                        <span className={`text-[11px] ${isActive ? "text-neutral-200" : "text-neutral-400"}`}>
                          {formatTime(chat.last_message_time)}
                        </span>
                      </div>
                      <p className={`mt-2 truncate text-xs ${isActive ? "text-neutral-300" : "text-neutral-500"}`}>
                        {chat.last_message_text || "Сообщений ещё нет."}
                      </p>
                      <div className="mt-2 flex flex-wrap items-center gap-2">
                        {rentalCount > 0 ? (
                          <span
                            className={`inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-semibold ${
                              isActive ? "bg-white/10 text-white" : "bg-emerald-100 text-emerald-700"
                            }`}
                          >
                            Active rental
                          </span>
                        ) : null}
                        {adminCount > 0 ? (
                          <span
                            className={`inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-semibold ${
                              isActive ? "bg-white/10 text-white" : "bg-rose-100 text-rose-700"
                            }`}
                          >
                            !Админ {adminCount}
                          </span>
                        ) : null}
                        {unreadCount > 0 ? (
                          <span
                            className={`inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-semibold ${
                              isActive ? "bg-white/10 text-white" : "bg-amber-100 text-amber-700"
                            }`}
                          >
                            New {unreadCount}
                          </span>
                        ) : null}
                      </div>
                    </button>
                  );
                })
              ) : (
                <div className="rounded-xl border border-dashed border-neutral-200 bg-white px-4 py-6 text-center text-sm text-neutral-500">
                  Чаты не найдены.
                </div>
              )}
            </div>
          </div>

          <div className={`${mobileView === "chat" ? "flex" : "hidden"} min-h-0 flex-col lg:flex`}>
            <div className="flex min-h-0 flex-1 flex-col rounded-xl border border-neutral-200 bg-neutral-50 p-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <div className="text-lg font-semibold text-neutral-900">
                    {selectedChat ? selectedChat.name : "Выберите чат"}
                  </div>
                  <div className="text-xs text-neutral-500">
                    {selectedChat ? `ID чата: ${selectedChat.chat_id}` : "Выберите покупателя, чтобы открыть переписку."}
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    className="rounded-lg border border-neutral-200 bg-white px-3 py-2 text-xs font-semibold text-neutral-600 lg:hidden"
                    type="button"
                    onClick={() => setMobileView("list")}
                  >
                    Back to list
                  </button>
                  <button
                    className="rounded-lg border border-neutral-200 bg-white px-3 py-2 text-xs font-semibold text-neutral-600"
                    type="button"
                    onClick={() => loadHistory(selectedChatId)}
                  >
                    Load history
                  </button>
                </div>
              </div>

              <div className="mt-3 flex min-h-0 flex-1 flex-col overflow-hidden rounded-xl border border-neutral-200 bg-white p-4">
                {chatLoading ? (
                  <div className="rounded-xl border border-dashed border-neutral-200 bg-white px-4 py-6 text-center text-sm text-neutral-500">
                    Загружаем сообщения...
                  </div>
                ) : messages.length ? (
                  <div
                    ref={messageListRef}
                    className="flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto pr-1"
                    onScroll={() => {
                      const el = messageListRef.current;
                      if (!el) return;
                      const distance = el.scrollHeight - el.scrollTop - el.clientHeight;
                      keepScrollPinnedRef.current = distance < 120;
                    }}
                  >
                    {messages.map((message) => {
                      const isBot = Boolean(message.by_bot);
                      const adminCall = isAdminCommand(message.text, message.by_bot);
                      return (
                        <div
                          key={`${message.id}-${message.message_id}`}
                          className={`w-fit max-w-[72%] rounded-xl border px-3 py-2 text-sm break-words ${
                            isBot
                              ? "ml-auto self-end border-neutral-900 bg-neutral-900 text-white"
                              : adminCall
                                ? "self-start border-rose-300 bg-rose-50 text-rose-900"
                                : "self-start border-neutral-200 bg-white text-neutral-700"
                          }`}
                        >
                          <div className={`text-[11px] ${isBot ? "text-neutral-200" : "text-neutral-400"}`}>
                            {[message.author, message.message_type, formatTime(message.sent_time)].filter(Boolean).join(" | ")}
                          </div>
                          {adminCall ? (
                            <div className="mt-1 text-[10px] font-semibold uppercase tracking-wide text-rose-500">
                              Admin request
                            </div>
                          ) : null}
                          <div className="mt-2 max-h-60 overflow-y-auto whitespace-pre-wrap break-words pr-1">
                            {message.text || "(пусто)"}
                          </div>
                        </div>
                      );
                    })}
                    <div ref={messageEndRef} />
                  </div>
                ) : selectedChatId ? (
                  <div className="rounded-xl border border-dashed border-neutral-200 bg-white px-4 py-6 text-center text-sm text-neutral-500">
                    Пока нет сохранённых сообщений. Новые сообщения появятся автоматически.
                  </div>
                ) : (
                  <div className="rounded-xl border border-dashed border-neutral-200 bg-white px-4 py-6 text-center text-sm text-neutral-500">
                    Выберите чат, чтобы посмотреть сообщения.
                  </div>
                )}
              </div>

              <form className="mt-3 flex flex-col gap-3 sm:flex-row" onSubmit={handleSend}>
                <textarea
                  className="min-h-[88px] w-full rounded-xl border border-neutral-200 bg-white px-3 py-2 text-sm text-neutral-700 outline-none placeholder:text-neutral-400"
                  placeholder={selectedChat ? "Напишите сообщение..." : "Сначала выберите чат"}
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

          <div className={`${mobileView === "actions" ? "flex" : "hidden"} min-h-0 flex-col gap-4 lg:flex`}>
            <div className="rounded-xl border border-neutral-200 bg-neutral-50 p-4">
              <div className="flex items-center justify-between">
                <div className="text-sm font-semibold text-neutral-900">Действия аренды</div>
                <span className="text-[11px] text-neutral-500">{selectedRental ? "Готово" : "Выберите аренду"}</span>
              </div>
              {selectedRental ? (
                <div className="mt-3 space-y-3 text-xs text-neutral-600">
                  <div>
                    <div className="text-[11px] text-neutral-400">Аккаунт</div>
                    <div className="text-sm font-semibold text-neutral-900">{selectedRental.account || "-"}</div>
                  </div>
                  <div className="flex items-center justify-between">
                    <span>Осталось: {selectedRental.time_left || "-"}</span>
                    <span className="text-[11px] text-neutral-400">
                      {selectedRental.workspace_name || (selectedRental.workspace_id ? `WS ${selectedRental.workspace_id}` : "Workspace")}
                    </span>
                  </div>
                  <div className="grid grid-cols-2 gap-2">
                    <button
                      onClick={() => handleSetFreeze(true)}
                      disabled={rentalActionBusy}
                      className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs font-semibold text-slate-700 transition hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      Freeze
                    </button>
                    <button
                      onClick={() => handleSetFreeze(false)}
                      disabled={rentalActionBusy}
                      className="rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-xs font-semibold text-emerald-700 transition hover:bg-emerald-100 disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      Unfreeze
                    </button>
                  </div>
                  <button
                    onClick={handleReleaseRental}
                    disabled={rentalActionBusy}
                    className="w-full rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-xs font-semibold text-rose-700 transition hover:bg-rose-100 disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    Release
                  </button>
                  <button
                    onClick={handleRefundRental}
                    disabled={rentalActionBusy}
                    className="w-full rounded-lg border border-rose-300/60 bg-rose-500/10 px-3 py-2 text-xs font-semibold text-rose-600 transition hover:bg-rose-500/15 disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    Refund
                  </button>
                  <div className="text-[11px] text-neutral-400">
                    Refunds the latest order for this buyer.
                  </div>
                  <div className="grid grid-cols-2 gap-2">
                    <input
                      value={extendHours}
                      onChange={(e) => setExtendHours(e.target.value)}
                      placeholder="Hours"
                      type="number"
                      min="0"
                      className="w-full rounded-lg border border-neutral-200 bg-white px-3 py-2 text-xs text-neutral-700 outline-none placeholder:text-neutral-400"
                    />
                    <input
                      value={extendMinutes}
                      onChange={(e) => setExtendMinutes(e.target.value)}
                      placeholder="Minutes"
                      type="number"
                      min="0"
                      className="w-full rounded-lg border border-neutral-200 bg-white px-3 py-2 text-xs text-neutral-700 outline-none placeholder:text-neutral-400"
                    />
                  </div>
                  <button
                    onClick={handleExtendRental}
                    disabled={rentalActionBusy}
                    className="w-full rounded-lg bg-neutral-900 px-3 py-2 text-xs font-semibold text-white transition hover:bg-neutral-800 disabled:cursor-not-allowed disabled:bg-neutral-300"
                  >
                    Extend rental
                  </button>
                  <button
                    onClick={handleReplaceRental}
                    disabled={rentalActionBusy}
                    className="w-full rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-xs font-semibold text-emerald-700 transition hover:bg-emerald-100 disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    {ADMIN_REPLACE_LABEL}
                  </button>
                  <div className="text-[11px] text-neutral-400">
                    Performs a manual admin replacement and notifies the buyer.
                  </div>
                </div>
              ) : (
                <div className="mt-3 rounded-lg border border-dashed border-neutral-200 bg-white px-3 py-4 text-center text-xs text-neutral-500">
                  Выберите аренду, чтобы управлять ею.
                </div>
              )}
            </div>

            <div className="rounded-xl border border-neutral-200 bg-neutral-50 p-4">
              <div className="flex items-center justify-between">
                <div className="text-sm font-semibold text-neutral-900">Управление чатом</div>
                <span className="text-[11px] text-neutral-500">{selectedChat ? "Готово" : "Выберите чат"}</span>
              </div>
              <div className="mt-3 space-y-1 text-xs text-neutral-600">
                <div>Покупатель: {selectedChat?.name || "-"}</div>
                <div>ID чата: {selectedChat?.chat_id ?? "-"}</div>
                <div>Активные аренды: {selectedChat ? rentalsForBuyer.length : "-"}</div>
              </div>
            </div>

            <div className="flex min-h-0 flex-1 flex-col rounded-xl border border-neutral-200 bg-neutral-50 p-4">
              <div className="flex items-center justify-between">
                <div className="text-sm font-semibold text-neutral-900">Активные аренды</div>
                <button
                  className="rounded-lg border border-neutral-200 bg-white px-2 py-1 text-[11px] font-semibold text-neutral-600"
                  type="button"
                  onClick={() => loadRentals()}
                  disabled={rentalsLoading}
                >
                  Обновить
                </button>
              </div>
              <div className="mt-3 flex min-h-0 flex-1 flex-col gap-2 overflow-y-auto pr-1">
                {rentalsLoading ? (
                  <div className="rounded-xl border border-dashed border-neutral-200 bg-white px-4 py-6 text-center text-xs text-neutral-500">
                    Загружаем аренды...
                  </div>
                ) : selectedChat ? (
                  rentalsForBuyer.length ? (
                    rentalsForBuyer.map((item) => {
                      const pill = statusPill(item.status);
                      const isSelected = item.id === selectedRentalId;
                      return (
                        <button
                          key={item.id}
                          type="button"
                          onClick={() => setSelectedRentalId(item.id)}
                          className={`rounded-xl border px-3 py-3 text-left text-xs transition ${
                            isSelected
                              ? "border-neutral-900 bg-neutral-900 text-white"
                              : "border-neutral-200 bg-white text-neutral-700 hover:border-neutral-300"
                          }`}
                        >
                          <div className="flex items-center justify-between gap-2">
                            <div className="truncate text-sm font-semibold">{item.account || "Аккаунт"}</div>
                            <span className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${pill.className}`}>
                              {pill.label}
                            </span>
                          </div>
                          <div className="mt-2 flex items-center justify-between text-[11px] text-neutral-400">
                            <span className={`${isSelected ? "text-neutral-200" : ""}`}>{item.time_left || "-"}</span>
                            <span className={`${isSelected ? "text-neutral-200" : ""}`}>
                              {item.workspace_name || (item.workspace_id ? `WS ${item.workspace_id}` : "Workspace")}
                            </span>
                          </div>
                        </button>
                      );
                    })
                  ) : (
                    <div className="rounded-xl border border-dashed border-neutral-200 bg-white px-4 py-6 text-center text-xs text-neutral-500">
                      Нет активных аренд для этого покупателя.
                    </div>
                  )
                ) : (
                  <div className="rounded-xl border border-dashed border-neutral-200 bg-white px-4 py-6 text-center text-xs text-neutral-500">
                    Выберите чат, чтобы увидеть аренды.
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ChatsPage;
