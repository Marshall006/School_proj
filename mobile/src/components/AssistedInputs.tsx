/**
 * Composants de saisie assistee (le « mode assiste » du cahier des charges).
 *
 * Chaque gabarit reproduit la disposition apprise en classe :
 *
 * - `FractionBuilder` : la barre de fraction, avec numerateur et denominateur
 *   dans deux cases distinctes (on ne tape pas « 3/4 » à la main) ;
 * - `LongDivision` : la potence de la division posee, avec la barre verticale
 *   et la barre horizontale que l'enfant connait ;
 * - `ColumnOperation` : l'opération posee en colonnes, chiffres alignes ;
 * - `ChoiceList`, `OrderingList`, `MatchingBoard` : QCM, remise en ordre et
 *   associations, manipules au doigt.
 */

import { useState } from "react";
import { StyleSheet, Text, TextInput, TouchableOpacity, View } from "react-native";

import { colors, radius, spacing, type } from "../theme";

// ---------------------------------------------------------------------------
// Fraction
// ---------------------------------------------------------------------------

export function FractionBuilder({
  value,
  onChange,
}: {
  value: string;
  onChange: (value: string) => void;
}) {
  const [numerator, denominator] = value.includes("/") ? value.split("/") : [value, ""];

  const update = (top: string, bottom: string) =>
    onChange(bottom.length > 0 ? `${top}/${bottom}` : top);

  return (
    <View style={styles.fractionWrap}>
      <View style={styles.fraction}>
        <TextInput
          style={styles.fractionInput}
          value={numerator}
          onChangeText={(text) => update(text.replace(/[^\d-]/g, ""), denominator)}
          keyboardType="number-pad"
          placeholder="—"
          placeholderTextColor={colors.inkFaint}
          accessibilityLabel="Numerateur"
        />
        <View style={styles.fractionBar} />
        <TextInput
          style={styles.fractionInput}
          value={denominator}
          onChangeText={(text) => update(numerator, text.replace(/[^\d]/g, ""))}
          keyboardType="number-pad"
          placeholder="—"
          placeholderTextColor={colors.inkFaint}
          accessibilityLabel="Denominateur"
        />
      </View>
      <Text style={styles.caption}>Écris le numerateur en haut, le denominateur en bas.</Text>
    </View>
  );
}

// ---------------------------------------------------------------------------
// Division posee
// ---------------------------------------------------------------------------

export function LongDivision({
  dividend,
  divisor,
  quotient,
  onQuotientChange,
  remainder,
  onRemainderChange,
}: {
  dividend: string;
  divisor: string;
  quotient: string;
  onQuotientChange: (value: string) => void;
  remainder?: string;
  onRemainderChange?: (value: string) => void;
}) {
  return (
    <View style={styles.divisionWrap}>
      <View style={styles.divisionRow}>
        <View style={styles.divisionLeft}>
          <Text style={styles.divisionNumber}>{dividend}</Text>
        </View>
        <View style={styles.divisionBarVertical} />
        <View style={styles.divisionRight}>
          <Text style={styles.divisionNumber}>{divisor}</Text>
          <View style={styles.divisionBarHorizontal} />
          <TextInput
            style={styles.divisionInput}
            value={quotient}
            onChangeText={(text) => onQuotientChange(text.replace(/[^\d]/g, ""))}
            keyboardType="number-pad"
            placeholder="quotient"
            placeholderTextColor={colors.inkFaint}
            accessibilityLabel="Quotient"
          />
        </View>
      </View>
      {onRemainderChange && (
        <View style={styles.remainderRow}>
          <Text style={styles.caption}>Reste</Text>
          <TextInput
            style={[styles.divisionInput, styles.remainderInput]}
            value={remainder ?? ""}
            onChangeText={(text) => onRemainderChange(text.replace(/[^\d]/g, ""))}
            keyboardType="number-pad"
            placeholder="0"
            placeholderTextColor={colors.inkFaint}
            accessibilityLabel="Reste"
          />
        </View>
      )}
      <Text style={styles.caption}>La potence : le dividende a gauche, le diviseur a droite.</Text>
    </View>
  );
}

// ---------------------------------------------------------------------------
// Opération posee en colonnes
// ---------------------------------------------------------------------------

export function ColumnOperation({
  left,
  right,
  operator,
  value,
  onChange,
}: {
  left: string;
  right: string;
  operator: string;
  value: string;
  onChange: (value: string) => void;
}) {
  const width = Math.max(left.length, right.length, value.length, 4);
  return (
    <View style={styles.columnWrap}>
      <Text style={[styles.columnNumber, { minWidth: width * 20 }]}>{left}</Text>
      <View style={styles.columnLine}>
        <Text style={styles.columnOperator}>{operator}</Text>
        <Text style={[styles.columnNumber, { minWidth: width * 20 }]}>{right}</Text>
      </View>
      <View style={styles.columnRule} />
      <TextInput
        style={[styles.columnInput, { minWidth: width * 20 }]}
        value={value}
        onChangeText={(text) => onChange(text.replace(/[^\d,.\-]/g, ""))}
        keyboardType="numbers-and-punctuation"
        placeholder="résultat"
        placeholderTextColor={colors.inkFaint}
        accessibilityLabel="Résultat de l'opération"
      />
    </View>
  );
}

