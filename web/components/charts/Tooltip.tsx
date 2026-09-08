"use client";

import { useState, type ReactNode } from "react";

export interface TooltipState {
  x: number;
  y: number;
  content: ReactNode;
}

/** Infobulle de graphique : suit le curseur, ne capte jamais les evenements. */
export function useChartTooltip() {
  const [tip, setTip] = useState<TooltipState | null>(null);

  function show(event: React.MouseEvent, content: ReactNode) {
    const host = event.currentTarget.closest(".chart-wrap") as HTMLElement | null;
    if (!host) return;
    const bounds = host.getBoundingClientRect();
    setTip({
      x: event.clientX - bounds.left,
      y: event.clientY - bounds.top,
      content,
    });
  }

  const hide = () => setTip(null);

  const node = tip ? (
    <div
      className="chart-tooltip"
      style={{
        left: Math.max(8, Math.min(tip.x + 12, 10_000)),
        top: Math.max(4, tip.y - 46),
      }}
      role="status"
    >
      {tip.content}
    </div>
  ) : null;

  return { show, hide, node };
}
