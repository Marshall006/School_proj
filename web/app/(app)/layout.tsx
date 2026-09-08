"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";

import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { AVATARS } from "@/lib/format";

const LINKS = [
  { href: "/foyer", label: "Vue d'ensemble", icon: "◧" },
  { href: "/copies", label: "Copies a valider", icon: "✎" },
  { href: "/appareils", label: "Appareils", icon: "▭" },
  { href: "/calendrier", label: "Calendrier", icon: "▤" },
];

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const { session, children: kids, loading, logout } = useAuth();
  const [pending, setPending] = useState(0);
  const [theme, setTheme] = useState<"light" | "dark" | null>(null);

  useEffect(() => {
    if (!loading && !session) router.replace("/connexion");
  }, [session, loading, router]);

  useEffect(() => {
    if (!session) return;
    api.assessments
      .pendingReview()
      .then((rows) => setPending(rows.length))
      .catch(() => setPending(0));
  }, [session, pathname]);

  useEffect(() => {
    const stored = window.localStorage.getItem("koda.theme") as "light" | "dark" | null;
    if (stored) {
      setTheme(stored);
      document.documentElement.dataset.theme = stored;
    }
  }, []);

  function toggleTheme() {
    const next =
      theme === "dark" ? "light" : theme === "light" ? "dark" : window.matchMedia("(prefers-color-scheme: dark)").matches ? "light" : "dark";
    setTheme(next);
    document.documentElement.dataset.theme = next;
    window.localStorage.setItem("koda.theme", next);
  }

  if (loading || !session) {
    return (
      <main className="auth-page">
        <p className="muted">Chargement…</p>
      </main>
    );
  }

  return (
    <div className="shell">
      <aside className="sidebar">
        <Link href="/foyer" className="brand">
          <span className="brand-mark">K</span>
          <span>
            <span className="brand-name">KODA</span>
            <br />
            <span className="brand-tagline">L&apos;ecran se merite.</span>
          </span>
        </Link>

        <nav className="nav">
          {LINKS.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className="nav-item"
              aria-current={pathname === link.href ? "page" : undefined}
            >
              <span aria-hidden="true">{link.icon}</span>
              {link.label}
              {link.href === "/copies" && pending > 0 && <span className="nav-badge">{pending}</span>}
            </Link>
          ))}

          <span className="nav-label">Enfants</span>
          {kids.length === 0 && <span className="nav-item muted">Aucun enfant</span>}
          {kids.map((child) => (
            <Link
              key={child.id}
              href={`/enfants/${child.id}`}
              className="nav-item"
              aria-current={pathname.startsWith(`/enfants/${child.id}`) ? "page" : undefined}
            >
              <span aria-hidden="true">{AVATARS[child.avatar] ?? "🙂"}</span>
              {child.display_name}
              <span className="muted small" style={{ marginLeft: "auto" }}>
                {child.grade_code}
              </span>
            </Link>
          ))}
        </nav>

        <div className="spacer" />

        <div className="stack" style={{ gap: 8 }}>
          <button className="btn btn-sm" onClick={toggleTheme}>
            {theme === "dark" ? "☀ Theme clair" : "☾ Theme sombre"}
          </button>
          <div className="small secondary" style={{ padding: "0 8px" }}>
            {session.parent.display_name}
            <br />
            <span className="muted">{session.family.name}</span>
          </div>
          <button className="btn btn-sm" onClick={() => void logout()}>
            Se deconnecter
          </button>
        </div>
      </aside>

      <main className="main">{children}</main>
    </div>
  );
}
