"use client";

import { useEffect, useRef, useState } from "react";
import { api, type ChatMessage, type ChatSession } from "@/lib/api";

function FeedbackButtons({ message }: { message: ChatMessage }) {
  const [state, setState] = useState<"idle" | "liked" | "disliked" | "asking_reason">("idle");
  const [reason, setReason] = useState("");

  async function like() {
    setState("liked");
    await api.postChatFeedback(message.id, true);
  }

  async function submitDislike() {
    setState("disliked");
    await api.postChatFeedback(message.id, false, reason || undefined);
  }

  if (state === "liked") return <p className="mt-2 text-xs text-emerald-600">Liked.</p>;
  if (state === "disliked") return <p className="mt-2 text-xs text-amber-600">Noted — thanks.</p>;

  if (state === "asking_reason") {
    return (
      <div className="mt-2 flex flex-col gap-2">
        <textarea
          autoFocus
          rows={2}
          placeholder="What would you change?"
          className="w-full rounded border border-border-warm px-2 py-1 text-xs"
          value={reason}
          onChange={(e) => setReason(e.target.value)}
        />
        <div className="flex gap-2">
          <button
            onClick={submitDislike}
            className="rounded bg-accent px-3 py-1 text-xs text-white hover:bg-accent-dark"
          >
            Submit
          </button>
          <button onClick={() => setState("idle")} className="text-xs text-muted">
            Cancel
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="mt-2 flex gap-3 text-xs">
      <button onClick={like} className="text-muted hover:text-emerald-600">
        👍 Like
      </button>
      <button onClick={() => setState("asking_reason")} className="text-muted hover:text-amber-600">
        👎 Not quite
      </button>
    </div>
  );
}

function SessionSidebar({
  sessions,
  activeId,
  onSelect,
  onNew,
  onDelete,
}: {
  sessions: ChatSession[];
  activeId: number | null;
  onSelect: (id: number) => void;
  onNew: () => void;
  onDelete: (id: number) => void;
}) {
  return (
    <div className="flex w-56 flex-none flex-col gap-2 border-r border-border-warm pr-3">
      <button
        onClick={onNew}
        className="rounded bg-accent px-3 py-2 text-sm font-medium text-white hover:bg-accent-dark"
      >
        + New chat
      </button>
      <div className="flex flex-col gap-1 overflow-y-auto">
        {sessions.map((s) => (
          <div
            key={s.id}
            className={`group flex items-center justify-between gap-1 rounded px-2 py-2 text-xs ${
              s.id === activeId ? "bg-accent/10 text-foreground" : "text-muted hover:bg-background"
            }`}
          >
            <button onClick={() => onSelect(s.id)} className="flex-1 truncate text-left">
              {s.preview ? s.preview.slice(0, 40) : s.title || "New chat"}
            </button>
            <button
              onClick={() => onDelete(s.id)}
              className="hidden text-muted hover:text-red-600 group-hover:inline"
              title="Delete chat"
            >
              ✕
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function ChatPage() {
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [activeId, setActiveId] = useState<number | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    (async () => {
      let list = await api.listChatSessions().catch(() => []);
      if (list.length === 0) {
        const created = await api.createChatSession();
        list = [created];
      }
      setSessions(list);
      setActiveId(list[0].id);
    })();
  }, []);

  useEffect(() => {
    if (activeId == null) return;
    api.getChatHistory(activeId).then(setMessages).catch(() => {});
  }, [activeId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function newChat() {
    const created = await api.createChatSession();
    setSessions((s) => [created, ...s]);
    setActiveId(created.id);
  }

  async function deleteChat(id: number) {
    await api.deleteChatSession(id);
    const remaining = sessions.filter((s) => s.id !== id);
    if (remaining.length === 0) {
      const created = await api.createChatSession();
      setSessions([created]);
      setActiveId(created.id);
    } else {
      setSessions(remaining);
      if (activeId === id) setActiveId(remaining[0].id);
    }
  }

  async function send(e: React.FormEvent) {
    e.preventDefault();
    if (!input.trim() || sending || activeId == null) return;
    const text = input;
    setInput("");
    setSending(true);
    setMessages((m) => [
      ...m,
      { id: Date.now(), role: "organizer", content: text, recommendation_id: null, created_at: "" },
    ]);
    try {
      const reply = await api.postChat(text, activeId);
      setMessages((m) => [...m, reply]);
      setSessions((s) =>
        s.map((sess) => (sess.id === activeId && !sess.preview ? { ...sess, preview: text } : sess))
      );
    } finally {
      setSending(false);
    }
  }

  return (
    <div className="mx-auto flex max-w-4xl gap-4">
      <SessionSidebar
        sessions={sessions}
        activeId={activeId}
        onSelect={setActiveId}
        onNew={newChat}
        onDelete={deleteChat}
      />
      <div className="flex h-[70vh] flex-1 flex-col rounded-lg border border-border-warm bg-card">
        <div className="flex-1 overflow-y-auto p-4">
          {messages.length === 0 && (
            <p className="text-sm text-muted">
              Describe an idea for your next event -- e.g. &quot;who should we ask for pizza
              sponsorship?&quot; or &quot;plan the next event&quot;. Or ask &quot;what should I
              try next?&quot; for suggestions based on what you&apos;ve done so far.
            </p>
          )}
          <div className="flex flex-col gap-4">
            {messages.map((m) => (
              <div
                key={m.id}
                className={`max-w-[85%] rounded-lg px-3 py-2 text-sm ${
                  m.role === "organizer"
                    ? "ml-auto bg-accent text-white"
                    : "bg-background text-foreground"
                }`}
              >
                <p className="whitespace-pre-wrap">{m.content}</p>
                {m.role === "assistant" && <FeedbackButtons message={m} />}
              </div>
            ))}
          </div>
          <div ref={bottomRef} />
        </div>
        <form onSubmit={send} className="flex gap-2 border-t border-border-warm p-3">
          <input
            className="flex-1 rounded border border-border-warm px-3 py-2 text-sm"
            placeholder="Describe your next event idea..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            disabled={sending}
          />
          <button
            type="submit"
            disabled={sending}
            className="rounded bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-dark disabled:opacity-50"
          >
            {sending ? "..." : "Send"}
          </button>
        </form>
      </div>
    </div>
  );
}
