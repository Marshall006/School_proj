/**
 * KODA — application enfant.
 *
 * Navigation volontairement minimale : l'application n'a que quatre etats
 * (appairage, verrouille, examen, deverrouille). Une pile de navigation
 * complete serait une surface d'evasion supplementaire sur un appareil dont on
 * veut precisement contraindre l'usage.
 */

import { useState } from "react";
import { ActivityIndicator, StatusBar, StyleSheet, View } from "react-native";
import type { Submission } from "@koda/shared";

import { ExamScreen } from "./src/screens/ExamScreen";
import { LockScreen } from "./src/screens/LockScreen";
import { PairingScreen } from "./src/screens/PairingScreen";
import { ResultScreen } from "./src/screens/ResultScreen";
import { UnlockedScreen } from "./src/screens/UnlockedScreen";
import { AppProvider, useApp } from "./src/state/AppState";
import { colors } from "./src/theme";

type Overlay =
  | { kind: "none" }
  | { kind: "exam"; mode: "unlock" | "practice" }
  | { kind: "result"; result: Submission };

function Router() {
  const { phase } = useApp();
  const [overlay, setOverlay] = useState<Overlay>({ kind: "none" });

  if (overlay.kind === "exam") {
    return (
      <ExamScreen
        kind={overlay.mode}
        onCancel={() => setOverlay({ kind: "none" })}
        onFinished={(result) => setOverlay({ kind: "result", result })}
      />
    );
  }

  if (overlay.kind === "result") {
    return (
      <ResultScreen
        result={overlay.result}
        onUseCode={() => setOverlay({ kind: "none" })}
        onClose={() => setOverlay({ kind: "none" })}
      />
    );
  }

  switch (phase) {
    case "loading":
      return (
        <View style={styles.center}>
          <ActivityIndicator color={colors.accent} size="large" />
        </View>
      );
    case "pairing":
      return <PairingScreen />;
    case "unlocked":
      return <UnlockedScreen onPractice={() => setOverlay({ kind: "exam", mode: "practice" })} />;
    default:
      return <LockScreen onStartExam={() => setOverlay({ kind: "exam", mode: "unlock" })} />;
  }
}

export default function App() {
  return (
    <AppProvider>
      <StatusBar barStyle="light-content" backgroundColor={colors.bg} />
      <Router />
    </AppProvider>
  );
}

const styles = StyleSheet.create({
  center: { flex: 1, backgroundColor: colors.bg, alignItems: "center", justifyContent: "center" },
});
