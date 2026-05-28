import { useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { getCurrentWindow } from "@tauri-apps/api/window";
import { VoiceVisualizer } from "./components/VoiceVisualizer/VoiceVisualizer";
import { ChatPanel } from "./components/ChatPanel/ChatPanel";
import { CommandInput } from "./components/CommandInput/CommandInput";
import { SettingsPanel } from "./components/Settings/SettingsPanel";
import { useJarvisStore } from "./stores/jarvisStore";
import type { JarvisStatus } from "./types";

// ── Hex grid SVG background ─────────────────────────────────────────────────
function HexGrid() {
  return (
    <svg className="absolute inset-0 w-full h-full pointer-events-none" xmlns="http://www.w3.org/2000/svg">
      <defs>
        <pattern id="hexbg" x="0" y="0" width="56" height="48" patternUnits="userSpaceOnUse">
          <polygon
            points="28,2 54,16 54,44 28,58 2,44 2,16"
            fill="none"
            stroke="#00d4ff"
            strokeWidth="0.3"
            opacity="0.08"
          />
        </pattern>
      </defs>
      <rect width="100%" height="100%" fill="url(#hexbg)" />
    </svg>
  );
}

// ── Scanning horizontal line ─────────────────────────────────────────────────
function ScanLine() {
  return (
    <motion.div
      className="absolute left-0 right-0 h-px pointer-events-none z-0"
      style={{ background: "linear-gradient(90deg, transparent, #00d4ff22, #00d4ff44, #00d4ff22, transparent)" }}
      initial={{ top: "0%" }}
      animate={{ top: ["5%", "95%", "5%"] }}
      transition={{ duration: 8, repeat: Infinity, ease: "linear" }}
    />
  );
}

// ── Corner brackets ──────────────────────────────────────────────────────────
function Corner({ pos }: { pos: "tl" | "tr" | "bl" | "br" }) {
  const posClass = {
    tl: "top-0 left-0",
    tr: "top-0 right-0 rotate-90",
    bl: "bottom-0 left-0 -rotate-90",
    br: "bottom-0 right-0 rotate-180",
  }[pos];
  return (
    <div className={`absolute ${posClass} w-6 h-6 pointer-events-none`}>
      <svg width="24" height="24" viewBox="0 0 24 24">
        <path d="M2 14 L2 2 L14 2" fill="none" stroke="#00d4ff" strokeWidth="1.5" opacity="0.6" />
      </svg>
    </div>
  );
}

// ── HUD data readout ─────────────────────────────────────────────────────────
function DataReadout({ label, value, color = "#00d4ff" }: { label: string; value: string; color?: string }) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-[9px] tracking-widest opacity-40" style={{ color }}>
        {label}
      </span>
      <span className="text-[11px] font-mono tracking-wider" style={{ color, textShadow: `0 0 8px ${color}88` }}>
        {value}
      </span>
    </div>
  );
}

