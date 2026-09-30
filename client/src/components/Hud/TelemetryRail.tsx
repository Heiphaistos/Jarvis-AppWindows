import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { Brain, Database, MicOff, Trash2, Volume2, VolumeX, Wifi, WifiOff } from "lucide-react";
import { useJarvisStore } from "../../stores/jarvisStore";
import { RadialGauge } from "./RadialGauge";
import { useAccent } from "./status";

const LEVEL_LABEL = { instant: "INSTANTANÉ", standard: "STANDARD", deep: "PROFOND" } as const;

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center gap-2">
        <span className="text-[9px] tracking-[0.35em] text-blue-200/40">{title}</span>
        <div className="flex-1 h-px bg-gradient-to-r from-cyan-400/25 to-transparent" />
      </div>
      {children}
    </div>
  );
}

/** Colonne de télémétrie : jauges système, cerveau actif, voix, mémoire. */
export function TelemetryRail() {
  const accent = useAccent();
  const metrics = useJarvisStore((s) => s.metrics);
  const isConnected = useJarvisStore((s) => s.isConnected);
  const ttsEnabled = useJarvisStore((s) => s.ttsEnabled);
  const setTtsEnabled = useJarvisStore((s) => s.setTtsEnabled);
  const wsSend = useJarvisStore((s) => s.wsSend);
  const clearMessages = useJarvisStore((s) => s.clearMessages);
  const sttAvailable = useJarvisStore((s) => s.sttAvailable);
  const llmAvailable = useJarvisStore((s) => s.llmAvailable);
  const providerLabel = useJarvisStore((s) => s.providerLabel);
  const providerModel = useJarvisStore((s) => s.providerModel);
  const lastBrain = useJarvisStore((s) => s.lastBrain);
  const memoryVersion = useJarvisStore((s) => s.memoryVersion);

  const [memCount, setMemCount] = useState<number | null>(null);
  const [gpuName, setGpuName] = useState("");
  useEffect(() => {
    if (!isConnected) return;
    fetch("http://127.0.0.1:8765/api/memories/count").then((r) => r.json())
      .then((d: { count: number }) => setMemCount(d.count)).catch(() => {});
  }, [isConnected, memoryVersion]);
  useEffect(() => {
    if (!isConnected) return;
    fetch("http://127.0.0.1:8765/api/system_info").then((r) => r.json())
      .then((d: { info: string }) => setGpuName(d.info.match(/GPU: ([^|]+)/)?.[1].trim() ?? "")).catch(() => {});
  }, [isConnected]);

  const toggleMute = () => {
    const next = !ttsEnabled;
    setTtsEnabled(next);
    wsSend?.({ type: "set_tts", payload: { enabled: next } });
  };
  const ttftColor = !lastBrain ? accent : lastBrain.ttftMs < 600 ? "#00ff88" : lastBrain.ttftMs < 1500 ? "#ffcc44" : "#ff8844";

  return (
    <aside className="w-[270px] shrink-0 flex flex-col gap-5 p-4 glass-panel rounded-2xl overflow-y-auto hud-corners">
      <Section title="SYSTÈME">
        <div className="grid grid-cols-2 gap-y-1 justify-items-center">
          <RadialGauge label="CPU" value={metrics.cpu} accent={accent} />
          <RadialGauge label="RAM" value={metrics.ram} accent={accent} />
          <RadialGauge label="GPU" value={metrics.gpu} accent={accent} />
          <RadialGauge label="VRAM" value={metrics.vram} accent={accent} />
        </div>
        {gpuName && <div className="text-center text-[9px] font-mono text-blue-200/40 truncate">{gpuName}</div>}
      </Section>

      <Section title="CERVEAU">
        <div className="rounded-xl p-3 flex flex-col gap-1.5"
          style={{ background: `${accent}0d`, border: `1px solid ${accent}2a` }}>
          <div className="flex items-center gap-2">
            <Brain size={13} style={{ color: accent }} />
            <span className="text-[11px] font-semibold tracking-wide truncate" style={{ color: accent }}>
              {lastBrain ? lastBrain.label : providerLabel}
            </span>
          </div>
          <div className="text-[10px] font-mono text-blue-100/60 truncate">
            {lastBrain?.model || providerModel || "—"}
          </div>
          {lastBrain && (
            <div className="flex items-center justify-between pt-1 text-[9px] tracking-widest">
              <span className="text-blue-200/50">{LEVEL_LABEL[lastBrain.level]}</span>
              <span className="font-mono" style={{ color: ttftColor }}>{lastBrain.ttftMs} ms</span>
            </div>
          )}
        </div>
      </Section>

      <Section title="LIAISONS">
        <div className="flex flex-col gap-1.5 text-[10px]">
          <div className="flex items-center justify-between">
            <span className="flex items-center gap-1.5 text-blue-100/60">
              {isConnected ? <Wifi size={11} /> : <WifiOff size={11} />} Noyau
            </span>
            <span style={{ color: isConnected ? "#00ff88" : "#ff4466" }}>{isConnected ? "EN LIGNE" : "HORS LIGNE"}</span>
          </div>
          <div className="flex items-center justify-between">
            <span className="flex items-center gap-1.5 text-blue-100/60"><Database size={11} /> Mémoire</span>
            <span className="font-mono text-blue-100/70">{memCount ?? "—"} faits</span>
          </div>
          {isConnected && !sttAvailable && (
            <div className="flex items-center gap-1.5 text-[9px] text-amber-300/80"><MicOff size={10} /> Micro indisponible (Whisper)</div>
          )}
          {isConnected && !llmAvailable && (
            <div className="text-[9px] text-rose-300/80">Cerveau local absent — utilisez un cerveau cloud ou AUTO</div>
          )}
        </div>
      </Section>

      <div className="mt-auto flex flex-col gap-2">
        <motion.button whileTap={{ scale: 0.97 }} onClick={toggleMute}
          className="flex items-center justify-center gap-2 py-2 rounded-xl text-[10px] tracking-[0.25em] font-semibold"
          style={{
            color: ttsEnabled ? accent : "#ff5566",
            background: ttsEnabled ? `${accent}14` : "#ff556614",
            border: `1px solid ${ttsEnabled ? `${accent}44` : "#ff556644"}`,
          }}>
          {ttsEnabled ? <Volume2 size={13} /> : <VolumeX size={13} />}
          {ttsEnabled ? "VOIX ACTIVE" : "VOIX COUPÉE"}
        </motion.button>
        <button onClick={clearMessages}
          className="flex items-center justify-center gap-1.5 py-1.5 rounded-xl text-[9px] tracking-[0.25em] text-rose-300/50 border border-rose-400/10 hover:text-rose-300 hover:border-rose-400/40 hover:bg-rose-400/5 transition">
          <Trash2 size={10} /> EFFACER L'HISTORIQUE
        </button>
      </div>
    </aside>
  );
}
