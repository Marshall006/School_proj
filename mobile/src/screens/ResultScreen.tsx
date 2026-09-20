/**
 * Le verdict, et surtout la correction.
 *
 * En cas de réussite, le code apparait en grand et s'utilisé en un geste.
 * En cas d'échec, pas de code — mais la correction détaillée, avec la réponse
 * attendue, l'explication et, quand c'est possible, le diagnostic de l'erreur.
 * C'est ce qui fait du temps de carence un temps utile.
 */

import { useState } from "react";
import { StyleSheet, Text, View } from "react-native";
import type { Submission } from "@koda/shared";

import {
  Banner,
  Card,
  Chip,
  GhostButton,
  PrimaryButton,
  Screen,
  SectionTitle,
} from "../components/kit";
import { useApp } from "../state/AppState";
import { colors, radius, spacing, type } from "../theme";

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

export function ResultScreen({
  result,
  onUseCode,
  onClose,
  reviewOnly = false,
}: {
  result: Submission;
  onUseCode: (code: string) => void;
  onClose: () => void;
  reviewOnly?: boolean;
}) {
  const { submitCode } = useApp();
  const [showReview, setShowReview] = useState(reviewOnly || !result.passed);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const wrong = result.review.filter((item) => item.is_correct === false).length;
  const right = result.review.filter((item) => item.is_correct === true).length;

  async function useCode() {
    if (!result.unlock_code) return;
    setBusy(true);
    const outcome = await submitCode(result.unlock_code.code);
    setBusy(false);
    if (outcome.ok) onUseCode(result.unlock_code.code);
    else setError(outcome.message ?? "Le code n'a pas été accepté.");
  }

  const tone = result.pending_manual_review ? "gold" : result.passed ? "success" : "soft";

  return (
    <Screen>
      {/* --- La note ------------------------------------------------------ */}
      <Card tone={tone} style={styles.scoreCard}>
        <Text style={styles.badge}>
          {result.pending_manual_review
            ? "⏳ En attente d'un parent"
            : result.passed
              ? "🎉 Réussi !"
              : "Pas encore"}
        </Text>
        <View style={styles.scoreRow}>
          <Text style={[styles.score, result.passed && styles.scorePassed]}>
            {result.score_out_of_20.toFixed(1).replace(".", ",")}
          </Text>
          <Text style={styles.scoreMax}>/ 20</Text>
        </View>
        <Text style={styles.scoreHint}>
          Il fallait {result.pass_score_out_of_20.toFixed(1).replace(".", ",")}/20 ·{" "}
          {right} bonne{right > 1 ? "s" : ""} réponse{right > 1 ? "s" : ""} sur {result.review.length}
        </Text>
        {result.xp_earned > 0 ? <Chip label={`+${result.xp_earned} XP`} tone="gold" icon="⭐" /> : null}
      </Card>

      {result.pending_manual_review ? (
        <Banner tone="gold" title="Une réponse écrite à la main">
          La machine n&apos;a pas su la relire. Un parent va la regarder : tu n&apos;es pas pénalisé.
        </Banner>
      ) : null}

      {/* --- Le code gagne ------------------------------------------------- */}
      {result.unlock_code && !reviewOnly ? (
        <Card style={styles.codeCard}>
          <Text style={styles.codeLabel}>Ton code d&apos;accès</Text>
          <Text style={styles.code}>{result.unlock_code.formatted}</Text>
          <Chip label={`${result.unlock_code.duration_minutes} minutes`} tone="primary" icon="⏱" />
          <PrimaryButton
            label="Utiliser maintenant"
            icon="🔓"
            busy={busy}
            onPress={() => void useCode()}
          />
          {error ? <Banner tone="danger">{error}</Banner> : null}
        </Card>
      ) : null}

      {/* --- Le temps de révision ------------------------------------------ */}
      {result.lockout && !reviewOnly ? (
        <Banner tone="gold" title={`Temps de révision : ${result.lockout.remaining_minutes} min`}>
          Relis la correction ci-dessous. Tu pourras retenter après ce délai — ou plus tot si un
          parent leve l&apos;attente.
        </Banner>
      ) : null}

      {/* --- Le détail des points ------------------------------------------ */}
      {result.xp_detail.length > 0 && !reviewOnly ? (
        <Card tone="soft">
          <SectionTitle>Mes points</SectionTitle>
          {result.xp_detail.map((entry, index) => (
            <View key={index} style={styles.xpRow}>
              <Text style={styles.xpLabel}>{entry.label}</Text>
              <Text style={styles.xpAmount}>+{entry.amount}</Text>
            </View>
          ))}
        </Card>
      ) : null}

      {/* --- La correction -------------------------------------------------- */}
      <GhostButton
        label={
          showReview
            ? "Masquer la correction"
            : `Voir la correction (${wrong} erreur${wrong > 1 ? "s" : ""})`
        }
        icon="📖"
        onPress={() => setShowReview((v) => !v)}
      />

      {showReview
        ? result.review.map((entry) => (
            <Card
              key={entry.position}
              style={[
                styles.reviewCard,
                {
                  borderLeftColor: entry.is_correct
                    ? colors.success
                    : entry.needs_manual_review
                      ? colors.gold
                      : colors.danger,
                },
              ]}
            >
              <View style={styles.reviewHead}>
                <Text style={styles.reviewIndex}>Question {entry.position + 1}</Text>
                {entry.subject_code ? <Chip label={entry.subject_code} /> : null}
                <View style={{ flex: 1 }} />
                <Text style={styles.reviewPoints}>{entry.points}</Text>
              </View>

              <Text style={styles.reviewPrompt}>{entry.prompt}</Text>

              <View style={styles.answerRow}>
                <Text style={styles.answerKey}>Ta réponse</Text>
                <Text style={styles.answerValue}>{formatAnswer(entry.your_answer)}</Text>
              </View>
              {!entry.is_correct ? (
                <View style={styles.answerRow}>
                  <Text style={styles.answerKey}>Attendu</Text>
                  <Text style={[styles.answerValue, styles.expected]}>
                    {formatAnswer(entry.expected)}
                  </Text>
                </View>
              ) : null}

              {entry.diagnosis ? (
                <Banner tone="gold" title="Indice">
                  {entry.diagnosis}
                </Banner>
              ) : null}
              {entry.explanation ? <Text style={styles.explanation}>{entry.explanation}</Text> : null}
            </Card>
          ))
        : null}

      <GhostButton label={reviewOnly ? "Retour" : "Terminer"} onPress={onClose} />
    </Screen>
  );
}

