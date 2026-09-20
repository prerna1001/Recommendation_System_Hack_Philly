"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api, type EventSummary } from "@/lib/api";

const EMPTY_NEW_EVENT = { name: "", date: "", format: "", venue: "" };

function NewEventForm({ onCreated }: { onCreated: (id: number) => void }) {
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(EMPTY_NEW_EVENT);
  const [saving, setSaving] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    try {
      const created = await api.createEvent(form);
      setForm(EMPTY_NEW_EVENT);
      setOpen(false);
      onCreated(created.id);
    } finally {
      setSaving(false);
    }
  }

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        className="mb-6 rounded bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-dark"
      >
        + New event
      </button>
    );
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="mb-6 grid max-w-xl gap-3 rounded-xl border border-accent/30 bg-accent/5 p-4 sm:grid-cols-2"
    >
      <div>
        <label className="mb-1 block text-sm text-muted">Event name</label>
        <input
          required
          className="w-full rounded border border-border-warm bg-card px-3 py-2 text-sm"
          value={form.name}
          onChange={(e) => setForm({ ...form, name: e.target.value })}
        />
      </div>
      <div>
        <label className="mb-1 block text-sm text-muted">Date</label>
        <input
          required
          type="date"
          className="w-full rounded border border-border-warm bg-card px-3 py-2 text-sm"
          value={form.date}
          onChange={(e) => setForm({ ...form, date: e.target.value })}
        />
      </div>
      <div>
        <label className="mb-1 block text-sm text-muted">Format</label>
        <input
          placeholder="e.g. open co-working, pitch competition"
          className="w-full rounded border border-border-warm bg-card px-3 py-2 text-sm"
          value={form.format}
          onChange={(e) => setForm({ ...form, format: e.target.value })}
        />
      </div>
      <div>
        <label className="mb-1 block text-sm text-muted">Venue</label>
        <input
          className="w-full rounded border border-border-warm bg-card px-3 py-2 text-sm"
          value={form.venue}
          onChange={(e) => setForm({ ...form, venue: e.target.value })}
        />
      </div>
      <div className="flex gap-2 sm:col-span-2">
        <button
          type="submit"
          disabled={saving}
          className="rounded bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-dark disabled:opacity-50"
        >
          {saving ? "Creating..." : "Create event"}
        </button>
        <button
          type="button"
          onClick={() => setOpen(false)}
          className="rounded px-4 py-2 text-sm text-muted hover:text-accent"
        >
          Cancel
        </button>
      </div>
    </form>
  );
}

function EventPhoto({ event }: { event: EventSummary }) {
  if (event.photo_url) {
    // eslint-disable-next-line @next/next/no-img-element
    return <img src={event.photo_url} alt={event.name} className="h-40 w-full object-cover" />;
  }
  return (
    <div className="flex h-40 w-full items-center justify-center bg-linear-to-br from-accent/20 to-accent/5 text-4xl">
      ☕
    </div>
  );
}

export default function DashboardPage() {
  const router = useRouter();
  const [events, setEvents] = useState<EventSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.listEvents().then(setEvents).catch((e) => setError(String(e)));
  }, []);

  if (error) return <p className="text-red-600">{error}</p>;
  if (!events) return <p className="text-muted">Loading...</p>;

  return (
    <div>
      <h1 className="mb-1 text-xl font-semibold">Events</h1>
      <p className="mb-4 text-sm text-muted">Past events, or create the next one and fill in the organizer feedback once it's happened.</p>
      <NewEventForm onCreated={(id) => router.push(`/dashboard/${id}`)} />
      {events.length === 0 && (
        <p className="text-sm text-muted">No events yet -- create your first one above.</p>
      )}
      <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
        {events.map((e) => {
          const turnoutRate =
            e.registered_count && e.attended_count
              ? Math.round((e.attended_count / e.registered_count) * 100)
              : null;
          return (
            <Link
              key={e.id}
              href={`/dashboard/${e.id}`}
              className="group overflow-hidden rounded-xl border border-border-warm bg-card shadow-sm transition hover:-translate-y-0.5 hover:border-accent hover:shadow-md"
            >
              <EventPhoto event={e} />
              <div className="p-4">
                <div className="flex items-start justify-between gap-2">
                  <h2 className="font-medium leading-snug group-hover:text-accent">{e.name}</h2>
                </div>
                <p className="mt-0.5 text-xs text-muted">{e.date}</p>
                <p className="mt-1 text-sm text-muted">
                  {e.format} · {e.venue}
                </p>
                <div className="mt-3 flex flex-wrap gap-1.5">
                  <span className="rounded-full bg-background px-2.5 py-1 text-xs text-muted">
                    {e.sponsor_count} sponsor{e.sponsor_count === 1 ? "" : "s"}
                  </span>
                  {turnoutRate !== null && (
                    <span className="rounded-full bg-background px-2.5 py-1 text-xs text-muted">
                      {e.attended_count}/{e.registered_count} attended ({turnoutRate}%)
                    </span>
                  )}
                  {e.relevant_connection_rate !== null && (
                    <span
                      className={`rounded-full px-2.5 py-1 text-xs font-medium ${
                        e.relevant_connection_rate >= 0.5
                          ? "bg-emerald-100 text-emerald-700"
                          : "bg-amber-100 text-amber-700"
                      }`}
                    >
                      {Math.round(e.relevant_connection_rate * 100)}% connection rate
                    </span>
                  )}
                  {e.weather_tag && (
                    <span className="rounded-full bg-background px-2.5 py-1 text-xs text-muted">
                      {e.weather_tag}
                    </span>
                  )}
                </div>
                {e.success_assessment && (
                  <p className="mt-2 line-clamp-2 text-xs text-muted">{e.success_assessment}</p>
                )}
              </div>
            </Link>
          );
        })}
      </div>
    </div>
  );
}
