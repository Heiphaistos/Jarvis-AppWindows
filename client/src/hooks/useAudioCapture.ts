import { useRef, useCallback } from "react";
import { useJarvisStore } from "../stores/jarvisStore";
import type { ClientEvent } from "../types";

// Laisse le navigateur choisir le sample rate natif (WebView2 = 48000 Hz en général)
// Le serveur reçoit le vrai rate et resamplé à 16kHz côté Python
const CHUNK_SIZE = 4096;

export function useAudioCapture(send: (e: ClientEvent) => void) {
  const streamRef = useRef<MediaStream | null>(null);
  const contextRef = useRef<AudioContext | null>(null);
  const processorRef = useRef<ScriptProcessorNode | null>(null);

  const startCapture = useCallback(async () => {
    if (streamRef.current) return;
    try {
      streamRef.current = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
        },
      });
      // Pas de sampleRate forcé — AudioContext utilise le rate natif du device
      const ctx = new AudioContext();
      contextRef.current = ctx;
      const actualSampleRate = ctx.sampleRate; // 44100 ou 48000 selon WebView2
      const source = ctx.createMediaStreamSource(streamRef.current);
      const processor = ctx.createScriptProcessor(CHUNK_SIZE, 1, 1);
      processor.onaudioprocess = (e) => {
        const data = Array.from(e.inputBuffer.getChannelData(0));
        // Envoie le vrai sample rate pour que le serveur puisse resampler
        send({ type: "audio_chunk", payload: { data, sampleRate: actualSampleRate } });
      };
      source.connect(processor);
      processor.connect(ctx.destination);
      processorRef.current = processor;
    } catch (err) {
      console.error("Microphone access denied:", err);
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
