"use client";

import { BAND_LABELS } from "@/lib/format";
import { useChartTooltip } from "./Tooltip";

const ORDER = ["fragile", "en_cours", "acquis", "expert"] as const;
const FILLS: Record<string, string> = {
  fragile: "var(--ordinal-1)",
  en_cours: "var(--ordinal-2)",
  acquis: "var(--ordinal-3)",
  expert: "var(--ordinal-4)",
};

/**
 * Répartition des notions par palier de maîtrise.
 *
 * Echelle ordonnee (fragile -> expert) : une seule teinte, du clair au fonce.
 * La legende porte les effectifs, donc la couleur n'est jamais le seul canal.
 */
export function MasteryBar({ bands }: { bands: Record<string, number> }) {
  const { show, hide, node } = useChartTooltip();
  const entries = ORDER.map((band) => ({ band, count: bands[band] ?? 0 }));
  const total = entries.reduce((sum, entry) => sum + entry.count, 0) + (bands.unknown ?? 0);

  if (total === 0) {
    return <p className="empty">Le niveau se precisera après quelques évaluations.</p>;
  }

  const width = 520;
  const height = 30;
  const gap = 2;
  let cursor = 0;

  return (
    <div className="chart-wrap">
      <div className="chart">
        <svg width={width} height={height} role="img" aria-label="Répartition des notions par palier de maîtrise">
          {entries.map(({ band, count }) => {
            if (count === 0) return null;
            const segmentWidth = (count / total) * width - gap;
            const x = cursor;
            cursor += (count / total) * width;
            return (
              <g
                key={band}
                onMouseMove={(event) =>
                  show(
                    event,
                    <>
                      <strong>{BAND_LABELS[band]}</strong>
                      <br />
                      {count} notion{count > 1 ? "s" : ""} · {Math.round((count / total) * 100)} %
                    </>,
                  )
                }
                onMouseLeave={hide}
              >
                <rect x={x} y={4} width={Math.max(2, segmentWidth)} height={22} rx={4} fill={FILLS[band]} />
                {segmentWidth > 34 && (
                  <text
                    x={x + segmentWidth / 2}
                    y={19}
                    textAnchor="middle"
                    style={{
                      fontSize: 11,
                      fontWeight: 700,
                      // Les deux premieres marches sont trop claires pour du
                      // blanc : on inverse l'encre plutot que de perdre le
                      // contraste (le compte figure aussi dans la legende).
                      fill: band === "fragile" || band === "en_cours" ? "var(--chip-ink)" : "#fff",
                    }}
                  >
                    {count}
                  </text>
                )}
              </g>
            );
          })}
        </svg>
      </div>
      {node}
      <div className="legend" style={{ marginTop: 10 }}>
        {entries.map(({ band, count }) => (
          <span key={band} className="legend-item">
            <span className="legend-swatch" style={{ background: FILLS[band] }} />
            {BAND_LABELS[band]} · <strong className="tabular">{count}</strong>
          </span>
        ))}
        {(bands.unknown ?? 0) > 0 && (
          <span className="legend-item muted">
            <span className="legend-swatch" style={{ background: "var(--line-strong)" }} />
            {BAND_LABELS.unknown} · {bands.unknown}
          </span>
        )}
      </div>
    </div>
  );
}
