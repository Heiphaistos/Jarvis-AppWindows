# JARVIS dans le navigateur : panneau web local et version hébergée

JARVIS a toujours été composé de deux morceaux : un **serveur** (Python : cerveau, voix, outils, mémoire) et une **interface** (React) qui lui parle en HTTP et en WebSocket. L'application de bureau n'est que l'interface dans une fenêtre Tauri. Depuis la 5.4, le serveur sait aussi servir l'interface lui-même, ce qui donne deux nouvelles façons d'utiliser JARVIS.

| | Application (Tauri) | Panneau web local (`--web`) | Version hébergée (VPS) |
|---|---|---|---|
| Où tourne le serveur | sur le PC | sur le PC | sur le VPS |
| Interface | fenêtre native | onglet du navigateur | onglet du navigateur, téléphone compris |
| Contrôle du PC (fenêtres, fichiers, NiTriTe…) | oui | oui | **non** |
| Cerveau local, Whisper local | oui | oui | non (cloud) |
| Accès | le PC | le PC (ou le réseau local avec `--lan`) | partout, avec mot de passe |

## 1. Panneau web local — comme NiTriTe Agent

Le serveur tourne sur le PC, mais **sans fenêtre native** : l'interface s'ouvre dans le navigateur déjà installé (Edge, Chrome, Firefox).

- **Windows (portable)** : double-cliquer `JARVIS-Web.bat`, ou `jarvis_server.exe --web`.
- **Linux** : `jarvis_server --web` (binaire `jarvis-web-linux-x86_64` des releases), ou depuis les sources `python main.py --web`.

L'onglet s'ouvre tout seul, déjà connecté. Relancer la commande alors que JARVIS tourne rouvre simplement l'onglet. Le menu 🌐 en haut à droite propose **Démarrer avec la session** (Windows : clé `Run` de l'utilisateur ; Linux : `~/.config/autostart`) et **Arrêter JARVIS**. JARVIS ne s'arrête pas quand on ferme l'onglet : les routines et les rappels continuent d'être annoncés.

| Option | Effet |
|---|---|
| `--port N` | port d'écoute (défaut 8765, le suivant libre si l'application de bureau l'occupe) |
| `--no-browser` | ne pas ouvrir le navigateur (le lien avec la clé est écrit dans la console) |
| `--app` | fenêtre d'application Edge/Chrome, sans onglets ni barre d'adresse |
| `--lan` | accessible depuis un autre appareil du réseau local (partager le lien avec la clé) |

### Ce que ça économise

Le panneau n'ajoute pas de WebView (WebView2 sous Windows, WebKitGTK sous Linux) à côté du navigateur qu'on a déjà ouvert : c'est un processus de rendu en moins. Le serveur, lui, est le même : ce qui pèse vraiment sur un PC modeste, ce sont les **modèles locaux** (Mistral-7B : ~5 Go de RAM/VRAM ; Whisper small : ~0,5 Go). Sur une petite machine :

1. onglet **CERVEAU** → un cerveau cloud (Gemini Flash et Groq ont des offres gratuites) : le LLM local n'est jamais sollicité ;
2. une clé **Groq** suffit aussi pour la voix (Whisper large-v3 dans le cloud, plus juste que le small local) ;
3. disposition **Compact** (barre du haut) : pas d'hologramme 3D, le plus léger pour le navigateur.

### Sécurité

Le panneau donne accès à des outils qui agissent sur le PC ; il est verrouillé comme NiTriTe Agent :

- écoute sur `127.0.0.1` uniquement (sauf `--lan`, explicite) ;
- à chaque lancement, une **clé aléatoire de 256 bits** est transmise à l'onglet dans le fragment de l'URL (`#t=…`, jamais envoyé sur le réseau), puis échangée contre un cookie de session `HttpOnly` et effacée de la barre d'adresse ; toute l'API et le WebSocket l'exigent ;
- l'en-tête `Host` est vérifié (parade au *DNS rebinding*) et toute écriture ou connexion WebSocket venant d'une autre origine est refusée : un site ouvert dans un autre onglet ne peut pas piloter JARVIS ;
- Content-Security-Policy stricte, pas d'intégration en iframe, pas de Referer.

