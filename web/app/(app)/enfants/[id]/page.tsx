"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import type { Child, Dashboard } from "@koda/shared";

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
  const passThreshold = 0.7;
  const session = status.session;

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

  return (
    <>
      <div className="page-head">
        <span style={{ fontSize: 38 }} aria-hidden="true">
          {AVATARS[child.avatar] ?? "🙂"}
        </span>
        <div className="grow">
          <h1>{child.display_name}</h1>
          <p className="page-subtitle">
            {child.grade_code} · {PERIOD_LABELS[status.period_type]} ·{" "}
            {status.unlock_paths.parent_direct
              ? "deverrouillage parental autorise"
              : "acces uniquement par evaluation"}
          </p>
        </div>
        <div className="row">
          <Link className="btn" href={`/enfants/${childId}/reglages`}>
            Regles
          </Link>
          <button className="btn btn-primary" onClick={() => setUnlock(true)}>
            {status.unlock_paths.parent_direct ? "Debloquer" : "Rallonge"}
          </button>
        </div>
      </div>

      <div className="stack">
        {/* --- Etat instantane --------------------------------------------- */}
        <Card
          title={
            status.screen_state === "unlocked"
              ? "Tablette ouverte"
              : status.screen_state === "paused"
                ? "En pause — ecran eteint"
                : "Tablette verrouillee"
          }
          hint={session ? `depuis ${relative(session.started_at)}` : undefined}
          action={
            session ? (
              <div className="row" style={{ gap: 8 }}>
                <button className="btn btn-sm" disabled={busy} onClick={() => void act(() => api.screen.extend(session.id, 15))}>
                  +15 min
                </button>
                <button className="btn btn-sm btn-danger" disabled={busy} onClick={() => void act(() => api.screen.stop(session.id))}>
                  Couper
                </button>
              </div>
            ) : status.lockout ? (
              <button className="btn btn-sm" disabled={busy} onClick={() => void act(() => api.children.releaseLockout(childId))}>
                Lever la carence
              </button>
            ) : null
          }
        >
          {session ? (
            <div className="row" style={{ gap: 24, alignItems: "flex-end" }}>
              <div>
                <div className="hero-figure">{minutes(session.remaining_minutes)}</div>
                <span className="small muted">restant sur {minutes(session.granted_minutes)} accordees</span>
              </div>
              <div className="grow" style={{ minWidth: 200 }}>
                <div style={{ height: 10, background: "var(--surface-sunken)", borderRadius: 5, overflow: "hidden" }}>
                  <div
                    style={{
                      height: "100%",
                      width: `${Math.max(2, (session.remaining_ms / (session.granted_minutes * 60000 || 1)) * 100)}%`,
                      background: "var(--data-1)",
                      borderRadius: 5,
                    }}
                  />
                </div>
                <div className="row small muted" style={{ marginTop: 6 }}>
                  <span>Fenetre limite : {formatDateTime(session.wall_deadline_at)}</span>
                  <span className="spacer" />
                  <span>Integrite {Math.round(session.integrity_score * 100)} %</span>
                </div>
              </div>
            </div>
          ) : status.lockout ? (
            <div className="stack" style={{ gap: 10 }}>
              <div className="hero-figure" style={{ color: "var(--serious)" }}>
                {countdown(status.lockout.remaining_seconds)}
              </div>
              <p className="secondary">{status.lockout.message}</p>
              {status.lockout.review_topics.length > 0 && (
                <div className="row">
                  <span className="small muted">A revoir :</span>
                  {status.lockout.review_topics.slice(0, 4).map((topic, index) => (
                    <Tag key={index}>{String((topic as { subject_code?: string }).subject_code ?? "notion")}</Tag>
                  ))}
                </div>
              )}
            </div>
          ) : (
            <p className="secondary">
              Aucune session en cours. {child.display_name} peut lancer une evaluation depuis sa
              tablette pour obtenir un code
              {status.unlock_paths.parent_direct ? ", ou vous pouvez debloquer directement." : "."}
            </p>
          )}
        </Card>

        {/* --- Chiffres cles ------------------------------------------------ */}
        <div className="grid grid-4">
          <Stat
            label="Aujourd'hui"
            value={minutes(status.screen_time_today.granted_minutes)}
            hint={`sur ${minutes(status.screen_time_today.cap_minutes)} autorisees`}
          />
          <Stat
            label="Taux de reussite"
            value={percent(totals.pass_rate)}
            hint={`${totals.assessments_passed}/${totals.assessments_graded} evaluations validees`}
            tone={totals.pass_rate !== null && totals.pass_rate < 0.5 ? "warning" : undefined}
          />
          <Stat label="Experience" value={child.xp_balance.toLocaleString("fr-FR")} hint={`${child.xp_lifetime.toLocaleString("fr-FR")} XP cumules`} />
          <Stat
            label="Serie"
            value={`${status.streak_days} j`}
            hint={status.streak_days > 1 ? "jours consecutifs d'effort" : "reprend des demain"}
          />
        </div>

        {/* --- Alertes ------------------------------------------------------ */}
        {alerts.length > 0 && (
          <Card title="Signaux a surveiller" hint={`${alerts.length} element(s)`}>
            <div className="stack" style={{ gap: 8 }}>
              {alerts.slice(0, 5).map((alert, index) => (
                <Alert key={index} tone={alert.severity === "critical" ? "critical" : alert.severity === "warning" ? "warning" : "info"}>
                  {alert.message} <span className="muted small">· {relative(alert.at)}</span>
                </Alert>
              ))}
            </div>
          </Card>
        )}

        {/* --- Performance -------------------------------------------------- */}
        <div className="grid grid-2">
          <Card
            title="Reussite par matiere"
            hint="30 derniers jours"
            action={
              <button className="btn btn-sm" onClick={() => setShowTable((v) => !v)}>
                {showTable ? "Voir le graphique" : "Voir le tableau"}
              </button>
            }
          >
            {subjects.length === 0 ? (
              <Empty>Les premieres evaluations alimenteront ce graphique.</Empty>
            ) : showTable ? (
              <table className="table">
                <thead>
                  <tr>
                    <th>Matiere</th>
                    <th className="num">Reponses</th>
                    <th className="num">Justes</th>
                    <th className="num">Reussite</th>
                  </tr>
                </thead>
                <tbody>
                  {subjects.map((row) => (
                    <tr key={row.subject_code}>
                      <td>{row.subject_name}</td>
                      <td className="num">{row.answered}</td>
                      <td className="num">{row.correct}</td>
                      <td className="num">{percent(row.success_rate)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <RankedBars
                threshold={passThreshold}
                rows={subjects.map((row) => ({
                  label: row.subject_name,
                  value: row.success_rate,
                  detail: `${row.correct}/${row.answered} reponses justes · ${row.avg_seconds} s par question`,
                }))}
              />
            )}
          </Card>

          <Card title="Temps d'ecran" hint="14 derniers jours">
            <ColumnTrend data={screen_time_trend} />
          </Card>
        </div>

        {/* --- Maitrise ------------------------------------------------------ */}
        <Card
          title="Niveau par notion"
          hint={`${mastery.topics_tracked} notions suivies · ${mastery.due_for_review} a revoir`}
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
                    <th className="num">Reussite</th>
                    <th className="num">Tentatives</th>
                    <th>Revision</th>
                  </tr>
                </thead>
                <tbody>
                  {mastery.gaps.map((gap) => (
                    <tr key={gap.topic_id}>
                      <td>{gap.topic_name}</td>
                      <td>
                        <Tag tone={gap.band === "fragile" ? "critical" : gap.band === "en_cours" ? "warning" : "good"}>
                          {BAND_LABELS[gap.band] ?? gap.band}
                        </Tag>
                      </td>
                      <td className="num">{percent(gap.success_rate)}</td>
                      <td className="num">{gap.attempts}</td>
                      <td>{gap.due ? <Tag tone="warning">▲ a revoir</Tag> : <span className="muted small">planifiee</span>}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <p className="small muted" style={{ marginTop: 10 }}>
                Le moteur consacre environ 40 % de chaque evaluation a ces notions, 40 % au programme
                en cours et 20 % aux acquis — pour progresser sans decourager.
              </p>
            </>
          )}
        </Card>

        {/* --- Historique ---------------------------------------------------- */}
        <div className="grid grid-2">
          <Card title="Dernieres evaluations">
            {recent_assessments.length === 0 ? (
              <Empty>Aucune evaluation terminee.</Empty>
            ) : (
              <table className="table">
                <thead>
                  <tr>
                    <th>Date</th>
                    <th>Type</th>
                    <th className="num">Note</th>
                    <th>Resultat</th>
                    <th className="num">Gagne</th>
                  </tr>
                </thead>
                <tbody>
                  {recent_assessments.map((row) => (
                    <tr key={row.id}>
                      <td className="small">{formatDateTime(row.created_at)}</td>
                      <td className="small">{row.kind === "practice" ? "Entrainement" : "Deverrouillage"}</td>
                      <td className="num tabular">{score20(row.score_out_of_20)}</td>
                      <td>
                        {row.status === "needs_review" ? (
                          <Tag tone="warning">A valider</Tag>
                        ) : row.passed ? (
                          <Tag tone="good">✓ Reussie</Tag>
                        ) : (
                          <Tag tone="critical">Echouee</Tag>
                        )}
                      </td>
                      <td className="num small">
                        {row.reward_minutes > 0 ? minutes(row.reward_minutes) : `${row.xp_earned} XP`}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </Card>

          <Card title="Codes emis" hint="10 derniers">
            {codes.length === 0 ? (
              <Empty>Aucun code genere pour le moment.</Empty>
            ) : (
              <table className="table">
                <thead>
                  <tr>
                    <th>Emis</th>
                    <th>Origine</th>
                    <th className="num">Duree</th>
                    <th>Etat</th>
                  </tr>
                </thead>
                <tbody>
                  {codes.slice(0, 10).map((code) => (
                    <tr key={code.id}>
                      <td className="small">{formatDateTime(code.created_at)}</td>
                      <td className="small">{KIND_LABELS[code.kind] ?? code.kind}</td>
                      <td className="num small">{minutes(code.duration_minutes)}</td>
                      <td>
                        {code.status === "consumed" ? (
                          <span className="small muted">
                            utilise{code.consumed_offline ? " (hors ligne)" : ""}
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
                          <span className="small muted">{code.status === "revoked" ? "annule" : "expire"}</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </Card>
        </div>

        {history.length > 0 && (
          <Card title="Mouvements d'experience" hint="derniers gains">
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
                    <td className="num tabular" style={{ color: entry.delta > 0 ? "var(--good-ink)" : "var(--ink-secondary)" }}>
                      {entry.delta > 0 ? "+" : ""}
                      {entry.delta}
                    </td>
                    <td className="num tabular muted">{entry.balance_after}</td>
                  </tr>
                ))}
              </tbody>
            </table>
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
