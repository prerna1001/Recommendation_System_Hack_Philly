"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { api, type EventDetail, type EventSummary, type Sponsor } from "@/lib/api";

type RetroForm = Pick<
  EventSummary,
  | "registered_count"
  | "attended_count"
  | "weather_tag"
  | "turnout_reason"
  | "success_assessment"
  | "photo_url"
>;

const SPONSOR_TYPES = ["devtools_startup", "vc_agency", "local_business", "enterprise", "agency", "infra"];
const CONTRIBUTION_TYPES = ["cash", "credits", "food", "venue", "swag"];
const EMPTY_SPONSOR: Omit<Sponsor, "id"> = {
  sponsor_name: "",
  sponsor_type: "",
  contribution_type: "",
  contact_person: "",
  how_connected: "",
};

function AddSponsorForm({ onAdd }: { onAdd: (sponsor: Omit<Sponsor, "id">) => Promise<void> }) {
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(EMPTY_SPONSOR);
  const [saving, setSaving] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    try {
      await onAdd(form);
      setForm(EMPTY_SPONSOR);
      setOpen(false);
    } finally {
      setSaving(false);
    }
  }

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        className="rounded bg-accent px-3 py-1.5 text-xs font-medium text-white hover:bg-accent-dark"
      >
        + Add sponsor
      </button>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="grid max-w-xl gap-3 rounded-lg border border-accent/30 bg-accent/5 p-4 sm:grid-cols-2">
      <div className="sm:col-span-2">
        <label className="mb-1 block text-sm text-muted">Sponsor name</label>
        <input
          required
          className="w-full rounded border border-border-warm bg-card px-3 py-2 text-sm"
          value={form.sponsor_name}
          onChange={(e) => setForm({ ...form, sponsor_name: e.target.value })}
        />
      </div>
      <div>
        <label className="mb-1 block text-sm text-muted">Sponsor type</label>
        <input
          required
          list="sponsor-types"
          className="w-full rounded border border-border-warm bg-card px-3 py-2 text-sm"
          value={form.sponsor_type}
          onChange={(e) => setForm({ ...form, sponsor_type: e.target.value })}
        />
        <datalist id="sponsor-types">
          {SPONSOR_TYPES.map((t) => (
            <option key={t} value={t} />
          ))}
        </datalist>
      </div>
      <div>
        <label className="mb-1 block text-sm text-muted">Contribution type</label>
        <input
          required
          list="contribution-types"
          className="w-full rounded border border-border-warm bg-card px-3 py-2 text-sm"
          value={form.contribution_type}
          onChange={(e) => setForm({ ...form, contribution_type: e.target.value })}
        />
        <datalist id="contribution-types">
          {CONTRIBUTION_TYPES.map((t) => (
            <option key={t} value={t} />
          ))}
        </datalist>
      </div>
      <div>
        <label className="mb-1 block text-sm text-muted">Contact person</label>
        <input
          className="w-full rounded border border-border-warm bg-card px-3 py-2 text-sm"
          value={form.contact_person}
          onChange={(e) => setForm({ ...form, contact_person: e.target.value })}
        />
      </div>
      <div>
        <label className="mb-1 block text-sm text-muted">How connected</label>
        <input
          placeholder="e.g. warm intro, cold outreach"
          className="w-full rounded border border-border-warm bg-card px-3 py-2 text-sm"
          value={form.how_connected}
          onChange={(e) => setForm({ ...form, how_connected: e.target.value })}
        />
      </div>
      <div className="flex gap-2 sm:col-span-2">
        <button
          type="submit"
          disabled={saving}
          className="rounded bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-dark disabled:opacity-50"
        >
          {saving ? "Adding..." : "Add sponsor"}
        </button>
        <button type="button" onClick={() => setOpen(false)} className="text-sm text-muted hover:text-accent">
          Cancel
        </button>
      </div>
    </form>
  );
}

