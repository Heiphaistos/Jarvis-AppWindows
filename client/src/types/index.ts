export type JarvisStatus =
  | "idle"
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

export type ServerEvent =
  | { type: "status"; payload: { status: JarvisStatus } }
  | { type: "token"; payload: { token: string; messageId: string } }
  | { type: "message_done"; payload: { messageId: string } }
  | { type: "tts_audio"; payload: { audio: string } }
  | { type: "tts_chunk"; payload: { audio: string; final: boolean; index: number } }
  | { type: "stt_text"; payload: { text: string } }
  | { type: "tool_result"; payload: { tool: string; result: string } }
  | { type: "error"; payload: { message: string } }
  | { type: "server_status"; payload: { llm: boolean; stt: boolean; tts: boolean } }
  | { type: "system_alert"; payload: { alert_type: string; message: string } };

export type ClientEvent =
  | { type: "text_query"; payload: { text: string } }
  | { type: "audio_chunk"; payload: AudioChunk }
  | { type: "mic_stop"; payload: Record<string, never> }
  | { type: "tts_done"; payload: Record<string, never> }
  | { type: "set_tts"; payload: { enabled: boolean } }
  | { type: "set_voice"; payload: { voice: string } }
  | { type: "clear_history"; payload: Record<string, never> };
