/**
 * Pave de saisie assiste.
 *
 * Sur tablette, taper une virgule ou un symbole mathematique au clavier
 * systeme est penible et casse la concentration. Le pave affiche exactement les
 * touches utiles a la question en cours, telles que le serveur les a decrites
 * dans `input_spec`.
 */

import { StyleSheet, Text, TouchableOpacity, View } from "react-native";

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

  return (
    <View style={styles.pad}>
      {rows.map((row, rowIndex) => (
        <View key={rowIndex} style={styles.row}>
          {row.map((key) => (
            <TouchableOpacity
              key={key}
              style={[styles.key, key === "⌫" && styles.keyMuted]}
              onPress={() => onKey(key)}
              accessibilityLabel={key === "⌫" ? "Effacer" : key}
            >
              <Text style={styles.keyText}>{key}</Text>
            </TouchableOpacity>
          ))}
        </View>
      ))}
      {extras.length > 0 && (
        <View style={styles.row}>
          {extras.map((key) => (
            <TouchableOpacity key={key} style={[styles.key, styles.keySoft]} onPress={() => onKey(key)}>
              <Text style={styles.keyText}>{key}</Text>
            </TouchableOpacity>
          ))}
        </View>
      )}
      {onClear && (
        <TouchableOpacity style={styles.clear} onPress={onClear}>
          <Text style={styles.clearText}>Tout effacer</Text>
        </TouchableOpacity>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  pad: { gap: spacing(1) },
  row: { flexDirection: "row", gap: spacing(1) },
  key: {
    flex: 1,
    minHeight: 54,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.surfaceHigh,
    borderRadius: radius.sm,
    borderWidth: 1,
    borderColor: colors.border,
  },
  keyMuted: { backgroundColor: colors.surface },
  keySoft: { backgroundColor: colors.bgSoft },
  keyText: { color: colors.ink, fontSize: 22, fontWeight: "600" },
  clear: { alignSelf: "flex-start", paddingVertical: 6, paddingHorizontal: 12 },
  clearText: { color: colors.inkMuted, ...type.small },
});
