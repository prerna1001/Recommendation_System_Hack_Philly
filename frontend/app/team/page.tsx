"use client";

import { useEffect, useState } from "react";
import { api, type Member } from "@/lib/api";

const EMPTY: Omit<Member, "id"> = { name: "", email: "", linkedin_url: "", photo_url: "" };

function MemberCard({ member, onSave, onDelete }: {
  member: Member;
  onSave: (id: number, data: Omit<Member, "id">) => Promise<void>;
  onDelete: (id: number) => Promise<void>;
}) {
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState<Omit<Member, "id">>(member);
  const [saving, setSaving] = useState(false);

  async function save(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    try {
      await onSave(member.id, form);
      setEditing(false);
    } finally {
      setSaving(false);
    }
  }

  if (editing) {
    return (
      <form onSubmit={save} className="flex flex-col gap-2 rounded-lg border border-accent/40 bg-card p-4">
        <input
          className="rounded border border-border-warm px-2 py-1 text-sm"
          placeholder="Name"
          value={form.name}
          onChange={(e) => setForm({ ...form, name: e.target.value })}
        />
        <input
          className="rounded border border-border-warm px-2 py-1 text-sm"
          placeholder="Email"
          value={form.email}
          onChange={(e) => setForm({ ...form, email: e.target.value })}
        />
        <input
          className="rounded border border-border-warm px-2 py-1 text-sm"
          placeholder="LinkedIn URL"
          value={form.linkedin_url}
          onChange={(e) => setForm({ ...form, linkedin_url: e.target.value })}
        />
        <input
          className="rounded border border-border-warm px-2 py-1 text-sm"
          placeholder="Photo URL"
          value={form.photo_url}
          onChange={(e) => setForm({ ...form, photo_url: e.target.value })}
        />
        <div className="flex gap-2">
          <button
            type="submit"
            disabled={saving}
            className="rounded bg-accent px-3 py-1 text-xs text-white hover:bg-accent-dark"
          >
            {saving ? "Saving..." : "Save"}
          </button>
          <button type="button" onClick={() => setEditing(false)} className="text-xs text-muted">
            Cancel
          </button>
        </div>
      </form>
    );
  }

  return (
    <div className="flex items-center gap-3 rounded-lg border border-border-warm bg-card p-4">
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={member.photo_url || "https://placehold.co/56x56/a9642b/ffffff?text=%20"}
        alt=""
        className="h-14 w-14 shrink-0 rounded-full border border-border-warm object-cover"
      />
      <div className="min-w-0 flex-1">
        <p className="font-medium">{member.name}</p>
        <p className="truncate text-sm text-muted">{member.email}</p>
        {member.linkedin_url && (
          <a
            href={member.linkedin_url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs text-accent hover:underline"
          >
            LinkedIn
          </a>
        )}
      </div>
      <div className="flex shrink-0 flex-col gap-1 text-xs">
        <button onClick={() => setEditing(true)} className="text-muted hover:text-accent">
          Edit
        </button>
        <button onClick={() => onDelete(member.id)} className="text-muted hover:text-red-600">
          Remove
        </button>
      </div>
    </div>
  );
}

export default function TeamPage() {
  const [members, setMembers] = useState<Member[] | null>(null);
  const [newMember, setNewMember] = useState(EMPTY);
  const [adding, setAdding] = useState(false);

  function load() {
    api.listMembers().then(setMembers);
  }

  useEffect(load, []);

  async function handleAdd(e: React.FormEvent) {
    e.preventDefault();
    if (!newMember.name.trim()) return;
    setAdding(true);
    try {
      await api.addMember(newMember);
      setNewMember(EMPTY);
      load();
    } finally {
      setAdding(false);
    }
  }

  async function handleSave(id: number, data: Omit<Member, "id">) {
    await api.updateMember(id, data);
    load();
  }

  async function handleDelete(id: number) {
    await api.deleteMember(id);
    load();
  }

  if (!members) return <p className="text-muted">Loading...</p>;

  return (
    <div>
      <h1 className="mb-1 text-xl font-semibold">Team</h1>
      <p className="mb-6 text-sm text-muted">
        Everyone at your company who shows up in warm-intro matching. Add each member's info so
        the chat can find the right person to ask for an introduction.
      </p>

      <div className="mb-6 grid gap-3 sm:grid-cols-2">
        {members.map((m) => (
          <MemberCard key={m.id} member={m} onSave={handleSave} onDelete={handleDelete} />
        ))}
      </div>

      <form onSubmit={handleAdd} className="max-w-md rounded-lg border border-dashed border-border-warm bg-card p-4">
        <h2 className="mb-3 text-sm font-medium">Add a team member</h2>
        <div className="flex flex-col gap-2">
          <input
            required
            placeholder="Name"
            className="rounded border border-border-warm px-3 py-2 text-sm"
            value={newMember.name}
            onChange={(e) => setNewMember({ ...newMember, name: e.target.value })}
          />
          <input
            placeholder="Email"
            className="rounded border border-border-warm px-3 py-2 text-sm"
            value={newMember.email}
            onChange={(e) => setNewMember({ ...newMember, email: e.target.value })}
          />
          <input
            placeholder="LinkedIn URL"
            className="rounded border border-border-warm px-3 py-2 text-sm"
            value={newMember.linkedin_url}
            onChange={(e) => setNewMember({ ...newMember, linkedin_url: e.target.value })}
          />
          <input
            placeholder="Photo URL"
            className="rounded border border-border-warm px-3 py-2 text-sm"
            value={newMember.photo_url}
            onChange={(e) => setNewMember({ ...newMember, photo_url: e.target.value })}
          />
          <button
            type="submit"
            disabled={adding}
            className="mt-1 w-fit rounded bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-dark disabled:opacity-50"
          >
            {adding ? "Adding..." : "Add member"}
          </button>
        </div>
      </form>
    </div>
  );
}
