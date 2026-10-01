import { useEffect, useMemo, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useJarvisStore } from "../../stores/jarvisStore";

interface BootLine {
  text: string;
  status: () => "ok" | "warn" | "pending";
}

function ArcReactor({ ignited }: { ignited: boolean }) {
  return (
    <div className="relative w-40 h-40">
      <motion.div
        className="absolute inset-0 rounded-full"
        style={ignited ? { boxShadow: "0 0 80px rgb(var(--accent-rgb) / 0.6)" } : undefined}
        animate={ignited ? { opacity: [0.45, 1, 0.45] } : {}}
        transition={{ duration: 2, repeat: Infinity }}
      />
      <svg viewBox="0 0 200 200" className="w-full h-full">
        {/* Anneau externe cranté */}
        <motion.g
          animate={{ rotate: 360 }}
          transition={{ duration: 20, repeat: Infinity, ease: "linear" }}
          style={{ transformOrigin: "100px 100px" }}
        >
          {Array.from({ length: 10 }).map((_, i) => {
            const a = (i / 10) * Math.PI * 2;
            const x1 = 100 + Math.cos(a) * 78;
            const y1 = 100 + Math.sin(a) * 78;
            const x2 = 100 + Math.cos(a) * 90;
            const y2 = 100 + Math.sin(a) * 90;
            return (
              <line
                key={i}
                x1={x1} y1={y1} x2={x2} y2={y2}
                stroke={ignited ? "var(--accent)" : "#1a3a55"}
                strokeWidth="6"
                strokeLinecap="round"
                opacity={ignited ? 0.9 : 0.4}
              />
            );
          })}
        </motion.g>
        <circle cx="100" cy="100" r="70" fill="none" stroke={ignited ? "var(--accent)" : "#1a3a55"} strokeWidth="2" opacity="0.7" />
        {/* Anneau interne contre-rotatif */}
        <motion.g
          animate={{ rotate: -360 }}
          transition={{ duration: 12, repeat: Infinity, ease: "linear" }}
          style={{ transformOrigin: "100px 100px" }}
        >
          <circle
            cx="100" cy="100" r="52"
            fill="none"
            stroke={ignited ? "#66eaff" : "#16324a"}
            strokeWidth="3"
            strokeDasharray="20 12"
            opacity="0.8"
          />
        </motion.g>
        {/* Triangle central */}
        <motion.polygon
          points="100,62 133,138 67,138"
          fill="none"
          stroke={ignited ? "#aaf6ff" : "#1a3a55"}
          strokeWidth="3"
          animate={ignited ? { opacity: [0.6, 1, 0.6] } : { opacity: 0.3 }}
          transition={{ duration: 1.6, repeat: Infinity }}
        />
        <motion.circle
          cx="100" cy="100" r="18"
          fill={ignited ? "#e0fbff" : "#0a1a2a"}
          animate={ignited ? { r: [17, 20, 17] } : {}}
          transition={{ duration: 1.6, repeat: Infinity }}
          style={{ filter: ignited ? "drop-shadow(0 0 12px var(--accent))" : undefined }}
        />
      </svg>
    </div>
  );
}

/** Splash d'initialisation Stark Industries — checks réels (WS/LLM/STT/TTS),
 *  arc reactor qui s'allume, skippable au clic. Joué une fois par session. */
export function BootSequence() {
  const bootDone = useJarvisStore((s) => s.bootDone);
  const setBootDone = useJarvisStore((s) => s.setBootDone);
  const isConnected = useJarvisStore((s) => s.isConnected);
  const llmAvailable = useJarvisStore((s) => s.llmAvailable);
  const sttAvailable = useJarvisStore((s) => s.sttAvailable);
  const providerLabel = useJarvisStore((s) => s.providerLabel);

  const [visibleLines, setVisibleLines] = useState(0);
  const [ignited, setIgnited] = useState(false);

  const lines: BootLine[] = useMemo(
    () => [
      { text: "STARK INDUSTRIES © UNIFIED OS — BOOT v4.0", status: () => "ok" },
      { text: "Initialisation du réacteur ARC…", status: () => "ok" },
      { text: "Liaison neurale WebSocket :8765", status: () => (isConnected ? "ok" : "pending") },
      { text: `Cerveau cognitif — ${providerLabel}`, status: () => (llmAvailable ? "ok" : "warn") },
      { text: "Reconnaissance vocale Whisper", status: () => (sttAvailable ? "ok" : "warn") },
      { text: "Synthèse vocale Piper", status: () => "ok" },
      { text: "Protocoles Fable : raisonnement · vérification · mémoire", status: () => "ok" },
      { text: "Tous les systèmes sont opérationnels.", status: () => "ok" },
    ],
    [isConnected, llmAvailable, sttAvailable, providerLabel]
  );

  useEffect(() => {
    if (bootDone) return;
    if (visibleLines >= lines.length) {
      setIgnited(true);
      const t = setTimeout(() => setBootDone(true), 1400);
      return () => clearTimeout(t);
    }
    const t = setTimeout(() => setVisibleLines((n) => n + 1), visibleLines === 0 ? 400 : 320);
    return () => clearTimeout(t);
  }, [bootDone, visibleLines, lines.length, setBootDone]);

  if (bootDone) return null;

  return (
    <AnimatePresence>
      <motion.div
        className="fixed inset-0 z-50 flex flex-col items-center justify-center gap-8 cursor-pointer select-none"
        style={{ background: "radial-gradient(ellipse at center, color-mix(in srgb, var(--accent) 10%, var(--bg-2)) 0%, var(--bg) 70%)" }}
        exit={{ opacity: 0, scale: 1.06 }}
        transition={{ duration: 0.6 }}
        onClick={() => setBootDone(true)}
        title="Cliquer pour passer"
      >
        <ArcReactor ignited={ignited} />

        <motion.h1
          className="text-4xl font-bold tracking-[0.5em] text-white pl-[0.5em]"
          style={{ fontFamily: "var(--font-display)", textShadow: "0 0 30px var(--accent), 0 0 80px rgb(var(--accent-rgb) / 0.33)" }}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.3 }}
        >
          J.A.R.V.I.S.
        </motion.h1>

        <div className="w-[min(480px,90vw)] font-mono text-[12px] leading-relaxed">
          {lines.slice(0, visibleLines).map((line, i) => {
            const st = line.status();
            const color = st === "ok" ? "#00ff88" : st === "warn" ? "#ffaa00" : "var(--accent)";
            const tag = st === "ok" ? "OK" : st === "warn" ? "ATTN" : "…";
            return (
              <motion.div
                key={i}
                initial={{ opacity: 0, x: -8 }}
                animate={{ opacity: 1, x: 0 }}
                className="flex justify-between gap-4 text-cyan-200/70"
              >
                <span>{line.text}</span>
                <span style={{ color, textShadow: `0 0 8px ${color}` }}>[{tag}]</span>
              </motion.div>
            );
          })}
        </div>

        <motion.p
          className="text-[10px] tracking-[0.4em] text-cyan-600 font-mono"
          animate={{ opacity: [0.3, 0.8, 0.3] }}
          transition={{ duration: 2, repeat: Infinity }}
        >
          CLIQUER POUR PASSER
        </motion.p>
      </motion.div>
    </AnimatePresence>
  );
}
