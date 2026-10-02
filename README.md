<div align="center">
  <h1>J.A.R.V.I.S.</h1>
  <p><strong>Assistant IA local style Iron Man — Cerveau multi-API (local ou cloud), wake word « Hey Jarvis », HUD holographique 3D, 51 outils, vision.</strong></p>

  ![Version](https://img.shields.io/badge/version-5.5.1-blue)
  ![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux%20%7C%20Web-0078D4)
  ![Stack](https://img.shields.io/badge/stack-Tauri%20v2%20%2B%20Python%20FastAPI-purple)
  ![CUDA](https://img.shields.io/badge/CUDA-12.1%2B-76B900?logo=nvidia)
  ![License](https://img.shields.io/badge/licence-MIT-green)
</div>

---

## Description

J.A.R.V.I.S. (*Just A Rather Very Intelligent System*) est un assistant IA local inspiré de l'Iron Man de Marvel. Par défaut il tourne sans aucune connexion cloud : le LLM Mistral-7B Q4 est exécuté localement via CUDA, la reconnaissance vocale (STT) et la synthèse vocale (TTS) sont assurées par Faster-Whisper et Piper. Depuis la v4.0, le cerveau est interchangeable : n'importe quelle API compatible OpenAI (OpenAI, Gemini, Ollama, Groq, DeepSeek, xAI, OpenRouter, Mistral, LM Studio, vLLM…) ou l'API Anthropic native peut prendre le relais, avec bascule automatique sur le cerveau local en cas de panne. Une boucle agent « Fable » (réflexion → outils → vérification) enchaîne jusqu'à 5 appels d'outils par message, guidée par 6 disciplines de raisonnement routées par intention, avec mémoire persistante et journal de leçons SQLite entre les sessions.

---

## Nouveautés 5.5 — version web, panneau web local, Linux

- **Panneau web local** (comme NiTriTe Agent) : `jarvis_server --web` (ou `JARVIS-Web.bat` dans le portable) fait tourner JARVIS sur le PC **sans fenêtre native** ; l'interface s'ouvre dans le navigateur déjà installé, déjà connectée. Même JARVIS, mêmes outils, une WebView en moins. Menu 🌐 : démarrer avec la session, arrêter JARVIS. Accès réservé à l'onglet ouvert par JARVIS : clé de 256 bits dans le fragment de l'URL échangée contre un cookie `HttpOnly`, vérification du Host (DNS rebinding) et de l'origine. Options `--app` (fenêtre Edge/Chrome sans onglets), `--lan`, `--port`, `--no-browser`.
- **Version web hébergée** : `deploy/web/` (Docker + nginx) pour l'installer sur un VPS en HTTPS, avec mot de passe. Cerveaux, voix et transcription dans le cloud ; les 27 outils qui agiraient sur la machine (fenêtres, fichiers, NiTriTe…) y sont retirés. Mesuré : **≈ 50 Mo de RAM au repos, ≈ 64 Mo avec 10 sessions vocales, image de 351 Mo**. Interface utilisable sur téléphone. Détails et chiffres : [`docs/WEB.md`](docs/WEB.md).
- **Linux** : application de bureau (.deb, .AppImage, .rpm) et serveur. Outils adaptés : applications (équivalents Linux de Chrome, Bloc-notes, Explorateur, Calculatrice, Terminal…), capture d'écran (gnome-screenshot, Spectacle, grim, scrot), presse-papiers (wl-clipboard, xclip), volume (PipeWire, PulseAudio, ALSA), batterie, ping, journal système (journald), multimédia via MPRIS (playerctl), contrôle des fenêtres et du clavier via xdotool et wmctrl (session X11). Données dans `~/.local/share/JARVIS`. Build : `scripts/build-linux.sh` ou la CI GitHub.
- **Interface dans le navigateur** : micro via le navigateur (ré-échantillonné en 16 kHz avant l'envoi : trois fois moins de données), adresses du serveur relatives, barre de titre adaptée.
- **Sécurité de l'application** : le WebSocket vérifiait déjà l'origine ; c'est maintenant le cas de toute l'API en écriture. Un site ouvert dans le navigateur pouvait par exemple remplacer le fichier d'identifiants Gmail (un envoi de fichier échappe au contrôle CORS du navigateur).
- **Corrections** : identifiants Gmail perdus à chaque arrêt de l'exécutable compilé (ils étaient rangés dans le dossier temporaire de PyInstaller) ; sans voix locale Piper, JARVIS restait muet : il prend maintenant la voix en ligne Henri ; retour OAuth Gmail sur le bon port ou la bonne adresse publique.

## Nouveautés 5.2 — diagnostic NiTriTe, contrôle du PC, voix fiable

- **Diagnostic avancé avec NiTriTe Agent** : JARVIS se connecte à [NiTriTe Agent](https://github.com/Heiphaistos/Nitrite-We-Panel-) (il lit son port et son jeton dans `%LOCALAPPDATA%\NiTriTe-WebPanel\session.json`, même sécurité que le navigateur). « Fais-moi un rapport de santé de mon PC », « ma batterie va bien ? », « état de mes disques », « mon PC chauffe », « j'ai eu des écrans bleus » → santé et cycles de la batterie, SMART des disques, températures CPU/GPU, écrans bleus et journal Système, programmes au démarrage, santé de Windows, performances, matériel. Les **alertes** (batterie sous 80 %, disque en « Warning », secteurs réalloués, 80/90 °C, redémarrage en attente…) sont calculées localement ; le rapport complet est enregistré dans `Documents\JARVIS\Rapports`. Le briefing signale aussi les alertes. **Lecture seule** : aucune commande qui efface, désinstalle ou modifie le système n'est accessible à JARVIS. « Lance NiTriTe » démarre l'agent sans navigateur (`JARVIS_NITRITE_AGENT` pour indiquer le chemin de l'exe) ; sans lui, un diagnostic de base (psutil) reste disponible.
- **Outils en parallèle** : plusieurs informations indépendantes sont récupérées d'un coup — « la météo à Paris, Lyon et Nice » lance les trois requêtes en même temps (4 max), au lieu de l'une après l'autre. Claude, OpenAI, Gemini et les API compatibles transmettent maintenant tous leurs appels d'outils, plus seulement le premier.
- **Contrôle du PC, au clavier comme à la voix** : lister les fenêtres, en mettre une au premier plan, la réduire, l'agrandir ou la fermer (fermeture normale : l'application peut proposer d'enregistrer) ; taper du texte (accents et emoji compris, via l'API Unicode de Windows, sans toucher au presse-papiers) ; envoyer des raccourcis (« ctrl+s », « alt+tab », « win+d ») ; remplir un formulaire champ par champ avec Tab entre chaque, et le valider. Sans fenêtre précisée, la cible est celle qui était au premier plan avant JARVIS — jamais JARVIS lui-même. Aucune dépendance ajoutée (API Win32 via ctypes).
- **Mode vocal fiable** : si une clé **Groq** (gratuite) ou OpenAI est configurée dans l'onglet CERVEAU, la voix est transcrite par Whisper large-v3 (Groq, ~0,3 s) ou gpt-4o-mini-transcribe — bien plus juste en français que le Whisper « small » local, qui reste le secours hors ligne (`JARVIS_CLOUD_STT=0` pour ne rien envoyer). Le filtre anti-hallucinations compare maintenant la phrase entière : « ouvre google.com », « traduction de… » ou « merci » ne sont plus jetés à tort, tandis que les génériques inventés par Whisper (« Sous-titrage ST' 501 », « merci d'avoir regardé »), les boucles et l'écho de la consigne sont écartés ; les segments peu fiables (logprob, taux de compression) aussi. « Jervis », « Jar vice »… redeviennent « Jarvis ». En mode vocal, JARVIS répond en une à trois phrases parlées, fait répéter une phrase incohérente plutôt que d'inventer, et demande confirmation avant d'agir quand la transcription est incertaine (marquée « (?) » à l'écran).
- **Routines** : « tous les matins en semaine à 7h30, fais-moi le briefing » → JARVIS annonce à voix haute un briefing condensé en quelques phrases (date, météo, rappels, alertes PC, actualité) ; « chaque lundi à 9h, contrôle la santé du PC » → contrôle via NiTriTe, **muet si tout va bien** ; ou un rappel récurrent (« tous les soirs à 21h, pense à tes médicaments »). Jours : tous les jours, en semaine, week-end, liste ou plage (« lundi-vendredi »). Une routine manquée de plus d'une heure (PC éteint) est reportée au lendemain au lieu de se déclencher à l'allumage. Liste et annulation avec `list_reminders` / `cancel_reminder`.

## Nouveautés 5.1 — mémoire, recherche, actions en chaîne

- **Mémoire automatique** : après chaque échange (clavier, voix ou LIVE), JARVIS retient de lui-même ce que vous dites de vous — prénom, ville, goûts, projets, proches, habitudes — sans qu'il faille dire « retiens ». Un fait qui change est mis à jour (même clé), « oublie… » l'efface. Quand vous le corrigez, il en tire une **leçon** réinjectée dans ses consignes. Les faits sans ambiguïté (prénom, ville, âge, métier) sont extraits localement ; le reste par le cerveau le plus rapide, en arrière-plan, sans ralentir la réponse. Jamais de mot de passe, code ni numéro de carte. Onglet **MÉMOIRE** : tout voir, supprimer un souvenir ou une leçon, couper la fonction (ou `JARVIS_AUTO_MEMORY=0`). Seuls les souvenirs pertinents pour la demande sont injectés dans le prompt (identité et préférences toujours).
- **Mémoire des conversations** : chaque session est résumée et archivée (tous les 6 messages, à l'effacement de l'historique et à la fermeture). « De quoi on a parlé hier ? » retrouve les échanges passés ; les conversations récentes et pertinentes sont rappelées à JARVIS. Dans une longue discussion, les messages qui sortent de la fenêtre de contexte sont condensés en un résumé glissant : JARVIS garde le fil du début. Les leçons injectées sont aussi triées par pertinence avec la demande.
- **Recherche approfondie** : « fais une recherche sur… », « renseigne-toi sur… » → JARVIS interroge le web, lit en parallèle plusieurs sources de sites différents, garde les passages qui répondent à la question et rédige une synthèse structurée avec citations [1], [2]… en signalant contradictions et incertitudes (cerveau standard ou profond, jamais le plus rapide).
- **Recherche web et actualités sans dépendance** : `web_search` et `get_news` reposaient sur `duckduckgo_search`, absent de `requirements.txt` — ils échouaient sur une installation neuve. Ils utilisent maintenant DuckDuckGo puis Bing (recherche) et Google News puis Bing News (actualités), avec bascule automatique si un moteur ne répond pas.
- **Actions en plusieurs étapes** : avec un cerveau cloud, JARVIS enchaîne jusqu'à 4 outils dans une même demande (« regarde la météo à Lyon et mets-moi un rappel parapluie s'il pleut ») : il lit chaque résultat avant de décider de l'étape suivante. Un même appel n'est jamais exécuté deux fois (pas de rappel ni de mail en double) ; le dernier tour force toujours une réponse.
- **Voix propre** : la synthèse vocale ne lit plus la mise en forme — ni astérisques, titres, puces, citations [n], URL ou blocs de code ; l'écran garde la réponse formatée.

## Nouveautés 5.0 — cerveau AUTO, HUD v5, outils natifs, vision

- **HUD v5** : hologramme au centre avec anneaux HUD animés, rail de télémétrie (jauges circulaires, cerveau utilisé, latence), conversation dans un panneau en verre ; chaque réponse affiche le modèle qui l'a produite et sa latence.
- **Appel d'outils natif** pour les cerveaux cloud (schémas générés depuis les signatures des 51 outils).
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
- **51 outils intégrés** — système, réseau, calcul, météo, email Gmail, gestion fichiers, mémoire persistante, minuteurs et rappels parlés, lecture de pages web, Wikipédia, contrôle multimédia, vision (écran et images)
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
| Desktop | Tauri v2 + Rust (Windows, Linux) |
| Web | panneau local (`--web`) ou version hébergée Docker (`deploy/web/`) |
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

- **Windows 10/11 x64** ou **Linux x86-64** (Ubuntu 22.04+, Debian 12+, Fedora…)
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

### Linux

```bash
./scripts/build-linux.sh          # → client/src-tauri/target/release/bundle/{deb,appimage,rpm}
LOCAL_LLM=0 ./scripts/build-linux.sh   # sans cerveau local (build rapide, cerveaux cloud)
```

Contrôle des fenêtres et du clavier : `sudo apt install xdotool wmctrl` (session X11). Presse-papiers : `wl-clipboard` (Wayland) ou `xclip`. Multimédia : `playerctl`.

### Panneau web et version hébergée

```bash
cd server && python main.py --web          # panneau web local (après npm run build dans client/)
docker compose -f deploy/web/docker-compose.yml up -d --build   # version hébergée (VPS)
```

Voir [`docs/WEB.md`](docs/WEB.md).

---

## Outils disponibles (51)

| Catégorie | Outils |
|-----------|--------|
| **Système** | `open_application`, `kill_application`, `take_screenshot`, `read_clipboard`, `write_clipboard`, `delete_temp_files`, `create_file`, `move_file` |
| **Windows** | `get_battery`, `set_volume`, `ping_host`, `get_public_ip`, `list_directory`, `read_file` |
| **Monitoring** | `get_system_info`, `diagnose_system`, `list_processes` |
| **Contrôle du PC** | `list_windows`, `window_action`, `type_text`, `press_keys`, `fill_form` |
| **Diagnostic NiTriTe** | `pc_diagnostic`, `pc_health_report`, `nitrite_start` |
| **Web & Info** | `web_search`, `deep_research`, `get_weather`, `get_news` |
| **Calcul** | `calculate`, `convert_units`, `translate_text` |
| **Mémoire** | `save_memory`, `recall_memory`, `list_memories`, `forget_memory`, `recall_conversations` (+ mémoire automatique) |
| **Email** | `list_emails`, `send_email` |
| **Assistant** | `briefing`, `set_routine`, `set_timer`, `set_reminder`, `list_reminders`, `cancel_reminder`, `media_control` |
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
