/**
 * Persistance locale — variante web.
 *
 * Metro choisit automatiquement ce fichier plutot que `storage.ts` quand la
 * plateforme est le web. Deux raisons a cette separation :
 *
 * - `@react-native-async-storage/async-storage` echoue au chargement dans un
 *   navigateur (incompatibilite d'interoperabilite de sa dependance
 *   `merge-options`), ce qui suffit a faire planter l'application entiere ;
 * - `expo-secure-store` n'a pas d'equivalent navigateur.
 *
 * L'API publique est identique a celle de `storage.ts` : le reste du code ne
 * sait pas sur quelle plateforme il tourne.
 *
 * ATTENTION : dans un navigateur, le secret d'appareil est stocke en clair
 * dans `localStorage`, la ou le natif utilise le Keychain / Keystore. Le mode
 * web sert a faire tourner et demontrer l'application sans telephone, pas a
 * equiper l'appareil d'un enfant.
 */

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

/** Repli en memoire : navigation privee, ou rendu cote serveur. */
const memory = new Map<string, string>();

function backend(): Pick<Storage, "getItem" | "setItem" | "removeItem"> {
  try {
    if (typeof localStorage !== "undefined") {
      localStorage.getItem("koda.probe");
      return localStorage;
    }
  } catch {
    // localStorage refuse (navigation privee, cookies bloques).
  }
  return {
    getItem: (key: string) => memory.get(key) ?? null,
    setItem: (key: string, value: string) => void memory.set(key, value),
    removeItem: (key: string) => void memory.delete(key),
  };
}

const read = (key: string): string | null => backend().getItem(key);
const write = (key: string, value: string): void => backend().setItem(key, value);
const drop = (key: string): void => backend().removeItem(key);

export const storage = {
  async saveIdentity(identity: DeviceIdentity): Promise<void> {
    write(SECURE_KEYS.deviceSecret, identity.deviceSecret);
    write(SECURE_KEYS.deviceToken, identity.deviceToken);
    write(KEYS.deviceId, identity.deviceId);
    write(KEYS.childId, identity.childId);
    write(KEYS.acceptedCounter, String(identity.acceptedCounter));
  },

  async loadIdentity(): Promise<DeviceIdentity | null> {
    const secret = read(SECURE_KEYS.deviceSecret);
    const token = read(SECURE_KEYS.deviceToken);
    const deviceId = read(KEYS.deviceId);
    const childId = read(KEYS.childId);
    if (!secret || !token || !deviceId || !childId) return null;
    return {
      deviceSecret: secret,
      deviceToken: token,
      deviceId,
      childId,
      acceptedCounter: Number(read(KEYS.acceptedCounter) ?? "0"),
    };
  },

  async clearIdentity(): Promise<void> {
    drop(SECURE_KEYS.deviceSecret);
    drop(SECURE_KEYS.deviceToken);
    for (const key of Object.values(KEYS)) drop(key);
  },

  async setAcceptedCounter(counter: number): Promise<void> {
    write(KEYS.acceptedCounter, String(counter));
  },

  async getFailedAttempts(): Promise<number> {
    return Number(read(KEYS.failedAttempts) ?? "0");
  },

  async setFailedAttempts(count: number): Promise<void> {
    write(KEYS.failedAttempts, String(count));
  },

  async getLockedUntil(): Promise<number> {
    return Number(read(KEYS.lockedUntil) ?? "0");
  },

  async setLockedUntil(timestamp: number): Promise<void> {
    write(KEYS.lockedUntil, String(timestamp));
  },

  async cache<T>(key: keyof typeof KEYS, value: T): Promise<void> {
    write(KEYS[key], JSON.stringify(value));
  },

  async readCache<T>(key: keyof typeof KEYS): Promise<T | null> {
    const raw = read(KEYS[key]);
    if (!raw) return null;
    try {
      return JSON.parse(raw) as T;
    } catch {
      return null;
    }
  },
};

export { KEYS };
