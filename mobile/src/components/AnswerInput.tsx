/**
 * Aiguillage de saisie : le bon composant pour la bonne question.
 *
 * Deux modes coexistent, comme le prevoit le cahier des charges :
 *
 * - **assiste** : pave adapte, constructeur de fraction, potence de division,
 *   opération posee, QCM, remise en ordre, associations ;
 * - **manuscrit** : l'ardoise, ou l'enfant pose son calcul comme sur une
 *   feuille. Ce qu'il écrit est transmis tel quel ; si la transcription est
 *   douteuse, c'est un parent qui tranchera plutot que la machine.
 *
 * Le serveur decrit dans `input_spec` le clavier et le gabarit a utiliser :
 * l'interface n'a pas a deviner.
 */

import { useMemo, useState } from "react";
import { ScrollView, StyleSheet, Text, TextInput, TouchableOpacity, View } from "react-native";
import type { AssessmentItem } from "@koda/shared";

import { colors, radius, spacing, type } from "../theme";
import { Keypad, type KeypadMode } from "./Keypad";
import { Slate, type SlateValue } from "./Slate";
import {
  ChoiceList,
  ColumnOperation,
  FractionBuilder,
  LongDivision,
  MatchingBoard,
  OrderingList,
} from "./AssistedInputs";

export type AnswerMode = "assisted" | "handwritten";

export interface AnswerState {
  answer: Record<string, unknown> | null;
  mode: AnswerMode;
  strokes: SlateValue | null;
}

/** Extrait « 1 234 : 7 » d'un enonce pour alimenter la potence. */
function parseDivision(prompt: string): { dividend: string; divisor: string } | null {
  const match = prompt.match(/([\d   ]+)\s*[:÷]\s*(\d+)/);
  if (!match) return null;
  return { dividend: match[1].trim(), divisor: match[2] };
}

/** Extrait « 345 + 678 » pour l'opération posee. */
function parseColumn(prompt: string): { left: string; right: string; operator: string } | null {
  const match = prompt.match(/([\d   ,.]+)\s*([+\-x×])\s*([\d   ,.]+)/);
  if (!match) return null;
  return { left: match[1].trim(), operator: match[2].replace("×", "x"), right: match[3].trim() };
}

