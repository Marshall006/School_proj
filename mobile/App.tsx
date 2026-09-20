/**
 * KODA — application enfant.
 *
 * Navigation volontairement minimale : cinq états seulement (appairage,
 * verrouillé, examen, résultat, relecture, déverrouillé). Une pile de
 * navigation complète serait une surface d'evasion supplementaire sur un
 * appareil dont on veut precisement contraindre l'usage.
 */

import { useState } from "react";
import { ActivityIndicator, StatusBar, StyleSheet, Text, View } from "react-native";
import type { Submission } from "@koda/shared";

import { ExamScreen } from "./src/screens/ExamScreen";
import { LockScreen } from "./src/screens/LockScreen";
import { PairingScreen } from "./src/screens/PairingScreen";
import { ResultScreen } from "./src/screens/ResultScreen";
import { ReviewScreen } from "./src/screens/ReviewScreen";
import { UnlockedScreen } from "./src/screens/UnlockedScreen";
import { AppProvider, useApp } from "./src/state/AppState";
import { colors, type } from "./src/theme";

type Overlay =
  | { kind: "none" }
  | { kind: "exam"; mode: "unlock" | "practice" }
  | { kind: "result"; result: Submission }
  | { kind: "review"; assessmentId: string };

function Router() {
  const { phase, sync } = useApp();
  const [overlay, setOverlay] = useState<Overlay>({ kind: "none" });
  // Revenir au verrou après un examen : l'état du serveur a change (carence
  // ouverte, points gagnes, code delivre), il faut le relire.
  const close = () => {
    setOverlay({ kind: "none" });
    void sync();
  };

  switch (overlay.kind) {
    case "exam":
      return (
        <ExamScreen
          kind={overlay.mode}
          onCancel={close}
          onFinished={(result) => setOverlay({ kind: "result", result })}
        />
      );
    case "result":
      return <ResultScreen result={overlay.result} onUseCode={close} onClose={close} />;
    case "review":
      return <ReviewScreen assessmentId={overlay.assessmentId} onClose={close} />;
    default:
      break;
  }

  switch (phase) {
    case "loading":
      return (
        <View style={styles.center}>
          <ActivityIndicator color={colors.primary} size="large" />
          <Text style={styles.loading}>KODA</Text>
        </View>
      );
    case "pairing":
      return <PairingScreen />;
    case "unlocked":
      return <UnlockedScreen onPractice={() => setOverlay({ kind: "exam", mode: "practice" })} />;
    default:
      return (
        <LockScreen
          onStartExam={(mode) => setOverlay({ kind: "exam", mode })}
          onReview={(assessmentId) => setOverlay({ kind: "review", assessmentId })}
        />
      );
  }
}

export default function App() {
  return (
    <AppProvider>
      <StatusBar barStyle="dark-content" backgroundColor={colors.bg} />
      <Router />
    </AppProvider>
  );
}

const styles = StyleSheet.create({
  center: {
    flex: 1,
    backgroundColor: colors.bg,
    alignItems: "center",
    justifyContent: "center",
    gap: 16,
  },
  loading: { color: colors.inkFaint, ...type.tiny, letterSpacing: 4 },
});
