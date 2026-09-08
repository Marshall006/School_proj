/**
 * Le verdict, et surtout la correction.
 *
 * En cas de reussite : le code apparait, gros, et s'utilise en un geste.
 * En cas d'echec : pas de code, mais la correction detaillee, question par
 * question, avec l'explication et — quand c'est possible — le diagnostic de
 * l'erreur. C'est ce qui rend le temps de carence utile plutot que punitif.
 */

import { useState } from "react";
import { ScrollView, StyleSheet, Text, TouchableOpacity, View } from "react-native";
import type { Submission } from "@koda/shared";

import { useApp } from "../state/AppState";
import { colors, radius, spacing, type } from "../theme";

export function ResultScreen({
  result,
  onUseCode,
  onClose,
}: {
  result: Submission;
  onUseCode: (code: string) => void;
  onClose: () => void;
}) {
  const { submitCode } = useApp();
  const [showReview, setShowReview] = useState(!result.passed);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function useCode() {
    if (!result.unlock_code) return;
    setBusy(true);
    const outcome = await submitCode(result.unlock_code.code);
    setBusy(false);
    if (outcome.ok) {
      onUseCode(result.unlock_code.code);
    } else {
      setError(outcome.message ?? "Le code n'a pas ete accepte.");
    }
  }

  const wrong = result.review.filter((item) => item.is_correct === false);

  return (
    <ScrollView style={styles.root} contentContainerStyle={styles.content}>
      <View style={[styles.scoreCard, result.passed ? styles.scoreCardPassed : styles.scoreCardFailed]}>
        <Text style={styles.scoreLabel}>
          {result.pending_manual_review
            ? "En attente d'un parent"
            : result.passed
              ? "Reussi"
              : "Pas encore"}
        </Text>
        <Text style={styles.scoreValue}>
          {result.score_out_of_20.toFixed(1).replace(".", ",")}
          <Text style={styles.scoreMax}> / 20</Text>
        </Text>
        <Text style={styles.scoreHint}>
          Il fallait {result.pass_score_out_of_20.toFixed(1).replace(".", ",")}/20
        </Text>
        {result.xp_earned > 0 && <Text style={styles.xp}>+{result.xp_earned} XP</Text>}
      </View>

      {result.pending_manual_review && (
        <View style={styles.infoCard}>
          <Text style={styles.infoText}>
            Une de tes reponses a ete ecrite a la main et la machine n&apos;a pas su la lire. Un
            parent va la regarder : tu n&apos;es pas penalise.
          </Text>
        </View>
      )}

      {result.unlock_code && (
        <View style={styles.codeCard}>
          <Text style={styles.codeLabel}>Ton code d&apos;acces</Text>
          <Text style={styles.code}>{result.unlock_code.formatted}</Text>
          <Text style={styles.codeHint}>{result.unlock_code.duration_minutes} minutes de temps d&apos;ecran</Text>
          <TouchableOpacity style={styles.primaryButton} onPress={() => void useCode()} disabled={busy}>
            <Text style={styles.primaryText}>{busy ? "Ouverture…" : "Utiliser maintenant"}</Text>
          </TouchableOpacity>
          {error && <Text style={styles.error}>{error}</Text>}
        </View>
      )}

      {result.lockout && (
        <View style={styles.cooldownCard}>
          <Text style={styles.cooldownTitle}>Temps de revision : {result.lockout.remaining_minutes} min</Text>
          <Text style={styles.cooldownText}>
            Relis la correction ci-dessous. Tu pourras retenter apres ce delai — ou plus tot si un
            parent leve l&apos;attente.
          </Text>
        </View>
      )}

      {result.xp_detail.length > 0 && (
        <View style={styles.xpCard}>
          {result.xp_detail.map((entry, index) => (
            <View key={index} style={styles.xpRow}>
              <Text style={styles.xpLabel}>{entry.label}</Text>
              <Text style={styles.xpAmount}>+{entry.amount}</Text>
            </View>
          ))}
        </View>
      )}

      <TouchableOpacity style={styles.toggle} onPress={() => setShowReview((v) => !v)}>
        <Text style={styles.toggleText}>
          {showReview ? "Masquer la correction" : `Voir la correction (${wrong.length} erreur${wrong.length > 1 ? "s" : ""})`}
        </Text>
      </TouchableOpacity>

      {showReview &&
        result.review.map((entry) => (
          <View
            key={entry.position}
            style={[
              styles.reviewCard,
              entry.is_correct ? styles.reviewOk : entry.needs_manual_review ? styles.reviewPending : styles.reviewKo,
            ]}
          >
            <View style={styles.reviewHead}>
              <Text style={styles.reviewIndex}>Question {entry.position + 1}</Text>
              <Text style={styles.reviewPoints}>{entry.points}</Text>
            </View>
            <Text style={styles.reviewPrompt}>{entry.prompt}</Text>

            <View style={styles.reviewLine}>
              <Text style={styles.reviewKey}>Ta reponse</Text>
              <Text style={styles.reviewValue}>{formatAnswer(entry.your_answer)}</Text>
            </View>
            {!entry.is_correct && (
              <View style={styles.reviewLine}>
                <Text style={styles.reviewKey}>Attendu</Text>
                <Text style={[styles.reviewValue, styles.reviewExpected]}>{formatAnswer(entry.expected)}</Text>
              </View>
            )}

            {entry.diagnosis && <Text style={styles.diagnosis}>💡 {entry.diagnosis}</Text>}
            {entry.explanation && <Text style={styles.explanation}>{entry.explanation}</Text>}
          </View>
        ))}

      <TouchableOpacity style={styles.secondaryButton} onPress={onClose}>
        <Text style={styles.secondaryText}>Retour</Text>
      </TouchableOpacity>
    </ScrollView>
  );
}

