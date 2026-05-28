import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Settings, X, Volume2, VolumeX, Mic } from "lucide-react";
import { useJarvisStore } from "../../stores/jarvisStore";

interface VoiceOption {
  id: string;
  label: string;
  description: string;
}

const VOICE_OPTIONS: VoiceOption[] = [
  { id: "fr_FR-upmc-medium",  label: "UPMC Medium",  description: "Voix masculine française classique" },
  { id: "fr_FR-mls-medium",   label: "MLS Medium",   description: "Voix naturelle multi-locuteurs" },
  { id: "fr_FR-siwis-medium", label: "SIWIS Medium",  description: "Voix féminine claire et nette" },
];

export function SettingsPanel() {
  const [open, setOpen] = useState(false);
  const ttsEnabled = useJarvisStore((s) => s.ttsEnabled);
  const selectedVoice = useJarvisStore((s) => s.selectedVoice);
  const setTtsEnabled = useJarvisStore((s) => s.setTtsEnabled);
  const setSelectedVoice = useJarvisStore((s) => s.setSelectedVoice);
  const wsSend = useJarvisStore((s) => s.wsSend);
  const [availableVoices, setAvailableVoices] = useState<string[]>([]);

  useEffect(() => {
    fetch("http://127.0.0.1:8765/api/voices")
      .then((r) => r.json())
      .then((d) => setAvailableVoices(d.voices ?? []))
      .catch(() => setAvailableVoices(["fr_FR-upmc-medium"]));
  }, [open]);

  const applyVoice = (voiceId: string) => {
    setSelectedVoice(voiceId);
    wsSend?.({ type: "set_voice", payload: { voice: voiceId } });
  };

  const toggleTts = () => {
    const next = !ttsEnabled;
    setTtsEnabled(next);
    wsSend?.({ type: "set_tts", payload: { enabled: next } });
  };

  return (
    <>
      {/* Settings button */}
      <motion.button
        whileHover={{ scale: 1.1 }}
        whileTap={{ scale: 0.9 }}
        onClick={() => setOpen((v) => !v)}
        className="w-7 h-7 flex items-center justify-center rounded text-blue-400/40 hover:text-cyan-400 hover:bg-cyan-400/10 transition-colors"
        title="Paramètres"
      >
        <Settings size={14} />
      </motion.button>

      <AnimatePresence>
        {open && (
          <>
            {/* Backdrop */}
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="fixed inset-0 z-40"
              onClick={() => setOpen(false)}
            />

            {/* Panel */}
            <motion.div
              initial={{ opacity: 0, x: 20, scale: 0.95 }}
              animate={{ opacity: 1, x: 0, scale: 1 }}
              exit={{ opacity: 0, x: 20, scale: 0.95 }}
              transition={{ duration: 0.2 }}
              className="fixed top-12 right-4 z-50 w-72"
              style={{
                background: "linear-gradient(135deg, rgba(0,15,40,0.97), rgba(0,8,25,0.99))",
                border: "1px solid rgba(0,212,255,0.2)",
                borderRadius: "4px",
                backdropFilter: "blur(20px)",
                boxShadow: "0 0 40px #00d4ff11, 0 20px 60px rgba(0,0,0,0.8)",
              }}
            >
              {/* Header */}
              <div className="flex items-center justify-between px-4 py-3 border-b border-cyan-900/30">
                <div className="flex items-center gap-2">
                  <Settings size={12} className="text-cyan-400/60" />
                  <span className="text-[11px] tracking-widest text-cyan-400/80 font-bold">PARAMÈTRES</span>
                </div>
                <button onClick={() => setOpen(false)} className="text-blue-400/40 hover:text-red-400 transition-colors">
                  <X size={14} />
                </button>
              </div>

              <div className="p-4 flex flex-col gap-5">
                {/* TTS Toggle */}
                <div className="flex flex-col gap-2">
                  <div className="text-[9px] tracking-widest text-blue-400/40">SYNTHÈSE VOCALE</div>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      {ttsEnabled
                        ? <Volume2 size={14} className="text-cyan-400" />
                        : <VolumeX size={14} className="text-blue-400/40" />
                      }
                      <span className="text-xs text-cyan-100/70">
                        {ttsEnabled ? "Voix activée" : "Voix désactivée"}
                      </span>
                    </div>
                    <button
                      onClick={toggleTts}
                      className="relative w-10 h-5 rounded-full transition-all"
                      style={{
                        background: ttsEnabled ? "rgba(0,212,255,0.3)" : "rgba(255,255,255,0.05)",
                        border: `1px solid ${ttsEnabled ? "rgba(0,212,255,0.5)" : "rgba(255,255,255,0.1)"}`,
                      }}
                    >
                      <motion.div
                        animate={{ x: ttsEnabled ? 20 : 2 }}
                        transition={{ type: "spring", stiffness: 500, damping: 30 }}
                        className="absolute top-0.5 w-4 h-4 rounded-full"
                        style={{ background: ttsEnabled ? "#00d4ff" : "#ffffff22", boxShadow: ttsEnabled ? "0 0 8px #00d4ff" : "none" }}
                      />
                    </button>
                  </div>
                </div>

                {/* Voice selector */}
                <div className="flex flex-col gap-2">
                  <div className="text-[9px] tracking-widest text-blue-400/40">VOIX FRANÇAISE</div>
                  <div className="flex flex-col gap-1.5">
                    {VOICE_OPTIONS.filter((v) =>
                      availableVoices.length === 0 || availableVoices.includes(v.id)
                    ).map((voice) => {
                      const isSelected = selectedVoice === voice.id;
                      return (
                        <button
                          key={voice.id}
                          onClick={() => applyVoice(voice.id)}
                          className="flex items-start gap-3 p-2.5 rounded text-left transition-all"
                          style={{
                            background: isSelected ? "rgba(0,212,255,0.1)" : "rgba(255,255,255,0.02)",
                            border: `1px solid ${isSelected ? "rgba(0,212,255,0.3)" : "rgba(255,255,255,0.05)"}`,
                          }}
                        >
                          <div
                            className="mt-0.5 w-2 h-2 rounded-full flex-shrink-0"
                            style={{
                              background: isSelected ? "#00d4ff" : "transparent",
                              border: `1px solid ${isSelected ? "#00d4ff" : "rgba(255,255,255,0.2)"}`,
                              boxShadow: isSelected ? "0 0 6px #00d4ff" : "none",
                            }}
                          />
                          <div>
                            <div className="text-[11px] font-bold tracking-wider" style={{ color: isSelected ? "#00d4ff" : "#ffffff66" }}>
                              {voice.label}
                            </div>
                            <div className="text-[9px] text-blue-400/30 mt-0.5">{voice.description}</div>
                          </div>
                        </button>
                      );
                    })}
                  </div>
                </div>

                {/* Mic info */}
                <div className="flex flex-col gap-2 pt-1 border-t border-cyan-900/20">
                  <div className="text-[9px] tracking-widest text-blue-400/40">MICROPHONE</div>
                  <div className="flex items-center gap-2 text-[10px] text-blue-400/50">
                    <Mic size={11} />
                    <span>Cliquer sur le micro pour activer · Recliquer pour envoyer</span>
                  </div>
                </div>
              </div>

              {/* Bottom accent */}
              <div className="h-px mx-4 mb-3" style={{ background: "linear-gradient(90deg, transparent, #00d4ff22, transparent)" }} />
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </>
  );
}