export default function EventDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const eventId = Number(params.id);

  const [detail, setDetail] = useState<EventDetail | null>(null);
  const [retro, setRetro] = useState<RetroForm>({
    registered_count: null,
    attended_count: null,
    weather_tag: null,
    turnout_reason: null,
    success_assessment: null,
    photo_url: null,
  });
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    api.getEvent(eventId).then((d) => {
      setDetail(d);
      setRetro({
        registered_count: d.event.registered_count,
        attended_count: d.event.attended_count,
        weather_tag: d.event.weather_tag,
        turnout_reason: d.event.turnout_reason,
        success_assessment: d.event.success_assessment,
        photo_url: d.event.photo_url,
      });
    });
  }, [eventId]);

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setSaved(false);
    try {
      const updated = await api.updateRetro(eventId, retro);
      setDetail((d) => (d ? { ...d, event: updated } : d));
      setSaved(true);
    } finally {
      setSaving(false);
    }
  }

  async function handleDeleteEvent() {
    if (!confirm("Delete this event? This also removes its sponsors, feedback, and rubric scores. This can't be undone.")) return;
    await api.deleteEvent(eventId);
    router.push("/dashboard");
  }

  async function handleAddSponsor(sponsor: Omit<Sponsor, "id">) {
    const added = await api.addSponsor(eventId, sponsor);
    setDetail((d) => (d ? { ...d, sponsors: [...d.sponsors, added] } : d));
  }

  async function handleDeleteSponsor(sponsorId: number) {
    await api.deleteSponsor(sponsorId);
    setDetail((d) => (d ? { ...d, sponsors: d.sponsors.filter((s) => s.id !== sponsorId) } : d));
  }

  if (!detail) return <p className="text-muted">Loading...</p>;
  const { event, sponsors, feedback, rubric_scores } = detail;

  return (
    <div className="flex flex-col gap-8">
      <div className="overflow-hidden rounded-xl border border-border-warm bg-card">
        {event.photo_url ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={event.photo_url} alt={event.name} className="h-56 w-full object-cover" />
        ) : (
          <div className="flex h-40 w-full items-center justify-center bg-linear-to-br from-accent/20 to-accent/5 text-5xl">
            ☕
          </div>
        )}
        <div className="flex items-start justify-between gap-4 p-5">
          <div>
            <h1 className="text-xl font-semibold">{event.name}</h1>
            <p className="text-sm text-muted">
              {event.format} at {event.venue} · {event.date}
            </p>
          </div>
          <button
            onClick={handleDeleteEvent}
            className="shrink-0 rounded border border-red-200 px-3 py-1.5 text-xs text-red-600 hover:bg-red-50"
          >
            Delete event
          </button>
        </div>
      </div>

      <section className="rounded-xl border border-accent/30 bg-accent/5 p-5">
        <h2 className="font-medium">Organizer feedback</h2>
        <p className="mb-4 text-sm text-muted">
          Your own read on how this event went. This is what actually drives the next-event
          plan when you ask the chat to plan one -- it&apos;s treated as ground truth over the
          attendee survey averages below.
        </p>
        <form onSubmit={handleSave} className="grid max-w-xl gap-4 sm:grid-cols-2">
          <div className="sm:col-span-2">
            <label className="mb-1 block text-sm text-muted">Event photo URL</label>
            <input
              type="url"
              placeholder="https://..."
              className="w-full rounded border border-border-warm bg-card px-3 py-2 text-sm"
              value={retro.photo_url ?? ""}
              onChange={(e) => setRetro({ ...retro, photo_url: e.target.value })}
            />
          </div>
          <div>
            <label className="mb-1 block text-sm text-muted">Registered</label>
            <input
              type="number"
              className="w-full rounded border border-border-warm bg-card px-3 py-2 text-sm"
              value={retro.registered_count ?? ""}
              onChange={(e) =>
                setRetro({ ...retro, registered_count: e.target.value ? Number(e.target.value) : null })
              }
            />
          </div>
          <div>
            <label className="mb-1 block text-sm text-muted">Attended</label>
            <input
              type="number"
              className="w-full rounded border border-border-warm bg-card px-3 py-2 text-sm"
              value={retro.attended_count ?? ""}
              onChange={(e) =>
                setRetro({ ...retro, attended_count: e.target.value ? Number(e.target.value) : null })
              }
            />
          </div>
          <div className="sm:col-span-2">
            <label className="mb-1 block text-sm text-muted">
              Weather / day-of-week tag
            </label>
            <input
              placeholder="e.g. sunny_weekend, cold_weeknight, holiday_clash"
              className="w-full rounded border border-border-warm bg-card px-3 py-2 text-sm"
              value={retro.weather_tag ?? ""}
              onChange={(e) => setRetro({ ...retro, weather_tag: e.target.value })}
            />
          </div>
          <div className="sm:col-span-2">
            <label className="mb-1 block text-sm text-muted">
              Why turnout was what it was (your read)
            </label>
            <textarea
              rows={3}
              placeholder="e.g. beautiful weekend, competed with a street festival nearby"
              className="w-full rounded border border-border-warm bg-card px-3 py-2 text-sm"
              value={retro.turnout_reason ?? ""}
              onChange={(e) => setRetro({ ...retro, turnout_reason: e.target.value })}
            />
          </div>
          <div className="sm:col-span-2">
            <label className="mb-1 block text-sm text-muted">
              Was it successful? Why or why not?
            </label>
            <textarea
              rows={3}
              className="w-full rounded border border-border-warm bg-card px-3 py-2 text-sm"
              value={retro.success_assessment ?? ""}
              onChange={(e) => setRetro({ ...retro, success_assessment: e.target.value })}
            />
          </div>
          <div className="sm:col-span-2">
            <button
              type="submit"
              disabled={saving}
              className="rounded bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-dark disabled:opacity-50"
            >
              {saving ? "Saving..." : "Save notes"}
            </button>
            {saved && <span className="ml-3 text-sm text-emerald-600">Saved.</span>}
          </div>
        </form>
      </section>

      <section>
        <h2 className="mb-3 font-medium">Sponsors ({sponsors.length})</h2>
        <div className="mb-3">
          <AddSponsorForm onAdd={handleAddSponsor} />
        </div>
        <div className="flex flex-col gap-2">
          {sponsors.map((s) => (
            <div key={s.id} className="flex items-center justify-between gap-2 rounded border border-border-warm bg-card p-3 text-sm">
              <div>
                <span className="font-medium">{s.sponsor_name}</span>{" "}
                <span className="text-muted">
                  ({s.sponsor_type} → {s.contribution_type}
                  {s.how_connected ? `, via ${s.how_connected}` : ""})
                </span>
              </div>
              <button
                onClick={() => handleDeleteSponsor(s.id)}
                className="shrink-0 text-xs text-muted hover:text-red-600"
              >
                Remove
              </button>
            </div>
          ))}
        </div>
      </section>

      <section>
        <h2 className="font-medium">Rubric scorecard</h2>
        <p className="mb-3 text-xs text-muted">Derived from the attendee survey -- supporting evidence, not the organizer feedback form above.</p>
        <div className="flex flex-wrap gap-2">
          {rubric_scores
            .filter((r) => r.category !== "relevant_connection_rate")
            .map((r) => (
              <span
                key={r.id}
                className="rounded-full bg-background px-3 py-1 text-xs text-muted"
              >
                {r.category}: {r.score}/5
              </span>
            ))}
        </div>
      </section>

      <details className="group rounded-lg border border-border-warm bg-card p-4">
        <summary className="cursor-pointer list-none font-medium text-muted marker:hidden">
          <span className="mr-1 inline-block transition group-open:rotate-90">›</span>
          Raw attendee survey responses ({feedback.length})
          <span className="ml-2 text-xs font-normal">
            -- individual submissions behind the rubric scorecard above, not the organizer
            feedback form
          </span>
        </summary>
        <div className="mt-3 flex flex-col gap-2">
          {feedback.map((f) => (
            <div key={f.id} className="rounded border border-border-warm bg-background p-3 text-sm">
              <div className="flex items-center justify-between text-xs text-muted">
                <span>{f.respondent}</span>
                <span>{f.had_relevant_connection ? "✓ made a connection" : "no relevant connection"}</span>
              </div>
              <p className="mt-1">{f.free_text}</p>
            </div>
          ))}
        </div>
      </details>
    </div>
  );
}
