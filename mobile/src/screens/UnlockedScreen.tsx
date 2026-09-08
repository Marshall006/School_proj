/**
 * L'espace deverrouille.
 *
 * Volontairement sobre : le temps d'ecran gagne se passe ailleurs, pas ici.
 * On y trouve le minuteur, la possibilite de rendre du temps volontairement,
 * et la porte d'entree vers l'auto-evaluation qui rapporte des XP.
 */

import { StyleSheet, Text, TouchableOpacity, View } from "react-native";

import { formatRemaining } from "../lib/timer";
import { useApp } from "../state/AppState";
import { colors, radius, spacing, type } from "../theme";

export function UnlockedScreen({ onPractice }: { onPractice: () => void }) {
  const { child, remainingMs, session, lockNow, online, pendingSync } = useApp();
  const total = session?.grantedMs ?? 1;
  const ratio = Math.max(0, Math.min(1, remainingMs / total));

  return (
    <View style={styles.root}>
      <View style={styles.header}>
        <Text style={styles.hello}>{child?.display_name}</Text>
        <View style={styles.badges}>
          {child && <Text style={styles.badge}>{child.xp_balance} XP</Text>}
          <Text style={[styles.badge, online ? styles.badgeOnline : styles.badgeOffline]}>
            {online ? "en ligne" : "hors ligne"}
          </Text>
        </View>
      </View>

      <View style={styles.timerCard}>
        <Text style={styles.timerLabel}>Temps restant</Text>
        <Text style={styles.timer}>{formatRemaining(remainingMs)}</Text>
        <View style={styles.track}>
          <View style={[styles.fill, { width: `${ratio * 100}%` }]} />
        </View>
        <Text style={styles.timerHint}>
          Le decompte se met en pause quand l&apos;ecran s&apos;eteint.
          {session?.offline ? " Session ouverte hors ligne : elle sera synchronisee." : ""}
        </Text>
      </View>

      <TouchableOpacity style={styles.practiceCard} onPress={onPractice}>
        <Text style={styles.practiceTitle}>Gagner du temps en plus</Text>
        <Text style={styles.practiceText}>
          Fais une evaluation libre : chaque bonne reponse rapporte des XP, convertibles en minutes
          d&apos;ecran.
        </Text>
      </TouchableOpacity>

      <View style={{ flex: 1 }} />

      {pendingSync > 0 && (
        <Text style={styles.pending}>{pendingSync} evenement(s) en attente de synchronisation</Text>
      )}

      <TouchableOpacity style={styles.stopButton} onPress={() => void lockNow()}>
        <Text style={styles.stopText}>J&apos;ai fini — garder mon temps</Text>
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.bg, padding: spacing(2.5), paddingTop: spacing(6), gap: spacing(2) },
  header: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  hello: { color: colors.ink, ...type.title },
  badges: { flexDirection: "row", gap: 6 },
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

  timerCard: { backgroundColor: colors.surface, borderRadius: radius.lg, padding: spacing(3), alignItems: "center", gap: spacing(1) },
  timerLabel: { color: colors.inkMuted, ...type.small, textTransform: "uppercase", letterSpacing: 1 },
  timer: { color: colors.ink, fontSize: 64, fontWeight: "800", fontVariant: ["tabular-nums"] },
  track: { height: 8, width: "100%", backgroundColor: colors.bgSoft, borderRadius: 4, overflow: "hidden" },
  fill: { height: 8, backgroundColor: colors.accent, borderRadius: 4 },
  timerHint: { color: colors.inkFaint, ...type.small, textAlign: "center" },

  practiceCard: { backgroundColor: colors.surface, borderRadius: radius.lg, padding: spacing(2.5), gap: 6 },
  practiceTitle: { color: colors.ink, ...type.subtitle },
  practiceText: { color: colors.inkMuted, ...type.small, lineHeight: 20 },

  pending: { color: colors.inkFaint, ...type.small, textAlign: "center" },
  stopButton: { backgroundColor: colors.surfaceHigh, borderRadius: radius.md, padding: spacing(2), alignItems: "center" },
  stopText: { color: colors.ink, fontWeight: "700" },
});
