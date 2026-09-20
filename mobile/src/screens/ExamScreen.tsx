/**
 * L'examen.
 *
 * Conditions d'un devoir : une question à la fois, un chronometre visible, pas
 * de sortie accidentelle. Les réponses sont sauvegardees au fil de l'eau — une
 * coupure ne fait rien perdre — et l'envoi final regroupe tout, ce qui permet
 * de composer entierement hors ligne.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ActivityIndicator, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import type { Assessment, Submission } from "@koda/shared";

import { ApiError, NetworkError, api } from "../api/client";
import { AnswerInput, type AnswerState } from "../components/AnswerInput";
import { Banner, Chip, GhostButton, PrimaryButton } from "../components/kit";
import { confirmAsync } from "../lib/confirm";
import { useApp } from "../state/AppState";
import { colors, elevation, radius, spacing, type } from "../theme";

const BUCKET_LABEL: Record<string, string> = {
  remediation: "A consolider",
  apprentissage: "Programme en cours",
  consolidation: "Tu maîtrises déjà",
};
const BUCKET_TONE: Record<string, "gold" | "primary" | "success"> = {
  remediation: "gold",
  apprentissage: "primary",
  consolidation: "success",
};

export function ExamScreen({
  kind,
  onFinished,
  onCancel,
}: {
  kind: "unlock" | "practice";
  onFinished: (result: Submission) => void;
  onCancel: () => void;
}) {
  const { identity } = useApp();
  const [exam, setExam] = useState<Assessment | null>(null);
  const [index, setIndex] = useState(0);
  const [answers, setAnswers] = useState<Record<string, AnswerState>>({});
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [remaining, setRemaining] = useState<number | null>(null);
  const startedAt = useRef(Date.now());
  const questionStart = useRef(Date.now());
  const backgroundCount = useRef(0);

  useEffect(() => {
    if (!identity) return;
    void (async () => {
      setBusy(true);
      try {
        const current = await api.currentAssessment(identity.deviceToken).catch(() => null);
        const assessment =
          current && current.kind === kind
            ? current
            : await api.startAssessment(identity.deviceToken, kind);
        setExam(assessment);
        setAnswers(
          Object.fromEntries(
            assessment.items.map((item) => [
              item.id,
              {
                answer: item.answer ?? null,
                mode: (item.answer_mode as AnswerState["mode"]) ?? "assisted",
                strokes: null,
              },
            ]),
          ),
        );
      } catch (err) {
        setError(
          err instanceof ApiError
            ? err.message
            : err instanceof NetworkError
              ? "Impossible de charger l'évaluation sans connexion."
              : "Erreur inattendue.",
        );
      } finally {
        setBusy(false);
      }
    })();
  }, [identity, kind]);

  useEffect(() => {
    if (!exam?.time_limit_seconds) return;
    const tick = () => {
      const elapsed = Math.round((Date.now() - startedAt.current) / 1000);
      const left = (exam.time_limit_seconds ?? 0) - elapsed;
      setRemaining(Math.max(0, left));
      if (left <= 0) void submit(true);
    };
    tick();
    const timer = setInterval(tick, 1000);
    return () => clearInterval(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [exam]);

  const item = exam?.items[index];

  const isAnswered = useCallback(
    (state: AnswerState | undefined) =>
      Boolean(state?.answer && Object.keys(state.answer).length > 0) ||
      Boolean(state?.strokes?.paths.length),
    [],
  );
  const answered = useMemo(
    () => Object.values(answers).filter(isAnswered).length,
    [answers, isAnswered],
  );

  const saveCurrent = useCallback(
    async (itemId: string, state: AnswerState) => {
      if (!identity || !exam) return;
      try {
        await api.saveAnswer(identity.deviceToken, exam.id, itemId, {
          answer: state.answer,
          answer_mode: state.mode,
          strokes: state.strokes ? (state.strokes as unknown as Record<string, unknown>) : null,
          time_spent_ms: Date.now() - questionStart.current,
        });
      } catch {
        // Hors ligne : la réponse partira avec l'envoi final.
      }
    },
    [identity, exam],
  );

  function goTo(next: number) {
    if (!exam || !item) return;
    void saveCurrent(item.id, answers[item.id]);
    questionStart.current = Date.now();
    setIndex(Math.max(0, Math.min(exam.items.length - 1, next)));
  }

  async function submit(auto = false) {
    if (!identity || !exam || busy) return;
    setBusy(true);
    setError(null);
    try {
      const result = await api.submit(identity.deviceToken, exam.id, {
        answers: Object.fromEntries(
          Object.entries(answers).map(([id, state]) => [
            id,
            { answer: state.answer, answer_mode: state.mode, strokes: state.strokes ?? null },
          ]),
        ),
        integrity: {
          duration_seconds: Math.round((Date.now() - startedAt.current) / 1000),
          background_events: backgroundCount.current,
          auto_submitted: auto,
        },
      });
      onFinished(result);
    } catch (err) {
      setError(
        err instanceof NetworkError
          ? "Envoi impossible : reconnecte-toi puis réessaie. Tes réponses sont gardées."
          : err instanceof ApiError
            ? err.message
            : "Envoi impossible.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function confirmSubmit() {
    const missing = (exam?.items.length ?? 0) - answered;
    if (missing > 0) {
      const ok = await confirmAsync({
        title: "Envoyer maintenant ?",
        message: `Il te reste ${missing} question${missing > 1 ? "s" : ""} sans réponse.`,
        confirmLabel: "Envoyer quand même",
        cancelLabel: "Continuer l'examen",
      });
      if (!ok) return;
    }
    await submit();
  }

  async function quit() {
    const ok = await confirmAsync({
      title: "Quitter l'évaluation ?",
      message: "Tes réponses sont gardées, tu pourras reprendre ou tu en etais.",
      confirmLabel: "Quitter",
      cancelLabel: "Continuer",
    });
    if (ok) onCancel();
  }

  if (error && !exam) {
    return (
      <View style={styles.center}>
        <Banner tone="danger" title="Évaluation indisponible">
          {error}
        </Banner>
        <GhostButton label="Retour" onPress={onCancel} />
      </View>
    );
  }

  if (!exam || !item) {
    return (
      <View style={styles.center}>
        <ActivityIndicator color={colors.primary} size="large" />
        <Text style={styles.loading}>Je prépare tes questions…</Text>
      </View>
    );
  }

  const bucket = (item as unknown as { bucket?: string }).bucket;
  const urgent = remaining !== null && remaining < 60;

  return (
    <View style={styles.root}>
      {/* --- Barre haute ---------------------------------------------------- */}
      <View style={styles.topBar}>
        <Pressable onPress={() => void quit()} accessibilityLabel="Quitter" style={styles.quitButton}>
          <Text style={styles.quit}>✕</Text>
        </Pressable>
        <View style={{ flex: 1 }}>
          <Text style={styles.counter}>
            Question {index + 1} sur {exam.items.length}
          </Text>
          <View style={styles.dots}>
            {exam.items.map((candidate, position) => (
              <Pressable
                key={candidate.id}
                onPress={() => goTo(position)}
                accessibilityLabel={`Aller à la question ${position + 1}`}
                style={[
                  styles.dot,
                  isAnswered(answers[candidate.id]) && styles.dotAnswered,
                  position === index && styles.dotCurrent,
                ]}
              />
            ))}
          </View>
        </View>
        {remaining !== null ? (
          <Chip
            label={`${Math.floor(remaining / 60)}:${String(remaining % 60).padStart(2, "0")}`}
            tone={urgent ? "danger" : "neutral"}
            icon="⏱"
          />
        ) : null}
      </View>

      {/* --- La question ----------------------------------------------------- */}
      <ScrollView contentContainerStyle={styles.content}>
        {bucket ? (
          <Chip label={BUCKET_LABEL[bucket] ?? bucket} tone={BUCKET_TONE[bucket] ?? "primary"} />
        ) : null}

        {item.instructions ? (
          <View style={styles.instructions}>
            <Text style={styles.instructionsText}>{item.instructions}</Text>
          </View>
        ) : null}

        <Text style={styles.prompt}>{item.prompt}</Text>

        <AnswerInput
          item={item}
          state={answers[item.id] ?? { answer: null, mode: "assisted", strokes: null }}
          onChange={(state) => setAnswers((current) => ({ ...current, [item.id]: state }))}
        />

        {error ? <Banner tone="danger">{error}</Banner> : null}
      </ScrollView>

      {/* --- Barre basse ----------------------------------------------------- */}
      <View style={styles.bottomBar}>
        <View style={{ flex: 1 }}>
          <GhostButton label="Précédent" onPress={() => goTo(index - 1)} disabled={index === 0} />
        </View>
        <View style={{ flex: 1.4 }}>
          {index < exam.items.length - 1 ? (
            <PrimaryButton label="Suivant" onPress={() => goTo(index + 1)} />
          ) : (
            <PrimaryButton
              label="Terminer"
              icon="✓"
              tone="success"
              busy={busy}
              onPress={() => void confirmSubmit()}
            />
          )}
        </View>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.bg },
  center: {
    flex: 1,
    backgroundColor: colors.bg,
    alignItems: "center",
    justifyContent: "center",
    gap: spacing(2),
    padding: spacing(3),
  },
  loading: { color: colors.inkSoft, ...type.body },

  topBar: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing(1.5),
    paddingHorizontal: spacing(2.5),
    paddingTop: spacing(6),
    paddingBottom: spacing(1.5),
    backgroundColor: colors.surface,
    borderBottomLeftRadius: radius.lg,
    borderBottomRightRadius: radius.lg,
    ...elevation.card,
  },
  quitButton: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: colors.surfaceAlt,
    alignItems: "center",
    justifyContent: "center",
  },
  quit: { color: colors.inkSoft, fontSize: 17, fontWeight: "800" },
  counter: { color: colors.ink, ...type.small, fontWeight: "800" },
  dots: { flexDirection: "row", gap: 4, marginTop: 6, flexWrap: "wrap" },
  dot: { width: 16, height: 6, borderRadius: 3, backgroundColor: colors.line },
  dotAnswered: { backgroundColor: colors.success },
  dotCurrent: { backgroundColor: colors.primary, width: 24 },

  content: { padding: spacing(2.5), gap: spacing(2.5), paddingBottom: spacing(5) },
  instructions: {
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    padding: spacing(2),
    borderLeftWidth: 4,
    borderLeftColor: colors.primary,
  },
  instructionsText: { color: colors.inkSoft, ...type.body, lineHeight: 24 },
  prompt: { color: colors.ink, fontSize: 24, fontWeight: "800", lineHeight: 33, letterSpacing: -0.3 },

  bottomBar: {
    flexDirection: "row",
    gap: spacing(1.5),
    padding: spacing(2.5),
    paddingBottom: spacing(3.5),
    backgroundColor: colors.surface,
    borderTopWidth: 1,
    borderTopColor: colors.line,
  },
});
