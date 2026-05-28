# J.A.R.V.I.S. — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Construire un assistant IA local Iron Man-style avec interface Tauri v2 + React, backend Python FastAPI, LLM local GGUF, STT/TTS temps réel et tool calling sécurisé.

**Architecture:** Frontend Tauri v2 communique via WebSocket avec un serveur FastAPI Python embarqué comme sidecar. Le sidecar orchestre le LLM (llama-cpp-python CUDA), Faster-Whisper (STT), Piper TTS, et un système de wake word. Les outils système sont exposés via un registre de fonctions whitelistées.

**Tech Stack:** Tauri v2 · Rust · React 18 · TypeScript · Tailwind CSS · Python 3.14 · FastAPI · llama-cpp-python · Faster-Whisper · Piper TTS · openWakeWord · Zustand · Framer Motion · Vite 6

**Hardware cible:** RTX 3070 8GB VRAM · CUDA 13.1 · Driver 591.74 · Windows 11

---

## Structure des fichiers

```
C:\Users\Momo\Documents\Jarvis\
├── client/                          # Tauri v2 + React frontend
│   ├── src/
│   │   ├── components/
│   │   │   ├── ChatPanel/
│   │   │   │   ├── ChatPanel.tsx    # Liste des messages
│   │   │   │   ├── Message.tsx      # Bulle message individuelle
│   │   │   │   └── TypingIndicator.tsx
│   │   │   ├── VoiceVisualizer/
│   │   │   │   ├── VoiceVisualizer.tsx  # Sphère audio animée
│   │   │   │   └── AudioCanvas.tsx      # Web Audio API canvas
│   │   │   ├── StatusBar/
│   │   │   │   └── StatusBar.tsx    # LISTENING / THINKING / SPEAKING
│   │   │   └── CommandInput/
│   │   │       └── CommandInput.tsx # Champ texte + bouton PTT
│   │   ├── hooks/
│   │   │   ├── useWebSocket.ts     # Connexion WS au serveur Python
│   │   │   ├── useAudioCapture.ts  # Capture micro + envoi audio
│   │   │   └── useJarvis.ts        # Hook orchestrateur principal
│   │   ├── stores/
│   │   │   └── jarvisStore.ts      # Zustand store (messages, état)
│   │   ├── types/
│   │   │   └── index.ts            # Types TypeScript partagés
│   │   ├── lib/
│   │   │   └── audioVisualizer.ts  # Analyse FFT Web Audio
│   │   ├── App.tsx
│   │   └── main.tsx
│   ├── src-tauri/
│   │   ├── src/
│   │   │   ├── main.rs             # Entry point Tauri
│   │   │   ├── lib.rs              # Setup app + handlers
│   │   │   ├── commands/
│   │   │   │   ├── mod.rs
│   │   │   │   └── sidecar.rs      # Start/stop Python sidecar
│   │   │   └── error.rs            # JarvisError type
│   │   ├── capabilities/
│   │   │   └── default.json
│   │   ├── Cargo.toml
│   │   └── tauri.conf.json
│   ├── package.json
│   ├── tsconfig.json
│   ├── tsconfig.node.json
│   ├── vite.config.ts
│   └── index.html
├── server/                          # Python FastAPI sidecar
│   ├── main.py                      # Entry point FastAPI + WS
│   ├── api/
│   │   ├── __init__.py
│   │   ├── websocket.py             # WS handler + message routing
│   │   └── routes.py                # REST routes (health, config)
│   ├── core/
│   │   ├── __init__.py
│   │   ├── llm.py                   # LLM manager (llama-cpp-python)
│   │   ├── stt.py                   # Faster-Whisper STT
│   │   ├── tts.py                   # Piper TTS
│   │   ├── wake_word.py             # openWakeWord detector
│   │   └── memory.py                # Context window manager
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── registry.py              # Tool dispatcher whitelist
│   │   ├── system_tools.py          # open_app, kill_app
│   │   ├── file_tools.py            # create/move/delete files
│   │   └── info_tools.py            # CPU/RAM/GPU psutil
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── logger.py                # Logging centralisé
│   │   └── config.py                # Settings Pydantic
│   ├── models/                      # GGUF models (gitignored)
│   └── requirements.txt
├── scripts/
│   ├── setup.ps1                    # Install deps + download modèles
│   ├── build.ps1                    # PyInstaller + Tauri build
│   └── clean.ps1                    # Nettoyage post-build
├── .logs/
├── .gitignore
└── README.md
```

---

## Phase 1 — Scaffold & Infrastructure

### Task 1: Initialisation Git + Structure

**Files:**
- Create: `.gitignore`
- Create: `README.md`
- Create: `.logs/.gitkeep`

- [ ] **Step 1: Initialiser le repo Git**

```powershell
cd "C:\Users\Momo\Documents\Jarvis"
git init
git remote add origin https://github.com/heiphaistos44-crypto/Jarvis.git
```

- [ ] **Step 2: Créer .gitignore**

```gitignore
# Python
__pycache__/
*.pyc
*.pyo
*.pyd
.venv/
venv/
*.egg-info/
dist/
build/
.eggs/

# Models (fichiers lourds)
server/models/*.gguf
server/models/*.bin
server/models/piper/

# Tauri build
client/src-tauri/target/
client/node_modules/
client/dist/

# Logs
.logs/
*.log

# Secrets
.env
.env.local

# OS
Thumbs.db
.DS_Store
desktop.ini

# PyInstaller
server/dist/
server/build/
server/*.spec
```

- [ ] **Step 3: Créer dossiers**

```powershell
New-Item -ItemType Directory -Force -Path @(
  "client", "server/api", "server/core", "server/tools", 
  "server/utils", "server/models", "scripts", ".logs"
)
New-Item -ItemType File -Path ".logs/.gitkeep" -Force
```

- [ ] **Step 4: Commit initial**

```bash
git add .gitignore README.md .logs/.gitkeep
git commit -m "chore: init project structure for JARVIS assistant"
```

---

### Task 2: Setup Python Backend (venv + deps)

**Files:**
- Create: `server/requirements.txt`
- Create: `server/utils/logger.py`
- Create: `server/utils/config.py`

- [ ] **Step 1: Créer venv Python**

```powershell
cd "C:\Users\Momo\Documents\Jarvis\server"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

- [ ] **Step 2: Créer requirements.txt**

```text
# Web framework
fastapi==0.115.12
uvicorn[standard]==0.34.3
websockets==14.2

# AI — LLM
llama-cpp-python==0.3.9

# AI — STT
faster-whisper==1.1.1

# AI — Wake Word
openwakeword==0.6.0

# System tools
psutil==6.1.1
pyautogui==0.9.54

# Data validation
pydantic==2.11.5
pydantic-settings==2.9.1

# Audio
sounddevice==0.5.1
numpy==2.2.6
scipy==1.15.3

# Utilities
python-multipart==0.0.20
aiofiles==24.1.0
```

> **Note piper-tts :** Piper n'a pas de package PyPI standard. Télécharger le binaire Windows depuis https://github.com/rhasspy/piper/releases et placer dans `server/models/piper/piper.exe`. Le module `tts.py` l'appelle via subprocess.

- [ ] **Step 3: Installer (sans llama-cpp — nécessite build CUDA séparé)**

```powershell
pip install fastapi uvicorn[standard] websockets faster-whisper openwakeword psutil pyautogui pydantic pydantic-settings sounddevice numpy scipy python-multipart aiofiles
```

- [ ] **Step 4: Créer utils/logger.py**

```python
import logging
import sys
from pathlib import Path
from datetime import datetime

LOGS_DIR = Path(__file__).parents[2] / ".logs"
LOGS_DIR.mkdir(exist_ok=True)

def _build_handler() -> logging.FileHandler:
    log_file = LOGS_DIR / f"jarvis_{datetime.now():%Y-%m-%d}.log"
    handler = logging.FileHandler(log_file, encoding="utf-8")
    handler.setFormatter(logging.Formatter(
        "[%(asctime)s] [%(levelname)s] %(name)s — %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S"
    ))
    return handler

