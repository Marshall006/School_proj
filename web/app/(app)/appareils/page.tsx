"use client";

import { useCallback, useEffect, useState } from "react";
import type { DeviceSummary } from "@koda/shared";

import { ApiError, api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { AVATARS, countdown, formatDateTime, relative } from "@/lib/format";
import { Alert, Card, Empty, Loading, Modal, Tag } from "@/components/ui";
import {
  IconAlert,
  IconCheck,
  IconClock,
  IconDevice,
  IconPlus,
  IconShield,
} from "@/components/icons";

export default function AppareilsPage() {
  const { children } = useAuth();
  const [devices, setDevices] = useState<DeviceSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [pairing, setPairing] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setDevices(await api.devices.list());
    setLoading(false);
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  if (loading) return <Loading />;

  const childOf = (childId: string) => children.find((c) => c.id === childId);
  const nameOf = (childId: string) => childOf(childId)?.display_name ?? "Enfant";

  async function act(action: () => Promise<unknown>) {
    setBusy(true);
    try {
      await action();
      await load();
    } finally {
      setBusy(false);
    }
  }

  const active = devices.filter((d) => d.status === "active").length;

  return (
    <>
      <div className="page-head">
        <div className="grow">
          <h1>Appareils</h1>
          <p className="page-subtitle">
            Chaque tablette reçoit, une seule fois, un secret qui lui permet de vérifier les codes
            même sans réseau. Révoquer un appareil coupe immédiatement son accès.
          </p>
        </div>
        <Tag tone={active > 0 ? "good" : undefined}>
          <IconDevice size={13} />
          {active} appareil{active > 1 ? "s" : ""} actif{active > 1 ? "s" : ""}
        </Tag>
      </div>

      <div className="stack">
        <Card
          title={
            <span className="row" style={{ gap: 8 }}>
              <IconPlus size={17} /> Appairer une tablette
            </span>
          }
          hint="première utilisation"
        >
          <p className="secondary small" style={{ marginBottom: 14 }}>
            Installez l&apos;application KODA sur la tablette, puis saisissez-y le code généré ici.
            Ce code d&apos;appairage n&apos;est pas un code de déverrouillage : il ne sert
            qu&apos;à relier l&apos;appareil au foyer.
          </p>
          <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>
            {children.length === 0 && <Empty>Ajoutez d&apos;abord un enfant.</Empty>}
            {children.map((child) => (
              <button key={child.id} className="btn" onClick={() => setPairing(child.id)}>
                <span aria-hidden="true">{AVATARS[child.avatar] ?? "🙂"}</span>
                Appairer pour {child.display_name}
              </button>
            ))}
          </div>
        </Card>

        {devices.length === 0 ? (
          <Card>
            <Empty>
              Aucun appareil appairé pour le moment. Tant qu&apos;aucune tablette n&apos;est
              reliée, les codes générés ici n&apos;ont nulle part où être saisis.
            </Empty>
          </Card>
        ) : (
          <div className="grid grid-2">
            {devices.map((device) => {
              const locked =
                device.code_locked_until && new Date(device.code_locked_until) > new Date();
              const skewMinutes = Math.abs(Math.round(device.clock_skew_ms / 60000));
              const revoked = device.status !== "active";
              return (
                <Card key={device.id} className={revoked ? "child-card is-locked" : "child-card"}>
                  <div className="row" style={{ marginBottom: 12, gap: 12 }}>
                    <span className="avatar" aria-hidden="true">
                      {AVATARS[childOf(device.child_id)?.avatar ?? 0] ?? "🙂"}
                    </span>
                    <div style={{ minWidth: 0 }}>
                      <h2 style={{ marginBottom: 1 }}>{device.name}</h2>
                      <span className="small muted">
                        {nameOf(device.child_id)} · {device.platform}
                      </span>
                    </div>
                    <span className="spacer" />
                    <Tag tone={revoked ? "critical" : "good"}>
                      {revoked ? (
                        "Révoqué"
                      ) : (
                        <>
                          <IconCheck size={13} />
                          Actif
                        </>
                      )}
                    </Tag>
                  </div>

                  <table className="table">
                    <tbody>
                      <tr>
                        <td className="muted small">Dernière activité</td>
                        <td className="small">
                          {device.last_seen_at ? relative(device.last_seen_at) : "jamais"}
                        </td>
                      </tr>
                      <tr>
                        <td className="muted small">Écart d&apos;horloge</td>
                        <td className="small">
                          {skewMinutes > 5 ? (
                            <Tag tone="warning">
                              <IconAlert size={13} />
                              {skewMinutes} min d&apos;écart
                            </Tag>
                          ) : (
                            <span className="muted">à l&apos;heure</span>
                          )}
                        </td>
                      </tr>
                      <tr>
                        <td className="muted small">Codes erronés</td>
                        <td className="small">
                          {device.failed_code_attempts === 0 ? (
                            <span className="muted">aucun</span>
                          ) : (
                            <Tag tone={device.failed_code_attempts >= 5 ? "critical" : "warning"}>
                              {device.failed_code_attempts} essai
                              {device.failed_code_attempts > 1 ? "s" : ""}
                            </Tag>
                          )}
                        </td>
                      </tr>
                      {device.tamper_score > 0 && (
                        <tr>
                          <td className="muted small">Signaux d&apos;anomalie</td>
                          <td className="small">
                            <Tag tone={device.tamper_score > 2 ? "critical" : "warning"}>
                              <IconShield size={13} />
                              indice {device.tamper_score.toFixed(1)}
                            </Tag>
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>

                  {locked && (
                    <Alert tone="warning">
                      Saisie bloquée encore{" "}
                      {countdown(
                        Math.round(
                          (new Date(device.code_locked_until!).getTime() - Date.now()) / 1000,
                        ),
                      )}{" "}
                      après des codes erronés répétés.
                    </Alert>
                  )}

                  <hr className="divider" />
                  <div className="row" style={{ gap: 8 }}>
                    {device.failed_code_attempts > 0 && (
                      <button
                        className="btn btn-sm"
                        disabled={busy}
                        onClick={() => void act(() => api.devices.resetAttempts(device.id))}
                      >
                        <IconCheck size={15} />
                        Débloquer la saisie
                      </button>
                    )}
                    <span className="spacer" />
                    {device.status === "active" && (
                      <button
                        className="btn btn-sm btn-danger"
                        disabled={busy}
                        onClick={() => void act(() => api.devices.revoke(device.id))}
                      >
                        Révoquer
                      </button>
                    )}
                  </div>
                </Card>
              );
            })}
          </div>
        )}
      </div>

      {pairing && (
        <PairingDialog
          childId={pairing}
          childName={nameOf(pairing)}
          onClose={() => {
            setPairing(null);
            void load();
          }}
        />
      )}
    </>
  );
}

function PairingDialog({
  childId,
  childName,
  onClose,
}: {
  childId: string;
  childName: string;
  onClose: () => void;
}) {
  const [code, setCode] = useState<{ code: string; expires_at: string } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [remaining, setRemaining] = useState(0);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    api.devices
      .pairingCode({ child_id: childId, suggested_name: `Tablette de ${childName}` })
      .then(setCode)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Génération impossible."));
  }, [childId, childName]);

  useEffect(() => {
    if (!code) return;
    const tick = () =>
      setRemaining(
        Math.max(0, Math.round((new Date(code.expires_at).getTime() - Date.now()) / 1000)),
      );
    tick();
    const timer = window.setInterval(tick, 1000);
    return () => window.clearInterval(timer);
  }, [code]);

  async function copy() {
    if (!code) return;
    try {
      await navigator.clipboard.writeText(code.code);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      /* Presse-papiers refuse (page non securisee) : le code reste lisible a l'ecran. */
    }
  }

  return (
    <Modal
      title={`Appairer une tablette pour ${childName}`}
      onClose={onClose}
      footer={
        <button className="btn btn-primary" onClick={onClose}>
          Terminé
        </button>
      }
    >
      {error ? (
        <Alert tone="critical">{error}</Alert>
      ) : code ? (
        <div className="stack">
          <ol className="secondary small" style={{ paddingLeft: 18, margin: 0, lineHeight: 1.9 }}>
            <li>Installez l&apos;application KODA sur la tablette de {childName}.</li>
            <li>
              Sur l&apos;écran d&apos;accueil, choisissez « Première utilisation — appairer cet
              appareil ».
            </li>
            <li>Saisissez le code ci-dessous.</li>
          </ol>
          <button
            className="code-display"
            onClick={() => void copy()}
            title="Copier le code"
            style={{
              letterSpacing: "0.18em",
              fontSize: "2rem",
              border: "none",
              cursor: "pointer",
              width: "100%",
            }}
          >
            {code.code}
          </button>
          <div className="row">
            {copied && (
              <Tag tone="good">
                <IconCheck size={13} />
                Copié
              </Tag>
            )}
            <span className="spacer" />
            <Tag tone={remaining < 300 ? "warning" : undefined}>
              <IconClock size={13} />
              Valable encore {countdown(remaining)}
            </Tag>
          </div>
          <Alert tone="info">
            Ce code ne sert qu&apos;une fois, et il expire le {formatDateTime(code.expires_at)}. Ce
            n&apos;est pas le code qui ouvre la tablette.
          </Alert>
        </div>
      ) : (
        <p className="muted">Génération du code…</p>
      )}
    </Modal>
  );
}
