import { useEffect, useRef } from "react";
import { useJarvisStore } from "../../stores/jarvisStore";
import { drawFrame } from "../../lib/audioVisualizer";

export function VoiceVisualizer() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const animRef = useRef<number>(0);
  const status = useJarvisStore((s) => s.status);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const audioCtx = new AudioContext();
    const analyser = audioCtx.createAnalyser();
    analyser.fftSize = 256;

    const loop = () => {
      drawFrame({ canvas, analyser, status });
      animRef.current = requestAnimationFrame(loop);
    };
    loop();

    return () => {
      cancelAnimationFrame(animRef.current);
      audioCtx.close();
    };
  }, [status]);

  return (
    <canvas
      ref={canvasRef}
      width={260}
      height={260}
      className="rounded-full"
      style={{ filter: "drop-shadow(0 0 20px #00d4ff66)" }}
    />
  );
}
