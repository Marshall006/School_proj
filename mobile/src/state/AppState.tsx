/**
 * État central de l'application enfant.
 *
 * Trois responsabilites :
 *
 * 1. **Le verrou.** Savoir si la tablette est ouverte ou fermee, y compris
 *    sans reseau. La verite locale prime : si le minuteur local est a zero, on
 *    verrouillé, même si le serveur est injoignable.
 * 2. **Le minuteur.** Compter le temps écran à l'aide d'une horloge monotone,
 *    se figer quand l'application passe en arriere-plan, et se resynchroniser
 *    avec le serveur des que possible.
 * 3. **La synchronisation.** Recuperer les règles et la carence, rejouer la
 *    file d'attente hors ligne, signaler les codes revoques.
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { AppState as RNAppState, type AppStateStatus } from "react-native";
import type { DeviceSyncResponse, EffectivePolicy, Lockout } from "@koda/shared";

import { ApiError, NetworkError, api, queue } from "../api/client";
import { lockGuard } from "../lib/lockGuard";
import { ScreenTimer } from "../lib/timer";
import { storage, type DeviceIdentity } from "../lib/storage";

export type Phase = "loading" | "pairing" | "locked" | "unlocked";

export interface ChildProfile {
  id: string;
  display_name: string;
  grade_code: string;
  country_code: string;
  avatar: string;
  xp_balance: number;
  streak_days: number;
}

interface SessionState {
  id: string | null;
  grantedMs: number;
  startedAt: string;
  offline: boolean;
}

interface AppValue {
  phase: Phase;
  identity: DeviceIdentity | null;
  child: ChildProfile | null;
  policy: EffectivePolicy | null;
  lockout: Lockout | null;
  online: boolean;
  remainingMs: number;
  session: SessionState | null;
  pendingSync: number;
  messages: string[];
  pair: (code: string, deviceName: string) => Promise<void>;
  redeemXp: (xpToSpend?: number) => Promise<{ granted_minutes: number }>;
  submitCode: (code: string) => Promise<{ ok: boolean; message?: string; minutes?: number }>;
  sync: () => Promise<void>;
  lockNow: () => Promise<void>;
  reset: () => Promise<void>;
}

const AppContext = createContext<AppValue | null>(null);

const HEARTBEAT_MS = 30_000;
const BOOT_ID = `boot-${Date.now().toString(36)}`;

export function AppProvider({ children }: { children: ReactNode }) {
  const [phase, setPhase] = useState<Phase>("loading");
  const [identity, setIdentity] = useState<DeviceIdentity | null>(null);
  const [child, setChild] = useState<ChildProfile | null>(null);
  const [policy, setPolicy] = useState<EffectivePolicy | null>(null);
  const [lockout, setLockout] = useState<Lockout | null>(null);
  const [online, setOnline] = useState(true);
  const [session, setSession] = useState<SessionState | null>(null);
  const [remainingMs, setRemainingMs] = useState(0);
  const [pendingSync, setPendingSync] = useState(0);
  const [messages, setMessages] = useState<string[]>([]);

  const timerRef = useRef<ScreenTimer | null>(null);
  const identityRef = useRef<DeviceIdentity | null>(null);
  const sessionRef = useRef<SessionState | null>(null);

  identityRef.current = identity;
  sessionRef.current = session;

  // --- Demarrage -----------------------------------------------------------
  useEffect(() => {
    void (async () => {
      const stored = await storage.loadIdentity();
      if (!stored) {
        setPhase("pairing");
        return;
      }
      setIdentity(stored);
      setChild(await storage.readCache<ChildProfile>("child"));
      setPolicy(await storage.readCache<EffectivePolicy>("policy"));
      setPhase("locked");
      void syncWith(stored);
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // --- Synchronisation -----------------------------------------------------
  const syncWith = useCallback(async (id: DeviceIdentity) => {
    try {
      const response: DeviceSyncResponse = await api.sync(id.deviceToken, {
        boot_id: BOOT_ID,
        device_wall_ms: Date.now(),
      });
      setOnline(true);
      setChild(response.child);
      setPolicy(response.policy);
      setLockout(response.lockout);
      setMessages(response.messages);
      await storage.cache("child", response.child);
      await storage.cache("policy", response.policy);
      await storage.cache("revoked", response.revoked_code_fingerprints);
      if (response.accepted_counter !== id.acceptedCounter) {
        await storage.setAcceptedCounter(response.accepted_counter);
        setIdentity({ ...id, acceptedCounter: response.accepted_counter });
      }

      if (response.active_session) {
        const active = response.active_session;
        const timer = new ScreenTimer(active.granted_ms, active.consumed_ms);
        timer.start();
        timerRef.current = timer;
        setSession({
          id: active.id,
          grantedMs: active.granted_ms,
          startedAt: active.started_at,
          offline: false,
        });
        setRemainingMs(timer.remainingMs);
        setPhase("unlocked");
      } else if (!sessionRef.current?.offline) {
        timerRef.current = null;
        setSession(null);
        setRemainingMs(0);
        setPhase("locked");
      }

      setPendingSync(await queue.size());
      const flushed = await queue.flush(id.deviceToken);
      if (flushed > 0) setPendingSync(await queue.size());
    } catch (error) {
      if (error instanceof NetworkError) {
        setOnline(false);
      } else if (error instanceof ApiError && error.code === "device_revoked") {
        await storage.clearIdentity();
        setIdentity(null);
        setPhase("pairing");
      }
    }
  }, []);

  const sync = useCallback(async () => {
    if (identityRef.current) await syncWith(identityRef.current);
  }, [syncWith]);

  // --- Minuteur ------------------------------------------------------------
  useEffect(() => {
    if (phase !== "unlocked") return;
    const tick = setInterval(() => {
      const timer = timerRef.current;
      if (!timer) return;
      setRemainingMs(timer.remainingMs);
      if (timer.expired) void lockNow();
    }, 1000);
    return () => clearInterval(tick);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [phase]);

  // --- Battement de coeur --------------------------------------------------
  useEffect(() => {
    if (phase !== "unlocked") return;
    const beat = setInterval(() => {
      void sendHeartbeat(true);
    }, HEARTBEAT_MS);
    return () => clearInterval(beat);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [phase]);

  const sendHeartbeat = useCallback(
    async (screenOn: boolean) => {
      const id = identityRef.current;
      const current = sessionRef.current;
      const timer = timerRef.current;
      if (!id || !timer) return;
      if (!current?.id) return; // session ouverte hors ligne : rien a signaler encore

      const payload = {
        monotonic_ms: timer.monotonicMs,
        device_wall_ms: Date.now(),
        screen_on: screenOn,
        boot_id: BOOT_ID,
      };
      try {
        const result = await api.heartbeat(id.deviceToken, current.id, payload);
        setOnline(true);
        timer.reconcile(result.consumed_ms, result.granted_ms);
        setRemainingMs(timer.remainingMs);
        if (result.should_lock) void lockNow();
      } catch (error) {
        if (error instanceof NetworkError) {
          setOnline(false);
          await queue.push({
            path: `/screen/sessions/${current.id}/heartbeat`,
            method: "POST",
            body: payload,
          });
          setPendingSync(await queue.size());
        }
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [],
  );

  // --- Écran eteint / application en arriere-plan --------------------------
  useEffect(() => {
    const subscription = RNAppState.addEventListener("change", (status: AppStateStatus) => {
      const timer = timerRef.current;
      if (!timer) return;
      if (status === "active") {
        timer.start();
        void sendHeartbeat(true);
        void sync();
      } else {
        // Le minuteur se fige : le temps d'écran ne s'ecoule pas écran eteint.
        timer.pause();
        void sendHeartbeat(false);
      }
    });
    return () => subscription.remove();
  }, [sendHeartbeat, sync]);

  // --- Actions -------------------------------------------------------------

  const pair = useCallback(async (code: string, deviceName: string) => {
    const credentials = await api.claim({
      pairing_code: code.trim().toUpperCase(),
      name: deviceName || "Tablette",
      platform: "android",
      app_version: "1.0.0",
      boot_id: BOOT_ID,
    });
    const stored: DeviceIdentity = {
      deviceId: credentials.device_id,
      childId: credentials.child_id,
      deviceToken: credentials.device_token,
      deviceSecret: credentials.device_secret,
      acceptedCounter: credentials.accepted_counter,
    };
    await storage.saveIdentity(stored);
    setIdentity(stored);
    setPhase("locked");
    await syncWith(stored);
  }, [syncWith]);

  const submitCode = useCallback(
    async (code: string): Promise<{ ok: boolean; message?: string; minutes?: number }> => {
      const id = identityRef.current;
      if (!id) return { ok: false, message: "Cet appareil n'est pas appairé." };

      // 1. Vérification locale : elle fonctionne même sans reseau.
      const attempt = await lockGuard.attempt({
        code,
        secretHex: id.deviceSecret,
        deviceId: id.deviceId,
        lastCounter: id.acceptedCounter,
      });
      if (!attempt.ok || !attempt.payload) {
        return { ok: false, message: attempt.message };
      }

      const grantedMs = attempt.payload.durationMinutes * 60_000;
      setIdentity({ ...id, acceptedCounter: attempt.payload.counter });

      // 2. On ouvre immediatement, puis on previent le serveur.
      const timer = new ScreenTimer(grantedMs);
      timer.start();
      timerRef.current = timer;
      const openedAt = new Date().toISOString();
      setSession({ id: null, grantedMs, startedAt: openedAt, offline: true });
      setRemainingMs(grantedMs);
      setPhase("unlocked");
      setLockout(null);

      try {
        const result = await api.redeem(id.deviceToken, {
          code,
          boot_id: BOOT_ID,
          device_wall_ms: Date.now(),
        });
        setOnline(true);
        timer.reconcile(0, result.granted_ms);
        setSession({
          id: result.session_id,
          grantedMs: result.granted_ms,
          startedAt: result.started_at,
          offline: false,
        });
        setRemainingMs(timer.remainingMs);
        return {
          ok: true,
          minutes: result.granted_minutes,
          message: result.truncated_by_cap
            ? "Le plafond du jour a reduit la durée accordée."
            : undefined,
        };
      } catch (error) {
        if (error instanceof NetworkError) {
          // Hors ligne : on note la consommation pour la déclarer plus tard.
          await queue.push({
            path: "/unlock/redeem",
            method: "POST",
            body: { code, boot_id: BOOT_ID, consumed_offline_at: openedAt },
          });
          setOnline(false);
          setPendingSync(await queue.size());
          return { ok: true, minutes: attempt.payload.durationMinutes };
        }
        // Refus du serveur (code révoqué, couvre-feu, plafond) : on referme.
        timerRef.current = null;
        setSession(null);
        setRemainingMs(0);
        setPhase("locked");
        return {
          ok: false,
          message: error instanceof ApiError ? error.message : "Déverrouillage refuse.",
        };
      }
    },
    [],
  );

  /** Conversion des points d'expérience en minutes d'écran. */
  const redeemXp = useCallback(
    async (xpToSpend?: number) => {
      const id = identityRef.current;
      if (!id) throw new ApiError(400, "not_paired", "Cet appareil n'est pas appairé.", {});
      const result = await api.redeemXp(id.deviceToken, {
        child_id: id.childId,
        ...(xpToSpend ? { xp_to_spend: xpToSpend } : {}),
      });
      // Le solde d'XP et la session viennent du serveur : on resynchronise.
      await syncWith(id);
      return result;
    },
    [syncWith],
  );

  const lockNow = useCallback(async () => {
    const id = identityRef.current;
    const current = sessionRef.current;
    if (id && current?.id) {
      try {
        await api.endSession(id.deviceToken, current.id);
      } catch {
        /* la fermeture locale reste prioritaire */
      }
    }
    timerRef.current = null;
    setSession(null);
    setRemainingMs(0);
    setPhase("locked");
    void sync();
  }, [sync]);

  const reset = useCallback(async () => {
    await storage.clearIdentity();
    timerRef.current = null;
    setIdentity(null);
    setChild(null);
    setPolicy(null);
    setSession(null);
    setPhase("pairing");
  }, []);

  const value = useMemo<AppValue>(
    () => ({
      phase,
      identity,
      child,
      policy,
      lockout,
      online,
      remainingMs,
      session,
      pendingSync,
      messages,
      pair,
      redeemXp,
      submitCode,
      sync,
      lockNow,
      reset,
    }),
    [phase, identity, child, policy, lockout, online, remainingMs, session, pendingSync, messages, pair, redeemXp, submitCode, sync, lockNow, reset],
  );

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}

export function useApp(): AppValue {
  const context = useContext(AppContext);
  if (!context) throw new Error("useApp doit être utilisé dans AppProvider");
  return context;
}
