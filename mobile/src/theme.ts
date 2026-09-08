/**
 * Systeme visuel de l'application enfant.
 *
 * Deux ambiances : l'ecran de verrouillage et l'examen sont sobres et
 * concentres (fond profond, peu de couleurs) ; l'espace deverrouille est plus
 * chaleureux. On evite l'esthetique "jeu de hasard" : la recompense vient du
 * travail, pas d'un feu d'artifice.
 */

export const colors = {
  bg: "#0f172a",
  bgSoft: "#16223f",
  surface: "#1e2b4d",
  surfaceHigh: "#26355c",
  border: "#33436e",
  ink: "#f8fafc",
  inkMuted: "#a7b4d0",
  inkFaint: "#7688aa",

  accent: "#4d94ff",
  accentInk: "#0b1c38",
  success: "#34d399",
  successInk: "#052e21",
  warning: "#fbbf24",
  danger: "#f87171",

  // Reprise des blocs du moteur adaptatif, pour situer chaque question.
  bucketRemediation: "#fbbf24",
  bucketApprentissage: "#4d94ff",
  bucketConsolidation: "#34d399",

  slate: "#fdfdfb",
  slateInk: "#1a1a1a",
  slateGrid: "#dfe4ec",
};

export const spacing = (n: number) => n * 8;

export const radius = { sm: 10, md: 16, lg: 24, pill: 999 };

export const type = {
  hero: { fontSize: 44, fontWeight: "800" as const, letterSpacing: -1 },
  title: { fontSize: 24, fontWeight: "700" as const },
  subtitle: { fontSize: 18, fontWeight: "600" as const },
  body: { fontSize: 16, fontWeight: "400" as const },
  small: { fontSize: 13, fontWeight: "500" as const },
  code: { fontSize: 34, fontWeight: "800" as const, letterSpacing: 6 },
};

export const shadow = {
  shadowColor: "#000",
  shadowOpacity: 0.25,
  shadowRadius: 12,
  shadowOffset: { width: 0, height: 4 },
  elevation: 4,
};
