"use client";

import { useCallback, useEffect, useState } from "react";

import { ApiError, api, type AssessmentSummary, type ParentAssessmentView } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { formatDateTime, minutes, score20 } from "@/lib/format";
import { Alert, Card, Empty, Loading, Tag } from "@/components/ui";

/**
 * Validation parentale des reponses manuscrites.
 *
 * Quand la reconnaissance d'ecriture n'est pas fiable, l'enfant n'est jamais
 * penalise : la copie arrive ici et c'est le parent qui tranche.
 */
export default function CopiesPage() {
  const { children } = useAuth();
  const [pending, setPending] = useState<AssessmentSummary[]>([]);
  const [selected, setSelected] = useState<ParentAssessmentView | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const load = useCallback(async () => {
    const rows = await api.assessments.pendingReview();
    setPending(rows);
    setLoading(false);
    if (rows.length > 0) {
      setSelected(await api.assessments.view(rows[0].id));
    } else {
      setSelected(null);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  if (loading) return <Loading />;

  async function grade(itemId: string, score: number) {
    if (!selected) return;
    setBusy(true);
    setMessage(null);
    try {
      const result = await api.assessments.grade(selected.assessment.id, itemId, score);
      if (result) {
        setMessage(
          result.passed
            ? `Evaluation validee : ${score20(result.score_out_of_20)}. Le code d'acces a ete delivre.`
            : `Evaluation non validee : ${score20(result.score_out_of_20)}. Le temps de carence demarre.`,
        );
      }
      await load();
    } catch (err) {
      setMessage(err instanceof ApiError ? err.message : "Enregistrement impossible.");
    } finally {
      setBusy(false);
    }
  }

  const nameOf = (childId: string) => children.find((c) => c.id === childId)?.display_name ?? "Enfant";

  return (
    <>
      <div className="page-head">
        <div className="grow">
          <h1>Copies a valider</h1>
          <p className="page-subtitle">
            Ces reponses ont ete ecrites a la main sur l&apos;ardoise et n&apos;ont pas pu etre
            corrigees automatiquement. Votre verdict conclut l&apos;evaluation.
          </p>
        </div>
      </div>

      {pending.length === 0 ? (
        <Card>
          <Empty>Aucune copie en attente. Tout est corrige.</Empty>
        </Card>
      ) : (
        <div className="stack">
          {message && <Alert tone="good">{message}</Alert>}

          <div className="row" style={{ gap: 6 }}>
            {pending.map((row) => (
              <button
                key={row.id}
                className={`btn btn-sm${selected?.assessment.id === row.id ? " btn-primary" : ""}`}
                onClick={() => void api.assessments.view(row.id).then(setSelected)}
              >
                {nameOf(row.child_id)} · {formatDateTime(row.created_at)}
              </button>
            ))}
          </div>

          {selected && (
            <Card
              title={`Copie du ${formatDateTime(selected.assessment.created_at)}`}
              hint={`${selected.assessment.points_earned}/${selected.assessment.points_max} points acquis · seuil ${score20(selected.assessment.pass_score_out_of_20)}`}
            >
              <div className="stack">
                {selected.items.map((item) => (
                  <div
                    key={item.id}
                    className="card"
                    style={{
                      background: item.needs_manual_review ? "var(--accent-wash)" : "var(--surface-sunken)",
                      borderColor: item.needs_manual_review ? "var(--accent)" : "var(--line)",
                    }}
                  >
                    <div className="row" style={{ marginBottom: 8 }}>
                      <span className="tag">Question {item.position + 1}</span>
                      {item.subject_code && <span className="tag">{item.subject_code}</span>}
                      <span className="spacer" />
                      {item.needs_manual_review ? (
                        <Tag tone="warning">▲ A trancher</Tag>
                      ) : item.is_correct ? (
                        <Tag tone="good">✓ Juste</Tag>
                      ) : (
                        <Tag tone="critical">Faux</Tag>
                      )}
                    </div>

                    <p style={{ marginBottom: 10 }}>{item.prompt}</p>

                    {item.strokes?.paths && item.strokes.paths.length > 0 && (
                      <Strokes strokes={item.strokes} />
                    )}

                    <div className="row small secondary" style={{ marginTop: 8 }}>
                      <span>
                        Reponse transcrite :{" "}
                        <strong>{String((item.answer as { transcript?: string })?.transcript ?? "—")}</strong>
                      </span>
                      <span className="spacer" />
                      <span className="muted">
                        {item.time_spent_ms > 0 ? `${Math.round(item.time_spent_ms / 1000)} s` : ""}
                      </span>
                    </div>

                    {item.needs_manual_review && (
                      <>
                        <hr className="divider" />
                        <div className="row" style={{ gap: 8 }}>
                          <span className="small secondary">Votre verdict :</span>
                          <button className="btn btn-sm btn-primary" disabled={busy} onClick={() => void grade(item.id, 1)}>
                            ✓ Juste
                          </button>
                          <button className="btn btn-sm" disabled={busy} onClick={() => void grade(item.id, 0.5)}>
                            Partiellement juste
                          </button>
                          <button className="btn btn-sm btn-danger" disabled={busy} onClick={() => void grade(item.id, 0)}>
                            Faux
                          </button>
                        </div>
                      </>
                    )}
                  </div>
                ))}
              </div>
            </Card>
          )}
        </div>
      )}
    </>
  );
}

/** Restitution du trace de l'ardoise, tel que l'enfant l'a ecrit. */
function Strokes({ strokes }: { strokes: { paths?: number[][][]; width?: number; height?: number } }) {
  const width = strokes.width ?? 400;
  const height = strokes.height ?? 200;
  return (
    <div
      style={{
        background: "var(--surface-raised)",
        border: "1px solid var(--line)",
        borderRadius: "var(--radius-sm)",
        padding: 8,
        overflowX: "auto",
      }}
    >
      <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Reponse manuscrite">
        {(strokes.paths ?? []).map((path, index) => (
          <polyline
            key={index}
            points={path.map((point) => `${point[0]},${point[1]}`).join(" ")}
            fill="none"
            stroke="var(--ink)"
            strokeWidth={2.5}
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        ))}
      </svg>
    </div>
  );
}
