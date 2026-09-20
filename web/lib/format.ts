/** Mise en forme francaise : durées, dates, scores. */

export function minutes(total: number): string {
  if (total <= 0) return "0 min";
  const hours = Math.floor(total / 60);
  const rest = total % 60;
  if (hours === 0) return `${rest} min`;
  if (rest === 0) return `${hours} h`;
  return `${hours} h ${String(rest).padStart(2, "0")}`;
}

export function msToMinutes(ms: number): string {
  return minutes(Math.round(ms / 60000));
}

export function countdown(seconds: number): string {
  if (seconds <= 0) return "terminé";
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  if (h > 0) return `${h} h ${String(m).padStart(2, "0")}`;
  if (m > 0) return `${m} min ${String(s).padStart(2, "0")}`;
  return `${s} s`;
}

export function score20(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  return `${value.toFixed(1).replace(".", ",")}/20`;
}

export function percent(value: number | null | undefined, digits = 0): string {
  if (value === null || value === undefined) return "—";
  return `${(value * 100).toFixed(digits).replace(".", ",")} %`;
}

const DATE_FMT = new Intl.DateTimeFormat("fr-FR", { day: "numeric", month: "short" });
const DATETIME_FMT = new Intl.DateTimeFormat("fr-FR", {
  day: "numeric",
  month: "short",
  hour: "2-digit",
  minute: "2-digit",
});
const TIME_FMT = new Intl.DateTimeFormat("fr-FR", { hour: "2-digit", minute: "2-digit" });

export const formatDate = (iso: string) => DATE_FMT.format(new Date(iso));
export const formatDateTime = (iso: string) => DATETIME_FMT.format(new Date(iso));
export const formatTime = (iso: string) => TIME_FMT.format(new Date(iso));

export function relative(iso: string): string {
  const delta = Date.now() - new Date(iso).getTime();
  const minutesAgo = Math.round(delta / 60000);
  if (minutesAgo < 1) return "a l'instant";
  if (minutesAgo < 60) return `il y a ${minutesAgo} min`;
  const hoursAgo = Math.round(minutesAgo / 60);
  if (hoursAgo < 24) return `il y a ${hoursAgo} h`;
  const daysAgo = Math.round(hoursAgo / 24);
  if (daysAgo === 1) return "hier";
  if (daysAgo < 30) return `il y a ${daysAgo} jours`;
  return formatDate(iso);
}

export const PERIOD_LABELS: Record<string, string> = {
  school: "Période scolaire",
  weekend: "Week-end",
  holiday: "Vacances",
};

export const BAND_LABELS: Record<string, string> = {
  unknown: "A découvrir",
  fragile: "Fragile",
  en_cours: "En cours",
  acquis: "Acquis",
  expert: "Expert",
};

export const KIND_LABELS: Record<string, string> = {
  parent_direct: "Déverrouillage parental",
  assessment_reward: "Évaluation réussie",
  xp_redeem: "Conversion d'XP",
  parent_bonus: "Bonus parental",
  emergency: "Deblocage de secours",
};

export const LOCKOUT_LABELS: Record<string, string> = {
  failed_assessment: "Évaluation échouée",
  too_many_attempts: "Trop de tentatives",
  daily_cap: "Plafond quotidien",
  curfew: "Couvre-feu",
  parent_manual: "Decision parentale",
  tamper_detected: "Anomalie détectée",
  code_bruteforce: "Codes erronés repetes",
};

export const AVATARS: Record<string, string> = {
  fox: "🦊",
  owl: "🦉",
  cat: "🐱",
  panda: "🐼",
  robot: "🤖",
  rocket: "🚀",
  dolphin: "🐬",
  lion: "🦁",
};
