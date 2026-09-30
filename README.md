<div align="center">
  <h1>J.A.R.V.I.S.</h1>
  <p><strong>Assistant IA local style Iron Man — Cerveau multi-API (local ou cloud), wake word « Hey Jarvis », HUD holographique 3D, 38 outils, vision.</strong></p>

  ![Version](https://img.shields.io/badge/version-5.0.0-blue)
  ![Platform](https://img.shields.io/badge/platform-Windows%2010%2F11-0078D4?logo=windows)
  ![Stack](https://img.shields.io/badge/stack-Tauri%20v2%20%2B%20Python%20FastAPI-purple)
  ![CUDA](https://img.shields.io/badge/CUDA-12.1%2B-76B900?logo=nvidia)
  ![License](https://img.shields.io/badge/licence-MIT-green)
</div>

---

## Description

J.A.R.V.I.S. (*Just A Rather Very Intelligent System*) est un assistant IA local inspiré de l'Iron Man de Marvel. Par défaut il tourne sans aucune connexion cloud : le LLM Mistral-7B Q4 est exécuté localement via CUDA, la reconnaissance vocale (STT) et la synthèse vocale (TTS) sont assurées par Faster-Whisper et Piper. Depuis la v4.0, le cerveau est interchangeable : n'importe quelle API compatible OpenAI (OpenAI, Gemini, Ollama, Groq, DeepSeek, xAI, OpenRouter, Mistral, LM Studio, vLLM…) ou l'API Anthropic native peut prendre le relais, avec bascule automatique sur le cerveau local en cas de panne. Une boucle agent « Fable » (réflexion → outils → vérification) enchaîne jusqu'à 5 appels d'outils par message, guidée par 6 disciplines de raisonnement routées par intention, avec mémoire persistante et journal de leçons SQLite entre les sessions.

---

## Nouveautés 5.0 — cerveau AUTO, HUD v5, outils natifs, vision

- **HUD v5** : hologramme au centre avec anneaux HUD animés, rail de télémétrie (jauges circulaires, cerveau utilisé, latence), conversation dans un panneau en verre ; chaque réponse affiche le modèle qui l'a produite et sa latence.
- **Appel d'outils natif** pour les cerveaux cloud (schémas générés depuis les signatures des 38 outils).
- **Nouveaux outils** : minuteurs et rappels annoncés à voix haute, lecture de pages web, Wikipédia, touches multimédia, vision de l'écran et des images.
- **Mode LIVE (Gemini Live)** : bouton LIVE → conversation vocale temps réel avec Gemini. Le micro part directement vers Gemini, la voix revient en flux continu sans attendre la fin de la phrase, les outils de JARVIS restent disponibles pendant la conversation, et le texte tapé au clavier reçoit aussi une réponse parlée. La voix Gemini choisie (Charon, Orus, Iapetus) est réutilisée. Requiert la clé Gemini de l'onglet CERVEAU ; modèle réglable avec `JARVIS_LIVE_MODEL` (défaut `gemini-2.5-flash-native-audio-preview-09-2025`). Pour éviter l'écho, le micro est coupé pendant que JARVIS parle.
- **Rapidité** : connexions persistantes et préchauffées vers les cerveaux, synthèse vocale en parallèle, première phrase prononcée dès la première virgule.
- **Routage multi-modèles (mode AUTO)** : chaque demande est classée en *instantané* (salutations, ordres, reformulation d'un résultat d'outil), *standard* ou *profond* (analyse, code, rédaction). Chaque niveau a sa chaîne de cerveaux, par défaut :
  - instantané : Cerebras → Groq → Gemini 2.5 Flash-Lite → Claude Haiku 4.5 → …
  - standard : Gemini 2.5 Flash → Claude Sonnet 5.5 → OpenAI → Groq → …
  - profond : Claude Opus 5.5 → Gemini 2.5 Pro → OpenAI → DeepSeek → …
  Seuls les cerveaux dont la clé est configurée sont utilisés ; le cerveau local reste le dernier recours.
- **Course au premier mot** : si le premier cerveau n'a rien dit après 0,6 s (instantané), 1,2 s (standard) ou 2,5 s (profond), le suivant démarre en parallèle ; le premier qui parle gagne, l'autre est annulé.
- **Télémétrie** : latence du premier mot et débit (tokens/s) mesurés pour chaque cerveau ; en instantané, le plus rapide passe devant ; deux échecs d'affilée mettent un cerveau en pause 90 s. Le HUD affiche le modèle, le niveau et la latence de chaque réponse.
- **Voix Gemini** (Charon, Orus, Iapetus) : voix neurales graves, jouées avec une consigne de ton « majordome IA posé ». Elles utilisent la clé Gemini de l'onglet CERVEAU ; Edge Henri puis Piper prennent le relais en cas de quota ou de coupure. Modèle et consigne réglables avec `JARVIS_GEMINI_TTS_MODEL` et `JARVIS_GEMINI_TTS_STYLE`.
- Chaînes modifiables via `POST /api/providers` (`{"name": "auto", "chains": {"deep": ["anthropic", "gemini@gemini-2.5-pro"]}}`), format `preset` ou `preset@modèle`.

## Fonctionnalités

- **LLM local 100% CUDA** — Mistral-7B-Instruct Q4_K_M via llama-cpp-python, contexte 8192 tokens, aucun appel cloud
- **Cerveau multi-API** — onglet CERVEAU : Anthropic natif + toute API OpenAI-compatible (clé stockée côté serveur, jamais dans le client), fallback local automatique
- **Wake word « Hey Jarvis »** — openWakeWord local (ONNX CPU), mode veille avec chime de confirmation, audio jamais transcrit ni conservé
- **Disciplines Fable** — 6 skills de raisonnement (deep-reasoning, calibrated-judgment, verification, communication, token-economy, memory) routés par intention, variantes compacte/complète selon le cerveau
- **Leçons apprises** — les échecs d'outils sont mémorisés et réinjectés au prompt pour ne pas être répétés
- **Boot sequence Stark** — splash d'initialisation avec checks systèmes réels et arc reactor animé
- **Hologramme 3D** — sphère de 6000 particules + anneaux orbitaux (three.js), audio-réactive sur la voix
- **Voice orb** — overlay plein écran type Siri (écoute rouge / analyse ambre / parole verte)
- **Timeline agent** — les étapes réflexion/outil/vérification s'affichent en direct
- **STT temps réel** — Faster-Whisper (small), transcription instantanée du micro
- **TTS naturel** — Piper TTS voix française (`fr_FR-upmc-medium`) avec compresseur et présence boost
- **38 outils intégrés** — système, réseau, calcul, météo, email Gmail, gestion fichiers, mémoire persistante, minuteurs et rappels parlés, lecture de pages web, Wikipédia, contrôle multimédia, vision (écran et images)
- **Agent loop multi-étapes** — enchaîne automatiquement jusqu'à 5 appels d'outils par message
- **Mémoire persistante** — SQLite long-terme, rappelée à chaque session
- **Moniteur système** — alertes temps réel CPU/RAM/disque via WebSocket
- **Interface Iron Man** — fond hexagonal animé, visualiseur arc reactor, scan line, coins décoratifs
- **Démarrage rapide** — port 8765 ouvert en < 2 s, modèles chargés en arrière-plan
- **Export conversation** — téléchargement Markdown de la session complète
- **Rendu Markdown** — titres, tableaux, citations, liens, gras/italic, bouton copie

---

## Stack technique

| Couche | Technologies |
|--------|-------------|
| Desktop | Tauri v2 + Rust |
| Frontend | React 19 + TypeScript + Tailwind CSS + Framer Motion + three.js/R3F |
| Backend | Python 3.12 + FastAPI + WebSocket |
| LLM | Mistral-7B local (défaut) · Anthropic · toute API OpenAI-compatible |
| Wake word | openWakeWord `hey_jarvis` (ONNX, CPU) |
| STT | Faster-Whisper small |
| TTS | Piper TTS (fr_FR-upmc-medium) |
| Mémoire | SQLite (`core/persistent_memory.py`) |
| Monitoring | psutil + asyncio pub/sub |

---

## Prérequis

- **Windows 10/11 x64**
- **GPU NVIDIA** avec CUDA >= 12.1 (RTX 3070+ recommandé, 8 GB VRAM minimum)
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

Placer les modèles dans `server/models/` :

```
server/models/
├── mistral-7b-instruct-v0.3.Q4_K_M.gguf    ← LLM (4.1 GB)
│   └── Source : https://huggingface.co/bartowski/Mistral-7B-Instruct-v0.3-GGUF
├── faster-whisper-small/                     ← STT (téléchargé automatiquement)
└── piper/
    └── fr_FR-upmc-medium.onnx               ← TTS voix française
```

### 4. Lancer en développement

```powershell
# Terminal 1 — backend Python
cd server
.\.venv\Scripts\Activate.ps1
python main.py

# Terminal 2 — frontend Tauri
cd client
npm install
npx tauri dev
```

### 5. Build production

```powershell
cd client
npx tauri build
# → client/src-tauri/target/release/JARVIS.exe
# → client/src-tauri/target/release/bundle/nsis/JARVIS_4.0.0_x64-setup.exe
```

Le script `LANCER-JARVIS.bat` démarre automatiquement le serveur Python puis l'interface.

---

## Outils disponibles (38)

| Catégorie | Outils |
|-----------|--------|
| **Système** | `open_application`, `kill_application`, `take_screenshot`, `read_clipboard`, `write_clipboard`, `delete_temp_files`, `create_file`, `move_file` |
| **Windows** | `get_battery`, `set_volume`, `ping_host`, `get_public_ip`, `list_directory`, `read_file` |
| **Monitoring** | `get_system_info`, `diagnose_system`, `list_processes` |
| **Web & Info** | `web_search`, `get_weather`, `get_news` |
| **Calcul** | `calculate`, `convert_units`, `translate_text` |
| **Mémoire** | `save_memory`, `recall_memory`, `list_memories` |
| **Email** | `list_emails`, `send_email` |
| **Assistant** | `set_timer`, `set_reminder`, `list_reminders`, `cancel_reminder`, `media_control` |
| **Recherche** | `read_webpage`, `wikipedia_summary` |
| **Vision** | `analyze_screen`, `analyze_image` (Gemini, Claude ou OpenAI selon les clés configurées) |

---

## Raccourcis clavier

| Raccourci | Action |
|-----------|--------|
| `Ctrl+K` | Focus sur la saisie |
| `Escape` | Vider et quitter la saisie |

---

## Aperçu

> Captures disponibles lors de la prochaine release publique.

---

## Crédits & inspirations

L'interface cinématique et le système multi-provider portent des idées de deux projets
open source (MIT) réimplémentées dans cette stack :

- [harsh-raj00/my-jarvis](https://github.com/harsh-raj00/my-jarvis) — boot sequence, hologramme 3D, voice orb
- [hzaid01/Jarvis](https://github.com/hzaid01/Jarvis) — architecture multi-provider LLM

---

## Licence

MIT — © 2026 Heiphaistos
