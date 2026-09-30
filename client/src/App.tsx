import { useEffect, useRef } from "react";
import { motion } from "framer-motion";
import { getCurrentWindow } from "@tauri-apps/api/window";
import { ChatPanel } from "./components/ChatPanel/ChatPanel";
import { CommandInput } from "./components/CommandInput/CommandInput";
import { SettingsPanel } from "./components/Settings/SettingsPanel";
import { BootSequence } from "./components/Boot/BootSequence";
import { VoiceOrb } from "./components/VoiceOrb/VoiceOrb";
import { CoreStage } from "./components/Hud/CoreStage";
import { TelemetryRail } from "./components/Hud/TelemetryRail";
import { useAccent } from "./components/Hud/status";
import { useJarvisStore } from "./stores/jarvisStore";

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

function WindowControls() {
  const minimize = () => void getCurrentWindow().minimize();
  const maximize = async () => {
    const win = getCurrentWindow();
    (await win.isMaximized()) ? void win.unmaximize() : void win.maximize();
  };
  const close = () => void getCurrentWindow().close();

  return (
    <div className="flex items-center gap-1">
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

function Header() {
  const isConnected = useJarvisStore((s) => s.isConnected);
  const accent = useAccent();
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
      className="relative z-10 flex items-center justify-between px-4 py-2 mx-3 mt-3 mb-2 rounded-2xl glass-subtle"
      data-tauri-drag-region
    >
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

      <div className="absolute left-1/2 -translate-x-1/2 text-center pointer-events-none">
        <h1
          className="holo-title text-2xl font-bold tracking-[0.6em]"
          style={{ color: accent, textShadow: `0 0 20px ${accent}, 0 0 50px ${accent}66, 0 0 80px ${accent}33` }}
        >
          J.A.R.V.I.S.
        </h1>
        <p className="text-[8px] text-blue-400/35 tracking-[0.35em] mt-0.5">
          JUST A RATHER VERY INTELLIGENT SYSTEM
        </p>
      </div>

      <div className="flex items-center gap-3">
        <span className="text-[10px] text-blue-400/40 tracking-widest font-mono">
          <span ref={timeRef} />
        </span>
        <div className="w-px h-3 bg-cyan-900/40" />
        <span className="text-[10px] text-cyan-400/60 tracking-widest">v5.0.0</span>
        <div className="w-px h-3 bg-cyan-900/40" />
        <SettingsPanel />
        <div className="w-px h-3 bg-cyan-900/40" />
        <WindowControls />
      </div>
    </div>
  );
}

function ChatAreaFrame() {
  return (
    <>
      <div className="absolute top-0 right-0 w-32 h-px bg-gradient-to-l from-cyan-400/30 to-transparent" />
      <div className="absolute top-0 right-0 w-px h-16 bg-gradient-to-b from-cyan-400/30 to-transparent" />
      <div className="absolute bottom-0 left-0 w-32 h-px bg-gradient-to-r from-cyan-400/20 to-transparent" />
    </>
  );
}

export default function App() {
  const layoutSide = useJarvisStore((s) => s.layoutSide);
  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === "k") {
        e.preventDefault();
        const input = document.querySelector<HTMLInputElement>("[data-jarvis-input]");
        input?.focus();
      }
      if (e.key === "Escape") {
        const input = document.querySelector<HTMLInputElement>("[data-jarvis-input]");
        if (input && document.activeElement === input) {
          input.value = "";
          input.blur();
        }
      }
    };
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, []);

  return (
    <div className="h-screen flex flex-col relative overflow-hidden bg-[#010d1a]">
      <HexGrid />
      <ScanLine />

      <div className="absolute top-1/4 left-1/4 w-96 h-96 rounded-full pointer-events-none"
        style={{ background: "radial-gradient(circle, #00d4ff08 0%, transparent 70%)", transform: "translate(-50%, -50%)" }} />
      <div className="absolute bottom-1/4 right-1/4 w-80 h-80 rounded-full pointer-events-none"
        style={{ background: "radial-gradient(circle, #8800ff06 0%, transparent 70%)", transform: "translate(50%, 50%)" }} />

      <Header />

      <div className={`flex-1 flex overflow-hidden relative z-10 gap-3 px-3 pb-3 pt-1 ${layoutSide === "right" ? "flex-row-reverse" : ""}`}>
        <div className="hidden xl:flex"><TelemetryRail /></div>

        <div className="hidden md:flex flex-1 min-w-0"><CoreStage /></div>

        <div className="w-full md:w-[440px] 2xl:w-[540px] shrink-0 flex flex-col relative glass-panel rounded-2xl overflow-hidden hud-corners">
          <ChatAreaFrame />
          <ChatPanel />
          <CommandInput />
        </div>
      </div>

      <Corner pos="tl" />
      <Corner pos="tr" />
      <Corner pos="bl" />
      <Corner pos="br" />

      <VoiceOrb />
      <BootSequence />
    </div>
  );
}
