/**
 * Relecture d'une correction passee.
 *
 * Accessible pendant le temps de carence : c'est la contrepartie du délai
 * impose. L'écran recharge la copie depuis le serveur et la presente avec la
 * même mise en forme que juste après l'examen, sans reafficher de code.
 */

import { useEffect, useState } from "react";
import { ActivityIndicator, StyleSheet, Text, View } from "react-native";
import type { Submission } from "@koda/shared";

import { ApiError, NetworkError, api } from "../api/client";
import { Banner, GhostButton, Screen } from "../components/kit";
import { useApp } from "../state/AppState";
import { colors, type } from "../theme";
import { ResultScreen } from "./ResultScreen";

export function ReviewScreen({
  assessmentId,
  onClose,
}: {
  assessmentId: string;
  onClose: () => void;
}) {
  const { identity } = useApp();
  const [review, setReview] = useState<Submission | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!identity) return;
    void (async () => {
      try {
        setReview(await api.review(identity.deviceToken, assessmentId));
      } catch (err) {
        setError(
          err instanceof NetworkError
            ? "Il faut être connecté pour relire ta correction."
            : err instanceof ApiError
              ? err.message
              : "Correction indisponible.",
        );
      }
    })();
  }, [identity, assessmentId]);

  if (error) {
    return (
      <Screen>
        <Banner tone="danger" title="Correction indisponible">
          {error}
        </Banner>
        <GhostButton label="Retour" onPress={onClose} />
      </Screen>
    );
  }

  if (!review) {
    return (
      <View style={styles.center}>
        <ActivityIndicator color={colors.primary} size="large" />
        <Text style={styles.loading}>Je retrouve ta copie…</Text>
      </View>
    );
  }

  return <ResultScreen result={review} reviewOnly onUseCode={onClose} onClose={onClose} />;
}

const styles = StyleSheet.create({
  center: { flex: 1, backgroundColor: colors.bg, alignItems: "center", justifyContent: "center", gap: 16 },
  loading: { color: colors.inkSoft, ...type.body },
});
