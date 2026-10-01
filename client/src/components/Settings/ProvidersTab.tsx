import { useCallback, useEffect, useState } from "react";
import { CheckCircle, Cpu, KeyRound, Loader2, Zap } from "lucide-react";
import { useJarvisStore } from "../../stores/jarvisStore";
import type { BrainLevel, ProviderInfo, ProvidersStatus } from "../../types";

const LEVELS: { id: BrainLevel; label: string; hint: string }[] = [
  { id: "instant", label: "INSTANTANÉ", hint: "salutations, ordres, reformulations" },
  { id: "standard", label: "STANDARD", hint: "conversation" },
  { id: "deep", label: "PROFOND", hint: "analyse, code, rédaction" },
];

/** Mode AUTO : un cerveau par niveau de réflexion, course au premier mot. */
function AutoCard({ status, busy, onActivate, onHedging }: {
  status: ProvidersStatus;
  busy: boolean;
  onActivate: () => void;
  onHedging: (v: boolean) => void;
}) {
  const routing = status.routing;
  const isAuto = status.active === "auto";
  if (!routing) return null;
  const configured = LEVELS.some((l) => routing.resolved[l.id]?.length);
  return (
    <div className="flex flex-col gap-2 p-3 rounded"
      style={{
        background: isAuto ? "rgb(var(--accent-rgb) / 0.08)" : "rgba(255,255,255,0.02)",
        border: `1px solid ${isAuto ? "rgb(var(--accent-rgb) / 0.4)" : "rgba(255,255,255,0.06)"}`,
      }}>
      <div className="flex items-center gap-2">
        <Zap size={13} className="text-cyan-400 shrink-0" />
        <div className="flex-1">
          <div className="text-[11px] font-bold tracking-wider" style={{ color: isAuto ? "var(--accent)" : "#ffffffaa" }}>
            AUTO — ROUTAGE MULTI-MODÈLES
          </div>
          <div className="text-[8px] text-blue-400/40">
            Chaque demande part vers le cerveau adapté ; si le premier tarde, le suivant démarre en parallèle et le plus rapide répond.
          </div>
        </div>
        {isAuto ? (
          <CheckCircle size={12} className="text-cyan-400 shrink-0" />
        ) : (
          <button disabled={busy || !configured} onClick={onActivate}
            className="px-2 py-1 rounded text-[9px] tracking-widest font-bold disabled:opacity-30"
            style={{ background: "rgb(var(--accent-rgb) / 0.12)", border: "1px solid rgb(var(--accent-rgb) / 0.4)", color: "var(--accent)" }}>
            ACTIVER
          </button>
        )}
      </div>
      {LEVELS.map((l) => {
        const brains = routing.resolved[l.id] ?? [];
        return (
          <div key={l.id} className="text-[9px]">
            <span className="tracking-widest text-cyan-400/70">{l.label}</span>
            <span className="text-blue-400/30"> · {l.hint}</span>
            <div className="text-blue-300/60 truncate">
              {brains.length ? brains.slice(0, 4).join("  →  ") : "aucun cerveau configuré (repli local)"}
            </div>
          </div>
        );
      })}
      {Object.keys(routing.telemetry).length > 0 && (
        <div className="grid grid-cols-2 gap-x-3 gap-y-0.5 pt-1 border-t border-cyan-900/30">
          {Object.entries(routing.telemetry).map(([key, t]) => (
            <div key={key} className="text-[8px] flex justify-between gap-2" title={t.last_error || undefined}>
              <span className="truncate text-blue-300/50">{key}</span>
              <span style={{ color: t.cooling_down ? "#ff6655" : "#00ff88aa" }}>
                {t.cooling_down ? "PAUSE" : t.ttft_ms != null ? `${t.ttft_ms} ms` : "—"}
                {t.tokens_per_s != null && ` · ${Math.round(t.tokens_per_s)} t/s`}
              </span>
            </div>
          ))}
        </div>
      )}
      <label className="flex items-center gap-2 text-[9px] text-blue-400/50 cursor-pointer">
        <input type="checkbox" checked={routing.hedging} onChange={(e) => onHedging(e.target.checked)} />
        Course au premier mot (lance un 2e cerveau si le 1er tarde)
      </label>
    </div>
  );
}

