/**
 * Protocole KODA-UNLOCK v1 — portage TypeScript de `app/core/unlock_protocol.py`.
 *
 * Cette implementation permet a la tablette de l'enfant de valider un code
 * **sans reseau**. Elle est verifiee, a chaque build, contre les vecteurs de
 * test produits par l'implementation Python de reference : les deux ne peuvent
 * pas diverger silencieusement.
 *
 * Voir `docs/SECURITE.md` pour la justification du format et de la resistance
 * a la force brute.
 */

import { bytesToHex, constantTimeEquals, hexToBytes, hmacSha256, sha256, utf8Bytes } from "./sha256.js";

export const PROTOCOL_VERSION = "KODA1";
export const CODE_DIGITS = 10;
export const TAG_DIGITS = 7;
export const DURATION_STEP_MINUTES = 5;
export const MAX_DURATION_UNITS = 99;
export const DEFAULT_LOOKAHEAD = 16;
export const DEFAULT_BUCKET_TOLERANCE = 1;

export enum UnlockKind {
  ParentDirect = 0,
  AssessmentReward = 1,
  XpRedeem = 2,
  ParentBonus = 3,
  Emergency = 4,
}

/** Taille de la tranche temporelle, par nature de code (secondes). */
export const BUCKET_SECONDS: Record<UnlockKind, number> = {
  [UnlockKind.ParentDirect]: 1800,
  [UnlockKind.AssessmentReward]: 1800,
  [UnlockKind.XpRedeem]: 1800,
  [UnlockKind.ParentBonus]: 1800,
  [UnlockKind.Emergency]: 43200,
};

export const KIND_LABELS: Record<UnlockKind, string> = {
  [UnlockKind.ParentDirect]: "Deverrouillage parental",
  [UnlockKind.AssessmentReward]: "Evaluation reussie",
  [UnlockKind.XpRedeem]: "Points d'experience",
  [UnlockKind.ParentBonus]: "Bonus parental",
  [UnlockKind.Emergency]: "Deblocage de secours",
};

export class UnlockProtocolError extends Error {
  readonly code: string;

  constructor(message: string, code = "invalid_unlock_code") {
    super(message);
    this.name = "UnlockProtocolError";
    this.code = code;
  }
}

export interface UnlockPayload {
  kind: UnlockKind;
  durationMinutes: number;
  counter: number;
  timeBucket: number;
}

export function normalizeCode(raw: string): string {
  return String(raw ?? "").replace(/\D/g, "");
}

/** Presentation lisible : `123 456 7890`. */
export function formatCode(raw: string): string {
  const digits = normalizeCode(raw);
  if (digits.length !== CODE_DIGITS) return digits;
  return `${digits.slice(0, 3)} ${digits.slice(3, 6)} ${digits.slice(6)}`;
}

export function currentBucket(kind: UnlockKind, nowSeconds: number): number {
  return Math.floor(nowSeconds / BUCKET_SECONDS[kind]);
}

function signingInput(
  deviceId: string,
  counter: number,
  durationUnits: number,
  kind: UnlockKind,
  timeBucket: number,
): Uint8Array {
  return utf8Bytes(
    [PROTOCOL_VERSION, deviceId, String(counter), String(durationUnits), String(kind), String(timeBucket)].join("|"),
  );
}

/** Troncature dynamique facon RFC 4226, ramenee a TAG_DIGITS chiffres. */
function tag(
  secretHex: string,
  deviceId: string,
  counter: number,
  durationUnits: number,
  kind: UnlockKind,
  timeBucket: number,
): string {
  const digest = hmacSha256(hexToBytes(secretHex), signingInput(deviceId, counter, durationUnits, kind, timeBucket));
  const offset = digest[digest.length - 1] & 0x0f;
  const truncated =
    ((digest[offset] & 0x7f) * 0x1000000 +
      digest[offset + 1] * 0x10000 +
      digest[offset + 2] * 0x100 +
      digest[offset + 3]) %
    10 ** TAG_DIGITS;
  return String(truncated).padStart(TAG_DIGITS, "0");
}

