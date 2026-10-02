import { useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Newspaper, Timer, Eye, Atom, BookmarkPlus } from "lucide-react";
import { useJarvisStore } from "../../stores/jarvisStore";
import { Message } from "./Message";
import { TypingIndicator } from "./TypingIndicator";
import { serverMode } from "../../lib/session";

const SUGGESTIONS: { icon: typeof Newspaper; text: string; pc?: boolean }[] = [
  { icon: Newspaper, text: "Fais-moi le point" },
  { icon: Timer, text: "Mets un minuteur de 10 minutes pour les pâtes" },
  { icon: Eye, text: "Regarde mon écran et dis-moi ce que tu vois", pc: true },
  { icon: Atom, text: "Explique-moi le fonctionnement d'un réacteur à fusion" },
  { icon: BookmarkPlus, text: "Souviens-toi que je préfère les réponses courtes" },
];

function greeting() {
  const h = new Date().getHours();
  return h >= 5 && h < 18 ? "Bonjour, Monsieur." : "Bonsoir, Monsieur.";
}

export function ChatPanel() {
  const messages = useJarvisStore((s) => s.messages);
  const pendingMessageId = useJarvisStore((s) => s.pendingMessageId);
  const status = useJarvisStore((s) => s.status);
  const sendQuery = useJarvisStore((s) => s.sendQuery);
  const isConnected = useJarvisStore((s) => s.isConnected);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (messages.length) bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages.length, pendingMessageId]);

  return (
    <div className="chat-log" aria-live="polite">
      <AnimatePresence>
        {messages.length === 0 && (
          <motion.div className="welcome" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
            <span className="eyebrow">J.A.R.V.I.S.</span>
            <h2>{greeting()}</h2>
            <p>{isConnected ? "Que puis-je faire pour vous ?" : "Connexion au cœur en cours…"}</p>
            <div className="welcome-grid">
              {SUGGESTIONS.filter((s) => !(s.pc && serverMode() === "hosted")).map(({ icon: Icon, text }, i) => (
                <motion.button
                  key={text}
                  className="welcome-card"
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: 0.12 + i * 0.07 }}
                  disabled={!isConnected}
                  onClick={() => sendQuery(text)}
                >
                  <Icon />
                  {text}
                </motion.button>
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
