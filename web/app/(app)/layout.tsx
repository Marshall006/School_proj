"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";

import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { AVATARS } from "@/lib/format";
import {
  IconCalendar,
  IconCopies,
  IconDevice,
  IconHome,
  IconLogout,
  IconMoon,
  IconSun,
} from "@/components/icons";

const LINKS = [
  { href: "/foyer", label: "Vue d'ensemble", Icon: IconHome },
  { href: "/copies", label: "Copies à valider", Icon: IconCopies },
  { href: "/appareils", label: "Appareils", Icon: IconDevice },
  { href: "/calendrier", label: "Calendrier", Icon: IconCalendar },
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
    const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
    const next =
      theme === "dark" ? "light" : theme === "light" ? "dark" : prefersDark ? "light" : "dark";
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

  const isDark =
    theme === "dark" ||
    (theme === null && typeof window !== "undefined" && window.matchMedia("(prefers-color-scheme: dark)").matches);

  return (
    <div className="shell">
      <aside className="sidebar">
        <Link href="/foyer" className="brand">
          <span className="brand-mark">K</span>
          <span>
            <span className="brand-name">KODA</span>
            <br />
            <span className="brand-tagline">L&apos;écran se mérite.</span>
          </span>
        </Link>

        <nav className="nav">
          {LINKS.map(({ href, label, Icon }) => (
            <Link
              key={href}
              href={href}
              className="nav-item"
              aria-current={pathname === href ? "page" : undefined}
            >
              <Icon size={18} />
              {label}
              {href === "/copies" && pending > 0 && <span className="nav-badge">{pending}</span>}
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
              <span aria-hidden="true" style={{ fontSize: 17, lineHeight: 1 }}>
                {AVATARS[child.avatar] ?? "🙂"}
              </span>
              {child.display_name}
              <span className="muted small" style={{ marginLeft: "auto" }}>
                {child.grade_code}
              </span>
            </Link>
          ))}
        </nav>

        <div className="spacer" />

        <div className="stack" style={{ gap: 10 }}>
          <button className="btn btn-sm" onClick={toggleTheme}>
            {isDark ? <IconSun size={15} /> : <IconMoon size={15} />}
            {isDark ? "Thème clair" : "Thème sombre"}
          </button>
          <div className="small secondary" style={{ padding: "0 8px", lineHeight: 1.4 }}>
            <strong style={{ color: "var(--ink)" }}>{session.parent.display_name}</strong>
            <br />
            <span className="muted">{session.family.name}</span>
          </div>
          <button className="btn btn-sm" onClick={() => void logout()}>
            <IconLogout size={15} />
            Se déconnecter
          </button>
        </div>
      </aside>

      <main className="main">{children}</main>
    </div>
  );
}
