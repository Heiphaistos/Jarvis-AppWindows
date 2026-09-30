export type JarvisStatus =
  | "idle"
  | "standby"
  | "listening"
  | "processing"
  | "speaking"
  | "error";

export type MessageRole = "user" | "assistant" | "system";

export interface Message {
  id: string;
  role: MessageRole;
  content: string;
  timestamp: number;
}

export interface AudioChunk {
  data: number[];
  sampleRate: number;
}

export type AgentPhase = "thinking" | "tool" | "verify" | "done";

export interface AgentStep {
  phase: AgentPhase;
  detail: string;
  timestamp: number;
}

export interface ProviderInfo {
  name: string;
  label: string;
  kind: "anthropic" | "openai";
  needs_key: boolean;
  base_url: string;
  model: string;
  api_key_masked: string;
  configured: boolean;
}

export type BrainLevel = "instant" | "standard" | "deep";

export interface BrainTelemetry {
  ttft_ms: number | null;
  tokens_per_s: number | null;
  ok: number;
  failures: number;
  cooling_down: boolean;
  last_error: string;
}

export interface RoutingStatus {
  chains: Record<BrainLevel, string[]>;
  hedging: boolean;
  resolved: Record<BrainLevel, string[]>;
  telemetry: Record<string, BrainTelemetry>;
}

/** Cerveau qui a répondu au dernier message (mode AUTO). */
export interface BrainRoute {
  messageId: string;
  level: BrainLevel;
  provider: string;
  label: string;
  model: string;
  ttftMs: number;
}

export interface ProvidersStatus {
  routing?: RoutingStatus;
  active: string;
  active_label: string;
  active_model: string;
  tier: "local" | "cloud";
  local_available: boolean;
  providers: ProviderInfo[];
}

export type ServerEvent =
  | { type: "status"; payload: { status: JarvisStatus } }
  | { type: "token"; payload: { token: string; messageId: string } }
  | { type: "message_done"; payload: { messageId: string } }
  | { type: "tts_audio"; payload: { audio: string } }
  | { type: "tts_chunk"; payload: { audio: string; final: boolean; index: number } }
  | { type: "stt_text"; payload: { text: string } }
  | { type: "tool_result"; payload: { tool: string; result: string } }
  | { type: "agent_step"; payload: { phase: AgentPhase; detail: string; messageId: string } }
  | { type: "brain"; payload: BrainRoute }
  | { type: "live_state"; payload: { active: boolean; error?: string; model?: string; voice?: string } }
  | { type: "live_audio"; payload: { audio: string; rate: number } }
  | { type: "live_transcript"; payload: { role: "user" | "assistant"; text: string } }
  | { type: "live_interrupted"; payload: Record<string, never> }
  | { type: "live_turn_complete"; payload: Record<string, never> }
  | { type: "reminder"; payload: { id: number; kind: "timer" | "reminder"; message: string } }
  | { type: "wake"; payload: Record<string, never> }
  | { type: "wake_unavailable"; payload: Record<string, never> }
  | { type: "notice"; payload: { message: string } }
  | {
      type: "memory_update";
      payload: {
        saved: { key: string; value: string; category: string }[];
        forgotten: string[];
        lesson: string;
        summary: string;
      };
    }
  | { type: "error"; payload: { message: string } }
  | {
      type: "server_status";
      payload: {
        llm: boolean;
        stt: boolean;
        tts: boolean;
        provider?: string;
        providerLabel?: string;
        providerModel?: string;
      };
    }
  | { type: "system_alert"; payload: { alert_type: string; message: string } }
  | {
      type: "system_metrics";
      payload: { cpu: number; ram: number; gpu: number | null; vram: number | null };
    }
  | { type: "perf_changed"; payload: { active: string } };

export type ClientEvent =
  | { type: "text_query"; payload: { text: string; council?: boolean } }
  | { type: "audio_chunk"; payload: AudioChunk }
  | { type: "wake_audio"; payload: AudioChunk }
  | { type: "wake_reset"; payload: Record<string, never> }
  | { type: "stop_generation"; payload: Record<string, never> }
  | { type: "mic_stop"; payload: Record<string, never> }
  | { type: "tts_done"; payload: Record<string, never> }
  | { type: "set_tts"; payload: { enabled: boolean } }
  | { type: "set_voice"; payload: { voice: string } }
  | { type: "clear_history"; payload: Record<string, never> }
  | { type: "live_start"; payload: { voice: string } }
  | { type: "live_stop"; payload: Record<string, never> };
