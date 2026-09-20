/**
 * Client HTTP du tableau de bord.
 *
 * Trois responsabilites : porter le jeton, rafraichir la session quand il
 * expiré, et transformer les erreurs de l'API en objets exploitables par
 * l'interface (le message est déjà redige en français cote serveur).
 */

import type {
  Assessment,
  Child,
  Dashboard,
  DeviceSummary,
  EffectivePolicy,
  Lockout,
  ScreenSession,
  Session,
  Submission,
} from "@koda/shared";

export const API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

const ACCESS_KEY = "koda.access";
const REFRESH_KEY = "koda.refresh";

export class ApiError extends Error {
  readonly code: string;
  readonly status: number;
  readonly details: Record<string, unknown>;

  constructor(status: number, code: string, message: string, details: Record<string, unknown> = {}) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

export const tokens = {
  get access(): string | null {
    if (typeof window === "undefined") return null;
    return window.localStorage.getItem(ACCESS_KEY);
  },
  get refresh(): string | null {
    if (typeof window === "undefined") return null;
    return window.localStorage.getItem(REFRESH_KEY);
  },
  set(access: string, refresh: string) {
    window.localStorage.setItem(ACCESS_KEY, access);
    window.localStorage.setItem(REFRESH_KEY, refresh);
  },
  clear() {
    window.localStorage.removeItem(ACCESS_KEY);
    window.localStorage.removeItem(REFRESH_KEY);
  },
};

async function parse(response: Response): Promise<unknown> {
  if (response.status === 204) return null;
  const text = await response.text();
  if (!text) return null;
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

async function refreshSession(): Promise<boolean> {
  const refresh = tokens.refresh;
  if (!refresh) return false;
  const response = await fetch(`${API_URL}/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: refresh }),
  });
  if (!response.ok) {
    tokens.clear();
    return false;
  }
  const body = (await response.json()) as { access_token: string; refresh_token: string };
  tokens.set(body.access_token, body.refresh_token);
  return true;
}

async function request<T>(
  path: string,
  options: RequestInit & { retry?: boolean } = {},
): Promise<T> {
  const { retry = true, ...init } = options;
  const headers = new Headers(init.headers);
  headers.set("Content-Type", "application/json");
  const access = tokens.access;
  if (access) headers.set("Authorization", `Bearer ${access}`);

  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, { ...init, headers });
  } catch {
    throw new ApiError(0, "network_error", "Le serveur est injoignable. Vérifie que l'API tourne.");
  }

  if (response.status === 401 && retry && tokens.refresh) {
    if (await refreshSession()) {
      return request<T>(path, { ...options, retry: false });
    }
  }

  const body = await parse(response);
  if (!response.ok) {
    const payload = body as { error?: { code: string; message: string; details?: Record<string, unknown> } };
    throw new ApiError(
      response.status,
      payload?.error?.code ?? "erreur",
      payload?.error?.message ?? `Erreur ${response.status}`,
      payload?.error?.details ?? {},
    );
  }
  return body as T;
}

const get = <T,>(path: string) => request<T>(path);
const post = <T,>(path: string, body?: unknown) =>
  request<T>(path, { method: "POST", body: body === undefined ? undefined : JSON.stringify(body) });
const put = <T,>(path: string, body?: unknown) =>
  request<T>(path, { method: "PUT", body: JSON.stringify(body) });
const patch = <T,>(path: string, body?: unknown) =>
  request<T>(path, { method: "PATCH", body: JSON.stringify(body) });
const del = <T,>(path: string) => request<T>(path, { method: "DELETE" });

// --- Types locaux ----------------------------------------------------------

export interface PolicyProfile {
  id: string;
  family_id: string;
  child_id: string | null;
  period_type: "school" | "weekend" | "holiday";
  name: string;
  is_active: boolean;
  pass_score_pct: number;
  question_count: number;
  time_limit_minutes: number;
  difficulty_bias: number;
  reward_minutes: number;
  daily_cap_minutes: number;
  max_attempts_per_day: number;
  allow_parent_direct_unlock: boolean;
  allow_assessment_unlock: boolean;
  cooldown_minutes: number;
  cooldown_escalation: number;
  review_required_before_retry: boolean;
  minutes_per_100_xp: number;
  xp_daily_bonus_cap_minutes: number;
  practice_xp_multiplier: number;
  curfew_start: string | null;
  curfew_end: string | null;
  subject_codes: string[];
}

export interface CalendarPeriod {
  id: string;
  label: string;
  period_type: "school" | "weekend" | "holiday";
  start_date: string;
  end_date: string;
}

export interface IssuedCodeResponse {
  id: string;
  code: string;
  formatted: string;
  kind: string;
  duration_minutes: number;
  expires_at: string;
  device_id: string;
  child_id: string;
}

export interface UnlockCodeRecord {
  id: string;
  child_id: string;
  device_id: string;
  kind: string;
  status: "issued" | "consumed" | "expired" | "revoked";
  duration_minutes: number;
  expires_at: string;
  consumed_at: string | null;
  consumed_offline: boolean;
  note: string | null;
  created_at: string;
}

export interface AssessmentSummary {
  id: string;
  child_id: string;
  kind: string;
  status: string;
  score_pct: number | null;
  score_out_of_20: number | null;
  passed: boolean | null;
  question_count: number;
  reward_minutes: number;
  xp_earned: number;
  duration_seconds: number | null;
  created_at: string;
  submitted_at: string | null;
}

export interface ParentAssessmentView {
  assessment: {
    id: string;
    kind: string;
    status: string;
    score_out_of_20: number | null;
    passed: boolean | null;
    points_earned: number;
    points_max: number;
    pass_score_out_of_20: number;
    duration_seconds: number | null;
    created_at: string;
    blueprint: Record<string, unknown>;
    integrity: Record<string, unknown>;
  };
  items: Array<{
    id: string;
    position: number;
    prompt: string | null;
    type: string;
    subject_code: string | null;
    answer: Record<string, unknown> | null;
    answer_mode: string | null;
    strokes: { paths?: number[][][]; width?: number; height?: number } | null;
    is_correct: boolean | null;
    score: number;
    points: string;
    feedback: Record<string, unknown>;
    needs_manual_review: boolean;
    parent_comment: string | null;
    time_spent_ms: number;
  }>;
}

// --- Surface publique ------------------------------------------------------

export const api = {
  auth: {
    login: (email: string, password: string) =>
      post<Session>("/auth/login", { email, password }),
    register: (payload: {
      email: string;
      password: string;
      display_name: string;
      family_name: string;
      country_code?: string;
      phone?: string;
    }) => post<Session>("/auth/register", payload),
    me: () => get<Session>("/auth/me"),
    logout: () => post<void>("/auth/logout", { refresh_token: tokens.refresh ?? "" }),
  },
  children: {
    list: () => get<Child[]>("/children"),
    get: (id: string) => get<Child>(`/children/${id}`),
    create: (payload: { display_name: string; grade_code: string; country_code?: string; pin?: string }) =>
      post<Child>("/children", payload),
    update: (id: string, payload: Record<string, unknown>) => patch<Child>(`/children/${id}`, payload),
    dashboard: (id: string) => get<Dashboard>(`/children/${id}/dashboard`),
    status: (id: string) => get<Dashboard["status"]>(`/children/${id}/status`),
    policy: (id: string) => get<EffectivePolicy>(`/children/${id}/policy`),
    lockout: (id: string) => get<Lockout | null>(`/children/${id}/lockout`),
    releaseLockout: (id: string) => post<{ released: boolean }>(`/children/${id}/lockout/release`),
    assessments: (id: string) => get<AssessmentSummary[]>(`/children/${id}/assessments`),
    sessions: (id: string) => get<ScreenSession[]>(`/children/${id}/screen-sessions`),
    assign: (id: string, payload: { kind: string; question_count?: number }) =>
      post<Assessment>(`/parent/children/${id}/assessments`, payload),
  },
  policies: {
    list: () => get<PolicyProfile[]>("/policies"),
    upsert: (payload: Record<string, unknown>) => put<PolicyProfile>("/policies", payload),
    remove: (id: string) => del<void>(`/policies/${id}`),
  },
  calendar: {
    list: () => get<CalendarPeriod[]>("/calendar"),
    add: (payload: { label: string; period_type: string; start_date: string; end_date: string }) =>
      post<CalendarPeriod>("/calendar", payload),
    remove: (id: string) => del<void>(`/calendar/${id}`),
  },
  devices: {
    list: () => get<DeviceSummary[]>("/devices"),
    pairingCode: (payload: { child_id: string; suggested_name?: string; ttl_minutes?: number }) =>
      post<{ code: string; expires_at: string; child_id: string; instructions: string }>(
        "/devices/pairing-code",
        payload,
      ),
    revoke: (id: string) => post<DeviceSummary>(`/devices/${id}/revoke`),
    resetAttempts: (id: string) => post<DeviceSummary>(`/devices/${id}/unlock-attempts/reset`),
  },
  unlock: {
    parentCode: (payload: { child_id: string; device_id?: string; duration_minutes: number; note?: string }) =>
      post<IssuedCodeResponse>("/unlock/parent-code", payload),
    bonusCode: (payload: { child_id: string; device_id?: string; duration_minutes: number; note?: string }) =>
      post<IssuedCodeResponse>("/unlock/bonus-code", payload),
    codes: (childId: string) => get<UnlockCodeRecord[]>(`/unlock/codes?child_id=${childId}`),
    revoke: (id: string) => post<UnlockCodeRecord>(`/unlock/codes/${id}/revoke`),
    xpQuote: (payload: { child_id: string; xp_to_spend?: number }) =>
      post<{
        minutes: number;
        xp_spent: number;
        xp_remaining: number;
        capped_by_daily_limit: boolean;
        reason: string | null;
        minutes_per_100_xp: number;
      }>("/unlock/xp/quote", payload),
  },
  screen: {
    extend: (sessionId: string, minutes: number, reason?: string) =>
      post<ScreenSession>(`/screen/sessions/${sessionId}/extend`, { minutes, reason }),
    stop: (sessionId: string) => post<ScreenSession>(`/screen/sessions/${sessionId}/stop`),
    events: (sessionId: string) =>
      get<{
        session_id: string;
        state: string;
        integrity_score: number;
        events: Array<{
          type: string;
          at: string;
          delta_ms: number;
          skew_ms: number;
          screen_on: boolean;
          meta: Record<string, unknown>;
        }>;
      }>(`/screen/sessions/${sessionId}/events`),
  },
  assessments: {
    pendingReview: () => get<AssessmentSummary[]>("/parent/assessments/pending-review"),
    view: (id: string) => get<ParentAssessmentView>(`/parent/assessments/${id}`),
    grade: (assessmentId: string, itemId: string, score: number, comment?: string) =>
      post<Submission | null>(`/parent/assessments/${assessmentId}/items/${itemId}/grade`, {
        score,
        comment,
      }),
  },
  catalog: {
    countries: () =>
      get<Array<{ code: string; name: string; currency: string; capital: string; grades: Array<{ code: string; name: string; cycle: string; age: number }> }>>(
        "/catalog/countries",
      ),
    subjects: () => get<Array<{ id: string; code: string; name: string; color: string; icon: string }>>("/catalog/subjects"),
    coverage: () =>
      get<{ total_questions: number; total_topics: number; total_subjects: number; coverage: Array<{ country_code: string; grade_code: string; questions: number }> }>(
        "/catalog/coverage",
      ),
  },
  family: {
    overview: () =>
      get<{ children_count: number; active_sessions: number; open_lockouts: number; total_xp: number }>(
        "/family/overview",
      ),
    audit: (verify = false) =>
      get<{ events: number; integrity?: { valid: boolean; checked: number; reason?: string } }>(
        `/family/audit${verify ? "?verify=true" : ""}`,
      ),
  },
};
