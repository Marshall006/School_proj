"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Alert, Card } from "@/components/ui";

export default function ConnexionPage() {
  const router = useRouter();
  const { session, loading, login, register } = useAuth();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState({
    email: "",
    password: "",
    display_name: "",
    family_name: "",
    country_code: "FR",
  });

  useEffect(() => {
    if (!loading && session) router.replace("/foyer");
  }, [session, loading, router]);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      if (mode === "login") {
        await login(form.email, form.password);
      } else {
        await register(form);
      }
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "Une erreur inattendue est survenue.",
      );
    } finally {
      setBusy(false);
    }
  }

  const set = (key: keyof typeof form) => (event: React.ChangeEvent<HTMLInputElement>) =>
    setForm((current) => ({ ...current, [key]: event.target.value }));

  return (
    <main className="auth-page">
      <div className="auth-card stack">
        <div className="row" style={{ justifyContent: "center", marginBottom: 4 }}>
          <span className="brand-mark" style={{ width: 42, height: 42, fontSize: 18 }}>
            K
          </span>
          <div>
            <div className="brand-name" style={{ fontSize: "1.25rem" }}>
              KODA
            </div>
            <div className="brand-tagline">L&apos;ecran se merite.</div>
          </div>
        </div>

        <Card>
          <div className="row" style={{ marginBottom: 16, gap: 6 }}>
            <button
              type="button"
              className={`btn btn-sm${mode === "login" ? " btn-primary" : ""}`}
              onClick={() => setMode("login")}
            >
              Connexion
            </button>
            <button
              type="button"
              className={`btn btn-sm${mode === "register" ? " btn-primary" : ""}`}
              onClick={() => setMode("register")}
            >
              Creer un foyer
            </button>
          </div>

          <form className="stack" onSubmit={submit} style={{ gap: 13 }}>
            {mode === "register" && (
              <>
                <div className="field">
                  <label htmlFor="display_name">Votre prenom</label>
                  <input id="display_name" required value={form.display_name} onChange={set("display_name")} />
                </div>
                <div className="field">
                  <label htmlFor="family_name">Nom du foyer</label>
                  <input id="family_name" required value={form.family_name} onChange={set("family_name")} placeholder="Famille Diallo" />
                </div>
                <div className="field">
                  <label htmlFor="country">Pays</label>
                  <select
                    id="country"
                    value={form.country_code}
                    onChange={(event) => setForm((c) => ({ ...c, country_code: event.target.value }))}
                  >
                    <option value="FR">France</option>
                    <option value="BJ">Benin</option>
                    <option value="CI">Cote d&apos;Ivoire</option>
                    <option value="SN">Senegal</option>
                  </select>
                  <span className="help">Determine les programmes scolaires proposes.</span>
                </div>
              </>
            )}

            <div className="field">
              <label htmlFor="email">Adresse e-mail</label>
              <input id="email" type="email" required autoComplete="email" value={form.email} onChange={set("email")} />
            </div>
            <div className="field">
              <label htmlFor="password">Mot de passe</label>
              <input
                id="password"
                type="password"
                required
                minLength={8}
                autoComplete={mode === "login" ? "current-password" : "new-password"}
                value={form.password}
                onChange={set("password")}
              />
              {mode === "register" && <span className="help">8 caracteres minimum.</span>}
            </div>

            {error && <Alert tone="critical">{error}</Alert>}

            <button className="btn btn-primary btn-block" type="submit" disabled={busy}>
              {busy ? "Un instant…" : mode === "login" ? "Se connecter" : "Creer le foyer"}
            </button>
          </form>
        </Card>

        <Card>
          <p className="small secondary">
            <strong>Compte de demonstration</strong> — apres <code>make demo</code> :
            <br />
            <code>demo@koda.app</code> · <code>demo-koda-2026</code>
          </p>
        </Card>
      </div>
    </main>
  );
}
