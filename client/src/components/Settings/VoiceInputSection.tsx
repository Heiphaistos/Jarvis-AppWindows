import { useCallback, useEffect, useRef, useState } from "react";
import { Mic, MicOff, RefreshCw } from "lucide-react";
import { listMics, restartMic, startMic, type MicCapture, type MicDevice } from "../../lib/mic";
import { useJarvisStore } from "../../stores/jarvisStore";
import { Row, Section, Select, Slider, Status, TextField, Toggle, useRuntimeSettings } from "./controls";

const ENGINE_LABELS: Record<string, string> = {
  auto: "Automatique (cloud si une clé existe, sinon local)",
  groq: "Groq — Whisper large (rapide, gratuit)",
  openai: "OpenAI — gpt-4o-mini-transcribe",
  local: "Whisper local (hors ligne)",
};

/** Teste le micro choisi : niveau en direct, comparé au seuil de détection. */
function MicTester({ threshold }: { threshold: number }) {
  const [level, setLevel] = useState(0);
  const [active, setActive] = useState(false);
  const [error, setError] = useState("");
  const captureRef = useRef<MicCapture | null>(null);

  const stop = useCallback(async () => {
    const c = captureRef.current;
    captureRef.current = null;
    setActive(false);
    setLevel(0);
    await c?.stop();
  }, []);

  useEffect(() => () => void stop(), [stop]);

  const start = async () => {
    setError("");
    try {
      captureRef.current = await startMic((data) => {
        let sq = 0;
        for (let i = 0; i < data.length; i++) sq += data[i] * data[i];
        setLevel(Math.sqrt(sq / Math.max(1, data.length)));
      });
      setActive(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  // Échelle logarithmique : 0.0005 → 0 %, 0.2 → 100 %
  const pct = (v: number) => Math.max(0, Math.min(100, ((Math.log10(Math.max(v, 0.0005)) + 3.3) / 2.6) * 100));
  const heard = level >= threshold;

  return (
    <div className="set-meter-wrap">
      <button type="button" className="btn btn-ghost btn-sm" onClick={() => void (active ? stop() : start())}>
        {active ? <MicOff /> : <Mic />}
        {active ? "Arrêter le test" : "Tester le micro"}
      </button>
      <div className="set-meter" aria-hidden>
        <i style={{ width: `${pct(level)}%`, background: heard ? "var(--green)" : "var(--accent)" }} />
        <b style={{ left: `${pct(threshold)}%` }} title="Seuil de détection" />
      </div>
      <span className="set-hint">
        {error
          ? `Micro indisponible : ${error}`
          : active
            ? heard ? "Voix détectée ✓" : "Parlez : la barre doit dépasser le trait du seuil"
            : "La barre doit dépasser le trait quand vous parlez, et rester en dessous dans le silence."}
      </span>
    </div>
  );
}

export function VoiceInputSection() {
  const { values, update, error, saved } = useRuntimeSettings();
  const micDevice = useJarvisStore((s) => s.micDevice);
  const setMicDevice = useJarvisStore((s) => s.setMicDevice);
  const [mics, setMics] = useState<MicDevice[]>([]);
  const [micError, setMicError] = useState("");

  const refreshMics = useCallback(() => {
    setMicError("");
    listMics()
      .then(setMics)
      .catch((e) => setMicError(e instanceof Error ? e.message : String(e)));
  }, []);
  useEffect(refreshMics, [refreshMics]);

  const chooseMic = async (id: string) => {
    setMicDevice(id);
    await restartMic().catch(() => undefined);
  };

  if (!values) {
    return <Section title="Micro"><p className="set-hint">{error || "Chargement…"}</p></Section>;
  }

  const threshold = Number(values["voice.speech_threshold"]);
  const engine = String(values["voice.stt_engine"]);

  return (
    <>
      <Section title="Micro">
        <Row label="Micro utilisé" hint={micError || "Le micro par défaut du système si rien n'est choisi."}>
          <div className="flex gap-2 items-center">
            <Select
              label="Micro utilisé"
              value={micDevice}
              onChange={(v) => void chooseMic(v)}
              options={[
                { value: "", label: "Micro par défaut du système" },
                ...mics.map((m) => ({ value: m.id, label: m.isDefault ? `${m.label} (par défaut)` : m.label })),
              ]}
            />
            <button type="button" className="icon-btn" onClick={refreshMics} title="Actualiser la liste" aria-label="Actualiser la liste des micros">
              <RefreshCw />
            </button>
          </div>
        </Row>
        <MicTester threshold={threshold} />
        <Row label="Sensibilité" hint="Plus bas = capte les voix faibles ; plus haut = ignore le bruit de fond.">
          <Slider
            label="Seuil de détection de la voix"
            value={threshold}
            min={0.0005}
            max={0.03}
            step={0.0005}
            format={(v) => v.toFixed(4)}
            onCommit={(v) => void update({ "voice.speech_threshold": v })}
          />
        </Row>
        <Row label="Fin de phrase" hint="Silence à attendre avant d'envoyer ce que vous avez dit.">
          <Slider
            label="Silence avant envoi"
            value={Number(values["voice.end_silence_ms"])}
            min={400}
            max={4000}
            step={100}
            format={(v) => `${(v / 1000).toFixed(1)} s`}
            onCommit={(v) => void update({ "voice.end_silence_ms": v })}
          />
        </Row>
        <Row label="Phrase la plus longue" hint="Au-delà, la phrase est envoyée même sans silence.">
          <Slider
            label="Durée maximale d'une phrase"
            value={Number(values["voice.max_utterance_s"])}
            min={5}
            max={120}
            step={5}
            format={(v) => `${v} s`}
            onCommit={(v) => void update({ "voice.max_utterance_s": v })}
          />
        </Row>
      </Section>

      <Section
        title="Reconnaissance vocale"
        hint="Groq et OpenAI utilisent la clé enregistrée dans l'onglet Cerveau. Sans clé, ou en cas d'échec, Whisper local prend le relais."
      >
        <Row label="Moteur">
          <Select
            label="Moteur de transcription"
            value={engine}
            onChange={(v) => void update({ "voice.stt_engine": v })}
            options={Object.entries(ENGINE_LABELS).map(([value, label]) => ({ value, label }))}
          />
        </Row>
        <Row label="Transcription dans le cloud" hint="Désactivé : l'audio ne quitte jamais votre machine.">
          <Toggle
            label="Transcription dans le cloud"
            checked={Boolean(values["voice.cloud_stt"])}
            disabled={engine === "local"}
            onChange={(v) => void update({ "voice.cloud_stt": v })}
          />
        </Row>
        <Row label="Langue parlée" hint="Code à 2 lettres : fr, en, es, de…">
          <TextField
            label="Langue parlée"
            value={String(values["voice.stt_language"])}
            onCommit={(v) => void update({ "voice.stt_language": v.toLowerCase() })}
          />
        </Row>
        {(engine === "auto" || engine === "groq") && (
          <Row label="Modèle Groq">
            <TextField
              label="Modèle de transcription Groq"
              value={String(values["voice.groq_stt_model"])}
              onCommit={(v) => void update({ "voice.groq_stt_model": v })}
            />
          </Row>
        )}
        {(engine === "auto" || engine === "openai") && (
          <Row label="Modèle OpenAI">
            <TextField
              label="Modèle de transcription OpenAI"
              value={String(values["voice.openai_stt_model"])}
              onCommit={(v) => void update({ "voice.openai_stt_model": v })}
            />
          </Row>
        )}
        <Status error={error} saved={saved} />
      </Section>
    </>
  );
}
