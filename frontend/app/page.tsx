import Link from "next/link";

const sections = [
  {
    href: "/team",
    title: "Team",
    description: "Your company's members: name, email, LinkedIn, and photo.",
  },
  {
    href: "/dashboard",
    title: "Dashboard",
    description: "Past events: sponsors, turnout, and what worked.",
  },
  {
    href: "/chat",
    title: "Chat",
    description: "Describe your next event idea and get contact/plan suggestions.",
  },
];

export default function Home() {
  return (
    <div className="grid gap-4 sm:grid-cols-3">
      {sections.map((s) => (
        <Link
          key={s.href}
          href={s.href}
          className="rounded-lg border border-border-warm bg-card p-6 transition hover:border-accent hover:shadow-sm"
        >
          <h2 className="mb-1 font-semibold">{s.title}</h2>
          <p className="text-sm text-muted">{s.description}</p>
        </Link>
      ))}
    </div>
  );
}
