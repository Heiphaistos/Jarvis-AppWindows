import { useEffect, useState } from "react";
import { MicOff, AlertTriangle, Volume2, VolumeX, Trash2 } from "lucide-react";
import { useJarvisStore } from "../../stores/jarvisStore";

const API = "http://127.0.0.1:8765";
const CIRC = 201; // 2πr, r = 32

/** Infos matériel + nombre de souvenirs, relus à chaque (re)connexion. */
function useServerInfo() {
  const isConnected = useJarvisStore((s) => s.isConnected);
  const memoryVersion = useJarvisStore((s) => s.memoryVersion);
  const [hw, setHw] = useState({ gpu: "—", vram: "—" });
  const [memCount, setMemCount] = useState<number | null>(null);
  useEffect(() => {
    if (!isConnected) return;
    fetch(`${API}/api/system_info`)
      .then((r) => r.json())
      .then((d: { info: string }) => {
        const gpu = d.info.match(/GPU: ([^|]+)/);
        const vram = d.info.match(/VRAM: (\d+)\/(\d+)/);
        setHw({ gpu: gpu ? gpu[1].trim() : "—", vram: vram ? `${(+vram[2] / 1024).toFixed(1)} Go` : "—" });
      })
      .catch(() => {});
  }, [isConnected]);
  useEffect(() => {
    if (!isConnected) return;
    fetch(`${API}/api/memories/count`)
      .then((r) => r.json())
      .then((d: { count: number }) => setMemCount(d.count))
      .catch(() => {});
  }, [isConnected, memoryVersion]);
  return { hw, memCount };
}

function loadColor(v: number) {
  return v > 88 ? "var(--red)" : v > 70 ? "var(--amber)" : "var(--accent)";
}

function Gauge({ label, value }: { label: string; value: number | null }) {
  const v = Math.min(Math.max(value ?? 0, 0), 100);
  return (
    <div className="gauge" style={{ "--gc": loadColor(v) } as React.CSSProperties}>
      <svg viewBox="0 0 80 80" aria-hidden>
        <circle className="g-bg" cx="40" cy="40" r="32" />
        <circle className="g-val" cx="40" cy="40" r="32" style={{ strokeDashoffset: CIRC * (1 - v / 100) }} />
      </svg>
      <b>{value === null ? "—" : `${Math.round(v)}%`}</b>
      <span>{label}</span>
    </div>
  );
}

export function Gauges({ row = false }: { row?: boolean }) {
  const m = useJarvisStore((s) => s.metrics);
  return (
    <div className={`gauges${row ? " row" : ""}`}>
      <Gauge label="CPU" value={m.cpu} />
      <Gauge label="RAM" value={m.ram} />
      <Gauge label="GPU" value={m.gpu} />
      <Gauge label="VRAM" value={m.vram} />
    </div>
  );
}

function Warnings() {
  const isConnected = useJarvisStore((s) => s.isConnected);
  const stt = useJarvisStore((s) => s.sttAvailable);
  const llm = useJarvisStore((s) => s.llmAvailable);
  if (!isConnected) return null;
  return (
    <>
      {!stt && <div className="warn"><MicOff />Micro indisponible : modèle Whisper non chargé.</div>}
      {!llm && <div className="warn err"><AlertTriangle />Cerveau local absent : utilisez un cerveau cloud ou AUTO.</div>}
    </>
  );
}

export function VoiceToggle() {
  const tts = useJarvisStore((s) => s.ttsEnabled);
  const setTts = useJarvisStore((s) => s.setTtsEnabled);
  const wsSend = useJarvisStore((s) => s.wsSend);
  const toggle = () => {
    setTts(!tts);
    wsSend?.({ type: "set_tts", payload: { enabled: !tts } });
  };
  return (
    <button className={`btn btn-ghost btn-sm btn-block${tts ? "" : " is-off"}`} onClick={toggle}>
      {tts ? <Volume2 /> : <VolumeX />}
      {tts ? "Voix active" : "Voix coupée"}
    </button>
  );
}

