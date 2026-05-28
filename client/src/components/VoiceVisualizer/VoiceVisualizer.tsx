import { useEffect, useRef } from "react";
import { useJarvisStore } from "../../stores/jarvisStore";
import { drawFrame } from "../../lib/audioVisualizer";

export function VoiceVisualizer() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const animRef = useRef<number>(0);
  const startRef = useRef<number>(0);
  const status = useJarvisStore((s) => s.status);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const audioCtx = new AudioContext();
    const analyser = audioCtx.createAnalyser();
    analyser.fftSize = 512;
    startRef.current = performance.now();

    const loop = (now: number) => {
      drawFrame({ canvas, analyser, status, time: now - startRef.current });
      animRef.current = requestAnimationFrame(loop);
    };
    animRef.current = requestAnimationFrame(loop);

    return () => {
      cancelAnimationFrame(animRef.current);
      audioCtx.close();
    };
  }, [status]);

  return (
    <div className="relative">
      <canvas
        ref={canvasRef}
        width={300}
        height={300}
        style={{
          filter: "drop-shadow(0 0 24px #00d4ff55) drop-shadow(0 0 8px #00d4ff33)",
        }}
      />
    </div>
  );
}
