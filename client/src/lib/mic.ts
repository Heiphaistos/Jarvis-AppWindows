import { isTauri } from "./platform";

/** Morceau audio mono en float32, tel qu'attendu par le serveur. */
export type ChunkHandler = (data: number[], sampleRate: number) => void;

export interface MicCapture {
  stop(): Promise<void>;
}

// Le serveur ré-échantillonne de toute façon en 16 kHz (Whisper, wake word) :
// côté navigateur on réduit tout de suite, ~3× moins de données sur le réseau.
const TARGET_RATE = 16000;

/**
 * Démarre la capture du micro.
 * - Tauri : capture native (Rust/cpal) — contourne le bug WebView2 MediaStream→AudioContext.
 * - Navigateur (panneau web, version hébergée) : getUserMedia + AudioWorklet.
 */
export function startMic(onChunk: ChunkHandler): Promise<MicCapture> {
  return isTauri ? startNativeMic(onChunk) : startBrowserMic(onChunk);
}

async function startNativeMic(onChunk: ChunkHandler): Promise<MicCapture> {
  const { invoke } = await import("@tauri-apps/api/core");
  const { listen } = await import("@tauri-apps/api/event");
  const unlisten = await listen<{ data: number[]; sampleRate: number }>(
    "jarvis_audio_chunk",
    (e) => onChunk(e.payload.data, e.payload.sampleRate),
  );
  try {
    await invoke<number>("start_mic");
  } catch (err) {
    unlisten();
    throw err;
  }
  return {
    async stop() {
      unlisten();
      try {
        await invoke("stop_mic");
      } catch {
        // déjà arrêté
      }
    },
  };
}

async function startBrowserMic(onChunk: ChunkHandler): Promise<MicCapture> {
  if (!navigator.mediaDevices?.getUserMedia) {
    throw new Error(
      "Micro indisponible : le navigateur l'autorise seulement en HTTPS ou sur 127.0.0.1.",
    );
  }
  const stream = await navigator.mediaDevices.getUserMedia({
    audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true, autoGainControl: true },
  });
  const ctx = new AudioContext();
  try {
    await ctx.audioWorklet.addModule(`${import.meta.env.BASE_URL}audio-processor.js`);
  } catch (err) {
    stream.getTracks().forEach((t) => t.stop());
    void ctx.close();
    throw err;
  }
  const source = ctx.createMediaStreamSource(stream);
  const node = new AudioWorkletNode(ctx, "audio-processor");
  const rate = ctx.sampleRate;
  node.port.onmessage = (e: MessageEvent<number[]>) => {
    const pcm = downsample(e.data, rate, TARGET_RATE);
    onChunk(pcm, rate > TARGET_RATE ? TARGET_RATE : rate);
  };
  source.connect(node);
  // Le worklet doit être relié à la sortie pour tourner ; il n'écrit rien.
  node.connect(ctx.destination);
  // Sans geste de l'utilisateur, le contexte peut rester suspendu jusqu'au premier clic.
  if (ctx.state === "suspended") void ctx.resume();
  return {
    async stop() {
      node.port.onmessage = null;
      source.disconnect();
      node.disconnect();
      stream.getTracks().forEach((t) => t.stop());
      await ctx.close().catch(() => undefined);
    },
  };
}

/** Moyenne par fenêtre (filtre anti-repliement simple) + arrondi : JSON plus léger. */
export function downsample(input: ArrayLike<number>, from: number, to: number): number[] {
  if (from <= to) return Array.from(input, round4);
  const ratio = from / to;
  const out: number[] = new Array(Math.floor(input.length / ratio));
  for (let i = 0; i < out.length; i++) {
    const start = Math.floor(i * ratio);
    const end = Math.min(input.length, Math.floor((i + 1) * ratio));
    let sum = 0;
    for (let j = start; j < end; j++) sum += input[j];
    out[i] = round4(sum / Math.max(1, end - start));
  }
  return out;
}

const round4 = (v: number) => Math.round(v * 10000) / 10000;