const API = "http://127.0.0.1:8765/api/providers";

/** Onglet CERVEAU — sélection du provider LLM (local, Anthropic, ou n'importe
 *  quelle API OpenAI-compatible). Les clés API sont write-only : envoyées au
 *  serveur, jamais relues. */
export function ProvidersTab() {
  const [status, setStatus] = useState<ProvidersStatus | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [apiKey, setApiKey] = useState("");
  const [model, setModel] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const refresh = useCallback(() => {
    fetch(API)
      .then((r) => r.json())
      .then((d: ProvidersStatus) => setStatus(d))
      .catch(() => setError("Serveur injoignable"));
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const openEditor = (p: ProviderInfo) => {
    setSelected(p.name);
    setApiKey("");
    setModel(p.model);
    setBaseUrl(p.base_url);
    setError("");
  };

  const submit = async (name: string, activate: boolean, extra: Record<string, unknown> = {}) => {
    setBusy(true);
    setError("");
    try {
      const body: Record<string, unknown> = { name, activate, ...extra };
      if (name !== "local" && selected === name) {
        if (apiKey) body.api_key = apiKey;
        if (model) body.model = model;
        if (baseUrl) body.base_url = baseUrl;
      }
      const res = await fetch(API, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(String(data.detail ?? "Erreur de configuration"));
      } else {
        const next = data as ProvidersStatus;
        setStatus(next);
        setApiKey("");
        if (activate) {
          setSelected(null);
          // Mise à jour immédiate du HUD (label CERVEAU) sans attendre le WS
          useJarvisStore.setState({
            providerLabel: next.active_label,
            providerModel: next.active_model,
          });
        }
      }
    } catch {
      setError("Serveur injoignable");
    } finally {
      setBusy(false);
    }
  };

  if (!status) {
    return (
      <div className="flex items-center justify-center gap-2 py-6 text-[10px] text-blue-400/40">
        <Loader2 size={12} className="animate-spin" /> Chargement…
      </div>
    );
  }

  const allProviders: (ProviderInfo & { isLocal?: boolean })[] = [
    {
      name: "local",
      label: "Local (Mistral GGUF)",
      kind: "openai",
      needs_key: false,
      base_url: "",
      model: "Mistral-7B",
      api_key_masked: "",
      configured: status.local_available,
      isLocal: true,
    },
    ...status.providers,
  ];

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center gap-2 p-2.5 rounded"
        style={{ background: "rgb(var(--accent-rgb) / 0.05)", border: "1px solid rgb(var(--accent-rgb) / 0.15)" }}>
        <Cpu size={13} className="text-cyan-400 shrink-0" />
        <div className="text-[9px] text-blue-400/60">
          Cerveau actif : <span className="text-cyan-400 font-bold">{status.active_label}</span>
          {status.active_model && <span className="text-blue-400/40"> · {status.active_model}</span>}
        </div>
      </div>

      {error && (
        <div className="text-[9px] text-red-400 px-1">{error}</div>
      )}

      <AutoCard
        status={status}
        busy={busy}
        onActivate={() => void submit("auto", true)}
        onHedging={(v) => void submit(status.active, false, { hedging: v })}
      />

      <div className="flex flex-col gap-1.5">
        {allProviders.map((p) => {
          const isActive = status.active === p.name;
          const isEditing = selected === p.name;
          return (
            <div key={p.name}>
              <button
                onClick={() => (p.isLocal ? void submit("local", true) : openEditor(p))}
                className="w-full flex items-center gap-3 p-2.5 rounded text-left transition-all"
                style={{
                  background: isActive ? "rgb(var(--accent-rgb) / 0.1)" : "rgba(255,255,255,0.02)",
                  border: `1px solid ${isActive ? "rgb(var(--accent-rgb) / 0.35)" : "rgba(255,255,255,0.05)"}`,
                }}
              >
                <div
                  className="w-2 h-2 rounded-full shrink-0"
                  style={{
                    background: isActive ? "var(--accent)" : p.configured ? "#00ff8855" : "transparent",
                    border: `1px solid ${isActive ? "var(--accent)" : p.configured ? "#00ff88" : "rgba(255,255,255,0.2)"}`,
                    boxShadow: isActive ? "0 0 6px var(--accent)" : "none",
                  }}
                />
                <div className="flex-1 min-w-0">
                  <div className="text-[11px] font-bold tracking-wider truncate"
                    style={{ color: isActive ? "var(--accent)" : "#ffffff77" }}>
                    {p.label}
                  </div>
                  <div className="text-[8px] text-blue-400/30 truncate">
                    {p.isLocal ? "100 % privé · hors-ligne" : p.model || "modèle à définir"}
                    {p.api_key_masked && ` · clé ${p.api_key_masked}`}
                  </div>
                </div>
                {isActive && <CheckCircle size={12} className="text-cyan-400 shrink-0" />}
              </button>

              {isEditing && !p.isLocal && (
                <div className="flex flex-col gap-2 mt-1.5 mb-1 p-3 rounded"
                  style={{ background: "rgb(var(--accent-rgb) / 0.03)", border: "1px solid rgb(var(--accent-rgb) / 0.12)" }}>
                  {p.needs_key && (
                    <label className="flex flex-col gap-1">
                      <span className="text-[8px] tracking-widest text-blue-400/40 flex items-center gap-1">
                        <KeyRound size={9} /> CLÉ API {p.api_key_masked && `(actuelle : ${p.api_key_masked})`}
                      </span>
                      <input
                        type="password"
                        value={apiKey}
                        onChange={(e) => setApiKey(e.target.value)}
                        placeholder={p.api_key_masked ? "Laisser vide pour conserver" : "sk-…"}
                        className="bg-black/40 border border-cyan-900/40 rounded px-2 py-1.5 text-[10px] text-cyan-100 outline-none focus:border-cyan-500/50"
                      />
                    </label>
                  )}
                  <label className="flex flex-col gap-1">
                    <span className="text-[8px] tracking-widest text-blue-400/40">MODÈLE</span>
                    <input
                      value={model}
                      onChange={(e) => setModel(e.target.value)}
                      placeholder="nom-du-modele"
                      className="bg-black/40 border border-cyan-900/40 rounded px-2 py-1.5 text-[10px] text-cyan-100 outline-none focus:border-cyan-500/50"
                    />
                  </label>
                  <label className="flex flex-col gap-1">
                    <span className="text-[8px] tracking-widest text-blue-400/40">BASE URL (OpenAI-compatible)</span>
                    <input
                      value={baseUrl}
                      onChange={(e) => setBaseUrl(e.target.value)}
                      placeholder="https://…/v1"
                      className="bg-black/40 border border-cyan-900/40 rounded px-2 py-1.5 text-[10px] text-cyan-100 outline-none focus:border-cyan-500/50"
                    />
                  </label>
                  <div className="flex gap-2 mt-1">
                    <button
                      disabled={busy}
                      onClick={() => void submit(p.name, false)}
                      className="flex-1 py-1.5 rounded text-[9px] tracking-widest transition-all disabled:opacity-40"
                      style={{ border: "1px solid rgb(var(--accent-rgb) / 0.25)", color: "rgb(var(--accent-rgb) / 0.53)" }}
                    >
                      ENREGISTRER
                    </button>
                    <button
                      disabled={busy}
                      onClick={() => void submit(p.name, true)}
                      className="flex-1 py-1.5 rounded text-[9px] tracking-widest font-bold transition-all disabled:opacity-40"
                      style={{ background: "rgb(var(--accent-rgb) / 0.12)", border: "1px solid rgb(var(--accent-rgb) / 0.4)", color: "var(--accent)" }}
                    >
                      {busy ? "…" : "ACTIVER"}
                    </button>
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>

      <p className="text-[8px] text-blue-400/25 leading-relaxed px-1">
        Toute API compatible OpenAI fonctionne (OpenAI, Gemini, Ollama, Groq, DeepSeek,
        xAI, OpenRouter, Mistral, LM Studio, vLLM…) via « API personnalisée ».
        Les clés restent sur votre machine, côté serveur. En cas de panne du provider
        cloud, JARVIS bascule automatiquement sur le cerveau local.
      </p>
    </div>
  );
}
