/**
 * Pave de saisie assiste.
 *
 * Sur tablette, taper une virgule ou un symbole mathematique au clavier
 * système est penible et casse la concentration. Le pave n'affiche que les
 * touches utiles à la question en cours, telles que le serveur les decrit dans
 * `input_spec`.
 */

import { Pressable, StyleSheet, Text, View } from "react-native";

import { colors, radius, spacing, type } from "../theme";

export type KeypadMode = "numeric" | "decimal" | "math" | "text" | "fraction" | "none";

const LAYOUTS: Record<string, string[][]> = {
  numeric: [
    ["1", "2", "3"],
    ["4", "5", "6"],
    ["7", "8", "9"],
    ["-", "0", "⌫"],
  ],
  decimal: [
    ["1", "2", "3"],
    ["4", "5", "6"],
    ["7", "8", "9"],
    [",", "0", "⌫"],
  ],
  math: [
    ["1", "2", "3", "+", "-"],
    ["4", "5", "6", "x", ":"],
    ["7", "8", "9", "/", ","],
    ["(", "0", ")", "=", "⌫"],
  ],
  fraction: [
    ["1", "2", "3"],
    ["4", "5", "6"],
    ["7", "8", "9"],
    ["/", "0", "⌫"],
  ],
};

export function Keypad({
  mode,
  palette,
  onKey,
  onClear,
}: {
  mode: KeypadMode;
  palette?: string[];
  onKey: (key: string) => void;
  onClear?: () => void;
}) {
  if (mode === "none") return null;
  const rows = LAYOUTS[mode] ?? LAYOUTS.numeric;
  const extras = (palette ?? []).filter((key) => !rows.flat().includes(key));

  const renderKey = (key: string, soft = false) => (
    <Pressable
      key={key}
      onPress={() => onKey(key)}
      accessibilityRole="button"
      accessibilityLabel={key === "⌫" ? "Effacer" : key}
      style={({ pressed }) => [
        styles.key,
        soft && styles.keySoft,
        key === "⌫" && styles.keyErase,
        pressed && styles.keyPressed,
      ]}
    >
      <Text style={[styles.keyText, key === "⌫" && styles.keyEraseText]}>{key}</Text>
    </Pressable>
  );

  return (
    <View style={styles.pad}>
      {rows.map((row, rowIndex) => (
        <View key={rowIndex} style={styles.row}>
          {row.map((key) => renderKey(key))}
        </View>
      ))}
      {extras.length > 0 ? (
        <View style={styles.row}>{extras.map((key) => renderKey(key, true))}</View>
      ) : null}
      {onClear ? (
        <Pressable onPress={onClear} style={styles.clear}>
          <Text style={styles.clearText}>Tout effacer</Text>
        </Pressable>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  pad: { gap: spacing(1) },
  row: { flexDirection: "row", gap: spacing(1) },
  key: {
    flex: 1,
    minHeight: 58,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.line,
  },
  keySoft: { backgroundColor: colors.primarySoft, borderColor: colors.primarySoft },
  keyErase: { backgroundColor: colors.surfaceAlt },
  keyPressed: { backgroundColor: colors.primarySoft, borderColor: colors.primary },
  keyText: { color: colors.ink, fontSize: 23, fontWeight: "700" },
  keyEraseText: { color: colors.inkSoft },
  clear: { alignSelf: "flex-start", paddingVertical: 8, paddingHorizontal: 12 },
  clearText: { color: colors.inkFaint, ...type.small, fontWeight: "700" },
});