const LEVEL_LABEL = { instant: "INSTANTANÉ", standard: "STANDARD", deep: "PROFOND" } as const;

function BrainList() {
  const isConnected = useJarvisStore((s) => s.isConnected);
  const providerLabel = useJarvisStore((s) => s.providerLabel);
  const providerModel = useJarvisStore((s) => s.providerModel);
  const lastBrain = useJarvisStore((s) => s.lastBrain);
  const council = useJarvisStore((s) => s.councilEnabled);
  const live = useJarvisStore((s) => s.liveActive);
  const model = lastBrain?.model || providerModel || providerLabel;
  const ttft = lastBrain?.ttftMs;
  const ttftColor = ttft === undefined ? undefined : ttft < 600 ? "var(--green)" : ttft < 1500 ? "var(--amber)" : "var(--red)";
  return (
    <dl className="rail-list">
      <div><dt>Cerveau</dt><dd title={lastBrain?.label || providerLabel}>{lastBrain?.label || providerLabel}</dd></div>
      <div><dt>Modèle</dt><dd title={model}>{model}</dd></div>
      {lastBrain && <div><dt>Niveau</dt><dd>{LEVEL_LABEL[lastBrain.level]}</dd></div>}
      {ttft !== undefined && <div><dt>1er mot</dt><dd style={{ color: ttftColor }}>{ttft} ms</dd></div>}
      <div><dt>Mode</dt><dd style={live ? { color: "var(--red)" } : undefined}>{live ? "LIVE" : council ? "CONSEIL" : "AUTO"}</dd></div>
      <div><dt>Liaison</dt><dd style={{ color: isConnected ? "var(--green)" : "var(--red)" }}>{isConnected ? "WS · 8765" : "COUPÉE"}</dd></div>
    </dl>
  );
}

/** Rail gauche de la disposition HUD — repris de la démo du site. */
export function TelemetryRail() {
  const { hw, memCount } = useServerInfo();
  const clearMessages = useJarvisStore((s) => s.clearMessages);
  return (
    <aside className="rail panel" aria-label="Télémétrie">
      <h2 className="rail-title">Système</h2>
      <Gauges />
      <h2 className="rail-title">Matériel</h2>
      <dl className="rail-list">
        <div><dt>GPU</dt><dd title={hw.gpu}>{hw.gpu}</dd></div>
        <div><dt>VRAM</dt><dd>{hw.vram}</dd></div>
      </dl>
      <h2 className="rail-title">Cerveau</h2>
      <BrainList />
      <h2 className="rail-title">Mémoire</h2>
      <dl className="rail-list">
        <div><dt>Souvenirs</dt><dd>{memCount ?? "—"}</dd></div>
      </dl>
      <Warnings />
      <div className="rail-foot">
        <VoiceToggle />
        <button className="btn btn-danger btn-sm btn-block" onClick={clearMessages}>
          <Trash2 />Effacer l'historique
        </button>
      </div>
    </aside>
  );
}

/** Pied du panneau Duo : jauges en ligne + cerveau + voix. */
export function SideFooter() {
  return (
    <div className="side-foot">
      <Gauges row />
      <BrainList />
      <Warnings />
      <VoiceToggle />
    </div>
  );
}

/** Ligne de puces (Immersif, Compact) : charge + cerveau, d'un coup d'œil. */
export function StatChips() {
  const m = useJarvisStore((s) => s.metrics);
  const providerModel = useJarvisStore((s) => s.lastBrain?.model || s.providerModel || s.providerLabel);
  const pct = (v: number | null) => (v === null ? "—" : `${Math.round(v)}%`);
  return (
    <div className="stat-chips">
      <span className="chip">CPU <b>{pct(m.cpu)}</b></span>
      <span className="chip">RAM <b>{pct(m.ram)}</b></span>
      <span className="chip">GPU <b>{pct(m.gpu)}</b></span>
      <span className="chip">VRAM <b>{pct(m.vram)}</b></span>
      <span className="chip max-w-[280px] overflow-hidden" title={providerModel}>CERVEAU <b className="truncate">{providerModel}</b></span>
    </div>
  );
}
