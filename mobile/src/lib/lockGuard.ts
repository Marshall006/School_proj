/**
 * Le verrou local.
 *
 * C'est le composant qui rend le produit credible : meme sans reseau, la
 * tablette sait dire si un code est authentique, combien de temps il ouvre, et
 * refuser un code deja utilise. Il implemente aussi le verrouillage progressif
 * de la saisie apres des erreurs repetees.
 */

import {
  UnlockProtocolError,
  formatCode,
  lockoutSecondsFor,
  normalizeCode,
  peekCode,
  verifyCode,
  type UnlockPayload,
} from "@koda/shared";

import { storage } from "./storage";

export interface UnlockAttempt {
  ok: boolean;
  payload?: UnlockPayload;
  message?: string;
  lockedUntil?: number;
  failedAttempts?: number;
}

const LOOKAHEAD = 16;

export const lockGuard = {
  /** Duree annoncee par le code, lisible avant meme la verification. */
  preview(code: string): { durationMinutes: number; kind: number } | null {
    try {
      const peeked = peekCode(code);
      return { durationMinutes: peeked.durationMinutes, kind: peeked.kind };
    } catch {
      return null;
    }
  },

  format: formatCode,
  normalize: normalizeCode,

  /**
   * Verifie un code hors ligne.
   *
   * En cas de succes, le compteur local avance : tous les codes anterieurs
   * deviennent inutilisables, y compris ceux notes sur un papier.
   */
  async attempt(options: {
    code: string;
    secretHex: string;
    deviceId: string;
    lastCounter: number;
    revokedFingerprints?: string[];
  }): Promise<UnlockAttempt> {
    const now = Date.now();
    const lockedUntil = await storage.getLockedUntil();
    if (lockedUntil > now) {
      return {
        ok: false,
        lockedUntil,
        message: "Trop d'essais. Patiente avant de reessayer.",
      };
    }

    try {
      const payload = verifyCode({
        code: options.code,
        secretHex: options.secretHex,
        deviceId: options.deviceId,
        lastCounter: options.lastCounter,
        lookahead: LOOKAHEAD,
        nowSeconds: now / 1000,
      });
      await storage.setAcceptedCounter(payload.counter);
      await storage.setFailedAttempts(0);
      await storage.setLockedUntil(0);
      return { ok: true, payload };
    } catch (error) {
      const attempts = (await storage.getFailedAttempts()) + 1;
      await storage.setFailedAttempts(attempts);
      const penalty = lockoutSecondsFor(attempts);
      if (penalty > 0) {
        await storage.setLockedUntil(now + penalty * 1000);
      }
      return {
        ok: false,
        failedAttempts: attempts,
        lockedUntil: penalty > 0 ? now + penalty * 1000 : undefined,
        message:
          error instanceof UnlockProtocolError
            ? error.message
            : "Ce code ne fonctionne pas.",
      };
    }
  },

  async remainingLockSeconds(): Promise<number> {
    const until = await storage.getLockedUntil();
    return Math.max(0, Math.ceil((until - Date.now()) / 1000));
  },
};
