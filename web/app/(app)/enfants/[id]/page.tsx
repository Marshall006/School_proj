"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import type { Dashboard } from "@koda/shared";

import { ApiError, api, type AssessmentSummary, type UnlockCodeRecord } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import {
  AVATARS,
  BAND_LABELS,
  KIND_LABELS,
  PERIOD_LABELS,
  countdown,
  formatDateTime,
  minutes,
  percent,
  relative,
  score20,
} from "@/lib/format";
import { ColumnTrend } from "@/components/charts/ColumnTrend";
import { MasteryBar } from "@/components/charts/MasteryBar";
import { RankedBars } from "@/components/charts/RankedBars";
import { UnlockDialog } from "@/components/UnlockDialog";
import { Alert, Card, Empty, Loading, Stat, Tag } from "@/components/ui";
import {
  IconAlert,
  IconBook,
  IconCheck,
  IconClock,
  IconFlame,
  IconLock,
  IconPlus,
  IconSettings,
  IconStar,
  IconUnlock,
} from "@/components/icons";

/** Seuil de reussite affiche en repere sur les graphiques (14/20). */
const PASS_THRESHOLD = 0.7;

export default function ChildDashboardPage() {
  const params = useParams<{ id: string }>();
  const childId = params.id;
  const { children, refreshChildren } = useAuth();
  const child = children.find((c) => c.id === childId);

  const [data, setData] = useState<Dashboard | null>(null);
  const [codes, setCodes] = useState<UnlockCodeRecord[]>([]);
  const [history, setHistory] = useState<AssessmentSummary[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [unlock, setUnlock] = useState(false);
  const [busy, setBusy] = useState(false);
  const [showTable, setShowTable] = useState(false);
  const [fullHistory, setFullHistory] = useState(false);

  const load = useCallback(async () => {
    try {
      const [dashboard, codeList, assessments] = await Promise.all([
        api.children.dashboard(childId),
        api.unlock.codes(childId),
        api.children.assessments(childId),
      ]);
      setData(dashboard);
      setCodes(codeList);
      setHistory(assessments);
      setError(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Chargement impossible.");
    }
  }, [childId]);

  useEffect(() => {
    void load();
    const timer = window.setInterval(() => void load(), 30_000);
    return () => window.clearInterval(timer);
  }, [load]);

  if (error) return <Alert tone="critical">{error}</Alert>;
  if (!data || !child) return <Loading />;

  const { status, subjects, mastery, screen_time_trend, alerts, totals, recent_assessments } = data;
  const session = status.session;
  const lockout = status.lockout;

  async function act(action: () => Promise<unknown>) {
    setBusy(true);
    try {
      await action();
      await load();
      await refreshChildren();
    } finally {
      setBusy(false);
    }
  }

  const evaluations = fullHistory ? history : recent_assessments;

  return (
    <>
      <div className="page-head">
        <span className="avatar avatar-lg" aria-hidden="true">
          {AVATARS[child.avatar] ?? "🙂"}
        </span>
        <div className="grow">
          <h1>{child.display_name}</h1>
          <p className="page-subtitle">
            {child.grade_code} · {PERIOD_LABELS[status.period_type]} ·{" "}
            {status.unlock_paths.parent_direct
              ? "déverrouillage parental autorisé"
              : "accès uniquement par évaluation"}
          </p>
        </div>
        <div className="row" style={{ gap: 8 }}>
          <Link className="btn" href={`/enfants/${childId}/reglages`}>
            <IconSettings size={16} />
            Règles
          </Link>
          <button className="btn btn-primary" onClick={() => setUnlock(true)}>
            {status.unlock_paths.parent_direct ? (
              <>
                <IconUnlock size={16} />
                Débloquer
              </>
            ) : (
              <>
                <IconPlus size={16} />
                Rallonge
              </>
            )}
          </button>
        </div>
      </div>

      <div className="stack">
        {/* --- État instantané ---------------------------------------------- */}
        <Card
          className={`child-card ${session ? "" : lockout ? "is-cooldown" : "is-locked"}`}
          title={
            <span className="row" style={{ gap: 8 }}>
              {session ? <IconUnlock size={17} /> : <IconLock size={17} />}
              {status.screen_state === "unlocked"
                ? "Tablette ouverte"
                : status.screen_state === "paused"
                  ? "En pause — écran éteint"
                  : "Tablette verrouillée"}
            </span>
          }
          hint={session ? `depuis ${relative(session.started_at)}` : undefined}
          action={
            session ? (
              <div className="row" style={{ gap: 8 }}>
                <button
                  className="btn btn-sm"
                  disabled={busy}
                  onClick={() => void act(() => api.screen.extend(session.id, 15))}
                >
                  <IconPlus size={15} />
                  15 min
                </button>
                <button
                  className="btn btn-sm btn-danger"
                  disabled={busy}
                  onClick={() => void act(() => api.screen.stop(session.id))}
                >
                  Couper
                </button>
              </div>
            ) : lockout ? (
              <button
                className="btn btn-sm"
                disabled={busy}
                onClick={() => void act(() => api.children.releaseLockout(childId))}
              >
                <IconCheck size={15} />
                Lever la carence
              </button>
            ) : null
          }
        >
          {session ? (
            <div className="row" style={{ gap: 28, alignItems: "flex-end" }}>
              <div>
                <div className="hero-figure">{minutes(session.remaining_minutes)}</div>
                <span className="small muted">
                  restant sur {minutes(session.granted_minutes)} accordées
                </span>
              </div>
              <div className="grow" style={{ minWidth: 220 }}>
                <div className="meter">
                  <span
                    style={{
                      width: `${Math.max(2, (session.remaining_ms / (session.granted_minutes * 60000 || 1)) * 100)}%`,
                    }}
                  />
                </div>
                <div className="row small muted" style={{ marginTop: 8 }}>
                  <span>Fenêtre limite : {formatDateTime(session.wall_deadline_at)}</span>
                  <span className="spacer" />
                  <span>Intégrité {Math.round(session.integrity_score * 100)} %</span>
                </div>
              </div>
            </div>
          ) : lockout ? (
            <div className="stack" style={{ gap: 12 }}>
              <div className="row" style={{ alignItems: "baseline", gap: 12 }}>
                <span className="hero-figure" style={{ color: "var(--serious-ink)" }}>
                  {countdown(lockout.remaining_seconds)}
                </span>
                <span className="small secondary">avant la prochaine tentative</span>
              </div>
              <p className="secondary">{lockout.message}</p>
              {lockout.review_topics.length > 0 && (
                <div className="row" style={{ gap: 8 }}>
                  <span className="small muted">À revoir :</span>
                  {lockout.review_topics.slice(0, 4).map((topic, index) => (
                    <Tag key={index} tone="warning">
                      <IconBook size={13} />
                      {String(
                        (topic as { topic_name?: string; subject_code?: string }).topic_name ??
                          (topic as { subject_code?: string }).subject_code ??
                          "notion",
                      )}
                    </Tag>
                  ))}
                </div>
              )}
            </div>
          ) : (
            <p className="secondary">
              Aucune session en cours. {child.display_name} peut lancer une évaluation depuis sa
              tablette pour obtenir un code
              {status.unlock_paths.parent_direct
                ? ", ou vous pouvez débloquer directement."
                : "."}
            </p>
          )}
        </Card>

        {/* --- Chiffres clés ------------------------------------------------ */}
        <div className="grid grid-4">
          <Stat
            label="Aujourd'hui"
            value={minutes(status.screen_time_today.granted_minutes)}
            hint={`sur ${minutes(status.screen_time_today.cap_minutes)} autorisées`}
          />
          <Stat
            label="Taux de réussite"
            value={percent(totals.pass_rate)}
            hint={`${totals.assessments_passed}/${totals.assessments_graded} évaluations validées`}
            tone={
              totals.pass_rate !== null && totals.pass_rate < 0.5
                ? "critical"
                : totals.pass_rate !== null && totals.pass_rate >= PASS_THRESHOLD
                  ? "good"
                  : undefined
            }
          />
          <Stat
            label="Expérience"
            value={child.xp_balance.toLocaleString("fr-FR")}
            hint={`${child.xp_lifetime.toLocaleString("fr-FR")} XP cumulés`}
          />
          <Stat
            label="Série"
            value={`${status.streak_days} j`}
            hint={status.streak_days > 1 ? "jours consécutifs d'effort" : "reprend dès demain"}
          />
        </div>

        {/* --- Alertes ------------------------------------------------------ */}
        {alerts.length > 0 && (
          <Card
            title={
              <span className="row" style={{ gap: 8 }}>
                <IconAlert size={17} /> Signaux à surveiller
              </span>
            }
            hint={`${alerts.length} élément${alerts.length > 1 ? "s" : ""}`}
          >
            <div className="stack" style={{ gap: 8 }}>
              {alerts.slice(0, 5).map((alert, index) => (
                <Alert
                  key={index}
                  tone={
                    alert.severity === "critical"
                      ? "critical"
                      : alert.severity === "warning"
                        ? "warning"
                        : "info"
                  }
                >
                  {alert.message} <span className="muted small">· {relative(alert.at)}</span>
                </Alert>
              ))}
            </div>
          </Card>
        )}

        {/* --- Performance --------------------------------------------------- */}
        <div className="grid grid-2">
          <Card
            title="Réussite par matière"
            hint="30 derniers jours"
            action={
              <button className="btn btn-sm" onClick={() => setShowTable((v) => !v)}>
                {showTable ? "Graphique" : "Tableau"}
              </button>
            }
          >
            {subjects.length === 0 ? (
              <Empty>Les premières évaluations alimenteront ce graphique.</Empty>
            ) : showTable ? (
              <table className="table">
                <thead>
                  <tr>
                    <th>Matière</th>
                    <th className="num">Réponses</th>
                    <th className="num">Justes</th>
                    <th className="num">Réussite</th>
                  </tr>
                </thead>
                <tbody>
                  {subjects.map((row) => (
                    <tr key={row.subject_code}>
                      <td>{row.subject_name}</td>
                      <td className="num tabular">{row.answered}</td>
                      <td className="num tabular">{row.correct}</td>
                      <td className="num tabular">{percent(row.success_rate)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <RankedBars
                threshold={PASS_THRESHOLD}
                rows={subjects.map((row) => ({
                  label: row.subject_name,
                  value: row.success_rate,
                  detail: `${row.correct}/${row.answered} réponses justes · ${row.avg_seconds} s par question`,
                }))}
              />
            )}
          </Card>

          <Card title="Temps d'écran" hint="14 derniers jours">
            <ColumnTrend data={screen_time_trend} />
          </Card>
        </div>

        {/* --- Maîtrise ------------------------------------------------------ */}
        <Card
          title="Niveau par notion"
          hint={`${mastery.topics_tracked} notions suivies · ${mastery.due_for_review} à revoir`}
        >
          <MasteryBar bands={mastery.bands} />
          {mastery.gaps.length > 0 && (
            <>
              <hr className="divider" />
              <h3 style={{ marginBottom: 10 }}>Lacunes prioritaires</h3>
              <table className="table">
                <thead>
                  <tr>
                    <th>Notion</th>
                    <th>Niveau</th>
                    <th className="num">Réussite</th>
                    <th className="num">Tentatives</th>
                    <th>Révision</th>
                  </tr>
                </thead>
                <tbody>
                  {mastery.gaps.map((gap) => (
                    <tr key={gap.topic_id}>
                      <td>{gap.topic_name}</td>
                      <td>
                        <Tag
                          tone={
                            gap.band === "fragile"
                              ? "critical"
                              : gap.band === "en_cours"
                                ? "warning"
                                : "good"
                          }
                        >
                          {BAND_LABELS[gap.band] ?? gap.band}
                        </Tag>
                      </td>
                      <td className="num tabular">{percent(gap.success_rate)}</td>
                      <td className="num tabular">{gap.attempts}</td>
                      <td>
                        {gap.due ? (
                          <Tag tone="warning">
                            <IconAlert size={13} />à revoir
                          </Tag>
                        ) : (
                          <span className="muted small">planifiée</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <p className="small muted" style={{ marginTop: 10 }}>
                Le moteur consacre environ 40 % de chaque évaluation à ces notions, 40 % au
                programme en cours et 20 % aux acquis — pour progresser sans décourager.
              </p>
            </>
          )}
        </Card>

        {/* --- Historique ----------------------------------------------------- */}
        <div className="grid grid-2">
          <Card
            title="Évaluations"
            hint={fullHistory ? `${history.length} au total` : "les plus récentes"}
            action={
              history.length > recent_assessments.length ? (
                <button className="btn btn-sm" onClick={() => setFullHistory((v) => !v)}>
                  {fullHistory ? "Réduire" : "Tout l'historique"}
                </button>
              ) : null
            }
          >
            {evaluations.length === 0 ? (
              <Empty>Aucune évaluation terminée.</Empty>
            ) : (
              <table className="table">
                <thead>
                  <tr>
                    <th>Date</th>
                    <th>Type</th>
                    <th className="num">Note</th>
                    <th>Résultat</th>
                    <th className="num">Gagné</th>
                  </tr>
                </thead>
                <tbody>
                  {evaluations.map((row) => (
                    <tr key={row.id}>
                      <td className="small">{formatDateTime(row.created_at)}</td>
                      <td className="small">
                        {row.kind === "practice" ? "Entraînement" : "Déverrouillage"}
                      </td>
                      <td className="num tabular">{score20(row.score_out_of_20)}</td>
                      <td>
                        {row.status === "needs_review" ? (
                          <Tag tone="warning">À valider</Tag>
                        ) : row.passed ? (
                          <Tag tone="good">
                            <IconCheck size={13} />
                            Réussie
                          </Tag>
                        ) : (
                          <Tag tone="critical">Échouée</Tag>
                        )}
                      </td>
                      <td className="num small">
                        {row.reward_minutes > 0
                          ? minutes(row.reward_minutes)
                          : `${row.xp_earned} XP`}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </Card>

          <Card title="Codes émis" hint="10 derniers">
            {codes.length === 0 ? (
              <Empty>Aucun code généré pour le moment.</Empty>
            ) : (
              <table className="table">
                <thead>
                  <tr>
                    <th>Émis</th>
                    <th>Origine</th>
                    <th className="num">Durée</th>
                    <th>État</th>
                  </tr>
                </thead>
                <tbody>
                  {codes.slice(0, 10).map((code) => (
                    <tr key={code.id}>
                      <td className="small">{formatDateTime(code.created_at)}</td>
                      <td className="small">{KIND_LABELS[code.kind] ?? code.kind}</td>
                      <td className="num small tabular">{minutes(code.duration_minutes)}</td>
                      <td>
                        {code.status === "consumed" ? (
                          <span className="small muted">
                            utilisé{code.consumed_offline ? " (hors ligne)" : ""}
                          </span>
                        ) : code.status === "issued" ? (
                          <button
                            className="btn btn-sm btn-danger"
                            disabled={busy}
                            onClick={() => void act(() => api.unlock.revoke(code.id))}
                          >
                            Annuler
                          </button>
                        ) : (
                          <span className="small muted">
                            {code.status === "revoked" ? "annulé" : "expiré"}
                          </span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </Card>
        </div>

        {data.xp_timeline.length > 0 && (
          <Card
            title={
              <span className="row" style={{ gap: 8 }}>
                <IconStar size={17} /> Mouvements d&apos;expérience
              </span>
            }
            hint="derniers gains"
          >
            <table className="table">
              <thead>
                <tr>
                  <th>Quand</th>
                  <th>Motif</th>
                  <th className="num">XP</th>
                  <th className="num">Solde</th>
                </tr>
              </thead>
              <tbody>
                {data.xp_timeline.slice(0, 8).map((entry, index) => (
                  <tr key={index}>
                    <td className="small">{relative(entry.at)}</td>
                    <td className="small">{entry.label ?? entry.reason}</td>
                    <td
                      className="num tabular"
                      style={{
                        color: entry.delta > 0 ? "var(--good-ink)" : "var(--ink-secondary)",
                        fontWeight: 600,
                      }}
                    >
                      {entry.delta > 0 ? "+" : ""}
                      {entry.delta}
                    </td>
                    <td className="num tabular muted">{entry.balance_after}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div className="row small muted" style={{ marginTop: 12, gap: 14 }}>
              <span className="row" style={{ gap: 6 }}>
                <IconStar size={14} />
                {child.xp_balance.toLocaleString("fr-FR")} XP disponibles
              </span>
              <span className="row" style={{ gap: 6 }}>
                <IconFlame size={14} />
                {child.streak_days} jour{child.streak_days > 1 ? "s" : ""} de série
              </span>
              <span className="row" style={{ gap: 6 }}>
                <IconClock size={14} />
                convertibles en temps d&apos;écran depuis la tablette
              </span>
            </div>
          </Card>
        )}
      </div>

      {unlock && (
        <UnlockDialog
          child={child}
          kind={status.unlock_paths.parent_direct ? "direct" : "bonus"}
          onClose={() => {
            setUnlock(false);
            void load();
          }}
        />
      )}
    </>
  );
}