def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(logging.DEBUG)
        logger.addHandler(_build_handler())
        stream = logging.StreamHandler(sys.stdout)
        stream.setFormatter(logging.Formatter("[%(levelname)s] %(name)s: %(message)s"))
        logger.addHandler(stream)
    return logger
```

- [ ] **Step 5: Créer utils/config.py**

```python
from pydantic_settings import BaseSettings
from pydantic import Field
from pathlib import Path

MODELS_DIR = Path(__file__).parents[1] / "models"

class Settings(BaseSettings):
    # Server
    host: str = "127.0.0.1"
    port: int = 8765
    
    # LLM
    model_path: Path = MODELS_DIR / "Meta-Llama-3-8B-Instruct.Q4_K_M.gguf"
    n_ctx: int = 4096
    n_gpu_layers: int = 35  # Charge ~6GB VRAM sur RTX 3070
    n_threads: int = 8
    
    # STT
    whisper_model: str = "small"  # "base" pour moins de VRAM
    whisper_device: str = "cuda"
    whisper_compute_type: str = "float16"
    
    # TTS
    piper_exe: Path = MODELS_DIR / "piper" / "piper.exe"
    piper_voice: Path = MODELS_DIR / "piper" / "en_US-lessac-high.onnx"
    
    # Wake Word
    wake_word_model: str = "jarvis"
    wake_word_threshold: float = 0.5
    
    # Memory
    max_context_messages: int = 20
    
    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

settings = Settings()
```

- [ ] **Step 6: Commit**

```bash
git add server/
git commit -m "feat: Python backend scaffold — logger, config, requirements"
```

---

### Task 3: Setup Tauri v2 + React

**Files:**
- Create: `client/` (via npm create tauri-app)

- [ ] **Step 1: Créer le projet Tauri**

```powershell
cd "C:\Users\Momo\Documents\Jarvis"
npm create tauri-app@latest client -- --template react-ts --manager npm
```

Répondre aux prompts :
- Identifier: `com.jarvis.assistant`
- Window title: `J.A.R.V.I.S.`

- [ ] **Step 2: Installer les dépendances frontend**

```powershell
cd client
npm install
npm install zustand framer-motion @tauri-apps/plugin-shell lucide-react
npm install -D tailwindcss @tailwindcss/vite autoprefixer
```

- [ ] **Step 3: Configurer Tailwind dans vite.config.ts**

```typescript
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig(async () => ({
  plugins: [tailwindcss(), react()],
  clearScreen: false,
  server: { port: 1420, strictPort: true, host: false },
  envPrefix: ["VITE_", "TAURI_ENV_*"],
  build: {
    target: process.env.TAURI_ENV_PLATFORM === "windows" ? "chrome105" : "safari13",
    minify: !process.env.TAURI_ENV_DEBUG ? "esbuild" : false,
    sourcemap: !!process.env.TAURI_ENV_DEBUG,
  },
}));
```

- [ ] **Step 4: Créer index.css (thème JARVIS)**

Remplacer `client/src/index.css` :

```css
@import "tailwindcss";

:root {
  --jarvis-blue: #00d4ff;
  --jarvis-glow: #0066ff;
  --jarvis-dark: #020c18;
  --jarvis-panel: rgba(0, 20, 50, 0.85);
  --jarvis-border: rgba(0, 212, 255, 0.3);
}

* { box-sizing: border-box; margin: 0; padding: 0; }

body {
  background: var(--jarvis-dark);
  color: #e0f4ff;
  font-family: 'Courier New', monospace;
  overflow: hidden;
  user-select: none;
  -webkit-user-select: none;
}

::-webkit-scrollbar { width: 4px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: var(--jarvis-border); border-radius: 2px; }
```

- [ ] **Step 5: Commit**

```bash
cd ..
git add client/
git commit -m "feat: Tauri v2 + React + Tailwind scaffold"
```

---

## Phase 2 — TypeScript Types & Zustand Store

### Task 4: Types & Store

**Files:**
- Create: `client/src/types/index.ts`
- Create: `client/src/stores/jarvisStore.ts`

- [ ] **Step 1: Créer types/index.ts**

```typescript
export type JarvisStatus = 
  | "idle" 
  | "listening" 
  | "processing" 
  | "speaking" 
  | "error";

export type MessageRole = "user" | "assistant" | "system";

export interface Message {
  id: string;
  role: MessageRole;
  content: string;
  timestamp: number;
}

export interface AudioChunk {
  data: number[];  // Float32Array sérialisée
  sampleRate: number;
}

// Messages WebSocket entrants (server → client)
export type ServerEvent =
  | { type: "status"; payload: { status: JarvisStatus } }
  | { type: "token"; payload: { token: string; messageId: string } }
  | { type: "message_done"; payload: { messageId: string } }
  | { type: "tts_audio"; payload: { audio: string } }  // base64 WAV
  | { type: "tool_result"; payload: { tool: string; result: string } }
  | { type: "error"; payload: { message: string } };

// Messages WebSocket sortants (client → server)
export type ClientEvent =
  | { type: "text_query"; payload: { text: string } }
  | { type: "audio_chunk"; payload: AudioChunk }
  | { type: "stop_speaking" };
```

- [ ] **Step 2: Créer stores/jarvisStore.ts**

```typescript
import { create } from "zustand";
import type { JarvisStatus, Message, ServerEvent } from "../types";

interface JarvisState {
  status: JarvisStatus;
  messages: Message[];
  isConnected: boolean;
  pendingMessageId: string | null;
  isMicActive: boolean;
  
  // Actions
  setStatus: (status: JarvisStatus) => void;
  setConnected: (v: boolean) => void;
  addMessage: (msg: Message) => void;
  appendToken: (messageId: string, token: string) => void;
  setMicActive: (v: boolean) => void;
  handleServerEvent: (event: ServerEvent) => void;
}

export const useJarvisStore = create<JarvisState>((set, get) => ({
  status: "idle",
  messages: [],
  isConnected: false,
  pendingMessageId: null,
  isMicActive: false,

  setStatus: (status) => set({ status }),
  setConnected: (isConnected) => set({ isConnected }),
  setMicActive: (isMicActive) => set({ isMicActive }),

  addMessage: (msg) =>
    set((s) => ({ messages: [...s.messages, msg] })),

  appendToken: (messageId, token) =>
    set((s) => ({
      messages: s.messages.map((m) =>
        m.id === messageId ? { ...m, content: m.content + token } : m
      ),
    })),

  handleServerEvent: (event) => {
    const { setStatus, addMessage, appendToken } = get();
    switch (event.type) {
      case "status":
        setStatus(event.payload.status);
        break;
      case "token": {
        const { messageId, token } = event.payload;
        const exists = get().messages.find((m) => m.id === messageId);
        if (!exists) {
          addMessage({
            id: messageId,
            role: "assistant",
            content: token,
            timestamp: Date.now(),
          });
          set({ pendingMessageId: messageId });
        } else {
          appendToken(messageId, token);
        }
        break;
      }
      case "message_done":
        set({ pendingMessageId: null });
        break;
      case "error":
        setStatus("error");
        addMessage({
          id: crypto.randomUUID(),
          role: "system",
          content: `⚠ ${event.payload.message}`,
          timestamp: Date.now(),
        });
        break;
    }
  },
}));
```

- [ ] **Step 3: Commit**

```bash
git add client/src/types/ client/src/stores/
git commit -m "feat: TypeScript types + Zustand store JARVIS"
```

---

## Phase 3 — Frontend Hooks

### Task 5: Hook WebSocket

**Files:**
- Create: `client/src/hooks/useWebSocket.ts`
- Create: `client/src/hooks/useAudioCapture.ts`
- Create: `client/src/hooks/useJarvis.ts`

- [ ] **Step 1: Créer hooks/useWebSocket.ts**

```typescript
import { useEffect, useRef, useCallback } from "react";
import { useJarvisStore } from "../stores/jarvisStore";
import type { ClientEvent, ServerEvent } from "../types";

const WS_URL = "ws://127.0.0.1:8765/ws";
const RECONNECT_DELAY = 2000;

