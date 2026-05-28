import { create } from "zustand";
import type { JarvisStatus, Message, ServerEvent } from "../types";

interface JarvisState {
  status: JarvisStatus;
  messages: Message[];
  isConnected: boolean;
  pendingMessageId: string | null;
  isMicActive: boolean;
  ttsEnabled: boolean;
  selectedVoice: string;
  wsSend: ((event: object) => void) | null;

  setStatus: (status: JarvisStatus) => void;
  setConnected: (v: boolean) => void;
  addMessage: (msg: Message) => void;
  appendToken: (messageId: string, token: string) => void;
  setMicActive: (v: boolean) => void;
  setTtsEnabled: (v: boolean) => void;
  setSelectedVoice: (v: string) => void;
  setWsSend: (fn: (event: object) => void) => void;
  handleServerEvent: (event: ServerEvent) => void;
}

async function playTtsAudio(b64: string, onDone: () => void) {
  try {
    const binary = atob(b64);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
    const audioCtx = new AudioContext();
    const buffer = await audioCtx.decodeAudioData(bytes.buffer);
    const source = audioCtx.createBufferSource();
    source.buffer = buffer;
    source.connect(audioCtx.destination);
    source.onended = () => {
      audioCtx.close();
      onDone();
    };
    source.start(0);
  } catch (e) {
    console.error("TTS playback error:", e);
    onDone();
  }
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

  setStatus: (status) => set({ status }),
  setConnected: (isConnected) => set({ isConnected }),
  setMicActive: (isMicActive) => set({ isMicActive }),
  setTtsEnabled: (ttsEnabled) => set({ ttsEnabled }),
  setSelectedVoice: (selectedVoice) => set({ selectedVoice }),
  setWsSend: (fn) => set({ wsSend: fn }),

  addMessage: (msg) =>
    set((s) => ({ messages: [...s.messages, msg] })),

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
        // Show transcribed text as user message
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
    }
  },
}));
