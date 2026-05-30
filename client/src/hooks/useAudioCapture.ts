import { useRef, useCallback } from "react";
import { useJarvisStore } from "../stores/jarvisStore";
import type { ClientEvent } from "../types";

const CHUNK_SIZE = 4096;
// Détecte si les chunks audio sont silencieux (permission Windows manquante)
let _silentChunkCount = 0;
const SILENT_WARNING_THRESHOLD = 16; // ~2s de silence → avertissement

export function useAudioCapture(send: (e: ClientEvent) => void) {
  const streamRef = useRef<MediaStream | null>(null);
  const contextRef = useRef<AudioContext | null>(null);
  const processorRef = useRef<ScriptProcessorNode | null>(null);

  const startCapture = useCallback(async () => {
    if (streamRef.current) return;
    _silentChunkCount = 0;
    try {
      streamRef.current = await navigator.mediaDevices.getUserMedia({
        audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true },
      });
      const ctx = new AudioContext();
      contextRef.current = ctx;
      if (ctx.state === "suspended") await ctx.resume();
      const actualSampleRate = ctx.sampleRate;
      const source = ctx.createMediaStreamSource(streamRef.current);
      const processor = ctx.createScriptProcessor(CHUNK_SIZE, 1, 1);

      processor.onaudioprocess = (e) => {
        const raw = e.inputBuffer.getChannelData(0);
        // Détecter micro silencieux (Windows privacy bloqué)
        let rms = 0;
        for (let i = 0; i < raw.length; i++) rms += raw[i] * raw[i];
        rms = Math.sqrt(rms / raw.length);
        if (rms < 0.0001) {
          _silentChunkCount++;
          if (_silentChunkCount === SILENT_WARNING_THRESHOLD) {
            useJarvisStore.getState().addMessage({
              id: crypto.randomUUID(),
              role: "system",
              content: "⚠ Microphone silencieux — vérifie Windows : Paramètres → Confidentialité → Microphone → Autoriser les apps de bureau à accéder au microphone → ACTIVÉ",
              timestamp: Date.now(),
            });
          }
        } else {
          _silentChunkCount = 0;
        }
        const data = Array.from(raw);
        send({ type: "audio_chunk", payload: { data, sampleRate: actualSampleRate } });
      };

      source.connect(processor);
      processor.connect(ctx.destination);
      processorRef.current = processor;
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      useJarvisStore.getState().addMessage({
        id: crypto.randomUUID(),
        role: "system",
        content: `⚠ Accès microphone refusé : ${msg}. Va dans Windows Paramètres → Confidentialité → Microphone.`,
        timestamp: Date.now(),
      });
      useJarvisStore.getState().setStatus("error");
      throw err;
    }
  }, [send]);

  const stopCapture = useCallback(() => {
    processorRef.current?.disconnect();
    contextRef.current?.close();
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    contextRef.current = null;
    processorRef.current = null;
    send({ type: "mic_stop", payload: {} });
  }, [send]);

  return { startCapture, stopCapture };
}
