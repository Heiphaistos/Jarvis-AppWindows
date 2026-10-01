import { serverMode } from "../../lib/session";
import { Row, Section, Status, TextField, useRuntimeSettings } from "./controls";

const GEMINI_TTS_MODELS = ["gemini-2.5-flash-preview-tts", "gemini-2.5-pro-preview-tts"];
const LIVE_MODELS = [
  "gemini-2.5-flash-native-audio-preview-09-2025",
  "gemini-live-2.5-flash-preview",
  "gemini-2.0-flash-live-001",
];

/** Onglet MOTEURS — modèles des voix Gemini, mode LIVE et intégration NiTriTe.
 *  Ces réglages n'existaient qu'en variables d'environnement. */
export function EnginesTab() {
  const { values, update, error, saved } = useRuntimeSettings();
  if (!values) return <p className="set-hint">{error || "Chargement…"}</p>;
  const onPc = serverMode() !== "hosted";

  return (
    <>
      <Section
        title="Voix Gemini"
        hint="Utilise la clé Gemini de l'onglet Cerveau. Choisissez une voix Gemini dans l'onglet Voix."
      >
        <Row label="Modèle de synthèse vocale">
          <TextField
            label="Modèle Gemini de synthèse vocale"
            list="jarvis-tts-models"
            value={String(values["tts.gemini_model"])}
            onCommit={(v) => void update({ "tts.gemini_model": v })}
          />
          <datalist id="jarvis-tts-models">
            {GEMINI_TTS_MODELS.map((m) => <option key={m} value={m} />)}
          </datalist>
        </Row>
      </Section>

      <Section
        title="Mode LIVE"
        hint="Conversation vocale en temps réel avec Gemini (bouton LIVE de la barre de saisie)."
      >
        <Row label="Modèle LIVE">
          <TextField
            label="Modèle Gemini du mode LIVE"
            list="jarvis-live-models"
            value={String(values["live.model"])}
            onCommit={(v) => void update({ "live.model": v })}
          />
          <datalist id="jarvis-live-models">
            {LIVE_MODELS.map((m) => <option key={m} value={m} />)}
          </datalist>
        </Row>
      </Section>

      {onPc && (
        <Section
          title="NiTriTe"
          hint="Laisser vide pour la recherche automatique (Téléchargements, Bureau, Program Files)."
        >
          <Row label="NiTriTe Agent" hint="Chemin complet de NiTriTe-Agent….exe">
            <TextField
              label="Chemin de NiTriTe-Agent.exe"
              placeholder="C:\…\NiTriTe-Agent-1.5.0.exe"
              value={String(values["nitrite.agent_path"])}
              onCommit={(v) => void update({ "nitrite.agent_path": v })}
            />
          </Row>
          <Row label="Fichier de session" hint="Avancé : session.json de l'agent, s'il n'est pas à son emplacement habituel.">
            <TextField
              label="Fichier de session de NiTriTe Agent"
              placeholder="…\NiTriTe-WebPanel\session.json"
              value={String(values["nitrite.session_path"])}
              onCommit={(v) => void update({ "nitrite.session_path": v })}
            />
          </Row>
        </Section>
      )}
      <Status error={error} saved={saved} />
    </>
  );
}
