/**
 * Système visuel de l'application enfant.
 *
 * Parti pris : clair, chaleureux, lisible de loin. Un enfant de 8 a 12 ans
 * doit comprendre en un coup d'oeil ce qu'il peut faire, sans lire un
 * paragraphe. D'ou : une seule action principale par écran, des cartes larges
 * aux angles genereux, et des cibles tactiles d'au moins 48 points.
 *
 * On evite volontairement l'esthetique "jeu de hasard" (neons, confettis
 * permanents, compteurs qui clignotent) : la recompense vient du travail, et
 * l'interface doit le refleter.
 */

export const colors = {
  // --- Fonds et encre ---
  bg: "#f3f6fc",
  surface: "#ffffff",
  surfaceAlt: "#eef3fd",
  ink: "#101a2e",
  inkSoft: "#4c5a78",
  inkFaint: "#8b96ad",
  line: "#e3e9f6",
  lineStrong: "#cfd8ec",

  // --- Marque ---
  primary: "#2a78d6",
  primaryDeep: "#1c5cab",
  primarySoft: "#e6effd",
  onPrimary: "#ffffff",

  // --- Recompense (XP, temps gagne) ---
  gold: "#f0a11c",
  goldSoft: "#fdf1dd",
  goldInk: "#7d5200",

  // --- États ---
  success: "#0f9d58",
  successSoft: "#e3f6ec",
  successInk: "#046340",
  danger: "#d64545",
  dangerSoft: "#fdeaea",
  dangerInk: "#9b2020",
  info: "#5b6bd6",

  // --- Blocs du moteur adaptatif ---
  bucketRemediation: "#f0a11c",
  bucketApprentissage: "#2a78d6",
  bucketConsolidation: "#0f9d58",

  // --- Ardoise ---
  slate: "#fffdf7",
  slateInk: "#18202f",
  slateGrid: "#e8ecf4",
};

export const spacing = (n: number) => n * 8;

export const radius = { sm: 12, md: 18, lg: 26, xl: 34, pill: 999 };

export const type = {
  display: { fontSize: 40, fontWeight: "800" as const, letterSpacing: -1 },
  title: { fontSize: 26, fontWeight: "800" as const, letterSpacing: -0.4 },
  heading: { fontSize: 20, fontWeight: "700" as const },
  body: { fontSize: 16, fontWeight: "400" as const },
  bodyStrong: { fontSize: 16, fontWeight: "600" as const },
  small: { fontSize: 13.5, fontWeight: "500" as const },
  tiny: { fontSize: 12, fontWeight: "700" as const, letterSpacing: 0.6 },
  code: { fontSize: 34, fontWeight: "800" as const, letterSpacing: 8 },
};

/** Ombres douces : de la profondeur sans salir le fond clair. */
export const elevation = {
  card: {
    shadowColor: "#0f1d3d",
    shadowOpacity: 0.07,
    shadowRadius: 18,
    shadowOffset: { width: 0, height: 6 },
    elevation: 3,
  },
  raised: {
    shadowColor: "#0f1d3d",
    shadowOpacity: 0.14,
    shadowRadius: 24,
    shadowOffset: { width: 0, height: 10 },
    elevation: 6,
  },
};

/** Emoji d'avatar, alignes sur ceux du tableau de bord parental. */
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

export const avatarOf = (key: string | undefined) => AVATARS[key ?? "fox"] ?? "🙂";
