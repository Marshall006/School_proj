"use client";

import { useEffect, useState } from "react";
import type { Child } from "@koda/shared";

import { ApiError, api, type IssuedCodeResponse } from "@/lib/api";
import { countdown, minutes as fmtMinutes } from "@/lib/format";
import { Alert, Modal } from "@/components/ui";

const DURATIONS = [15, 30, 45, 60, 90, 120, 180, 240];

/**
 * Generation d'un code de deverrouillage.
 *
 * Le parent choisit une duree, obtient un code a 10 chiffres et le dicte a
 * l'enfant. Le code fonctionne meme si la tablette est hors ligne, et il expire
 * : le compte a rebours est donc une information utile, pas une decoration.
 */
export function UnlockDialog({
  child,
  kind = "direct",
  onClose,
}: {
  child: Child;
  kind?: "direct" | "bonus";
  onClose: () => void;
}) {
  const [duration, setDuration] = useState(kind === "bonus" ? 30 : 60);
  const [note, setNote] = useState("");
  const [issued, setIssued] = useState<IssuedCodeResponse | null>(null);
  const [error, setError] = useState<{ message: string; code: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const [remaining, setRemaining] = useState(0);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (!issued) return;
    const tick = () =>
      setRemaining(Math.max(0, Math.round((new Date(issued.expires_at).getTime() - Date.now()) / 1000)));
    tick();
    const timer = window.setInterval(tick, 1000);
    return () => window.clearInterval(timer);
  }, [issued]);

  async function generate() {
    setBusy(true);
    setError(null);
    try {
      const call = kind === "bonus" ? api.unlock.bonusCode : api.unlock.parentCode;
      setIssued(
        await call({
          child_id: child.id,
          duration_minutes: duration,
          note: note.trim() || undefined,
        }),
      );
    } catch (err) {
      setError(
        err instanceof ApiError
          ? { message: err.message, code: err.code }
          : { message: "Impossible de generer le code.", code: "erreur" },
      );
    } finally {
      setBusy(false);
    }
  }

  async function copy() {
    if (!issued) return;
    try {
      await navigator.clipboard.writeText(issued.code);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      /* le presse-papier peut etre refuse : le code reste lisible a l'ecran */
    }
  }

  return (
    <Modal
      title={kind === "bonus" ? `Rallonge pour ${child.display_name}` : `Debloquer la tablette de ${child.display_name}`}
      onClose={onClose}
      footer={
        issued ? (
          <button className="btn btn-primary" onClick={onClose}>
            Termine
          </button>
        ) : (
          <>
            <button className="btn" onClick={onClose}>
              Annuler
            </button>
            <button className="btn btn-primary" onClick={() => void generate()} disabled={busy}>
              {busy ? "Generation…" : "Generer le code"}
            </button>
          </>
        )
      }
    >
      {issued ? (
        <div className="stack">
          <p className="secondary small">
            Dictez ce code a {child.display_name}. Il ouvre{" "}
            <strong>{fmtMinutes(issued.duration_minutes)}</strong> de temps d&apos;ecran et ne
            fonctionne qu&apos;une seule fois.
          </p>
          <div className="code-display">{issued.formatted}</div>
          <div className="row">
            <button className="btn btn-sm" onClick={() => void copy()}>
              {copied ? "✓ Copie" : "Copier"}
            </button>
            <span className="spacer" />
            <span className={`tag${remaining < 300 ? " tag-warning" : ""}`}>
              Expire dans {countdown(remaining)}
            </span>
          </div>
          <Alert tone="info">
            La tablette peut etre hors ligne : elle sait verifier ce code toute seule.
          </Alert>
        </div>
      ) : (
        <div className="stack">
          <div className="field">
            <label>Duree accordee</label>
            <div className="row" style={{ gap: 6 }}>
              {DURATIONS.map((value) => (
                <button
                  key={value}
                  type="button"
                  className={`btn btn-sm${value === duration ? " btn-primary" : ""}`}
                  onClick={() => setDuration(value)}
                >
                  {fmtMinutes(value)}
                </button>
              ))}
            </div>
          </div>
          <div className="field">
            <label htmlFor="note">Motif (facultatif)</label>
            <input
              id="note"
              value={note}
              onChange={(event) => setNote(event.target.value)}
              placeholder="Devoirs et lecons faits"
              maxLength={200}
            />
            <span className="help">Conserve dans l&apos;historique du foyer.</span>
          </div>
          {error && (
            <Alert tone={error.code === "policy_forbids" ? "warning" : "critical"}>
              {error.message}
              {error.code === "policy_forbids" && (
                <>
                  <br />
                  <span className="small">
                    Pendant les vacances, l&apos;acces se gagne par une evaluation. Vous pouvez
                    accorder une rallonge exceptionnelle a la place.
                  </span>
                </>
              )}
              {error.code === "no_paired_device" && (
                <>
                  <br />
                  <span className="small">Appairez d&apos;abord une tablette depuis « Appareils ».</span>
                </>
              )}
            </Alert>
          )}
        </div>
      )}
    </Modal>
  );
}
