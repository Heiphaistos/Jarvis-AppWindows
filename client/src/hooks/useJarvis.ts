import { useCallback } from "react";
import { useWebSocket } from "./useWebSocket";
import { useAudioCapture } from "./useAudioCapture";
import { useJarvisStore } from "../stores/jarvisStore";

export function useJarvis() {
  const { send } = useWebSocket();
  const isMicActive = useJarvisStore((s) => s.isMicActive);
  const status = useJarvisStore((s) => s.status);
  const { startCapture, stopCapture } = useAudioCapture(send);

  const sendText = useCallback(
    (text: string) => {
      if (!text.trim()) return;
      send({ type: "text_query", payload: { text } });
    },
    [send]
  );

  const toggleMic = useCallback(async () => {
    if (isMicActive) {
      stopCapture();
      useJarvisStore.getState().setMicActive(false);
    } else {
      await startCapture();
      useJarvisStore.getState().setMicActive(true);
    }
  }, [isMicActive, startCapture, stopCapture]);

  return { sendText, toggleMic, isMicActive, status };
}
