import React from "react";
import { useJarvisStore } from "../../stores/jarvisStore";
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

// Inline renderer: bold, inline code, links, italic
function renderInline(text: string): React.ReactNode[] {
  const nodes: React.ReactNode[] = [];
  const pattern = /(\*\*(.+?)\*\*|`([^`]+)`|\[([^\]]+)\]\((https?:\/\/[^)]+)\)|\*([^*\n]+)\*)/g;
  let last = 0;
  let match: RegExpExecArray | null;
  let key = 0;

  while ((match = pattern.exec(text)) !== null) {
    if (match.index > last) {
      nodes.push(text.slice(last, match.index));
    }
    const [full, , boldText, codeText, linkLabel, linkHref, italicText] = match;
    if (full.startsWith("**")) {
      nodes.push(
        <strong key={key++} className="font-bold text-cyan-200">
          {boldText}
        </strong>
      );
    } else if (full.startsWith("`")) {
      nodes.push(
        <code
          key={key++}
          className="bg-black/40 text-cyan-300 px-1 py-0.5 rounded text-xs font-mono border border-cyan-900/40"
        >
          {codeText}
        </code>
      );
    } else if (full.startsWith("[")) {
      nodes.push(
        <a
          key={key++}
          href={linkHref}
          target="_blank"
          rel="noopener noreferrer"
          className="text-cyan-400 underline hover:text-cyan-200 transition-colors cursor-pointer"
          onClick={(e) => {
            e.preventDefault();
          }}
        >
          {linkLabel}
        </a>
      );
    } else if (full.startsWith("*")) {
      nodes.push(
        <em key={key++} className="italic text-cyan-100/80">
          {italicText}
        </em>
      );
    }
    last = match.index + full.length;
  }
  if (last < text.length) nodes.push(text.slice(last));
  return nodes;
}

// Group consecutive table lines
function groupTableLines(lines: string[]): Array<string | string[]> {
  const result: Array<string | string[]> = [];
  let tableBuffer: string[] = [];

  for (const line of lines) {
    if (line.trim().startsWith("|") && line.trim().endsWith("|")) {
      tableBuffer.push(line);
    } else {
      if (tableBuffer.length >= 2) {
        result.push(tableBuffer);
      } else {
        result.push(...tableBuffer);
      }
      tableBuffer = [];
      result.push(line);
    }
  }
  if (tableBuffer.length >= 2) result.push(tableBuffer);
  else result.push(...tableBuffer);
  return result;
}

