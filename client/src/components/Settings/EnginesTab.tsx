import { serverMode } from "../../lib/session";
import { Row, Section, Select, Slider, Status, TextArea, TextField, Toggle, useRuntimeSettings } from "./controls";

const GEMINI_TTS_MODELS = ["gemini-2.5-flash-preview-tts", "gemini-2.5-pro-preview-tts"];
const LIVE_MODELS = [
  "gemini-2.5-flash-native-audio-preview-09-2025",
  "gemini-live-2.5-flash-preview",
  "gemini-2.0-flash-live-001",
];

const LENGTHS = [
  { value: "short", label: "Courtes — l'essentiel, vite" },
  { value: "normal", label: "Normales" },
  { value: "long", label: "Longues — explications détaillées" },
];

/** Onglet MOTEURS — comportement de JARVIS, voix Gemini, mode LIVE et NiTriTe.
 *  Ces réglages n'existaient qu'en variables d'environnement. */
export function EnginesTab() {
  const { values, update, error, saved } = useRuntimeSettings();
  if (!values) return <p className="set-hint">{error || "Chargement…"}</p>;
  const onPc = serverMode() !== "hosted";

  return (
    <>
      <Section
        title="Comportement de JARVIS"
        hint="Les consignes s'appliquent dès le prochain message (en cerveau local : à la prochaine reconnexion)."
      >
        <Row label="Comment JARVIS vous appelle" hint="« Monsieur », « Madame », « Tony », « Patron »…">
          <TextField
            label="Comment JARVIS vous appelle"
            value={String(values["assistant.user_title"])}
            onCommit={(v) => void update({ "assistant.user_title": v || "Monsieur" })}
          />
        </Row>
        <Row label="Accueil vocal au démarrage" hint="JARVIS vous salue à voix haute à l'ouverture : heure, état des systèmes.">
          <Toggle
            label="Accueil vocal au démarrage"
            checked={Boolean(values["assistant.greeting"])}
            onChange={(v) => void update({ "assistant.greeting": v })}
          />
        </Row>
        <Row label="Point rapide à l'accueil" hint="Ajoute les mails non lus et le prochain rendez-vous (onglet Comptes).">
          <Toggle
            label="Point rapide à l'accueil"
            checked={Boolean(values["assistant.greeting_briefing"])}
            disabled={!values["assistant.greeting"]}
            onChange={(v) => void update({ "assistant.greeting_briefing": v })}
          />
        </Row>
        <div className="set-field">
          <span className="set-label">Consignes personnelles</span>
          <span className="set-hint">Comment JARVIS doit vous appeler, son ton, ce qu'il doit savoir de vous, ce qu'il doit éviter…</span>
          <TextArea
            label="Consignes personnelles"
            maxLength={2000}
            placeholder={"Exemples :\nAppelle-moi Tony.\nRéponds en tutoyant, avec humour.\nJe travaille sous Windows 11 et je code en Rust."}
            value={String(values["assistant.instructions"])}
            onCommit={(v) => void update({ "assistant.instructions": v })}
          />
        </div>
        <Row label="Longueur des réponses" hint="Limite la taille des réponses des cerveaux cloud.">
          <Select
            label="Longueur des réponses"
            value={String(values["assistant.response_length"])}
            options={LENGTHS}
            onChange={(v) => void update({ "assistant.response_length": v })}
          />
        </Row>
        <Row label="Mémoire de la conversation" hint="Nombre de messages récents relus à chaque réponse. Plus = meilleur suivi, mais plus lent et plus coûteux.">
          <Slider
            label="Messages gardés en mémoire"
            value={Number(values["chat.context_messages"])}
            min={6}
            max={100}
            step={2}
            format={(v) => `${v} messages`}
            onCommit={(v) => void update({ "chat.context_messages": v })}
          />
        </Row>
      </Section>

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
        <Row label="Ton de la voix" hint="Consigne lue par Gemini avant chaque phrase. Vide = voix neutre.">
          <TextField
            label="Consigne de ton pour la voix Gemini"
            value={String(values["tts.gemini_style"])}
            onCommit={(v) => void update({ "tts.gemini_style": v })}
          />
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