// ── Left HUD panel ───────────────────────────────────────────────────────────
function LeftPanel() {
  const status = useJarvisStore((s) => s.status);
  const isConnected = useJarvisStore((s) => s.isConnected);

  const statusColors: Record<JarvisStatus, string> = {
    idle: "#00d4ff",
    listening: "#00ff88",
    processing: "#ffaa00",
    speaking: "#8866ff",
    error: "#ff3333",
  };
  const statusLabels: Record<JarvisStatus, string> = {
    idle: "STANDBY",
    listening: "ÉCOUTE",
    processing: "ANALYSE",
    speaking: "PAROLE",
    error: "ERREUR",
  };
  const col = statusColors[status];

  return (
    <div className="w-72 flex flex-col relative border-r border-cyan-900/20">
      {/* Top data strip */}
      <div className="px-4 pt-3 pb-2 border-b border-cyan-900/20 flex flex-col gap-2">
        <div className="flex justify-between items-start">
          <DataReadout label="PROCESSEUR" value="RTX 3070" />
          <DataReadout label="VRAM" value="8.0 GB" />
          <DataReadout label="CUDA" value="v13.1" />
        </div>
        <div className="h-1 bg-cyan-950 rounded-full overflow-hidden">
          <motion.div
            className="h-full rounded-full"
            style={{ background: `linear-gradient(90deg, ${col}, #00d4ff)` }}
            animate={{ width: status === "processing" ? "85%" : status === "listening" ? "60%" : "35%" }}
            transition={{ duration: 0.5 }}
          />
        </div>
      </div>

      {/* Arc reactor visualizer */}
      <div className="flex-1 flex flex-col items-center justify-center gap-4 py-4">
        <div className="relative">
          {/* Animated ring around canvas */}
          <motion.div
            className="absolute inset-0 rounded-full"
            style={{
              boxShadow: `0 0 30px ${col}44, 0 0 60px ${col}22, inset 0 0 30px ${col}11`,
            }}
            animate={{ opacity: [0.6, 1, 0.6] }}
            transition={{ duration: 2, repeat: Infinity }}
          />
          <VoiceVisualizer />
        </div>

        {/* Status badge */}
        <AnimatePresence mode="wait">
          <motion.div
            key={status}
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -6 }}
            className="flex flex-col items-center gap-1"
          >
            <div
              className="flex items-center gap-1.5 px-3 py-1 rounded border text-xs tracking-widest font-bold"
              style={{
                color: col,
                borderColor: `${col}44`,
                background: `${col}11`,
                textShadow: `0 0 10px ${col}`,
              }}
            >
              <motion.span
                animate={["listening", "processing", "speaking"].includes(status) ? { opacity: [1, 0, 1] } : {}}
                transition={{ duration: 0.8, repeat: Infinity }}
                className="w-1.5 h-1.5 rounded-full"
                style={{ background: col, boxShadow: `0 0 6px ${col}` }}
              />
              {statusLabels[status]}
            </div>
          </motion.div>
        </AnimatePresence>
      </div>

      {/* Bottom data strip */}
      <div className="px-4 py-3 border-t border-cyan-900/20 grid grid-cols-2 gap-x-4 gap-y-2">
        <DataReadout label="CONNEXION" value={isConnected ? "ACTIVE" : "COUPÉE"} color={isConnected ? "#00ff88" : "#ff3333"} />
        <DataReadout label="PROTOCOLE" value="WS-8765" />
        <DataReadout label="MÉMOIRE" value="20 MSG" />
        <DataReadout label="MODÈLE" value="MISTRAL 7B" />
      </div>
    </div>
  );
}

// ── Window controls ──────────────────────────────────────────────────────────
function WindowControls() {
  const minimize = () => void getCurrentWindow().minimize();
  const maximize = async () => {
    const win = getCurrentWindow();
    (await win.isMaximized()) ? void win.unmaximize() : void win.maximize();
  };
  const close = () => void getCurrentWindow().close();

  return (
    <div className="flex items-center gap-1">
      {/* Minimize */}
      <motion.button
        whileHover={{ scale: 1.1 }}
        whileTap={{ scale: 0.9 }}
        onClick={minimize}
        className="w-7 h-7 flex items-center justify-center rounded text-blue-400/40 hover:text-cyan-400 hover:bg-cyan-400/10 transition-colors"
        title="Réduire"
      >
        <svg width="12" height="12" viewBox="0 0 12 12" fill="currentColor">
          <rect x="1" y="5.5" width="10" height="1.5" rx="0.75" />
        </svg>
      </motion.button>

      {/* Maximize */}
      <motion.button
        whileHover={{ scale: 1.1 }}
        whileTap={{ scale: 0.9 }}
        onClick={maximize}
        className="w-7 h-7 flex items-center justify-center rounded text-blue-400/40 hover:text-cyan-400 hover:bg-cyan-400/10 transition-colors"
        title="Agrandir"
      >
        <svg width="11" height="11" viewBox="0 0 11 11" fill="none" stroke="currentColor" strokeWidth="1.5">
          <rect x="1" y="1" width="9" height="9" rx="1" />
        </svg>
      </motion.button>

      {/* Close */}
      <motion.button
        whileHover={{ scale: 1.1 }}
        whileTap={{ scale: 0.9 }}
        onClick={close}
        className="w-7 h-7 flex items-center justify-center rounded text-blue-400/40 hover:text-red-400 hover:bg-red-400/10 transition-colors"
        title="Fermer"
      >
        <svg width="11" height="11" viewBox="0 0 11 11" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
          <line x1="1.5" y1="1.5" x2="9.5" y2="9.5" />
          <line x1="9.5" y1="1.5" x2="1.5" y2="9.5" />
        </svg>
      </motion.button>
    </div>
  );
}

