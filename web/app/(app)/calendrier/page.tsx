"use client";

import { useCallback, useEffect, useState } from "react";

import { ApiError, api, type CalendarPeriod } from "@/lib/api";
import { PERIOD_LABELS, formatDate } from "@/lib/format";
import { Alert, Card, Empty, Loading, Tag } from "@/components/ui";

export default function CalendrierPage() {
  const [periods, setPeriods] = useState<CalendarPeriod[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const today = new Date().toISOString().slice(0, 10);
  const [form, setForm] = useState({
    label: "Vacances",
    period_type: "holiday",
    start_date: today,
    end_date: today,
  });

  const load = useCallback(async () => {
    setPeriods(await api.calendar.list());
    setLoading(false);
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  if (loading) return <Loading />;

  async function add() {
    setBusy(true);
    setError(null);
    try {
      await api.calendar.add(form);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Ajout impossible.");
    } finally {
      setBusy(false);
    }
  }

  const now = new Date().toISOString().slice(0, 10);

  return (
    <>
      <div className="page-head">
        <div className="grow">
          <h1>Calendrier scolaire</h1>
          <p className="page-subtitle">
            Declarez les vacances : les regles basculent automatiquement, et le deverrouillage
            direct laisse la place a l&apos;evaluation.
          </p>
        </div>
      </div>

      <div className="grid grid-2">
        <Card title="Ajouter une periode">
          <div className="stack" style={{ gap: 13 }}>
            <div className="field">
              <label htmlFor="label">Intitule</label>
              <input id="label" value={form.label} onChange={(e) => setForm((c) => ({ ...c, label: e.target.value }))} />
            </div>
            <div className="field">
              <label htmlFor="type">Type de periode</label>
              <select
                id="type"
                value={form.period_type}
                onChange={(e) => setForm((c) => ({ ...c, period_type: e.target.value }))}
              >
                <option value="holiday">Vacances</option>
                <option value="school">Periode scolaire</option>
                <option value="weekend">Week-end prolonge</option>
              </select>
            </div>
            <div className="row" style={{ gap: 12 }}>
              <div className="field" style={{ flex: 1 }}>
                <label htmlFor="debut">Debut</label>
                <input id="debut" type="date" value={form.start_date} onChange={(e) => setForm((c) => ({ ...c, start_date: e.target.value }))} />
              </div>
              <div className="field" style={{ flex: 1 }}>
                <label htmlFor="fin">Fin</label>
                <input id="fin" type="date" value={form.end_date} onChange={(e) => setForm((c) => ({ ...c, end_date: e.target.value }))} />
              </div>
            </div>
            {error && <Alert tone="critical">{error}</Alert>}
            <button className="btn btn-primary" onClick={() => void add()} disabled={busy}>
              {busy ? "Ajout…" : "Ajouter la periode"}
            </button>
          </div>
        </Card>

        <Card title="Periodes declarees">
          {periods.length === 0 ? (
            <Empty>
              Aucune periode declaree. Sans calendrier, les samedis et dimanches sont traites en
              week-end et le reste en periode scolaire.
            </Empty>
          ) : (
            <table className="table">
              <thead>
                <tr>
                  <th>Intitule</th>
                  <th>Type</th>
                  <th>Du</th>
                  <th>Au</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {periods.map((period) => {
                  const active = period.start_date <= now && now <= period.end_date;
                  return (
                    <tr key={period.id}>
                      <td>
                        {period.label} {active && <Tag tone="accent">en cours</Tag>}
                      </td>
                      <td className="small">{PERIOD_LABELS[period.period_type]}</td>
                      <td className="small">{formatDate(period.start_date)}</td>
                      <td className="small">{formatDate(period.end_date)}</td>
                      <td>
                        <button
                          className="btn btn-sm btn-danger"
                          disabled={busy}
                          onClick={() =>
                            void (async () => {
                              setBusy(true);
                              await api.calendar.remove(period.id);
                              await load();
                              setBusy(false);
                            })()
                          }
                        >
                          Retirer
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </Card>
      </div>
    </>
  );
}