export function useWebSocket() {
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout>>();
  const { setConnected, handleServerEvent } = useJarvisStore();

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    const ws = new WebSocket(WS_URL);
    wsRef.current = ws;

    ws.onopen = () => setConnected(true);

    ws.onmessage = (evt) => {
      try {
        const event = JSON.parse(evt.data) as ServerEvent;
        handleServerEvent(event);
      } catch (e) {
        console.error("WS parse error", e);
      }
    };

    ws.onclose = () => {
      setConnected(false);
      reconnectTimer.current = setTimeout(connect, RECONNECT_DELAY);
    };

    ws.onerror = () => ws.close();
  }, [setConnected, handleServerEvent]);

  useEffect(() => {
    connect();
    return () => {
      clearTimeout(reconnectTimer.current);
      wsRef.current?.close();
    };
  }, [connect]);

  const send = useCallback((event: ClientEvent) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(event));
    }
  }, []);

  return { send };
}
```

- [ ] **Step 2: Créer hooks/useAudioCapture.ts**

```typescript
import { useRef, useCallback } from "react";
import type { ClientEvent } from "../types";

const SAMPLE_RATE = 16000;
const CHUNK_SIZE = 4096;

export function useAudioCapture(send: (e: ClientEvent) => void) {
  const streamRef = useRef<MediaStream | null>(null);
  const contextRef = useRef<AudioContext | null>(null);
  const processorRef = useRef<ScriptProcessorNode | null>(null);

  const startCapture = useCallback(async () => {
    if (streamRef.current) return;
    streamRef.current = await navigator.mediaDevices.getUserMedia({
      audio: { sampleRate: SAMPLE_RATE, channelCount: 1, echoCancellation: true },
    });
    const ctx = new AudioContext({ sampleRate: SAMPLE_RATE });
    contextRef.current = ctx;
    const source = ctx.createMediaStreamSource(streamRef.current);
    const processor = ctx.createScriptProcessor(CHUNK_SIZE, 1, 1);
    processor.onaudioprocess = (e) => {
      const data = Array.from(e.inputBuffer.getChannelData(0));
      send({ type: "audio_chunk", payload: { data, sampleRate: SAMPLE_RATE } });
    };
    source.connect(processor);
    processor.connect(ctx.destination);
    processorRef.current = processor;
  }, [send]);

  const stopCapture = useCallback(() => {
    processorRef.current?.disconnect();
    contextRef.current?.close();
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    contextRef.current = null;
    processorRef.current = null;
  }, []);

  return { startCapture, stopCapture };
}
```

- [ ] **Step 3: Créer hooks/useJarvis.ts**

```typescript
import { useCallback } from "react";
import { useWebSocket } from "./useWebSocket";
import { useAudioCapture } from "./useAudioCapture";
import { useJarvisStore } from "../stores/jarvisStore";

export function useJarvis() {
  const { send } = useWebSocket();
  const { isMicActive, setMicActive, status } = useJarvisStore();
  const { startCapture, stopCapture } = useAudioCapture(send);

  const sendText = useCallback(
    (text: string) => {
      if (!text.trim()) return;
      send({ type: "text_query", payload: { text } });
    },
    [send]
  );

  const toggleMic = useCallback(async () => {
    if (isMicActive) {
      stopCapture();
      setMicActive(false);
    } else {
      await startCapture();
      setMicActive(true);
    }
  }, [isMicActive, startCapture, stopCapture, setMicActive]);

  return { sendText, toggleMic, isMicActive, status };
}
```

- [ ] **Step 4: Commit**

```bash
git add client/src/hooks/
git commit -m "feat: WebSocket + audio capture + orchestrator hooks"
```

---

## Phase 4 — Composants UI (Design JARVIS Iron Man)

### Task 6: AudioCanvas + VoiceVisualizer

**Files:**
- Create: `client/src/lib/audioVisualizer.ts`
- Create: `client/src/components/VoiceVisualizer/VoiceVisualizer.tsx`

- [ ] **Step 1: Créer lib/audioVisualizer.ts**

```typescript
export interface VisualizerOptions {
  canvas: HTMLCanvasElement;
  analyser: AnalyserNode;
  status: "idle" | "listening" | "processing" | "speaking" | "error";
}

const STATUS_COLORS: Record<string, string> = {
  idle: "#00d4ff",
  listening: "#00ff88",
  processing: "#ffaa00",
  speaking: "#00d4ff",
  error: "#ff4444",
};

export function drawFrame({ canvas, analyser, status }: VisualizerOptions) {
  const ctx = canvas.getContext("2d")!;
  const { width: W, height: H } = canvas;
  const cx = W / 2, cy = H / 2;
  const color = STATUS_COLORS[status] ?? "#00d4ff";
  const bufLen = analyser.frequencyBinCount;
  const data = new Uint8Array(bufLen);
  analyser.getByteFrequencyData(data);

  ctx.clearRect(0, 0, W, H);

  // Fond radial
  const bg = ctx.createRadialGradient(cx, cy, 0, cx, cy, cy);
  bg.addColorStop(0, "rgba(0,40,80,0.3)");
  bg.addColorStop(1, "transparent");
  ctx.fillStyle = bg;
  ctx.fillRect(0, 0, W, H);

  // Sphère pulsante
  const avgAmp = data.slice(0, 64).reduce((s, v) => s + v, 0) / 64 / 255;
  const baseR = 60;
  const pulseR = baseR + avgAmp * 30;

  const grd = ctx.createRadialGradient(cx, cy, 0, cx, cy, pulseR);
  grd.addColorStop(0, `${color}33`);
  grd.addColorStop(1, "transparent");
  ctx.beginPath();
  ctx.arc(cx, cy, pulseR, 0, Math.PI * 2);
  ctx.fillStyle = grd;
  ctx.fill();

  ctx.beginPath();
  ctx.arc(cx, cy, baseR, 0, Math.PI * 2);
  ctx.strokeStyle = `${color}88`;
  ctx.lineWidth = 2;
  ctx.stroke();

  // Barres fréquence en cercle
  const bars = 64;
  for (let i = 0; i < bars; i++) {
    const angle = (i / bars) * Math.PI * 2 - Math.PI / 2;
    const amp = data[Math.floor((i / bars) * bufLen)] / 255;
    const barLen = baseR * 0.6 * amp;
    const x1 = cx + Math.cos(angle) * (baseR + 4);
    const y1 = cy + Math.sin(angle) * (baseR + 4);
    const x2 = cx + Math.cos(angle) * (baseR + 4 + barLen);
    const y2 = cy + Math.sin(angle) * (baseR + 4 + barLen);
    ctx.beginPath();
    ctx.moveTo(x1, y1);
    ctx.lineTo(x2, y2);
    ctx.strokeStyle = color;
    ctx.lineWidth = 2;
    ctx.globalAlpha = 0.7 + amp * 0.3;
    ctx.stroke();
  }
  ctx.globalAlpha = 1;
}
```

- [ ] **Step 2: Créer VoiceVisualizer.tsx**

```tsx
import { useEffect, useRef } from "react";
import { useJarvisStore } from "../../stores/jarvisStore";
import { drawFrame } from "../../lib/audioVisualizer";

export function VoiceVisualizer() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const animRef = useRef<number>();
  const analyserRef = useRef<AnalyserNode | null>(null);
  const status = useJarvisStore((s) => s.status);

  useEffect(() => {
    const canvas = canvasRef.current!;
    const audioCtx = new AudioContext();
    const analyser = audioCtx.createAnalyser();
    analyser.fftSize = 256;
    analyserRef.current = analyser;

    const loop = () => {
      drawFrame({ canvas, analyser, status });
      animRef.current = requestAnimationFrame(loop);
    };
    loop();

    return () => {
      cancelAnimationFrame(animRef.current!);
      audioCtx.close();
    };
  }, [status]);

  return (
    <canvas
      ref={canvasRef}
      width={260}
      height={260}
      className="rounded-full"
      style={{ filter: "drop-shadow(0 0 20px #00d4ff66)" }}
    />
  );
}
```

- [ ] **Step 3: Commit**

```bash
git add client/src/lib/ client/src/components/VoiceVisualizer/
git commit -m "feat: voice visualizer — sphère FFT animée"
```

---

### Task 7: ChatPanel + Message

**Files:**
- Create: `client/src/components/ChatPanel/Message.tsx`
- Create: `client/src/components/ChatPanel/TypingIndicator.tsx`
- Create: `client/src/components/ChatPanel/ChatPanel.tsx`

- [ ] **Step 1: Créer Message.tsx**

```tsx
import { motion } from "framer-motion";
import type { Message as MsgType } from "../../types";

