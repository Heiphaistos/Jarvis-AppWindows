import { motion, AnimatePresence } from "framer-motion";
import { useJarvisStore } from "../../stores/jarvisStore";
import type { JarvisStatus } from "../../types";

const STATUS_CONFIG: Record<
  JarvisStatus,
  { label: string; color: string; pulse: boolean }
> = {
  idle: { label: "STANDBY", color: "text-blue-400", pulse: false },
  listening: { label: "LISTENING", color: "text-green-400", pulse: true },
  processing: { label: "PROCESSING...", color: "text-amber-400", pulse: true },
  speaking: { label: "SPEAKING", color: "text-cyan-400", pulse: true },
  error: { label: "ERROR", color: "text-red-400", pulse: false },
};

export function StatusBar() {
  const status = useJarvisStore((s) => s.status);
  const isConnected = useJarvisStore((s) => s.isConnected);
  const cfg = STATUS_CONFIG[status];

  return (
    <div className="flex items-center justify-between px-4 py-2 border-b border-cyan-900/40">
      <div className="flex items-center gap-2">
        <motion.div
          className={`w-2 h-2 rounded-full ${
            isConnected ? "bg-green-400" : "bg-red-400"
          }`}
          animate={isConnected ? { opacity: [1, 0.4, 1] } : {}}
          transition={{ duration: 2, repeat: Infinity }}
        />
        <span className="text-xs text-blue-400/60 tracking-widest">
          {isConnected ? "CORE ONLINE" : "CORE OFFLINE"}
        </span>
      </div>

      <AnimatePresence mode="wait">
        <motion.div
          key={status}
          initial={{ opacity: 0, y: -4 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: 4 }}
          className={`text-xs font-bold tracking-widest ${cfg.color}`}
        >
          {cfg.pulse && (
            <motion.span
              animate={{ opacity: [1, 0, 1] }}
              transition={{ duration: 1, repeat: Infinity }}
              className="mr-1"
            >
              ◉
            </motion.span>
          )}
          {cfg.label}
        </motion.div>
      </AnimatePresence>

      <span className="text-xs text-blue-400/40 tracking-widest">
        J.A.R.V.I.S. v1.0
      </span>
    </div>
  );
}
