"use client";

import { useCallback, useEffect, useState } from "react";
import type { DeviceSummary } from "@koda/shared";

import { ApiError, api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { countdown, formatDateTime, relative } from "@/lib/format";
import { Alert, Card, Empty, Loading, Modal, Tag } from "@/components/ui";

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

  const nameOf = (childId: string) =>
    children.find((c) => c.id === childId)?.display_name ?? "Enfant";

  async function act(action: () => Promise<unknown>) {
    setBusy(true);
    try {
      await action();
      await load();
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <div className="page-head">
        <div className="grow">
          <h1>Appareils</h1>
          <p className="page-subtitle">
            Chaque tablette recoit, une seule fois, un secret qui lui permet de verifier les codes
            hors ligne. Revoquer un appareil coupe immediatement son acces.
          </p>
        </div>
      </div>

      <div className="stack">
        <Card title="Appairer une tablette">
          <p className="secondary small" style={{ marginBottom: 12 }}>
            Installez l&apos;application KODA sur la tablette, puis saisissez-y le code genere ici.
          </p>
          <div className="row" style={{ gap: 8 }}>
            {children.length === 0 && <Empty>Ajoutez d&apos;abord un enfant.</Empty>}
            {children.map((child) => (
              <button key={child.id} className="btn" onClick={() => setPairing(child.id)}>
                Appairer pour {child.display_name}
              </button>
            ))}
          </div>
        </Card>

        {devices.length === 0 ? (
          <Card>
            <Empty>Aucun appareil appaire pour le moment.</Empty>
          </Card>
        ) : (
          <div className="grid grid-2">
            {devices.map((device) => {
              const locked = device.code_locked_until && new Date(device.code_locked_until) > new Date();
              const skewMinutes = Math.abs(Math.round(device.clock_skew_ms / 60000));
              return (
                <Card key={device.id}>
                  <div className="row" style={{ marginBottom: 10 }}>
                    <div>
                      <h2 style={{ marginBottom: 2 }}>{device.name}</h2>
                      <span className="small muted">
                        {nameOf(device.child_id)} · {device.platform}
                      </span>
                    </div>
                    <span className="spacer" />
                    <Tag tone={device.status === "active" ? "good" : "critical"}>
                      {device.status === "active" ? "Actif" : device.status === "revoked" ? "Revoque" : device.status}
                    </Tag>
                  </div>

                  <table className="table">
                    <tbody>
                      <tr>
                        <td className="muted small">Derniere activite</td>
                        <td className="small">
                          {device.last_seen_at ? relative(device.last_seen_at) : "jamais"}
                        </td>
                      </tr>
                      <tr>
                        <td className="muted small">Ecart d&apos;horloge</td>
                        <td className="small">
                          {skewMinutes > 5 ? (
                            <Tag tone="warning">▲ {skewMinutes} min d&apos;ecart</Tag>
                          ) : (
                            <span className="muted">a l&apos;heure</span>
                          )}
                        </td>
                      </tr>
                      <tr>
                        <td className="muted small">Codes errones</td>
                        <td className="small">
                          {device.failed_code_attempts === 0 ? (
                            <span className="muted">aucun</span>
                          ) : (
                            <Tag tone={device.failed_code_attempts >= 5 ? "critical" : "warning"}>
                              {device.failed_code_attempts} essai(s)
                            </Tag>
                          )}
                        </td>
                      </tr>
                      {device.tamper_score > 0 && (
                        <tr>
                          <td className="muted small">Signaux d&apos;anomalie</td>
                          <td className="small">
                            <Tag tone={device.tamper_score > 2 ? "critical" : "warning"}>
                              indice {device.tamper_score.toFixed(1)}
                            </Tag>
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>

                  {locked && (
                    <Alert tone="warning">
                      Saisie bloquee encore{" "}
                      {countdown(
                        Math.round((new Date(device.code_locked_until!).getTime() - Date.now()) / 1000),
                      )}{" "}
                      apres des codes errones repetes.
                    </Alert>
                  )}

                  <hr className="divider" />
                  <div className="row" style={{ gap: 8 }}>
                    {device.failed_code_attempts > 0 && (
                      <button className="btn btn-sm" disabled={busy} onClick={() => void act(() => api.devices.resetAttempts(device.id))}>
                        Debloquer la saisie
                      </button>
                    )}
                    {device.status === "active" && (
                      <button className="btn btn-sm btn-danger" disabled={busy} onClick={() => void act(() => api.devices.revoke(device.id))}>
                        Revoquer l&apos;appareil
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

  useEffect(() => {
    api.devices
      .pairingCode({ child_id: childId, suggested_name: `Tablette de ${childName}` })
      .then(setCode)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Generation impossible."));
  }, [childId, childName]);

  useEffect(() => {
    if (!code) return;
    const tick = () =>
      setRemaining(Math.max(0, Math.round((new Date(code.expires_at).getTime() - Date.now()) / 1000)));
    tick();
    const timer = window.setInterval(tick, 1000);
    return () => window.clearInterval(timer);
  }, [code]);

  return (
    <Modal
      title={`Appairer une tablette pour ${childName}`}
      onClose={onClose}
      footer={
        <button className="btn btn-primary" onClick={onClose}>
          Termine
        </button>
      }
    >
      {error ? (
        <Alert tone="critical">{error}</Alert>
      ) : code ? (
        <div className="stack">
          <ol className="secondary small" style={{ paddingLeft: 18, margin: 0, lineHeight: 1.8 }}>
            <li>Installez l&apos;application KODA sur la tablette de {childName}.</li>
            <li>Sur l&apos;ecran d&apos;accueil, choisissez « Appairer cet appareil ».</li>
            <li>Saisissez le code ci-dessous.</li>
          </ol>
          <div className="code-display" style={{ letterSpacing: "0.18em", fontSize: "2rem" }}>
            {code.code}
          </div>
          <div className="row">
            <span className="spacer" />
            <span className={`tag${remaining < 300 ? " tag-warning" : ""}`}>
              Valable encore {countdown(remaining)}
            </span>
          </div>
          <Alert tone="info">
            Ce code ne sert qu&apos;une fois. Il expire le {formatDateTime(code.expires_at)}.
          </Alert>
        </div>
      ) : (
        <p className="muted">Generation du code…</p>
      )}
    </Modal>
  );
}
