import { motion } from "framer-motion";
import type { Message as MsgType } from "../../types";

interface Props {
  message: MsgType;
}

export function Message({ message }: Props) {
  const isUser = message.role === "user";
  const isSystem = message.role === "system";

  return (
    <motion.div
      initial={{ opacity: 0, x: isUser ? 20 : -20 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.2 }}
      className={`flex ${isUser ? "justify-end" : "justify-start"} mb-3`}
    >
      <div
        className={`max-w-[75%] px-4 py-2 rounded-lg text-sm leading-relaxed border ${
          isSystem
            ? "bg-yellow-900/20 border-yellow-500/30 text-yellow-300"
            : isUser
            ? "bg-cyan-900/30 border-cyan-500/40 text-cyan-100"
            : "bg-blue-950/40 border-blue-500/20 text-blue-100"
        }`}
        style={{ backdropFilter: "blur(8px)" }}
      >
        {!isUser && !isSystem && (
          <div className="text-xs text-cyan-400 mb-1 font-bold tracking-widest">
            JARVIS
          </div>
        )}
        <pre className="whitespace-pre-wrap font-mono text-xs">
          {message.content}
        </pre>
        <div className="text-right text-[10px] text-blue-400/50 mt-1">
          {new Date(message.timestamp).toLocaleTimeString()}
        </div>
      </div>
    </motion.div>
  );
}
