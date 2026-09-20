"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import type { EffectivePolicy } from "@koda/shared";

import { ApiError, api, type PolicyProfile } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { AVATARS, PERIOD_LABELS, minutes } from "@/lib/format";
import { Alert, Card, Loading, Tag } from "@/components/ui";
import {
  IconArrow,
  IconCheck,
  IconClock,
  IconLock,
  IconStar,
  IconUnlock,
} from "@/components/icons";

const PERIODS = ["school", "weekend", "holiday"] as const;
type Period = (typeof PERIODS)[number];

interface Draft {
  pass_score_pct: number;
  question_count: number;
  time_limit_minutes: number;
  difficulty_bias: number;
  reward_minutes: number;
  daily_cap_minutes: number;
  max_attempts_per_day: number;
  cooldown_minutes: number;
  cooldown_escalation: number;
  allow_parent_direct_unlock: boolean;
  allow_assessment_unlock: boolean;
  review_required_before_retry: boolean;
  minutes_per_100_xp: number;
  xp_daily_bonus_cap_minutes: number;
  curfew_start: string;
  curfew_end: string;
}

const DEFAULTS: Draft = {
  pass_score_pct: 70,
  question_count: 10,
  time_limit_minutes: 20,
  difficulty_bias: 0,
  reward_minutes: 180,
  daily_cap_minutes: 300,
  max_attempts_per_day: 4,
  cooldown_minutes: 120,
  cooldown_escalation: 1,
  allow_parent_direct_unlock: true,
  allow_assessment_unlock: true,
  review_required_before_retry: true,
  minutes_per_100_xp: 15,
  xp_daily_bonus_cap_minutes: 60,
  curfew_start: "21:00",
  curfew_end: "07:00",
};

