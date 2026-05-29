# J.A.R.V.I.S. v3.0.0

**Just A Rather Very Intelligent System**

Assistant IA local Iron Man-style — Tauri v2 · React · Python FastAPI · LLM GGUF CUDA

---

## Fonctionnalités

- **LLM local CUDA** — Mistral-7B-Instruct Q4_K_M via llama-cpp-python, contexte 8192 tokens
- **Voix bidirectionnelle** — STT Faster-Whisper (small) + TTS Piper avec traitement audio JARVIS (compresseur, présence boost)
- **28 outils intégrés** — système, réseau, calcul, météo, email Gmail, mémoire persistante SQLite
- **Agent loop multi-étapes** — enchaîne jusqu'à 5 appels d'outils par message automatiquement
- **Mémoire persistante** — SQLite long-terme, rappelée à chaque session
- **Moniteur système** — alertes temps réel CPU/RAM/disque via WebSocket
- **Markdown rendu** — titres, tableaux, citations, liens, italic/gras, bouton copie
- **Export conversation** — téléchargement Markdown de la session complète
- **Démarrage rapide** — port 8765 ouvert en <2s, modèles chargés en background
- **Interface Iron Man** — fond hexagonal animé, visualiseur arc reactor, scan line, coins décoratifs

---

## Stack

| Couche | Technologie |
|--------|-------------|
| Desktop | Tauri v2 · Rust |
| Frontend | React 18 · TypeScript · Tailwind CSS · Framer Motion |
| Backend | Python 3.12 · FastAPI · WebSocket |
| LLM | Mistral-7B-Instruct-v0.3 Q4_K_M (GGUF) via llama-cpp-python CUDA |
| STT | Faster-Whisper small |
| TTS | Piper TTS (fr_FR-upmc-medium) |
| Mémoire | SQLite via `core/persistent_memory.py` |
| Monitoring | psutil · asyncio pub/sub |

---

## Prérequis

- **Windows 10/11 x64**
- **NVIDIA GPU** avec CUDA ≥ 12.1 (RTX 3070+ recommandé, 8 GB VRAM)
- **Python 3.10–3.12**
- **Node.js 18+**
- **Rust + Cargo** (stable)

---

## Installation

### 1. Cloner le dépôt

```powershell
git clone https://github.com/heiphaistos44-crypto/Jarvis.git
cd Jarvis
```

### 2. Configurer le backend Python

```powershell
cd server
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 3. Télécharger les modèles

```
server/models/
├── mistral-7b-instruct-v0.3.Q4_K_M.gguf    ← LLM (4.1 GB)
├── faster-whisper-small/                     ← STT (auto-téléchargé)
└── piper/
    └── fr_FR-upmc-medium.onnx               ← TTS voix française
```

Le modèle LLM peut être téléchargé depuis [Hugging Face — Mistral-7B-Instruct-v0.3-GGUF](https://huggingface.co/bartowski/Mistral-7B-Instruct-v0.3-GGUF).

### 4. Lancer en développement

```powershell
# Terminal 1 — backend
cd server
.\.venv\Scripts\Activate.ps1
python main.py

