import { useState, useEffect, useRef } from "react";
import { createPortal } from "react-dom";
import { motion, AnimatePresence } from "framer-motion";
import { Settings, X, Volume2, VolumeX, Mic, Globe, Mail, CheckCircle, AlertCircle, Upload, Cpu, Ear, Gauge, Palette, Shield, Brain } from "lucide-react";
import { openUrl } from "@tauri-apps/plugin-opener";
import { useJarvisStore } from "../../stores/jarvisStore";
import { ProvidersTab } from "./ProvidersTab";
import { PerfTab } from "./PerfTab";
import { ThemeTab } from "./ThemeTab";
import { MemoryTab } from "./MemoryTab";

interface VoiceOption {
  id: string;
  label: string;
  description: string;
}

// Voix masculines uniquement — l'identité vocale JARVIS
const VOICE_OPTIONS: VoiceOption[] = [
  { id: "gemini:Charon", label: "Charon — Gemini", description: "Voix grave et posée, ton de majordome IA (clé Gemini de l'onglet Cerveau)" },
  { id: "gemini:Orus", label: "Orus — Gemini", description: "Voix ferme et assurée, très « armure » (clé Gemini)" },
  { id: "gemini:Iapetus", label: "Iapetus — Gemini", description: "Voix claire et précise (clé Gemini)" },
  { id: "edge:fr-FR-HenriNeural", label: "Henri — Neural", description: "Voix masculine profonde et naturelle, esprit JARVIS (en ligne, secours local auto)" },
  { id: "edge:fr-FR-RemyMultilingualNeural", label: "Rémy — Neural", description: "Voix masculine jeune et fluide (en ligne, secours local auto)" },
  { id: "fr_FR-upmc-medium",  label: "UPMC — Local",  description: "Voix masculine française 100 % hors-ligne" },
];

type GmailStatus = "loading" | "non_configured" | "not_authenticated" | "connected";

