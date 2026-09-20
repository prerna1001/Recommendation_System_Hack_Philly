"use client";

import { useEffect, useRef, useState } from "react";
import { api, type ChatMessage } from "@/lib/api";

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

function Suggestions() {
  const [suggestions, setSuggestions] = useState<string | string[] | null>(null);
  const [loading, setLoading] = useState(false);

  async function load() {
    setLoading(true);
    try {
      const res = await api.getSuggestions();
      setSuggestions(res.suggestions);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  return (
    <div className="rounded-lg border border-border-warm bg-card p-4">
      <div className="mb-2 flex items-center justify-between">
        <h2 className="font-medium">What to try next</h2>
        <button onClick={load} disabled={loading} className="text-xs text-muted hover:text-accent">
          {loading ? "..." : "Refresh"}
        </button>
      </div>
      {!suggestions && <p className="text-sm text-muted">Loading...</p>}
      {Array.isArray(suggestions) ? (
        <ul className="list-disc pl-4 text-sm text-muted">
          {suggestions.map((s, i) => (
            <li key={i}>{s}</li>
          ))}
        </ul>
      ) : (
        <p className="whitespace-pre-wrap text-sm text-muted">{suggestions}</p>
      )}
    </div>
  );
}

export default function ChatPage() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    api.getChatHistory().then(setMessages).catch(() => {});
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function send(e: React.FormEvent) {
    e.preventDefault();
    if (!input.trim() || sending) return;
    const text = input;
    setInput("");
    setSending(true);
    setMessages((m) => [
      ...m,
      { id: Date.now(), role: "organizer", content: text, recommendation_id: null, created_at: "" },
    ]);
    try {
      const reply = await api.postChat(text);
      setMessages((m) => [...m, reply]);
    } finally {
      setSending(false);
    }
  }

  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_320px]">
      <div className="flex h-[70vh] flex-col rounded-lg border border-border-warm bg-card">
        <div className="flex-1 overflow-y-auto p-4">
          {messages.length === 0 && (
            <p className="text-sm text-muted">
              Describe an idea for your next event -- e.g. &quot;who should we ask for pizza
              sponsorship?&quot; or &quot;plan the next event&quot;.
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
      <Suggestions />
    </div>
  );
}
