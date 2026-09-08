/**
 * L'ecran de verrouillage : le point de passage oblige.
 *
 * Deux chemins, exactement ceux du cahier des charges :
 *
 * - saisir le code dicte par un parent (les devoirs sont faits) ;
 * - lancer une evaluation et gagner son code.
 *
 * Tout fonctionne hors ligne : la verification du code est locale, et l'ecran
 * indique clairement l'etat du reseau plutot que de bloquer sur une erreur.
 */

import { useEffect, useState } from "react";
import {
  ActivityIndicator,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native";

import { lockGuard } from "../lib/lockGuard";
import { useApp } from "../state/AppState";
import { colors, radius, spacing, type } from "../theme";

function useCountdown(untilIso: string | undefined) {
  const [seconds, setSeconds] = useState(0);
  useEffect(() => {
    if (!untilIso) return;
    const tick = () =>
      setSeconds(Math.max(0, Math.round((new Date(untilIso).getTime() - Date.now()) / 1000)));
    tick();
    const timer = setInterval(tick, 1000);
    return () => clearInterval(timer);
  }, [untilIso]);
  return seconds;
}

function formatDelay(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  if (h > 0) return `${h} h ${String(m).padStart(2, "0")}`;
  if (m > 0) return `${m} min ${String(s).padStart(2, "0")}`;
  return `${s} s`;
}

export function LockScreen({ onStartExam }: { onStartExam: () => void }) {
  const { child, policy, lockout, online, submitCode, sync, pendingSync, messages } = useApp();
  const [digits, setDigits] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [lockSeconds, setLockSeconds] = useState(0);
  const cooldown = useCountdown(lockout?.until);

  useEffect(() => {
    const tick = async () => setLockSeconds(await lockGuard.remainingLockSeconds());
    void tick();
    const timer = setInterval(() => void tick(), 1000);
    return () => clearInterval(timer);
  }, [error]);

  const preview = digits.length === 10 ? lockGuard.preview(digits) : null;

  async function press(key: string) {
    setError(null);
    if (key === "⌫") {
      setDigits((current) => current.slice(0, -1));
      return;
    }
    const next = (digits + key).slice(0, 10);
    setDigits(next);
    if (next.length === 10) {
      setBusy(true);
      const result = await submitCode(next);
      setBusy(false);
      if (!result.ok) {
        setError(result.message ?? "Ce code ne fonctionne pas.");
        setDigits("");
      }
    }
  }

  const blocked = lockSeconds > 0;

  return (
    <ScrollView style={styles.root} contentContainerStyle={styles.content}>
      <View style={styles.header}>
        <View>
          <Text style={styles.hello}>Bonjour {child?.display_name ?? ""}</Text>
          <Text style={styles.sub}>
            {child?.grade_code ?? ""}
            {policy ? ` · ${policy.period_type === "holiday" ? "vacances" : policy.period_type === "weekend" ? "week-end" : "periode scolaire"}` : ""}
          </Text>
        </View>
        <View style={styles.badges}>
          {child && <Text style={styles.badge}>{child.xp_balance} XP</Text>}
          <Text style={[styles.badge, online ? styles.badgeOnline : styles.badgeOffline]}>
            {online ? "en ligne" : "hors ligne"}
          </Text>
        </View>
      </View>

      {messages.map((message, index) => (
        <View key={index} style={styles.notice}>
          <Text style={styles.noticeText}>{message}</Text>
        </View>
      ))}

      {lockout && cooldown > 0 ? (
        <View style={styles.cooldownCard}>
          <Text style={styles.cooldownLabel}>Temps de revision</Text>
          <Text style={styles.cooldownValue}>{formatDelay(cooldown)}</Text>
          <Text style={styles.cooldownText}>
            {lockout.message ?? "Relis la correction avant de retenter."}
          </Text>
          {lockout.review_topics.length > 0 && (
            <View style={styles.topics}>
              {lockout.review_topics.slice(0, 4).map((topic, index) => (
                <Text key={index} style={styles.topic}>
                  {String((topic as { subject_code?: string }).subject_code ?? "notion")}
                </Text>
              ))}
            </View>
          )}
        </View>
      ) : (
        <TouchableOpacity style={styles.examCard} onPress={onStartExam}>
          <Text style={styles.examTitle}>Passer l&apos;evaluation</Text>
          <Text style={styles.examText}>
            {policy
              ? `${policy.question_count} questions · il faut ${policy.pass_score_out_of_20}/20 pour obtenir ton code · ${policy.reward_minutes} min a la cle`
              : "Reponds correctement et obtiens ton code."}
          </Text>
          <Text style={styles.examCta}>Commencer →</Text>
        </TouchableOpacity>
      )}

      <View style={styles.codeCard}>
        <Text style={styles.codeTitle}>J&apos;ai un code</Text>
        <Text style={styles.codeHelp}>
          Un parent peut te dicter un code a 10 chiffres. Il fonctionne meme sans internet.
        </Text>

        <View style={styles.codeBoxes}>
          {Array.from({ length: 10 }).map((_, index) => (
            <View key={index} style={[styles.codeBox, digits.length === index && styles.codeBoxActive]}>
              <Text style={styles.codeDigit}>{digits[index] ?? ""}</Text>
            </View>
          ))}
        </View>

        {preview && (
          <Text style={styles.preview}>Ce code ouvre {preview.durationMinutes} minutes.</Text>
        )}
        {error && <Text style={styles.error}>{error}</Text>}
        {blocked && (
          <Text style={styles.error}>
            Saisie bloquee encore {formatDelay(lockSeconds)} apres trop d&apos;essais.
          </Text>
        )}

        <View style={styles.keypad}>
          {["1", "2", "3", "4", "5", "6", "7", "8", "9", "", "0", "⌫"].map((key, index) =>
            key === "" ? (
              <View key={index} style={styles.keySpacer} />
            ) : (
              <TouchableOpacity
                key={index}
                style={[styles.key, (busy || blocked) && styles.keyDisabled]}
                onPress={() => void press(key)}
                disabled={busy || blocked}
              >
                <Text style={styles.keyText}>{key}</Text>
              </TouchableOpacity>
            ),
          )}
        </View>
        {busy && <ActivityIndicator color={colors.accent} />}
      </View>

      <TouchableOpacity style={styles.syncRow} onPress={() => void sync()}>
        <Text style={styles.syncText}>
          {pendingSync > 0 ? `${pendingSync} evenement(s) a synchroniser · toucher pour reessayer` : "Synchroniser"}
        </Text>
      </TouchableOpacity>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.bg },
  content: { padding: spacing(2.5), gap: spacing(2), paddingBottom: spacing(6) },
  header: { flexDirection: "row", alignItems: "flex-start", justifyContent: "space-between" },
  hello: { color: colors.ink, ...type.title },
  sub: { color: colors.inkMuted, ...type.small },
  badges: { alignItems: "flex-end", gap: 4 },
  badge: {
    color: colors.inkMuted,
    ...type.small,
    backgroundColor: colors.surface,
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: radius.pill,
    overflow: "hidden",
  },
  badgeOnline: { color: colors.success },
  badgeOffline: { color: colors.warning },

  notice: { backgroundColor: colors.surface, borderRadius: radius.md, padding: spacing(1.5) },
  noticeText: { color: colors.warning, ...type.small },

  cooldownCard: {
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
    padding: spacing(3),
    alignItems: "center",
    gap: spacing(1),
    borderWidth: 1,
    borderColor: colors.warning,
  },
  cooldownLabel: { color: colors.warning, ...type.small, textTransform: "uppercase", letterSpacing: 1 },
  cooldownValue: { color: colors.ink, fontSize: 48, fontWeight: "800" },
  cooldownText: { color: colors.inkMuted, textAlign: "center", ...type.body },
  topics: { flexDirection: "row", flexWrap: "wrap", gap: 6, marginTop: spacing(1) },
  topic: {
    color: colors.ink,
    ...type.small,
    backgroundColor: colors.surfaceHigh,
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: radius.pill,
    overflow: "hidden",
  },

  examCard: { backgroundColor: colors.accent, borderRadius: radius.lg, padding: spacing(3), gap: spacing(1) },
  examTitle: { color: colors.accentInk, ...type.title },
  examText: { color: colors.accentInk, ...type.small, opacity: 0.85 },
  examCta: { color: colors.accentInk, fontWeight: "800", fontSize: 17, marginTop: spacing(1) },

  codeCard: { backgroundColor: colors.surface, borderRadius: radius.lg, padding: spacing(2.5), gap: spacing(1.5) },
  codeTitle: { color: colors.ink, ...type.subtitle },
  codeHelp: { color: colors.inkMuted, ...type.small },
  codeBoxes: { flexDirection: "row", gap: 4, justifyContent: "center", marginVertical: spacing(1) },
  codeBox: {
    width: 28,
    height: 40,
    borderRadius: 8,
    backgroundColor: colors.bgSoft,
    alignItems: "center",
    justifyContent: "center",
    borderWidth: 2,
    borderColor: "transparent",
  },
  codeBoxActive: { borderColor: colors.accent },
  codeDigit: { color: colors.ink, fontSize: 20, fontWeight: "700" },
  preview: { color: colors.success, ...type.small, textAlign: "center" },
  error: { color: colors.danger, ...type.small, textAlign: "center" },

  keypad: { flexDirection: "row", flexWrap: "wrap", gap: spacing(1), justifyContent: "center" },
  key: {
    width: "30%",
    minHeight: 58,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.surfaceHigh,
    borderRadius: radius.md,
  },
  keySpacer: { width: "30%" },
  keyDisabled: { opacity: 0.4 },
  keyText: { color: colors.ink, fontSize: 24, fontWeight: "700" },

  syncRow: { alignItems: "center", padding: spacing(1) },
  syncText: { color: colors.inkFaint, ...type.small },
});
