"use client";

import { useEffect, type ReactNode } from "react";

export function Card({
  title,
  hint,
  action,
  children,
  className = "",
}: {
  title?: ReactNode;
  hint?: ReactNode;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`card ${className}`}>
      {(title || action) && (
        <div className="card-head">
          {title && <h2>{title}</h2>}
          {hint && <span className="card-hint">{hint}</span>}
          {action && <div style={{ marginLeft: hint ? 10 : "auto" }}>{action}</div>}
        </div>
      )}
      {children}
    </section>
  );
}

export function Stat({
  label,
  value,
  hint,
  tone,
}: {
  label: string;
  value: ReactNode;
  hint?: ReactNode;
  tone?: "good" | "warning" | "critical";
}) {
  const color =
    tone === "good" ? "var(--good-ink)" : tone === "critical" ? "var(--critical)" : undefined;
  return (
    <div className="stat">
      <span className="stat-label">{label}</span>
      <span className="stat-value" style={{ color }}>
        {value}
      </span>
      {hint && <span className="stat-hint">{hint}</span>}
    </div>
  );
}

export function Tag({
  children,
  tone,
}: {
  children: ReactNode;
  tone?: "good" | "warning" | "critical" | "accent";
}) {
  return <span className={`tag${tone ? ` tag-${tone}` : ""}`}>{children}</span>;
}

export function Modal({
  title,
  onClose,
  children,
  footer,
}: {
  title: ReactNode;
  onClose: () => void;
  children: ReactNode;
  footer?: ReactNode;
}) {
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
    };
  }, [onClose]);

  return (
    <div className="modal-backdrop" onClick={onClose} role="presentation">
      <div
        className="modal"
        onClick={(event) => event.stopPropagation()}
        role="dialog"
        aria-modal="true"
      >
        <div className="modal-head">
          <h2>{title}</h2>
          <button className="modal-close" onClick={onClose} aria-label="Fermer">
            ×
          </button>
        </div>
        {children}
        {footer && <div className="row" style={{ marginTop: 18, justifyContent: "flex-end" }}>{footer}</div>}
      </div>
    </div>
  );
}

export function Alert({
  tone = "info",
  children,
}: {
  tone?: "info" | "good" | "warning" | "critical";
  children: ReactNode;
}) {
  const icons = { info: "ⓘ", good: "✓", warning: "▲", critical: "■" };
  return (
    <div className={`alert${tone === "info" ? "" : ` alert-${tone}`}`}>
      <span className="alert-icon" aria-hidden="true">
        {icons[tone]}
      </span>
      <div>{children}</div>
    </div>
  );
}

export function Loading({ label = "Chargement…" }: { label?: string }) {
  return (
    <div className="stack" aria-busy="true" aria-live="polite">
      <div className="skeleton" style={{ height: 84 }} />
      <div className="skeleton" style={{ height: 200 }} />
      <span className="muted small">{label}</span>
    </div>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return <p className="empty">{children}</p>;
}