export function minutesToUnits(minutes: number): number {
  if (!Number.isFinite(minutes) || minutes <= 0) {
    throw new UnlockProtocolError("La duree doit etre strictement positive.");
  }
  if (minutes % DURATION_STEP_MINUTES !== 0) {
    throw new UnlockProtocolError(`La duree doit etre un multiple de ${DURATION_STEP_MINUTES} minutes.`);
  }
  const units = minutes / DURATION_STEP_MINUTES;
  if (units > MAX_DURATION_UNITS) {
    throw new UnlockProtocolError(`Duree maximale : ${MAX_DURATION_UNITS * DURATION_STEP_MINUTES} minutes.`);
  }
  return units;
}

/**
 * Emet un code. Cote appareil ce n'est utile qu'aux tests : en production,
 * seul le serveur emet (il detient le compteur).
 */
export function issueCode(options: {
  secretHex: string;
  deviceId: string;
  counter: number;
  durationMinutes: number;
  kind?: UnlockKind;
  nowSeconds?: number;
}): string {
  const kind = options.kind ?? UnlockKind.ParentDirect;
  const units = minutesToUnits(options.durationMinutes);
  const bucket = currentBucket(kind, options.nowSeconds ?? Date.now() / 1000);
  return (
    String(units).padStart(2, "0") + String(kind) + tag(options.secretHex, options.deviceId, options.counter, units, kind, bucket)
  );
}

/** Lit la partie en clair (nature, duree) sans verifier la signature. */
export function peekCode(raw: string): { kind: UnlockKind; durationMinutes: number } {
  const digits = normalizeCode(raw);
  if (digits.length !== CODE_DIGITS) {
    throw new UnlockProtocolError(`Un code KODA contient ${CODE_DIGITS} chiffres.`, "malformed");
  }
  const units = Number(digits.slice(0, 2));
  const kind = Number(digits[2]) as UnlockKind;
  if (!(kind in BUCKET_SECONDS)) {
    throw new UnlockProtocolError("Nature de code inconnue.", "malformed");
  }
  if (units === 0) {
    throw new UnlockProtocolError("Duree nulle.", "malformed");
  }
  return { kind, durationMinutes: units * DURATION_STEP_MINUTES };
}

/**
 * Verifie un code hors ligne.
 *
 * L'appelant doit persister `payload.counter` comme nouveau `lastCounter` :
 * c'est ce qui tue definitivement les codes anterieurs.
 */
export function verifyCode(options: {
  code: string;
  secretHex: string;
  deviceId: string;
  lastCounter: number;
  lookahead?: number;
  bucketTolerance?: number;
  nowSeconds?: number;
}): UnlockPayload {
  const digits = normalizeCode(options.code);
  const { kind, durationMinutes } = peekCode(digits);
  const units = durationMinutes / DURATION_STEP_MINUTES;
  const provided = digits.slice(3);
  const lookahead = Math.max(1, options.lookahead ?? DEFAULT_LOOKAHEAD);
  const tolerance = options.bucketTolerance ?? DEFAULT_BUCKET_TOLERANCE;
  const baseBucket = currentBucket(kind, options.nowSeconds ?? Date.now() / 1000);

  for (let counter = options.lastCounter + 1; counter <= options.lastCounter + lookahead; counter += 1) {
    for (let offset = -tolerance; offset <= tolerance; offset += 1) {
      const expected = tag(options.secretHex, options.deviceId, counter, units, kind, baseBucket + offset);
      if (constantTimeEquals(expected, provided)) {
        return { kind, durationMinutes, counter, timeBucket: baseBucket + offset };
      }
    }
  }
  throw new UnlockProtocolError("Code invalide, deja utilise ou expire.");
}

/** Empreinte non reversible, identique cote serveur (journal et revocation). */
export function codeFingerprint(code: string, deviceId: string): string {
  const digits = normalizeCode(code);
  return bytesToHex(sha256(utf8Bytes(`${PROTOCOL_VERSION}|${deviceId}|${digits}`)));
}

/** Verrouillage progressif de la saisie apres des erreurs repetees. */
export const LOCKOUT_LADDER: Array<[number, number]> = [
  [5, 5 * 60],
  [10, 30 * 60],
  [15, 24 * 3600],
];

export function lockoutSecondsFor(failedAttempts: number): number {
  let penalty = 0;
  for (const [threshold, seconds] of LOCKOUT_LADDER) {
    if (failedAttempts >= threshold) penalty = seconds;
  }
  return penalty;
}
