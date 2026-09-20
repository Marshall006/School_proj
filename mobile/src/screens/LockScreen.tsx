/**
 * L'écran de verrouillage : le point de passage oblige.
 *
 * Il doit répondre en un coup d'oeil à la seule question que se pose l'enfant :
 * « comment j'ouvre la tablette ? ». Deux chemins, exactement ceux du cahier
 * des charges, presentes cote à côté et jamais caches :
 *
 *   1. réussir une évaluation — le chemin principal, mis en avant ;
 *   2. saisir le code dicte par un parent, quand les devoirs sont faits.
 *
 * Pendant un temps de carence, le premier chemin est remplace par le compte a
 * rebours, mais deux portes restent ouvertes : relire la correction et
 * s'entraîner pour gagner des points. Le délai sert a réviser, pas a attendre.
 */

import { useCallback, useEffect, useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";

import { ApiError, api } from "../api/client";
import {
  Avatar,
  Banner,
  Card,
  Chip,
  GhostButton,
  PrimaryButton,
  Screen,
  SectionTitle,
} from "../components/kit";
import { lockGuard } from "../lib/lockGuard";
import { useApp } from "../state/AppState";
import { avatarOf, colors, radius, spacing, type } from "../theme";

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

const PERIOD_LABEL: Record<string, string> = {
  school: "période scolaire",
  weekend: "week-end",
  holiday: "vacances",
};

export function LockScreen({
  onStartExam,
  onReview,
}: {
  onStartExam: (kind: "unlock" | "practice") => void;
  onReview: (assessmentId: string) => void;
}) {
  const { child, policy, lockout, online, identity, submitCode, sync, redeemXp, pendingSync, messages } =
    useApp();

  const [eligibility, setEligibility] = useState<{
    allowed: boolean;
    reason: string | null;
    details: Record<string, unknown>;
    attempts_today: number;
    max_attempts_per_day: number;
  } | null>(null);
  const [digits, setDigits] = useState("");
  const [showKeypad, setShowKeypad] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [lockSeconds, setLockSeconds] = useState(0);
  const [xpMessage, setXpMessage] = useState<string | null>(null);

  const loadEligibility = useCallback(async () => {
    if (!identity) return;
    try {
      setEligibility(await api.eligibility(identity.deviceToken, "unlock"));
    } catch {
      setEligibility(null); // hors ligne : on reste optimiste, le serveur tranchera
    }
  }, [identity]);

  useEffect(() => {
    void loadEligibility();
  }, [loadEligibility, lockout?.until]);

  useEffect(() => {
    const tick = async () => setLockSeconds(await lockGuard.remainingLockSeconds());
    void tick();
    const timer = setInterval(() => void tick(), 1000);
    return () => clearInterval(timer);
  }, [error]);

  const preview = digits.length === 10 ? lockGuard.preview(digits) : null;
  const keypadBlocked = lockSeconds > 0;

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

  // --- Conversion des points en minutes ------------------------------------
  const rate = policy?.minutes_per_100_xp ?? 0;
  const cap = policy?.xp_daily_bonus_cap_minutes ?? 0;
  const rawMinutes = Math.floor(((child?.xp_balance ?? 0) * rate) / 100);
  const convertible = Math.max(0, Math.min(rawMinutes, cap) - (Math.min(rawMinutes, cap) % 5));

  async function convertXp() {
    setBusy(true);
    setXpMessage(null);
    try {
      const result = await redeemXp();
      setXpMessage(`+${result.granted_minutes} minutes débloquées !`);
    } catch (err) {
      setXpMessage(err instanceof ApiError ? err.message : "Conversion impossible pour le moment.");
    } finally {
      setBusy(false);
    }
  }

  // La carence peut venir de la synchronisation (hors ligne compris) ou de la
  // réponse d'eligibilite, qui est plus fraiche juste après un examen.
  const cooldownSource = lockout?.until ?? (eligibility?.details as { until?: string } | undefined)?.until;
  const cooldown = useCountdown(cooldownSource);
  const fallbackLockout =
    eligibility?.reason === "cooldown_active"
      ? (eligibility.details as unknown as NonNullable<typeof lockout>)
      : null;
  const activeLockout =
    lockout ?? fallbackLockout;
  const inCooldown = Boolean(activeLockout && cooldown > 0);
  const attemptsLeft = eligibility
    ? Math.max(0, eligibility.max_attempts_per_day - eligibility.attempts_today)
    : null;
  const blockedByAttempts = eligibility?.reason === "too_many_attempts";

  return (
    <Screen>
      {/* --- En-tete ------------------------------------------------------ */}
      <View style={styles.header}>
        <Avatar emoji={avatarOf(child?.avatar)} size={62} />
        <View style={{ flex: 1 }}>
          <Text style={styles.hello}>Salut {child?.display_name ?? ""} !</Text>
          <Text style={styles.sub}>
            {child?.grade_code ?? ""}
            {policy ? ` · ${PERIOD_LABEL[policy.period_type] ?? policy.period_type}` : ""}
          </Text>
        </View>
      </View>

      <View style={styles.chips}>
        <Chip label={`${child?.xp_balance ?? 0} XP`} tone="gold" icon="⭐" />
        {(child?.streak_days ?? 0) > 1 ? (
          <Chip label={`${child?.streak_days} jours d'affilee`} tone="success" icon="🔥" />
        ) : null}
        <Chip label={online ? "en ligne" : "hors ligne"} tone={online ? "neutral" : "gold"} />
      </View>

      {messages.map((message, index) => (
        <Banner key={index} tone="gold">
          {message}
        </Banner>
      ))}

      {/* --- Chemin 1 : l'évaluation -------------------------------------- */}
      {inCooldown ? (
        <Card tone="gold">
          <Text style={styles.eyebrow}>Temps de révision</Text>
          <Text style={styles.countdown}>{formatDelay(cooldown)}</Text>
          <Text style={styles.cooldownText}>
            {activeLockout?.message ?? "Relis ta correction, puis retente ta chance."}
          </Text>

          {activeLockout?.review_topics?.length ? (
            <View style={styles.topics}>
              {activeLockout!.review_topics.slice(0, 5).map((topic, index) => (
                <Chip
                  key={index}
                  label={String((topic as { subject_code?: string }).subject_code ?? "notion")}
                />
              ))}
            </View>
          ) : null}

          {activeLockout?.source_assessment_id ? (
            <PrimaryButton
              label="Revoir ma correction"
              icon="📖"
              tone="gold"
              onPress={() => onReview(activeLockout!.source_assessment_id as string)}
            />
          ) : null}
          <GhostButton
            label="M'entraîner en attendant (gagne des XP)"
            icon="✏️"
            onPress={() => onStartExam("practice")}
          />
        </Card>
      ) : blockedByAttempts ? (
        <Card tone="soft">
          <Text style={styles.eyebrow}>Essais du jour termines</Text>
          <Text style={styles.cardTitle}>Tu as utilisé tes {eligibility?.max_attempts_per_day} essais</Text>
          <Text style={styles.cooldownText}>
            Reviens demain, ou demande un code à tes parents. En attendant, tu peux t&apos;entraîner :
            ca rapporte des XP.
          </Text>
          <GhostButton label="M'entraîner" icon="✏️" onPress={() => onStartExam("practice")} />
        </Card>
      ) : (
        <Pressable onPress={() => onStartExam("unlock")} accessibilityRole="button">
          {({ pressed }) => (
            <View style={[styles.heroCard, pressed && styles.heroPressed]}>
              <Text style={styles.heroEyebrow}>Chemin principal</Text>
              <Text style={styles.heroTitle}>Gagner mon temps d&apos;écran</Text>
              <Text style={styles.heroText}>
                {policy
                  ? `${policy.question_count} questions · il te faut ${policy.pass_score_out_of_20}/20 · ${policy.reward_minutes} minutes à la clé`
                  : "Réponds correctement et obtiens ton code."}
              </Text>
              <View style={styles.heroFooter}>
                <Text style={styles.heroCta}>Commencer l&apos;évaluation →</Text>
                {attemptsLeft !== null ? (
                  <Text style={styles.heroHint}>
                    {attemptsLeft} essai{attemptsLeft > 1 ? "s" : ""} aujourd&apos;hui
                  </Text>
                ) : null}
              </View>
            </View>
          )}
        </Pressable>
      )}

      {/* --- Les points d'expérience -------------------------------------- */}
      {rate > 0 ? (
        <Card tone={convertible >= 5 ? "surface" : "soft"}>
          <SectionTitle hint={`100 XP = ${rate} min`}>Mes points</SectionTitle>
          <View style={styles.xpRow}>
            <Text style={styles.xpValue}>{child?.xp_balance ?? 0}</Text>
            <Text style={styles.xpUnit}>XP</Text>
            <View style={{ flex: 1 }} />
            {convertible >= 5 ? (
              <Chip label={`≈ ${convertible} min`} tone="gold" icon="⏱" />
            ) : (
              <Text style={styles.xpHint}>Entraîne-toi pour en gagner</Text>
            )}
          </View>
          {convertible >= 5 ? (
            <PrimaryButton
              label={`Convertir en ${convertible} minutes`}
              icon="⭐"
              tone="gold"
              busy={busy}
              onPress={() => void convertXp()}
            />
          ) : (
            <GhostButton
              label="M'entraîner pour gagner des XP"
              icon="✏️"
              onPress={() => onStartExam("practice")}
            />
          )}
          {xpMessage ? <Text style={styles.xpMessage}>{xpMessage}</Text> : null}
        </Card>
      ) : null}

      {/* --- Chemin 2 : le code des parents -------------------------------- */}
      <Card>
        <Pressable
          onPress={() => setShowKeypad((v) => !v)}
          accessibilityRole="button"
          style={styles.codeHeader}
        >
          <View style={{ flex: 1 }}>
            <SectionTitle>J&apos;ai un code de mes parents</SectionTitle>
            <Text style={styles.codeHelp}>
              10 chiffres. Il fonctionne même sans internet.
            </Text>
          </View>
          <Text style={styles.chevron}>{showKeypad ? "▴" : "▾"}</Text>
        </Pressable>

        {showKeypad ? (
          <View style={{ gap: spacing(1.5) }}>
            <View style={styles.codeBoxes}>
              {Array.from({ length: 10 }).map((_, index) => (
                <View
                  key={index}
                  style={[styles.codeBox, digits.length === index && styles.codeBoxActive]}
                >
                  <Text style={styles.codeDigit}>{digits[index] ?? ""}</Text>
                </View>
              ))}
            </View>

            {preview ? (
              <Text style={styles.preview}>Ce code ouvre {preview.durationMinutes} minutes.</Text>
            ) : null}
            {error ? <Banner tone="danger">{error}</Banner> : null}
            {keypadBlocked ? (
              <Banner tone="danger" title="Trop d'essais">
                Patiente encore {formatDelay(lockSeconds)} avant de reessayer.
              </Banner>
            ) : null}

            <View style={styles.keypad}>
              {["1", "2", "3", "4", "5", "6", "7", "8", "9", "", "0", "⌫"].map((key, index) =>
                key === "" ? (
                  <View key={index} style={styles.keySpacer} />
                ) : (
                  <Pressable
                    key={index}
                    onPress={() => void press(key)}
                    disabled={busy || keypadBlocked}
                    accessibilityRole="button"
                    accessibilityLabel={key === "⌫" ? "Effacer" : key}
                    style={({ pressed }) => [
                      styles.key,
                      pressed && styles.keyPressed,
                      (busy || keypadBlocked) && styles.keyDisabled,
                    ]}
                  >
                    <Text style={styles.keyText}>{key}</Text>
                  </Pressable>
                ),
              )}
            </View>
          </View>
        ) : null}
      </Card>

      <Pressable onPress={() => void sync()} style={styles.syncRow}>
        <Text style={styles.syncText}>
          {pendingSync > 0
            ? `${pendingSync} élément(s) à synchroniser · toucher pour réessayer`
            : "Tout est à jour · toucher pour synchroniser"}
        </Text>
      </Pressable>
    </Screen>
  );
}

const styles = StyleSheet.create({
  header: { flexDirection: "row", alignItems: "center", gap: spacing(1.5) },
  hello: { color: colors.ink, ...type.title },
  sub: { color: colors.inkFaint, ...type.small },
  chips: { flexDirection: "row", flexWrap: "wrap", gap: spacing(1) },

  heroCard: {
    backgroundColor: colors.primary,
    borderRadius: radius.lg,
    padding: spacing(3),
    gap: spacing(1),
    shadowColor: colors.primaryDeep,
    shadowOpacity: 0.3,
    shadowRadius: 22,
    shadowOffset: { width: 0, height: 10 },
    elevation: 6,
  },
  heroPressed: { transform: [{ scale: 0.99 }] },
  heroEyebrow: { color: "#cfe2ff", ...type.tiny, textTransform: "uppercase" },
  heroTitle: { color: colors.onPrimary, ...type.title },
  heroText: { color: "#dceaff", ...type.small, lineHeight: 20 },
  heroFooter: { flexDirection: "row", alignItems: "center", marginTop: spacing(1) },
  heroCta: { color: colors.onPrimary, fontSize: 17, fontWeight: "800" },
  heroHint: { color: "#cfe2ff", ...type.small, marginLeft: "auto" },

  eyebrow: { color: colors.goldInk, ...type.tiny, textTransform: "uppercase" },
  cardTitle: { color: colors.ink, ...type.heading },
  countdown: { color: colors.ink, ...type.display },
  cooldownText: { color: colors.inkSoft, ...type.small, lineHeight: 20 },
  topics: { flexDirection: "row", flexWrap: "wrap", gap: 6 },

  xpRow: { flexDirection: "row", alignItems: "baseline", gap: 6 },
  xpValue: { color: colors.ink, ...type.display },
  xpUnit: { color: colors.goldInk, ...type.heading },
  xpHint: { color: colors.inkFaint, ...type.small },
  xpMessage: { color: colors.successInk, ...type.small, fontWeight: "700" },

  codeHeader: { flexDirection: "row", alignItems: "center", gap: spacing(1) },
  codeHelp: { color: colors.inkFaint, ...type.small },
  chevron: { color: colors.inkFaint, fontSize: 18 },
  codeBoxes: { flexDirection: "row", gap: 5, justifyContent: "center" },
  codeBox: {
    width: 28,
    height: 42,
    borderRadius: 10,
    backgroundColor: colors.surfaceAlt,
    alignItems: "center",
    justifyContent: "center",
    borderWidth: 2,
    borderColor: "transparent",
  },
  codeBoxActive: { borderColor: colors.primary, backgroundColor: colors.primarySoft },
  codeDigit: { color: colors.ink, fontSize: 20, fontWeight: "800" },
  preview: { color: colors.successInk, ...type.small, textAlign: "center", fontWeight: "700" },

  keypad: { flexDirection: "row", flexWrap: "wrap", gap: spacing(1), justifyContent: "center" },
  key: {
    width: "30%",
    minHeight: 60,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.surfaceAlt,
    borderRadius: radius.md,
  },
  keyPressed: { backgroundColor: colors.primarySoft },
  keySpacer: { width: "30%" },
  keyDisabled: { opacity: 0.4 },
  keyText: { color: colors.ink, fontSize: 24, fontWeight: "800" },

  syncRow: { alignItems: "center", paddingVertical: spacing(1) },
  syncText: { color: colors.inkFaint, ...type.small },
});
