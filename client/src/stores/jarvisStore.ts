import { create } from "zustand";
import type { AgentStep, BrainRoute, JarvisStatus, Message, ServerEvent } from "../types";

const MAX_MESSAGES = 200;
const MAX_AGENT_STEPS = 30;

// Singleton AudioContext — one per app session
let _audioCtx: AudioContext | null = null;
export let ttsAnalyser: AnalyserNode | null = null;
export function getTtsAnalyser(): AnalyserNode | null {
  return ttsAnalyser;
}
async function getAudioContext(): Promise<AudioContext> {
  if (!_audioCtx || _audioCtx.state === "closed") {
    _audioCtx = new AudioContext();
    ttsAnalyser = _audioCtx.createAnalyser();
    ttsAnalyser.fftSize = 512;
    ttsAnalyser.connect(_audioCtx.destination);
  }
  if (_audioCtx.state === "suspended") {
    // Sans await, la lecture démarre sur un contexte suspendu → aucun son
    // et onended ne se déclenche jamais (queue TTS bloquée 60s).
    try {
      await _audioCtx.resume();
    } catch (e) {
      console.error("AudioContext resume failed:", e);
    }
  }
  return _audioCtx;
}

function buildJarvisChain(ctx: AudioContext): AudioNode {
  // High-pass: remove low-end rumble below 90 Hz
  const hp = ctx.createBiquadFilter();
  hp.type = "highpass";
  hp.frequency.value = 90;

  // Presence boost at 3 kHz — gives JARVIS that crisp, clear-articulation quality
  const presence = ctx.createBiquadFilter();
  presence.type = "peaking";
  presence.frequency.value = 3000;
  presence.Q.value = 1.4;
  presence.gain.value = 4;

  // Slight high-shelf rolloff above 10 kHz — cuts harshness
  const shelf = ctx.createBiquadFilter();
  shelf.type = "highshelf";
  shelf.frequency.value = 10000;
  shelf.gain.value = -2;

  // Compressor: tight, even dynamics
  const comp = ctx.createDynamicsCompressor();
  comp.threshold.value = -20;
  comp.knee.value = 5;
  comp.ratio.value = 5;
  comp.attack.value = 0.003;
  comp.release.value = 0.12;

  hp.connect(presence);
  presence.connect(shelf);
  shelf.connect(comp);

  let tail: AudioNode = comp;

  // ── Effet « armure » façon film : le timbre JARVIS d'Iron Man vient
  // surtout du traitement haut-parleur — résonances métalliques (combs très
  // courts) + bande passante resserrée, mixées sous le signal clair.
  if (useJarvisStore.getState().armorFx) {
    const bandLow = ctx.createBiquadFilter();
    bandLow.type = "highpass";
    bandLow.frequency.value = 280;
    const bandHigh = ctx.createBiquadFilter();
    bandHigh.type = "lowpass";
    bandHigh.frequency.value = 6200;
    const metal1 = ctx.createDelay(0.05);
    metal1.delayTime.value = 0.009;
    const fb1 = ctx.createGain();
    fb1.gain.value = 0.32;
    metal1.connect(fb1).connect(metal1);
    const metal2 = ctx.createDelay(0.05);
    metal2.delayTime.value = 0.0135;
    const fb2 = ctx.createGain();
    fb2.gain.value = 0.24;
    metal2.connect(fb2).connect(metal2);
    const wet = ctx.createGain();
    wet.gain.value = 0.4;
    const dry = ctx.createGain();
    dry.gain.value = 0.78;
    const mix = ctx.createGain();

    comp.connect(dry).connect(mix);
    comp.connect(bandLow);
    bandLow.connect(bandHigh);
    bandHigh.connect(metal1).connect(wet);
    bandHigh.connect(metal2).connect(wet);
    wet.connect(mix);
    tail = mix;
  }

  if (ttsAnalyser) {
    tail.connect(ttsAnalyser);
  } else {
    tail.connect(ctx.destination);
  }
  return hp; // chain entry point
}

// ── Thèmes esthétiques ───────────────────────────────────────────────────────
export type ThemeName =
  | "arctic" | "mark3" | "emerald" | "amethyst"
  | "crimson" | "solar" | "silver" | "neon" | "custom";
