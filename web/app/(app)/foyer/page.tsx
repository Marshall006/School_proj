"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import type { Child, Dashboard } from "@koda/shared";

import { ApiError, api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { AVATARS, PERIOD_LABELS, countdown, minutes } from "@/lib/format";
import { UnlockDialog } from "@/components/UnlockDialog";
import { Alert, Card, Empty, Loading, Modal, Stat, Tag } from "@/components/ui";

type Status = Dashboard["status"];

export default function FoyerPage() {
  const { children, refreshChildren, session } = useAuth();
  const [statuses, setStatuses] = useState<Record<string, Status>>({});
  const [overview, setOverview] = useState<{ children_count: number; active_sessions: number; open_lockouts: number; total_xp: number } | null>(null);
  const [coverage, setCoverage] = useState<{ total_questions: number; total_topics: number } | null>(null);
  const [audit, setAudit] = useState<{ events: number; integrity?: { valid: boolean } } | null>(null);
  const [loading, setLoading] = useState(true);
  // On memorise aussi la nature du deverrouillage : pendant les vacances, le
  // deverrouillage direct est coupe et seule la rallonge exceptionnelle reste.
  const [unlockFor, setUnlockFor] = useState<{ child: Child; kind: "direct" | "bonus" } | null>(
    null,
  );
  const [creating, setCreating] = useState(false);

  const load = useCallback(async () => {
    const list = await refreshChildren();
    const entries = await Promise.all(
      list.map(async (child) => {
        try {
          return [child.id, await api.children.status(child.id)] as const;
        } catch {
          return [child.id, null] as const;
        }
      }),
    );
    setStatuses(Object.fromEntries(entries.filter(([, value]) => value)) as Record<string, Status>);
    const [ov, cov, aud] = await Promise.allSettled([
      api.family.overview(),
      api.catalog.coverage(),
      api.family.audit(true),
    ]);
    if (ov.status === "fulfilled") setOverview(ov.value);
    if (cov.status === "fulfilled") setCoverage(cov.value);
    if (aud.status === "fulfilled") setAudit(aud.value);
    setLoading(false);
  }, [refreshChildren]);

  useEffect(() => {
    void load();
    const timer = window.setInterval(() => void load(), 30_000);
    return () => window.clearInterval(timer);
  }, [load]);

  if (loading) return <Loading />;

  return (
    <>
      <div className="page-head">
        <div className="grow">
          <h1>Bonjour {session?.parent.display_name}</h1>
          <p className="page-subtitle">
            {children.length === 0
              ? "Commencez par ajouter un enfant, puis appairez sa tablette."
              : "Etat des tablettes du foyer, en temps reel."}
          </p>
        </div>
        <button className="btn btn-primary" onClick={() => setCreating(true)}>
          + Ajouter un enfant
        </button>
      </div>

      <div className="stack">
        {children.length === 0 ? (
          <Card>
            <Empty>
              Aucun enfant enregistre. Ajoutez-en un pour commencer : vous pourrez ensuite appairer
              sa tablette et definir les regles du foyer.
            </Empty>
          </Card>
        ) : (
          <div className="grid grid-2">
            {children.map((child) => (
              <ChildCard
                key={child.id}
                child={child}
                status={statuses[child.id]}
                onUnlock={(kind) => setUnlockFor({ child, kind })}
                onChanged={load}
              />
            ))}
          </div>
        )}

        <div className="grid grid-4">
          <Stat label="Enfants" value={overview?.children_count ?? children.length} />
          <Stat
            label="Tablettes ouvertes"
            value={overview?.active_sessions ?? 0}
            hint={overview?.active_sessions ? "session en cours" : "tout est verrouille"}
          />
          <Stat
            label="Temps de carence"
            value={overview?.open_lockouts ?? 0}
            hint={overview?.open_lockouts ? "revision en cours" : "aucun blocage"}
            tone={overview?.open_lockouts ? "warning" : undefined}
          />
          <Stat label="Experience cumulee" value={(overview?.total_xp ?? 0).toLocaleString("fr-FR")} hint="XP disponibles" />
        </div>

        <div className="grid grid-2">
          <Card title="Banque pedagogique" hint="contenu disponible">
            {coverage ? (
              <p className="secondary">
                <strong className="tabular">{coverage.total_questions.toLocaleString("fr-FR")}</strong>{" "}
                questions reparties sur <strong>{coverage.total_topics}</strong> notions, par pays et
                par classe. Le moteur y puise pour composer chaque evaluation.
              </p>
            ) : (
              <Empty>Contenu indisponible.</Empty>
            )}
          </Card>

          <Card title="Journal du foyer" hint="integrite verifiee">
            {audit ? (
              <div className="stack" style={{ gap: 10 }}>
                <p className="secondary">
                  <strong className="tabular">{audit.events}</strong> evenements enregistres
                  (codes emis, evaluations, modifications de regles).
                </p>
                {audit.integrity?.valid ? (
                  <Alert tone="good">
                    Chaine d&apos;audit intacte : l&apos;historique affiche n&apos;a pas ete modifie.
                  </Alert>
                ) : (
                  <Alert tone="critical">Anomalie detectee dans le journal du foyer.</Alert>
                )}
              </div>
            ) : (
              <Empty>Journal indisponible.</Empty>
            )}
          </Card>
        </div>
      </div>

      {unlockFor && (
        <UnlockDialog
          child={unlockFor.child}
          kind={unlockFor.kind}
          onClose={() => {
            setUnlockFor(null);
            void load();
          }}
        />
      )}
      {creating && (
        <NewChildDialog
          onClose={() => setCreating(false)}
          onCreated={() => {
            setCreating(false);
            void load();
          }}
        />
      )}
    </>
  );
}

function ChildCard({
  child,
  status,
  onUnlock,
  onChanged,
}: {
  child: Child;
  status?: Status;
  onUnlock: (kind: "direct" | "bonus") => void;
  onChanged: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const session = status?.session ?? null;
  const lockout = status?.lockout ?? null;

  const state = status?.screen_state ?? "locked";
  const tone = state === "unlocked" ? "good" : state === "paused" ? "warning" : undefined;
  const stateLabel =
    state === "unlocked" ? "Tablette ouverte" : state === "paused" ? "En pause (ecran eteint)" : "Verrouillee";

  async function stopSession() {
    if (!session) return;
    setBusy(true);
    try {
      await api.screen.stop(session.id);
      onChanged();
    } finally {
      setBusy(false);
    }
  }

  async function releaseLockout() {
    setBusy(true);
    try {
      await api.children.releaseLockout(child.id);
      onChanged();
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card>
      <div className="row" style={{ marginBottom: 12 }}>
        <span style={{ fontSize: 30 }} aria-hidden="true">
          {AVATARS[child.avatar] ?? "🙂"}
        </span>
        <div>
          <Link href={`/enfants/${child.id}`}>
            <h2 style={{ marginBottom: 1 }}>{child.display_name}</h2>
          </Link>
          <span className="small muted">
            {child.grade_code} · {status ? PERIOD_LABELS[status.period_type] : "—"}
          </span>
        </div>
        <span className="spacer" />
        <Tag tone={tone}>{stateLabel}</Tag>
      </div>

      {session ? (
        <div className="stack" style={{ gap: 8, marginBottom: 12 }}>
          <div className="row">
            <span className="hero-figure" style={{ fontSize: "2rem" }}>
              {minutes(session.remaining_minutes)}
            </span>
            <span className="small secondary">restant sur {minutes(session.granted_minutes)}</span>
          </div>
          <div style={{ height: 8, background: "var(--surface-sunken)", borderRadius: 4, overflow: "hidden" }}>
            <div
              style={{
                height: "100%",
                width: `${Math.max(2, (session.remaining_ms / (session.granted_minutes * 60000 || 1)) * 100)}%`,
                background: "var(--data-1)",
                borderRadius: 4,
              }}
            />
          </div>
          {session.anomaly_count > 0 && (
            <Alert tone="warning">
              {session.anomaly_count} incoherence detectee pendant cette session (horloge ou
              redemarrage).
            </Alert>
          )}
        </div>
      ) : lockout ? (
        <div className="stack" style={{ gap: 8, marginBottom: 12 }}>
          <Alert tone="warning">
            <strong>Temps de carence — {countdown(lockout.remaining_seconds)}</strong>
            <br />
            <span className="small">{lockout.message ?? "Revision en cours avant la prochaine tentative."}</span>
          </Alert>
        </div>
      ) : (
        <p className="secondary small" style={{ marginBottom: 12 }}>
          {status?.unlock_paths.assessment
            ? `${child.display_name} peut ouvrir la tablette en reussissant une evaluation.`
            : "Aucune session en cours."}
        </p>
      )}

      <div className="row" style={{ gap: 8 }}>
        <span className="tag">{child.xp_balance.toLocaleString("fr-FR")} XP</span>
        {child.streak_days > 1 && <span className="tag">Serie de {child.streak_days} jours</span>}
        {status && (
          <span className="tag">
            {status.screen_time_today.granted_minutes}/{status.screen_time_today.cap_minutes} min aujourd&apos;hui
          </span>
        )}
      </div>

      <hr className="divider" />

      <div className="row" style={{ gap: 8 }}>
        {status?.unlock_paths.parent_direct ? (
          <button className="btn btn-primary btn-sm" onClick={() => onUnlock("direct")}>
            Debloquer
          </button>
        ) : (
          <button
            className="btn btn-sm"
            onClick={() => onUnlock("bonus")}
            title="Le deverrouillage direct est coupe pendant cette periode"
          >
            Accorder une rallonge
          </button>
        )}
        {session && (
          <button className="btn btn-sm btn-danger" onClick={() => void stopSession()} disabled={busy}>
            Couper maintenant
          </button>
        )}
        {lockout && (
          <button className="btn btn-sm" onClick={() => void releaseLockout()} disabled={busy}>
            Lever la carence
          </button>
        )}
        <span className="spacer" />
        <Link className="btn btn-sm" href={`/enfants/${child.id}`}>
          Details
        </Link>
      </div>
    </Card>
  );
}

function NewChildDialog({ onClose, onCreated }: { onClose: () => void; onCreated: () => void }) {
  const [form, setForm] = useState({ display_name: "", grade_code: "CM1", country_code: "FR", pin: "" });
  const [grades, setGrades] = useState<Array<{ code: string; name: string }>>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.catalog
      .countries()
      .then((countries) => {
        const country = countries.find((c) => c.code === form.country_code);
        setGrades(country?.grades ?? []);
      })
      .catch(() => setGrades([]));
  }, [form.country_code]);

  async function submit() {
    setBusy(true);
    setError(null);
    try {
      await api.children.create({
        display_name: form.display_name,
        grade_code: form.grade_code,
        country_code: form.country_code,
        pin: form.pin || undefined,
      });
      onCreated();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Creation impossible.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal
      title="Ajouter un enfant"
      onClose={onClose}
      footer={
        <>
          <button className="btn" onClick={onClose}>
            Annuler
          </button>
          <button className="btn btn-primary" onClick={() => void submit()} disabled={busy || !form.display_name}>
            {busy ? "Creation…" : "Ajouter"}
          </button>
        </>
      }
    >
      <div className="stack" style={{ gap: 13 }}>
        <div className="field">
          <label htmlFor="name">Prenom</label>
          <input
            id="name"
            value={form.display_name}
            onChange={(event) => setForm((c) => ({ ...c, display_name: event.target.value }))}
          />
        </div>
        <div className="row" style={{ gap: 12, alignItems: "flex-end" }}>
          <div className="field" style={{ flex: 1 }}>
            <label htmlFor="pays">Pays</label>
            <select
              id="pays"
              value={form.country_code}
              onChange={(event) => setForm((c) => ({ ...c, country_code: event.target.value }))}
            >
              <option value="FR">France</option>
              <option value="BJ">Benin</option>
              <option value="CI">Cote d&apos;Ivoire</option>
              <option value="SN">Senegal</option>
            </select>
          </div>
          <div className="field" style={{ flex: 1 }}>
            <label htmlFor="classe">Classe</label>
            <select
              id="classe"
              value={form.grade_code}
              onChange={(event) => setForm((c) => ({ ...c, grade_code: event.target.value }))}
            >
              {grades.map((grade) => (
                <option key={grade.code} value={grade.code}>
                  {grade.name}
                </option>
              ))}
            </select>
          </div>
        </div>
        <div className="field">
          <label htmlFor="pin">NIP de l&apos;enfant (facultatif)</label>
          <input
            id="pin"
            inputMode="numeric"
            pattern="\d{4,6}"
            maxLength={6}
            value={form.pin}
            onChange={(event) => setForm((c) => ({ ...c, pin: event.target.value.replace(/\D/g, "") }))}
          />
          <span className="help">4 a 6 chiffres, pour ouvrir sa session sur la tablette.</span>
        </div>
        {error && <Alert tone="critical">{error}</Alert>}
      </div>
    </Modal>
  );
}
