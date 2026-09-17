/**
 * Client HTTP de l'application enfant.
 *
 * Il part du principe inverse d'un client web classique : **le reseau est
 * l'exception**. Chaque appel echoue proprement, les reponses utiles sont mises
 * en cache, et les evenements produits hors ligne sont mis en file pour etre
 * rejoues a la reconnexion.
 */

import type {
  Assessment,
  DeviceCredentials,
  DeviceSyncResponse,
  HeartbeatResponse,
  Submission,
} from "@koda/shared";

import Constants from "expo-constants";

import { storage } from "../lib/storage";

const DEFAULT_URL = "http://localhost:8000/api/v1";

/**
 * Adresse de l'API, par ordre de priorite :
 *
 * 1. `EXPO_PUBLIC_API_URL` si elle est definie (build de production, API
 *    distante) ;
 * 2. en developpement, le serveur Expo qui a servi l'application : il relaie
 *    `/api/*` vers l'API locale (voir `metro.config.js`). Le telephone joint
 *    donc l'API par la meme adresse que le bundle — IP locale en mode LAN,
 *    domaine `exp.direct` en HTTPS en mode tunnel — sans rien configurer ;
 * 3. a defaut, `localhost` (simulateur sur la meme machine).
 */
export function apiUrl(): string {
  const fromEnv = process.env.EXPO_PUBLIC_API_URL;
  if (fromEnv && fromEnv.length > 0) return fromEnv.replace(/\/+$/, "");

  // Sur le web, l'application est servie par le meme serveur que le relais :
  // viser la meme origine supprime tout probleme de CORS.
  if (typeof window !== "undefined" && window.location?.origin) {
    return `${window.location.origin}/api/v1`;
  }

  const hostUri = Constants.expoConfig?.hostUri;
  if (hostUri) {
    const host = hostUri.split("/")[0];
    // Un relais public (tunnel) est expose en HTTPS : sans port, ou sur 443.
    // Le mode reseau local porte le port de Metro (8081) et reste en HTTP.
    const port = host.match(/:(\d+)$/)?.[1];
    const secure = port === undefined || port === "443";
    const authority = port === "443" ? host.replace(/:443$/, "") : host;
    return `${secure ? "https" : "http"}://${authority}/api/v1`;
  }
  return DEFAULT_URL;
}

export class NetworkError extends Error {
  constructor() {
    super("Pas de connexion.");
    this.name = "NetworkError";
  }
}

export class ApiError extends Error {
  readonly code: string;
  readonly status: number;
  readonly details: Record<string, unknown>;

  constructor(status: number, code: string, message: string, details: Record<string, unknown>) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

interface QueuedCall {
  path: string;
  method: string;
  body: unknown;
  at: number;
}

async function call<T>(
  path: string,
  options: { method?: string; body?: unknown; token?: string | null; timeoutMs?: number } = {},
): Promise<T> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), options.timeoutMs ?? 12_000);
  try {
    const response = await fetch(`${apiUrl()}${path}`, {
      method: options.method ?? "GET",
      headers: {
        "Content-Type": "application/json",
        ...(options.token ? { Authorization: `Bearer ${options.token}` } : {}),
      },
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
      signal: controller.signal,
    });

    const text = await response.text();
    const payload = text ? (JSON.parse(text) as unknown) : null;

    if (!response.ok) {
      const error = payload as { error?: { code: string; message: string; details?: Record<string, unknown> } };
      throw new ApiError(
        response.status,
        error?.error?.code ?? "erreur",
        error?.error?.message ?? `Erreur ${response.status}`,
        error?.error?.details ?? {},
      );
    }
    return payload as T;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    throw new NetworkError();
  } finally {
    clearTimeout(timeout);
  }
}

