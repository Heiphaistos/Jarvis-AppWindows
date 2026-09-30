import { useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useJarvisStore } from "../../stores/jarvisStore";
import { Message } from "./Message";
import { TypingIndicator } from "./TypingIndicator";

const SUGGESTIONS = [
  "Comment va mon système ?",
  "Quelle est la météo à Paris ?",
  "Explique-moi le fonctionnement d'un réacteur à fusion",
  "Souviens-toi que je préfère les réponses courtes",
];

export function ChatPanel() {
  const messages = useJarvisStore((s) => s.messages);
  const pendingMessageId = useJarvisStore((s) => s.pendingMessageId);
  const status = useJarvisStore((s) => s.status);
  const exportConversation = useJarvisStore((s) => s.exportConversation);
  const sendQuery = useJarvisStore((s) => s.sendQuery);
  const isConnected = useJarvisStore((s) => s.isConnected);
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
            className="absolute inset-0 flex flex-col items-center justify-center gap-5"
          >
            <div className="text-center">
              <div className="text-lg font-light text-cyan-100/70 mb-1">
                Bonsoir, Monsieur.
              </div>
              <div className="text-[11px] text-blue-400/40 tracking-wide">
                Que puis-je faire pour vous ?
              </div>
            </div>
            <div className="flex flex-col gap-2 w-full max-w-sm px-6">
              {SUGGESTIONS.map((s, i) => (
                <motion.button
                  key={s}
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: 0.15 + i * 0.08 }}
                  whileHover={{ scale: 1.02, x: 3 }}
                  whileTap={{ scale: 0.98 }}
                  disabled={!isConnected}
                  onClick={() => sendQuery(s)}
                  className="text-left px-4 py-2.5 rounded-xl text-[12px] text-cyan-100/60 hover:text-cyan-100 transition-colors disabled:opacity-30"
                  style={{
                    background: "rgba(0,120,190,0.06)",
                    border: "1px solid rgba(0,212,255,0.1)",
                  }}
                >
                  {s}
                </motion.button>
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {messages.length > 0 && (
        <div className="flex justify-end px-3 pt-1 pb-3">
          <button
            onClick={exportConversation}
            title="Exporter la conversation en Markdown"
            className="text-xs text-cyan-800 hover:text-cyan-400 transition-colors flex items-center gap-1"
          >
            <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
              <polyline points="7 10 12 15 17 10" />
              <line x1="12" y1="15" x2="12" y2="3" />
            </svg>
            Exporter
          </button>
        </div>
      )}

      {messages.map((msg) => (
        <Message key={msg.id} message={msg} />
      ))}
      {status === "processing" && !pendingMessageId && <TypingIndicator />}
      <div ref={bottomRef} />
    </div>
  );
}
