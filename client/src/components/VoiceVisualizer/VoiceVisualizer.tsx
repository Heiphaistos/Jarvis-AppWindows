import { useEffect, useRef } from "react";
import { motion } from "framer-motion";
import { useJarvisStore, getTtsAnalyser } from "../../stores/jarvisStore";
import { drawFrame } from "../../lib/audioVisualizer";

export function VoiceVisualizer() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const animRef = useRef<number>(0);
  const startRef = useRef<number>(0);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const audioCtxRef = useRef<AudioContext | null>(null);
  const status = useJarvisStore((s) => s.status);
  const isThinking = status === "processing";

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    // Crée un AudioContext local pour l'analyser micro (silence = idle/listening)
    const audioCtx = new AudioContext();
    audioCtxRef.current = audioCtx;
    const analyser = audioCtx.createAnalyser();
    analyser.fftSize = 512;
    analyserRef.current = analyser;
    startRef.current = performance.now();

    const loop = (now: number) => {
      drawFrame({
        canvas,
        analyser,
        status,
        time: now - startRef.current,
        ttsAnalyser: getTtsAnalyser(),
      });
      animRef.current = requestAnimationFrame(loop);
    };
    animRef.current = requestAnimationFrame(loop);

    return () => {
      cancelAnimationFrame(animRef.current);
      void audioCtx.close();
    };
  }, [status]);

  return (
    <div className="relative w-48 h-48">
      <canvas
        ref={canvasRef}
        width={192}
        height={192}
        className="absolute inset-0"
        style={{
          filter: "drop-shadow(0 0 24px #00d4ff55) drop-shadow(0 0 8px #00d4ff33)",
        }}
      />

      {/* Anneau rotatif THINKING */}
      {isThinking && (
        <>
          <motion.div
            className="absolute inset-0 rounded-full pointer-events-none"
            style={{
              border: "2px solid transparent",
              borderTopColor: "#ffaa00",
              borderRightColor: "#ffaa0066",
            }}
            animate={{ rotate: 360 }}
            transition={{ duration: 1.2, repeat: Infinity, ease: "linear" }}
          />
          <motion.div
            className="absolute inset-2 rounded-full pointer-events-none"
            style={{
              border: "1px solid transparent",
              borderBottomColor: "#ffaa00aa",
            }}
            animate={{ rotate: -360 }}
            transition={{ duration: 2, repeat: Infinity, ease: "linear" }}
          />
        </>
      )}
    </div>
  );
}