L'application de bureau profite aussi de la vérification d'origine sur toute l'API en écriture (le WebSocket l'avait déjà) : avant la 5.4, un site ouvert dans le navigateur pouvait par exemple remplacer le fichier d'identifiants Gmail, car un envoi de fichier échappe au contrôle CORS.

## 2. Version hébergée sur le VPS

Le serveur tourne dans un conteneur Docker, derrière nginx en HTTPS. Le navigateur n'autorise le micro qu'en HTTPS : le certificat est obligatoire.

```bash
git clone https://github.com/Heiphaistos/Jarvis-AppWindows.git /opt/jarvis-app
cd /opt/jarvis-app
cp deploy/web/.env.example deploy/web/.env
nano deploy/web/.env           # JARVIS_PASSWORD (long) et JARVIS_PUBLIC_ORIGIN
docker compose -f deploy/web/docker-compose.yml up -d --build

sudo cp deploy/web/nginx-jarvis-app.conf /etc/nginx/sites-available/jarvis-app.heiphaistos.org
sudo ln -s /etc/nginx/sites-available/jarvis-app.heiphaistos.org /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
sudo certbot --nginx -d jarvis-app.heiphaistos.org
```

Puis ouvrir `https://jarvis-app.heiphaistos.org`, se connecter et saisir les clés des cerveaux dans l'onglet **CERVEAU** (elles restent sur le serveur, dans le volume `jarvis-data`). Mise à jour : `git pull && docker compose -f deploy/web/docker-compose.yml up -d --build`.

Ce qui change par rapport à l'application :

- **27 outils retirés** : tout ce qui agit sur « la machine » (fenêtres, clavier, fichiers, applications, presse-papiers, capture d'écran, batterie, volume, processus, NiTriTe, médias). Sur un VPS, ils agiraient sur le VPS. JARVIS le sait et le dit si on le lui demande.
- Restent : conversation, recherche web et recherche approfondie, météo, actualités, Wikipédia, lecture de pages, calculs et conversions, traduction, mémoire, minuteurs, rappels et routines (annoncés dans l'onglet ouvert), Gmail, mode LIVE Gemini.
- Pas de modèle local : cerveaux cloud, transcription Groq ou OpenAI, voix Edge (Henri) ou Gemini.
- Pas de mot-clé « Hey Jarvis » : il imposerait d'envoyer le micro en continu au serveur.
- Un seul compte (un mot de passe) : la mémoire est celle d'une personne. Cinq essais de mot de passe par adresse IP toutes les 5 minutes.

### Ressources mesurées

Mesures faites sur l'image de ce dépôt (`docker stats`), cerveaux dans le cloud :

| | Valeur |
|---|---|
| Image Docker | **351 Mo** sur le disque (Python 3.12 slim + dépendances + interface) |
| RAM au repos | **≈ 50 Mo** |
| RAM, 10 sessions simultanées qui envoient de la voix | **≈ 64 Mo** |
| CPU | ≈ 0 % au repos, quelques % pendant une réponse (le calcul se fait chez le fournisseur du cerveau) |
| Données | quelques Mo (mémoire SQLite, rappels, journaux quotidiens dans `/data/logs`) |
| Réseau, micro ouvert | ≈ 100 Ko/s montants (audio 16 kHz), seulement pendant qu'on parle |
| Réseau, réponse parlée | ≈ 6 Ko/s descendants (MP3) |

Le conteneur est plafonné à 512 Mo et 1 CPU dans `docker-compose.yml` ; il tient largement sur le plus petit VPS. Le coût réel est celui des API des cerveaux : nul avec les offres gratuites de Gemini et Groq pour un usage personnel.

À éviter : faire tourner le cerveau local (Mistral-7B) sur le VPS. Sans GPU, il demande ~6 Go de RAM et ne produit que quelques mots par seconde : la version hébergée est faite pour les cerveaux cloud.

## Et ensuite : le VPS comme cerveau, le PC comme agent

Une étape suivante possible : un petit agent sur le PC, connecté au VPS, qui n'exécuterait que les outils locaux (fenêtres, fichiers, NiTriTe). On aurait JARVIS partout via le web, avec la main sur le PC quand il est allumé, et presque rien qui tourne sur le PC lui-même.