export function SettingsPanel() {
  const [open, setOpen] = useState(false);
  const [activeTab, setActiveTab] = useState<"voice" | "brain" | "memory" | "perf" | "theme" | "services">("voice");

  const ttsEnabled = useJarvisStore((s) => s.ttsEnabled);
  const selectedVoice = useJarvisStore((s) => s.selectedVoice);
  const setTtsEnabled = useJarvisStore((s) => s.setTtsEnabled);
  const setSelectedVoice = useJarvisStore((s) => s.setSelectedVoice);
  const wakeWordEnabled = useJarvisStore((s) => s.wakeWordEnabled);
  const wakeWordAvailable = useJarvisStore((s) => s.wakeWordAvailable);
  const setWakeWordEnabled = useJarvisStore((s) => s.setWakeWordEnabled);
  const armorFx = useJarvisStore((s) => s.armorFx);
  const setArmorFx = useJarvisStore((s) => s.setArmorFx);
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
    { id: "voice" as const, label: "Voix", icon: <Volume2 /> },
    { id: "brain" as const, label: "Cerveau", icon: <Cpu /> },
    { id: "memory" as const, label: "Mémoire", icon: <Brain /> },
    { id: "perf" as const, label: "Performances", icon: <Gauge /> },
    { id: "theme" as const, label: "Apparence", icon: <Palette /> },
    { id: "services" as const, label: "Services", icon: <Globe /> },
  ];

  return (
    <>
      <button className="icon-btn" onClick={() => setOpen((v) => !v)} title="Paramètres" aria-label="Paramètres">
        <Settings />
      </button>

      {createPortal(
      <AnimatePresence>
        {open && (
          /* Portal vers body : un ancêtre avec backdrop-filter piégerait cette modale `fixed` */
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="modal-backdrop"
            onPointerDown={(e) => { if (e.target === e.currentTarget) setOpen(false); }}
          >
            <motion.div
              initial={{ opacity: 0, scale: 0.95, y: 16 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 16 }}
              transition={{ duration: 0.22, ease: [0.16, 1, 0.3, 1] }}
              className="modal"
              role="dialog"
              aria-label="Paramètres"
              onPointerDown={(e) => e.stopPropagation()}
            >
                <div className="modal-head">
                  <h2>PARAMÈTRES</h2>
                  <button className="icon-btn" onClick={() => setOpen(false)} title="Fermer" aria-label="Fermer">
                    <X />
                  </button>
                </div>

                <div className="modal-tabs" role="tablist">
                  {tabs.map((tab) => (
                    <button
                      key={tab.id}
                      role="tab"
                      aria-selected={activeTab === tab.id}
                      onClick={() => setActiveTab(tab.id)}
                    >
                      {tab.icon}
                      {tab.label}
                    </button>
                  ))}
                </div>

                <div className="modal-body">
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
                              background: ttsEnabled ? "rgb(var(--accent-rgb) / 0.3)" : "rgba(255,255,255,0.05)",
                              border: `1px solid ${ttsEnabled ? "rgb(var(--accent-rgb) / 0.5)" : "rgba(255,255,255,0.1)"}`,
                            }}
                          >
                            <motion.div
                              animate={{ x: ttsEnabled ? 20 : 2 }}
                              transition={{ type: "spring", stiffness: 500, damping: 30 }}
                              className="absolute top-0.5 w-4 h-4 rounded-full"
                              style={{ background: ttsEnabled ? "var(--accent)" : "#ffffff22", boxShadow: ttsEnabled ? "0 0 8px var(--accent)" : "none" }}
                            />
                          </button>
                        </div>
                      </div>

                      {/* Voice selector */}
                      <div className="flex flex-col gap-2">
                        <div className="text-[9px] tracking-widest text-blue-400/40">VOIX FRANÇAISE</div>
                        <div className="flex flex-col gap-1.5">
                          {VOICE_OPTIONS.filter((v) =>
                            v.id.startsWith("edge:") ||
                            v.id.startsWith("gemini:") ||
                            availableVoices.length === 0 ||
                            availableVoices.includes(v.id)
                          ).map((voice) => {
                            const isSelected = selectedVoice === voice.id;
                            return (
                              <button
                                key={voice.id}
                                onClick={() => applyVoice(voice.id)}
                                className="flex items-start gap-3 p-2.5 rounded text-left transition-all"
                                style={{
                                  background: isSelected ? "rgb(var(--accent-rgb) / 0.1)" : "rgba(255,255,255,0.02)",
                                  border: `1px solid ${isSelected ? "rgb(var(--accent-rgb) / 0.3)" : "rgba(255,255,255,0.05)"}`,
                                }}
                              >
                                <div
                                  className="mt-0.5 w-2 h-2 rounded-full flex-shrink-0"
                                  style={{
                                    background: isSelected ? "var(--accent)" : "transparent",
                                    border: `1px solid ${isSelected ? "var(--accent)" : "rgba(255,255,255,0.2)"}`,
                                    boxShadow: isSelected ? "0 0 6px var(--accent)" : "none",
                                  }}
                                />
                                <div>
                                  <div className="text-[11px] font-bold tracking-wider" style={{ color: isSelected ? "var(--accent)" : "#ffffff66" }}>
                                    {voice.label}
                                  </div>
                                  <div className="text-[9px] text-blue-400/30 mt-0.5">{voice.description}</div>
                                </div>
                              </button>
                            );
                          })}
                        </div>
                      </div>

                      {/* Effet armure façon film */}
                      <div className="flex flex-col gap-2 pt-1 border-t border-cyan-900/20">
                        <div className="text-[9px] tracking-widest text-blue-400/40">EFFET « ARMURE » (TIMBRE DU FILM)</div>
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            <Shield size={14} className={armorFx ? "text-cyan-400" : "text-blue-400/40"} />
                            <span className="text-xs text-cyan-100/70">
                              {armorFx ? "Résonance métallique active" : "Voix naturelle sans traitement"}
                            </span>
                          </div>
                          <button
                            onClick={() => setArmorFx(!armorFx)}
                            className="relative w-10 h-5 rounded-full transition-all"
                            style={{
                              background: armorFx ? "rgb(var(--accent-rgb) / 0.3)" : "rgba(255,255,255,0.05)",
                              border: `1px solid ${armorFx ? "rgb(var(--accent-rgb) / 0.5)" : "rgba(255,255,255,0.1)"}`,
                            }}
                          >
                            <motion.div
                              animate={{ x: armorFx ? 20 : 2 }}
                              transition={{ type: "spring", stiffness: 500, damping: 30 }}
                              className="absolute top-0.5 w-4 h-4 rounded-full"
                              style={{ background: armorFx ? "var(--accent)" : "#ffffff22", boxShadow: armorFx ? "0 0 8px var(--accent)" : "none" }}
                            />
                          </button>
                        </div>
                        <p className="text-[8px] text-blue-400/25 leading-relaxed">
                          Reproduit le traitement haut-parleur de l'IA du film : résonances métalliques et bande passante resserrée, mixées sous la voix claire.
                        </p>
                      </div>

                      {/* Wake word toggle */}
                      <div className="flex flex-col gap-2 pt-1 border-t border-cyan-900/20">
                        <div className="text-[9px] tracking-widest text-blue-400/40">WAKE WORD « HEY JARVIS »</div>
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            <Ear size={14} className={wakeWordEnabled ? "text-cyan-400" : "text-blue-400/40"} />
                            <span className="text-xs text-cyan-100/70">
                              {!wakeWordAvailable
                                ? "Indisponible sur ce serveur"
                                : wakeWordEnabled
                                ? "Veille active — dites « Hey Jarvis »"
                                : "Veille désactivée"}
                            </span>
                          </div>
                          <button
                            onClick={() => setWakeWordEnabled(!wakeWordEnabled)}
                            disabled={!wakeWordAvailable}
                            className="relative w-10 h-5 rounded-full transition-all disabled:opacity-30"
                            style={{
                              background: wakeWordEnabled ? "rgb(var(--accent-rgb) / 0.3)" : "rgba(255,255,255,0.05)",
                              border: `1px solid ${wakeWordEnabled ? "rgb(var(--accent-rgb) / 0.5)" : "rgba(255,255,255,0.1)"}`,
                            }}
                          >
                            <motion.div
                              animate={{ x: wakeWordEnabled ? 20 : 2 }}
                              transition={{ type: "spring", stiffness: 500, damping: 30 }}
                              className="absolute top-0.5 w-4 h-4 rounded-full"
                              style={{ background: wakeWordEnabled ? "var(--accent)" : "#ffffff22", boxShadow: wakeWordEnabled ? "0 0 8px var(--accent)" : "none" }}
                            />
                          </button>
                        </div>
                        <p className="text-[8px] text-blue-400/25 leading-relaxed">
                          L'audio de veille est analysé localement pour le mot-clé uniquement — jamais transcrit ni conservé.
                        </p>
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

                  {/* ── BRAIN TAB ── */}
                  {activeTab === "brain" && <ProvidersTab />}

                  {/* ── PERF TAB ── */}
                  {activeTab === "memory" && <MemoryTab />}

                  {activeTab === "perf" && <PerfTab />}

                  {/* ── THEME TAB ── */}
                  {activeTab === "theme" && <ThemeTab />}

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
                              style={{ background: "rgb(var(--accent-rgb) / 0.08)", border: "1px solid rgb(var(--accent-rgb) / 0.2)", color: "var(--accent)" }}
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
                              style={{ background: "rgb(var(--accent-rgb) / 0.08)", border: "1px solid rgb(var(--accent-rgb) / 0.25)", color: "var(--accent)" }}
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

            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>,
      document.body)}
    </>
  );
}