export default function ReglagesPage() {
  const params = useParams<{ id: string }>();
  const childId = params.id;
  const { children } = useAuth();
  const child = children.find((c) => c.id === childId);

  const [period, setPeriod] = useState<Period>("school");
  const [profiles, setProfiles] = useState<PolicyProfile[]>([]);
  const [effective, setEffective] = useState<EffectivePolicy | null>(null);
  const [draft, setDraft] = useState<Draft>(DEFAULTS);
  const [baseline, setBaseline] = useState<Draft>(DEFAULTS);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    const [list, active] = await Promise.all([api.policies.list(), api.children.policy(childId)]);
    setProfiles(list);
    setEffective(active);
    setLoading(false);
  }, [childId]);

  useEffect(() => {
    void load();
  }, [load]);

  /** D'ou viennent les valeurs affichees : reglage propre a l'enfant, regle du
   *  foyer, ou valeurs par defaut de KODA. On le dit, pour qu'on sache si on
   *  modifie une regle existante ou si on en cree une. */
  const own = profiles.find((p) => p.child_id === childId && p.period_type === period);
  const family = profiles.find((p) => p.child_id === null && p.period_type === period);
  const origin = own ? "child" : family ? "family" : "defaults";

  useEffect(() => {
    const source = own ?? family;
    const next: Draft = source
      ? {
          pass_score_pct: source.pass_score_pct,
          question_count: source.question_count,
          time_limit_minutes: source.time_limit_minutes,
          difficulty_bias: source.difficulty_bias,
          reward_minutes: source.reward_minutes,
          daily_cap_minutes: source.daily_cap_minutes,
          max_attempts_per_day: source.max_attempts_per_day,
          cooldown_minutes: source.cooldown_minutes,
          cooldown_escalation: source.cooldown_escalation,
          allow_parent_direct_unlock: source.allow_parent_direct_unlock,
          allow_assessment_unlock: source.allow_assessment_unlock,
          review_required_before_retry: source.review_required_before_retry,
          minutes_per_100_xp: source.minutes_per_100_xp,
          xp_daily_bonus_cap_minutes: source.xp_daily_bonus_cap_minutes,
          curfew_start: source.curfew_start ?? "",
          curfew_end: source.curfew_end ?? "",
        }
      : { ...DEFAULTS, allow_parent_direct_unlock: period !== "holiday" };
    setDraft(next);
    setBaseline(next);
  }, [own, family, period]);

  const dirty = useMemo(
    () => (Object.keys(baseline) as Array<keyof Draft>).some((key) => draft[key] !== baseline[key]),
    [draft, baseline],
  );

  async function save() {
    setBusy(true);
    setError(null);
    try {
      await api.policies.upsert({
        ...draft,
        curfew_start: draft.curfew_start || null,
        curfew_end: draft.curfew_end || null,
        child_id: childId,
        period_type: period,
        name: `${child?.display_name ?? "Enfant"} — ${PERIOD_LABELS[period]}`,
      });
      await load();
      setSaved(true);
      window.setTimeout(() => setSaved(false), 2500);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Enregistrement impossible.");
    } finally {
      setBusy(false);
    }
  }

  if (loading || !child) return <Loading />;

  const set = <K extends keyof Draft>(key: K, value: Draft[K]) =>
    setDraft((current) => ({ ...current, [key]: value }));
  const num = (key: keyof Draft) => (event: React.ChangeEvent<HTMLInputElement>) =>
    set(key, Number(event.target.value) as Draft[typeof key]);

  return (
    <>
      <div className="page-head">
        <span className="avatar avatar-lg" aria-hidden="true">
          {AVATARS[child.avatar] ?? "🙂"}
        </span>
        <div className="grow">
          <h1>Règles — {child.display_name}</h1>
          <p className="page-subtitle">
            Chaque période a ses propres règles. Celles qui s&apos;appliquent maintenant :{" "}
            <strong>{effective ? PERIOD_LABELS[effective.period_type] : "—"}</strong>
            {effective && effective.source !== "child" && (
              <span className="muted">
                {" "}
                (héritées {effective.source === "family" ? "du foyer" : "des valeurs par défaut"})
              </span>
            )}
          </p>
        </div>
        <Link className="btn" href={`/enfants/${childId}`}>
          <IconArrow size={16} className="flip" />
          Tableau de bord
        </Link>
      </div>

      <div className="stack">
        <div className="row" style={{ gap: 12 }}>
          <div className="segmented" role="group" aria-label="Période à régler">
            {PERIODS.map((value) => (
              <button
                key={value}
                aria-pressed={period === value}
                onClick={() => setPeriod(value)}
                title={
                  effective?.period_type === value ? "Période en cours" : "Régler cette période"
                }
              >
                {effective?.period_type === value && <span className="dot" aria-hidden="true" />}
                {PERIOD_LABELS[value]}
              </button>
            ))}
          </div>
          <span className="spacer" />
          <Tag tone={origin === "child" ? "accent" : undefined}>
            {origin === "child"
              ? "Règle propre à l'enfant"
              : origin === "family"
                ? "Héritée du foyer"
                : "Valeurs par défaut"}
          </Tag>
        </div>

        {period === "holiday" && (
          <Alert tone="info">
            Pendant les vacances il n&apos;y a plus de devoirs à valider : par défaut le
            déverrouillage direct est coupé et l&apos;évaluation devient le seul chemin. Vous gardez
            la possibilité d&apos;accorder une rallonge exceptionnelle à tout moment.
          </Alert>
        )}

        <div className="grid grid-2">
          <Card
            title={
              <span className="row" style={{ gap: 8 }}>
                <IconCheck size={17} /> Exigence de réussite
              </span>
            }
          >
            <div className="stack" style={{ gap: 16 }}>
              <div className="field">
                <label htmlFor="seuil">
                  Note minimale :{" "}
                  <strong>
                    {(draft.pass_score_pct * 0.2).toFixed(1).replace(".", ",")}/20
                  </strong>
                </label>
                <input
                  id="seuil"
                  type="range"
                  min={40}
                  max={100}
                  step={5}
                  value={draft.pass_score_pct}
                  onChange={num("pass_score_pct")}
                />
                <span className="help">En dessous, le code n&apos;est pas délivré.</span>
              </div>
              <div className="field">
                <label htmlFor="nb">Nombre de questions : {draft.question_count}</label>
                <input
                  id="nb"
                  type="range"
                  min={5}
                  max={25}
                  value={draft.question_count}
                  onChange={num("question_count")}
                />
              </div>
              <div className="field">
                <label htmlFor="duree">Temps imparti : {minutes(draft.time_limit_minutes)}</label>
                <input
                  id="duree"
                  type="range"
                  min={5}
                  max={60}
                  step={5}
                  value={draft.time_limit_minutes}
                  onChange={num("time_limit_minutes")}
                />
              </div>
              <div className="field">
                <label htmlFor="biais">
                  Exigence :{" "}
                  <strong>
                    {draft.difficulty_bias < -0.3
                      ? "plus accessible"
                      : draft.difficulty_bias > 0.3
                        ? "plus exigeante"
                        : "équilibrée"}
                  </strong>
                </label>
                <input
                  id="biais"
                  type="range"
                  min={-1}
                  max={1}
                  step={0.25}
                  value={draft.difficulty_bias}
                  onChange={num("difficulty_bias")}
                />
                <span className="help">
                  Déplace la difficulté visée autour de 75 % de réussite attendue.
                </span>
              </div>
            </div>
          </Card>

          <Card
            title={
              <span className="row" style={{ gap: 8 }}>
                <IconUnlock size={17} /> Récompense
              </span>
            }
          >
            <div className="stack" style={{ gap: 16 }}>
              <div className="field">
                <label htmlFor="recompense">Temps accordé : {minutes(draft.reward_minutes)}</label>
                <input
                  id="recompense"
                  type="range"
                  min={15}
                  max={360}
                  step={15}
                  value={draft.reward_minutes}
                  onChange={num("reward_minutes")}
                />
              </div>
              <div className="field">
                <label htmlFor="plafond">
                  Plafond quotidien : {minutes(draft.daily_cap_minutes)}
                </label>
                <input
                  id="plafond"
                  type="range"
                  min={0}
                  max={600}
                  step={15}
                  value={draft.daily_cap_minutes}
                  onChange={num("daily_cap_minutes")}
                />
                <span className="help">Toutes origines confondues, y compris les rallonges.</span>
              </div>
              <div className="field">
                <label htmlFor="tentatives">
                  Tentatives par jour : {draft.max_attempts_per_day}
                </label>
                <input
                  id="tentatives"
                  type="range"
                  min={1}
                  max={10}
                  value={draft.max_attempts_per_day}
                  onChange={num("max_attempts_per_day")}
                />
              </div>
              <label className="switch">
                <input
                  type="checkbox"
                  checked={draft.allow_parent_direct_unlock}
                  onChange={(event) => set("allow_parent_direct_unlock", event.target.checked)}
                />
                <span>
                  Autoriser le déverrouillage parental direct
                  <br />
                  <span className="help">
                    Les devoirs sont faits hors ligne : vous dictez un code.
                  </span>
                </span>
              </label>
              <label className="switch">
                <input
                  type="checkbox"
                  checked={draft.allow_assessment_unlock}
                  onChange={(event) => set("allow_assessment_unlock", event.target.checked)}
                />
                <span>
                  Autoriser le déverrouillage par évaluation
                  <br />
                  <span className="help">
                    L&apos;enfant obtient son code en réussissant l&apos;examen.
                  </span>
                </span>
              </label>
              {!draft.allow_parent_direct_unlock && !draft.allow_assessment_unlock && (
                <Alert tone="warning">
                  Les deux chemins sont coupés : la tablette resterait verrouillée en permanence.
                </Alert>
              )}
            </div>
          </Card>

          <Card
            title={
              <span className="row" style={{ gap: 8 }}>
                <IconLock size={17} /> Sanction et révision
              </span>
            }
          >
            <div className="stack" style={{ gap: 16 }}>
              <div className="field">
                <label htmlFor="carence">
                  Temps de carence après un échec : {minutes(draft.cooldown_minutes)}
                </label>
                <input
                  id="carence"
                  type="range"
                  min={0}
                  max={360}
                  step={15}
                  value={draft.cooldown_minutes}
                  onChange={num("cooldown_minutes")}
                />
                <span className="help">
                  Délai obligatoire avant une nouvelle tentative. La correction détaillée reste
                  consultable pendant tout ce temps.
                </span>
              </div>
              <div className="field">
                <label htmlFor="escalade">
                  Escalade à chaque nouvel échec du jour : ×{draft.cooldown_escalation.toFixed(2)}
                </label>
                <input
                  id="escalade"
                  type="range"
                  min={1}
                  max={3}
                  step={0.25}
                  value={draft.cooldown_escalation}
                  onChange={num("cooldown_escalation")}
                />
                <span className="help">
                  {draft.cooldown_escalation === 1
                    ? "Pas d'escalade : la carence reste constante."
                    : `2e échec : ${minutes(Math.round(draft.cooldown_minutes * draft.cooldown_escalation))}, 3e : ${minutes(Math.round(draft.cooldown_minutes * draft.cooldown_escalation ** 2))}.`}
                </span>
              </div>
              <label className="switch">
                <input
                  type="checkbox"
                  checked={draft.review_required_before_retry}
                  onChange={(event) => set("review_required_before_retry", event.target.checked)}
                />
                <span>
                  Imposer la lecture de la correction avant de retenter
                  <br />
                  <span className="help">
                    La carence sert à réviser, pas seulement à attendre.
                  </span>
                </span>
              </label>
              <div className="row" style={{ gap: 12 }}>
                <div className="field" style={{ flex: 1 }}>
                  <label htmlFor="debut">Couvre-feu — début</label>
                  <input
                    id="debut"
                    type="time"
                    value={draft.curfew_start}
                    onChange={(e) => set("curfew_start", e.target.value)}
                  />
                </div>
                <div className="field" style={{ flex: 1 }}>
                  <label htmlFor="fin">Couvre-feu — fin</label>
                  <input
                    id="fin"
                    type="time"
                    value={draft.curfew_end}
                    onChange={(e) => set("curfew_end", e.target.value)}
                  />
                </div>
              </div>
              <span className="help">Laisser vide pour désactiver le couvre-feu.</span>
            </div>
          </Card>

          <Card
            title={
              <span className="row" style={{ gap: 8 }}>
                <IconStar size={17} /> Points d&apos;expérience
              </span>
            }
          >
            <div className="stack" style={{ gap: 16 }}>
              <div className="field">
                <label htmlFor="conversion">
                  Conversion : 100 XP ={" "}
                  <strong>
                    {draft.minutes_per_100_xp === 0
                      ? "désactivée"
                      : `${draft.minutes_per_100_xp} min`}
                  </strong>
                </label>
                <input
                  id="conversion"
                  type="range"
                  min={0}
                  max={40}
                  step={5}
                  value={draft.minutes_per_100_xp}
                  onChange={num("minutes_per_100_xp")}
                />
                <span className="help">À 0, l&apos;enfant ne peut plus convertir ses points.</span>
              </div>
              <div className="field">
                <label htmlFor="capxp">
                  Bonus quotidien maximal : {minutes(draft.xp_daily_bonus_cap_minutes)}
                </label>
                <input
                  id="capxp"
                  type="range"
                  min={0}
                  max={180}
                  step={15}
                  value={draft.xp_daily_bonus_cap_minutes}
                  onChange={num("xp_daily_bonus_cap_minutes")}
                />
              </div>
              <Alert tone="info">
                Les XP viennent des évaluations facultatives. Le rendement décroît au fil de la
                journée : impossible d&apos;enchaîner des QCM faciles pour gagner des heures.
              </Alert>
            </div>
          </Card>
        </div>

        {error && <Alert tone="critical">{error}</Alert>}

        <div className={`savebar${dirty ? " is-dirty" : ""}`}>
          <IconClock size={17} className="muted" />
          <span className="small secondary">
            {saved
              ? "Règles enregistrées."
              : dirty
                ? `Modifications non enregistrées pour « ${PERIOD_LABELS[period].toLowerCase()} ».`
                : `Aucune modification en attente.`}
          </span>
          <span className="spacer" />
          {dirty && (
            <button className="btn btn-sm" onClick={() => setDraft(baseline)} disabled={busy}>
              Annuler
            </button>
          )}
          <button
            className="btn btn-primary"
            onClick={() => void save()}
            disabled={busy || !dirty}
          >
            {busy ? "Enregistrement…" : "Enregistrer"}
          </button>
        </div>
      </div>
    </>
  );
}
