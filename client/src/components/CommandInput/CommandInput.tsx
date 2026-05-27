import { useState, useRef, useCallback } from "react";
import { Mic, MicOff, Send } from "lucide-react";
import { motion } from "framer-motion";
import { useJarvis } from "../../hooks/useJarvis";
import { useJarvisStore } from "../../stores/jarvisStore";

export function CommandInput() {
  const [text, setText] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);
  const { sendText, toggleMic, isMicActive } = useJarvis();
  const status = useJarvisStore((s) => s.status);
  const addMessage = useJarvisStore((s) => s.addMessage);
  const isDisabled = status === "processing" || status === "speaking";

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
    inputRef.current?.focus();
  }, [text, isDisabled, addMessage, sendText]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  return (
    <div className="p-4 border-t border-cyan-900/40">
      <div
        className="flex items-center gap-2 rounded-lg border px-3 py-2"
        style={{
          background: "rgba(0, 20, 50, 0.7)",
          borderColor: isMicActive
            ? "rgba(0, 255, 136, 0.5)"
            : "rgba(0, 212, 255, 0.2)",
          backdropFilter: "blur(8px)",
        }}
      >
        <input
          ref={inputRef}
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={isDisabled}
          placeholder="Entrez une commande..."
          className="flex-1 bg-transparent text-cyan-100 text-sm placeholder-blue-400/40 outline-none font-mono"
        />

        <motion.button
          whileHover={{ scale: 1.1 }}
          whileTap={{ scale: 0.9 }}
          onClick={() => void toggleMic()}
          className={`p-1.5 rounded transition-colors ${
            isMicActive
              ? "text-green-400"
              : "text-blue-400/60 hover:text-cyan-400"
          }`}
          title={isMicActive ? "Arrêter le micro" : "Activer le micro"}
        >
          {isMicActive ? <Mic size={18} /> : <MicOff size={18} />}
        </motion.button>

        <motion.button
          whileHover={{ scale: 1.1 }}
          whileTap={{ scale: 0.9 }}
          onClick={handleSubmit}
          disabled={!text.trim() || isDisabled}
          className="p-1.5 text-cyan-400 hover:text-cyan-300 disabled:opacity-30 transition-colors"
        >
          <Send size={18} />
        </motion.button>
      </div>

      <div className="text-center text-[10px] text-blue-400/30 mt-1 tracking-widest">
        ENTRÉE pour envoyer · Maintenir MIC pour parler
      </div>
    </div>
  );
}
