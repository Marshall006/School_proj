/**
 * Integration : la tablette valide hors ligne un code emis par le serveur.
 *
 * C'est la boucle complete du produit, jouee sans navigateur ni emulateur :
 *
 *   1. un parent genere un code depuis l'API ;
 *   2. la tablette le verifie **avec l'implementation TypeScript embarquee**,
 *      sans jamais rappeler le serveur ;
 *   3. elle refuse ensuite de le rejouer ;
 *   4. elle le consomme aupres du serveur, qui ouvre la session ;
 *   5. le minuteur bat la mesure et le temps decroit.
 *
 * Prerequis : `make demo` puis `make api` (API sur :8000).
 * Usage : node test/appareil-hors-ligne.mjs [url-api]
 */

import {
  UnlockProtocolError,
  formatCode,
  peekCode,
  verifyCode,
} from "../dist/unlock-protocol.js";

const API = process.argv[2] ?? "http://127.0.0.1:8000/api/v1";
const EMAIL = process.env.KODA_DEMO_EMAIL ?? "demo@koda.app";
const PASSWORD = process.env.KODA_DEMO_PASSWORD ?? "demo-koda-2026";

const passed = [];
const failed = [];
const check = (label, ok, detail = "") =>
  (ok ? passed : failed).push(label + (ok ? "" : ` — ${detail}`));

