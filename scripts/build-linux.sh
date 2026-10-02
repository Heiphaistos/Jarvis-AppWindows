#!/usr/bin/env bash
# Build JARVIS pour Linux : serveur Python (PyInstaller) + application Tauri
# (.deb, .AppImage, .rpm). À lancer depuis la racine du dépôt.
#
#   ./scripts/build-linux.sh            # avec cerveau local (llama-cpp, CPU)
#   LOCAL_LLM=0 ./scripts/build-linux.sh  # cerveaux cloud uniquement (build rapide)
#
# Prérequis (Debian/Ubuntu) :
#   sudo apt install python3.11-venv build-essential cmake curl \
#        libwebkit2gtk-4.1-dev libgtk-3-dev libayatana-appindicator3-dev \
#        librsvg2-dev libasound2-dev libssl-dev patchelf file
#   + Node.js 22 et Rust (rustup).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY="${PYTHON:-python3.11}"   # openwakeword dépend de tflite-runtime : Python ≤ 3.11 sous Linux
LOCAL_LLM="${LOCAL_LLM:-1}"

echo "[1/4] Interface (React)"
cd "$ROOT/client"
npm ci --no-audit --no-fund
npm run build

echo "[2/4] Environnement Python ($PY)"
cd "$ROOT/server"
[ -d .venv ] || "$PY" -m venv .venv
.venv/bin/pip install -q --upgrade pip
grep -v '^llama-cpp-python' requirements.txt > /tmp/jarvis-req.txt
.venv/bin/pip install -q -r /tmp/jarvis-req.txt pyinstaller
if [ "$LOCAL_LLM" = "1" ]; then
  # Compilé pour tout processeur x86-64 (pas seulement celui de la machine de build).
  CMAKE_ARGS="-DGGML_NATIVE=OFF" .venv/bin/pip install -q llama-cpp-python==0.3.4 \
    || echo "ATTENTION : llama-cpp non installé — cerveau local indisponible (cloud uniquement)."
fi

echo "[3/4] Serveur compilé (PyInstaller)"
.venv/bin/pyinstaller --noconfirm --clean jarvis_server.spec
mkdir -p "$ROOT/client/src-tauri/resources"
cp dist/jarvis_server "$ROOT/client/src-tauri/resources/jarvis_server"
chmod +x "$ROOT/client/src-tauri/resources/jarvis_server"

echo "[4/4] Application (Tauri)"
cd "$ROOT/client"
npx tauri build
echo
echo "Paquets : $ROOT/client/src-tauri/target/release/bundle/{deb,appimage,rpm}"
echo "Panneau web seul (sans fenêtre native) : $ROOT/server/dist/jarvis_server --web"
