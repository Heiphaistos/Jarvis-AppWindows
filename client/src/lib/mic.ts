import { isTauri } from "./platform";

/** Morceau audio mono en float32, tel qu'attendu par le serveur. */
export type ChunkHandler = (data: number[], sampleRate: number) => void;

export interface MicCapture {
  stop(): Promise<void>;
}

export interface MicDevice {
  /** Nom du périphérique (application) ou deviceId (navigateur). */
  id: string;
  label: string;
  isDefault: boolean;
}

// Le serveur ré-échantillonne de toute façon en 16 kHz (Whisper, wake word) :
// on réduit tout de suite, ~3× moins de données sur le réseau et l'IPC.
const TARGET_RATE = 16000;
const DEVICE_KEY = "jarvis_mic_device";

/*
 * Un seul flux micro, partagé entre la veille « Hey Jarvis » et l'écoute.
 * Auparavant chacun ouvrait et fermait le micro de son côté : en cliquant sur
 * le micro pendant la veille, l'arrêt de la veille (stop_mic) coupait le flux
 * que l'écoute venait d'ouvrir. Le flux ne s'arrête plus que lorsque plus
 * personne ne l'utilise.
 */
const listeners = new Set<ChunkHandler>();
const errorListeners = new Set<(message: string) => void>();
let running: MicCapture | null = null;
let opening: Promise<void> | null = null;

function dispatch(data: ArrayLike<number>, rate: number) {
  const pcm = downsample(data, rate, TARGET_RATE);
  const outRate = rate > TARGET_RATE ? TARGET_RATE : rate;
  listeners.forEach((fn) => fn(pcm, outRate));
}

function reportError(message: string) {
  errorListeners.forEach((fn) => fn(message));
}

/** Prévient quand le flux micro tombe (micro débranché, périphérique repris…). */
export function onMicError(fn: (message: string) => void): () => void {
  errorListeners.add(fn);
  return () => errorListeners.delete(fn);
}

function selectedDevice(): string {
  try {
    return localStorage.getItem(DEVICE_KEY) || "";
  } catch {
    return "";
  }
}

async function ensureRunning(): Promise<void> {
  if (running) return;
  if (!opening) {
    opening = (isTauri ? openNativeMic(selectedDevice()) : openBrowserMic(selectedDevice()))
      .then((capture) => {
        running = capture;
      })
      .finally(() => {
        opening = null;
      });
  }
  await opening;
  // Tout le monde est parti pendant l'ouverture : on referme.
  if (listeners.size === 0) await shutdown();
}

async function shutdown(): Promise<void> {
  if (opening) await opening.catch(() => undefined);
  const capture = running;
  running = null;
  await capture?.stop();
}

/**
 * Démarre la capture du micro.
 * - Application (Tauri) : capture native (Rust/cpal) — contourne le bug WebView2 MediaStream→AudioContext.
 * - Navigateur (panneau web, version hébergée) : getUserMedia + AudioWorklet.
 */
export async function startMic(onChunk: ChunkHandler): Promise<MicCapture> {
  listeners.add(onChunk);
  try {
    await ensureRunning();
  } catch (err) {
    listeners.delete(onChunk);
    throw err;
  }
  let stopped = false;
  return {
    async stop() {
      if (stopped) return;
      stopped = true;
      listeners.delete(onChunk);
      if (listeners.size === 0) await shutdown();
    },
  };
}

/** Rouvre le micro avec le périphérique choisi, si une capture est en cours. */
export async function restartMic(): Promise<void> {
  if (!running && !opening) return;
  await shutdown();
  if (listeners.size > 0) await ensureRunning();
}

/** Micros disponibles. Dans le navigateur, les noms n'apparaissent qu'après
 *  une première autorisation du micro. */
export async function listMics(): Promise<MicDevice[]> {
  if (isTauri) {
    const { invoke } = await import("@tauri-apps/api/core");
    const mics = await invoke<{ name: string; is_default: boolean }[]>("list_mics");
    return mics.map((m) => ({ id: m.name, label: m.name, isDefault: m.is_default }));
  }
  if (!navigator.mediaDevices?.enumerateDevices) return [];
  const devices = await navigator.mediaDevices.enumerateDevices();
  return devices
    .filter((d) => d.kind === "audioinput" && d.deviceId !== "default" && d.deviceId !== "communications")
    .map((d, i) => ({ id: d.deviceId, label: d.label || `Micro ${i + 1}`, isDefault: false }));
}

async function openNativeMic(device: string): Promise<MicCapture> {
  const { invoke } = await import("@tauri-apps/api/core");
  const { listen } = await import("@tauri-apps/api/event");
  const unlisten = await listen<{ data: number[]; sampleRate: number }>(
    "jarvis_audio_chunk",
    (e) => dispatch(e.payload.data, e.payload.sampleRate),
  );
  const unlistenError = await listen<string>("jarvis_audio_error", (e) => reportError(String(e.payload)));
  try {
    await invoke<number>("start_mic", { device: device || null });
  } catch (err) {
    unlisten();
    unlistenError();
    throw err instanceof Error ? err : new Error(String(err));
  }
  return {
    async stop() {
      unlisten();
      unlistenError();
      try {
        await invoke("stop_mic");
      } catch {
        // déjà arrêté
      }
    },
  };
}

async function openBrowserMic(device: string): Promise<MicCapture> {
  if (!navigator.mediaDevices?.getUserMedia) {
    throw new Error(
      "Micro indisponible : le navigateur l'autorise seulement en HTTPS ou sur 127.0.0.1.",
    );
  }
  const constraints: MediaTrackConstraints = {
    channelCount: 1, echoCancellation: true, noiseSuppression: true, autoGainControl: true,
  };
  let stream: MediaStream;
  try {
    stream = await navigator.mediaDevices.getUserMedia({
      audio: device ? { ...constraints, deviceId: { exact: device } } : constraints,
    });
  } catch (err) {
    // Micro choisi débranché : on retombe sur le micro par défaut.
    if (!device) throw err;
    stream = await navigator.mediaDevices.getUserMedia({ audio: constraints });
  }
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
  node.port.onmessage = (e: MessageEvent<number[]>) => dispatch(e.data, rate);
  source.connect(node);
  // Le worklet doit être relié à la sortie pour tourner ; il n'écrit rien.
  node.connect(ctx.destination);
  // Sans geste de l'utilisateur, le contexte peut rester suspendu jusqu'au premier clic.
  if (ctx.state === "suspended") void ctx.resume();
  const track = stream.getAudioTracks()[0];
  if (track) track.onended = () => reportError("Le micro a été déconnecté.");
  return {
    async stop() {
      node.port.onmessage = null;
      if (track) track.onended = null;
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
