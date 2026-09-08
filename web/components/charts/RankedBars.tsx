"use client";

import { useChartTooltip } from "./Tooltip";

export interface RankedRow {
  label: string;
  value: number | null;
  detail?: string;
  count?: number;
}

/**
 * Taux de reussite par matiere, classe du plus faible au plus fort.
 *
 * Une seule teinte : la comparaison porte sur une grandeur, pas sur des
 * identites. Le trait pointille marque le seuil exige par le foyer ; les
 * matieres en dessous portent une etiquette explicite (jamais la couleur
 * seule) pour rester lisibles en cas de daltonisme ou d'impression.
 */
export function RankedBars({
  rows,
  threshold,
  thresholdLabel = "seuil de reussite",
}: {
  rows: RankedRow[];
  threshold?: number;
  thresholdLabel?: string;
}) {
  const { show, hide, node } = useChartTooltip();

  if (rows.length === 0) {
    return <p className="empty">Aucune reponse enregistree sur la periode.</p>;
  }

  const rowHeight = 30;
  const labelWidth = 148;
  const padRight = 132;
  const width = 600;
  const height = rows.length * rowHeight + 22;
  const plotWidth = width - labelWidth - padRight;
  const x = (value: number) => labelWidth + Math.max(0, Math.min(1, value)) * plotWidth;

  return (
    <div className="chart-wrap">
      <div className="chart">
        <svg width={width} height={height} role="img" aria-label="Taux de reussite par matiere">
          {[0, 0.25, 0.5, 0.75, 1].map((tick) => (
            <line key={tick} className="grid-line" x1={x(tick)} x2={x(tick)} y1={4} y2={rows.length * rowHeight} />
          ))}

          {rows.map((row, index) => {
            const top = index * rowHeight + 6;
            const value = row.value ?? 0;
            const barWidth = Math.max(3, x(value) - labelWidth);
            const below = threshold !== undefined && row.value !== null && row.value < threshold;
            return (
              <g
                key={row.label}
                onMouseMove={(event) =>
                  show(
                    event,
                    <>
                      <strong>{row.label}</strong>
                      <br />
                      {row.value === null ? "aucune donnee" : `${Math.round(value * 100)} % de reussite`}
                      {row.detail ? (
                        <>
                          <br />
                          {row.detail}
                        </>
                      ) : null}
                    </>,
                  )
                }
                onMouseLeave={hide}
              >
                <rect x={0} y={top - 4} width={width} height={rowHeight - 2} fill="transparent" />
                <text
                  className="axis-label"
                  x={labelWidth - 10}
                  y={top + 13}
                  textAnchor="end"
                  style={{ fill: "var(--ink-secondary)", fontSize: 12 }}
                >
                  {row.label}
                </text>
                <rect x={labelWidth} y={top + 3} width={plotWidth} height={14} rx={4} fill="var(--surface-sunken)" />
                <rect
                  x={labelWidth}
                  y={top + 3}
                  width={barWidth}
                  height={14}
                  rx={4}
                  fill="var(--data-1)"
                />
                <text className="bar-value" x={x(value) + 8} y={top + 14}>
                  {row.value === null ? "—" : `${Math.round(value * 100)} %`}
                </text>
                {/* Le statut s'ecrit a cote de la barre, jamais dessus : sur un
                    aplat colore le texte perdrait tout contraste. Icone + mot,
                    pour ne pas dependre de la couleur. */}
                {below && (
                  <text
                    x={x(value) + 44}
                    y={top + 14}
                    style={{ fill: "var(--serious-ink)", fontSize: 10, fontWeight: 700 }}
                  >
                    ▲ sous le seuil
                  </text>
                )}
              </g>
            );
          })}

          {threshold !== undefined && (
            <>
              <line
                className="threshold-line"
                x1={x(threshold)}
                x2={x(threshold)}
                y1={2}
                y2={rows.length * rowHeight + 2}
              />
              <text className="axis-label" x={x(threshold)} y={height - 5} textAnchor="middle">
                {thresholdLabel} · {Math.round(threshold * 100)} %
              </text>
            </>
          )}
        </svg>
      </div>
      {node}
    </div>
  );
}
