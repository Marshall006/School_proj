"use client";

import { useChartTooltip } from "./Tooltip";
import { minutes } from "@/lib/format";

export interface TrendPoint {
  date: string;
  granted_minutes: number;
  consumed_minutes: number;
  sessions: number;
}

/**
 * Temps d'écran jour par jour.
 *
 * Deux nuances d'une même teinte : la barre claire est le temps *accordé*,
 * la barre foncee le temps reellement *consommé*. Le rapport entre les deux
 * repond à la question que se posent les parents ("est-ce que tout le temps
 * gagne est utilisé ?") sans introduire une seconde couleur.
 */
export function ColumnTrend({ data, height = 168 }: { data: TrendPoint[]; height?: number }) {
  const { show, hide, node } = useChartTooltip();

  if (data.length === 0) {
    return <p className="empty">Pas encore de temps d&apos;écran enregistré.</p>;
  }

  const width = Math.max(320, data.length * 34);
  const padTop = 14;
  const padBottom = 26;
  const padLeft = 34;
  const plotHeight = height - padTop - padBottom;
  const plotWidth = width - padLeft - 8;

  const maxValue = Math.max(60, ...data.map((d) => Math.max(d.granted_minutes, d.consumed_minutes)));
  const step = maxValue > 240 ? 120 : maxValue > 120 ? 60 : 30;
  const ticks: number[] = [];
  for (let value = 0; value <= maxValue; value += step) ticks.push(value);

  const slot = plotWidth / data.length;
  const barWidth = Math.max(6, Math.min(20, slot - 8));
  const y = (value: number) => padTop + plotHeight - (value / maxValue) * plotHeight;

  return (
    <div className="chart-wrap">
      <div className="chart">
        <svg width={width} height={height} role="img" aria-label="Temps d'écran des 14 derniers jours">
          {ticks.map((tick) => (
            <g key={tick}>
              <line className="grid-line" x1={padLeft} x2={width - 8} y1={y(tick)} y2={y(tick)} />
              <text className="axis-label" x={padLeft - 7} y={y(tick) + 4} textAnchor="end">
                {tick}
              </text>
            </g>
          ))}
          <line className="baseline" x1={padLeft} x2={width - 8} y1={y(0)} y2={y(0)} />

          {data.map((point, index) => {
            const cx = padLeft + slot * index + slot / 2;
            const grantedHeight = Math.max(0, y(0) - y(point.granted_minutes));
            const consumedHeight = Math.max(0, y(0) - y(point.consumed_minutes));
            const label = new Date(point.date).toLocaleDateString("fr-FR", {
              day: "numeric",
              month: "short",
            });
            return (
              <g
                key={point.date}
                onMouseMove={(event) =>
                  show(
                    event,
                    <>
                      <strong>{label}</strong>
                      <br />
                      Accordé : {minutes(point.granted_minutes)}
                      <br />
                      Consommé : {minutes(point.consumed_minutes)}
                      {point.sessions > 0 ? (
                        <>
                          <br />
                          {point.sessions} session{point.sessions > 1 ? "s" : ""}
                        </>
                      ) : null}
                    </>,
                  )
                }
                onMouseLeave={hide}
              >
                {/* Zone de survol plus large que la barre. */}
                <rect x={cx - slot / 2} y={padTop} width={slot} height={plotHeight} fill="transparent" />
                {grantedHeight > 0 && (
                  <rect
                    x={cx - barWidth / 2}
                    y={y(point.granted_minutes)}
                    width={barWidth}
                    height={grantedHeight}
                    rx={4}
                    fill="var(--ordinal-1)"
                  />
                )}
                {consumedHeight > 0 && (
                  <rect
                    x={cx - barWidth / 2 + 2}
                    y={y(point.consumed_minutes)}
                    width={barWidth - 4}
                    height={consumedHeight}
                    rx={3}
                    fill="var(--data-1)"
                  />
                )}
                {index % 2 === 0 && (
                  <text className="axis-label" x={cx} y={height - 8} textAnchor="middle">
                    {new Date(point.date).getDate()}
                  </text>
                )}
              </g>
            );
          })}
        </svg>
      </div>
      {node}
      <div className="legend" style={{ marginTop: 10 }}>
        <span className="legend-item">
          <span className="legend-swatch" style={{ background: "var(--ordinal-1)" }} /> Temps accordé
        </span>
        <span className="legend-item">
          <span className="legend-swatch" style={{ background: "var(--data-1)" }} /> Temps consommé
        </span>
        <span className="muted small" style={{ marginLeft: "auto" }}>
          minutes par jour
        </span>
      </div>
    </div>
  );
}
