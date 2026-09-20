/**
 * Briques d'interface de l'application enfant.
 *
 * Tout l'écran se composé de ces quelques pieces, pour que l'application ait
 * partout le même rythme : mêmes rayons, mêmes ombres, mêmes cibles tactiles.
 */

import type { ReactNode } from "react";
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
  type StyleProp,
  type ViewStyle,
} from "react-native";
import Svg, { Circle, Defs, LinearGradient, Stop } from "react-native-svg";

import { colors, elevation, radius, spacing, type } from "../theme";

// ---------------------------------------------------------------------------
// Structure
// ---------------------------------------------------------------------------

export function Screen({
  children,
  scroll = true,
  style,
}: {
  children: ReactNode;
  scroll?: boolean;
  style?: StyleProp<ViewStyle>;
}) {
  if (!scroll) {
    return <View style={[styles.screen, styles.screenPad, style]}>{children}</View>;
  }
  return (
    <ScrollView style={styles.screen} contentContainerStyle={[styles.screenPad, style]}>
      {children}
    </ScrollView>
  );
}

export function Card({
  children,
  tone = "surface",
  style,
}: {
  children: ReactNode;
  tone?: "surface" | "soft" | "gold" | "success" | "danger";
  style?: StyleProp<ViewStyle>;
}) {
  return <View style={[styles.card, styles[`card_${tone}`], style]}>{children}</View>;
}

export function SectionTitle({ children, hint }: { children: ReactNode; hint?: string }) {
  return (
    <View style={styles.sectionTitle}>
      <Text style={styles.sectionTitleText}>{children}</Text>
      {hint ? <Text style={styles.sectionTitleHint}>{hint}</Text> : null}
    </View>
  );
}

// ---------------------------------------------------------------------------
// Actions
// ---------------------------------------------------------------------------

export function PrimaryButton({
  label,
  onPress,
  disabled,
  busy,
  tone = "primary",
  icon,
}: {
  label: string;
  onPress: () => void;
  disabled?: boolean;
  busy?: boolean;
  tone?: "primary" | "gold" | "success" | "danger";
  icon?: string;
}) {
  const inactive = disabled || busy;
  return (
    <Pressable
      onPress={onPress}
      disabled={inactive}
      accessibilityRole="button"
      accessibilityState={{ disabled: !!inactive }}
      style={({ pressed }) => [
        styles.button,
        styles[`button_${tone}`],
        pressed && !inactive && styles.buttonPressed,
        inactive && styles.buttonDisabled,
      ]}
    >
      {busy ? (
        <ActivityIndicator color={colors.onPrimary} />
      ) : (
        <Text style={styles.buttonLabel}>
          {icon ? `${icon}  ` : ""}
          {label}
        </Text>
      )}
    </Pressable>
  );
}

export function GhostButton({
  label,
  onPress,
  disabled,
  icon,
  danger,
}: {
  label: string;
  onPress: () => void;
  disabled?: boolean;
  icon?: string;
  danger?: boolean;
}) {
  return (
    <Pressable
      onPress={onPress}
      disabled={disabled}
      accessibilityRole="button"
      style={({ pressed }) => [
        styles.ghost,
        pressed && !disabled && styles.ghostPressed,
        disabled && styles.buttonDisabled,
      ]}
    >
      <Text style={[styles.ghostLabel, danger && { color: colors.dangerInk }]}>
        {icon ? `${icon}  ` : ""}
        {label}
      </Text>
    </Pressable>
  );
}

// ---------------------------------------------------------------------------
// Indicateurs
// ---------------------------------------------------------------------------

export function Chip({
  label,
  tone = "neutral",
  icon,
}: {
  label: string;
  tone?: "neutral" | "primary" | "gold" | "success" | "danger";
  icon?: string;
}) {
  return (
    <View style={[styles.chip, styles[`chip_${tone}`]]}>
      <Text style={[styles.chipLabel, styles[`chipLabel_${tone}`]]}>
        {icon ? `${icon} ` : ""}
        {label}
      </Text>
    </View>
  );
}

export function ProgressBar({ value, tone = "primary" }: { value: number; tone?: "primary" | "gold" }) {
  const pct = Math.max(0, Math.min(1, value));
  return (
    <View style={styles.track} accessibilityRole="progressbar">
      <View
        style={[
          styles.fill,
          { width: `${pct * 100}%`, backgroundColor: tone === "gold" ? colors.gold : colors.primary },
        ]}
      />
    </View>
  );
}

/** Anneau de progression : le minuteur du temps d'écran. */
export function Ring({
  value,
  size = 210,
  thickness = 16,
  children,
}: {
  value: number;
  size?: number;
  thickness?: number;
  children?: ReactNode;
}) {
  const pct = Math.max(0, Math.min(1, value));
  const r = (size - thickness) / 2;
  const circumference = 2 * Math.PI * r;
  return (
    <View style={{ width: size, height: size, alignItems: "center", justifyContent: "center" }}>
      <Svg width={size} height={size} style={{ position: "absolute" }}>
        <Defs>
          <LinearGradient id="ring" x1="0" y1="0" x2="1" y2="1">
            <Stop offset="0" stopColor={colors.primary} />
            <Stop offset="1" stopColor={colors.info} />
          </LinearGradient>
        </Defs>
        <Circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          stroke={colors.surfaceAlt}
          strokeWidth={thickness}
          fill="none"
        />
        <Circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          stroke="url(#ring)"
          strokeWidth={thickness}
          strokeLinecap="round"
          fill="none"
          strokeDasharray={`${circumference} ${circumference}`}
          strokeDashoffset={circumference * (1 - pct)}
          transform={`rotate(-90 ${size / 2} ${size / 2})`}
        />
      </Svg>
      <View style={{ alignItems: "center" }}>{children}</View>
    </View>
  );
}

