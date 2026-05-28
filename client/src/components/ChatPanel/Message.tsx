import { motion } from "framer-motion";
import type { Message as MsgType } from "../../types";

interface Props {
  message: MsgType;
}

export function Message({ message }: Props) {
  const isUser = message.role === "user";
  const isSystem = message.role === "system";
  const time = new Date(message.timestamp).toLocaleTimeString("fr-FR", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });

  if (isSystem) {
    return (
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        className="flex justify-center mb-3"
      >
        <div className="px-3 py-1 text-[10px] tracking-widest rounded border border-yellow-500/20 bg-yellow-900/10 text-yellow-400/70">
          ⚡ {message.content}
        </div>
      </motion.div>
    );
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25 }}
      className={`flex ${isUser ? "justify-end" : "justify-start"} mb-4`}
    >
      {/* JARVIS avatar indicator */}
      {!isUser && (
        <div className="flex-shrink-0 w-6 mt-1 mr-2 flex flex-col items-center gap-1">
          <div
            className="w-1.5 h-1.5 rounded-full"
            style={{ background: "#00d4ff", boxShadow: "0 0 6px #00d4ff" }}
          />
          <div className="flex-1 w-px bg-cyan-900/40" />
        </div>
      )}

      <div className={`max-w-[78%] flex flex-col ${isUser ? "items-end" : "items-start"}`}>
        {/* Label */}
        <div className="text-[9px] tracking-widest mb-1 px-1" style={{ color: isUser ? "#00d4ffaa" : "#00ff88aa" }}>
          {isUser ? "VOUS" : "J.A.R.V.I.S."}
        </div>

        {/* Bubble */}
        <div
          className="relative px-4 py-2.5 text-sm leading-relaxed"
          style={
            isUser
              ? {
                  background: "linear-gradient(135deg, rgba(0,80,120,0.4), rgba(0,40,80,0.6))",
                  border: "1px solid rgba(0,212,255,0.25)",
                  borderRadius: "12px 2px 12px 12px",
                  backdropFilter: "blur(12px)",
                  boxShadow: "0 0 20px #00d4ff11, inset 0 0 20px #00d4ff08",
                }
              : {
                  background: "linear-gradient(135deg, rgba(0,20,50,0.6), rgba(0,10,30,0.8))",
                  border: "1px solid rgba(0,136,170,0.2)",
                  borderRadius: "2px 12px 12px 12px",
                  backdropFilter: "blur(12px)",
                  boxShadow: "0 0 20px #00d4ff08",
                }
          }
        >
          {/* Top accent line for JARVIS */}
          {!isUser && (
            <div className="absolute top-0 left-0 right-0 h-px rounded-t-full" style={{ background: "linear-gradient(90deg, #00d4ff44, transparent)" }} />
          )}

          <pre className="whitespace-pre-wrap font-mono text-xs text-cyan-50/90">
            {message.content}
          </pre>

          {/* Timestamp */}
          <div className="text-right text-[9px] text-blue-400/35 mt-1.5 font-mono tracking-widest">
            {time}
          </div>
        </div>
      </div>

      {/* User avatar indicator */}
      {isUser && (
        <div className="flex-shrink-0 w-6 mt-1 ml-2 flex flex-col items-center gap-1">
          <div
            className="w-1.5 h-1.5 rounded-full"
            style={{ background: "#00d4ff", boxShadow: "0 0 6px #00d4ff88" }}
          />
          <div className="flex-1 w-px bg-cyan-900/40" />
        </div>
      )}
    </motion.div>
  );
}