export type HoloStyle = "sphere" | "reactor" | "galaxy" | "dna" | "matrix" | "vortex";
export type HoloDensity = "low" | "normal" | "high";
export type HoloSpeed = "slow" | "normal" | "fast";

export const THEMES: Record<ThemeName, { label: string; accent: string; accentSoft: string }> = {
  arctic:   { label: "Arctic (classique)", accent: "#00d4ff", accentSoft: "#0088aa" },
  mark3:    { label: "Mark III (rouge & or)", accent: "#ffb340", accentSoft: "#cc4422" },
  emerald:  { label: "Émeraude", accent: "#00ff9d", accentSoft: "#00aa66" },
  amethyst: { label: "Améthyste", accent: "#b388ff", accentSoft: "#7744cc" },
  crimson:  { label: "Crimson", accent: "#ff3355", accentSoft: "#aa1133" },
  solar:    { label: "Solar", accent: "#ffdd44", accentSoft: "#cc8800" },
  silver:   { label: "Argent", accent: "#cfe8ff", accentSoft: "#7799bb" },
  neon:     { label: "Néon Rose", accent: "#ff44dd", accentSoft: "#aa2299" },
  custom:   { label: "Personnalisé", accent: "#00d4ff", accentSoft: "#0088aa" },
};

/** Accent effectif du thème courant (gère la couleur personnalisée). */
export function accentOf(theme: ThemeName, customAccent: string): string {
  return theme === "custom" ? customAccent : THEMES[theme].accent;
}

function _stored<T extends string>(key: string, valid: readonly T[], fallback: T): T {
  const v = localStorage.getItem(key);
  return v && (valid as readonly string[]).includes(v) ? (v as T) : fallback;
}

const MALE_VOICES = new Set([
  "gemini:Charon",
  "gemini:Orus",
  "gemini:Iapetus",
  "gemini:Algenib",
  "edge:fr-FR-HenriNeural",
  "edge:fr-FR-RemyMultilingualNeural",
  "fr_FR-upmc-medium",
]);

function _initialVoice(): string {
  // Migration : tout choix antérieur non masculin (SIWIS, MLS, Denise…)
  // revient à Henri — l'identité vocale JARVIS est masculine.
  const stored = localStorage.getItem("jarvis_voice");
  return stored && MALE_VOICES.has(stored) ? stored : "edge:fr-FR-HenriNeural";
}

function ttsPlaybackRate(): number {
  // +4 % de pitch : uniquement pour Piper (rend le synthétique plus net).
  // Les voix neurales Edge sont naturelles — ne pas les dénaturer.
  const v = useJarvisStore.getState().selectedVoice;
  return v.startsWith("edge:") || v.startsWith("gemini:") ? 1.0 : 1.04;
}

// ── Mode LIVE : flux PCM 16 bits de Gemini, joué sans trou ni recouvrement ──
let _liveNextTime = 0;
let _liveSources: AudioBufferSourceNode[] = [];
let _liveChain: AudioNode | null = null;

async function playLivePcm(b64: string, rate: number, onIdle: () => void) {
  const ctx = await getAudioContext();
  const bin = atob(b64);
  const bytes = new Uint8Array(bin.length - (bin.length % 2));
  for (let i = 0; i < bytes.length; i++) bytes[i] = bin.charCodeAt(i);
  const pcm = new Int16Array(bytes.buffer);
  if (!pcm.length) return;
  const buffer = ctx.createBuffer(1, pcm.length, rate);
  const channel = buffer.getChannelData(0);
  for (let i = 0; i < pcm.length; i++) channel[i] = pcm[i] / 32768;
  const source = ctx.createBufferSource();
  source.buffer = buffer;
  if (!_liveChain) _liveChain = buildJarvisChain(ctx);
  source.connect(_liveChain);
  // Chaque morceau démarre exactement à la fin du précédent (petite avance de 40 ms au départ).
  const start = Math.max(ctx.currentTime + 0.04, _liveNextTime);
  source.start(start);
  _liveNextTime = start + buffer.duration;
  _liveSources.push(source);
  source.onended = () => {
    _liveSources = _liveSources.filter((s) => s !== source);
    if (_liveSources.length === 0) onIdle();
  };
}