interface Props { message: MsgType }

export function Message({ message }: Props) {
  const isUser = message.role === "user";
  const isSystem = message.role === "system";

  return (
    <motion.div
      initial={{ opacity: 0, x: isUser ? 20 : -20 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.2 }}
      className={`flex ${isUser ? "justify-end" : "justify-start"} mb-3`}
    >
      <div
        className={`max-w-[75%] px-4 py-2 rounded-lg text-sm leading-relaxed border ${
          isSystem
            ? "bg-yellow-900/20 border-yellow-500/30 text-yellow-300"
            : isUser
            ? "bg-cyan-900/30 border-cyan-500/40 text-cyan-100"
            : "bg-blue-950/40 border-blue-500/20 text-blue-100"
        }`}
        style={{ backdropFilter: "blur(8px)" }}
      >
        {!isUser && !isSystem && (
          <div className="text-xs text-cyan-400 mb-1 font-bold tracking-widest">JARVIS</div>
        )}
        <pre className="whitespace-pre-wrap font-mono text-xs">{message.content}</pre>
        <div className="text-right text-[10px] text-blue-400/50 mt-1">
          {new Date(message.timestamp).toLocaleTimeString()}
        </div>
      </div>
    </motion.div>
  );
}
```

- [ ] **Step 2: Créer TypingIndicator.tsx**

```tsx
import { motion } from "framer-motion";

export function TypingIndicator() {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="flex justify-start mb-3"
    >
      <div className="bg-blue-950/40 border border-blue-500/20 px-4 py-3 rounded-lg flex gap-1 items-center">
        {[0, 1, 2].map((i) => (
          <motion.div
            key={i}
            className="w-2 h-2 rounded-full bg-cyan-400"
            animate={{ scale: [1, 1.5, 1] }}
            transition={{ duration: 0.8, repeat: Infinity, delay: i * 0.2 }}
          />
        ))}
      </div>
    </motion.div>
  );
}
```

- [ ] **Step 3: Créer ChatPanel.tsx**

```tsx
import { useEffect, useRef } from "react";
import { useJarvisStore } from "../../stores/jarvisStore";
import { Message } from "./Message";
import { TypingIndicator } from "./TypingIndicator";

export function ChatPanel() {
  const messages = useJarvisStore((s) => s.messages);
  const pendingMessageId = useJarvisStore((s) => s.pendingMessageId);
  const status = useJarvisStore((s) => s.status);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages.length, pendingMessageId]);

  return (
    <div
      className="flex-1 overflow-y-auto px-4 py-2"
      style={{ scrollbarWidth: "thin" }}
    >
      {messages.length === 0 && (
        <div className="flex items-center justify-center h-full text-blue-400/40 text-sm tracking-widest">
          SYSTÈME EN ATTENTE DE COMMANDE...
        </div>
      )}
      {messages.map((msg) => (
        <Message key={msg.id} message={msg} />
      ))}
      {status === "processing" && !pendingMessageId && <TypingIndicator />}
      <div ref={bottomRef} />
    </div>
  );
}
```

- [ ] **Step 4: Commit**

```bash
git add client/src/components/ChatPanel/
git commit -m "feat: ChatPanel avec animations Framer Motion"
```

---

### Task 8: StatusBar + CommandInput + App Layout

**Files:**
- Create: `client/src/components/StatusBar/StatusBar.tsx`
- Create: `client/src/components/CommandInput/CommandInput.tsx`
- Modify: `client/src/App.tsx`

- [ ] **Step 1: Créer StatusBar.tsx**

```tsx
import { motion, AnimatePresence } from "framer-motion";
import { useJarvisStore } from "../../stores/jarvisStore";
import type { JarvisStatus } from "../../types";

const STATUS_CONFIG: Record<JarvisStatus, { label: string; color: string; pulse: boolean }> = {
  idle:       { label: "STANDBY",       color: "text-blue-400",  pulse: false },
  listening:  { label: "LISTENING",     color: "text-green-400", pulse: true  },
  processing: { label: "PROCESSING...", color: "text-amber-400", pulse: true  },
  speaking:   { label: "SPEAKING",      color: "text-cyan-400",  pulse: true  },
  error:      { label: "ERROR",         color: "text-red-400",   pulse: false },
};

export function StatusBar() {
  const { status, isConnected } = useJarvisStore((s) => ({
    status: s.status,
    isConnected: s.isConnected,
  }));
  const cfg = STATUS_CONFIG[status];

  return (
    <div className="flex items-center justify-between px-4 py-2 border-b border-cyan-900/40">
      <div className="flex items-center gap-2">
        <motion.div
          className={`w-2 h-2 rounded-full ${isConnected ? "bg-green-400" : "bg-red-400"}`}
          animate={isConnected ? { opacity: [1, 0.4, 1] } : {}}
          transition={{ duration: 2, repeat: Infinity }}
        />
        <span className="text-xs text-blue-400/60 tracking-widest">
          {isConnected ? "CORE ONLINE" : "CORE OFFLINE"}
        </span>
      </div>

      <AnimatePresence mode="wait">
        <motion.div
          key={status}
          initial={{ opacity: 0, y: -4 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: 4 }}
          className={`text-xs font-bold tracking-widest ${cfg.color}`}
        >
          {cfg.pulse && (
            <motion.span
              animate={{ opacity: [1, 0, 1] }}
              transition={{ duration: 1, repeat: Infinity }}
              className="mr-1"
            >
              ◉
            </motion.span>
          )}
          {cfg.label}
        </motion.div>
      </AnimatePresence>

      <span className="text-xs text-blue-400/40 tracking-widest">J.A.R.V.I.S. v1.0</span>
    </div>
  );
}
```

- [ ] **Step 2: Créer CommandInput.tsx**

```tsx
import { useState, useRef, useCallback } from "react";
import { Mic, MicOff, Send } from "lucide-react";
import { motion } from "framer-motion";
import { useJarvis } from "../../hooks/useJarvis";
import { useJarvisStore } from "../../stores/jarvisStore";

