/**
 * L'examen.
 *
 * L'ecran reproduit les conditions d'un devoir : une question a la fois, un
 * chronometre visible, pas de retour au reste de la tablette. Les reponses sont
 * sauvegardees au fil de l'eau (une coupure ne fait rien perdre) et l'envoi
 * final regroupe tout, ce qui permet de composer entierement hors ligne si
 * l'epreuve a ete telechargee.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native";
import type { Assessment, Submission } from "@koda/shared";

import { ApiError, NetworkError, api } from "../api/client";
import { AnswerInput, type AnswerState } from "../components/AnswerInput";
import { useApp } from "../state/AppState";
import { colors, radius, spacing, type } from "../theme";

const BUCKET_LABEL: Record<string, string> = {
  remediation: "Notion a consolider",
  apprentissage: "Programme en cours",
  consolidation: "Tu maitrises deja",
};
const BUCKET_COLOR: Record<string, string> = {
  remediation: colors.bucketRemediation,
  apprentissage: colors.bucketApprentissage,
  consolidation: colors.bucketConsolidation,
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

  // --- Chargement de l'epreuve --------------------------------------------
  useEffect(() => {
    if (!identity) return;
    void (async () => {
      setBusy(true);
      try {
        const current = await api.currentAssessment(identity.deviceToken).catch(() => null);
        const assessment = current ?? (await api.startAssessment(identity.deviceToken, kind));
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
              ? "Impossible de charger l'evaluation sans connexion."
              : "Erreur inattendue.",
        );
      } finally {
        setBusy(false);
      }
    })();
  }, [identity, kind]);

  // --- Chronometre ---------------------------------------------------------
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

  const answered = useMemo(
    () => Object.values(answers).filter((state) => state.answer && Object.keys(state.answer).length > 0).length,
    [answers],
  );

  const saveCurrent = useCallback(
    async (itemId: string, state: AnswerState) => {
      if (!identity || !exam) return;
      const payload = {
        answer: state.answer,
        answer_mode: state.mode,
        strokes: state.strokes ? (state.strokes as unknown as Record<string, unknown>) : null,
        time_spent_ms: Date.now() - questionStart.current,
      };
      try {
        await api.saveAnswer(identity.deviceToken, exam.id, itemId, payload);
      } catch {
        // Hors ligne : la reponse part avec l'envoi final.
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
      const payload = {
        answers: Object.fromEntries(
          Object.entries(answers).map(([id, state]) => [
            id,
            {
              answer: state.answer,
              answer_mode: state.mode,
              strokes: state.strokes ?? null,
            },
          ]),
        ),
        integrity: {
          duration_seconds: Math.round((Date.now() - startedAt.current) / 1000),
          background_events: backgroundCount.current,
          auto_submitted: auto,
        },
      };
      const result = await api.submit(identity.deviceToken, exam.id, payload);
      onFinished(result);
    } catch (err) {
      setError(
        err instanceof NetworkError
          ? "Envoi impossible : reconnecte-toi puis reessaie. Tes reponses sont gardees."
          : err instanceof ApiError
            ? err.message
            : "Envoi impossible.",
      );
    } finally {
      setBusy(false);
    }
  }

  function confirmSubmit() {
    const missing = (exam?.items.length ?? 0) - answered;
    if (missing > 0) {
      Alert.alert(
        "Envoyer maintenant ?",
        `Il te reste ${missing} question${missing > 1 ? "s" : ""} sans reponse.`,
        [
          { text: "Continuer l'examen", style: "cancel" },
          { text: "Envoyer quand meme", onPress: () => void submit() },
        ],
      );
      return;
    }
    void submit();
  }

  if (error && !exam) {
    return (
      <View style={styles.center}>
        <Text style={styles.error}>{error}</Text>
        <TouchableOpacity style={styles.secondaryButton} onPress={onCancel}>
          <Text style={styles.secondaryText}>Retour</Text>
        </TouchableOpacity>
      </View>
    );
  }

  if (!exam || !item) {
    return (
      <View style={styles.center}>
        <ActivityIndicator color={colors.accent} size="large" />
        <Text style={styles.loading}>Preparation de ton evaluation…</Text>
      </View>
    );
  }

  const bucket = (item as unknown as { bucket?: string }).bucket;
  const progress = (index + 1) / exam.items.length;

  return (
    <View style={styles.root}>
      <View style={styles.topBar}>
        <TouchableOpacity onPress={onCancel} accessibilityLabel="Quitter">
          <Text style={styles.quit}>Quitter</Text>
        </TouchableOpacity>
        <Text style={styles.counter}>
          Question {index + 1} / {exam.items.length}
        </Text>
        {remaining !== null && (
          <Text style={[styles.timer, remaining < 60 && styles.timerUrgent]}>
            {Math.floor(remaining / 60)}:{String(remaining % 60).padStart(2, "0")}
          </Text>
        )}
      </View>
      <View style={styles.progressTrack}>
        <View style={[styles.progressFill, { width: `${progress * 100}%` }]} />
      </View>

      <ScrollView contentContainerStyle={styles.content}>
        {bucket && (
          <View style={[styles.bucket, { borderColor: BUCKET_COLOR[bucket] ?? colors.border }]}>
            <Text style={[styles.bucketText, { color: BUCKET_COLOR[bucket] ?? colors.inkMuted }]}>
              {BUCKET_LABEL[bucket] ?? bucket}
            </Text>
          </View>
        )}

        {item.instructions && <Text style={styles.instructions}>{item.instructions}</Text>}
        <Text style={styles.prompt}>{item.prompt}</Text>

        <AnswerInput
          item={item}
          state={answers[item.id] ?? { answer: null, mode: "assisted", strokes: null }}
          onChange={(state) => setAnswers((current) => ({ ...current, [item.id]: state }))}
        />

        {error && <Text style={styles.error}>{error}</Text>}
      </ScrollView>

      <View style={styles.bottomBar}>
        <TouchableOpacity
          style={[styles.navButton, index === 0 && styles.navDisabled]}
          onPress={() => goTo(index - 1)}
          disabled={index === 0}
        >
          <Text style={styles.navText}>Precedent</Text>
        </TouchableOpacity>

        {index < exam.items.length - 1 ? (
          <TouchableOpacity style={styles.primaryButton} onPress={() => goTo(index + 1)}>
            <Text style={styles.primaryText}>Suivant</Text>
          </TouchableOpacity>
        ) : (
          <TouchableOpacity style={styles.primaryButton} onPress={confirmSubmit} disabled={busy}>
            <Text style={styles.primaryText}>{busy ? "Envoi…" : "Terminer"}</Text>
          </TouchableOpacity>
        )}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.bg },
  center: { flex: 1, backgroundColor: colors.bg, alignItems: "center", justifyContent: "center", gap: spacing(2), padding: spacing(3) },
  loading: { color: colors.inkMuted, ...type.body },

  topBar: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: spacing(2.5),
    paddingTop: spacing(6),
    paddingBottom: spacing(1),
  },
  quit: { color: colors.inkFaint, ...type.small },
  counter: { color: colors.ink, ...type.small, fontWeight: "700" },
  timer: { color: colors.inkMuted, ...type.small, fontVariant: ["tabular-nums"] },
  timerUrgent: { color: colors.danger, fontWeight: "800" },

  progressTrack: { height: 4, backgroundColor: colors.surface, marginHorizontal: spacing(2.5), borderRadius: 2 },
  progressFill: { height: 4, backgroundColor: colors.accent, borderRadius: 2 },

  content: { padding: spacing(2.5), gap: spacing(2.5), paddingBottom: spacing(6) },
  bucket: { alignSelf: "flex-start", borderWidth: 1, borderRadius: radius.pill, paddingHorizontal: 12, paddingVertical: 4 },
  bucketText: { ...type.small, fontWeight: "700" },
  instructions: { color: colors.inkMuted, ...type.body, lineHeight: 24 },
  prompt: { color: colors.ink, fontSize: 23, fontWeight: "700", lineHeight: 32 },
  error: { color: colors.danger, ...type.small },

  bottomBar: {
    flexDirection: "row",
    gap: spacing(1.5),
    padding: spacing(2.5),
    borderTopWidth: 1,
    borderTopColor: colors.border,
    backgroundColor: colors.bgSoft,
  },
  navButton: { paddingVertical: spacing(2), paddingHorizontal: spacing(2.5), borderRadius: radius.md, backgroundColor: colors.surface },
  navDisabled: { opacity: 0.4 },
  navText: { color: colors.ink, fontWeight: "600" },
  primaryButton: { flex: 1, paddingVertical: spacing(2), borderRadius: radius.md, backgroundColor: colors.accent, alignItems: "center" },
  primaryText: { color: colors.accentInk, fontWeight: "800", fontSize: 17 },
  secondaryButton: { paddingVertical: spacing(1.5), paddingHorizontal: spacing(3), borderRadius: radius.md, backgroundColor: colors.surface },
  secondaryText: { color: colors.ink, fontWeight: "600" },
});
