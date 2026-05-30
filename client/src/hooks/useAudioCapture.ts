import { useRef, useCallback } from "react";
import { invoke } from "@tauri-apps/api/core";
import { listen, type UnlistenFn } from "@tauri-apps/api/event";
import { useJarvisStore } from "../stores/jarvisStore";
import type { ClientEvent } from "../types";

// Capture audio native via Rust/WASAPI — contourne le bug WebView2 MediaStream→AudioContext
let _silentChunkCount = 0;
const SILENT_WARNING_THRESHOLD = 16;

interface AudioChunkPayload {
  data: number[];
  sampleRate: number;
}

export function useAudioCapture(send: (e: ClientEvent) => void) {
  const unlistenRef = useRef<UnlistenFn | null>(null);
  const activeRef = useRef(false);

  const startCapture = useCallback(async () => {
    if (activeRef.current) return;
    activeRef.current = true;
    _silentChunkCount = 0;

    try {
      // Écouter les chunks audio émis par Rust/cpal
      unlistenRef.current = await listen<AudioChunkPayload>(
        "jarvis_audio_chunk",
        (event) => {
          const { data, sampleRate } = event.payload;

          // Détection silence
          let rms = 0;
          for (let i = 0; i < data.length; i++) rms += data[i] * data[i];
          rms = Math.sqrt(rms / data.length);

          if (rms < 0.0001) {
            _silentChunkCount++;
            if (_silentChunkCount === SILENT_WARNING_THRESHOLD) {
              useJarvisStore.getState().addMessage({
                id: crypto.randomUUID(),
                role: "system",
                content:
                  "⚠ Microphone silencieux — aucun son détecté. Vérifie que le bon micro est sélectionné dans Windows.",
                timestamp: Date.now(),
              });
            }
          } else {
            _silentChunkCount = 0;
          }

          send({ type: "audio_chunk", payload: { data, sampleRate } });
        }
      );

      // Démarrer la capture WASAPI (retourne le sample rate réel)
      const sampleRate = await invoke<number>("start_mic");
      console.log("[JARVIS-AUDIO] Capture WASAPI démarrée — sampleRate:", sampleRate);
    } catch (err) {
      activeRef.current = false;
      const msg = err instanceof Error ? err.message : String(err);
      useJarvisStore.getState().addMessage({
        id: crypto.randomUUID(),
        role: "system",
        content: `⚠ Erreur capture audio : ${msg}`,
        timestamp: Date.now(),
      });
      useJarvisStore.getState().setStatus("error");
      throw err;
    }
  }, [send]);

  const stopCapture = useCallback(async () => {
    activeRef.current = false;
    unlistenRef.current?.();
    unlistenRef.current = null;
    try {
      await invoke("stop_mic");
    } catch (_) {
      // Ignore si déjà arrêté
    }
    send({ type: "mic_stop", payload: {} });
  }, [send]);

  return { startCapture, stopCapture };
}
