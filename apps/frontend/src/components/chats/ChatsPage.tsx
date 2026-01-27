import React, { useMemo, useState } from "react";

type ChatItem = {
  id: number;
  name: string;
  lastMessage: string;
  lastTime: string;
  unread?: boolean;
  adminCalls?: number;
  avatarUrl?: string | null;
};

type ChatMessage = {
  id: string;
  author: string;
  text: string;
  sentAt: string;
  byBot?: boolean;
  type?: string;
};

const DEMO_CHATS: ChatItem[] = [
  {
    id: 101,
    name: "Buyer Masha",
    lastMessage: "Thanks, received the account.",
    lastTime: "14:21",
    unread: false,
    adminCalls: 0,
  },
  {
    id: 102,
    name: "Buyer Alex",
    lastMessage: "Need help with the code.",
    lastTime: "13:05",
    unread: true,
    adminCalls: 2,
  },
  {
    id: 103,
    name: "Buyer Ivan",
    lastMessage: "Payment done, waiting.",
    lastTime: "Yesterday",
    unread: true,
    adminCalls: 0,
  },
  {
    id: 104,
    name: "Buyer Lina",
    lastMessage: "Can I extend for 2 hours?",
    lastTime: "Mon",
    unread: false,
    adminCalls: 1,
  },
];

const DEMO_MESSAGES: Record<number, ChatMessage[]> = {
  101: [
    {
      id: "m101-1",
      author: "Buyer Masha",
      text: "Hi, I paid for lot 1.",
      sentAt: "13:55",
    },
    {
      id: "m101-2",
      author: "Bot",
      text: "Your account details are ready.",
      sentAt: "13:56",
      byBot: true,
      type: "auto",
    },
  ],
  102: [
    {
      id: "m102-1",
      author: "Buyer Alex",
      text: "I need help with the code.",
      sentAt: "13:01",
    },
    {
      id: "m102-2",
      author: "Bot",
      text: "Use !code to receive the Steam Guard code.",
      sentAt: "13:02",
      byBot: true,
      type: "auto",
    },
  ],
  103: [
    {
      id: "m103-1",
      author: "Buyer Ivan",
      text: "Payment done, waiting.",
      sentAt: "12:21",
    },
  ],
  104: [
    {
      id: "m104-1",
      author: "Buyer Lina",
      text: "Can I extend for 2 hours?",
      sentAt: "Mon 18:42",
    },
    {
      id: "m104-2",
      author: "Bot",
      text: "Sure. Pay the extension lot and I will extend automatically.",
      sentAt: "Mon 18:43",
      byBot: true,
      type: "auto",
    },
  ],
};

const ChatsPage: React.FC = () => {
  const [chatSearch, setChatSearch] = useState("");
  const [selectedChatId, setSelectedChatId] = useState<number | null>(DEMO_CHATS[0]?.id ?? null);
  const [messages, setMessages] = useState<ChatMessage[]>(
    selectedChatId ? DEMO_MESSAGES[selectedChatId] || [] : [],
  );
  const [draft, setDraft] = useState("");

  const filteredChats = useMemo(() => {
    const query = chatSearch.trim().toLowerCase();
    if (!query) return DEMO_CHATS;
    return DEMO_CHATS.filter((chat) => {
      const name = chat.name.toLowerCase();
      const last = chat.lastMessage.toLowerCase();
      return name.includes(query) || last.includes(query);
    });
  }, [chatSearch]);

  const selectedChat = useMemo(
    () => DEMO_CHATS.find((chat) => chat.id === selectedChatId) || null,
    [selectedChatId],
  );

  const handleSelectChat = (chatId: number) => {
    setSelectedChatId(chatId);
    setMessages(DEMO_MESSAGES[chatId] || []);
  };

  const handleSend = (event: React.FormEvent) => {
    event.preventDefault();
    if (!selectedChatId) return;
    const text = draft.trim();
    if (!text) return;
    const next: ChatMessage = {
      id: `local-${Date.now()}`,
      author: "You",
      text,
      sentAt: "Now",
      byBot: true,
      type: "manual",
    };
    setMessages((prev) => [...prev, next]);
    setDraft("");
  };

  return (
    <div className="space-y-6">
      <div className="rounded-2xl border border-neutral-200 bg-white p-6 shadow-sm shadow-neutral-200/70">
        <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
          <div>
            <h3 className="text-lg font-semibold text-neutral-900">Chats</h3>
            <p className="text-sm text-neutral-500">Design preview. API wiring comes next.</p>
          </div>
          <button className="rounded-lg border border-neutral-200 bg-neutral-50 px-3 py-2 text-xs text-neutral-600">
            Refresh
          </button>
        </div>

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
              >
                Update
              </button>
            </div>
            <div className="mt-4 max-h-[520px] space-y-2 overflow-y-auto pr-1">
              {filteredChats.length ? (
                filteredChats.map((chat) => {
                  const isActive = chat.id === selectedChatId;
                  return (
                    <button
                      key={chat.id}
                      type="button"
                      onClick={() => handleSelectChat(chat.id)}
                      className={`w-full rounded-xl border px-3 py-3 text-left transition ${
                        isActive
                          ? "border-neutral-900 bg-neutral-900 text-white"
                          : "border-neutral-200 bg-white text-neutral-700 hover:border-neutral-300"
                      }`}
                    >
                      <div className="flex items-center justify-between gap-3">
                        <div className="truncate text-sm font-semibold">
                          {chat.name}
                        </div>
                        <span className={`text-[11px] ${isActive ? "text-neutral-200" : "text-neutral-400"}`}>
                          {chat.lastTime}
                        </span>
                      </div>
                      <p className={`mt-2 truncate text-xs ${isActive ? "text-neutral-300" : "text-neutral-500"}`}>
                        {chat.lastMessage || "No messages yet."}
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
                        {chat.adminCalls ? (
                          <span
                            className={`inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-semibold ${
                              isActive ? "bg-white/10 text-white" : "bg-rose-100 text-rose-700"
                            }`}
                          >
                            Admin {chat.adminCalls}
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
              >
                Load history
              </button>
            </div>

            <div className="flex-1 space-y-3 overflow-y-auto rounded-xl border border-neutral-200 bg-neutral-50 p-4">
              {messages.length ? (
                messages.map((message) => {
                  const isBot = Boolean(message.byBot);
                  return (
                    <div
                      key={message.id}
                      className={`max-w-[78%] rounded-xl border px-3 py-2 text-sm ${
                        isBot
                          ? "ml-auto border-neutral-900 bg-neutral-900 text-white"
                          : "border-neutral-200 bg-white text-neutral-700"
                      }`}
                    >
                      <div className={`text-[11px] ${isBot ? "text-neutral-200" : "text-neutral-400"}`}>
                        {[message.author, message.type, message.sentAt].filter(Boolean).join(" | ")}
                      </div>
                      <div className="mt-2 whitespace-pre-wrap">{message.text}</div>
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