// ---------------------------------------------------------------------------
// QCM
// ---------------------------------------------------------------------------

export interface Choice {
  id: string;
  text?: string;
}

export function ChoiceList({
  choices,
  selected,
  multiple,
  onToggle,
}: {
  choices: Choice[];
  selected: string[];
  multiple?: boolean;
  onToggle: (id: string) => void;
}) {
  return (
    <View style={{ gap: spacing(1) }}>
      {choices.map((choice) => {
        const active = selected.includes(choice.id);
        return (
          <TouchableOpacity
            key={choice.id}
            style={[styles.choice, active && styles.choiceActive]}
            onPress={() => onToggle(choice.id)}
            accessibilityRole={multiple ? "checkbox" : "radio"}
            accessibilityState={{ checked: active }}
          >
            <View style={[styles.choiceMark, multiple && styles.choiceMarkSquare, active && styles.choiceMarkActive]}>
              {active && <Text style={styles.choiceMarkText}>✓</Text>}
            </View>
            <Text style={[styles.choiceText, active && styles.choiceTextActive]}>{choice.text ?? choice.id}</Text>
          </TouchableOpacity>
        );
      })}
      {multiple && <Text style={styles.caption}>Plusieurs réponses sont possibles.</Text>}
    </View>
  );
}

// ---------------------------------------------------------------------------
// Remise en ordre
// ---------------------------------------------------------------------------

export function OrderingList({
  items,
  order,
  onChange,
}: {
  items: Choice[];
  order: string[];
  onChange: (order: string[]) => void;
}) {
  const current = order.length === items.length ? order : items.map((item) => item.id);

  function move(index: number, direction: -1 | 1) {
    const target = index + direction;
    if (target < 0 || target >= current.length) return;
    const next = [...current];
    const moved = next[index];
    next[index] = next[target];
    next[target] = moved;
    onChange(next);
  }

  return (
    <View style={{ gap: spacing(1) }}>
      {current.map((id, index) => {
        const item = items.find((candidate) => candidate.id === id);
        return (
          <View key={id} style={styles.orderRow}>
            <Text style={styles.orderIndex}>{index + 1}</Text>
            <Text style={styles.orderText}>{item?.text ?? id}</Text>
            <TouchableOpacity style={styles.orderButton} onPress={() => move(index, -1)} accessibilityLabel="Monter">
              <Text style={styles.orderButtonText}>▲</Text>
            </TouchableOpacity>
            <TouchableOpacity style={styles.orderButton} onPress={() => move(index, 1)} accessibilityLabel="Descendre">
              <Text style={styles.orderButtonText}>▼</Text>
            </TouchableOpacity>
          </View>
        );
      })}
    </View>
  );
}

// ---------------------------------------------------------------------------
// Associations
// ---------------------------------------------------------------------------

