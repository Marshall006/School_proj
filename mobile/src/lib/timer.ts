/**
 * Minuteur local.
 *
 * Il s'appuie sur une horloge **monotone** : `Date.now()` peut etre manipule
 * en changeant l'heure de la tablette, alors que le temps ecoule depuis le
 * demarrage de l'application ne peut pas reculer. Le serveur recoit cette
 * mesure et non l'heure murale.
 *
 * Quand l'ecran s'eteint (application en arriere-plan), le minuteur se met en
 * pause : c'est la regle du produit, et c'est ici qu'elle est appliquee.
 */

export interface TimerSnapshot {
  activeMs: number;
  remainingMs: number;
  running: boolean;
}

export class ScreenTimer {
  private grantedMs: number;
  private consumedMs: number;
  private startedAt: number | null = null;
  private baseMs = 0;

  constructor(grantedMs: number, alreadyConsumedMs = 0) {
    this.grantedMs = grantedMs;
    this.consumedMs = alreadyConsumedMs;
    this.baseMs = alreadyConsumedMs;
  }

  /** Millisecondes ecoulees depuis le lancement de l'application. */
  private static monotonic(): number {
    if (typeof performance !== "undefined" && typeof performance.now === "function") {
      return performance.now();
    }
    return Date.now();
  }

  start(): void {
    if (this.startedAt === null) {
      this.startedAt = ScreenTimer.monotonic();
    }
  }

  /** Ecran eteint ou application en arriere-plan : on fige le decompte. */
  pause(): void {
    if (this.startedAt !== null) {
      this.consumedMs += ScreenTimer.monotonic() - this.startedAt;
      this.startedAt = null;
    }
  }

  get activeMs(): number {
    const live = this.startedAt === null ? 0 : ScreenTimer.monotonic() - this.startedAt;
    return Math.round(this.consumedMs + live);
  }

  /** Valeur transmise au serveur : temps monotone consomme depuis le debut. */
  get monotonicMs(): number {
    return this.activeMs;
  }

  get remainingMs(): number {
    return Math.max(0, this.grantedMs - this.activeMs);
  }

  get expired(): boolean {
    return this.remainingMs <= 0;
  }

  extend(extraMs: number): void {
    this.grantedMs += extraMs;
  }

  /** Recalage sur la verite du serveur, sans jamais rendre du temps deja consomme. */
  reconcile(serverConsumedMs: number, serverGrantedMs: number): void {
    this.grantedMs = serverGrantedMs;
    if (serverConsumedMs > this.activeMs) {
      const delta = serverConsumedMs - this.activeMs;
      this.consumedMs += delta;
      this.baseMs += delta;
    }
  }

  snapshot(): TimerSnapshot {
    return {
      activeMs: this.activeMs,
      remainingMs: this.remainingMs,
      running: this.startedAt !== null,
    };
  }
}

export function formatRemaining(ms: number): string {
  const total = Math.max(0, Math.floor(ms / 1000));
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const seconds = total % 60;
  if (hours > 0) return `${hours} h ${String(minutes).padStart(2, "0")}`;
  return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
}
