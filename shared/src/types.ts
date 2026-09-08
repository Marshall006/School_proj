/**
 * Types partages entre l'API, le tableau de bord parent et l'application enfant.
 *
 * Ils suivent exactement les schemas Pydantic de `backend/app/schemas`. Toute
 * divergence se voit a la compilation des deux clients.
 */

export type PeriodType = "school" | "weekend" | "holiday";
export type ScreenState = "locked" | "unlocked" | "paused";
export type AssessmentKind = "unlock" | "practice" | "parent_assigned" | "placement";
export type AssessmentStatus =
  | "in_progress"
  | "submitted"
  | "graded"
  | "needs_review"
  | "expired"
  | "abandoned";
export type AnswerMode = "assisted" | "handwritten" | "voice";
export type QuestionType =
  | "mcq_single"
  | "mcq_multi"
  | "true_false"
  | "numeric"
  | "short_text"
  | "fill_blank"
  | "ordering"
  | "matching"
  | "expression"
  | "handwritten"
  | "voice";

export interface ApiError {
  error: { code: string; message: string; details: Record<string, unknown> };
}

export interface Parent {
  id: string;
  family_id: string;
  email: string;
  display_name: string;
  phone: string | null;
  role: "owner" | "guardian" | "viewer";
}

export interface Family {
  id: string;
  name: string;
  country_code: string;
  timezone: string;
  locale: string;
}

export interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

export interface Session {
  parent: Parent;
  family: Family;
  tokens: TokenPair;
}

export interface Child {
  id: string;
  family_id: string;
  display_name: string;
  grade_code: string;
  country_code: string;
  avatar: string;
  birth_date: string | null;
  xp_balance: number;
  xp_lifetime: number;
  streak_days: number;
  is_active: boolean;
  created_at: string;
}

export interface EffectivePolicy {
  period_type: PeriodType;
  source: "child" | "family" | "default";
  pass_score_pct: number;
  pass_score_out_of_20: number;
  question_count: number;
  time_limit_minutes: number;
  reward_minutes: number;
  daily_cap_minutes: number;
  max_attempts_per_day: number;
  allow_parent_direct_unlock: boolean;
  allow_assessment_unlock: boolean;
  cooldown_minutes: number;
  minutes_per_100_xp: number;
  xp_daily_bonus_cap_minutes: number;
  curfew_start: string | null;
  curfew_end: string | null;
  subject_codes: string[];
  timezone: string;
}

export interface Lockout {
  id: string;
  reason: string;
  until: string;
  remaining_seconds: number;
  remaining_minutes: number;
  message: string | null;
  review_topics: Array<Record<string, unknown>>;
}

export interface DeviceCredentials {
  device_id: string;
  child_id: string;
  device_token: string;
  device_secret: string;
  accepted_counter: number;
  protocol: string;
  server_time: string;
}

export interface DeviceSummary {
  id: string;
  child_id: string;
  name: string;
  platform: string;
  status: "pending" | "active" | "revoked" | "lost";
  last_seen_at: string | null;
  clock_skew_ms: number;
  tamper_score: number;
  failed_code_attempts: number;
  code_locked_until: string | null;
}

export interface InputSpec {
  keypad?: "numeric" | "decimal" | "math" | "fraction" | "text" | "none";
  widget?: "long_division" | "column_operation" | "fraction_builder" | "drag_drop" | "canvas";
  template?: string;
  palette?: string[];
  allow_handwriting?: boolean;
}

export interface AssessmentItem {
  id: string;
  position: number;
  type: QuestionType;
  difficulty: number;
  prompt: string;
  instructions: string | null;
  choices: Array<{ id: string; text?: string; items?: string[] }> | null;
  assets: unknown[];
  input_spec: InputSpec;
  points_max: number;
  estimated_seconds: number;
  subject_code: string | null;
  answered: boolean;
  answer: Record<string, unknown> | null;
  answer_mode: AnswerMode | null;
}

export interface Assessment {
  id: string;
  child_id: string;
  kind: AssessmentKind;
  status: AssessmentStatus;
  question_count: number;
  points_max: number;
  pass_score_pct: number;
  pass_score_out_of_20: number;
  started_at: string | null;
  expires_at: string | null;
  time_limit_seconds: number | null;
  items: AssessmentItem[];
  blueprint_distribution: Record<string, number>;
}

export interface ReviewItem {
  position: number;
  subject_code: string | null;
  bucket: string | null;
  prompt: string | null;
  choices: Array<{ id: string; text?: string }> | null;
  type: QuestionType;
  difficulty: number;
  your_answer: unknown;
  expected: unknown;
  is_correct: boolean | null;
  score: number;
  points: string;
  explanation: string | null;
  diagnosis: string | null;
  detail: string | null;
  per_part: Array<Record<string, unknown>>;
  needs_manual_review: boolean;
  time_spent_ms: number;
}

