export interface VisualizerOptions {
  canvas: HTMLCanvasElement;
  analyser: AnalyserNode;
  status: "idle" | "listening" | "processing" | "speaking" | "error";
  time: number;
  ttsAnalyser?: AnalyserNode | null;
}

const STATUS_COLORS: Record<string, [string, string]> = {
  idle:       ["#00d4ff", "#0088aa"],
  listening:  ["#00ff88", "#00aa55"],
  processing: ["#ffaa00", "#ff6600"],
  speaking:   ["#00d4ff", "#8800ff"],
  error:      ["#ff3333", "#aa0000"],
};

// Reuse frequency buffers per analyser — avoids allocation every frame
const _freqBuffers = new WeakMap<AnalyserNode, Uint8Array>();
function getFreqBuffer(analyser: AnalyserNode): Uint8Array {
  let buf = _freqBuffers.get(analyser);
  if (!buf) {
    buf = new Uint8Array(analyser.frequencyBinCount);
    _freqBuffers.set(analyser, buf);
  }
  return buf;
}

function hex(ctx: CanvasRenderingContext2D, cx: number, cy: number, r: number, color: string, alpha: number) {
  ctx.save();
  ctx.globalAlpha = alpha;
  ctx.beginPath();
  for (let i = 0; i < 6; i++) {
    const a = (i * Math.PI) / 3 - Math.PI / 6;
    i === 0 ? ctx.moveTo(cx + r * Math.cos(a), cy + r * Math.sin(a))
             : ctx.lineTo(cx + r * Math.cos(a), cy + r * Math.sin(a));
  }
  ctx.closePath();
  ctx.strokeStyle = color;
  ctx.lineWidth = 1;
  ctx.stroke();
  ctx.restore();
}

