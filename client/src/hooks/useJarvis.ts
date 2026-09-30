import { useCallback } from "react";
import { useWebSocket } from "./useWebSocket";
import { useAudioCapture } from "./useAudioCapture";
import { useWakeWord } from "./useWakeWord";
import { useJarvisStore } from "../stores/jarvisStore";

export function useJarvis() {
  const { send } = useWebSocket();
  const isMicActive = useJarvisStore((s) => s.isMicActive);
  const status = useJarvisStore((s) => s.status);
  const { startCapture, stopCapture } = useAudioCapture(send);

  const activateMic = useCallback(async () => {
    try {
      await startCapture();
      useJarvisStore.getState().setMicActive(true);
    } catch {
      useJarvisStore.getState().setMicActive(false);
    }
  }, [startCapture]);

  // Mode veille « Hey Jarvis » → active le micro à la détection
  useWakeWord(send, activateMic);

  const sendText = useCallback(
    (text: string) => {
      if (!text.trim()) return;
      send({
        type: "text_query",
        payload: { text, council: useJarvisStore.getState().councilEnabled },
      });
    },
    [send]
  );

  const toggleMic = useCallback(async () => {
    if (isMicActive) {
      stopCapture();
      useJarvisStore.getState().setMicActive(false);
    } else {
      await activateMic();
    }
  }, [isMicActive, activateMic, stopCapture]);

  /** Mode LIVE : conversation vocale temps réel avec Gemini (micro ouvert en continu). */
  const toggleLive = useCallback(async () => {
    const st = useJarvisStore.getState();
    if (st.liveActive) {
      send({ type: "live_stop", payload: {} });
      stopCapture();
      st.setMicActive(false);
      return;
    }
    const voice = st.selectedVoice.startsWith("gemini:") ? st.selectedVoice.slice(7) : "Charon";
    send({ type: "live_start", payload: { voice } });
    if (!st.isMicActive) await activateMic();
  }, [send, stopCapture, activateMic]);

  return { sendText, toggleMic, toggleLive, isMicActive, status };
}
