/**
 * Première utilisation : la tablette recoit son identite et son secret.
 *
 * Écran volontairement explicite : le code demande ici n'est pas le code qui
 * ouvre le temps d'écran, c'est celui qui relie l'appareil au foyer. La
 * confusion entre les deux est le premier obstacle rencontre par un nouvel
 * utilisateur.
 */

import { useState } from "react";
import {
  KeyboardAvoidingView,
  Platform,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";

import { ApiError, NetworkError, apiUrl } from "../api/client";
import { Banner, Card, PrimaryButton, Screen } from "../components/kit";
import { useApp } from "../state/AppState";
import { colors, radius, spacing, type } from "../theme";

export function PairingScreen() {
  const { pair } = useApp();
  const [code, setCode] = useState("");
  const [name, setName] = useState("Ma tablette");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit() {
    setBusy(true);
    setError(null);
    try {
      await pair(code, name);
    } catch (err) {
      setError(
        err instanceof NetworkError
          ? `Impossible de joindre le serveur (${apiUrl()}). Vérifie le réseau.`
          : err instanceof ApiError
            ? err.message
            : "Appairage impossible.",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === "ios" ? "padding" : undefined}>
      <Screen>
        <View style={styles.hero}>
          <View style={styles.logo}>
            <Text style={styles.logoText}>K</Text>
          </View>
          <Text style={styles.brand}>KODA</Text>
          <Text style={styles.tagline}>L&apos;écran se mérite.</Text>
        </View>

        <Card>
          <Text style={styles.step}>Première utilisation</Text>
          <Text style={styles.title}>Relier cette tablette à tes parents</Text>
          <Text style={styles.help}>
            Un parent ouvre son tableau de bord KODA, va dans{" "}
            <Text style={styles.strong}>Appareils</Text> puis{" "}
            <Text style={styles.strong}>Appairer</Text>, et te dicte le code qui s&apos;affiche.
          </Text>

          <Text style={styles.label}>Code d&apos;appairage</Text>
          <TextInput
            style={styles.codeInput}
            value={code}
            onChangeText={(text) => setCode(text.toUpperCase())}
            placeholder="ABCD-1234"
            placeholderTextColor={colors.inkFaint}
            autoCapitalize="characters"
            autoCorrect={false}
            maxLength={12}
            accessibilityLabel="Code d'appairage"
          />

          <Text style={styles.label}>Nom de cette tablette</Text>
          <TextInput
            style={styles.input}
            value={name}
            onChangeText={setName}
            placeholder="Tablette du salon"
            placeholderTextColor={colors.inkFaint}
          />

          {error ? <Banner tone="danger" title="Ca n'a pas marche">{error}</Banner> : null}

          <PrimaryButton
            label="Relier la tablette"
            icon="🔗"
            onPress={() => void submit()}
            disabled={code.trim().length < 4}
            busy={busy}
          />
        </Card>

        <Banner tone="info" title="Ce n'est pas le code de déverrouillage">
          Celui-ci ne sert qu&apos;une fois, pour relier l&apos;appareil. Ensuite, tu obtiendras du
          temps d&apos;écran en reussissant une évaluation, ou avec un code que tes parents te
          donneront.
        </Banner>

        <Text style={styles.footnote}>Serveur : {apiUrl()}</Text>
      </Screen>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  hero: { alignItems: "center", gap: 6, marginBottom: spacing(1) },
  logo: {
    width: 72,
    height: 72,
    borderRadius: 24,
    backgroundColor: colors.primary,
    alignItems: "center",
    justifyContent: "center",
  },
  logoText: { color: colors.onPrimary, fontSize: 36, fontWeight: "800" },
  brand: { color: colors.ink, ...type.title, letterSpacing: 2 },
  tagline: { color: colors.inkFaint, ...type.small },

  step: { color: colors.primaryDeep, ...type.tiny, textTransform: "uppercase" },
  title: { color: colors.ink, ...type.heading },
  help: { color: colors.inkSoft, ...type.small, lineHeight: 21 },
  strong: { color: colors.ink, fontWeight: "800" },

  label: { color: colors.inkSoft, ...type.small, marginTop: spacing(0.5) },
  codeInput: {
    backgroundColor: colors.surfaceAlt,
    borderRadius: radius.md,
    paddingVertical: spacing(2),
    color: colors.ink,
    fontSize: 26,
    fontWeight: "800",
    letterSpacing: 4,
    textAlign: "center",
  },
  input: {
    backgroundColor: colors.surfaceAlt,
    borderRadius: radius.md,
    padding: spacing(1.75),
    color: colors.ink,
    fontSize: 16,
  },
  footnote: { color: colors.inkFaint, ...type.small, textAlign: "center" },
});
