"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

import { useAuth } from "@/lib/auth";

export default function Home() {
  const router = useRouter();
  const { session, loading } = useAuth();

  useEffect(() => {
    if (loading) return;
    router.replace(session ? "/foyer" : "/connexion");
  }, [session, loading, router]);

  return (
    <main className="auth-page">
      <p className="muted">Chargement…</p>
    </main>
  );
}
