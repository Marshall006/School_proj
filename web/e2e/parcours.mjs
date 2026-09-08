/**
 * Parcours navigateur du tableau de bord parental.
 *
 * Exerce l'interface reelle contre l'API reelle et le jeu de demonstration :
 * connexion, generation d'un code, graphiques, reglages, thème sombre.
 *
 * Prerequis :
 *   python -m app.cli demo         # foyer de demonstration
 *   make api                       # API sur :8000
 *   make web                       # tableau de bord sur :3000
 *   npx playwright install chromium   # une fois, depuis `web/`
 *
 * Usage :
 *   cd web && npm run e2e -- [url-du-tableau-de-bord]
 *
 * L'API doit autoriser l'origine du tableau de bord :
 *   KODA_CORS_ORIGINS=http://localhost:3000
 */

import { chromium } from "playwright";

const WEB = process.argv[2] ?? "http://127.0.0.1:3000";
const EMAIL = process.env.KODA_DEMO_EMAIL ?? "demo@koda.app";
const PASSWORD = process.env.KODA_DEMO_PASSWORD ?? "demo-koda-2026";

const passed = [];
const failed = [];
const check = (label, ok, detail = "") =>
  (ok ? passed : failed).push(label + (ok ? "" : ` — ${detail}`));

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
const consoleErrors = [];
page.on("console", (message) => {
  if (message.type() === "error") consoleErrors.push(message.text());
});
page.on("pageerror", (error) => consoleErrors.push(String(error)));

// 1. Connexion
await page.goto(`${WEB}/connexion`, { waitUntil: "networkidle" });
check("page de connexion", await page.getByRole("button", { name: "Se connecter" }).isVisible());
await page.fill("#email", EMAIL);
await page.fill("#password", PASSWORD);
await page.click("button[type=submit]");
await page.waitForURL("**/foyer", { timeout: 20000 });
check("connexion reussie", page.url().includes("/foyer"));

// 2. Vue d'ensemble
await page.waitForSelector("text=Banque pedagogique", { timeout: 20000 });
await page.waitForSelector("text=Journal du foyer", { timeout: 20000 });
const foyer = await page.textContent("body");
check("enfants listes", /Noam|Aya/.test(foyer));
check("banque pedagogique", /questions reparties sur/.test(foyer));
check("chaine d'audit verifiee", /Chaine d.audit intacte/.test(foyer));

// 3. Generation d'un code de deverrouillage
await page.locator("button", { hasText: /^(Debloquer|Accorder une rallonge)$/ }).first().click();
await page.waitForSelector(".modal");
const generate = page.locator(".modal button", { hasText: "Generer le code" });
if (await generate.count()) {
  await generate.click();
  await page.waitForSelector(".code-display", { timeout: 10000 });
  const code = (await page.textContent(".code-display")).replace(/\D/g, "");
  check("code a 10 chiffres", code.length === 10, `recu "${code}"`);
  check("compte a rebours", (await page.textContent(".modal")).includes("Expire dans"));
}
await page.locator(".modal-close").click();
await page.waitForSelector(".modal", { state: "detached" });

// 4. Tableau de bord d'un enfant
await page.locator("a[href*='/enfants/']").first().click();
await page.waitForSelector("text=Reussite par matiere", { timeout: 20000 });
const enfant = await page.textContent("body");
for (const marker of ["Reussite par matiere", "Niveau par notion", "Dernieres evaluations"]) {
  check(`section « ${marker} »`, enfant.includes(marker));
}
check("graphiques SVG", (await page.locator("svg").count()) >= 3);
check("legendes presentes", (await page.locator(".legend-item").count()) >= 2);

await page.locator("button", { hasText: "Voir le tableau" }).first().click();
await page.waitForSelector("table.table");
check("vue tableau (alternative au graphique)", (await page.locator("table.table").count()) > 0);

// 5. Reglages
await page.goto(`${page.url()}/reglages`, { waitUntil: "networkidle" });
await page.waitForSelector("text=Exigence de reussite", { timeout: 15000 });
const regles = await page.textContent("body");
check("page de regles", regles.includes("Temps de carence") && regles.includes("Vacances"));

// 6. Autres pages
for (const [path, marker] of [
  ["/appareils", "Appairer une tablette"],
  ["/copies", "Copies a valider"],
  ["/calendrier", "Calendrier scolaire"],
]) {
  await page.goto(`${WEB}${path}`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1200);
  check(`page ${path}`, (await page.textContent("body")).includes(marker));
}

// 7. Thème sombre
await page.goto(`${WEB}/foyer`, { waitUntil: "networkidle" });
await page.waitForTimeout(1000);
await page.locator("button", { hasText: /Theme (sombre|clair)/ }).click();
await page.waitForTimeout(400);
check("bascule de theme", ["dark", "light"].includes(await page.getAttribute("html", "data-theme")));

check("aucune erreur console", consoleErrors.length === 0, consoleErrors.slice(0, 3).join(" | "));

await browser.close();

console.log(`\n${passed.length} verifications reussies`);
for (const label of passed) console.log("  ✓ " + label);
if (failed.length > 0) {
  console.error(`\n${failed.length} echec(s) :`);
  for (const label of failed) console.error("  ✗ " + label);
  process.exit(1);
}
console.log("\nParcours navigateur complet : OK\n");
