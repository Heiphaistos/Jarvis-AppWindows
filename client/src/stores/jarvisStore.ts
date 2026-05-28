import { create } from "zustand";
import type { JarvisStatus, Message, ServerEvent } from "../types";

const MAX_MESSAGES = 200;
const TTS_TIMEOUT_MS = 60_000;

// Singleton AudioContext — one per app session
let _audioCtx: AudioContext | null = null;
function getAudioContext(): AudioContext {
  if (!_audioCtx || _audioCtx.state === "closed") {
    _audioCtx = new AudioContext();
  }
  if (_audioCtx.state === "suspended") {
    void _audioCtx.resume();
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
  comp.connect(ctx.destination);
  return hp; // chain entry point
}

async function playTtsAudio(b64: string, onDone: () => void) {
  let timeoutId: number | undefined;
  try {
    const binary = atob(b64);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
    const ctx = getAudioContext();
    const buffer = await ctx.decodeAudioData(bytes.buffer);
    const source = ctx.createBufferSource();
    source.buffer = buffer;
    // Slight speed-up: raises pitch ~4% for a crisper, more synthetic quality
    source.playbackRate.value = 1.04;
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

  setStatus: (status: JarvisStatus) => void;
  setConnected: (v: boolean) => void;
  addMessage: (msg: Message) => void;
  appendToken: (messageId: string, token: string) => void;
  setMicActive: (v: boolean) => void;
  setTtsEnabled: (v: boolean) => void;
  setSelectedVoice: (v: string) => void;
  setWsSend: (fn: (event: object) => void) => void;
  clearMessages: () => void;
  handleServerEvent: (event: ServerEvent) => void;
}

export const useJarvisStore = create<JarvisState>((set, get) => ({
  status: "idle",
  messages: [],
  isConnected: false,
  pendingMessageId: null,
  isMicActive: false,
  ttsEnabled: true,
  selectedVoice: "fr_FR-upmc-medium",
  wsSend: null,
  sttAvailable: false,
  llmAvailable: false,

  setStatus: (status) => set({ status }),
  setConnected: (isConnected) => set({ isConnected }),
  setMicActive: (isMicActive) => set({ isMicActive }),
  setTtsEnabled: (ttsEnabled) => set({ ttsEnabled }),
  setSelectedVoice: (selectedVoice) => set({ selectedVoice }),
  setWsSend: (fn) => set({ wsSend: fn }),
  clearMessages: () => {
    set({ messages: [], pendingMessageId: null });
    get().wsSend?.({ type: "clear_history", payload: {} });
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

      case "error":
        setStatus("error");
        addMessage({
          id: crypto.randomUUID(),
          role: "system",
          content: `⚠ ${event.payload.message}`,
          timestamp: Date.now(),
        });
        break;

      case "server_status":
        set({
          sttAvailable: event.payload.stt,
          llmAvailable: event.payload.llm,
        });
        break;
    }
  },
}));
