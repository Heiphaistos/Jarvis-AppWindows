import { useRef, useCallback } from "react";
import { useJarvisStore } from "../stores/jarvisStore";
import type { ClientEvent } from "../types";

const SAMPLE_RATE = 16000;
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
          sampleRate: SAMPLE_RATE,
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
        },
      });
      const ctx = new AudioContext({ sampleRate: SAMPLE_RATE });
      contextRef.current = ctx;
      const source = ctx.createMediaStreamSource(streamRef.current);
      const processor = ctx.createScriptProcessor(CHUNK_SIZE, 1, 1);
      processor.onaudioprocess = (e) => {
        const data = Array.from(e.inputBuffer.getChannelData(0));
        send({ type: "audio_chunk", payload: { data, sampleRate: SAMPLE_RATE } });
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