export interface IssuedCode {
  id: string;
  code: string;
  formatted: string;
  kind: string;
  duration_minutes: number;
  expires_at: string;
}

export interface Submission {
  assessment_id: string;
  status: AssessmentStatus;
  passed: boolean;
  pending_manual_review: boolean;
  score_pct: number;
  score_out_of_20: number;
  pass_score_pct: number;
  pass_score_out_of_20: number;
  points_earned: number;
  points_max: number;
  unlock_code: IssuedCode | null;
  lockout: Lockout | null;
  xp_earned: number;
  xp_detail: Array<{ amount: number; reason: string; label: string }>;
  review: ReviewItem[];
  weak_topics: Array<{ topic_id: string; subject_code: string; missed: number; sample_prompt?: string }>;
  mastery_moves: Array<{ topic_id: string; subject_code: string; from: string; to: string }>;
}

export interface ScreenSession {
  id: string;
  child_id: string;
  device_id: string;
  state: "active" | "paused" | "ended" | "expired" | "revoked";
  granted_ms: number;
  bonus_ms: number;
  consumed_ms: number;
  offline_ms: number;
  started_at: string;
  wall_deadline_at: string;
  ended_at: string | null;
  end_reason: string | null;
  anomaly_count: number;
  integrity_score: number;
}

export interface HeartbeatResponse {
  session_id: string;
  state: string;
  remaining_ms: number;
  remaining_minutes: number;
  consumed_ms: number;
  granted_ms: number;
  should_lock: boolean;
  anomalies: string[];
  server_time: string;
  wall_deadline_at: string;
}

export interface DeviceSyncResponse {
  server_time: string;
  clock_skew_ms: number;
  clock_trustworthy: boolean;
  child: {
    id: string;
    display_name: string;
    grade_code: string;
    country_code: string;
    avatar: string;
    xp_balance: number;
    streak_days: number;
  };
  policy: EffectivePolicy;
  lockout: Lockout | null;
  active_session: {
    id: string;
    state: string;
    remaining_ms: number;
    granted_ms: number;
    consumed_ms: number;
    started_at: string;
    wall_deadline_at: string;
  } | null;
  revoked_code_fingerprints: string[];
  accepted_counter: number;
  lookahead_window: number;
  heartbeat_interval_seconds: number;
  should_lock: boolean;
  messages: string[];
}

export interface SubjectPerformance {
  subject_code: string;
  subject_name: string;
  answered: number;
  correct: number;
  success_rate: number | null;
  avg_score: number;
  avg_seconds: number;
}

export interface MasteryGap {
  topic_id: string;
  topic_name: string;
  subject_code: string;
  band: string;
  ewma: number;
  success_rate: number | null;
  attempts: number;
  urgency: number;
  due: boolean;
}

export interface Dashboard {
  status: {
    child_id: string;
    display_name: string;
    grade_code: string;
    xp_balance: number;
    streak_days: number;
    screen_state: ScreenState;
    session: {
      id: string;
      state: string;
      remaining_ms: number;
      remaining_minutes: number;
      granted_minutes: number;
      started_at: string;
      wall_deadline_at: string;
      integrity_score: number;
      anomaly_count: number;
    } | null;
    lockout: Lockout | null;
    screen_time_today: { granted_minutes: number; cap_minutes: number; remaining_minutes: number };
    pending_codes: number;
    period_type: PeriodType;
    unlock_paths: { parent_direct: boolean; assessment: boolean };
  };
  subjects: SubjectPerformance[];
  mastery: { topics_tracked: number; bands: Record<string, number>; gaps: MasteryGap[]; due_for_review: number };
  recent_assessments: Array<{
    id: string;
    kind: string;
    status: string;
    score_out_of_20: number | null;
    passed: boolean | null;
    question_count: number;
    reward_minutes: number;
    xp_earned: number;
    duration_seconds: number | null;
    created_at: string;
  }>;
  screen_time_trend: Array<{ date: string; granted_minutes: number; consumed_minutes: number; sessions: number }>;
  alerts: Array<{ severity: "info" | "warning" | "critical"; type: string; message: string; at: string }>;
  xp_timeline: Array<{ delta: number; reason: string; label: string | null; balance_after: number; at: string }>;
  totals: {
    assessments_graded: number;
    assessments_passed: number;
    pass_rate: number | null;
    xp_lifetime: number;
  };
  generated_at: string;
}
