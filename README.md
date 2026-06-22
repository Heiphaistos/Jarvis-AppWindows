<div align="center">
  <h1>J.A.R.V.I.S.</h1>
  <p><strong>Assistant IA local style Iron Man — LLM GGUF, voix bidirectionnelle, 28 outils, 100% local.</strong></p>

  ![Version](https://img.shields.io/badge/version-3.0.0-blue)
  ![Platform](https://img.shields.io/badge/platform-Windows%2010%2F11-0078D4?logo=windows)
  ![Stack](https://img.shields.io/badge/stack-Tauri%20v2%20%2B%20Python%20FastAPI-purple)
  ![CUDA](https://img.shields.io/badge/CUDA-12.1%2B-76B900?logo=nvidia)
  ![License](https://img.shields.io/badge/licence-MIT-green)
</div>

---

## Description

J.A.R.V.I.S. (*Just A Rather Very Intelligent System*) est un assistant IA entièrement local inspiré de l'Iron Man de Marvel. Il tourne sans aucune connexion cloud : le LLM Mistral-7B Q4 est exécuté localement via CUDA, la reconnaissance vocale (STT) et la synthèse vocale (TTS) sont assurées par Faster-Whisper et Piper. Une boucle agent multi-étapes enchaîne jusqu'à 5 appels d'outils par message, avec mémoire persistante SQLite entre les sessions.

---

## Fonctionnalités

- **LLM local 100% CUDA** — Mistral-7B-Instruct Q4_K_M via llama-cpp-python, contexte 8192 tokens, aucun appel cloud
- **STT temps réel** — Faster-Whisper (small), transcription instantanée du micro
- **TTS naturel** — Piper TTS voix française (`fr_FR-upmc-medium`) avec compresseur et présence boost
- **28 outils intégrés** — système, réseau, calcul, météo, email Gmail, gestion fichiers, mémoire persistante
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
| Frontend | React 18 + TypeScript + Tailwind CSS + Framer Motion |
| Backend | Python 3.12 + FastAPI + WebSocket |
| LLM | Mistral-7B-Instruct-v0.3 Q4_K_M (GGUF) via llama-cpp-python CUDA |
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
# → client/src-tauri/target/release/bundle/nsis/JARVIS_3.0.0_x64-setup.exe
```

Le script `LANCER-JARVIS.bat` démarre automatiquement le serveur Python puis l'interface.

---

## Outils disponibles (28)

| Catégorie | Outils |
|-----------|--------|
| **Système** | `open_application`, `kill_application`, `take_screenshot`, `read_clipboard`, `write_clipboard`, `delete_temp_files`, `create_file`, `move_file` |
| **Windows** | `get_battery`, `set_volume`, `ping_host`, `get_public_ip`, `list_directory`, `read_file` |
| **Monitoring** | `get_system_info`, `diagnose_system`, `list_processes` |
| **Web & Info** | `web_search`, `get_weather`, `get_news` |
| **Calcul** | `calculate`, `convert_units`, `translate_text` |
| **Mémoire** | `save_memory`, `recall_memory`, `list_memories` |
| **Email** | `list_emails`, `send_email` |

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

## Licence

MIT — © 2026 Heiphaistos