// ── Header ───────────────────────────────────────────────────────────────────
function Header() {
  const isConnected = useJarvisStore((s) => s.isConnected);
  const timeRef = useRef<HTMLSpanElement>(null);

  useEffect(() => {
    const tick = () => {
      if (timeRef.current) {
        timeRef.current.textContent = new Date().toLocaleTimeString("fr-FR", {
          hour: "2-digit", minute: "2-digit", second: "2-digit",
        });
      }
    };
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, []);

  return (
    <div
      className="relative z-10 flex items-center justify-between px-4 py-2 border-b border-cyan-900/30"
      data-tauri-drag-region
    >
      {/* Left HUD info */}
      <div className="flex items-center gap-4" data-tauri-drag-region>
        <div className="flex items-center gap-2">
          <motion.div
            className="w-2 h-2 rounded-full"
            style={{ background: isConnected ? "#00ff88" : "#ff3333", boxShadow: `0 0 8px ${isConnected ? "#00ff88" : "#ff3333"}` }}
            animate={{ opacity: [1, 0.4, 1] }}
            transition={{ duration: 2, repeat: Infinity }}
          />
          <span className="text-[10px] tracking-widest" style={{ color: isConnected ? "#00ff88" : "#ff3333" }}>
            {isConnected ? "CORE ONLINE" : "CORE OFFLINE"}
          </span>
        </div>
        <div className="w-px h-3 bg-cyan-900/40" />
        <span className="text-[10px] text-blue-400/40 tracking-widest font-mono">
          SYS://JARVIS.LOCAL
        </span>
      </div>

      {/* Center title */}
      <div className="absolute left-1/2 -translate-x-1/2 text-center pointer-events-none">
        <h1
          className="text-2xl font-bold tracking-[0.6em] text-cyan-400"
          style={{ textShadow: "0 0 20px #00d4ff, 0 0 50px #00d4ff66, 0 0 80px #00d4ff33" }}
        >
          J.A.R.V.I.S.
        </h1>
        <p className="text-[8px] text-blue-400/35 tracking-[0.35em] mt-0.5">
          JUST A RATHER VERY INTELLIGENT SYSTEM
        </p>
      </div>

      {/* Right: clock + version + settings + window controls */}
      <div className="flex items-center gap-3">
        <span className="text-[10px] text-blue-400/40 tracking-widest font-mono">
          <span ref={timeRef} />
        </span>
        <div className="w-px h-3 bg-cyan-900/40" />
        <span className="text-[10px] text-cyan-400/60 tracking-widest">v1.0.0</span>
        <div className="w-px h-3 bg-cyan-900/40" />
        <SettingsPanel />
        <div className="w-px h-3 bg-cyan-900/40" />
        <WindowControls />
      </div>
    </div>
  );
}

// ── Right chat area decoration ────────────────────────────────────────────────
function ChatAreaFrame() {
  return (
    <>
      {/* Top-right corner accent */}
      <div className="absolute top-0 right-0 w-32 h-px bg-gradient-to-l from-cyan-400/30 to-transparent" />
      <div className="absolute top-0 right-0 w-px h-16 bg-gradient-to-b from-cyan-400/30 to-transparent" />
      {/* Bottom-left corner accent */}
      <div className="absolute bottom-0 left-0 w-32 h-px bg-gradient-to-r from-cyan-400/20 to-transparent" />
    </>
  );
}

// ── Main App ─────────────────────────────────────────────────────────────────
export default function App() {
  return (
    <div className="h-screen flex flex-col relative overflow-hidden bg-[#010d1a]">
      <HexGrid />
      <ScanLine />

      {/* Ambient glow spots */}
      <div className="absolute top-1/4 left-1/4 w-96 h-96 rounded-full pointer-events-none"
        style={{ background: "radial-gradient(circle, #00d4ff08 0%, transparent 70%)", transform: "translate(-50%, -50%)" }} />
      <div className="absolute bottom-1/4 right-1/4 w-80 h-80 rounded-full pointer-events-none"
        style={{ background: "radial-gradient(circle, #8800ff06 0%, transparent 70%)", transform: "translate(50%, 50%)" }} />

      <Header />

      <div className="flex-1 flex overflow-hidden relative z-10">
        <LeftPanel />

        {/* Right chat area */}
        <div className="flex-1 flex flex-col relative">
          <ChatAreaFrame />
          <ChatPanel />
          <CommandInput />
        </div>
      </div>

      {/* Global corner brackets */}
      <Corner pos="tl" />
      <Corner pos="tr" />
      <Corner pos="bl" />
      <Corner pos="br" />
    </div>
  );
}
