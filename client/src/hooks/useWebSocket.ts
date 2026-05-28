import { useEffect, useRef, useCallback } from "react";
import { useJarvisStore } from "../stores/jarvisStore";
import type { ClientEvent, ServerEvent } from "../types";

const WS_URL = "ws://127.0.0.1:8765/ws";
const RECONNECT_DELAY = 2000;

export function useWebSocket() {
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<number | undefined>(undefined);

  const send = useCallback((event: ClientEvent) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(event));
    }
  }, []);

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    const ws = new WebSocket(WS_URL);
    wsRef.current = ws;

    ws.onopen = () => {
      useJarvisStore.getState().setConnected(true);
      // Expose send to the store so tts_audio handler can use it
      useJarvisStore.getState().setWsSend((event) => {
        if (ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify(event));
      });
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
      reconnectTimer.current = setTimeout(connect, RECONNECT_DELAY);
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
