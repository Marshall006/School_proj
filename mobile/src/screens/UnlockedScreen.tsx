/**
 * L'espace déverrouillé.
 *
 * Volontairement calme : le temps gagne se passe ailleurs, pas ici. On y
 * trouve le minuteur, de quoi rendre du temps volontairement, et la porte vers
 * l'auto-évaluation qui rapporte des points.
 */

import { useState } from "react";
import { StyleSheet, Text, View } from "react-native";

import { ApiError } from "../api/client";
import {
  Avatar,
  Banner,
  Card,
  Chip,
  GhostButton,
  PrimaryButton,
  Ring,
  Screen,
  SectionTitle,
} from "../components/kit";
import { formatRemaining } from "../lib/timer";
import { useApp } from "../state/AppState";
import { avatarOf, colors, spacing, type } from "../theme";

export function UnlockedScreen({ onPractice }: { onPractice: () => void }) {
  const { child, policy, remainingMs, session, lockNow, online, pendingSync, redeemXp } = useApp();
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const total = session?.grantedMs ?? 1;
  const ratio = Math.max(0, Math.min(1, remainingMs / total));
  const lowOnTime = remainingMs < 5 * 60_000;

  const rate = policy?.minutes_per_100_xp ?? 0;
  const cap = policy?.xp_daily_bonus_cap_minutes ?? 0;
  const raw = Math.floor(((child?.xp_balance ?? 0) * rate) / 100);
  const convertible = Math.max(0, Math.min(raw, cap) - (Math.min(raw, cap) % 5));

  async function convert() {
    setBusy(true);
    setMessage(null);
    try {
      const result = await redeemXp();
      setMessage(`+${result.granted_minutes} minutes ajoutées.`);
    } catch (err) {
      setMessage(err instanceof ApiError ? err.message : "Conversion impossible pour le moment.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Screen>
      <View style={styles.header}>
        <Avatar emoji={avatarOf(child?.avatar)} size={48} />
        <Text style={styles.name}>{child?.display_name}</Text>
        <View style={{ flex: 1 }} />
        <Chip label={online ? "en ligne" : "hors ligne"} tone={online ? "neutral" : "gold"} />
      </View>

      <Card style={styles.timerCard}>
        <Ring value={ratio} size={230}>
          <Text style={styles.timerLabel}>Temps restant</Text>
          <Text style={styles.timer}>{formatRemaining(remainingMs)}</Text>
          <Text style={styles.timerTotal}>sur {Math.round(total / 60000)} min</Text>
        </Ring>
        <Text style={styles.timerHint}>
          Le decompte s&apos;arrete quand l&apos;écran s&apos;eteint.
          {session?.offline ? " Session ouverte hors ligne, elle sera synchronisee." : ""}
        </Text>
        {lowOnTime ? (
          <Banner tone="gold" title="Bientot fini">
            Il te reste moins de 5 minutes. Pense a sauvegarder ce que tu fais.
          </Banner>
        ) : null}
      </Card>

      <Card>
        <SectionTitle hint={rate > 0 ? `100 XP = ${rate} min` : undefined}>
          Gagner plus de temps
        </SectionTitle>
        <Text style={styles.text}>
          Une évaluation libre ne coute rien et rapporte des XP, convertibles en minutes.
        </Text>
        <PrimaryButton label="M'entraîner" icon="✏️" onPress={onPractice} />
        {convertible >= 5 ? (
          <PrimaryButton
            label={`Convertir ${child?.xp_balance ?? 0} XP en ${convertible} min`}
            icon="⭐"
            tone="gold"
            busy={busy}
            onPress={() => void convert()}
          />
        ) : null}
        {message ? <Text style={styles.message}>{message}</Text> : null}
      </Card>

      {pendingSync > 0 ? (
        <Banner tone="gold">{pendingSync} element(s) en attente de synchronisation.</Banner>
      ) : null}

      <GhostButton label="J'ai fini — garder mon temps" icon="⏸" onPress={() => void lockNow()} />
    </Screen>
  );
}

const styles = StyleSheet.create({
  header: { flexDirection: "row", alignItems: "center", gap: spacing(1.5) },
  name: { color: colors.ink, ...type.heading },
  timerCard: { alignItems: "center" },
  timerLabel: { color: colors.inkFaint, ...type.tiny, textTransform: "uppercase" },
  timer: { color: colors.ink, fontSize: 48, fontWeight: "800", fontVariant: ["tabular-nums"] },
  timerTotal: { color: colors.inkFaint, ...type.small },
  timerHint: { color: colors.inkFaint, ...type.small, textAlign: "center" },
  text: { color: colors.inkSoft, ...type.small, lineHeight: 20 },
  message: { color: colors.successInk, ...type.small, fontWeight: "700" },
});
