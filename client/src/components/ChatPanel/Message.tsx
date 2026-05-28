import React from "react";
import { motion } from "framer-motion";
import type { Message as MsgType } from "../../types";

interface Props {
  message: MsgType;
}

// ─── Markdown parser (no external lib) ───────────────────────────────────────

interface CodeBlock {
  kind: "code";
  lang: string;
  content: string;
}
interface TextSegment {
  kind: "text";
  content: string;
}
type Segment = CodeBlock | TextSegment;

function splitCodeBlocks(raw: string): Segment[] {
  const segments: Segment[] = [];
  const fenceRe = /```(\w*)\n?([\s\S]*?)```/g;
  let last = 0;
  let m: RegExpExecArray | null;
  while ((m = fenceRe.exec(raw)) !== null) {
    if (m.index > last) {
      segments.push({ kind: "text", content: raw.slice(last, m.index) });
    }
    segments.push({ kind: "code", lang: m[1] || "code", content: m[2] });
    last = m.index + m[0].length;
  }
  if (last < raw.length) {
    segments.push({ kind: "text", content: raw.slice(last) });
  }
  return segments;
}

// Inline renderer: bold, inline code, then raw text node
function renderInline(text: string): React.ReactNode[] {
  const parts: React.ReactNode[] = [];
  // Split on **bold** and `inline code`
  const re = /(\*\*(.+?)\*\*|`([^`]+)`)/g;
  let last = 0;
  let m: RegExpExecArray | null;
  let key = 0;
  while ((m = re.exec(text)) !== null) {
    if (m.index > last) {
      parts.push(text.slice(last, m.index));
    }
    if (m[0].startsWith("**")) {
      parts.push(<strong key={key++} className="font-bold text-cyan-100">{m[2]}</strong>);
    } else {
      parts.push(
        <code
          key={key++}
          className="px-1 py-0.5 rounded text-[11px] font-mono"
          style={{ background: "rgba(0,212,255,0.12)", color: "#7dd3fc" }}
        >
          {m[3]}
        </code>
      );
    }
    last = m.index + m[0].length;
  }
  if (last < text.length) parts.push(text.slice(last));
  return parts;
}

// Text segment renderer: handles bullet lists, numbered lists, paragraphs
function renderTextSegment(text: string, segKey: number): React.ReactNode {
  const lines = text.split("\n");
  const nodes: React.ReactNode[] = [];
  let ulItems: string[] = [];
  let olItems: string[] = [];
  let key = 0;

  const flushUl = () => {
    if (ulItems.length === 0) return;
    nodes.push(
      <ul key={`ul-${segKey}-${key++}`} className="my-1 flex flex-col gap-0.5">
        {ulItems.map((item, i) => (
          <li key={i} className="flex items-start gap-2">
            <span className="mt-[7px] flex-shrink-0 w-1 h-1 rounded-full" style={{ background: "rgba(0,212,255,0.6)" }} />
            <span className="text-cyan-50/90">{renderInline(item)}</span>
          </li>
        ))}
      </ul>
    );
    ulItems = [];
  };

  const flushOl = () => {
    if (olItems.length === 0) return;
    nodes.push(
      <ol key={`ol-${segKey}-${key++}`} className="my-1 flex flex-col gap-0.5">
        {olItems.map((item, i) => (
          <li key={i} className="flex items-start gap-2">
            <span className="flex-shrink-0 font-mono text-[11px]" style={{ color: "rgba(0,212,255,0.6)", minWidth: "1rem" }}>{i + 1}.</span>
            <span className="text-cyan-50/90">{renderInline(item)}</span>
          </li>
        ))}
      </ol>
    );
    olItems = [];
  };

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const bulletMatch = line.match(/^[-*]\s+(.+)$/);
    const numberedMatch = line.match(/^\d+\.\s+(.+)$/);

    if (bulletMatch) {
      flushOl();
      ulItems.push(bulletMatch[1]);
    } else if (numberedMatch) {
      flushUl();
      olItems.push(numberedMatch[1]);
    } else {
      flushUl();
      flushOl();
      if (line.trim() === "") {
        if (i > 0 && i < lines.length - 1) {
          nodes.push(<div key={`br-${segKey}-${key++}`} className="h-1" />);
        }
      } else {
        nodes.push(
          <p key={`p-${segKey}-${key++}`} className="text-cyan-50/90 leading-relaxed">
            {renderInline(line)}
          </p>
        );
      }
    }
  }
  flushUl();
  flushOl();
  return <>{nodes}</>;
}

function MarkdownContent({ content }: { content: string }) {
  const segments = splitCodeBlocks(content);
  return (
    <div className="flex flex-col gap-1 text-sm">
      {segments.map((seg, i) => {
        if (seg.kind === "code") {
          return (
            <div
              key={i}
              className="rounded overflow-hidden my-1"
              style={{ background: "rgba(0,0,0,0.5)", border: "1px solid rgba(0,212,255,0.15)" }}
            >
              {/* Header bar */}
              <div
                className="flex items-center px-3 py-1 border-b"
                style={{ borderColor: "rgba(0,212,255,0.15)", background: "rgba(0,212,255,0.05)" }}
              >
                <span className="text-[10px] font-mono tracking-widest" style={{ color: "#00d4ff" }}>
                  {seg.lang.toUpperCase()}
                </span>
              </div>
              {/* Code content */}
              <pre
                className="px-3 py-2 text-xs font-mono overflow-x-auto"
                style={{ color: "rgba(125,211,252,0.9)", whiteSpace: "pre-wrap", wordBreak: "break-word" }}
              >
                {seg.content}
              </pre>
            </div>
          );
        }
        return <div key={i}>{renderTextSegment(seg.content, i)}</div>;
      })}
    </div>
  );
}

export function Message({ message }: Props) {
  const isUser = message.role === "user";
  const isSystem = message.role === "system";
  const time = new Date(message.timestamp).toLocaleTimeString("fr-FR", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });

  if (isSystem) {
    return (
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        className="flex justify-center mb-3"
      >
        <div className="px-3 py-1 text-[10px] tracking-widest rounded border border-yellow-500/20 bg-yellow-900/10 text-yellow-400/70">
          ⚡ {message.content}
        </div>
      </motion.div>
    );
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25 }}
      className={`flex ${isUser ? "justify-end" : "justify-start"} mb-4`}
    >
      {/* JARVIS avatar indicator */}
      {!isUser && (
        <div className="flex-shrink-0 w-6 mt-1 mr-2 flex flex-col items-center gap-1">
          <div
            className="w-1.5 h-1.5 rounded-full"
            style={{ background: "#00d4ff", boxShadow: "0 0 6px #00d4ff" }}
          />
          <div className="flex-1 w-px bg-cyan-900/40" />
        </div>
      )}

      <div className={`max-w-[78%] flex flex-col ${isUser ? "items-end" : "items-start"}`}>
        {/* Label */}
        <div className="text-[9px] tracking-widest mb-1 px-1" style={{ color: isUser ? "#00d4ffaa" : "#00ff88aa" }}>
          {isUser ? "VOUS" : "J.A.R.V.I.S."}
        </div>

        {/* Bubble */}
        <div
          className="relative px-4 py-2.5 text-sm leading-relaxed"
          style={
            isUser
              ? {
                  background: "linear-gradient(135deg, rgba(0,80,120,0.4), rgba(0,40,80,0.6))",
                  border: "1px solid rgba(0,212,255,0.25)",
                  borderRadius: "12px 2px 12px 12px",
                  backdropFilter: "blur(12px)",
                  boxShadow: "0 0 20px #00d4ff11, inset 0 0 20px #00d4ff08",
                }
              : {
                  background: "linear-gradient(135deg, rgba(0,20,50,0.6), rgba(0,10,30,0.8))",
                  border: "1px solid rgba(0,136,170,0.2)",
                  borderRadius: "2px 12px 12px 12px",
                  backdropFilter: "blur(12px)",
                  boxShadow: "0 0 20px #00d4ff08",
                }
          }
        >
          {/* Top accent line for JARVIS */}
          {!isUser && (
            <div className="absolute top-0 left-0 right-0 h-px rounded-t-full" style={{ background: "linear-gradient(90deg, #00d4ff44, transparent)" }} />
          )}

          <MarkdownContent content={message.content} />

          {/* Timestamp */}
          <div className="text-right text-[9px] text-blue-400/35 mt-1.5 font-mono tracking-widest">
            {time}
          </div>
        </div>
      </div>

      {/* User avatar indicator */}
      {isUser && (
        <div className="flex-shrink-0 w-6 mt-1 ml-2 flex flex-col items-center gap-1">
          <div
            className="w-1.5 h-1.5 rounded-full"
            style={{ background: "#00d4ff", boxShadow: "0 0 6px #00d4ff88" }}
          />
          <div className="flex-1 w-px bg-cyan-900/40" />
        </div>
      )}
    </motion.div>
  );
}
