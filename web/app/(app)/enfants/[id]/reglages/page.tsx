"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import type { EffectivePolicy } from "@koda/shared";

import { ApiError, api, type PolicyProfile } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { PERIOD_LABELS, minutes } from "@/lib/format";
import { Alert, Card, Loading, Tag } from "@/components/ui";

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

  useEffect(() => {
    const own = profiles.find((p) => p.child_id === childId && p.period_type === period);
    const family = profiles.find((p) => p.child_id === null && p.period_type === period);
    const source = own ?? family;
    setDraft(
      source
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
        : { ...DEFAULTS, allow_parent_direct_unlock: period !== "holiday" },
    );
  }, [profiles, period, childId]);

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
        <div className="grow">
          <h1>Regles — {child.display_name}</h1>
          <p className="page-subtitle">
            Chaque periode a ses propres regles. Celles applicables maintenant :{" "}
            <strong>{effective ? PERIOD_LABELS[effective.period_type] : "—"}</strong>
            {effective && effective.source !== "child" && (
              <span className="muted"> (heritees {effective.source === "family" ? "du foyer" : "des valeurs par defaut"})</span>
            )}
          </p>
        </div>
        <Link className="btn" href={`/enfants/${childId}`}>
          Retour au tableau de bord
        </Link>
      </div>

      <div className="stack">
        <div className="row" style={{ gap: 6 }}>
          {PERIODS.map((value) => (
            <button
              key={value}
              className={`btn btn-sm${period === value ? " btn-primary" : ""}`}
              onClick={() => setPeriod(value)}
            >
              {PERIOD_LABELS[value]}
              {effective?.period_type === value && <span> · en cours</span>}
            </button>
          ))}
        </div>

        {period === "holiday" && (
          <Alert tone="info">
            Pendant les vacances il n&apos;y a plus de devoirs a valider : par defaut le
            deverrouillage direct est coupe et l&apos;evaluation devient le seul chemin. Vous gardez
            la possibilite d&apos;accorder une rallonge exceptionnelle a tout moment.
          </Alert>
        )}

        <div className="grid grid-2">
          <Card title="Exigence de reussite">
            <div className="stack" style={{ gap: 16 }}>
              <div className="field">
                <label htmlFor="seuil">
                  Note minimale : <strong>{(draft.pass_score_pct * 0.2).toFixed(1).replace(".", ",")}/20</strong>
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
                <span className="help">En dessous, le code n&apos;est pas delivre.</span>
              </div>
              <div className="field">
                <label htmlFor="nb">Nombre de questions : {draft.question_count}</label>
                <input id="nb" type="range" min={5} max={25} value={draft.question_count} onChange={num("question_count")} />
              </div>
              <div className="field">
                <label htmlFor="duree">Temps imparti : {minutes(draft.time_limit_minutes)}</label>
                <input id="duree" type="range" min={5} max={60} step={5} value={draft.time_limit_minutes} onChange={num("time_limit_minutes")} />
              </div>
              <div className="field">
                <label htmlFor="biais">
                  Exigence :{" "}
                  {draft.difficulty_bias < -0.3 ? "plus accessible" : draft.difficulty_bias > 0.3 ? "plus exigeante" : "equilibree"}
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
                <span className="help">Deplace la difficulte visee autour de 75 % de reussite attendue.</span>
              </div>
            </div>
          </Card>

          <Card title="Recompense">
            <div className="stack" style={{ gap: 16 }}>
              <div className="field">
                <label htmlFor="recompense">Temps accorde : {minutes(draft.reward_minutes)}</label>
                <input id="recompense" type="range" min={15} max={360} step={15} value={draft.reward_minutes} onChange={num("reward_minutes")} />
              </div>
              <div className="field">
                <label htmlFor="plafond">Plafond quotidien : {minutes(draft.daily_cap_minutes)}</label>
                <input id="plafond" type="range" min={0} max={600} step={15} value={draft.daily_cap_minutes} onChange={num("daily_cap_minutes")} />
                <span className="help">Toutes origines confondues, y compris les rallonges.</span>
              </div>
              <div className="field">
                <label htmlFor="tentatives">Tentatives par jour : {draft.max_attempts_per_day}</label>
                <input id="tentatives" type="range" min={1} max={10} value={draft.max_attempts_per_day} onChange={num("max_attempts_per_day")} />
              </div>
              <label className="switch">
                <input
                  type="checkbox"
                  checked={draft.allow_parent_direct_unlock}
                  onChange={(event) => set("allow_parent_direct_unlock", event.target.checked)}
                />
                <span>
                  Autoriser le deverrouillage parental direct
                  <br />
                  <span className="help">Les devoirs sont faits hors ligne : vous dictez un code.</span>
                </span>
              </label>
              <label className="switch">
                <input
                  type="checkbox"
                  checked={draft.allow_assessment_unlock}
                  onChange={(event) => set("allow_assessment_unlock", event.target.checked)}
                />
                <span>
                  Autoriser le deverrouillage par evaluation
                  <br />
                  <span className="help">L&apos;enfant obtient son code en reussissant l&apos;examen.</span>
                </span>
              </label>
            </div>
          </Card>

          <Card title="Sanction et revision">
            <div className="stack" style={{ gap: 16 }}>
              <div className="field">
                <label htmlFor="carence">Temps de carence apres un echec : {minutes(draft.cooldown_minutes)}</label>
                <input id="carence" type="range" min={0} max={360} step={15} value={draft.cooldown_minutes} onChange={num("cooldown_minutes")} />
                <span className="help">
                  Delai obligatoire avant une nouvelle tentative. La correction detaillee reste
                  consultable pendant tout ce temps.
                </span>
              </div>
              <div className="field">
                <label htmlFor="escalade">
                  Escalade a chaque nouvel echec du jour : x{draft.cooldown_escalation.toFixed(2)}
                </label>
                <input id="escalade" type="range" min={1} max={3} step={0.25} value={draft.cooldown_escalation} onChange={num("cooldown_escalation")} />
                <span className="help">
                  {draft.cooldown_escalation === 1
                    ? "Pas d'escalade : la carence reste constante."
                    : `2e echec : ${minutes(Math.round(draft.cooldown_minutes * draft.cooldown_escalation))}, 3e : ${minutes(Math.round(draft.cooldown_minutes * draft.cooldown_escalation ** 2))}.`}
                </span>
              </div>
              <div className="row" style={{ gap: 12 }}>
                <div className="field" style={{ flex: 1 }}>
                  <label htmlFor="debut">Couvre-feu — debut</label>
                  <input id="debut" type="time" value={draft.curfew_start} onChange={(e) => set("curfew_start", e.target.value)} />
                </div>
                <div className="field" style={{ flex: 1 }}>
                  <label htmlFor="fin">Couvre-feu — fin</label>
                  <input id="fin" type="time" value={draft.curfew_end} onChange={(e) => set("curfew_end", e.target.value)} />
                </div>
              </div>
              <span className="help">Laisser vide pour desactiver le couvre-feu.</span>
            </div>
          </Card>

          <Card title="Points d'experience">
            <div className="stack" style={{ gap: 16 }}>
              <div className="field">
                <label htmlFor="conversion">
                  Conversion : 100 XP = {draft.minutes_per_100_xp} min
                </label>
                <input id="conversion" type="range" min={0} max={40} step={5} value={draft.minutes_per_100_xp} onChange={num("minutes_per_100_xp")} />
                <span className="help">A 0, la conversion est desactivee.</span>
              </div>
              <div className="field">
                <label htmlFor="capxp">Bonus quotidien maximal : {minutes(draft.xp_daily_bonus_cap_minutes)}</label>
                <input id="capxp" type="range" min={0} max={180} step={15} value={draft.xp_daily_bonus_cap_minutes} onChange={num("xp_daily_bonus_cap_minutes")} />
              </div>
              <Alert tone="info">
                Les XP viennent des evaluations facultatives. Le rendement decroit au fil de la
                journee : impossible d&apos;enchainer des QCM faciles pour gagner des heures.
              </Alert>
            </div>
          </Card>
        </div>

        {error && <Alert tone="critical">{error}</Alert>}

        <div className="row">
          {saved && <Tag tone="good">✓ Regles enregistrees</Tag>}
          <span className="spacer" />
          <button className="btn btn-primary" onClick={() => void save()} disabled={busy}>
            {busy ? "Enregistrement…" : `Enregistrer pour ${PERIOD_LABELS[period].toLowerCase()}`}
          </button>
        </div>
      </div>
    </>
  );
}
