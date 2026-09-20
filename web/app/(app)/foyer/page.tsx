"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import type { Child, Dashboard } from "@koda/shared";

import { ApiError, api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { AVATARS, PERIOD_LABELS, countdown, minutes } from "@/lib/format";
import { UnlockDialog } from "@/components/UnlockDialog";
import { Alert, Card, Empty, Loading, Modal, Stat, Tag } from "@/components/ui";
import {
  IconArrow,
  IconBook,
  IconCheck,
  IconClock,
  IconFlame,
  IconLock,
  IconPlus,
  IconShield,
  IconStar,
  IconUnlock,
} from "@/components/icons";

type Status = Dashboard["status"];

export default function FoyerPage() {
  const { children, refreshChildren, session } = useAuth();
  const [statuses, setStatuses] = useState<Record<string, Status>>({});
  const [overview, setOverview] = useState<{
    children_count: number;
    active_sessions: number;
    open_lockouts: number;
    total_xp: number;
  } | null>(null);
  const [coverage, setCoverage] = useState<{ total_questions: number; total_topics: number } | null>(null);
  const [audit, setAudit] = useState<{ events: number; integrity?: { valid: boolean } } | null>(null);
  const [loading, setLoading] = useState(true);
  const [unlockFor, setUnlockFor] = useState<{ child: Child; kind: "direct" | "bonus" } | null>(null);
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

  const today = new Intl.DateTimeFormat("fr-FR", {
    weekday: "long",
    day: "numeric",
    month: "long",
  }).format(new Date());

  return (
    <>
      <div className="page-head">
        <div className="grow">
          <p className="small muted" style={{ textTransform: "capitalize", marginBottom: 2 }}>
            {today}
          </p>
          <h1>Bonjour {session?.parent.display_name}</h1>
          <p className="page-subtitle">
            {children.length === 0
              ? "Commencez par ajouter un enfant, puis appairez sa tablette."
              : "État des tablettes du foyer, en temps réel."}
          </p>
        </div>
        <button className="btn btn-primary" onClick={() => setCreating(true)}>
          <IconPlus size={16} />
          Ajouter un enfant
        </button>
      </div>

      <div className="stack">
        {children.length === 0 ? (
          <Card>
            <Empty>
              Aucun enfant enregistré. Ajoutez-en un pour commencer : vous pourrez ensuite appairer
              sa tablette et définir les règles du foyer.
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
            hint={overview?.active_sessions ? "session en cours" : "tout est verrouillé"}
          />
          <Stat
            label="Temps de carence"
            value={overview?.open_lockouts ?? 0}
            hint={overview?.open_lockouts ? "révision en cours" : "aucun blocage"}
            tone={overview?.open_lockouts ? "warning" : undefined}
          />
          <Stat
            label="Expérience cumulée"
            value={(overview?.total_xp ?? 0).toLocaleString("fr-FR")}
            hint="XP disponibles"
          />
        </div>

        <div className="grid grid-2">
          <Card
            title={
              <span className="row" style={{ gap: 8 }}>
                <IconBook size={17} /> Banque pédagogique
              </span>
            }
            hint="contenu disponible"
          >
            {coverage ? (
              <p className="secondary">
                <strong className="tabular" style={{ fontSize: "1.35rem", color: "var(--ink)" }}>
                  {coverage.total_questions.toLocaleString("fr-FR")}
                </strong>{" "}
                questions réparties sur <strong>{coverage.total_topics}</strong> notions, par pays et
                par classe. Le moteur y puise pour composer chaque évaluation.
              </p>
            ) : (
              <Empty>Contenu indisponible.</Empty>
            )}
          </Card>

          <Card
            title={
              <span className="row" style={{ gap: 8 }}>
                <IconShield size={17} /> Journal du foyer
              </span>
            }
            hint="intégrité vérifiée"
          >
            {audit ? (
              <div className="stack" style={{ gap: 12 }}>
                <p className="secondary">
                  <strong className="tabular" style={{ fontSize: "1.35rem", color: "var(--ink)" }}>
                    {audit.events}
                  </strong>{" "}
                  événements enregistrés (codes émis, évaluations, modifications de règles).
                </p>
                {audit.integrity?.valid ? (
                  <Alert tone="good">
                    Chaîne d&apos;audit intacte : l&apos;historique affiché n&apos;a pas été modifié.
                  </Alert>
                ) : (
                  <Alert tone="critical">Anomalie détectée dans le journal du foyer.</Alert>
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
    state === "unlocked" ? "Tablette ouverte" : state === "paused" ? "En pause" : "Verrouillée";
  const StateIcon = state === "locked" ? IconLock : IconUnlock;

  async function act(action: () => Promise<unknown>) {
    setBusy(true);
    try {
      await action();
      onChanged();
    } finally {
      setBusy(false);
    }
  }

  const cardClass = session ? "" : lockout ? "is-cooldown" : "is-locked";
  const ratio = session ? session.remaining_ms / (session.granted_minutes * 60000 || 1) : 0;

  return (
    <Card className={`child-card ${cardClass}`}>
      <div className="row" style={{ marginBottom: 14, gap: 12 }}>
        <span className="avatar" aria-hidden="true">
          {AVATARS[child.avatar] ?? "🙂"}
        </span>
        <div style={{ minWidth: 0 }}>
          <Link href={`/enfants/${child.id}`}>
            <h2 style={{ marginBottom: 1 }}>{child.display_name}</h2>
          </Link>
          <span className="small muted">
            {child.grade_code} · {status ? PERIOD_LABELS[status.period_type] : "—"}
          </span>
        </div>
        <span className="spacer" />
        <Tag tone={tone}>
          <StateIcon size={13} />
          {stateLabel}
        </Tag>
      </div>

      {session ? (
        <div className="stack" style={{ gap: 10, marginBottom: 14 }}>
          <div className="row" style={{ alignItems: "baseline", gap: 10 }}>
            <span className="hero-figure" style={{ fontSize: "2.125rem" }}>
              {minutes(session.remaining_minutes)}
            </span>
            <span className="small secondary">restant sur {minutes(session.granted_minutes)}</span>
          </div>
          <div className="meter">
            <span style={{ width: `${Math.max(2, ratio * 100)}%` }} />
          </div>
          {session.anomaly_count > 0 && (
            <Alert tone="warning">
              {session.anomaly_count} incohérence détectée pendant cette session (horloge ou
              redémarrage).
            </Alert>
          )}
        </div>
      ) : lockout ? (
        <div className="stack" style={{ gap: 10, marginBottom: 14 }}>
          <div className="row" style={{ alignItems: "baseline", gap: 10 }}>
            <span className="hero-figure" style={{ fontSize: "2.125rem", color: "var(--serious-ink)" }}>
              {countdown(lockout.remaining_seconds)}
            </span>
            <span className="small secondary">de révision</span>
          </div>
          <p className="small secondary">
            {lockout.message ?? "Révision en cours avant la prochaine tentative."}
          </p>
        </div>
      ) : (
        <p className="secondary small" style={{ marginBottom: 14 }}>
          {status?.unlock_paths.assessment
            ? `${child.display_name} peut ouvrir la tablette en réussissant une évaluation.`
            : "Aucune session en cours."}
        </p>
      )}

      <div className="row" style={{ gap: 8 }}>
        <span className="tag tag-gold">
          <IconStar size={13} />
          {child.xp_balance.toLocaleString("fr-FR")} XP
        </span>
        {child.streak_days > 1 && (
          <span className="tag">
            <IconFlame size={13} />
            {child.streak_days} jours
          </span>
        )}
        {status && (
          <span className="tag">
            <IconClock size={13} />
            {status.screen_time_today.granted_minutes}/{status.screen_time_today.cap_minutes} min
          </span>
        )}
      </div>

      <hr className="divider" />

      <div className="row" style={{ gap: 8 }}>
        {status?.unlock_paths.parent_direct ? (
          <button className="btn btn-primary btn-sm" onClick={() => onUnlock("direct")}>
            <IconUnlock size={15} />
            Débloquer
          </button>
        ) : (
          <button
            className="btn btn-sm"
            onClick={() => onUnlock("bonus")}
            title="Le déverrouillage direct est coupé pendant cette période"
          >
            <IconClock size={15} />
            Accorder une rallonge
          </button>
        )}
        {session && (
          <button
            className="btn btn-sm btn-danger"
            onClick={() => void act(() => api.screen.stop(session.id))}
            disabled={busy}
          >
            Couper
          </button>
        )}
        {lockout && (
          <button
            className="btn btn-sm"
            onClick={() => void act(() => api.children.releaseLockout(child.id))}
            disabled={busy}
          >
            <IconCheck size={15} />
            Lever la carence
          </button>
        )}
        <span className="spacer" />
        <Link className="btn btn-sm" href={`/enfants/${child.id}`}>
          Détails
          <IconArrow size={15} />
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
      .then((countries) => setGrades(countries.find((c) => c.code === form.country_code)?.grades ?? []))
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
      setError(err instanceof ApiError ? err.message : "Création impossible.");
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
          <button
            className="btn btn-primary"
            onClick={() => void submit()}
            disabled={busy || !form.display_name}
          >
            {busy ? "Création…" : "Ajouter"}
          </button>
        </>
      }
    >
      <div className="stack" style={{ gap: 14 }}>
        <div className="field">
          <label htmlFor="name">Prénom</label>
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
              <option value="BJ">Bénin</option>
              <option value="CI">Côte d&apos;Ivoire</option>
              <option value="SN">Sénégal</option>
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
            maxLength={6}
            value={form.pin}
            onChange={(event) => setForm((c) => ({ ...c, pin: event.target.value.replace(/\D/g, "") }))}
          />
          <span className="help">4 à 6 chiffres, pour ouvrir sa session sur la tablette.</span>
        </div>
        {error && <Alert tone="critical">{error}</Alert>}
      </div>
    </Modal>
  );
}