# Terminal 2 — frontend
cd client
npm install
npx tauri dev
```

### 5. Build production

```powershell
cd client
npx tauri build
# → client/src-tauri/target/release/JARVIS.exe
# → client/src-tauri/target/release/bundle/nsis/JARVIS_1.0.0_x64-setup.exe
```

L'exécutable `JARVIS.exe` démarre automatiquement le serveur Python au lancement.

---

## Outils disponibles (28)

**Système** : `open_application`, `kill_application`, `take_screenshot`, `read_clipboard`, `write_clipboard`, `delete_temp_files`, `create_file`, `move_file`

**Windows** : `get_battery`, `set_volume`, `ping_host`, `get_public_ip`, `list_directory`, `read_file`

**Monitoring** : `get_system_info`, `diagnose_system`, `list_processes`

**Web & Info** : `web_search`, `get_weather`, `get_news`

**Calcul** : `calculate`, `convert_units`, `translate_text`

**Mémoire** : `save_memory`, `recall_memory`, `list_memories`

**Email** : `list_emails`, `send_email`

---

## Raccourcis clavier

| Raccourci | Action |
|-----------|--------|
| `Ctrl+K` | Focus sur la saisie |
| `Escape` | Vider et quitter la saisie |

---

## Architecture

```
Jarvis/
├── server/                  # Backend Python
│   ├── main.py              # FastAPI app + lifespan + sidecar entry
│   ├── api/
│   │   ├── routes.py        # REST endpoints (/health, /system_info, …)
│   │   └── websocket.py     # WS handler + agent loop
│   ├── core/
│   │   ├── llm.py           # LLMManager + system prompt + tool call parser
│   │   ├── stt.py           # STTManager (Faster-Whisper)
│   │   ├── tts.py           # TTSManager (Piper)
│   │   ├── memory.py        # Context memory par session
│   │   ├── persistent_memory.py  # Mémoire long-terme SQLite
│   │   └── monitor.py       # Moniteur CPU/RAM/disque + pub/sub WebSocket
│   ├── tools/
│   │   ├── registry.py      # ToolRegistry — 28 outils enregistrés
│   │   ├── system_tools.py  # open/kill/screenshot/clipboard/files
│   │   ├── windows_tools.py # battery/volume/ping/ip/directory/read_file
│   │   ├── info_tools.py    # system_info/diagnose/processes
│   │   ├── web_tools.py     # web_search/weather/news
│   │   ├── calc_tools.py    # calculate/convert/translate
│   │   ├── memory_tools.py  # save/recall/list memories
│   │   └── email_tools.py   # Gmail OAuth + list/send
│   └── utils/
│       ├── config.py        # Settings (model paths, ports, …)
│       ├── logger.py        # Logger centralisé
│       └── rate_limiter.py  # Rate limiting par connexion WS
│
└── client/                  # Frontend Tauri
    ├── src-tauri/
    │   └── src/
    │       ├── lib.rs        # Setup Tauri + auto-start sidecar
    │       └── commands/
    │           └── sidecar.rs  # launch_server / kill_server
    └── src/
        ├── App.tsx           # Layout principal + raccourcis clavier
        ├── stores/
        │   └── jarvisStore.ts  # Zustand store + TTS audio pipeline
        ├── hooks/
        │   ├── useWebSocket.ts   # WS avec reconnexion exponentielle
        │   ├── useJarvis.ts      # Orchestrateur text/mic
        │   └── useAudioCapture.ts
        └── components/
            ├── ChatPanel/    # Messages + rendu Markdown + copie
            ├── CommandInput/ # Saisie texte
            ├── VoiceVisualizer/  # Visualiseur arc reactor
            └── Settings/     # Voix, TTS, Gmail
```

---

## Variables de configuration

Fichier `server/utils/config.py` :

| Paramètre | Défaut | Description |
|-----------|--------|-------------|
| `host` | `127.0.0.1` | Hôte du serveur |
| `port` | `8765` | Port WebSocket/HTTP |
| `n_ctx` | `8192` | Fenêtre de contexte LLM |
| `n_gpu_layers` | `-1` | Layers GPU (−1 = tout) |
| `max_context_messages` | `30` | Messages gardés en mémoire de session |

---

## Changelog

### v3.0.0 (2026-05-29)
- Agent loop multi-étapes (max 5 outils par message)
- 9 nouveaux outils : battery, volume, ping, IP, directory, read_file, calculate, convert_units, translate_text
- Moniteur système proactif (CPU/RAM/disque) avec alertes WebSocket
- Markdown 2.0 : titres, tableaux, citations, liens, bouton copie, export conversation
- Démarrage non-bloquant : port ouvert en <2s, modèles en background
- Broadcast `server_status` dynamique après chargement LLM/STT
- Contexte étendu à 8192 tokens, historique à 30 messages
- Raccourcis clavier (Ctrl+K, Escape)

### v2.0.0 (2026-05-28)
- Sidecar Rust : démarrage automatique du serveur Python depuis JARVIS.exe
- Support origine Tauri v2 (`http://tauri.localhost`)
- Langue française forcée via `chat_format="mistral-instruct"`
- Microphone auto-autorisé via `--use-fake-ui-for-media-stream`

### v1.0.0 (2026-05-27)
- Version initiale : LLM local CUDA + STT + TTS + interface Iron Man
