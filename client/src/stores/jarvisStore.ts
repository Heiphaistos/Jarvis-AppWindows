import { create } from "zustand";
import type { JarvisStatus, Message, ServerEvent } from "../types";

interface JarvisState {
  status: JarvisStatus;
  messages: Message[];
  isConnected: boolean;
  pendingMessageId: string | null;
  isMicActive: boolean;

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
