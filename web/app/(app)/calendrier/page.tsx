"use client";

import { useCallback, useEffect, useState } from "react";

import { ApiError, api, type CalendarPeriod } from "@/lib/api";
import { PERIOD_LABELS, formatDate } from "@/lib/format";
import { Alert, Card, Empty, Loading, Tag } from "@/components/ui";
import { IconCalendar, IconInfo, IconPlus, IconSun } from "@/components/icons";

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
  const current = periods.find((p) => p.start_date <= now && now <= p.end_date);
  const invalidRange = form.end_date < form.start_date;

  return (
    <>
      <div className="page-head">
        <div className="grow">
          <h1>Calendrier scolaire</h1>
          <p className="page-subtitle">
            Déclarez les vacances : les règles basculent automatiquement, et le déverrouillage
            direct laisse la place à l&apos;évaluation.
          </p>
        </div>
        <Tag tone={current ? "accent" : undefined}>
          <IconCalendar size={13} />
          {current ? current.label : "Période scolaire ordinaire"}
        </Tag>
      </div>

      <div className="grid grid-2">
        <Card
          title={
            <span className="row" style={{ gap: 8 }}>
              <IconPlus size={17} /> Ajouter une période
            </span>
          }
        >
          <div className="stack" style={{ gap: 14 }}>
            <div className="field">
              <label htmlFor="label">Intitulé</label>
              <input
                id="label"
                value={form.label}
                onChange={(e) => setForm((c) => ({ ...c, label: e.target.value }))}
              />
            </div>
            <div className="field">
              <label htmlFor="type">Type de période</label>
              <select
                id="type"
                value={form.period_type}
                onChange={(e) => setForm((c) => ({ ...c, period_type: e.target.value }))}
              >
                <option value="holiday">Vacances</option>
                <option value="school">Période scolaire</option>
                <option value="weekend">Week-end prolongé</option>
              </select>
              <span className="help">
                {form.period_type === "holiday"
                  ? "Plus de devoirs à valider : l'évaluation devient le chemin principal."
                  : form.period_type === "school"
                    ? "Rythme scolaire : vous pouvez débloquer directement quand les devoirs sont faits."
                    : "Pont ou jour férié : les règles du week-end s'appliquent."}
              </span>
            </div>
            <div className="row" style={{ gap: 12 }}>
              <div className="field" style={{ flex: 1 }}>
                <label htmlFor="debut">Début</label>
                <input
                  id="debut"
                  type="date"
                  value={form.start_date}
                  onChange={(e) => setForm((c) => ({ ...c, start_date: e.target.value }))}
                />
              </div>
              <div className="field" style={{ flex: 1 }}>
                <label htmlFor="fin">Fin</label>
                <input
                  id="fin"
                  type="date"
                  value={form.end_date}
                  onChange={(e) => setForm((c) => ({ ...c, end_date: e.target.value }))}
                />
              </div>
            </div>
            {invalidRange && <Alert tone="warning">La fin précède le début.</Alert>}
            {error && <Alert tone="critical">{error}</Alert>}
            <button
              className="btn btn-primary"
              onClick={() => void add()}
              disabled={busy || invalidRange || !form.label.trim()}
            >
              {busy ? "Ajout…" : "Ajouter la période"}
            </button>
          </div>
        </Card>

        <Card
          title={
            <span className="row" style={{ gap: 8 }}>
              <IconSun size={17} /> Périodes déclarées
            </span>
          }
          hint={periods.length > 0 ? `${periods.length} période${periods.length > 1 ? "s" : ""}` : undefined}
        >
          {periods.length === 0 ? (
            <Empty>
              Aucune période déclarée. Sans calendrier, les samedis et dimanches sont traités en
              week-end et le reste en période scolaire.
            </Empty>
          ) : (
            <table className="table">
              <thead>
                <tr>
                  <th>Intitulé</th>
                  <th>Type</th>
                  <th>Du</th>
                  <th>Au</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {periods.map((period) => {
                  const active = period.start_date <= now && now <= period.end_date;
                  const past = period.end_date < now;
                  return (
                    <tr key={period.id} style={past ? { opacity: 0.6 } : undefined}>
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
          <hr className="divider" />
          <p className="row small muted" style={{ gap: 8, alignItems: "flex-start" }}>
            <IconInfo size={15} />
            <span>
              La période du jour décide des règles appliquées à chaque enfant. Elle est visible sur
              sa page de règles, et une période déclarée ici prime sur le jour de la semaine.
            </span>
          </p>
        </Card>
      </div>
    </>
  );
}
