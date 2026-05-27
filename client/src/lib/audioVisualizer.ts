export interface VisualizerOptions {
  canvas: HTMLCanvasElement;
  analyser: AnalyserNode;
  status: "idle" | "listening" | "processing" | "speaking" | "error";
}

const STATUS_COLORS: Record<string, string> = {
  idle: "#00d4ff",
  listening: "#00ff88",
  processing: "#ffaa00",
  speaking: "#00d4ff",
  error: "#ff4444",
};

export function drawFrame({ canvas, analyser, status }: VisualizerOptions) {
  const ctx = canvas.getContext("2d")!;
  const { width: W, height: H } = canvas;
  const cx = W / 2;
  const cy = H / 2;
  const color = STATUS_COLORS[status] ?? "#00d4ff";
  const bufLen = analyser.frequencyBinCount;
  const data = new Uint8Array(bufLen);
  analyser.getByteFrequencyData(data);

  ctx.clearRect(0, 0, W, H);

  const bg = ctx.createRadialGradient(cx, cy, 0, cx, cy, cy);
  bg.addColorStop(0, "rgba(0,40,80,0.3)");
  bg.addColorStop(1, "transparent");
  ctx.fillStyle = bg;
  ctx.fillRect(0, 0, W, H);

  const avgAmp =
    data.slice(0, 64).reduce((s, v) => s + v, 0) / 64 / 255;
  const baseR = 60;
  const pulseR = baseR + avgAmp * 30;

  const grd = ctx.createRadialGradient(cx, cy, 0, cx, cy, pulseR);
  grd.addColorStop(0, `${color}33`);
  grd.addColorStop(1, "transparent");
  ctx.beginPath();
  ctx.arc(cx, cy, pulseR, 0, Math.PI * 2);
  ctx.fillStyle = grd;
  ctx.fill();

  ctx.beginPath();
  ctx.arc(cx, cy, baseR, 0, Math.PI * 2);
  ctx.strokeStyle = `${color}88`;
  ctx.lineWidth = 2;
  ctx.stroke();

  const bars = 64;
  for (let i = 0; i < bars; i++) {
    const angle = (i / bars) * Math.PI * 2 - Math.PI / 2;
    const amp = data[Math.floor((i / bars) * bufLen)] / 255;
    const barLen = baseR * 0.6 * amp;
    const x1 = cx + Math.cos(angle) * (baseR + 4);
    const y1 = cy + Math.sin(angle) * (baseR + 4);
    const x2 = cx + Math.cos(angle) * (baseR + 4 + barLen);
    const y2 = cy + Math.sin(angle) * (baseR + 4 + barLen);
    ctx.beginPath();
    ctx.moveTo(x1, y1);
    ctx.lineTo(x2, y2);
    ctx.strokeStyle = color;
    ctx.lineWidth = 2;
    ctx.globalAlpha = 0.7 + amp * 0.3;
    ctx.stroke();
  }
  ctx.globalAlpha = 1;
}