export function AnswerInput({
  item,
  state,
  onChange,
}: {
  item: AssessmentItem;
  state: AnswerState;
  onChange: (state: AnswerState) => void;
}) {
  const allowHandwriting = item.input_spec.allow_handwriting !== false;
  const [mode, setMode] = useState<AnswerMode>(state.mode);

  const setAnswer = (answer: Record<string, unknown> | null) =>
    onChange({ ...state, answer, mode });

  const textValue = String((state.answer?.value as string | number | undefined) ?? "");
  const selected = useMemo<string[]>(() => {
    if (!state.answer) return [];
    const single = state.answer.choice as string | undefined;
    const multi = state.answer.choices as string[] | undefined;
    return multi ?? (single ? [single] : []);
  }, [state.answer]);

  function switchMode(next: AnswerMode) {
    setMode(next);
    onChange({ ...state, mode: next });
  }

  const keypadMode: KeypadMode = (item.input_spec.keypad as KeypadMode) ?? "numeric";
  const widget = item.input_spec.widget;

  function appendKey(key: string) {
    if (key === "⌫") {
      setAnswer({ value: textValue.slice(0, -1) });
      return;
    }
    setAnswer({ value: textValue + key });
  }

  // --- Mode manuscrit ------------------------------------------------------
  if (mode === "handwritten" && allowHandwriting) {
    return (
      <View style={{ gap: spacing(1.5) }}>
        <ModeSwitch mode={mode} onChange={switchMode} allowHandwriting={allowHandwriting} />
        <Slate
          value={state.strokes}
          onChange={(strokes) =>
            onChange({
              ...state,
              strokes,
              mode: "handwritten",
              answer: { ...(state.answer ?? {}), has_strokes: strokes.paths.length > 0 },
            })
          }
        />
        <View style={styles.transcriptRow}>
          <Text style={styles.label}>Recopie ton résultat</Text>
          <TextInput
            style={styles.transcript}
            value={String((state.answer?.transcript as string | undefined) ?? "")}
            onChangeText={(text) =>
              onChange({
                ...state,
                mode: "handwritten",
                answer: { ...(state.answer ?? {}), transcript: text, has_strokes: (state.strokes?.paths.length ?? 0) > 0 },
              })
            }
            placeholder="ex. 1 234"
            placeholderTextColor={colors.inkFaint}
            keyboardType="numbers-and-punctuation"
          />
        </View>
        <Text style={styles.caption}>
          Si ton ecriture est difficile a lire, un parent regardera ton ardoise : tu ne seras jamais
          compte faux a cause de la machine.
        </Text>
      </View>
    );
  }

  // --- Mode assiste --------------------------------------------------------
  let control: React.ReactNode = null;

  switch (item.type) {
    case "mcq_single":
    case "true_false":
      control = (
        <ChoiceList
          choices={(item.choices ?? []).map((c) => ({ id: c.id, text: c.text }))}
          selected={selected}
          onToggle={(id) => setAnswer({ choice: id })}
        />
      );
      break;

    case "mcq_multi":
      control = (
        <ChoiceList
          multiple
          choices={(item.choices ?? []).map((c) => ({ id: c.id, text: c.text }))}
          selected={selected}
          onToggle={(id) =>
            setAnswer({
              choices: selected.includes(id) ? selected.filter((s) => s !== id) : [...selected, id],
            })
          }
        />
      );
      break;

    case "ordering":
      control = (
        <OrderingList
          items={(item.choices ?? []).map((c) => ({ id: c.id, text: c.text }))}
          order={(state.answer?.order as string[]) ?? []}
          onChange={(order) => setAnswer({ order })}
        />
      );
      break;

    case "matching": {
      const groups = item.choices ?? [];
      const left = (groups.find((g) => g.id === "left")?.items as string[]) ?? [];
      const right = (groups.find((g) => g.id === "right")?.items as string[]) ?? [];
      control = (
        <MatchingBoard
          left={left}
          right={right}
          pairs={(state.answer?.pairs as Record<string, string>) ?? {}}
          onChange={(pairs) => setAnswer({ pairs })}
        />
      );
      break;
    }

    case "fill_blank": {
      const values = (state.answer?.values as string[]) ?? [];
      const blanks = Math.max(1, (item.prompt.match(/\.\.\./g) ?? ["..."]).length);
      control = (
        <View style={{ gap: spacing(1) }}>
          {Array.from({ length: blanks }).map((_, index) => (
            <View key={index} style={styles.blankRow}>
              <Text style={styles.label}>Trou {index + 1}</Text>
              <TextInput
                style={styles.blankInput}
                value={values[index] ?? ""}
                onChangeText={(text) => {
                  const next = [...values];
                  next[index] = text;
                  setAnswer({ values: next });
                }}
                placeholder="…"
                placeholderTextColor={colors.inkFaint}
              />
            </View>
          ))}
        </View>
      );
      break;
    }

    case "short_text":
      control = (
        <TextInput
          style={styles.textAnswer}
          value={textValue}
          onChangeText={(text) => setAnswer({ value: text })}
          placeholder="Écris ta réponse"
          placeholderTextColor={colors.inkFaint}
          autoCapitalize="none"
          autoCorrect={false}
        />
      );
      break;

    default: {
      // numeric, expression, handwritten en repli assiste
      if (widget === "fraction_builder") {
        control = <FractionBuilder value={textValue} onChange={(value) => setAnswer({ value })} />;
      } else if (widget === "long_division") {
        const parsed = parseDivision(item.prompt);
        control = parsed ? (
          <LongDivision
            dividend={parsed.dividend}
            divisor={parsed.divisor}
            quotient={textValue}
            onQuotientChange={(value) => setAnswer({ value })}
          />
        ) : (
          <BigNumberField value={textValue} onChange={(value) => setAnswer({ value })} />
        );
      } else if (widget === "column_operation") {
        const parsed = parseColumn(item.prompt);
        control = parsed ? (
          <ColumnOperation
            left={parsed.left}
            right={parsed.right}
            operator={parsed.operator}
            value={textValue}
            onChange={(value) => setAnswer({ value })}
          />
        ) : (
          <BigNumberField value={textValue} onChange={(value) => setAnswer({ value })} />
        );
      } else {
        control = <BigNumberField value={textValue} onChange={(value) => setAnswer({ value })} />;
      }
    }
  }

  const showKeypad =
    keypadMode !== "none" &&
    !["mcq_single", "mcq_multi", "true_false", "ordering", "matching", "short_text"].includes(item.type);

  return (
    <View style={{ gap: spacing(2) }}>
      <ModeSwitch mode={mode} onChange={switchMode} allowHandwriting={allowHandwriting} />
      {control}
      {showKeypad && (
        <Keypad
          mode={keypadMode}
          palette={item.input_spec.palette}
          onKey={appendKey}
          onClear={() => setAnswer({ value: "" })}
        />
      )}
    </View>
  );
}

