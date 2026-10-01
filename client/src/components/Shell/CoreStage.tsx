import { lazy, Suspense } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Mic } from "lucide-react";
import { ArcOverlay } from "./ArcOverlay";
import { useJarvisStore, THEMES } from "../../stores/jarvisStore";
import { STATUS_COLORS, STATUS_LABELS, statusCss } from "./theme";

// three.js chargé en différé — n'alourdit pas le démarrage
const JarvisScene = lazy(() =>
  import("../Scene/JarvisScene").then((m) => ({ default: m.JarvisScene }))
);

/** Réplique en cours, affichée en sous-titre sous l'hologramme. */
function LiveCaption() {
  const text = useJarvisStore((s) => {
    const id = s.pendingMessageId;
    return id ? s.messages.find((m) => m.id === id)?.content ?? "" : "";
  });
  const tail = text.length > 220 ? `…${text.slice(-220)}` : text;
  return (
    <AnimatePresence>
      {tail && (
        <motion.p key="caption" className="core-caption" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}>
          {tail}
        </motion.p>
      )}
    </AnimatePresence>
  );
}

interface Props {
  isMicActive: boolean;
  onMic: () => void;
}

/** Cœur holographique : scène 3D, statut, gros bouton micro. */
export function CoreStage({ isMicActive, onMic }: Props) {
  const accent = useJarvisStore((s) => (s.theme === "custom" ? s.customAccent : THEMES[s.theme].accent));
  const status = useJarvisStore((s) => s.status);
  const isConnected = useJarvisStore((s) => s.isConnected);
  const wake = useJarvisStore((s) => s.wakeWordEnabled);
  const label = isConnected ? STATUS_LABELS[status] : "HORS LIGNE";
  const sc = isConnected ? statusCss(status) : "var(--red)";
  const busy = status === "listening" || status === "processing" || status === "speaking";

  return (
    <section className="core" aria-label="Hologramme" style={{ "--sc": sc } as React.CSSProperties}>
      <div className="core-halo" />
      <div className="core-arcs">
        <ArcOverlay color={!isConnected ? "#ff4466" : status === "idle" ? accent : STATUS_COLORS[status]} busy={busy} />
      </div>
      <div className="core-stage">
        <Suspense fallback={null}>
          <JarvisScene />
        </Suspense>
      </div>
      <div className="core-status">
        <span className={`dot${busy ? " live" : ""}`} />
        {label}
      </div>
      <LiveCaption />
      <button
        className={`mic${isMicActive ? " is-on" : ""}`}
        onClick={onMic}
        disabled={!isConnected}
        title={isMicActive ? "Couper le micro" : "Parler à JARVIS"}
        aria-label={isMicActive ? "Couper le micro" : "Parler à JARVIS"}
      >
        <Mic />
      </button>
      <p className="core-hint">
        {isMicActive ? "Je vous écoute…" : wake ? "Dites « Hey Jarvis » ou touchez le micro" : "Touchez le micro pour parler"}
      </p>
    </section>
  );
}