export function drawFrame({ canvas, analyser, status, time, ttsAnalyser = null }: VisualizerOptions) {
  const ctx = canvas.getContext("2d")!;
  const W = canvas.width;
  const H = canvas.height;
  const cx = W / 2;
  const cy = H / 2;
  const [col, col2] = STATUS_COLORS[status] ?? STATUS_COLORS.idle;
  const t = time * 0.001;

  // Quand SPEAKING, utilise les fréquences TTS réelles
  const activeAnalyser = status === "speaking" && ttsAnalyser ? ttsAnalyser : analyser;
  const bufLen = activeAnalyser.frequencyBinCount;
  const rawData = getFreqBuffer(activeAnalyser);
  activeAnalyser.getByteFrequencyData(rawData);
  const rawAvg = rawData.slice(0, 80).reduce((s, v) => s + v, 0) / 80 / 255;

  const idlePulse = status === "idle" || rawAvg < 0.02;
  const syntheticBase = idlePulse
    ? Math.abs(Math.sin(t * 1.1)) * 0.25 + Math.abs(Math.sin(t * 0.4 + 1)) * 0.12
    : 0;
  const data = idlePulse
    ? new Uint8Array(bufLen).map((_, i) => {
        const wave = Math.sin(t * 2.2 + (i / bufLen) * Math.PI * 4) * 0.5 + 0.5;
        const pulse = Math.abs(Math.sin(t * 1.1)) * 0.6;
        return Math.round((wave * pulse * 0.5 + syntheticBase * 0.3) * 180);
      })
    : rawData;
  const avgAmp = idlePulse ? syntheticBase : rawAvg;

  ctx.clearRect(0, 0, W, H);

  const bg = ctx.createRadialGradient(cx, cy, 0, cx, cy, cx);
  bg.addColorStop(0, `${col}18`);
  bg.addColorStop(0.6, `${col}06`);
  bg.addColorStop(1, "transparent");
  ctx.fillStyle = bg;
  ctx.fillRect(0, 0, W, H);

  for (let ring = 1; ring <= 4; ring++) {
    const r = ring * 28 + Math.sin(t * 0.5 + ring) * 2;
    hex(ctx, cx, cy, r, col, 0.06 + ring * 0.02);
  }

  for (let arc = 0; arc < 3; arc++) {
    const baseAngle = t * (0.4 + arc * 0.15) + (arc * Math.PI * 2) / 3;
    const r = 95 + arc * 8;
    ctx.save();
    ctx.globalAlpha = 0.25 + avgAmp * 0.3;
    ctx.beginPath();
    ctx.arc(cx, cy, r, baseAngle, baseAngle + Math.PI * 0.6);
    ctx.strokeStyle = arc === 1 ? col2 : col;
    ctx.lineWidth = arc === 1 ? 1 : 0.5;
    ctx.stroke();
    ctx.restore();
  }

  const mainR = 82 + avgAmp * 12;
  const ringGrd = ctx.createLinearGradient(cx - mainR, cy, cx + mainR, cy);
  ringGrd.addColorStop(0, `${col}00`);
  ringGrd.addColorStop(0.5, col);
  ringGrd.addColorStop(1, `${col}00`);
  ctx.save();
  ctx.globalAlpha = 0.7 + avgAmp * 0.3;
  ctx.beginPath();
  ctx.arc(cx, cy, mainR, 0, Math.PI * 2);
  ctx.strokeStyle = ringGrd;
  ctx.lineWidth = 1.5;
  ctx.stroke();
  ctx.restore();

  const innerGrd = ctx.createRadialGradient(cx, cy, 0, cx, cy, mainR);
  innerGrd.addColorStop(0, `${col}22`);
  innerGrd.addColorStop(0.5, `${col}08`);
  innerGrd.addColorStop(1, "transparent");
  ctx.fillStyle = innerGrd;
  ctx.beginPath();
  ctx.arc(cx, cy, mainR, 0, Math.PI * 2);
  ctx.fill();

  const bars = 72;
  for (let i = 0; i < bars; i++) {
    const angle = (i / bars) * Math.PI * 2 - Math.PI / 2;
    const amp = data[Math.floor((i / bars) * bufLen)] / 255;
    const barLen = 4 + amp * 36;
    const x1 = cx + Math.cos(angle) * (mainR + 3);
    const y1 = cy + Math.sin(angle) * (mainR + 3);
    const x2 = cx + Math.cos(angle) * (mainR + 3 + barLen);
    const y2 = cy + Math.sin(angle) * (mainR + 3 + barLen);
    ctx.save();
    ctx.globalAlpha = 0.3 + amp * 0.7;
    ctx.beginPath();
    ctx.moveTo(x1, y1);
    ctx.lineTo(x2, y2);
    ctx.strokeStyle = amp > 0.6 ? col2 : col;
    ctx.lineWidth = amp > 0.5 ? 2 : 1;
    ctx.stroke();
    ctx.restore();
  }

  const innerBars = 36;
  for (let i = 0; i < innerBars; i++) {
    const angle = (i / innerBars) * Math.PI * 2 - Math.PI / 2;
    const amp = data[Math.floor((i / innerBars) * bufLen * 0.3)] / 255;
    const barLen = amp * (mainR * 0.55);
    const x1 = cx + Math.cos(angle) * 12;
    const y1 = cy + Math.sin(angle) * 12;
    const x2 = cx + Math.cos(angle) * (12 + barLen);
    const y2 = cy + Math.sin(angle) * (12 + barLen);
    ctx.save();
    ctx.globalAlpha = amp * 0.5;
    ctx.beginPath();
    ctx.moveTo(x1, y1);
    ctx.lineTo(x2, y2);
    ctx.strokeStyle = col;
    ctx.lineWidth = 1;
    ctx.stroke();
    ctx.restore();
  }

  const coreR = 12 + avgAmp * 5;
  hex(ctx, cx, cy, coreR, col, 0.8);

  const coreGrd = ctx.createRadialGradient(cx, cy, 0, cx, cy, coreR);
  coreGrd.addColorStop(0, `${col}cc`);
  coreGrd.addColorStop(0.5, `${col}44`);
  coreGrd.addColorStop(1, "transparent");
  ctx.fillStyle = coreGrd;
  ctx.beginPath();
  ctx.arc(cx, cy, coreR, 0, Math.PI * 2);
  ctx.fill();

  for (let i = 0; i < 24; i++) {
    const angle = (i / 24) * Math.PI * 2;
    const len = i % 6 === 0 ? 8 : i % 3 === 0 ? 5 : 3;
    const x1 = cx + Math.cos(angle) * (mainR - 1);
    const y1 = cy + Math.sin(angle) * (mainR - 1);
    const x2 = cx + Math.cos(angle) * (mainR - 1 - len);
    const y2 = cy + Math.sin(angle) * (mainR - 1 - len);
    ctx.save();
    ctx.globalAlpha = 0.5;
    ctx.beginPath();
    ctx.moveTo(x1, y1);
    ctx.lineTo(x2, y2);
    ctx.strokeStyle = col;
    ctx.lineWidth = i % 6 === 0 ? 1.5 : 0.5;
    ctx.stroke();
    ctx.restore();
  }

  const scanAngle = t * 1.2;
  ctx.save();
  ctx.globalAlpha = 0.15;
  const scanGrd = ctx.createLinearGradient(
    cx, cy,
    cx + Math.cos(scanAngle) * (mainR + 40),
    cy + Math.sin(scanAngle) * (mainR + 40)
  );
  scanGrd.addColorStop(0, col);
  scanGrd.addColorStop(1, "transparent");
  ctx.beginPath();
  ctx.moveTo(cx, cy);
  ctx.lineTo(cx + Math.cos(scanAngle) * (mainR + 40), cy + Math.sin(scanAngle) * (mainR + 40));
  ctx.strokeStyle = scanGrd;
  ctx.lineWidth = 20;
  ctx.stroke();
  ctx.restore();
}