export function Avatar({ emoji, size = 64 }: { emoji: string; size?: number }) {
  return (
    <View
      style={[
        styles.avatar,
        { width: size, height: size, borderRadius: size / 2 },
      ]}
    >
      <Text style={{ fontSize: size * 0.52 }}>{emoji}</Text>
    </View>
  );
}

export function Banner({
  tone = "info",
  title,
  children,
}: {
  tone?: "info" | "gold" | "danger" | "success";
  title?: string;
  children: ReactNode;
}) {
  return (
    <View style={[styles.banner, styles[`banner_${tone}`]]}>
      {title ? <Text style={[styles.bannerTitle, styles[`bannerTitle_${tone}`]]}>{title}</Text> : null}
      <Text style={styles.bannerText}>{children}</Text>
    </View>
  );
}

// ---------------------------------------------------------------------------

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.bg },
  screenPad: { padding: spacing(2.5), paddingTop: spacing(7), paddingBottom: spacing(6), gap: spacing(2) },

  card: {
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
    padding: spacing(2.5),
    gap: spacing(1.5),
    ...elevation.card,
  },
  card_surface: {},
  card_soft: { backgroundColor: colors.surfaceAlt, shadowOpacity: 0 },
  card_gold: { backgroundColor: colors.goldSoft, shadowOpacity: 0 },
  card_success: { backgroundColor: colors.successSoft, shadowOpacity: 0 },
  card_danger: { backgroundColor: colors.dangerSoft, shadowOpacity: 0 },

  sectionTitle: { flexDirection: "row", alignItems: "baseline", gap: spacing(1), marginTop: spacing(0.5) },
  sectionTitleText: { color: colors.ink, ...type.heading },
  sectionTitleHint: { color: colors.inkFaint, ...type.small },

  button: {
    minHeight: 56,
    borderRadius: radius.md,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: spacing(3),
    ...elevation.card,
  },
  button_primary: { backgroundColor: colors.primary },
  button_gold: { backgroundColor: colors.gold },
  button_success: { backgroundColor: colors.success },
  button_danger: { backgroundColor: colors.danger },
  buttonPressed: { transform: [{ scale: 0.985 }], shadowOpacity: 0.04 },
  buttonDisabled: { opacity: 0.45 },
  buttonLabel: { color: colors.onPrimary, fontSize: 17, fontWeight: "800" },

  ghost: {
    minHeight: 48,
    borderRadius: radius.md,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: spacing(2),
    backgroundColor: colors.surfaceAlt,
  },
  ghostPressed: { backgroundColor: colors.line },
  ghostLabel: { color: colors.inkSoft, fontSize: 15, fontWeight: "700" },

  chip: {
    paddingHorizontal: spacing(1.5),
    paddingVertical: 6,
    borderRadius: radius.pill,
    backgroundColor: colors.surfaceAlt,
  },
  chip_neutral: {},
  chip_primary: { backgroundColor: colors.primarySoft },
  chip_gold: { backgroundColor: colors.goldSoft },
  chip_success: { backgroundColor: colors.successSoft },
  chip_danger: { backgroundColor: colors.dangerSoft },
  chipLabel: { ...type.small, fontWeight: "700", color: colors.inkSoft },
  chipLabel_neutral: {},
  chipLabel_primary: { color: colors.primaryDeep },
  chipLabel_gold: { color: colors.goldInk },
  chipLabel_success: { color: colors.successInk },
  chipLabel_danger: { color: colors.dangerInk },

  track: { height: 10, borderRadius: 5, backgroundColor: colors.surfaceAlt, overflow: "hidden" },
  fill: { height: 10, borderRadius: 5 },

  avatar: {
    backgroundColor: colors.primarySoft,
    alignItems: "center",
    justifyContent: "center",
  },

  banner: { borderRadius: radius.md, padding: spacing(2), gap: 4 },
  banner_info: { backgroundColor: colors.primarySoft },
  banner_gold: { backgroundColor: colors.goldSoft },
  banner_danger: { backgroundColor: colors.dangerSoft },
  banner_success: { backgroundColor: colors.successSoft },
  bannerTitle: { ...type.small, fontWeight: "800" },
  bannerTitle_info: { color: colors.primaryDeep },
  bannerTitle_gold: { color: colors.goldInk },
  bannerTitle_danger: { color: colors.dangerInk },
  bannerTitle_success: { color: colors.successInk },
  bannerText: { color: colors.inkSoft, ...type.small, lineHeight: 20 },
});