export function CommandInput() {
  const [text, setText] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);
  const { sendText, toggleMic, isMicActive } = useJarvis();
  const status = useJarvisStore((s) => s.status);
  const addMessage = useJarvisStore((s) => s.addMessage);
  const isDisabled = status === "processing" || status === "speaking";

  const handleSubmit = useCallback(() => {
    if (!text.trim() || isDisabled) return;
    addMessage({ id: crypto.randomUUID(), role: "user", content: text, timestamp: Date.now() });
    sendText(text);
    setText("");
    inputRef.current?.focus();
  }, [text, isDisabled, addMessage, sendText]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  return (
    <div className="p-4 border-t border-cyan-900/40">
      <div
        className="flex items-center gap-2 rounded-lg border px-3 py-2"
        style={{
          background: "rgba(0, 20, 50, 0.7)",
          borderColor: isMicActive ? "rgba(0, 255, 136, 0.5)" : "rgba(0, 212, 255, 0.2)",
          backdropFilter: "blur(8px)",
        }}
      >
        <input
          ref={inputRef}
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={isDisabled}
          placeholder="Entrez une commande..."
          className="flex-1 bg-transparent text-cyan-100 text-sm placeholder-blue-400/40 outline-none font-mono"
        />

        <motion.button
          whileHover={{ scale: 1.1 }}
          whileTap={{ scale: 0.9 }}
          onClick={() => void toggleMic()}
          className={`p-1.5 rounded transition-colors ${
            isMicActive ? "text-green-400" : "text-blue-400/60 hover:text-cyan-400"
          }`}
          title={isMicActive ? "Arrêter le micro" : "Activer le micro"}
        >
          {isMicActive ? <Mic size={18} /> : <MicOff size={18} />}
        </motion.button>

        <motion.button
          whileHover={{ scale: 1.1 }}
          whileTap={{ scale: 0.9 }}
          onClick={handleSubmit}
          disabled={!text.trim() || isDisabled}
          className="p-1.5 text-cyan-400 hover:text-cyan-300 disabled:opacity-30 transition-colors"
        >
          <Send size={18} />
        </motion.button>
      </div>

      <div className="text-center text-[10px] text-blue-400/30 mt-1 tracking-widest">
        ENTRÉE pour envoyer · Maintenir MIC pour parler
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Réécrire App.tsx**

```tsx
import { VoiceVisualizer } from "./components/VoiceVisualizer/VoiceVisualizer";
import { ChatPanel } from "./components/ChatPanel/ChatPanel";
import { StatusBar } from "./components/StatusBar/StatusBar";
import { CommandInput } from "./components/CommandInput/CommandInput";

// Grille hexagonale en arrière-plan
function HexGrid() {
  return (
    <svg
      className="absolute inset-0 w-full h-full opacity-5 pointer-events-none"
      xmlns="http://www.w3.org/2000/svg"
    >
      <defs>
        <pattern id="hex" x="0" y="0" width="60" height="52" patternUnits="userSpaceOnUse">
          <polygon
            points="30,2 58,17 58,46 30,61 2,46 2,17"
            fill="none"
            stroke="#00d4ff"
            strokeWidth="0.5"
          />
        </pattern>
      </defs>
      <rect width="100%" height="100%" fill="url(#hex)" />
    </svg>
  );
}

export default function App() {
  return (
    <div className="h-screen flex flex-col relative overflow-hidden bg-[#020c18]">
      <HexGrid />

      {/* Header */}
      <div className="relative z-10 text-center py-3 border-b border-cyan-900/30">
        <h1
          className="text-2xl font-bold tracking-[0.5em] text-cyan-400"
          style={{ textShadow: "0 0 20px #00d4ff, 0 0 40px #00d4ff66" }}
        >
          J.A.R.V.I.S.
        </h1>
        <p className="text-[10px] text-blue-400/40 tracking-widest mt-0.5">
          JUST A RATHER VERY INTELLIGENT SYSTEM
        </p>
      </div>

      <StatusBar />

      {/* Body */}
      <div className="flex-1 flex overflow-hidden relative z-10">
        {/* Panneau gauche — Visualiseur */}
        <div className="w-72 flex flex-col items-center justify-center border-r border-cyan-900/30 p-4 gap-4">
          <VoiceVisualizer />
          <div className="text-center">
            <div className="text-xs text-blue-400/50 tracking-widest">SYSTÈME ACTIF</div>
            <div className="text-xs text-cyan-400/70 mt-1">RTX 3070 · CUDA 13</div>
          </div>
        </div>

        {/* Panneau droit — Chat */}
        <div className="flex-1 flex flex-col">
          <ChatPanel />
          <CommandInput />
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Tester le frontend seul**

```powershell
cd "C:\Users\Momo\Documents\Jarvis\client"
npm run dev
# Ouvrir http://localhost:1420 — UI doit s'afficher sans backend
```

- [ ] **Step 5: Commit**

```bash
git add client/src/
git commit -m "feat: UI JARVIS complète — layout Iron Man, status bar, voice viz"
```

---

## Phase 5 — Backend Python (LLM + WS)

### Task 9: FastAPI + WebSocket Manager

**Files:**
- Create: `server/api/__init__.py`
- Create: `server/api/websocket.py`
- Create: `server/api/routes.py`
- Create: `server/main.py`

- [ ] **Step 1: Créer api/websocket.py**

```python
from __future__ import annotations
import json
import uuid
from fastapi import WebSocket, WebSocketDisconnect
from utils.logger import get_logger
from core.llm import LLMManager
from core.memory import ContextMemory
from tools.registry import ToolRegistry

logger = get_logger("websocket")

class ConnectionManager:
    def __init__(self) -> None:
        self.active: list[WebSocket] = []

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self.active.append(ws)
        logger.info("Client connecté")

    def disconnect(self, ws: WebSocket) -> None:
        self.active.remove(ws)
        logger.info("Client déconnecté")

    async def send(self, ws: WebSocket, event_type: str, payload: dict) -> None:
        await ws.send_text(json.dumps({"type": event_type, "payload": payload}))

manager = ConnectionManager()

async def websocket_handler(
    ws: WebSocket,
    llm: LLMManager,
    memory: ContextMemory,
    tools: ToolRegistry,
) -> None:
    await manager.connect(ws)
    try:
        while True:
            raw = await ws.receive_text()
            event = json.loads(raw)
            event_type: str = event.get("type", "")
            payload: dict = event.get("payload", {})

            if event_type == "text_query":
                await handle_text_query(ws, payload["text"], llm, memory, tools)
            elif event_type == "audio_chunk":
                pass  # géré par STT en Task 11
            else:
                logger.warning(f"Type d'événement inconnu: {event_type}")

    except WebSocketDisconnect:
        manager.disconnect(ws)
    except Exception as e:
        logger.error(f"Erreur WebSocket: {e}", exc_info=True)
        await manager.send(ws, "error", {"message": str(e)})
        manager.disconnect(ws)

async def handle_text_query(
    ws: WebSocket,
    text: str,
    llm: LLMManager,
    memory: ContextMemory,
    tools: ToolRegistry,
) -> None:
    await manager.send(ws, "status", {"status": "processing"})
    memory.add_user(text)
    message_id = str(uuid.uuid4())

    # Streaming tokens
    full_response = ""
    async for token in llm.stream(memory.get_messages()):
        full_response += token
        await manager.send(ws, "token", {"token": token, "messageId": message_id})

    memory.add_assistant(full_response)
    await manager.send(ws, "message_done", {"messageId": message_id})
    await manager.send(ws, "status", {"status": "idle"})
```

- [ ] **Step 2: Créer api/routes.py**

```python
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()

class HealthResponse(BaseModel):
    status: str
    version: str

@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(status="ok", version="1.0.0")
```

- [ ] **Step 3: Créer main.py**

```python
from __future__ import annotations
import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, WebSocket
from utils.logger import get_logger
from utils.config import settings
from core.llm import LLMManager
from core.memory import ContextMemory
from tools.registry import ToolRegistry
from api.routes import router
from api.websocket import websocket_handler

logger = get_logger("main")

llm = LLMManager(settings)
memory = ContextMemory(settings.max_context_messages)
tools = ToolRegistry()

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info("Chargement du modèle LLM...")
    await asyncio.to_thread(llm.load)
    logger.info("Modèle chargé ✓")
    yield
    llm.unload()
    logger.info("Serveur arrêté.")

app = FastAPI(title="JARVIS Core", lifespan=lifespan)
app.include_router(router, prefix="/api")

@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket) -> None:
    await websocket_handler(ws, llm, memory, tools)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        log_level="info",
        ws_ping_interval=20,
        ws_ping_timeout=30,
    )
```

- [ ] **Step 4: Commit**

```bash
git add server/
git commit -m "feat: FastAPI + WebSocket handler avec streaming tokens"
```

---

### Task 10: LLM Manager + Memory

**Files:**
- Create: `server/core/llm.py`
- Create: `server/core/memory.py`

- [ ] **Step 1: Installer llama-cpp-python avec CUDA**

```powershell
# Dans le venv Python server
$env:CMAKE_ARGS="-DLLAMA_CUDA=on -DCUDA_TOOLKIT_ROOT_DIR=C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.x"
pip install llama-cpp-python==0.3.9 --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cu121
```

> **Alternative simplifiée (wheel pré-compilé CUDA 12.1) :**
> ```powershell
> pip install llama-cpp-python --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cu121
> ```

- [ ] **Step 2: Créer core/llm.py**

```python
from __future__ import annotations
import asyncio
from typing import AsyncGenerator, TYPE_CHECKING
from utils.logger import get_logger

if TYPE_CHECKING:
    from utils.config import Settings

logger = get_logger("llm")