export const api = {
  /** Appairage : echange le code du parent contre les identifiants durables. */
  claim: (payload: {
    pairing_code: string;
    name: string;
    platform: string;
    os_version?: string;
    app_version?: string;
    boot_id?: string;
  }) => call<DeviceCredentials>("/devices/claim", { method: "POST", body: payload }),

  sync: (token: string, payload: { boot_id?: string; device_wall_ms?: number; app_version?: string }) =>
    call<DeviceSyncResponse>("/device/sync", { method: "POST", body: payload, token }),

  redeem: (
    token: string,
    payload: {
      code: string;
      boot_id?: string;
      device_wall_ms?: number;
      consumed_offline_at?: string;
      offline_active_ms?: number;
    },
  ) =>
    call<{
      session_id: string;
      granted_minutes: number;
      granted_ms: number;
      remaining_ms: number;
      started_at: string;
      wall_deadline_at: string;
      truncated_by_cap: boolean;
      warnings: string[];
      heartbeat_interval_seconds: number;
    }>("/unlock/redeem", { method: "POST", body: payload, token }),

  heartbeat: (
    token: string,
    sessionId: string,
    payload: { monotonic_ms: number; device_wall_ms?: number; screen_on: boolean; boot_id?: string },
  ) =>
    call<HeartbeatResponse>(`/screen/sessions/${sessionId}/heartbeat`, {
      method: "POST",
      body: payload,
      token,
    }),

  endSession: (token: string, sessionId: string) =>
    call<unknown>(`/screen/sessions/${sessionId}/end`, { method: "POST", token }),

  eligibility: (token: string, kind = "unlock") =>
    call<{
      allowed: boolean;
      reason: string | null;
      details: Record<string, unknown>;
      attempts_today: number;
      max_attempts_per_day: number;
    }>(`/assessments/eligibility?kind=${kind}`, { token }),

  startAssessment: (token: string, kind: string, questionCount?: number) =>
    call<Assessment>("/assessments", {
      method: "POST",
      body: { kind, question_count: questionCount },
      token,
    }),

  currentAssessment: (token: string) => call<Assessment | null>("/assessments/current", { token }),

  saveAnswer: (
    token: string,
    assessmentId: string,
    itemId: string,
    payload: {
      answer?: Record<string, unknown> | null;
      answer_mode?: string;
      strokes?: Record<string, unknown> | null;
      time_spent_ms?: number;
    },
  ) =>
    call<void>(`/assessments/${assessmentId}/items/${itemId}`, {
      method: "PATCH",
      body: payload,
      token,
    }),

  submit: (
    token: string,
    assessmentId: string,
    payload: { answers?: Record<string, unknown>; integrity?: Record<string, unknown> },
  ) => call<Submission>(`/assessments/${assessmentId}/submit`, { method: "POST", body: payload, token }),

  review: (token: string, assessmentId: string) =>
    call<Submission>(`/assessments/${assessmentId}/review`, { token }),

  redeemXp: (token: string, payload: { child_id: string; xp_to_spend?: number }) =>
    call<{ session_id: string; granted_minutes: number; granted_ms: number; remaining_ms: number; started_at: string; wall_deadline_at: string; truncated_by_cap: boolean; warnings: string[]; heartbeat_interval_seconds: number }>(
      "/unlock/xp/redeem",
      { method: "POST", body: payload, token },
    ),
};

/** File d'attente des appels produits hors ligne. */
export const queue = {
  async push(entry: Omit<QueuedCall, "at">): Promise<void> {
    const current = (await storage.readCache<QueuedCall[]>("queue")) ?? [];
    current.push({ ...entry, at: Date.now() });
    await storage.cache("queue", current.slice(-100));
  },

  async flush(token: string): Promise<number> {
    const current = (await storage.readCache<QueuedCall[]>("queue")) ?? [];
    if (current.length === 0) return 0;
    const remaining: QueuedCall[] = [];
    let sent = 0;
    for (const entry of current) {
      try {
        await call(entry.path, { method: entry.method, body: entry.body, token });
        sent += 1;
      } catch (error) {
        if (error instanceof NetworkError) {
          remaining.push(entry); // on retentera plus tard
        }
        // Une erreur metier (code deja consomme...) ne doit pas boucler indefiniment.
      }
    }
    await storage.cache("queue", remaining);
    return sent;
  },

  async size(): Promise<number> {
    return ((await storage.readCache<QueuedCall[]>("queue")) ?? []).length;
  },
};