function BigNumberField({ value, onChange }: { value: string; onChange: (value: string) => void }) {
  return (
    <View style={styles.bigFieldWrap}>
      <TextInput
        style={styles.bigField}
        value={value}
        onChangeText={onChange}
        placeholder="—"
        placeholderTextColor={colors.inkFaint}
        keyboardType="numbers-and-punctuation"
        accessibilityLabel="Ta réponse"
      />
    </View>
  );
}

function ModeSwitch({
  mode,
  onChange,
  allowHandwriting,
}: {
  mode: AnswerMode;
  onChange: (mode: AnswerMode) => void;
  allowHandwriting: boolean;
}) {
  if (!allowHandwriting) return null;
  return (
    <View style={styles.modeSwitch}>
      <TouchableOpacity
        style={[styles.modeButton, mode === "assisted" && styles.modeButtonActive]}
        onPress={() => onChange("assisted")}
      >
        <Text style={[styles.modeText, mode === "assisted" && styles.modeTextActive]}>✏️  Mode assiste</Text>
      </TouchableOpacity>
      <TouchableOpacity
        style={[styles.modeButton, mode === "handwritten" && styles.modeButtonActive]}
        onPress={() => onChange("handwritten")}
      >
        <Text style={[styles.modeText, mode === "handwritten" && styles.modeTextActive]}>🖐  Ardoise</Text>
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  modeSwitch: {
    flexDirection: "row",
    gap: 4,
    backgroundColor: colors.surfaceAlt,
    padding: 5,
    borderRadius: radius.pill,
    alignSelf: "stretch",
  },
  modeButton: {
    flex: 1,
    minHeight: 44,
    alignItems: "center",
    justifyContent: "center",
    borderRadius: radius.pill,
  },
  modeButtonActive: {
    backgroundColor: colors.surface,
    shadowColor: "#0f1d3d",
    shadowOpacity: 0.1,
    shadowRadius: 8,
    shadowOffset: { width: 0, height: 2 },
    elevation: 2,
  },
  modeText: { color: colors.inkSoft, ...type.small, fontWeight: "600" },
  modeTextActive: { color: colors.primaryDeep, fontWeight: "800" },

  bigFieldWrap: { alignItems: "center" },
  bigField: {
    minWidth: 200,
    textAlign: "center",
    fontSize: 40,
    fontWeight: "700",
    color: colors.ink,
    paddingVertical: spacing(1),
    borderBottomWidth: 3,
    borderBottomColor: colors.primary,
  },
  textAnswer: {
    fontSize: 20,
    color: colors.ink,
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    padding: spacing(2),
    borderWidth: 1,
    borderColor: colors.line,
  },
  blankRow: { flexDirection: "row", alignItems: "center", gap: spacing(1.5) },
  blankInput: {
    flex: 1,
    fontSize: 18,
    color: colors.ink,
    backgroundColor: colors.surface,
    borderRadius: radius.sm,
    padding: spacing(1.5),
    borderWidth: 1,
    borderColor: colors.line,
  },
  label: { color: colors.inkSoft, ...type.small, minWidth: 96 },
  caption: { color: colors.inkFaint, ...type.small },
  transcriptRow: { flexDirection: "row", alignItems: "center", gap: spacing(1.5) },
  transcript: {
    flex: 1,
    fontSize: 22,
    fontWeight: "700",
    color: colors.ink,
    backgroundColor: colors.surface,
    borderRadius: radius.sm,
    padding: spacing(1.5),
    borderWidth: 1,
    borderColor: colors.line,
  },
});
