import { VoiceVisualizer } from "./components/VoiceVisualizer/VoiceVisualizer";
import { ChatPanel } from "./components/ChatPanel/ChatPanel";
import { StatusBar } from "./components/StatusBar/StatusBar";
import { CommandInput } from "./components/CommandInput/CommandInput";

function HexGrid() {
  return (
    <svg
      className="absolute inset-0 w-full h-full opacity-5 pointer-events-none"
      xmlns="http://www.w3.org/2000/svg"
    >
      <defs>
        <pattern
          id="hex"
          x="0"
          y="0"
          width="60"
          height="52"
          patternUnits="userSpaceOnUse"
        >
          <polygon
            points="30,2 58,17 58,46 30,61 2,46 2,17"
            fill="none"
            stroke="#00d4ff"
            strokeWidth="0.5"
          />
        </pattern>
      </defs>
      <rect width="100%" height="100%" fill="url(#hex)" />
    </svg>
  );
}

export default function App() {
  return (
    <div className="h-screen flex flex-col relative overflow-hidden bg-[#020c18]">
      <HexGrid />

      <div className="relative z-10 text-center py-3 border-b border-cyan-900/30">
        <h1
          className="text-2xl font-bold tracking-[0.5em] text-cyan-400"
          style={{
            textShadow: "0 0 20px #00d4ff, 0 0 40px #00d4ff66",
          }}
        >
          J.A.R.V.I.S.
        </h1>
        <p className="text-[10px] text-blue-400/40 tracking-widest mt-0.5">
          JUST A RATHER VERY INTELLIGENT SYSTEM
        </p>
      </div>

      <StatusBar />

      <div className="flex-1 flex overflow-hidden relative z-10">
        <div className="w-72 flex flex-col items-center justify-center border-r border-cyan-900/30 p-4 gap-4">
          <VoiceVisualizer />
          <div className="text-center">
            <div className="text-xs text-blue-400/50 tracking-widest">
              SYSTÈME ACTIF
            </div>
            <div className="text-xs text-cyan-400/70 mt-1">
              RTX 3070 · CUDA 13
            </div>
          </div>
        </div>

        <div className="flex-1 flex flex-col">
          <ChatPanel />
          <CommandInput />
        </div>
      </div>
    </div>
  );
}
