import { useEffect, useRef } from "react";
import { Download, Trash2 } from "lucide-react";
import { ChatPanel } from "./components/ChatPanel/ChatPanel";
import { CommandInput } from "./components/CommandInput/CommandInput";
import { BootSequence } from "./components/Boot/BootSequence";
import { VoiceOrb } from "./components/VoiceOrb/VoiceOrb";
import { AgentSteps } from "./components/AgentSteps/AgentSteps";
import { Backdrop } from "./components/Shell/Backdrop";
import { TitleBar } from "./components/Shell/TitleBar";
import { CoreStage } from "./components/Shell/CoreStage";
import { TelemetryRail, SideFooter, StatChips } from "./components/Shell/Telemetry";
import { useThemeVars } from "./components/Shell/theme";
import { useJarvis } from "./hooks/useJarvis";
import { useJarvisStore } from "./stores/jarvisStore";

type Jarvis = ReturnType<typeof useJarvis>;

function ChatColumn({ jarvis }: { jarvis: Jarvis }) {
  const hasMessages = useJarvisStore((s) => s.messages.length > 0);
  const exportConversation = useJarvisStore((s) => s.exportConversation);
  const clearMessages = useJarvisStore((s) => s.clearMessages);
  return (
    <section className="chat panel" aria-label="Conversation">
      <header className="panel-head">
        <span className="readout">Conversation</span>
        {hasMessages && (
          <div className="flex gap-1">
            <button className="icon-btn" onClick={exportConversation} title="Exporter en Markdown" aria-label="Exporter en Markdown">
              <Download />
            </button>
            <button className="icon-btn" onClick={clearMessages} title="Effacer l'historique" aria-label="Effacer l'historique">
              <Trash2 />
            </button>
          </div>
        )}
      </header>
      <ChatPanel />
      <AgentSteps />
      <CommandInput sendText={jarvis.sendText} toggleMic={jarvis.toggleMic} toggleLive={jarvis.toggleLive} isMicActive={jarvis.isMicActive} />
    </section>
  );
}

export default function App() {
  useThemeVars();
  const jarvis = useJarvis();
  const layout = useJarvisStore((s) => s.layout);
  const side = useJarvisStore((s) => s.layoutSide);
  const onMic = () => void jarvis.toggleMic();

  // Accueil parlé « Bonjour Monsieur » dès l'ouverture, une fois l'initialisation terminée.
  const bootDone = useJarvisStore((s) => s.bootDone);
  const isConnected = useJarvisStore((s) => s.isConnected);
  const wsSend = useJarvisStore((s) => s.wsSend);
  const greeted = useRef(false);
  useEffect(() => {
    if (greeted.current || !bootDone || !isConnected || !wsSend) return;
    greeted.current = true;
    wsSend({ type: "greet", payload: {} });
  }, [bootDone, isConnected, wsSend]);

  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      const input = document.querySelector<HTMLInputElement>("[data-jarvis-input]");
      if ((e.ctrlKey || e.metaKey) && e.key === "k") {
        e.preventDefault();
        input?.focus();
      }
      if (e.key === "Escape" && input && document.activeElement === input) input.blur();
    };
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, []);

  const core = <CoreStage isMicActive={jarvis.isMicActive} onMic={onMic} />;
  const chat = <ChatColumn jarvis={jarvis} />;

  return (
    <div className="shell">
      <Backdrop />
      <TitleBar />
      <main className="stage" data-layout={layout} data-side={side}>
        {layout === "hud" && (<><TelemetryRail />{core}{chat}</>)}
        {layout === "immersive" && (<>{core}<StatChips />{chat}</>)}
        {layout === "split" && (
          <>
            <aside className="side panel">{core}<SideFooter /></aside>
            {chat}
          </>
        )}
        {layout === "compact" && (<><StatChips />{chat}</>)}
      </main>
      {layout === "compact" && <VoiceOrb />}
      <BootSequence />
    </div>
  );
}
