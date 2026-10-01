import { useState, useEffect, useRef } from "react";
import { createPortal } from "react-dom";
import { motion, AnimatePresence } from "framer-motion";
import { Settings, X, Volume2, Globe, Mail, CheckCircle, AlertCircle, Upload, Cpu, Ear, Gauge, Palette, Shield, Brain, Wrench, Play } from "lucide-react";
import { SERVER_ORIGIN, gmailRedirectUri, openExternal } from "../../lib/platform";
import { useJarvisStore } from "../../stores/jarvisStore";
import { ProvidersTab } from "./ProvidersTab";
import { PerfTab } from "./PerfTab";
import { ThemeTab } from "./ThemeTab";
import { MemoryTab } from "./MemoryTab";
import { VoiceInputSection } from "./VoiceInputSection";
import { EnginesTab } from "./EnginesTab";
import { Row, Section, Toggle } from "./controls";

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
  const [activeTab, setActiveTab] = useState<"voice" | "brain" | "engines" | "memory" | "perf" | "theme" | "services">("voice");

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
    fetch(`${SERVER_ORIGIN}/api/voices`)
      .then((r) => r.json())
      .then((d) => setAvailableVoices(d.voices ?? []))
      .catch(() => setAvailableVoices(["fr_FR-upmc-medium"]));
  }, []);

  useEffect(() => {
    if (!open) return;
    fetch(`${SERVER_ORIGIN}/api/auth/gmail/status`)
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
    const res = await fetch(`${SERVER_ORIGIN}/api/auth/gmail/upload_credentials`, {
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
    await openExternal(gmailAuthUrl);
    // Poll status after a delay to detect when auth completes
    setTimeout(() => {
      fetch(`${SERVER_ORIGIN}/api/auth/gmail/status`)
        .then((r) => r.json())
        .then((d) => {
          setGmailStatus(d.status as GmailStatus);
          setGmailAuthUrl(d.auth_url ?? null);
        });
    }, 8000);
  };

  const disconnectGmail = async () => {
    await fetch(`${SERVER_ORIGIN}/api/auth/gmail/disconnect`, { method: "DELETE" });
    setGmailStatus("not_authenticated");
    const r = await fetch(`${SERVER_ORIGIN}/api/auth/gmail/status`);
    const d = await r.json();
    setGmailAuthUrl(d.auth_url ?? null);
  };

  const tabs = [
    { id: "voice" as const, label: "Voix", icon: <Volume2 /> },
    { id: "brain" as const, label: "Cerveau", icon: <Cpu /> },
    { id: "engines" as const, label: "Moteurs", icon: <Wrench /> },
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
                      <Section title="Voix de JARVIS">
                        <Row label={ttsEnabled ? "Voix activée" : "Voix désactivée"} hint="JARVIS lit ses réponses à voix haute.">
                          <Toggle label="Voix activée" checked={ttsEnabled} onChange={toggleTts} />
                        </Row>
                        <div className="set-providers">
                          {VOICE_OPTIONS.filter((v) =>
                            v.id.startsWith("edge:") ||
                            v.id.startsWith("gemini:") ||
                            availableVoices.length === 0 ||
                            availableVoices.includes(v.id)
                          ).map((voice) => {
                            const isSelected = selectedVoice === voice.id;
                            return (
                              <div key={voice.id} className={`set-pcard${isSelected ? " is-active" : ""}`}>
                                <div className="set-pcard-head">
                                  <button type="button" className="set-voice-pick" aria-pressed={isSelected} onClick={() => applyVoice(voice.id)}>
                                    <i className={isSelected ? "pdot ok" : "pdot"} />
                                    <span className="set-provider-text">
                                      <strong>{voice.label}</strong>
                                      <small>{voice.description}</small>
                                    </span>
                                  </button>
                                  {isSelected && <span className="set-status ok"><CheckCircle size={14} /> Choisie</span>}
                                  <button
                                    type="button"
                                    className="btn btn-ghost btn-sm"
                                    disabled={!wsSend}
                                    title="Écouter cette voix"
                                    onClick={() => {
                                      applyVoice(voice.id);
                                      wsSend?.({ type: "preview_voice", payload: {} });
                                    }}
                                  >
                                    <Play />Écouter
                                  </button>
                                </div>
                              </div>
                            );
                          })}
                        </div>
                      </Section>

                      <Section title="Effets et veille">
                        <Row
                          label={<><Shield size={14} /> Effet « armure »</>}
                          hint="Timbre du film : résonances métalliques et bande passante resserrée, mixées sous la voix claire."
                        >
                          <Toggle label="Effet armure" checked={armorFx} onChange={setArmorFx} />
                        </Row>
                        <Row
                          label={<><Ear size={14} /> Veille « Hey Jarvis »</>}
                          hint={!wakeWordAvailable
                            ? "Indisponible sur ce serveur (modèle de mot-clé absent)."
                            : "L'audio de veille est analysé localement pour le mot-clé uniquement — jamais transcrit ni conservé."}
                        >
                          <Toggle
                            label="Veille Hey Jarvis"
                            checked={wakeWordEnabled}
                            disabled={!wakeWordAvailable}
                            onChange={setWakeWordEnabled}
                          />
                        </Row>
                      </Section>

                      {/* Micro et reconnaissance vocale */}
                      <VoiceInputSection />
                    </>
                  )}

                  {/* ── BRAIN TAB ── */}
                  {activeTab === "brain" && <ProvidersTab />}

                  {activeTab === "engines" && <EnginesTab />}

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
                                  <li>Ajoutez {gmailRedirectUri()} dans redirect URIs</li>
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
