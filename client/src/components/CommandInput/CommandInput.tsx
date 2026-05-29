import { useState, useRef, useCallback } from "react";
import { Mic, MicOff, Send, Zap, CheckCircle } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { useJarvis } from "../../hooks/useJarvis";
import { useJarvisStore } from "../../stores/jarvisStore";

export function CommandInput() {
  const [text, setText] = useState("");
  const [sent, setSent] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const { sendText, toggleMic, isMicActive } = useJarvis();
  const status = useJarvisStore((s) => s.status);
  const isConnected = useJarvisStore((s) => s.isConnected);
  const addMessage = useJarvisStore((s) => s.addMessage);
  const isDisabled = !isConnected || status === "processing" || status === "speaking";

  const handleSubmit = useCallback(() => {
    if (!text.trim() || isDisabled) return;
    addMessage({
      id: crypto.randomUUID(),
      role: "user",
      content: text,
      timestamp: Date.now(),
    });
    sendText(text);
    setText("");
    setSent(true);
    setTimeout(() => setSent(false), 1500);
    inputRef.current?.focus();
  }, [text, isDisabled, addMessage, sendText]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const activeColor = isMicActive ? "#00ff88" : "#00d4ff";

  return (
    <div className="relative px-4 pb-4 pt-2">
      {/* Top separator line */}
      <div className="absolute top-0 left-4 right-4 h-px" style={{ background: "linear-gradient(90deg, transparent, #00d4ff33, transparent)" }} />

      {/* Processing indicator */}
      <AnimatePresence>
        {isDisabled && (
          <motion.div
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -4 }}
            className="flex items-center gap-2 mb-2 px-1"
          >
            <Zap size={10} className="text-amber-400" />
            <span className="text-[9px] tracking-widest text-amber-400/70">
              {status === "processing" ? "TRAITEMENT EN COURS..." : "SYNTHÈSE VOCALE..."}
            </span>
            <motion.div
              className="flex-1 h-px"
              style={{ background: "linear-gradient(90deg, #ffaa0033, transparent)" }}
            />
          </motion.div>
        )}
      </AnimatePresence>

      {/* Input container */}
      <div
        className="flex items-center gap-3 px-4 py-3 relative"
        style={{
          background: "linear-gradient(135deg, rgba(0,20,50,0.8), rgba(0,10,30,0.9))",
          border: `1px solid ${isMicActive ? "#00ff8844" : "#00d4ff22"}`,
          borderRadius: "4px",
          backdropFilter: "blur(16px)",
          boxShadow: `0 0 20px ${activeColor}11, inset 0 0 30px #00d4ff06`,
          transition: "border-color 0.3s, box-shadow 0.3s",
        }}
      >
        {/* Left accent */}
        <div className="absolute left-0 top-2 bottom-2 w-px" style={{ background: `linear-gradient(180deg, transparent, ${activeColor}88, transparent)` }} />

        {/* Input label */}
        <span className="text-[9px] tracking-widest text-blue-400/30 shrink-0">CMD://</span>

        <input
          ref={inputRef}
          data-jarvis-input
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={isDisabled}
          placeholder={!isConnected ? "CORE OFFLINE — en attente de connexion..." : isMicActive ? "Parlez maintenant..." : "Entrez une commande..."}
          className="flex-1 bg-transparent text-cyan-100 text-sm placeholder-blue-400/30 outline-none font-mono tracking-wide"
          style={{ caretColor: activeColor }}
          autoFocus
        />

        {/* Mic button */}
        <motion.button
          whileHover={{ scale: 1.1 }}
          whileTap={{ scale: 0.9 }}
          onClick={() => void toggleMic()}
          className="p-2 rounded transition-all relative"
          style={{
            color: isMicActive ? "#00ff88" : "#00d4ff66",
            background: isMicActive ? "#00ff8811" : "transparent",
            border: `1px solid ${isMicActive ? "#00ff8833" : "transparent"}`,
          }}
          title={isMicActive ? "Arrêter le micro" : "Activer le micro"}
        >
          {isMicActive && (
            <motion.div
              className="absolute inset-0 rounded"
              style={{ background: "#00ff8811", border: "1px solid #00ff8844" }}
              animate={{ opacity: [0.5, 1, 0.5] }}
              transition={{ duration: 1, repeat: Infinity }}
            />
          )}
          {isMicActive ? <Mic size={16} /> : <MicOff size={16} />}
        </motion.button>

        {/* Send button */}
        <motion.button
          whileHover={{ scale: 1.05 }}
          whileTap={{ scale: 0.95 }}
          onClick={handleSubmit}
          disabled={!text.trim() || isDisabled}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded text-[11px] tracking-widest font-bold transition-all"
          style={{
            background: sent ? "#00ff8811" : text.trim() && !isDisabled ? "linear-gradient(135deg, #00d4ff22, #00d4ff11)" : "transparent",
            border: `1px solid ${sent ? "#00ff8833" : text.trim() && !isDisabled ? "#00d4ff44" : "#00d4ff11"}`,
            color: sent ? "#00ff88" : text.trim() && !isDisabled ? "#00d4ff" : "#00d4ff33",
            boxShadow: sent ? "0 0 12px #00ff8822" : text.trim() && !isDisabled ? "0 0 12px #00d4ff22" : "none",
          }}
        >
          <AnimatePresence mode="wait">
            {sent ? (
              <motion.span
                key="ok"
                initial={{ scale: 0 }}
                animate={{ scale: 1 }}
                exit={{ scale: 0 }}
                className="flex items-center gap-1.5"
              >
                <CheckCircle size={13} />
                ENVOYÉ
              </motion.span>
            ) : (
              <motion.span key="send" className="flex items-center gap-1.5">
                <Send size={13} />
                ENVOYER
              </motion.span>
            )}
          </AnimatePresence>
        </motion.button>
      </div>

      {/* Bottom hint */}
      <div className="flex justify-center gap-6 mt-1.5">
        <span className="text-[9px] text-blue-400/20 tracking-widest">ENTRÉE pour envoyer</span>
        <span className="text-[9px] text-blue-400/15">·</span>
        <span className="text-[9px] text-blue-400/20 tracking-widest">MIC pour parler</span>
      </div>
    </div>
  );
}
