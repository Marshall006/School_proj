"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Alert, Card } from "@/components/ui";
import { IconBook, IconLock, IconStar } from "@/components/icons";

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
      setError(err instanceof ApiError ? err.message : "Une erreur inattendue est survenue.");
    } finally {
      setBusy(false);
    }
  }

  const set = (key: keyof typeof form) => (event: React.ChangeEvent<HTMLInputElement>) =>
    setForm((current) => ({ ...current, [key]: event.target.value }));

  return (
    <main className="auth-page">
      <div className="auth-card stack">
        <div className="row" style={{ justifyContent: "center", marginBottom: 2 }}>
          <span className="brand-mark" style={{ width: 46, height: 46, fontSize: 20 }}>
            K
          </span>
          <div>
            <div className="brand-name" style={{ fontSize: "1.375rem" }}>
              KODA
            </div>
            <div className="brand-tagline">L&apos;écran se mérite.</div>
          </div>
        </div>

        <ul className="auth-pitch">
          <li>
            <IconLock size={16} />
            La tablette reste verrouillée tant que le travail n&apos;est pas fait.
          </li>
          <li>
            <IconBook size={16} />
            L&apos;enfant passe une évaluation : réussie, elle ouvre l&apos;écran.
          </li>
          <li>
            <IconStar size={16} />
            Vous voyez où il progresse, et où il faut l&apos;aider.
          </li>
        </ul>

        <Card>
          <div className="segmented" style={{ marginBottom: 18, width: "100%" }}>
            <button
              type="button"
              aria-pressed={mode === "login"}
              onClick={() => setMode("login")}
              style={{ flex: 1, justifyContent: "center" }}
            >
              Connexion
            </button>
            <button
              type="button"
              aria-pressed={mode === "register"}
              onClick={() => setMode("register")}
              style={{ flex: 1, justifyContent: "center" }}
            >
              Créer un foyer
            </button>
          </div>

          <form className="stack" onSubmit={submit} style={{ gap: 14 }}>
            {mode === "register" && (
              <>
                <div className="field">
                  <label htmlFor="display_name">Votre prénom</label>
                  <input
                    id="display_name"
                    required
                    value={form.display_name}
                    onChange={set("display_name")}
                  />
                </div>
                <div className="field">
                  <label htmlFor="family_name">Nom du foyer</label>
                  <input
                    id="family_name"
                    required
                    value={form.family_name}
                    onChange={set("family_name")}
                    placeholder="Famille Diallo"
                  />
                </div>
                <div className="field">
                  <label htmlFor="country">Pays</label>
                  <select
                    id="country"
                    value={form.country_code}
                    onChange={(event) =>
                      setForm((c) => ({ ...c, country_code: event.target.value }))
                    }
                  >
                    <option value="FR">France</option>
                    <option value="BJ">Bénin</option>
                    <option value="CI">Côte d&apos;Ivoire</option>
                    <option value="SN">Sénégal</option>
                  </select>
                  <span className="help">Détermine les programmes scolaires proposés.</span>
                </div>
              </>
            )}

            <div className="field">
              <label htmlFor="email">Adresse e-mail</label>
              <input
                id="email"
                type="email"
                required
                autoComplete="email"
                value={form.email}
                onChange={set("email")}
              />
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
              {mode === "register" && <span className="help">8 caractères minimum.</span>}
            </div>

            {error && <Alert tone="critical">{error}</Alert>}

            <button className="btn btn-primary btn-block" type="submit" disabled={busy}>
              {busy ? "Un instant…" : mode === "login" ? "Se connecter" : "Créer le foyer"}
            </button>
          </form>
        </Card>

        <p className="small muted" style={{ textAlign: "center", lineHeight: 1.7 }}>
          <strong>Compte de démonstration</strong> — après <code>make demo</code> :<br />
          <code>demo@koda.app</code> · <code>demo-koda-2026</code>
        </p>
      </div>
    </main>
  );
}
