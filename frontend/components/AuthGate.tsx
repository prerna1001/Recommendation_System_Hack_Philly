"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api, ApiError, type Company } from "@/lib/api";

const PUBLIC_PATHS = ["/login", "/signup"];

export default function AuthGate({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const isPublic = PUBLIC_PATHS.includes(pathname);

  const [company, setCompany] = useState<Company | null>(null);
  const [checked, setChecked] = useState(false);

  useEffect(() => {
    if (isPublic) {
      setChecked(true);
      return;
    }
    api.auth
      .me()
      .then(setCompany)
      .catch((err) => {
        if (err instanceof ApiError && err.status === 401) {
          router.replace("/login");
        }
      })
      .finally(() => setChecked(true));
  }, [isPublic, router]);

  async function handleLogout() {
    await api.auth.logout();
    setCompany(null);
    router.push("/login");
  }

  return (
    <>
      <header className="border-b border-border-warm bg-card">
        <nav className="mx-auto flex max-w-5xl items-center justify-between gap-6 px-6 py-4">
          <div className="flex items-center gap-6">
            <Link href="/" className="font-semibold tracking-tight text-foreground">
              ☕ Code & Coffee Connector
            </Link>
            {company && (
              <div className="flex gap-5 text-sm text-muted">
                <Link href="/team" className="hover:text-accent">Team</Link>
                <Link href="/dashboard" className="hover:text-accent">Dashboard</Link>
                <Link href="/chat" className="hover:text-accent">Chat</Link>
              </div>
            )}
          </div>
          {company && (
            <div className="flex items-center gap-3 text-sm text-muted">
              <span>{company.name}</span>
              <button onClick={handleLogout} className="text-accent hover:underline">
                Log out
              </button>
            </div>
          )}
        </nav>
      </header>
      <main className="mx-auto w-full max-w-5xl flex-1 px-6 py-8">
        {!checked ? <p className="text-muted">Loading...</p> : isPublic || company ? children : null}
      </main>
    </>
  );
}
