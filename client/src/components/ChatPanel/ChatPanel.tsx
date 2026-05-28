import { useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useJarvisStore } from "../../stores/jarvisStore";
import { Message } from "./Message";
import { TypingIndicator } from "./TypingIndicator";

export function ChatPanel() {
  const messages = useJarvisStore((s) => s.messages);
  const pendingMessageId = useJarvisStore((s) => s.pendingMessageId);
  const status = useJarvisStore((s) => s.status);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages.length, pendingMessageId]);

  return (
    <div className="flex-1 overflow-y-auto px-4 pt-4 pb-2 relative scrollbar-thin scrollbar-track-transparent scrollbar-thumb-cyan-900/40">
      <AnimatePresence>
        {messages.length === 0 && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="absolute inset-0 flex flex-col items-center justify-center gap-3 pointer-events-none"
          >
            <div className="text-[10px] text-blue-400/25 tracking-[0.4em] text-center">
              ── SYSTÈME EN ATTENTE DE COMMANDE ──
            </div>
            <div className="flex gap-1">
              {[0, 1, 2].map((i) => (
                <motion.div
                  key={i}
                  className="w-1 h-1 rounded-full bg-cyan-400/20"
                  animate={{ opacity: [0.2, 0.8, 0.2] }}
                  transition={{ duration: 1.5, repeat: Infinity, delay: i * 0.3 }}
                />
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {messages.map((msg) => (
        <Message key={msg.id} message={msg} />
      ))}
      {status === "processing" && !pendingMessageId && <TypingIndicator />}
      <div ref={bottomRef} />
    </div>
  );
}