export function MatchingBoard({
  left,
  right,
  pairs,
  onChange,
}: {
  left: string[];
  right: string[];
  pairs: Record<string, string>;
  onChange: (pairs: Record<string, string>) => void;
}) {
  const [active, setActive] = useState<string | null>(null);

  function pick(rightValue: string) {
    if (!active) return;
    onChange({ ...pairs, [active]: rightValue });
    setActive(null);
  }

  return (
    <View style={{ gap: spacing(1.5) }}>
      {left.map((item) => (
        <View key={item} style={styles.matchRow}>
          <TouchableOpacity
            style={[styles.matchLeft, active === item && styles.matchLeftActive]}
            onPress={() => setActive(active === item ? null : item)}
          >
            <Text style={styles.choiceText}>{item}</Text>
          </TouchableOpacity>
          <Text style={styles.matchArrow}>→</Text>
          <View style={[styles.matchTarget, pairs[item] ? styles.matchTargetFilled : null]}>
            <Text style={pairs[item] ? styles.choiceTextActive : styles.caption}>
              {pairs[item] ?? "a relier"}
            </Text>
          </View>
        </View>
      ))}

      <Text style={styles.caption}>
        {active ? `Choisis la réponse pour « ${active} »` : "Touche un élément de gauche, puis sa réponse."}
      </Text>
      <View style={styles.matchOptions}>
        {right.map((option) => (
          <TouchableOpacity
            key={option}
            style={[styles.matchOption, !active && styles.matchOptionDisabled]}
            onPress={() => pick(option)}
            disabled={!active}
          >
            <Text style={styles.choiceText}>{option}</Text>
          </TouchableOpacity>
        ))}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  caption: { color: colors.inkFaint, ...type.small },

  fractionWrap: { alignItems: "center", gap: spacing(1) },
  fraction: { alignItems: "center", gap: 4 },
  fractionInput: {
    minWidth: 96,
    textAlign: "center",
    fontSize: 30,
    fontWeight: "700",
    color: colors.ink,
    paddingVertical: 6,
  },
  fractionBar: { height: 3, width: 110, backgroundColor: colors.ink, borderRadius: 2 },

  divisionWrap: { gap: spacing(1) },
  divisionRow: { flexDirection: "row", alignItems: "flex-start" },
  divisionLeft: { paddingRight: spacing(1.5), paddingTop: 2 },
  divisionNumber: { color: colors.ink, fontSize: 28, fontWeight: "700", letterSpacing: 2 },
  divisionBarVertical: { width: 3, minHeight: 96, backgroundColor: colors.ink, borderRadius: 2 },
  divisionRight: { paddingLeft: spacing(1.5), alignItems: "flex-start" },
  divisionBarHorizontal: { height: 3, width: 120, backgroundColor: colors.ink, marginVertical: 6, borderRadius: 2 },
  divisionInput: { color: colors.ink, fontSize: 26, fontWeight: "700", minWidth: 120, paddingVertical: 4 },
  remainderRow: { flexDirection: "row", alignItems: "center", gap: spacing(1) },
  remainderInput: { fontSize: 20, minWidth: 70 },

  columnWrap: { alignItems: "flex-end", alignSelf: "center", gap: 2 },
  columnNumber: { color: colors.ink, fontSize: 28, fontWeight: "700", textAlign: "right", letterSpacing: 3 },
  columnLine: { flexDirection: "row", alignItems: "center", gap: spacing(1) },
  columnOperator: { color: colors.primary, fontSize: 24, fontWeight: "700" },
  columnRule: { height: 3, width: 160, backgroundColor: colors.ink, marginVertical: 6, borderRadius: 2 },
  columnInput: { color: colors.primary, fontSize: 28, fontWeight: "700", textAlign: "right", letterSpacing: 3 },

  choice: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing(1.5),
    padding: spacing(2),
    borderRadius: radius.md,
    backgroundColor: colors.surface,
    borderWidth: 2,
    borderColor: colors.line,
  },
  choiceActive: { borderColor: colors.primary, backgroundColor: colors.surfaceAlt },
  choiceMark: {
    width: 26,
    height: 26,
    borderRadius: 13,
    borderWidth: 2,
    borderColor: colors.inkFaint,
    alignItems: "center",
    justifyContent: "center",
  },
  choiceMarkSquare: { borderRadius: 7 },
  choiceMarkActive: { borderColor: colors.primary, backgroundColor: colors.primary },
  choiceMarkText: { color: colors.onPrimary, fontWeight: "800", fontSize: 15 },
  choiceText: { color: colors.ink, fontSize: 17, flex: 1 },
  choiceTextActive: { color: colors.ink, fontSize: 17, fontWeight: "600", flex: 1 },

  orderRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing(1),
    padding: spacing(1.5),
    borderRadius: radius.md,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.line,
  },
  orderIndex: {
    width: 28,
    height: 28,
    borderRadius: 14,
    backgroundColor: colors.primary,
    color: colors.onPrimary,
    textAlign: "center",
    lineHeight: 28,
    fontWeight: "800",
  },
  orderText: { color: colors.ink, fontSize: 16, flex: 1 },
  orderButton: { padding: 8, borderRadius: radius.sm, backgroundColor: colors.surfaceAlt },
  orderButtonText: { color: colors.ink, fontSize: 13 },

  matchRow: { flexDirection: "row", alignItems: "center", gap: spacing(1) },
  matchLeft: {
    flex: 1,
    padding: spacing(1.5),
    borderRadius: radius.md,
    backgroundColor: colors.surface,
    borderWidth: 2,
    borderColor: colors.line,
  },
  matchLeftActive: { borderColor: colors.primary },
  matchArrow: { color: colors.inkFaint, fontSize: 18 },
  matchTarget: {
    flex: 1,
    padding: spacing(1.5),
    borderRadius: radius.md,
    borderWidth: 2,
    borderStyle: "dashed",
    borderColor: colors.line,
  },
  matchTargetFilled: { borderStyle: "solid", borderColor: colors.primary, backgroundColor: colors.surfaceAlt },
  matchOptions: { flexDirection: "row", flexWrap: "wrap", gap: spacing(1) },
  matchOption: {
    paddingVertical: spacing(1),
    paddingHorizontal: spacing(1.5),
    borderRadius: radius.pill,
    backgroundColor: colors.surfaceAlt,
    borderWidth: 1,
    borderColor: colors.line,
  },
  matchOptionDisabled: { opacity: 0.45 },
});
