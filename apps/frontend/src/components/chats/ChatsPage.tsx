import React, { useCallback, useEffect, useMemo, useState } from "react";

import { api, ChatItem, ChatMessageItem } from "../../services/api";
import { useWorkspace } from "../../context/WorkspaceContext";

const formatTime = (value?: string | null) => {
  if (!value) return "";
  const dt = new Date(value);
  if (Number.isNaN(dt.getTime())) return value;
  return dt.toLocaleString();
};

const ChatsPage: React.FC = () => {
  const { selectedId: selectedWorkspaceId } = useWorkspace();
  const workspaceId = selectedWorkspaceId === "all" ? null : (selectedWorkspaceId as number);

  const [chatSearch, setChatSearch] = useState("");
  const [chats, setChats] = useState<ChatItem[]>([]);
  const [chatListLoading, setChatListLoading] = useState(false);
  const [chatLoading, setChatLoading] = useState(false);
  const [selectedChatId, setSelectedChatId] = useState<number | null>(null);
  const [messages, setMessages] = useState<ChatMessageItem[]>([]);
  const [draft, setDraft] = useState("");
  const [status, setStatus] = useState<string | null>(null);

  const loadChats = useCallback(
    async (query?: string) => {
      if (!workspaceId) {
        setChats([]);
        setSelectedChatId(null);
        setMessages([]);
        setStatus("Select a workspace to view chats.");
        return;
      }
      setChatListLoading(true);
      try {
        const res = await api.listChats(workspaceId, query?.trim() || undefined, 300);
        const items = res.items || [];
        setChats(items);
        setStatus(null);
        if (!selectedChatId && items.length) {
          setSelectedChatId(items[0].chat_id);
        } else if (selectedChatId && !items.some((c) => c.chat_id === selectedChatId)) {
          setSelectedChatId(items[0]?.chat_id ?? null);
        }
      } catch (err) {
        const message = (err as { message?: string })?.message || "Failed to load chats.";
        setStatus(message);
      } finally {
        setChatListLoading(false);
      }
    },
    [workspaceId, selectedChatId],
  );

  const loadHistory = useCallback(
    async (chatId: number | null) => {
      if (!workspaceId || !chatId) {
        setMessages([]);
        return;
      }
      setChatLoading(true);
      try {
        const res = await api.getChatHistory(chatId, workspaceId, 300);
        setMessages(res.items || []);
      } catch (err) {
        const message = (err as { message?: string })?.message || "Failed to load chat history.";
        setStatus(message);
      } finally {
        setChatLoading(false);
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
    void loadHistory(selectedChatId);
  }, [selectedChatId, loadHistory]);

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
      message_id: Date.now(),
      chat_id: selectedChatId,
      author: "You",
      text,
      sent_time: new Date().toISOString(),
      by_bot: 1,
      message_type: "manual",
      workspace_id: workspaceId,
    };
    setMessages((prev) => [...prev, optimistic]);
    setDraft("");
    try {
      await api.sendChatMessage(selectedChatId, text, workspaceId);
      setChats((prev) =>
        prev.map((chat) =>
          chat.chat_id === selectedChatId
            ? {
                ...chat,
                last_message_text: text,
                last_message_time: new Date().toISOString(),
              }
            : chat,
        ),
      );
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
            onClick={() => loadChats(chatSearch)}
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
