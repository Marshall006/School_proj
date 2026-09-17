#!/usr/bin/env bash
# Lance l'application enfant (Expo) pour un telephone du meme reseau Wi-Fi.
#
# Sous WSL en mode NAT, Linux a une adresse interne (172.x) invisible du reseau
# local : un telephone ne peut pas la joindre. Plutot que de changer le mode
# reseau de WSL — qui peut rendre WSL inutilisable — on ajoute un simple pont
# cote Windows (`netsh portproxy`) et on demande a Expo d'annoncer l'adresse
# Wi-Fi de Windows. Rien n'est modifie dans WSL, et le pont s'annule en une
# commande.
#
# Usage : scripts/mobile.sh [--check]
set -uo pipefail

PORT="${KODA_EXPO_PORT:-8081}"
CHECK_ONLY=0
[ "${1:-}" = "--check" ] && CHECK_ONLY=1

bold() { printf '\033[1m%s\033[0m\n' "$1"; }
warn() { printf '\033[33m%s\033[0m\n' "$1"; }

is_wsl() { grep -qi microsoft /proc/version 2>/dev/null; }

windows_lan_ip() {
  powershell.exe -NoProfile -Command \
    "(Get-NetIPAddress -AddressFamily IPv4 | Where-Object { \$_.PrefixOrigin -in 'Dhcp','Manual' -and \$_.IPAddress -notlike '169.*' -and \$_.InterfaceAlias -notlike '*WSL*' -and \$_.InterfaceAlias -notlike '*vEthernet*' -and \$_.IPAddress -ne '127.0.0.1' } | Select-Object -First 1 -ExpandProperty IPAddress)" \
    2>/dev/null | tr -d '\r\n'
}

api_is_up() { curl -s -o /dev/null --max-time 3 "http://127.0.0.1:8000/health"; }

# --- Hors WSL : rien de particulier -----------------------------------------
if ! is_wsl; then
  api_is_up || warn "L'API ne repond pas sur le port 8000. Lancez 'make api' dans un autre terminal."
  [ "$CHECK_ONLY" = 1 ] && exit 0
  exec npx expo start --lan --port "$PORT"
fi

MODE="$(wslinfo --networking-mode 2>/dev/null || echo inconnu)"
WSL_IP="$(hostname -I | awk '{print $1}')"

# --- WSL en mode miroir : l'adresse est deja celle du reseau local -----------
if [ "$MODE" = "mirrored" ]; then
  bold "WSL en mode miroir : l'adresse $WSL_IP est directement joignable."
  api_is_up || warn "L'API ne repond pas sur le port 8000. Lancez 'make api'."
  [ "$CHECK_ONLY" = 1 ] && exit 0
  exec npx expo start --lan --port "$PORT"
fi

# --- WSL en mode NAT : pont cote Windows ------------------------------------
WIN_IP="$(windows_lan_ip)"
if [ -z "$WIN_IP" ]; then
  warn "Adresse Wi-Fi de Windows introuvable. Renseignez-la a la main :"
  warn "  REACT_NATIVE_PACKAGER_HOSTNAME=<votre-ip> npx expo start --lan"
  exit 1
fi

PROXY_OK=0
if netsh.exe interface portproxy show v4tov4 2>/dev/null | tr -d '\r' \
     | grep -qE "[[:space:]]${PORT}[[:space:]]+${WSL_IP//./\\.}[[:space:]]+${PORT}"; then
  PROXY_OK=1
fi

echo
bold "Telephone  ->  $WIN_IP:$PORT  (Windows)  ->  $WSL_IP:$PORT  (WSL)"
echo "L'API passe par ce meme port : le serveur Expo relaie /api/* vers l'API locale."
echo

if [ "$PROXY_OK" = 0 ]; then
  warn "Le pont Windows est absent (ou pointe vers une ancienne adresse WSL)."
  echo
  echo "  Ouvrez PowerShell EN ADMINISTRATEUR et collez :"
  echo
  echo "    netsh interface portproxy add v4tov4 listenport=$PORT listenaddress=0.0.0.0 connectport=$PORT connectaddress=$WSL_IP"
  echo
  echo "  Pour tout annuler plus tard :"
  echo
  echo "    netsh interface portproxy delete v4tov4 listenport=$PORT listenaddress=0.0.0.0"
  echo
  echo "  (L'adresse de WSL change a chaque redemarrage : relancez 'make mobile'"
  echo "   pour obtenir la commande a jour. Rien n'est modifie dans WSL.)"
  echo
  echo "  Le serveur Expo demarre quand meme : ajoutez le pont, puis rescannez"
  echo "  le QR code sans avoir a le redemarrer."
  echo
else
  echo "Pont Windows en place."
  echo
fi

api_is_up || warn "L'API ne repond pas sur le port 8000. Lancez 'make api' dans un autre terminal."

[ "$CHECK_ONLY" = 1 ] && exit 0

export REACT_NATIVE_PACKAGER_HOSTNAME="$WIN_IP"
exec npx expo start --lan --port "$PORT"