function renderTable(tableLines: string[], segKey: number, tableKey: number): React.ReactElement {
  const rows = tableLines
    .filter((l) => !/^\|[-| :]+\|$/.test(l.trim()))
    .map((l) =>
      l
        .split("|")
        .filter((c) => c !== "")
        .map((c) => c.trim())
    );

  if (rows.length === 0) return <React.Fragment key={`tbl-${segKey}-${tableKey}`} />;
  const [header, ...body] = rows;

  return (
    <div key={`tbl-${segKey}-${tableKey}`} className="overflow-x-auto my-2">
      <table className="text-xs border-collapse w-full">
        <thead>
          <tr>
            {header.map((cell, ci) => (
              <th
                key={ci}
                className="border border-cyan-900/40 bg-cyan-950/50 px-2 py-1 text-cyan-300 text-left font-semibold"
              >
                {renderInline(cell)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {body.map((row, ri) => (
            <tr key={ri} className={ri % 2 === 0 ? "bg-black/20" : "bg-black/10"}>
              {row.map((cell, ci) => (
                <td key={ci} className="border border-cyan-900/30 px-2 py-1 text-cyan-100/80">
                  {renderInline(cell)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// Text segment renderer: handles headings, blockquotes, hr, bullet lists, numbered lists, tables, paragraphs
function renderTextSegment(text: string, segKey: number): React.ReactNode {
  const rawLines = text.split("\n");
  const grouped = groupTableLines(rawLines);
  const nodes: React.ReactNode[] = [];
  let ulItems: string[] = [];
  let olItems: string[] = [];
  let key = 0;
  let tableCount = 0;

  const flushUl = () => {
    if (ulItems.length === 0) return;
    nodes.push(
      <ul key={`ul-${segKey}-${key++}`} className="my-1 flex flex-col gap-0.5">
        {ulItems.map((item, i) => (
          <li key={i} className="flex items-start gap-2">
            <span
              className="mt-[7px] flex-shrink-0 w-1 h-1 rounded-full"
              style={{ background: "rgb(var(--accent-rgb) / 0.6)" }}
            />
            <span>{renderInline(item)}</span>
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
            <span
              className="flex-shrink-0 font-mono text-[11px]"
              style={{ color: "rgb(var(--accent-rgb) / 0.6)", minWidth: "1rem" }}
            >
              {i + 1}.
            </span>
            <span>{renderInline(item)}</span>
          </li>
        ))}
      </ol>
    );
    olItems = [];
  };

  for (let i = 0; i < grouped.length; i++) {
    const item = grouped[i];

    // Table block
    if (Array.isArray(item)) {
      flushUl();
      flushOl();
      nodes.push(renderTable(item, segKey, tableCount++));
      continue;
    }

    const line = item as string;
    const bulletMatch = line.match(/^[-*]\s+(.+)$/);
    const numberedMatch = line.match(/^\d+\.\s+(.+)$/);

    // Headings
    if (line.startsWith("### ")) {
      flushUl();
      flushOl();
      nodes.push(
        <h3 key={`h3-${segKey}-${key++}`} className="text-sm font-bold text-cyan-300 mt-3 mb-1 border-b border-cyan-900/30 pb-0.5">
          {renderInline(line.slice(4))}
        </h3>
      );
    } else if (line.startsWith("## ")) {
      flushUl();
      flushOl();
      nodes.push(
        <h2 key={`h2-${segKey}-${key++}`} className="text-base font-bold text-cyan-200 mt-4 mb-1 border-b border-cyan-800/40 pb-1">
          {renderInline(line.slice(3))}
        </h2>
      );
    } else if (line.startsWith("# ")) {
      flushUl();
      flushOl();
      nodes.push(
        <h1 key={`h1-${segKey}-${key++}`} className="text-lg font-bold text-white mt-4 mb-2">
          {renderInline(line.slice(2))}
        </h1>
      );
    // Blockquote
    } else if (line.startsWith("> ")) {
      flushUl();
      flushOl();
      nodes.push(
        <blockquote key={`bq-${segKey}-${key++}`} className="border-l-2 border-cyan-500/50 pl-3 italic text-cyan-100/60 my-1 text-sm">
          {renderInline(line.slice(2))}
        </blockquote>
      );
    // Horizontal rule
    } else if (/^[-*_]{3,}$/.test(line.trim())) {
      flushUl();
      flushOl();
      nodes.push(<hr key={`hr-${segKey}-${key++}`} className="border-cyan-900/40 my-3" />);
    // Bullet list
    } else if (bulletMatch) {
      flushOl();
      ulItems.push(bulletMatch[1]);
    // Numbered list
    } else if (numberedMatch) {
      flushUl();
      olItems.push(numberedMatch[1]);
    // Empty line or paragraph
    } else {
      flushUl();
      flushOl();
      if (line.trim() === "") {
        if (i > 0 && i < grouped.length - 1) {
          nodes.push(<div key={`br-${segKey}-${key++}`} className="h-1" />);
        }
      } else {
        nodes.push(
          <p key={`p-${segKey}-${key++}`} className="leading-relaxed">
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
    <div className="flex flex-col gap-1">
      {segments.map((seg, i) => {
        if (seg.kind === "code") {
          return (
            <div
              key={i}
              className="rounded overflow-hidden my-1"
              style={{ background: "rgba(0,0,0,0.5)", border: "1px solid rgb(var(--accent-rgb) / 0.15)" }}
            >
              {/* Header bar */}
              <div
                className="flex items-center px-3 py-1 border-b"
                style={{ borderColor: "rgb(var(--accent-rgb) / 0.15)", background: "rgb(var(--accent-rgb) / 0.05)" }}
              >
                <span className="text-[10px] font-mono tracking-widest" style={{ color: "var(--accent)" }}>
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
  const brain = useJarvisStore((s) => s.messageBrains[message.id]);
  const isUser = message.role === "user";
  const isSystem = message.role === "system";
  const [copied, setCopied] = React.useState(false);
  const time = new Date(message.timestamp).toLocaleTimeString("fr-FR", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });

  const handleCopy = () => {
    void navigator.clipboard.writeText(message.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  if (isSystem) {
    return (
      <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="msg-sys">
        {message.content}
      </motion.div>
    );
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25 }}
      className={`msg ${isUser ? "msg-user" : "msg-bot"}`}
    >
      <div className="who">
        <span>{isUser ? "VOUS" : "J.A.R.V.I.S."}</span>
        <em title={brain ? `${brain.label} · niveau ${brain.level}` : undefined}>
          {!isUser && brain ? `${brain.model} · ${brain.ttftMs} ms · ` : ""}{time}
        </em>
      </div>
      <MarkdownContent content={message.content} />
      {!isUser && (
        <button onClick={handleCopy} title="Copier le message" className="msg-copy">
          {copied ? (
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
              <polyline points="20 6 9 17 4 12" />
            </svg>
          ) : (
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
              <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
            </svg>
          )}
        </button>
      )}
    </motion.div>
  );
}
