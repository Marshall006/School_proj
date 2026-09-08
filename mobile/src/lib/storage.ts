/**
 * Persistance locale.
 *
 * Le secret d'appareil va dans le magasin securise du systeme (Keychain /
 * Keystore) : c'est la cle qui autorise la validation des codes hors ligne.
 * Le reste (compteur, cache des regles, file d'attente de synchronisation)
 * vit dans le stockage ordinaire.
 */

import AsyncStorage from "@react-native-async-storage/async-storage";
import * as SecureStore from "expo-secure-store";

const SECURE_KEYS = {
  deviceSecret: "koda.device.secret",
  deviceToken: "koda.device.token",
} as const;

const KEYS = {
  deviceId: "koda.device.id",
  childId: "koda.child.id",
  acceptedCounter: "koda.unlock.counter",
  failedAttempts: "koda.unlock.failed",
  lockedUntil: "koda.unlock.lockedUntil",
  policy: "koda.cache.policy",
  child: "koda.cache.child",
  session: "koda.cache.session",
  revoked: "koda.cache.revoked",
  queue: "koda.queue",
  draft: "koda.exam.draft",
} as const;

export interface DeviceIdentity {
  deviceId: string;
  childId: string;
  deviceToken: string;
  deviceSecret: string;
  acceptedCounter: number;
}

async function secureSet(key: string, value: string): Promise<void> {
  if (await SecureStore.isAvailableAsync()) {
    await SecureStore.setItemAsync(key, value);
    return;
  }
  // Le web et certains emulateurs n'exposent pas de magasin securise.
  await AsyncStorage.setItem(`fallback:${key}`, value);
}

async function secureGet(key: string): Promise<string | null> {
  if (await SecureStore.isAvailableAsync()) {
    return SecureStore.getItemAsync(key);
  }
  return AsyncStorage.getItem(`fallback:${key}`);
}

async function secureDelete(key: string): Promise<void> {
  if (await SecureStore.isAvailableAsync()) {
    await SecureStore.deleteItemAsync(key);
    return;
  }
  await AsyncStorage.removeItem(`fallback:${key}`);
}

export const storage = {
  async saveIdentity(identity: DeviceIdentity): Promise<void> {
    await secureSet(SECURE_KEYS.deviceSecret, identity.deviceSecret);
    await secureSet(SECURE_KEYS.deviceToken, identity.deviceToken);
    await AsyncStorage.multiSet([
      [KEYS.deviceId, identity.deviceId],
      [KEYS.childId, identity.childId],
      [KEYS.acceptedCounter, String(identity.acceptedCounter)],
    ]);
  },

  async loadIdentity(): Promise<DeviceIdentity | null> {
    const [secret, token] = await Promise.all([
      secureGet(SECURE_KEYS.deviceSecret),
      secureGet(SECURE_KEYS.deviceToken),
    ]);
    const entries = await AsyncStorage.multiGet([KEYS.deviceId, KEYS.childId, KEYS.acceptedCounter]);
    const map = Object.fromEntries(entries) as Record<string, string | null>;
    if (!secret || !token || !map[KEYS.deviceId] || !map[KEYS.childId]) return null;
    return {
      deviceSecret: secret,
      deviceToken: token,
      deviceId: map[KEYS.deviceId]!,
      childId: map[KEYS.childId]!,
      acceptedCounter: Number(map[KEYS.acceptedCounter] ?? "0"),
    };
  },

  async clearIdentity(): Promise<void> {
    await secureDelete(SECURE_KEYS.deviceSecret);
    await secureDelete(SECURE_KEYS.deviceToken);
    await AsyncStorage.multiRemove(Object.values(KEYS));
  },

  async setAcceptedCounter(counter: number): Promise<void> {
    await AsyncStorage.setItem(KEYS.acceptedCounter, String(counter));
  },

  async getFailedAttempts(): Promise<number> {
    return Number((await AsyncStorage.getItem(KEYS.failedAttempts)) ?? "0");
  },

  async setFailedAttempts(count: number): Promise<void> {
    await AsyncStorage.setItem(KEYS.failedAttempts, String(count));
  },

  async getLockedUntil(): Promise<number> {
    return Number((await AsyncStorage.getItem(KEYS.lockedUntil)) ?? "0");
  },

  async setLockedUntil(timestamp: number): Promise<void> {
    await AsyncStorage.setItem(KEYS.lockedUntil, String(timestamp));
  },

  async cache<T>(key: keyof typeof KEYS, value: T): Promise<void> {
    await AsyncStorage.setItem(KEYS[key], JSON.stringify(value));
  },

  async readCache<T>(key: keyof typeof KEYS): Promise<T | null> {
    const raw = await AsyncStorage.getItem(KEYS[key]);
    if (!raw) return null;
    try {
      return JSON.parse(raw) as T;
    } catch {
      return null;
    }
  },
};

export { KEYS };