function stopLivePlayback() {
  for (const s of _liveSources) {
    try { s.stop(); } catch { /* déjà terminé */ }
  }
  _liveSources = [];
  _liveNextTime = 0;
}

let _liveUserMsg: string | null = null;
let _liveAssistantMsg: string | null = null;

async function playTtsAudio(b64: string, onDone: () => void) {
  let timeoutId: number | undefined;
  try {
    const binary = atob(b64);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
    const ctx = await getAudioContext();
    const buffer = await ctx.decodeAudioData(bytes.buffer);
    const source = ctx.createBufferSource();
    source.buffer = buffer;
    source.playbackRate.value = ttsPlaybackRate();
    source.connect(buildJarvisChain(ctx));

    timeoutId = window.setTimeout(() => {
      source.stop();
      onDone();
    }, TTS_TIMEOUT_MS);

    source.onended = () => {
      clearTimeout(timeoutId);
      onDone();
    };
    source.start(0);
  } catch (e) {
    console.error("TTS playback error:", e);
    clearTimeout(timeoutId);
    onDone();
  }
}

const _ttsQueue: string[] = [];
let _ttsPlaying = false;
const TTS_TIMEOUT_MS = 60_000;

async function _playNextChunk(onAllDone: () => void): Promise<void> {
  if (_ttsQueue.length === 0) {
    _ttsPlaying = false;
    onAllDone();
    return;
  }
  const b64 = _ttsQueue.shift()!;
  try {
    const binary = atob(b64);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
    const ctx = await getAudioContext();
    const buffer = await ctx.decodeAudioData(bytes.buffer);
    const source = ctx.createBufferSource();
    source.buffer = buffer;
    source.playbackRate.value = ttsPlaybackRate();
    source.connect(buildJarvisChain(ctx));

    let tid: number | undefined;
    const next = () => {
      clearTimeout(tid);
      void _playNextChunk(onAllDone);
    };
    tid = window.setTimeout(next, TTS_TIMEOUT_MS);
    source.onended = next;
    source.start(0);
  } catch (e) {
    console.error("TTS chunk error:", e);
    void _playNextChunk(onAllDone);
  }
}

function enqueueTtsChunk(b64: string, final: boolean, onAllDone: () => void): void {
  if (b64) _ttsQueue.push(b64);
  if (!_ttsPlaying && _ttsQueue.length > 0) {
    _ttsPlaying = true;
    void _playNextChunk(onAllDone);
  } else if (final && _ttsQueue.length === 0 && !_ttsPlaying) {
    onAllDone();
  }
}

function clearTtsQueue(): void {
  _ttsQueue.length = 0;
  _ttsPlaying = false;
}

interface JarvisState {
  status: JarvisStatus;
  messages: Message[];
  isConnected: boolean;
  pendingMessageId: string | null;
  isMicActive: boolean;
  ttsEnabled: boolean;
  selectedVoice: string;
  wsSend: ((event: object) => void) | null;
  sttAvailable: boolean;
  llmAvailable: boolean;
  providerLabel: string;
  providerModel: string;
  /** Dernier cerveau utilisé (mode AUTO) : niveau, modèle, latence du 1er mot. */
  lastBrain: BrainRoute | null;
  /** Cerveau qui a ouvert chaque réponse (id du message → routage). */
  messageBrains: Record<string, BrainRoute>;
  /** Conversation vocale temps réel Gemini Live en cours. */
  liveActive: boolean;
  agentSteps: AgentStep[];
  bootDone: boolean;
  wakeWordEnabled: boolean;
  wakeWordAvailable: boolean;
  wakeDetected: boolean;
  councilEnabled: boolean;
  setCouncilEnabled: (v: boolean) => void;
  metrics: { cpu: number; ram: number; gpu: number | null; vram: number | null };
  perfActive: string;
  /** Incrémenté quand la mémoire automatique apprend quelque chose (rafraîchit l'UI). */
  memoryVersion: number;
  sendQuery: (text: string) => void;
  stopGeneration: () => void;
  armorFx: boolean;
  setArmorFx: (v: boolean) => void;
  theme: ThemeName;
  setTheme: (t: ThemeName) => void;
  customAccent: string;
  setCustomAccent: (c: string) => void;
  holoStyle: HoloStyle;
  setHoloStyle: (h: HoloStyle) => void;
  holoDensity: HoloDensity;
  setHoloDensity: (d: HoloDensity) => void;
  holoSpeed: HoloSpeed;
  setHoloSpeed: (s: HoloSpeed) => void;
  layoutSide: "left" | "right";
  setLayoutSide: (s: "left" | "right") => void;

