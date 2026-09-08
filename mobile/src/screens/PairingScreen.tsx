/** Appairage : la tablette recoit son identite et son secret, une seule fois. */

import { useState } from "react";
import {
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from "react-native";

import { ApiError, NetworkError, apiUrl } from "../api/client";
import { useApp } from "../state/AppState";
import { colors, radius, spacing, type } from "../theme";

export function PairingScreen() {
  const { pair } = useApp();
  const [code, setCode] = useState("");
  const [name, setName] = useState("Tablette");
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
          ? `Serveur injoignable (${apiUrl()}). Verifie le reseau.`
          : err instanceof ApiError
            ? err.message
            : "Appairage impossible.",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <KeyboardAvoidingView style={styles.root} behavior={Platform.OS === "ios" ? "padding" : undefined}>
      <ScrollView contentContainerStyle={styles.content}>
        <Text style={styles.logo}>KODA</Text>
        <Text style={styles.tagline}>L&apos;ecran se merite.</Text>

        <View style={styles.card}>
          <Text style={styles.title}>Appairer cet appareil</Text>
          <Text style={styles.help}>
            Demande a un parent de generer un code d&apos;appairage depuis son tableau de bord, puis
            saisis-le ici.
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
          />

          <Text style={styles.label}>Nom de l&apos;appareil</Text>
          <TextInput
            style={styles.input}
            value={name}
            onChangeText={setName}
            placeholder="Tablette du salon"
            placeholderTextColor={colors.inkFaint}
          />

          {error && <Text style={styles.error}>{error}</Text>}

          <TouchableOpacity
            style={[styles.button, (busy || code.length < 4) && styles.buttonDisabled]}
            onPress={() => void submit()}
            disabled={busy || code.length < 4}
          >
            {busy ? <ActivityIndicator color={colors.accentInk} /> : <Text style={styles.buttonText}>Appairer</Text>}
          </TouchableOpacity>
        </View>

        <Text style={styles.footnote}>Serveur : {apiUrl()}</Text>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.bg },
  content: { padding: spacing(3), gap: spacing(2), justifyContent: "center", flexGrow: 1 },
  logo: { color: colors.ink, fontSize: 40, fontWeight: "800", textAlign: "center", letterSpacing: 4 },
  tagline: { color: colors.inkMuted, textAlign: "center", marginBottom: spacing(2) },
  card: { backgroundColor: colors.surface, borderRadius: radius.lg, padding: spacing(3), gap: spacing(1) },
  title: { color: colors.ink, ...type.title },
  help: { color: colors.inkMuted, ...type.small, marginBottom: spacing(1) },
  label: { color: colors.inkMuted, ...type.small, marginTop: spacing(1) },
  codeInput: {
    backgroundColor: colors.bgSoft,
    borderRadius: radius.md,
    padding: spacing(2),
    color: colors.ink,
    fontSize: 26,
    fontWeight: "700",
    letterSpacing: 4,
    textAlign: "center",
  },
  input: { backgroundColor: colors.bgSoft, borderRadius: radius.md, padding: spacing(1.5), color: colors.ink, fontSize: 16 },
  button: {
    backgroundColor: colors.accent,
    borderRadius: radius.md,
    padding: spacing(2),
    alignItems: "center",
    marginTop: spacing(2),
  },
  buttonDisabled: { opacity: 0.5 },
  buttonText: { color: colors.accentInk, fontWeight: "800", fontSize: 17 },
  error: { color: colors.danger, ...type.small, marginTop: spacing(1) },
  footnote: { color: colors.inkFaint, ...type.small, textAlign: "center" },
});
