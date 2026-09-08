/**
 * Verification croisee Python <-> TypeScript.
 *
 * Les vecteurs sont produits par l'implementation Python de reference
 * (`backend/app/core/unlock_protocol.py`). Si les deux portages divergent, ce
 * test echoue : c'est le garde-fou qui permet a la tablette de valider un code
 * hors ligne en etant certaine d'accepter exactement ce que le serveur emet.
 *
 *     node test/run.mjs        (apres `npm run build`)
 */

import { readFileSync } from "node:fs";
import { createHmac, createHash } from "node:crypto";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

import {
  UnlockProtocolError,
  codeFingerprint,
  formatCode,
  issueCode,
  lockoutSecondsFor,
  peekCode,
  verifyCode,
} from "../dist/unlock-protocol.js";
import { bytesToHex, hmacSha256, sha256, utf8Bytes, hexToBytes } from "../dist/sha256.js";

const here = dirname(fileURLToPath(import.meta.url));
const vectors = JSON.parse(readFileSync(join(here, "vectors.json"), "utf8"));

let passed = 0;
const failures = [];

function check(label, condition, detail = "") {
  if (condition) {
    passed += 1;
  } else {
    failures.push(`${label}${detail ? ` — ${detail}` : ""}`);
  }
}

// --- 1. SHA-256 et HMAC contre le module natif de Node ---------------------
for (const sample of ["", "abc", "KODA1|test|1|36|0|1000000", "é€𝄞 accents et emoji 🎒"]) {
  const mine = bytesToHex(sha256(utf8Bytes(sample)));
  const reference = createHash("sha256").update(sample, "utf8").digest("hex");
  check(`sha256("${sample.slice(0, 20)}")`, mine === reference, `${mine} != ${reference}`);
}
for (const keyHex of ["a1a1a1a1", "00".repeat(64), "ff".repeat(100)]) {
  const message = "message de test pour HMAC";
  const mine = bytesToHex(hmacSha256(hexToBytes(keyHex), utf8Bytes(message)));
  const reference = createHmac("sha256", Buffer.from(keyHex, "hex")).update(message, "utf8").digest("hex");
  check(`hmac(cle de ${keyHex.length / 2} octets)`, mine === reference, `${mine} != ${reference}`);
}

// --- 2. Emission : le TypeScript doit produire les codes du Python ---------
for (const vector of vectors.issue) {
  const code = issueCode({
    secretHex: vectors.secret_hex,
    deviceId: vectors.device_id,
    counter: vector.counter,
    durationMinutes: vector.duration_minutes,
    kind: vector.kind,
    nowSeconds: vector.now,
  });
  check(`emission c=${vector.counter} d=${vector.duration_minutes}min`, code === vector.code, `${code} != ${vector.code}`);
  check(`format c=${vector.counter}`, formatCode(code) === vector.formatted);
  check(
    `empreinte c=${vector.counter}`,
    codeFingerprint(code, vectors.device_id) === vector.fingerprint,
  );
  const peeked = peekCode(code);
  check(`lecture en clair c=${vector.counter}`, peeked.durationMinutes === vector.duration_minutes && peeked.kind === vector.kind);
}

// --- 3. Verification : memes acceptations, memes refus ---------------------
for (const vector of vectors.verify) {
  let result = null;
  let error = null;
  try {
    result = verifyCode({
      code: vector.code,
      secretHex: vectors.secret_hex,
      deviceId: vectors.device_id,
      lastCounter: vector.last_counter,
      nowSeconds: vector.now,
    });
  } catch (err) {
    error = err;
  }
  if (vector.expect.ok) {
    check(`verif "${vector.label}"`, result !== null, error ? error.message : "aucun resultat");
    if (result) {
      check(`  compteur "${vector.label}"`, result.counter === vector.expect.counter);
      if (vector.expect.duration_minutes !== undefined) {
        check(`  duree "${vector.label}"`, result.durationMinutes === vector.expect.duration_minutes);
      }
    }
  } else {
    check(`refus "${vector.label}"`, error instanceof UnlockProtocolError, "aurait du echouer");
  }
}

// --- 4. Proprietes locales -------------------------------------------------
check("mauvais secret refuse", (() => {
  try {
    verifyCode({
      code: vectors.issue[0].code,
      secretHex: "b2".repeat(32),
      deviceId: vectors.device_id,
      lastCounter: 0,
      nowSeconds: vectors.issue[0].now,
    });
    return false;
  } catch {
    return true;
  }
})());

check("mauvais appareil refuse", (() => {
  try {
    verifyCode({
      code: vectors.issue[0].code,
      secretHex: vectors.secret_hex,
      deviceId: "un-autre-appareil",
      lastCounter: 0,
      nowSeconds: vectors.issue[0].now,
    });
    return false;
  } catch {
    return true;
  }
})());

check("separateurs humains toleres", (() => {
  const code = vectors.issue[0].code;
  for (const variant of [formatCode(code), `${code.slice(0, 3)}-${code.slice(3, 6)}-${code.slice(6)}`, ` ${code} `]) {
    const payload = verifyCode({
      code: variant,
      secretHex: vectors.secret_hex,
      deviceId: vectors.device_id,
      lastCounter: 0,
      nowSeconds: vectors.issue[0].now,
    });
    if (payload.counter !== 1) return false;
  }
  return true;
})());

check("verrouillage progressif", lockoutSecondsFor(1) === 0 && lockoutSecondsFor(5) === 300 && lockoutSecondsFor(15) === 86400);

// --- 5. Performance : la verification doit rester instantanee sur tablette --
const started = Date.now();
for (let i = 0; i < 50; i += 1) {
  try {
    verifyCode({
      code: "0000000000",
      secretHex: vectors.secret_hex,
      deviceId: vectors.device_id,
      lastCounter: 0,
      nowSeconds: vectors.issue[0].now,
    });
  } catch {
    /* attendu */
  }
}
const perVerification = (Date.now() - started) / 50;
check(`performance (${perVerification.toFixed(1)} ms par verification exhaustive)`, perVerification < 60);

// --- Rapport ---------------------------------------------------------------
console.log(`\n${passed} verifications reussies`);
if (failures.length > 0) {
  console.error(`\n${failures.length} ECHEC(S) :`);
  for (const failure of failures) console.error(`  - ${failure}`);
  process.exit(1);
}
console.log("Les implementations Python et TypeScript sont identiques.\n");