async function call(path, { method = "GET", body, token } = {}) {
  const response = await fetch(`${API}${path}`, {
    method,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const text = await response.text();
  const payload = text ? JSON.parse(text) : null;
  if (!response.ok) {
    const error = new Error(payload?.error?.message ?? `HTTP ${response.status}`);
    error.code = payload?.error?.code;
    error.status = response.status;
    throw error;
  }
  return payload;
}

// --- 1. Le parent prepare un appareil neuf ---------------------------------
const session = await call("/auth/login", {
  method: "POST",
  body: { email: EMAIL, password: PASSWORD },
});
const parentToken = session.tokens.access_token;
check("connexion du parent", Boolean(parentToken));

const children = await call("/children", { token: parentToken });
const child = children[0];
check("un enfant existe", Boolean(child), "lancez `make demo` d'abord");

const pairing = await call("/devices/pairing-code", {
  method: "POST",
  token: parentToken,
  body: { child_id: child.id, suggested_name: "Tablette simulee" },
});
const credentials = await call("/devices/claim", {
  method: "POST",
  body: {
    pairing_code: pairing.code,
    name: "Tablette simulee",
    platform: "android",
    app_version: "1.0.0",
    boot_id: "boot-simulation",
  },
});
check("appairage : secret recu une seule fois", credentials.device_secret.length === 64);
check("compteur initial a zero", credentials.accepted_counter === 0);

// A partir d'ici le script a cree un appareil dans la base : quoi qu'il
// arrive, il doit le revoquer avant de sortir.
process.on("exit", () => {});
let cleanupDone = false;
async function cleanup() {
  if (cleanupDone) return;
  cleanupDone = true;
  try {
    await call(`/devices/${credentials.device_id}/revoke`, {
      method: "POST",
      token: parentToken,
    });
  } catch {
    /* deja revoque, ou serveur arrete : rien de plus a faire */
  }
}

try {

// --- 2. Le parent genere un code ------------------------------------------
// Pendant les vacances le deverrouillage direct est coupe : on bascule alors
// sur la rallonge exceptionnelle, exactement comme le fait le tableau de bord.
const codeBody = {
  child_id: child.id,
  device_id: credentials.device_id,
  duration_minutes: 45,
  note: "Integration hors ligne",
};
let issued;
try {
  issued = await call("/unlock/parent-code", { method: "POST", token: parentToken, body: codeBody });
  check("code emis (deverrouillage direct)", true);
} catch (error) {
  if (error.code !== "policy_forbids") throw error;
  issued = await call("/unlock/bonus-code", { method: "POST", token: parentToken, body: codeBody });
  check("deverrouillage direct refuse en vacances, rallonge acceptee", true);
}
check("code a 10 chiffres", /^\d{10}$/.test(issued.code), issued.code);

// --- 3. La tablette le verifie SANS reseau --------------------------------
const peeked = peekCode(issued.code);
check("duree lisible avant verification", peeked.durationMinutes === 45);

let localCounter = credentials.accepted_counter;
const payload = verifyCode({
  code: formatCode(issued.code), // saisi avec les espaces d'affichage
  secretHex: credentials.device_secret,
  deviceId: credentials.device_id,
  lastCounter: localCounter,
  nowSeconds: Date.now() / 1000,
});
check("verification hors ligne reussie", payload.durationMinutes === 45);
localCounter = payload.counter; // le compteur avance : les codes anterieurs meurent

// --- 4. Le rejeu est refuse, localement ------------------------------------
let replayRefused = false;
try {
  verifyCode({
    code: issued.code,
    secretHex: credentials.device_secret,
    deviceId: credentials.device_id,
    lastCounter: localCounter,
    nowSeconds: Date.now() / 1000,
  });
} catch (error) {
  replayRefused = error instanceof UnlockProtocolError;
}
check("rejeu refuse hors ligne", replayRefused);

// --- 5. Un code forge est refuse -------------------------------------------
let forgedRefused = false;
try {
  verifyCode({
    code: `99${issued.code.slice(2)}`, // duree gonflee a 495 minutes
    secretHex: credentials.device_secret,
    deviceId: credentials.device_id,
    lastCounter: credentials.accepted_counter,
    nowSeconds: Date.now() / 1000,
  });
} catch (error) {
  forgedRefused = error instanceof UnlockProtocolError;
}
check("duree falsifiee refusee", forgedRefused);

// --- 6. Consommation aupres du serveur -------------------------------------
const redeemed = await call("/unlock/redeem", {
  method: "POST",
  token: credentials.device_token,
  body: { code: issued.code, boot_id: "boot-simulation", device_wall_ms: Date.now() },
});
check("session ouverte", redeemed.granted_minutes > 0, JSON.stringify(redeemed));
check("duree accordee coherente", redeemed.granted_minutes <= 45);

let secondRedeemRefused = false;
try {
  await call("/unlock/redeem", {
    method: "POST",
    token: credentials.device_token,
    body: { code: issued.code },
  });
} catch (error) {
  secondRedeemRefused = error.code === "invalid_unlock_code";
}
check("le serveur refuse aussi le rejeu", secondRedeemRefused);

// --- 7. Le minuteur bat la mesure ------------------------------------------
const beat = await call(`/screen/sessions/${redeemed.session_id}/heartbeat`, {
  method: "POST",
  token: credentials.device_token,
  body: { monotonic_ms: 0, device_wall_ms: Date.now(), screen_on: true, boot_id: "boot-simulation" },
});
check("premier battement accepte", beat.state === "active", JSON.stringify(beat));

const later = await call(`/screen/sessions/${redeemed.session_id}/heartbeat`, {
  method: "POST",
  token: credentials.device_token,
  body: {
    monotonic_ms: 90_000,
    device_wall_ms: Date.now(),
    screen_on: false, // ecran eteint : le temps ne doit pas courir
    boot_id: "boot-simulation",
  },
});
check("ecran eteint : le minuteur se met en pause", later.state === "paused");
check("temps non consomme pendant la pause", later.consumed_ms === beat.consumed_ms);

// --- 8. Nettoyage : on revoque l'appareil simule ---------------------------
await cleanup();
let revokedRefused = false;
try {
  await call("/device/sync", { method: "POST", token: credentials.device_token, body: {} });
} catch (error) {
  revokedRefused = error.code === "device_revoked";
}
check("appareil revoque : tout acces coupe", revokedRefused);

} finally {
  await cleanup();
}

console.log(`\n${passed.length} verifications reussies`);
for (const label of passed) console.log("  ✓ " + label);
if (failed.length > 0) {
  console.error(`\n${failed.length} echec(s) :`);
  for (const label of failed) console.error("  ✗ " + label);
  process.exit(1);
}
console.log("\nBoucle complete serveur ↔ tablette hors ligne : OK\n");