SYSTEM_PROMPT = """Tu es J.A.R.V.I.S., un assistant IA ultra-intelligent et légèrement sarcastique, similaire à celui d'Iron Man. 
Tu réponds en français avec précision et concision. Tu peux exécuter des commandes système si demandé.
Tu t'adresses à l'utilisateur comme "Monsieur" par défaut."""

class LLMManager:
    def __init__(self, settings: "Settings") -> None:
        self._settings = settings
        self._llm: object | None = None  # llama_cpp.Llama

    def load(self) -> None:
        from llama_cpp import Llama  # type: ignore[import]
        self._llm = Llama(
            model_path=str(self._settings.model_path),
            n_ctx=self._settings.n_ctx,
            n_gpu_layers=self._settings.n_gpu_layers,
            n_threads=self._settings.n_threads,
            verbose=False,
        )
        logger.info(f"LLM chargé: {self._settings.model_path.name}")

    def unload(self) -> None:
        self._llm = None
        logger.info("LLM déchargé")

    async def stream(self, messages: list[dict]) -> AsyncGenerator[str, None]:
        if self._llm is None:
            raise RuntimeError("LLM non chargé")

        full_messages = [{"role": "system", "content": SYSTEM_PROMPT}] + messages

        def _generate():
            return self._llm.create_chat_completion(  # type: ignore[union-attr]
                messages=full_messages,
                max_tokens=1024,
                temperature=0.7,
                stream=True,
            )

        gen = await asyncio.to_thread(_generate)
        for chunk in gen:
            delta = chunk["choices"][0]["delta"]
            if content := delta.get("content"):
                yield content
```

- [ ] **Step 3: Créer core/memory.py**

```python
from __future__ import annotations
from collections import deque

class ContextMemory:
    def __init__(self, max_messages: int) -> None:
        self._messages: deque[dict[str, str]] = deque(maxlen=max_messages)

    def add_user(self, content: str) -> None:
        self._messages.append({"role": "user", "content": content})

    def add_assistant(self, content: str) -> None:
        self._messages.append({"role": "assistant", "content": content})

    def get_messages(self) -> list[dict[str, str]]:
        return list(self._messages)

    def clear(self) -> None:
        self._messages.clear()
```

- [ ] **Step 4: Commit**

```bash
git add server/core/llm.py server/core/memory.py
git commit -m "feat: LLM manager llama-cpp CUDA + context memory"
```

---

## Phase 6 — STT / TTS / Wake Word

### Task 11: Speech-to-Text (Faster-Whisper)

**Files:**
- Create: `server/core/stt.py`
- Modify: `server/api/websocket.py` (handler audio_chunk)

- [ ] **Step 1: Créer core/stt.py**

```python
from __future__ import annotations
import io
import numpy as np
import asyncio
from typing import TYPE_CHECKING
from utils.logger import get_logger

if TYPE_CHECKING:
    from utils.config import Settings

logger = get_logger("stt")

class STTManager:
    def __init__(self, settings: "Settings") -> None:
        self._settings = settings
        self._model = None

    def load(self) -> None:
        from faster_whisper import WhisperModel  # type: ignore[import]
        self._model = WhisperModel(
            self._settings.whisper_model,
            device=self._settings.whisper_device,
            compute_type=self._settings.whisper_compute_type,
        )
        logger.info(f"Whisper chargé: {self._settings.whisper_model}")

    async def transcribe_chunks(self, chunks: list[list[float]], sample_rate: int) -> str:
        if self._model is None:
            raise RuntimeError("STT non chargé")
        
        def _run():
            audio = np.concatenate([np.array(c, dtype=np.float32) for c in chunks])
            segments, _ = self._model.transcribe(audio, language="fr", beam_size=5)
            return " ".join(s.text.strip() for s in segments)

        return await asyncio.to_thread(_run)
```

- [ ] **Step 2: Mettre à jour websocket.py pour l'audio**

Ajouter dans `websocket_handler` après l'import STT (adapter le handler) :

```python
# Dans ConnectionManager, ajouter un buffer par connexion
# La gestion audio complète nécessite un buffer par client WS.
# Patron recommandé: stocker le buffer dans une dict ws→buffer
```

Ajouter dans `websocket_handler` :

```python
from core.stt import STTManager
audio_buffer: list[list[float]] = []
current_sample_rate: int = 16000

# Dans la boucle, cas audio_chunk:
elif event_type == "audio_chunk":
    audio_buffer.append(payload["data"])
    current_sample_rate = payload["sampleRate"]
    # Traitement par lot toutes les 2 secondes (~32 chunks de 4096 à 16kHz)
    if len(audio_buffer) >= 32:
        text = await stt.transcribe_chunks(audio_buffer, current_sample_rate)
        audio_buffer.clear()
        if text.strip():
            await handle_text_query(ws, text, llm, memory, tools)
```

- [ ] **Step 3: Commit**

```bash
git add server/core/stt.py server/api/websocket.py
git commit -m "feat: STT Faster-Whisper — transcription audio en temps réel"
```

---

### Task 12: Text-to-Speech (Piper)

**Files:**
- Create: `server/core/tts.py`

- [ ] **Step 1: Télécharger Piper**

```powershell
# Télécharger depuis https://github.com/rhasspy/piper/releases
# Extraire piper.exe dans server/models/piper/
# Télécharger la voix: en_US-lessac-high.onnx + en_US-lessac-high.onnx.json
# Les placer dans server/models/piper/
New-Item -ItemType Directory -Force "server\models\piper"
# Manuellement: déposer piper.exe + voix .onnx dans ce dossier
```

- [ ] **Step 2: Créer core/tts.py**

```python
from __future__ import annotations
import asyncio
import subprocess
import base64
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING
from utils.logger import get_logger

if TYPE_CHECKING:
    from utils.config import Settings

logger = get_logger("tts")

class TTSManager:
    def __init__(self, settings: "Settings") -> None:
        self._piper_exe = settings.piper_exe
        self._voice = settings.piper_voice
        self._available = self._piper_exe.exists() and self._voice.exists()
        if not self._available:
            logger.warning("Piper TTS non disponible — téléchargez le binaire")

    async def synthesize(self, text: str) -> str | None:
        """Retourne le WAV en base64, ou None si TTS indisponible."""
        if not self._available:
            return None

        def _run() -> bytes:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                tmp_path = Path(tmp.name)

            proc = subprocess.run(
                [str(self._piper_exe), "--model", str(self._voice), "--output_file", str(tmp_path)],
                input=text.encode("utf-8"),
                capture_output=True,
                timeout=30,
            )
            if proc.returncode != 0:
                raise RuntimeError(f"Piper error: {proc.stderr.decode()}")
            data = tmp_path.read_bytes()
            tmp_path.unlink(missing_ok=True)
            return data

        try:
            wav_bytes = await asyncio.to_thread(_run)
            return base64.b64encode(wav_bytes).decode()
        except Exception as e:
            logger.error(f"TTS failed: {e}")
            return None
```

- [ ] **Step 3: Intégrer TTS dans handle_text_query (websocket.py)**

Après `await manager.send(ws, "message_done", ...)` :

```python
if full_response.strip():
    audio_b64 = await tts.synthesize(full_response)
    if audio_b64:
        await manager.send(ws, "tts_audio", {"audio": audio_b64})
        await manager.send(ws, "status", {"status": "speaking"})
```

- [ ] **Step 4: Commit**

```bash
git add server/core/tts.py
git commit -m "feat: Piper TTS — synthèse vocale locale haute qualité"
```

---

## Phase 7 — Tool Calling Système

### Task 13: Tool Registry + System Tools

**Files:**
- Create: `server/tools/__init__.py`
- Create: `server/tools/registry.py`
- Create: `server/tools/system_tools.py`
- Create: `server/tools/file_tools.py`
- Create: `server/tools/info_tools.py`

- [ ] **Step 1: Créer tools/registry.py**

```python
from __future__ import annotations
import inspect
from typing import Callable, Any
from utils.logger import get_logger

logger = get_logger("tools")

