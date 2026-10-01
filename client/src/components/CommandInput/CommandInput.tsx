import { useState, useRef, useCallback } from "react";
import { Mic, MicOff, Send, Network, Square, Activity, CloudSun, Clock, Newspaper, Eye, AudioWaveform } from "lucide-react";
import { useJarvisStore } from "../../stores/jarvisStore";
import { serverMode } from "../../lib/session";

// pc : action sur la machine de Monsieur, absente de la version hébergée (VPS).
const QUICK_ACTIONS: { icon: typeof Newspaper; label: string; query: string; pc?: boolean }[] = [
  { icon: Newspaper, label: "Briefing", query: "Fais-moi le point" },
  { icon: Activity, label: "Diagnostic", query: "Fais un diagnostic complet du système", pc: true },
  { icon: CloudSun, label: "Météo", query: "Quelle est la météo à Paris ?" },
  { icon: Clock, label: "Heure", query: "Quelle heure est-il ?" },
  { icon: Eye, label: "Vision", query: "Regarde mon écran et dis-moi ce que tu vois", pc: true },
];

interface Props {
  sendText: (text: string) => void;
  toggleMic: () => Promise<void>;
  toggleLive: () => Promise<void>;
  isMicActive: boolean;
}

export function CommandInput({ sendText, toggleMic, toggleLive, isMicActive }: Props) {
  const [text, setText] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);
  const status = useJarvisStore((s) => s.status);
  const isConnected = useJarvisStore((s) => s.isConnected);
  const hasMessages = useJarvisStore((s) => s.messages.length > 0);
  const addMessage = useJarvisStore((s) => s.addMessage);
  const councilEnabled = useJarvisStore((s) => s.councilEnabled);
  const setCouncilEnabled = useJarvisStore((s) => s.setCouncilEnabled);
  const sendQuery = useJarvisStore((s) => s.sendQuery);
  const stopGeneration = useJarvisStore((s) => s.stopGeneration);
  const isBusy = status === "processing" || status === "speaking";
  const liveActive = useJarvisStore((s) => s.liveActive);
  // En LIVE, le texte tapé part aussi vers Gemini même pendant qu'il parle.
  const isDisabled = !isConnected || (isBusy && !liveActive);

  const handleSubmit = useCallback(() => {
    if (!text.trim() || isDisabled) return;
    addMessage({ id: crypto.randomUUID(), role: "user", content: text, timestamp: Date.now() });
    sendText(text);
    setText("");
    inputRef.current?.focus();
  }, [text, isDisabled, addMessage, sendText]);

  const placeholder = !isConnected
    ? "Hors ligne — connexion…"
    : isMicActive
      ? "Parlez maintenant…"
      : "Demandez à JARVIS…";

  return (
    <>
      {isBusy && !liveActive ? (
        <div className="busy">
          {status === "processing" ? "TRAITEMENT" : "SYNTHÈSE VOCALE"}
          <span className="bar" />
          <button className="btn btn-stop" onClick={stopGeneration} title="Interrompre JARVIS">
            <Square fill="currentColor" />Stop
          </button>
        </div>
      ) : (
        isConnected && hasMessages && (
          <div className="suggestions">
            {QUICK_ACTIONS.filter((a) => !(a.pc && serverMode() === "hosted")).map(({ icon: Icon, label, query }) => (
              <button key={label} onClick={() => sendQuery(query)}>
                <Icon />{label}
              </button>
            ))}
          </div>
        )
      )}

      <form className="chat-input" onSubmit={(e) => { e.preventDefault(); handleSubmit(); }}>
        <div className={`input-pill${isMicActive ? " mic-on" : ""}`}>
          <input
            ref={inputRef}
            data-jarvis-input
            value={text}
            onChange={(e) => setText(e.target.value)}
            disabled={isDisabled}
            placeholder={placeholder}
            maxLength={4000}
            autoFocus
          />
          <button
            type="button"
            className={`icon-btn${councilEnabled ? " on-violet" : ""}`}
            onClick={() => setCouncilEnabled(!councilEnabled)}
            title={councilEnabled
              ? "Conseil multi-IA actif : toutes les IA répondent, la meilleure réponse est arbitrée"
              : "Activer le conseil multi-IA"}
            aria-pressed={councilEnabled}
          >
            <Network />
          </button>
          <button
            type="button"
            className={`icon-btn${liveActive ? " on-red" : ""}`}
            onClick={() => void toggleLive()}
            disabled={!isConnected}
            title={liveActive ? "Terminer la conversation LIVE" : "Conversation vocale temps réel (Gemini Live, clé Gemini requise)"}
            aria-pressed={liveActive}
          >
            <AudioWaveform />
          </button>
          <button
            type="button"
            className={`icon-btn${isMicActive ? " on-green" : ""}`}
            onClick={() => void toggleMic()}
            disabled={!isConnected}
            title={isMicActive ? "Couper le micro" : "Activer le micro"}
            aria-pressed={isMicActive}
          >
            {isMicActive ? <Mic /> : <MicOff />}
          </button>
        </div>
        <button type="submit" className="btn btn-primary" disabled={!text.trim() || isDisabled} title="Envoyer (Entrée)">
          <Send />
          <span className="send-label">Envoyer</span>
        </button>
      </form>
    </>
  );
}
