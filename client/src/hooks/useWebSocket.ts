import { useEffect, useRef, useCallback } from "react";
import { useJarvisStore } from "../stores/jarvisStore";
import type { ClientEvent, ServerEvent } from "../types";

const WS_URL = "ws://127.0.0.1:8765/ws";
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

    const ws = new WebSocket(WS_URL);
    wsRef.current = ws;

    ws.onopen = () => {
      reconnectAttempts.current = 0;
      useJarvisStore.getState().setConnected(true);
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
