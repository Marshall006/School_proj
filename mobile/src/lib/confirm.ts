/**
 * Demande de confirmation, sur toutes les plateformes.
 *
 * `Alert.alert` de React Native n'est pas implemente dans un navigateur : le
 * dialogue ne s'affiche jamais et l'action reste bloquée sans le moindre
 * message. Comme l'application tourne aussi sur le web (démonstration sans
 * téléphone), la confirmation passe ici par le dialogue natif du navigateur.
 */

import { Alert, Platform } from "react-native";

export function confirmAsync(options: {
  title: string;
  message: string;
  confirmLabel: string;
  cancelLabel: string;
}): Promise<boolean> {
  if (Platform.OS === "web") {
    if (typeof window === "undefined" || typeof window.confirm !== "function") {
      return Promise.resolve(true);
    }
    return Promise.resolve(window.confirm(`${options.title}\n\n${options.message}`));
  }

  return new Promise((resolve) => {
    Alert.alert(options.title, options.message, [
      { text: options.cancelLabel, style: "cancel", onPress: () => resolve(false) },
      { text: options.confirmLabel, onPress: () => resolve(true) },
    ]);
  });
}