class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Callable[..., Any]] = {}
        self._register_defaults()

    def _register_defaults(self) -> None:
        from tools.system_tools import open_application, kill_application
        from tools.file_tools import delete_temp_files, create_file, move_file
        from tools.info_tools import get_system_info

        for fn in [open_application, kill_application,
                   delete_temp_files, create_file, move_file,
                   get_system_info]:
            self._tools[fn.__name__] = fn

    def execute(self, name: str, **kwargs: Any) -> str:
        if name not in self._tools:
            logger.warning(f"Outil non autorisé: {name}")
            return f"Erreur: outil '{name}' non disponible."
        try:
            result = self._tools[name](**kwargs)
            logger.info(f"Outil '{name}' exécuté: {result}")
            return str(result)
        except Exception as e:
            logger.error(f"Erreur outil '{name}': {e}")
            return f"Erreur lors de l'exécution de '{name}': {e}"

    def list_tools(self) -> list[str]:
        return list(self._tools.keys())
```

- [ ] **Step 2: Créer tools/system_tools.py**

```python
from __future__ import annotations
import subprocess
import psutil
import shutil
from utils.logger import get_logger

logger = get_logger("system_tools")

ALLOWED_APPS: dict[str, str] = {
    "chrome":     "chrome.exe",
    "firefox":    "firefox.exe",
    "notepad":    "notepad.exe",
    "explorer":   "explorer.exe",
    "calculator": "calc.exe",
    "vscode":     "code.exe",
    "terminal":   "wt.exe",
}

def open_application(name: str) -> str:
    key = name.lower().strip()
    if key not in ALLOWED_APPS:
        return f"Application '{name}' non autorisée. Disponibles: {', '.join(ALLOWED_APPS)}"
    exe = ALLOWED_APPS[key]
    subprocess.Popen([exe], shell=True, creationflags=0x08000000)
    return f"Application '{name}' lancée."

def kill_application(name: str) -> str:
    killed = 0
    for proc in psutil.process_iter(["name"]):
        if proc.info["name"] and name.lower() in proc.info["name"].lower():
            proc.terminate()
            killed += 1
    return f"{killed} processus '{name}' terminés." if killed else f"Aucun processus '{name}' trouvé."
```

- [ ] **Step 3: Créer tools/file_tools.py**

```python
from __future__ import annotations
import os
import shutil
import tempfile
from pathlib import Path
from utils.logger import get_logger

logger = get_logger("file_tools")

SAFE_TEMP_DIRS = [tempfile.gettempdir(), str(Path.home() / "AppData" / "Local" / "Temp")]

def delete_temp_files() -> str:
    count = 0
    errors = 0
    for dir_path in SAFE_TEMP_DIRS:
        for item in Path(dir_path).iterdir():
            try:
                if item.is_file():
                    item.unlink()
                    count += 1
                elif item.is_dir():
                    shutil.rmtree(item, ignore_errors=True)
                    count += 1
            except PermissionError:
                errors += 1
    return f"{count} éléments supprimés ({errors} erreurs de permission)."

def create_file(path: str, content: str = "") -> str:
    safe_path = Path(path).expanduser()
    if safe_path.is_absolute() and not str(safe_path).startswith(str(Path.home())):
        return "Erreur: création de fichier limitée au répertoire home."
    safe_path.parent.mkdir(parents=True, exist_ok=True)
    safe_path.write_text(content, encoding="utf-8")
    return f"Fichier créé: {safe_path}"

def move_file(src: str, dst: str) -> str:
    src_path, dst_path = Path(src).expanduser(), Path(dst).expanduser()
    if not src_path.exists():
        return f"Fichier source introuvable: {src}"
    shutil.move(str(src_path), str(dst_path))
    return f"Fichier déplacé: {src} → {dst}"
```

- [ ] **Step 4: Créer tools/info_tools.py**

```python
from __future__ import annotations
import psutil
from utils.logger import get_logger

logger = get_logger("info_tools")

def get_system_info() -> str:
    cpu = psutil.cpu_percent(interval=0.5)
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage("/")

    gpu_info = "N/A"
    try:
        import subprocess
        r = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.used,memory.total,utilization.gpu",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5
        )
        if r.returncode == 0:
            parts = r.stdout.strip().split(", ")
            gpu_info = f"{parts[0]} | VRAM: {parts[1]}/{parts[2]} MB | Load: {parts[3]}%"
    except Exception:
        pass

    return (
        f"CPU: {cpu}% | "
        f"RAM: {mem.used // 1024**2}/{mem.total // 1024**2} MB ({mem.percent}%) | "
        f"Disque C: {disk.used // 1024**3}/{disk.total // 1024**3} GB | "
        f"GPU: {gpu_info}"
    )
```

- [ ] **Step 5: Commit**

```bash
git add server/tools/
git commit -m "feat: tool registry sécurisé — system, file, info tools"
```

---

## Phase 8 — Tauri Sidecar + Configuration

### Task 14: Configuration Tauri v2

**Files:**
- Modify: `client/src-tauri/tauri.conf.json`
- Modify: `client/src-tauri/capabilities/default.json`
- Create: `client/src-tauri/src/commands/sidecar.rs`

- [ ] **Step 1: Mettre à jour tauri.conf.json**

```json
{
  "$schema": "https://schema.tauri.app/config/2",
  "productName": "JARVIS",
  "version": "1.0.0",
  "identifier": "com.jarvis.assistant",
  "build": {
    "beforeDevCommand": "npm run dev",
    "beforeBuildCommand": "npm run build",
    "devUrl": "http://localhost:1420",
    "frontendDist": "../dist"
  },
  "app": {
    "withGlobalTauri": false,
    "windows": [
      {
        "title": "J.A.R.V.I.S.",
        "width": 1100,
        "height": 720,
        "minWidth": 800,
        "minHeight": 600,
        "resizable": true,
        "decorations": false,
        "transparent": true,
        "center": true
      }
    ],
    "security": {
      "csp": "default-src 'self'; connect-src 'self' ws://127.0.0.1:8765; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'"
    }
  },
  "bundle": {
    "active": true,
    "targets": "all",
    "icon": ["icons/32x32.png", "icons/128x128.png", "icons/icon.ico"],
    "externalBin": ["binaries/jarvis-server"],
    "resources": ["binaries/*"]
  }
}
```

- [ ] **Step 2: Mettre à jour capabilities/default.json**

```json
{
  "$schema": "https://schema.tauri.app/config/2/capability",
  "identifier": "default",
  "description": "Default JARVIS capabilities",
  "windows": ["main"],
  "permissions": [
    "core:default",
    "shell:allow-execute",
    "shell:allow-open"
  ]
}
```

- [ ] **Step 3: Créer commands/sidecar.rs**

```rust
use std::process::{Child, Command};
use std::sync::Mutex;
use tauri::State;

pub struct SidecarState(pub Mutex<Option<Child>>);

#[tauri::command]
pub fn start_server(state: State<'_, SidecarState>) -> Result<(), String> {
    let mut child_guard = state.0.lock().map_err(|e| e.to_string())?;
    if child_guard.is_some() {
        return Ok(());
    }
    let child = Command::new("binaries/jarvis-server")
        .spawn()
        .map_err(|e| format!("Impossible de démarrer le serveur: {}", e))?;
    *child_guard = Some(child);
    Ok(())
}

