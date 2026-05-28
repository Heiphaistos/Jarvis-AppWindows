import { useState, useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Settings, X, Volume2, VolumeX, Mic, Globe, Mail, CheckCircle, AlertCircle, Upload } from "lucide-react";
import { openUrl } from "@tauri-apps/plugin-opener";
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

type GmailStatus = "loading" | "non_configured" | "not_authenticated" | "connected";

export function SettingsPanel() {
  const [open, setOpen] = useState(false);
  const [activeTab, setActiveTab] = useState<"voice" | "services">("voice");

  const ttsEnabled = useJarvisStore((s) => s.ttsEnabled);
  const selectedVoice = useJarvisStore((s) => s.selectedVoice);
  const setTtsEnabled = useJarvisStore((s) => s.setTtsEnabled);
  const setSelectedVoice = useJarvisStore((s) => s.setSelectedVoice);
  const wsSend = useJarvisStore((s) => s.wsSend);
  const [availableVoices, setAvailableVoices] = useState<string[]>([]);

  // Gmail state
  const [gmailStatus, setGmailStatus] = useState<GmailStatus>("loading");
  const [gmailAuthUrl, setGmailAuthUrl] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    fetch("http://127.0.0.1:8765/api/voices")
      .then((r) => r.json())
      .then((d) => setAvailableVoices(d.voices ?? []))
      .catch(() => setAvailableVoices(["fr_FR-upmc-medium"]));
  }, []);

  useEffect(() => {
    if (!open) return;
    fetch("http://127.0.0.1:8765/api/auth/gmail/status")
      .then((r) => r.json())
      .then((d) => {
        setGmailStatus(d.status as GmailStatus);
        setGmailAuthUrl(d.auth_url ?? null);
      })
      .catch(() => setGmailStatus("non_configured"));
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

  const handleCredentialsUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const fd = new FormData();
    fd.append("file", file);
    const res = await fetch("http://127.0.0.1:8765/api/auth/gmail/upload_credentials", {
      method: "POST",
      body: fd,
    });
    const data = await res.json();
    if (data.auth_url) {
      setGmailStatus("not_authenticated");
      setGmailAuthUrl(data.auth_url);
    }
  };

  const connectGmail = async () => {
    if (!gmailAuthUrl) return;
    await openUrl(gmailAuthUrl);
    // Poll status after a delay to detect when auth completes
    setTimeout(() => {
      fetch("http://127.0.0.1:8765/api/auth/gmail/status")
        .then((r) => r.json())
        .then((d) => {
          setGmailStatus(d.status as GmailStatus);
          setGmailAuthUrl(d.auth_url ?? null);
        });
    }, 8000);
  };

  const disconnectGmail = async () => {
    await fetch("http://127.0.0.1:8765/api/auth/gmail/disconnect", { method: "DELETE" });
    setGmailStatus("not_authenticated");
    const r = await fetch("http://127.0.0.1:8765/api/auth/gmail/status");
    const d = await r.json();
    setGmailAuthUrl(d.auth_url ?? null);
  };

  const tabs = [
    { id: "voice" as const, label: "VOIX", icon: <Volume2 size={11} /> },
    { id: "services" as const, label: "SERVICES", icon: <Globe size={11} /> },
  ];

  return (
    <>
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
          /* Single full-screen container: backdrop click closes, inner panel stops propagation */
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 flex items-center justify-center"
            style={{ background: "rgba(0,0,0,0.6)", backdropFilter: "blur(4px)" }}
            onPointerDown={(e) => { if (e.target === e.currentTarget) setOpen(false); }}
          >
            <motion.div
              initial={{ opacity: 0, scale: 0.92, y: 20 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.92, y: 20 }}
              transition={{ duration: 0.2, ease: "easeOut" }}
              className="w-[380px]"
              onPointerDown={(e) => e.stopPropagation()}
              style={{
                  background: "linear-gradient(135deg, rgba(0,15,40,0.98), rgba(0,8,25,0.99))",
                  border: "1px solid rgba(0,212,255,0.2)",
                  borderRadius: "6px",
                  backdropFilter: "blur(24px)",
                  boxShadow: "0 0 60px #00d4ff18, 0 30px 80px rgba(0,0,0,0.9)",
                }}
              >
                {/* Header */}
                <div className="flex items-center justify-between px-5 py-3 border-b border-cyan-900/30">
                  <div className="flex items-center gap-2">
                    <Settings size={12} className="text-cyan-400/60" />
                    <span className="text-[11px] tracking-widest text-cyan-400/80 font-bold">PARAMÈTRES J.A.R.V.I.S.</span>
                  </div>
                  <button onClick={() => setOpen(false)} className="text-blue-400/40 hover:text-red-400 transition-colors">
                    <X size={14} />
                  </button>
                </div>

                {/* Tabs */}
                <div className="flex border-b border-cyan-900/20">
                  {tabs.map((tab) => (
                    <button
                      key={tab.id}
                      onClick={() => setActiveTab(tab.id)}
                      className="flex-1 flex items-center justify-center gap-1.5 py-2.5 text-[9px] tracking-widest transition-all"
                      style={{
                        color: activeTab === tab.id ? "#00d4ff" : "#ffffff30",
                        borderBottom: activeTab === tab.id ? "1px solid #00d4ff" : "1px solid transparent",
                        background: activeTab === tab.id ? "rgba(0,212,255,0.05)" : "transparent",
                      }}
                    >
                      {tab.icon}
                      {tab.label}
                    </button>
                  ))}
                </div>

                <div className="p-5 flex flex-col gap-5 max-h-[70vh] overflow-y-auto">
                  {/* ── VOICE TAB ── */}
                  {activeTab === "voice" && (
                    <>
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
                    </>
                  )}

                  {/* ── SERVICES TAB ── */}
                  {activeTab === "services" && (
                    <div className="flex flex-col gap-4">
                      {/* Web Search */}
                      <div className="flex flex-col gap-2">
                        <div className="text-[9px] tracking-widest text-blue-400/40">RECHERCHE WEB</div>
                        <div className="flex items-center gap-3 p-3 rounded" style={{ background: "rgba(0,255,136,0.05)", border: "1px solid rgba(0,255,136,0.15)" }}>
                          <CheckCircle size={14} className="text-green-400 shrink-0" />
                          <div>
                            <div className="text-[11px] font-bold text-green-400 tracking-wider">DuckDuckGo</div>
                            <div className="text-[9px] text-blue-400/40 mt-0.5">Recherche web active · Dites "cherche X sur internet"</div>
                          </div>
                        </div>
                      </div>

                      {/* Gmail */}
                      <div className="flex flex-col gap-2">
                        <div className="text-[9px] tracking-widest text-blue-400/40">EMAIL — GMAIL</div>

                        {gmailStatus === "loading" && (
                          <div className="text-[10px] text-blue-400/40 text-center py-3">Vérification...</div>
                        )}

                        {gmailStatus === "connected" && (
                          <div className="flex flex-col gap-2">
                            <div className="flex items-center gap-3 p-3 rounded" style={{ background: "rgba(0,255,136,0.05)", border: "1px solid rgba(0,255,136,0.15)" }}>
                              <Mail size={14} className="text-green-400 shrink-0" />
                              <div className="flex-1">
                                <div className="text-[11px] font-bold text-green-400 tracking-wider">Gmail connecté</div>
                                <div className="text-[9px] text-blue-400/40 mt-0.5">Dites "lis mes emails" ou "envoie un email à..."</div>
                              </div>
                            </div>
                            <button
                              onClick={disconnectGmail}
                              className="text-[9px] tracking-widest text-red-400/50 hover:text-red-400 transition-colors text-center py-1"
                            >
                              Déconnecter
                            </button>
                          </div>
                        )}

                        {gmailStatus === "non_configured" && (
                          <div className="flex flex-col gap-3">
                            <div className="flex items-start gap-2 p-3 rounded text-[9px] text-blue-400/50" style={{ background: "rgba(255,170,0,0.05)", border: "1px solid rgba(255,170,0,0.15)" }}>
                              <AlertCircle size={12} className="text-amber-400 shrink-0 mt-0.5" />
                              <div>
                                <div className="text-amber-400 font-bold mb-1">Configuration requise</div>
                                <ol className="list-decimal ml-3 space-y-0.5 text-[8px]">
                                  <li>Allez sur console.cloud.google.com</li>
                                  <li>Créez un projet → Activez l'API Gmail</li>
                                  <li>Credentials → OAuth 2.0 → Application Bureau</li>
                                  <li>Ajoutez localhost:8765 dans redirect URIs</li>
                                  <li>Téléchargez credentials.json</li>
                                </ol>
                              </div>
                            </div>
                            <input
                              ref={fileInputRef}
                              type="file"
                              accept=".json"
                              className="hidden"
                              onChange={handleCredentialsUpload}
                            />
                            <button
                              onClick={() => fileInputRef.current?.click()}
                              className="flex items-center justify-center gap-2 py-2.5 rounded text-[10px] tracking-widest transition-all"
                              style={{ background: "rgba(0,212,255,0.08)", border: "1px solid rgba(0,212,255,0.2)", color: "#00d4ff" }}
                            >
                              <Upload size={12} />
                              Importer credentials.json
                            </button>
                          </div>
                        )}

                        {gmailStatus === "not_authenticated" && (
                          <div className="flex flex-col gap-2">
                            <div className="text-[9px] text-blue-400/50 px-1">
                              Credentials chargés. Autorisez l'accès à votre compte Gmail.
                            </div>
                            <button
                              onClick={connectGmail}
                              className="flex items-center justify-center gap-2 py-2.5 rounded text-[10px] tracking-widest transition-all"
                              style={{ background: "rgba(0,212,255,0.08)", border: "1px solid rgba(0,212,255,0.25)", color: "#00d4ff" }}
                            >
                              <Mail size={12} />
                              Connecter Gmail
                            </button>
                            <input
                              ref={fileInputRef}
                              type="file"
                              accept=".json"
                              className="hidden"
                              onChange={handleCredentialsUpload}
                            />
                            <button
                              onClick={() => fileInputRef.current?.click()}
                              className="text-[8px] tracking-widest text-blue-400/30 hover:text-blue-400/60 transition-colors text-center"
                            >
                              Changer de credentials
                            </button>
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                </div>

                {/* Bottom accent */}
                <div className="h-px mx-5 mb-3" style={{ background: "linear-gradient(90deg, transparent, #00d4ff22, transparent)" }} />
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}