  setStatus: (status: JarvisStatus) => void;
  setConnected: (v: boolean) => void;
  addMessage: (msg: Message) => void;
  appendToken: (messageId: string, token: string) => void;
  setMicActive: (v: boolean) => void;
  setTtsEnabled: (v: boolean) => void;
  setSelectedVoice: (v: string) => void;
  setWsSend: (fn: (event: object) => void) => void;
  setBootDone: (v: boolean) => void;
  setWakeWordEnabled: (v: boolean) => void;
  consumeWakeDetected: () => void;
  clearMessages: () => void;
  exportConversation: () => void;
  handleServerEvent: (event: ServerEvent) => void;
}

export const useJarvisStore = create<JarvisState>((set, get) => ({
  status: "idle",
  messages: [],
  isConnected: false,
  pendingMessageId: null,
  isMicActive: false,
  ttsEnabled: true,
  selectedVoice: _initialVoice(),
  wsSend: null,
  sttAvailable: false,
  llmAvailable: false,
  providerLabel: "Local (Mistral GGUF)",
  providerModel: "",
  lastBrain: null,
  messageBrains: {},
  liveActive: false,
  agentSteps: [],
  bootDone: false,
  wakeWordEnabled: localStorage.getItem("jarvis_wake_word") === "1",
  wakeWordAvailable: true,
  wakeDetected: false,
  councilEnabled: localStorage.getItem("jarvis_council") === "1",

  setStatus: (status) => set({ status }),
  setBootDone: (bootDone) => set({ bootDone }),
  setWakeWordEnabled: (wakeWordEnabled) => {
    localStorage.setItem("jarvis_wake_word", wakeWordEnabled ? "1" : "0");
    set({ wakeWordEnabled });
  },
  consumeWakeDetected: () => set({ wakeDetected: false }),
  setCouncilEnabled: (councilEnabled) => {
    localStorage.setItem("jarvis_council", councilEnabled ? "1" : "0");
    set({ councilEnabled });
  },
  metrics: { cpu: 0, ram: 0, gpu: null, vram: null },
  perfActive: "",
  memoryVersion: 0,
  armorFx: localStorage.getItem("jarvis_armor_fx") !== "0",
  setArmorFx: (armorFx) => {
    localStorage.setItem("jarvis_armor_fx", armorFx ? "1" : "0");
    set({ armorFx });
  },
  theme: _stored(
    "jarvis_theme",
    ["arctic", "mark3", "emerald", "amethyst", "crimson", "solar", "silver", "neon", "custom"] as const,
    "arctic",
  ),
  setTheme: (theme) => {
    localStorage.setItem("jarvis_theme", theme);
    set({ theme });
  },
  customAccent: localStorage.getItem("jarvis_custom_accent") || "#00d4ff",
  setCustomAccent: (customAccent) => {
    localStorage.setItem("jarvis_custom_accent", customAccent);
    set({ customAccent });
  },
  holoStyle: _stored(
    "jarvis_holo",
    ["sphere", "reactor", "galaxy", "dna", "matrix", "vortex"] as const,
    "sphere",
  ),
  setHoloStyle: (holoStyle) => {
    localStorage.setItem("jarvis_holo", holoStyle);
    set({ holoStyle });
  },
  holoDensity: _stored("jarvis_holo_density", ["low", "normal", "high"] as const, "normal"),
  setHoloDensity: (holoDensity) => {
    localStorage.setItem("jarvis_holo_density", holoDensity);
    set({ holoDensity });
  },
  holoSpeed: _stored("jarvis_holo_speed", ["slow", "normal", "fast"] as const, "normal"),
  setHoloSpeed: (holoSpeed) => {
    localStorage.setItem("jarvis_holo_speed", holoSpeed);
    set({ holoSpeed });
  },
  layoutSide: _stored("jarvis_layout", ["left", "right"] as const, "left"),
  setLayoutSide: (layoutSide) => {
    localStorage.setItem("jarvis_layout", layoutSide);
    set({ layoutSide });
  },

  sendQuery: (text) => {
    const { wsSend, addMessage, councilEnabled } = get();
    if (!text.trim() || !wsSend) return;
    addMessage({
      id: crypto.randomUUID(),
      role: "user",
      content: text,
      timestamp: Date.now(),
    });
    wsSend({ type: "text_query", payload: { text, council: councilEnabled } });
  },

  stopGeneration: () => {
    clearTtsQueue();
    get().wsSend?.({ type: "stop_generation", payload: {} });
  },
  setConnected: (isConnected) => {
    if (!isConnected) clearTtsQueue();
    set({ isConnected });
  },
  setMicActive: (isMicActive) => set({ isMicActive }),
  setTtsEnabled: (ttsEnabled) => set({ ttsEnabled }),
  setSelectedVoice: (selectedVoice) => {
    localStorage.setItem("jarvis_voice", selectedVoice);
    set({ selectedVoice });
  },
  setWsSend: (fn) => set({ wsSend: fn }),
  clearMessages: () => {
    clearTtsQueue();
    set({ messages: [], pendingMessageId: null });
    get().wsSend?.({ type: "clear_history", payload: {} });
  },

  exportConversation: () => {
    const messages = get().messages;
    if (messages.length === 0) return;
    const lines: string[] = [
      `# Conversation JARVIS — ${new Date().toLocaleDateString("fr-FR")}`,
      `\nExportée le ${new Date().toLocaleString("fr-FR")}`,
      "\n---\n",
    ];
    for (const msg of messages) {
      const roleLabel =
        msg.role === "user"
          ? "**Vous**"
          : msg.role === "assistant"
          ? "**JARVIS**"
          : "**Système**";
      const time = new Date(msg.timestamp).toLocaleTimeString("fr-FR", {
        hour: "2-digit",
        minute: "2-digit",
      });
      lines.push(`${roleLabel} *(${time})*\n\n${msg.content}\n\n---\n`);
    }
    const blob = new Blob([lines.join("\n")], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `jarvis-${new Date().toISOString().slice(0, 10)}.md`;
    a.click();
    URL.revokeObjectURL(url);
  },

  addMessage: (msg) =>
    set((s) => ({
      messages: s.messages.length >= MAX_MESSAGES
        ? [...s.messages.slice(-MAX_MESSAGES + 1), msg]
        : [...s.messages, msg],
    })),

  appendToken: (messageId, token) =>
    set((s) => ({
      messages: s.messages.map((m) =>
        m.id === messageId ? { ...m, content: m.content + token } : m
      ),
    })),

  handleServerEvent: (event) => {
    const { setStatus, addMessage, appendToken, wsSend } = get();

    switch (event.type) {
      case "status":
        // Nouvelle requête → efface la timeline de raisonnement précédente
        if (event.payload.status === "processing") set({ agentSteps: [] });
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

      case "stt_text":
        addMessage({
          id: crypto.randomUUID(),
          role: "user",
          content: event.payload.text,
          timestamp: Date.now(),
        });
        break;

      case "tts_audio":
        if (get().ttsEnabled) {
          playTtsAudio(event.payload.audio, () => {
            setStatus("idle");
            wsSend?.({ type: "tts_done", payload: {} });
          });
        } else {
          setStatus("idle");
          wsSend?.({ type: "tts_done", payload: {} });
        }
        break;

      case "tts_chunk": {
        const { audio, final } = event.payload;
        if (!get().ttsEnabled) {
          if (final) {
            setStatus("idle");
            wsSend?.({ type: "tts_done", payload: {} });
          }
          return;
        }
        enqueueTtsChunk(audio, final, () => {
          setStatus("idle");
          wsSend?.({ type: "tts_done", payload: {} });
        });
        break;
      }

      case "error":
        setStatus("error");
        addMessage({
          id: crypto.randomUUID(),
          role: "system",
          content: `⚠ ${event.payload.message}`,
          timestamp: Date.now(),
        });
        break;

      case "tool_result":
        // Les tool_results sont gérés silencieusement (le LLM en parle dans sa réponse)
        break;

      case "reminder": {
        const { kind, message } = event.payload;
        get().addMessage({
          id: crypto.randomUUID(),
          role: "system",
          content: `${kind === "timer" ? "⏱ Minuteur terminé" : "⏰ Rappel"} — ${message}`,
          timestamp: Date.now(),
        });
        break;
      }
      case "live_state": {
        const { active, error } = event.payload;
        set({ liveActive: active });
        if (!active) {
          stopLivePlayback();
          _liveUserMsg = _liveAssistantMsg = null;
          set({ status: "idle" });
        } else {
          set({ status: "listening" });
        }
        if (error) {
          get().addMessage({ id: crypto.randomUUID(), role: "system", content: `⚠ ${error}`, timestamp: Date.now() });
        }
        break;
      }
      case "live_audio": {
        set({ status: "speaking" });
        void playLivePcm(event.payload.audio, event.payload.rate, () => {
          if (get().liveActive) set({ status: "listening" });
        });
        break;
      }
      case "live_interrupted": {
        stopLivePlayback();
        if (get().liveActive) set({ status: "listening" });
        break;
      }
      case "live_transcript": {
        const { role, text } = event.payload;
        const current = role === "user" ? _liveUserMsg : _liveAssistantMsg;
        if (current && get().messages.some((m) => m.id === current)) {
          get().appendToken(current, text);
        } else {
          const id = crypto.randomUUID();
          get().addMessage({ id, role, content: text.trimStart(), timestamp: Date.now() });
          if (role === "user") _liveUserMsg = id;
          else _liveAssistantMsg = id;
        }
        break;
      }
      case "live_turn_complete": {
        _liveUserMsg = _liveAssistantMsg = null;
        break;
      }
      case "brain": {
        const route = event.payload;
        set((s) => ({
          lastBrain: route,
          // On garde le premier cerveau d'une réponse (les suivants reformulent un outil).
          messageBrains: s.messageBrains[route.messageId]
            ? s.messageBrains
            : { ...s.messageBrains, [route.messageId]: route },
        }));
        break;
      }
      case "agent_step": {
        const { phase, detail } = event.payload;
        if (phase === "done") {
          // Conserver la timeline jusqu'à la prochaine requête
          break;
        }
        set((s) => ({
          agentSteps: [
            ...s.agentSteps.slice(-MAX_AGENT_STEPS + 1),
            { phase, detail, timestamp: Date.now() },
          ],
        }));
        break;
      }

      case "wake":
        set({ wakeDetected: true });
        break;

      case "wake_unavailable":
        set({ wakeWordAvailable: false, wakeWordEnabled: false });
        addMessage({
          id: crypto.randomUUID(),
          role: "system",
          content: "⚠ Wake word indisponible — openwakeword non installé côté serveur.",
          timestamp: Date.now(),
        });
        break;

      case "memory_update":
        set((s) => ({ memoryVersion: s.memoryVersion + 1 }));
        addMessage({
          id: crypto.randomUUID(),
          role: "system",
          content: `🧠 Retenu — ${event.payload.summary}`,
          timestamp: Date.now(),
        });
        break;

      case "notice":
        addMessage({
          id: crypto.randomUUID(),
          role: "system",
          content: `ℹ ${event.payload.message}`,
          timestamp: Date.now(),
        });
        break;

      case "server_status":
        set({
          sttAvailable: event.payload.stt,
          llmAvailable: event.payload.llm,
          ...(event.payload.providerLabel
            ? { providerLabel: event.payload.providerLabel }
            : {}),
          ...(event.payload.providerModel
            ? { providerModel: event.payload.providerModel }
            : {}),
        });
        break;

      case "system_metrics":
        set({ metrics: event.payload });
        break;

      case "perf_changed":
        set({ perfActive: event.payload.active });
        break;

      case "system_alert": {
        const { message } = event.payload as { alert_type: string; message: string };
        get().addMessage({
          id: crypto.randomUUID(),
          role: "system",
          content: message,
          timestamp: Date.now(),
        });
        break;
      }
    }
  },
}));
