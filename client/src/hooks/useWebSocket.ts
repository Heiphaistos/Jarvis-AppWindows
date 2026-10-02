import { useEffect, useRef, useCallback } from "react";
import { useJarvisStore } from "../stores/jarvisStore";
import { wsUrl } from "../lib/platform";
import type { ClientEvent, ServerEvent } from "../types";

const RECONNECT_BASE_MS = 1000;
const RECONNECT_MAX_MS = 30_000;

export function useWebSocket() {
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<number | undefined>(undefined);
  const reconnectAttempts = useRef(0);

  const send = useCallback((event: ClientEvent) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(event));
    }
  }, []);

  const connect = useCallback(() => {
    // Avoid double-connecting if already open or connecting
    if (
      wsRef.current?.readyState === WebSocket.OPEN ||
      wsRef.current?.readyState === WebSocket.CONNECTING
    ) return;

    const ws = new WebSocket(wsUrl());
    wsRef.current = ws;

    ws.onopen = () => {
      reconnectAttempts.current = 0;
      const store = useJarvisStore.getState();
      store.setConnected(true);
      store.setWsSend((event) => {
        if (ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify(event));
      });
      // Synchronise la voix française choisie dès la connexion — le serveur
      // ne doit jamais parler avec une autre voix que celle affichée dans l'UI.
      ws.send(JSON.stringify({
        type: "set_voice",
        payload: { voice: store.selectedVoice },
      }));
      ws.send(JSON.stringify({
        type: "set_tts",
        payload: { enabled: store.ttsEnabled },
      }));
    };

    ws.onmessage = (evt) => {
      try {
        const event = JSON.parse(evt.data) as ServerEvent;
        useJarvisStore.getState().handleServerEvent(event);
      } catch (e) {
        console.error("WS parse error", e);
      }
    };

    ws.onclose = () => {
      useJarvisStore.getState().setConnected(false);
      // Exponential backoff: 1s, 2s, 4s, 8s … capped at 30s
      const delay = Math.min(
        RECONNECT_BASE_MS * 2 ** reconnectAttempts.current,
        RECONNECT_MAX_MS,
      );
      reconnectAttempts.current += 1;
      reconnectTimer.current = window.setTimeout(connect, delay);
    };

    ws.onerror = () => ws.close();
  }, []);

  useEffect(() => {
    connect();
    return () => {
      clearTimeout(reconnectTimer.current);
      wsRef.current?.close();
    };
  }, [connect]);

  return { send };
}