function formatAnswer(value: unknown): string {
  if (value === null || value === undefined || value === "") return "—";
  if (Array.isArray(value)) return value.join(", ");
  if (typeof value === "object") {
    return Object.entries(value as Record<string, unknown>)
      .map(([key, item]) => `${key} → ${String(item)}`)
      .join(", ");
  }
  return String(value);
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.bg },
  content: { padding: spacing(2.5), gap: spacing(2), paddingTop: spacing(6), paddingBottom: spacing(6) },

  scoreCard: { borderRadius: radius.lg, padding: spacing(3), alignItems: "center", gap: 4 },
  scoreCardPassed: { backgroundColor: colors.success },
  scoreCardFailed: { backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border },
  scoreLabel: { color: colors.successInk, ...type.small, fontWeight: "800", textTransform: "uppercase", letterSpacing: 1 },
  scoreValue: { color: colors.successInk, fontSize: 54, fontWeight: "800" },
  scoreMax: { fontSize: 24, fontWeight: "600" },
  scoreHint: { color: colors.successInk, ...type.small, opacity: 0.75 },
  xp: { color: colors.successInk, fontWeight: "800", marginTop: 4 },

  infoCard: { backgroundColor: colors.surface, borderRadius: radius.md, padding: spacing(2), borderWidth: 1, borderColor: colors.warning },
  infoText: { color: colors.inkMuted, ...type.body, lineHeight: 22 },

  codeCard: { backgroundColor: colors.surface, borderRadius: radius.lg, padding: spacing(3), alignItems: "center", gap: spacing(1) },
  codeLabel: { color: colors.inkMuted, ...type.small },
  code: { color: colors.ink, ...type.code },
  codeHint: { color: colors.inkMuted, ...type.small },
  primaryButton: { backgroundColor: colors.accent, borderRadius: radius.md, paddingVertical: spacing(1.5), paddingHorizontal: spacing(3), marginTop: spacing(1) },
  primaryText: { color: colors.accentInk, fontWeight: "800", fontSize: 16 },
  error: { color: colors.danger, ...type.small },

  cooldownCard: { backgroundColor: colors.surface, borderRadius: radius.md, padding: spacing(2), borderWidth: 1, borderColor: colors.warning, gap: 6 },
  cooldownTitle: { color: colors.warning, fontWeight: "800" },
  cooldownText: { color: colors.inkMuted, ...type.small, lineHeight: 20 },

  xpCard: { backgroundColor: colors.surface, borderRadius: radius.md, padding: spacing(2), gap: 6 },
  xpRow: { flexDirection: "row", justifyContent: "space-between" },
  xpLabel: { color: colors.inkMuted, ...type.small },
  xpAmount: { color: colors.success, ...type.small, fontWeight: "800" },

  toggle: { alignItems: "center", paddingVertical: spacing(1) },
  toggleText: { color: colors.accent, fontWeight: "700" },

  reviewCard: { backgroundColor: colors.surface, borderRadius: radius.md, padding: spacing(2), gap: 6, borderLeftWidth: 4 },
  reviewOk: { borderLeftColor: colors.success },
  reviewKo: { borderLeftColor: colors.danger },
  reviewPending: { borderLeftColor: colors.warning },
  reviewHead: { flexDirection: "row", justifyContent: "space-between" },
  reviewIndex: { color: colors.inkFaint, ...type.small, fontWeight: "700" },
  reviewPoints: { color: colors.inkFaint, ...type.small },
  reviewPrompt: { color: colors.ink, ...type.body, lineHeight: 22 },
  reviewLine: { flexDirection: "row", gap: spacing(1) },
  reviewKey: { color: colors.inkFaint, ...type.small, width: 88 },
  reviewValue: { color: colors.ink, ...type.small, flex: 1 },
  reviewExpected: { color: colors.success, fontWeight: "700" },
  diagnosis: { color: colors.warning, ...type.small, lineHeight: 20 },
  explanation: { color: colors.inkMuted, ...type.small, lineHeight: 20 },

  secondaryButton: { alignSelf: "center", paddingVertical: spacing(1.5), paddingHorizontal: spacing(3), borderRadius: radius.md, backgroundColor: colors.surface },
  secondaryText: { color: colors.ink, fontWeight: "600" },
});
