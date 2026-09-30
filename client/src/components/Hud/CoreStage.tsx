import { lazy, Suspense } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { useJarvisStore } from "../../stores/jarvisStore";
import { AgentSteps } from "../AgentSteps/AgentSteps";
import { ArcOverlay } from "./ArcOverlay";
import { STATUS_LABELS, useStatusColor } from "./status";

// three.js chargé en différé — n'alourdit pas le démarrage
const JarvisScene = lazy(() =>
  import("../Scene/JarvisScene").then((m) => ({ default: m.JarvisScene })),
);

/** Réplique en cours, affichée en sous-titre sous l'hologramme. */
function LiveCaption() {
  const text = useJarvisStore((s) => {
    const id = s.pendingMessageId;
    if (!id) return "";
    return s.messages.find((m) => m.id === id)?.content ?? "";
  });
  const tail = text.length > 220 ? `…${text.slice(-220)}` : text;
  return (
    <AnimatePresence>
      {tail && (
        <motion.p key="caption" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
          className="max-w-xl text-center text-[13px] leading-relaxed text-blue-50/80"
          style={{ textShadow: "0 0 12px rgba(0,0,0,0.9)" }}>
          {tail}
        </motion.p>
      )}
    </AnimatePresence>
  );
}

/** Scène centrale : hologramme 3D, anneaux HUD, statut et sous-titres. */
export function CoreStage() {
  const { status, color } = useStatusColor();
  const busy = status === "processing" || status === "speaking" || status === "listening";
  return (
    <section className="relative flex-1 min-w-0 flex flex-col items-center">
      <div className="relative w-full flex-1 min-h-0">
        <div className="absolute inset-0 rounded-full pointer-events-none"
          style={{ background: `radial-gradient(circle at 50% 50%, ${color}1f 0%, transparent 45%)` }} />
        <ArcOverlay color={color} busy={busy} />
        <Suspense fallback={null}>
          <JarvisScene />
        </Suspense>
      </div>

      <div className="relative z-10 flex flex-col items-center gap-3 pb-4 px-4 w-full">
        <AnimatePresence mode="wait">
          <motion.div key={status} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -6 }}
            className="flex items-center gap-2 px-4 py-1.5 rounded-full text-[11px] tracking-[0.4em] font-semibold"
            style={{ color, border: `1px solid ${color}55`, background: `${color}12`, textShadow: `0 0 12px ${color}`, boxShadow: `0 0 24px ${color}22` }}>
            <motion.span className="w-1.5 h-1.5 rounded-full" style={{ background: color, boxShadow: `0 0 8px ${color}` }}
              animate={busy ? { opacity: [1, 0.2, 1] } : { opacity: 1 }} transition={{ duration: 0.9, repeat: Infinity }} />
            {STATUS_LABELS[status]}
          </motion.div>
        </AnimatePresence>
        <LiveCaption />
        <div className="w-full max-w-2xl"><AgentSteps /></div>
      </div>
    </section>
  );
}
