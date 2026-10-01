import { motion, AnimatePresence } from "framer-motion";
import { BrainCircuit, Wrench, ShieldCheck } from "lucide-react";
import { useJarvisStore } from "../../stores/jarvisStore";
import type { AgentPhase } from "../../types";

const PHASE_CONF: Record<Exclude<AgentPhase, "done">, { icon: typeof BrainCircuit; color: string; label: string }> = {
  thinking: { icon: BrainCircuit, color: "var(--accent)", label: "RÉFLEXION" },
  tool: { icon: Wrench, color: "var(--amber)", label: "OUTIL" },
  verify: { icon: ShieldCheck, color: "var(--green)", label: "VÉRIFICATION" },
};

/** Timeline temps réel de la boucle agent (réflexion → outils → vérification). */
export function AgentSteps() {
  const steps = useJarvisStore((s) => s.agentSteps);
  const status = useJarvisStore((s) => s.status);

  if (steps.length === 0 || status === "idle" || status === "standby") return null;

  return (
    <div className="agent-steps">
      <AnimatePresence initial={false}>
        {steps.slice(-6).map((step, i, arr) => {
          const conf = PHASE_CONF[step.phase as Exclude<AgentPhase, "done">];
          if (!conf) return null;
          const Icon = conf.icon;
          const isLast = i === arr.length - 1;
          return (
            <motion.div
              key={step.timestamp + step.phase}
              initial={{ opacity: 0, x: 10 }}
              animate={{ opacity: isLast ? 1 : 0.45, x: 0 }}
              className="step"
              style={{ "--c": conf.color } as React.CSSProperties}
            >
              {i > 0 && <span className="step-sep">›</span>}
              <Icon />
              {conf.label}
              {step.detail ? ` · ${step.detail}` : ""}
            </motion.div>
          );
        })}
      </AnimatePresence>
    </div>
  );
}