#[tauri::command]
pub fn stop_server(state: State<'_, SidecarState>) -> Result<(), String> {
    let mut child_guard = state.0.lock().map_err(|e| e.to_string())?;
    if let Some(mut child) = child_guard.take() {
        child.kill().map_err(|e| e.to_string())?;
    }
    Ok(())
}
```

- [ ] **Step 4: Mettre à jour lib.rs**

```rust
mod commands;
use commands::sidecar::{start_server, stop_server, SidecarState};
use std::sync::Mutex;

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .manage(SidecarState(Mutex::new(None)))
        .invoke_handler(tauri::generate_handler![start_server, stop_server])
        .setup(|app| {
            // Démarrer le serveur Python au lancement
            let state = app.state::<SidecarState>();
            let _ = start_server(state);
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running JARVIS");
}
```

- [ ] **Step 5: Tester le build dev**

```powershell
cd "C:\Users\Momo\Documents\Jarvis\client"
npx tauri dev
```

- [ ] **Step 6: Commit**

```bash
git add client/src-tauri/
git commit -m "feat: Tauri sidecar config — serveur Python embarqué"
```

---

## Phase 9 — Build & Distribution

### Task 15: Scripts PowerShell + Build

**Files:**
- Create: `scripts/setup.ps1`
- Create: `scripts/build.ps1`
- Create: `scripts/clean.ps1`

- [ ] **Step 1: Créer scripts/setup.ps1**

```powershell
#Requires -Version 5.1
<#
.SYNOPSIS Setup JARVIS — installe les dépendances et télécharge les modèles.
#>
param(
    [switch]$SkipModels
)

$ErrorActionPreference = "Stop"
$Root = Split-Path $PSScriptRoot -Parent

Write-Host "[JARVIS SETUP] Création du venv Python..." -ForegroundColor Cyan
Set-Location "$Root\server"
python -m venv .venv
& ".\.venv\Scripts\Activate.ps1"

Write-Host "[JARVIS SETUP] Installation des dépendances..." -ForegroundColor Cyan
pip install -r requirements.txt

Write-Host "[JARVIS SETUP] Installation llama-cpp-python CUDA..." -ForegroundColor Cyan
pip install llama-cpp-python --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cu121

Write-Host "[JARVIS SETUP] Installation npm..." -ForegroundColor Cyan
Set-Location "$Root\client"
npm install

if (-not $SkipModels) {
    Write-Host "[JARVIS SETUP] Téléchargement modèle LLM Mistral-7B-Q4..." -ForegroundColor Yellow
    $ModelDir = "$Root\server\models"
    New-Item -ItemType Directory -Force -Path $ModelDir | Out-Null
    $ModelUrl = "https://huggingface.co/TheBloke/Mistral-7B-Instruct-v0.3-GGUF/resolve/main/mistral-7b-instruct-v0.3.Q4_K_M.gguf"
    $ModelPath = "$ModelDir\mistral-7b-instruct-v0.3.Q4_K_M.gguf"
    if (-not (Test-Path $ModelPath)) {
        Write-Host "Téléchargement en cours (~4.4 GB)..." -ForegroundColor Yellow
        Invoke-WebRequest -Uri $ModelUrl -OutFile $ModelPath -UseBasicParsing
    } else {
        Write-Host "Modèle déjà présent." -ForegroundColor Green
    }
}

Write-Host "[JARVIS SETUP] ✓ Setup terminé!" -ForegroundColor Green
```

- [ ] **Step 2: Créer scripts/build.ps1**

```powershell
#Requires -Version 5.1
<#
.SYNOPSIS Build JARVIS — PyInstaller + Tauri release build.
#>
$ErrorActionPreference = "Stop"
$Root = Split-Path $PSScriptRoot -Parent
$ServerDir = "$Root\server"
$ClientDir = "$Root\client"

# Étape 1: Kill les processus existants
Write-Host "[BUILD] Arrêt des processus JARVIS..." -ForegroundColor Cyan
Get-Process -Name "jarvis*" -ErrorAction SilentlyContinue | Stop-Process -Force

# Étape 2: Clean anciens artefacts
Write-Host "[BUILD] Nettoyage artefacts..." -ForegroundColor Cyan
$CleanPaths = @("$ServerDir\dist", "$ServerDir\build", "$ServerDir\*.spec")
foreach ($p in $CleanPaths) {
    Remove-Item -Path $p -Recurse -Force -ErrorAction SilentlyContinue
}

# Étape 3: Build Python avec PyInstaller
Write-Host "[BUILD] PyInstaller — compilation serveur Python..." -ForegroundColor Cyan
Set-Location $ServerDir
& ".\.venv\Scripts\Activate.ps1"
pip install pyinstaller -q
pyinstaller --onefile --name "jarvis-server" --distpath "$ClientDir\src-tauri\binaries" main.py
if ($LASTEXITCODE -ne 0) { throw "PyInstaller a échoué" }
Write-Host "[BUILD] ✓ jarvis-server.exe généré" -ForegroundColor Green

# Étape 4: Tauri build
Write-Host "[BUILD] Tauri build release..." -ForegroundColor Cyan
Set-Location $ClientDir
npx tauri build
if ($LASTEXITCODE -ne 0) { throw "Tauri build a échoué" }

Write-Host "[BUILD] ✓ Build terminé! Installeur dans client\src-tauri\target\release\bundle\" -ForegroundColor Green
```

- [ ] **Step 3: Créer scripts/clean.ps1**

```powershell
#Requires -Version 5.1
$Root = Split-Path $PSScriptRoot -Parent

Write-Host "[CLEAN] Nettoyage post-build..." -ForegroundColor Cyan
$Targets = @(
    "$Root\server\build",
    "$Root\server\dist",
    "$Root\server\*.spec",
    "$Root\client\src-tauri\target\release\build",
    "$Root\client\src-tauri\target\release\deps",
    "$Root\client\dist"
)
foreach ($t in $Targets) {
    Remove-Item -Path $t -Recurse -Force -ErrorAction SilentlyContinue
    Write-Host "  Supprimé: $t" -ForegroundColor DarkGray
}
Write-Host "[CLEAN] ✓ Nettoyage terminé." -ForegroundColor Green
```

- [ ] **Step 4: Commit final**

```bash
git add scripts/
git commit -m "feat: scripts PowerShell setup/build/clean"
git push -u origin main
```

---

## Checklist de Démarrage Rapide

```powershell
# 1. Cloner le repo
git clone https://github.com/heiphaistos44-crypto/Jarvis.git
cd Jarvis

# 2. Setup (installe deps + télécharge modèle ~4.4 GB)
.\scripts\setup.ps1

# 3. Démarrer le serveur Python (dev)
cd server
.\.venv\Scripts\Activate.ps1
python main.py

# 4. Démarrer le frontend Tauri (dev)
cd ..\client
npx tauri dev
```

---

## Notes Importantes

### Modèles à télécharger manuellement

| Modèle | Taille | Source |
|--------|--------|--------|
| `mistral-7b-instruct-v0.3.Q4_K_M.gguf` | ~4.4 GB | HuggingFace TheBloke |
| `piper.exe` | ~5 MB | GitHub rhasspy/piper releases |
| `en_US-lessac-high.onnx` | ~65 MB | GitHub rhasspy/piper voices |
| `en_US-lessac-high.onnx.json` | 1 KB | Accompagne le .onnx |

### Budget VRAM RTX 3070 (8 GB)

| Composant | VRAM |
|-----------|------|
| Mistral-7B Q4_K_M (35 layers GPU) | ~5.5 GB |
| Faster-Whisper small | ~0.5 GB |
| OS + drivers | ~0.5 GB |
| **Total** | **~6.5 GB** ✓ |

### Ordre de chargement des modèles

Pour éviter les OOM: LLM → Whisper → TTS (CPU).

---

## Self-Review — Couverture PRD

| Exigence PRD | Task |
|--------------|------|
| Tauri v2 + React + TypeScript | Task 3 |
| Tailwind CSS + design Iron Man | Task 3, 6, 7, 8 |
| WebSocket client↔server | Task 5, 9 |
| LLM GGUF CUDA | Task 10 |
| STT Faster-Whisper | Task 11 |
| TTS Piper | Task 12 |
| Tool calling sécurisé (whitelist) | Task 13 |
| Visualiseur audio (Web Audio) | Task 6 |
| Status bar (LISTENING/THINKING/SPEAKING) | Task 8 |
| Mémoire contexte | Task 10 |
| Logging centralisé | Task 2 |
| Typage strict Pydantic + TypeScript | Task 2, 4 |
| Build PyInstaller + Tauri sidecar | Task 14, 15 |
| Scripts PowerShell | Task 15 |
| .gitignore secrets/logs/models | Task 1 |
| Wake Word (openWakeWord) | ⚠ Non implémenté — Phase optionnelle |

### Phase optionnelle — Wake Word (openWakeWord)

Wake Word nécessite un microphone toujours actif en arrière-plan. À implémenter en `server/core/wake_word.py` une fois les autres phases validées. Pattern: thread séparé → queue → trigger `handle_text_query`.
