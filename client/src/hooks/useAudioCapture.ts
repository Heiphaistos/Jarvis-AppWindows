import { useRef, useCallback, useEffect } from "react";
import { useJarvisStore } from "../stores/jarvisStore";
import { onMicError, startMic, type MicCapture } from "../lib/mic";
import { isTauri } from "../lib/platform";
import type { ClientEvent } from "../types";

// Capture native (Rust/cpal) dans l'application, getUserMedia dans le navigateur.
let _silentChunkCount = 0;
const SILENT_WARNING_THRESHOLD = 16;

export function useAudioCapture(send: (e: ClientEvent) => void) {
  const micRef = useRef<MicCapture | null>(null);
  const activeRef = useRef(false);

  const startCapture = useCallback(async () => {
    if (activeRef.current) return;
    activeRef.current = true;
    _silentChunkCount = 0;

    try {
      micRef.current = await startMic((data, sampleRate) => {

          // Anti-écho : quand JARVIS parle (TTS dans les haut-parleurs), le
          // micro capte sa propre voix — ne pas la lui renvoyer à transcrire.
          const st = useJarvisStore.getState().status;
          if (st === "speaking" || st === "processing") return;

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
                content: isTauri
                  ? "⚠ Microphone silencieux — aucun son détecté. Choisis le bon micro dans Paramètres › Voix."
                  : "⚠ Microphone silencieux — aucun son détecté. Vérifie le micro autorisé pour ce site (icône à gauche de l'adresse).",
                timestamp: Date.now(),
              });
            }
          } else {
            _silentChunkCount = 0;
          }

          send({ type: "audio_chunk", payload: { data, sampleRate } });
      });
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

  // Flux coupé en cours de route (micro débranché, repris par une autre appli) :
  // on le dit, et on remet le bouton micro dans son état réel.
  useEffect(() => onMicError((message) => {
    if (!activeRef.current) return;
    activeRef.current = false;
    const mic = micRef.current;
    micRef.current = null;
    void mic?.stop();
    send({ type: "mic_stop", payload: {} });
    const st = useJarvisStore.getState();
    st.setMicActive(false);
    st.addMessage({
      id: crypto.randomUUID(),
      role: "system",
      content: `⚠ Micro interrompu : ${message}. Vérifie le micro choisi dans Paramètres › Voix.`,
      timestamp: Date.now(),
    });
  }), [send]);

  const stopCapture = useCallback(async () => {
    activeRef.current = false;
    const mic = micRef.current;
    micRef.current = null;
    await mic?.stop();
    send({ type: "mic_stop", payload: {} });
  }, [send]);

  return { startCapture, stopCapture };
}
