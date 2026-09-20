"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import type { Child, Session } from "@koda/shared";

import { api, tokens } from "./api";

interface AuthValue {
  session: Session | null;
  children: Child[];
  loading: boolean;
  error: string | null;
  login: (email: string, password: string) => Promise<void>;
  register: (payload: {
    email: string;
    password: string;
    display_name: string;
    family_name: string;
    country_code?: string;
  }) => Promise<void>;
  logout: () => Promise<void>;
  refreshChildren: () => Promise<Child[]>;
}

const AuthContext = createContext<AuthValue | null>(null);

export function AuthProvider({ children: tree }: { children: React.ReactNode }) {
  const router = useRouter();
  const [session, setSession] = useState<Session | null>(null);
  const [children, setChildren] = useState<Child[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refreshChildren = useCallback(async () => {
    const list = await api.children.list();
    setChildren(list);
    return list;
  }, []);

  useEffect(() => {
    let cancelled = false;
    async function boot() {
      if (!tokens.access) {
        setLoading(false);
        return;
      }
      try {
        const me = await api.auth.me();
        if (cancelled) return;
        setSession(me);
        await refreshChildren();
      } catch {
        tokens.clear();
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    void boot();
    return () => {
      cancelled = true;
    };
  }, [refreshChildren]);

  const login = useCallback(
    async (email: string, password: string) => {
      setError(null);
      const result = await api.auth.login(email, password);
      tokens.set(result.tokens.access_token, result.tokens.refresh_token);
      setSession(result);
      await refreshChildren();
      router.push("/foyer");
    },
    [refreshChildren, router],
  );

  const register = useCallback(
    async (payload: Parameters<AuthValue["register"]>[0]) => {
      setError(null);
      const result = await api.auth.register(payload);
      tokens.set(result.tokens.access_token, result.tokens.refresh_token);
      setSession(result);
      setChildren([]);
      router.push("/foyer");
    },
    [router],
  );

  const logout = useCallback(async () => {
    try {
      await api.auth.logout();
    } catch {
      /* la session locale part de toute facon */
    }
    tokens.clear();
    setSession(null);
    setChildren([]);
    router.push("/connexion");
  }, [router]);

  const value = useMemo<AuthValue>(
    () => ({ session, children, loading, error, login, register, logout, refreshChildren }),
    [session, children, loading, error, login, register, logout, refreshChildren],
  );

  return <AuthContext.Provider value={value}>{tree}</AuthContext.Provider>;
}

export function useAuth(): AuthValue {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth doit être utilisé dans AuthProvider");
  return context;
}