const styles = StyleSheet.create({
  scoreCard: { alignItems: "center", paddingVertical: spacing(3.5) },
  badge: { color: colors.inkSoft, ...type.tiny, textTransform: "uppercase" },
  scoreRow: { flexDirection: "row", alignItems: "baseline", gap: 6 },
  score: { color: colors.ink, fontSize: 64, fontWeight: "800", letterSpacing: -2 },
  scorePassed: { color: colors.successInk },
  scoreMax: { color: colors.inkFaint, fontSize: 24, fontWeight: "700" },
  scoreHint: { color: colors.inkSoft, ...type.small, textAlign: "center" },

  codeCard: { alignItems: "center" },
  codeLabel: { color: colors.inkFaint, ...type.tiny, textTransform: "uppercase" },
  code: { color: colors.primaryDeep, ...type.code },

  xpRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  xpLabel: { color: colors.inkSoft, ...type.small, flex: 1 },
  xpAmount: { color: colors.goldInk, ...type.small, fontWeight: "800" },

  reviewCard: { borderLeftWidth: 5, borderRadius: radius.md },
  reviewHead: { flexDirection: "row", alignItems: "center", gap: spacing(1) },
  reviewIndex: { color: colors.inkFaint, ...type.tiny, textTransform: "uppercase" },
  reviewPoints: { color: colors.inkFaint, ...type.small },
  reviewPrompt: { color: colors.ink, ...type.bodyStrong, lineHeight: 23 },
  answerRow: { flexDirection: "row", gap: spacing(1), alignItems: "flex-start" },
  answerKey: { color: colors.inkFaint, ...type.small, width: 92 },
  answerValue: { color: colors.ink, ...type.small, flex: 1, fontWeight: "600" },
  expected: { color: colors.successInk, fontWeight: "800" },
  explanation: { color: colors.inkSoft, ...type.small, lineHeight: 20 },
});
