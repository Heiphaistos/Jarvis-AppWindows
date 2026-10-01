import { useCallback, useEffect, useState } from "react";
import {
  ArrowDown, ArrowUp, CheckCircle, ChevronUp, Cpu, ExternalLink, Eye, EyeOff, KeyRound, ListRestart, Loader2, Plug, Plus,
  Save, SlidersHorizontal, Trash2, X, XCircle, Zap,
} from "lucide-react";
import { useJarvisStore } from "../../stores/jarvisStore";
import type { BrainLevel, ProviderInfo, ProvidersStatus } from "../../types";
import { api, openExternal } from "../../lib/platform";
import { Section } from "./controls";

const LEVELS: { id: BrainLevel; label: string; hint: string }[] = [
  { id: "instant", label: "Instantané", hint: "salutations, ordres, reformulations" },
  { id: "standard", label: "Standard", hint: "conversation" },
  { id: "deep", label: "Profond", hint: "analyse, code, rédaction" },
];

/** Où créer une clé API pour chaque fournisseur. */
const KEY_PAGES: Record<string, string> = {
  anthropic: "https://console.anthropic.com/settings/keys",
  openai: "https://platform.openai.com/api-keys",
  gemini: "https://aistudio.google.com/app/apikey",
  groq: "https://console.groq.com/keys",
  deepseek: "https://platform.deepseek.com/api_keys",
  xai: "https://console.x.ai",
  openrouter: "https://openrouter.ai/keys",
  cerebras: "https://cloud.cerebras.ai",
  huggingface: "https://huggingface.co/settings/tokens",
  mistral: "https://console.mistral.ai/api-keys",
};

type TestResult = { ok: boolean; detail: string };

async function postProviders(body: Record<string, unknown>): Promise<ProvidersStatus> {
  const res = await api("/providers", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(String(data.detail ?? "Erreur de configuration"));
  return data as ProvidersStatus;
}

/* ── Mode AUTO : chaînes de cerveaux modifiables ─────────────────────────── */

function ChainEditor({ status, onSave, busy }: {
  status: ProvidersStatus;
  onSave: (chains: Record<BrainLevel, string[]>) => void;
  busy: boolean;
}) {
  const routing = status.routing;
  const [chains, setChains] = useState<Record<BrainLevel, string[]> | null>(routing ? { ...routing.chains } : null);
  const [adding, setAdding] = useState<Record<BrainLevel, string>>({ instant: "", standard: "", deep: "" });
  useEffect(() => {
    if (routing) setChains({ ...routing.chains });
  }, [routing]);
  if (!routing || !chains) return null;

  const configured = new Set(status.providers.filter((p) => p.configured).map((p) => p.name));
  if (status.local_available) configured.add("local");
  const options = [...status.providers.map((p) => p.name), "local"];
  const dirty = JSON.stringify(chains) !== JSON.stringify(routing.chains);

  const move = (level: BrainLevel, i: number, delta: number) => {
    const list = [...chains[level]];
    const j = i + delta;
    if (j < 0 || j >= list.length) return;
    [list[i], list[j]] = [list[j], list[i]];
    setChains({ ...chains, [level]: list });
  };
  const remove = (level: BrainLevel, i: number) =>
    setChains({ ...chains, [level]: chains[level].filter((_, k) => k !== i) });
  const add = (level: BrainLevel) => {
    const spec = adding[level].trim();
    if (!spec || chains[level].includes(spec)) return;
    setChains({ ...chains, [level]: [...chains[level], spec] });
    setAdding({ ...adding, [level]: "" });
  };

  return (
    <details className="set-chains-box">
      <summary>Modifier les chaînes de cerveaux</summary>
    <div className="set-chains">
      {LEVELS.map((l) => (
        <div key={l.id} className="set-chain">
          <div className="set-label">{l.label} <span className="set-hint">· {l.hint}</span></div>
          <ol>
            {chains[l.id].map((spec, i) => {
              const ok = configured.has(spec.split("@")[0]);
              return (
                <li key={`${spec}-${i}`} className={ok ? "" : "is-off"} title={ok ? undefined : "Clé non configurée : ignoré"}>
                  <span className="truncate">{spec}</span>
                  {!ok && <em className="set-chain-off">sans clé</em>}
                  <button type="button" className="icon-btn" onClick={() => move(l.id, i, -1)} aria-label="Monter"><ArrowUp /></button>
                  <button type="button" className="icon-btn" onClick={() => move(l.id, i, 1)} aria-label="Descendre"><ArrowDown /></button>
                  <button type="button" className="icon-btn" onClick={() => remove(l.id, i)} aria-label="Retirer"><X /></button>
                </li>
              );
            })}
          </ol>
          <div className="flex gap-2">
            <input
              className="set-input"
              list="jarvis-brain-specs"
              placeholder="fournisseur ou fournisseur@modèle"
              value={adding[l.id]}
              onChange={(e) => setAdding({ ...adding, [l.id]: e.target.value })}
              onKeyDown={(e) => e.key === "Enter" && add(l.id)}
            />
            <button type="button" className="btn btn-ghost btn-sm" onClick={() => add(l.id)}><Plus />Ajouter</button>
          </div>
        </div>
      ))}
      <datalist id="jarvis-brain-specs">
        {options.map((o) => <option key={o} value={o} />)}
      </datalist>
      <div className="flex gap-2">
        <button type="button" className="btn btn-primary btn-sm" disabled={!dirty || busy} onClick={() => onSave(chains)}>
          Enregistrer les chaînes
        </button>
        <button type="button" className="btn btn-ghost btn-sm" disabled={!dirty || busy} onClick={() => setChains({ ...routing.chains })}>
          <ListRestart />Annuler
        </button>
      </div>
    </div>
    </details>
  );
}

/* ── Carte d'un fournisseur : clé visible directement ───────────────────── */

async function testProvider(name: string): Promise<TestResult> {
  const res = await api(`/providers/${name}/test`, { method: "POST" });
  return (await res.json()) as TestResult;
}

function ProviderCard({ p, active, onSaved, onActivate, startOpen }: {
  p: ProviderInfo;
  active: boolean;
  onSaved: (s: ProvidersStatus) => void;
  onActivate: () => Promise<void>;
  startOpen?: boolean;
}) {
  const [open, setOpen] = useState(!!startOpen);
  const [apiKey, setApiKey] = useState("");
  const [showKey, setShowKey] = useState(false);
  const [model, setModel] = useState(p.model);
  const [baseUrl, setBaseUrl] = useState(p.base_url);
  const [models, setModels] = useState<string[]>([]);
  const [busy, setBusy] = useState<"" | "key" | "save" | "test" | "models" | "use">("");
  const [result, setResult] = useState<TestResult | null>(null);
  useEffect(() => setModel(p.model), [p.model]);
  useEffect(() => setBaseUrl(p.base_url), [p.base_url]);

  const run = async (kind: typeof busy, fn: () => Promise<void>) => {
    setBusy(kind);
    setResult(null);
    try {
      await fn();
    } catch (e) {
      setResult({ ok: false, detail: e instanceof Error ? e.message : String(e) });
    } finally {
      setBusy("");
    }
  };

  const save = async (extra: Record<string, unknown> = {}) => {
    const body: Record<string, unknown> = { name: p.name, activate: false, model, base_url: baseUrl, ...extra };
    if (apiKey.trim()) body.api_key = apiKey.trim();
    onSaved(await postProviders(body));
    setApiKey("");
  };

  /** Enregistre la clé collée puis vérifie aussitôt qu'elle fonctionne. */
  const saveKey = () => run("key", async () => {
    await save();
    const t = await testProvider(p.name);
    setResult(t.ok ? { ok: true, detail: `Clé enregistrée — ${t.detail}` } : { ok: false, detail: `Clé enregistrée, mais : ${t.detail}` });
  });

  const loadModels = () => run("models", async () => {
    await save();
    const res = await api(`/providers/${p.name}/models`);
    const data = await res.json();
    if (!res.ok) throw new Error(String(data.detail ?? "Liste indisponible"));
    setModels(data.models ?? []);
    setResult({ ok: true, detail: `${(data.models ?? []).length} modèles trouvés : choisissez dans la liste du champ Modèle.` });
  });

  const removeCustom = () => run("save", async () => {
    const res = await api(`/providers/custom/${p.name}`, { method: "DELETE" });
    const data = await res.json();
    if (!res.ok) throw new Error(String(data.detail ?? "Suppression impossible"));
    onSaved(data as ProvidersStatus);
  });

  const hasKeyField = p.needs_key || p.custom;
  const listId = `models-${p.name}`;
  const summary = p.configured
    ? p.model || "modèle à définir"
    : p.needs_key ? "Clé API à renseigner" : p.base_url ? p.model || "modèle à définir" : "Adresse à renseigner";

  return (
    <div className={`set-pcard${active ? " is-active" : ""}${p.configured ? " is-ready" : ""}`}>
      <div className="set-pcard-head">
        <i className={p.configured ? "pdot ok" : "pdot"} title={p.configured ? "Prêt" : "Non configuré"} />
        <span className="set-provider-text">
          <strong>{p.label}{p.custom && <em className="set-tag">perso</em>}</strong>
          <small>{summary}{p.api_key_masked && ` · clé ${p.api_key_masked}`}</small>
        </span>
        {active ? (
          <span className="set-status ok"><CheckCircle size={14} /> Actif</span>
        ) : p.configured ? (
          <button type="button" className="btn btn-ghost btn-sm" disabled={!!busy} onClick={() => void run("use", onActivate)}>
            {busy === "use" ? <Loader2 className="animate-spin" /> : <Zap />}Utiliser
          </button>
        ) : null}
        <button
          type="button"
          className="icon-btn"
          aria-expanded={open}
          aria-label={open ? "Masquer les réglages" : "Modèle, adresse et autres réglages"}
          title="Modèle, adresse et autres réglages"
          onClick={() => setOpen(!open)}
        >
          {open ? <ChevronUp /> : <SlidersHorizontal />}
        </button>
      </div>

      {hasKeyField && (
        <div className="set-keyrow">
          <KeyRound size={15} aria-hidden />
          <input
            className="set-input"
            type={showKey ? "text" : "password"}
            autoComplete="off"
            spellCheck={false}
            aria-label={`Clé API ${p.label}`}
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && apiKey.trim() && void saveKey()}
            placeholder={p.api_key_masked ? `Remplacer la clé ${p.api_key_masked}…` : "Collez votre clé API ici"}
          />
          <button type="button" className="icon-btn" onClick={() => setShowKey(!showKey)} aria-label={showKey ? "Masquer la clé" : "Afficher la clé"}>
            {showKey ? <EyeOff /> : <Eye />}
          </button>
          <button type="button" className="btn btn-primary btn-sm" disabled={!apiKey.trim() || !!busy} onClick={() => void saveKey()}>
            {busy === "key" ? <Loader2 className="animate-spin" /> : <Save />}{p.api_key_masked ? "Remplacer" : "Enregistrer"}
          </button>
          {KEY_PAGES[p.name] && (
            <button type="button" className="btn btn-ghost btn-sm" onClick={() => void openExternal(KEY_PAGES[p.name])} title="Ouvre la page du fournisseur">
              <ExternalLink />Obtenir une clé
            </button>
          )}
        </div>
      )}

      {result && (
        <p className={`set-status ${result.ok ? "ok" : "err"}`} role="status">
          {result.ok ? <CheckCircle size={14} /> : <XCircle size={14} />} {result.detail}
        </p>
      )}

      {open && (
        <div className="set-editor">
          <label className="set-field">
            <span className="set-label">Modèle</span>
            <div className="flex gap-2">
              <input className="set-input" list={listId} value={model} onChange={(e) => setModel(e.target.value)} placeholder="nom-du-modele" spellCheck={false} />
              <button type="button" className="btn btn-ghost btn-sm" disabled={!!busy} onClick={() => void loadModels()}>
                {busy === "models" ? <Loader2 className="animate-spin" /> : <ListRestart />}Charger la liste
              </button>
            </div>
            <datalist id={listId}>{models.map((m) => <option key={m} value={m} />)}</datalist>
          </label>
          <label className="set-field">
            <span className="set-label">Adresse de l'API</span>
            <input className="set-input" value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)} placeholder="https://…/v1" spellCheck={false} />
          </label>
          <div className="flex flex-wrap gap-2">
            <button type="button" className="btn btn-primary btn-sm" disabled={!!busy} onClick={() => void run("save", async () => { await save(); setResult({ ok: true, detail: "Enregistré" }); })}>
              <Save />Enregistrer
            </button>
            <button type="button" className="btn btn-ghost btn-sm" disabled={!!busy} onClick={() => void run("test", async () => { await save(); setResult(await testProvider(p.name)); })}>
              {busy === "test" ? <Loader2 className="animate-spin" /> : <Plug />}Tester la connexion
            </button>
            {p.api_key_masked && (
              <button
                type="button"
                className="btn btn-danger btn-sm"
                disabled={!!busy}
                onClick={() => {
                  if (window.confirm(`Supprimer la clé ${p.label} ?`)) void run("save", () => save({ api_key: "" }));
                }}
              >
                <Trash2 />Supprimer la clé
              </button>
            )}
            {p.custom && (
              <button
                type="button"
                className="btn btn-danger btn-sm"
                disabled={!!busy}
                onClick={() => {
                  if (window.confirm(`Supprimer l'API « ${p.label} » ?`)) void removeCustom();
                }}
              >
                <Trash2 />Supprimer cette API
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

/* ── Ajouter une API ─────────────────────────────────────────────────────── */

/** Exemples d'APIs compatibles OpenAI, pour pré-remplir l'adresse. */
const API_TEMPLATES: { label: string; base_url: string; model: string; kind?: "openai" | "anthropic" }[] = [
  { label: "Together AI", base_url: "https://api.together.xyz/v1", model: "meta-llama/Llama-3.3-70B-Instruct-Turbo" },
  { label: "Fireworks AI", base_url: "https://api.fireworks.ai/inference/v1", model: "accounts/fireworks/models/llama-v3p3-70b-instruct" },
  { label: "Perplexity", base_url: "https://api.perplexity.ai", model: "sonar" },
  { label: "Moonshot (Kimi)", base_url: "https://api.moonshot.ai/v1", model: "kimi-latest" },
  { label: "Alibaba Qwen", base_url: "https://dashscope-intl.aliyuncs.com/compatible-mode/v1", model: "qwen-plus" },
  { label: "SambaNova", base_url: "https://api.sambanova.ai/v1", model: "Meta-Llama-3.3-70B-Instruct" },
  { label: "Nvidia NIM", base_url: "https://integrate.api.nvidia.com/v1", model: "meta/llama-3.3-70b-instruct" },
  { label: "vLLM / serveur local", base_url: "http://localhost:8000/v1", model: "" },
];

function AddApiForm({ onCreated }: { onCreated: (s: ProvidersStatus, name: string) => void }) {
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ label: "", base_url: "", model: "", api_key: "", kind: "openai" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const set = (k: keyof typeof form, v: string) => setForm((f) => ({ ...f, [k]: v }));

  const submit = async () => {
    setBusy(true);
    setError("");
    try {
      const res = await api("/providers/custom", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(String(data.detail ?? "Ajout refusé"));
      onCreated(data as ProvidersStatus, String(data.created));
      setForm({ label: "", base_url: "", model: "", api_key: "", kind: "openai" });
      setOpen(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  if (!open) {
    return (
      <button type="button" className="btn btn-primary btn-sm set-add-api" onClick={() => setOpen(true)}>
        <Plus />Ajouter une API
      </button>
    );
  }
  return (
    <div className="set-editor">
      <div className="set-label">Nouvelle API</div>
      <div className="set-templates">
        <span className="set-hint">Modèles :</span>
        {API_TEMPLATES.map((t) => (
          <button
            key={t.label}
            type="button"
            className="set-chip"
            onClick={() => setForm((f) => ({ ...f, label: t.label, base_url: t.base_url, model: t.model, kind: t.kind ?? "openai" }))}
          >
            {t.label}
          </button>
        ))}
      </div>
      <div className="set-grid2">
        <label className="set-field">
          <span className="set-label">Nom</span>
          <input className="set-input" value={form.label} onChange={(e) => set("label", e.target.value)} placeholder="Mon API" />
        </label>
        <label className="set-field">
          <span className="set-label">Format de l'API</span>
          <select className="set-input" value={form.kind} onChange={(e) => set("kind", e.target.value)}>
            <option value="openai">OpenAI (le plus courant)</option>
            <option value="anthropic">Anthropic</option>
          </select>
        </label>
        <label className="set-field">
          <span className="set-label">Adresse de l'API</span>
          <input className="set-input" value={form.base_url} onChange={(e) => set("base_url", e.target.value)} placeholder="https://…/v1" spellCheck={false} />
        </label>
        <label className="set-field">
          <span className="set-label">Modèle</span>
          <input className="set-input" value={form.model} onChange={(e) => set("model", e.target.value)} placeholder="nom-du-modele" spellCheck={false} />
        </label>
      </div>
      <label className="set-field">
        <span className="set-label"><KeyRound size={13} /> Clé API <em>(facultative pour un serveur local)</em></span>
        <input className="set-input" type="password" autoComplete="off" value={form.api_key} onChange={(e) => set("api_key", e.target.value)} placeholder="Collez votre clé ici" />
      </label>
      {error && <p className="set-status err" role="alert">{error}</p>}
      <div className="flex gap-2">
        <button type="button" className="btn btn-primary btn-sm" disabled={busy || !form.label.trim() || !form.base_url.trim()} onClick={() => void submit()}>
          {busy ? <Loader2 className="animate-spin" /> : <Plus />}Ajouter
        </button>
        <button type="button" className="btn btn-ghost btn-sm" onClick={() => setOpen(false)}>Annuler</button>
      </div>
    </div>
  );
}

/* ── Onglet ──────────────────────────────────────────────────────────────── */

/** Onglet CERVEAU — clés API, modèles, cerveau actif et routage AUTO.
 *  Les clés sont write-only : envoyées au serveur, jamais relues. */
export function ProvidersTab() {
  const [status, setStatus] = useState<ProvidersStatus | null>(null);
  const [busy, setBusy] = useState(false);
  const [filter, setFilter] = useState("");
  const [onlyReady, setOnlyReady] = useState(false);
  const [justCreated, setJustCreated] = useState("");
  const [error, setError] = useState("");

  const refresh = useCallback(() => {
    api("/providers")
      .then((r) => r.json())
      .then((d: ProvidersStatus) => setStatus(d))
      .catch(() => setError("Serveur injoignable"));
  }, []);
  useEffect(refresh, [refresh]);

  const apply = (next: ProvidersStatus) => {
    setStatus(next);
    // Mise à jour immédiate du HUD (label CERVEAU) sans attendre le WS
    useJarvisStore.setState({ providerLabel: next.active_label, providerModel: next.active_model });
  };

  const activate = async (name: string) => {
    setBusy(true);
    setError("");
    try {
      apply(await postProviders({ name, activate: true }));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const saveRouting = async (extra: Record<string, unknown>) => {
    if (!status) return;
    setBusy(true);
    setError("");
    try {
      apply(await postProviders({ name: status.active, activate: false, ...extra }));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  if (!status) {
    return (
      <p className="set-hint flex items-center gap-2">
        {error || <><Loader2 size={14} className="animate-spin" /> Chargement…</>}
      </p>
    );
  }

  const isAuto = status.active === "auto";
  const configuredCount = status.providers.filter((p) => p.configured).length;
  const q = filter.trim().toLowerCase();
  const shown = status.providers.filter((p) =>
    (!onlyReady || p.configured) && (!q || `${p.label} ${p.name} ${p.model}`.toLowerCase().includes(q)));
  const groups = [
    { title: "Vos APIs", items: shown.filter((p) => p.custom) },
    { title: "Services cloud (clé API)", items: shown.filter((p) => !p.custom && p.needs_key) },
    { title: "Locaux et gratuits sans clé", items: shown.filter((p) => !p.custom && !p.needs_key) },
  ];

  return (
    <>
      <div className="set-banner">
        <Cpu size={16} />
        <span>
          Cerveau actif : <strong>{status.active_label}</strong>
          {status.active_model && <em> · {status.active_model}</em>}
        </span>
      </div>
      {error && <p className="set-status err" role="alert">{error}</p>}

      <Section
        title="Clés API et fournisseurs"
        hint="Collez une clé puis « Enregistrer » : elle est vérifiée aussitôt. Les clés restent sur votre machine, côté serveur, et ne sont jamais réaffichées. En cas de panne d'un cerveau cloud, JARVIS bascule sur le cerveau local."
      >
        <div className="set-providers-tools">
          <input
            className="set-input"
            type="search"
            placeholder="Filtrer les fournisseurs…"
            aria-label="Filtrer les fournisseurs"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
          />
          <label className="set-check">
            <input type="checkbox" checked={onlyReady} onChange={(e) => setOnlyReady(e.target.checked)} />
            Seulement ceux qui sont prêts ({configuredCount})
          </label>
        </div>
        <AddApiForm onCreated={(next, name) => { apply(next); setJustCreated(name); setFilter(""); setOnlyReady(false); }} />
        <div className="set-providers">
          <button
            type="button"
            className={`set-provider${status.active === "local" ? " is-active" : ""}`}
            disabled={busy || !status.local_available}
            onClick={() => void activate("local")}
          >
            <i className={status.local_available ? "pdot ok" : "pdot"} />
            <span className="set-provider-text">
              <strong>Local (Mistral GGUF)</strong>
              <small>{status.local_available ? "100 % privé · hors ligne" : "Modèle local non installé"}</small>
            </span>
            {status.active === "local" && <CheckCircle size={16} />}
          </button>
          {groups.map((g) => g.items.length > 0 && (
            <div key={g.title} className="set-pgroup">
              <div className="set-pgroup-title">{g.title}</div>
              {g.items.map((p) => (
                <ProviderCard
                  key={p.name}
                  p={p}
                  active={status.active === p.name}
                  startOpen={p.name === justCreated}
                  onSaved={apply}
                  onActivate={() => activate(p.name)}
                />
              ))}
            </div>
          ))}
        </div>
      </Section>
      <Section
        title="Mode AUTO — un cerveau par niveau de réflexion"
        hint="Chaque demande part vers le premier cerveau disponible de sa chaîne ; si le premier tarde, le suivant démarre en parallèle et le plus rapide répond. Les cerveaux grisés n'ont pas de clé et sont ignorés. Écrivez « fournisseur@modèle » pour imposer un modèle."
      >
        <div className="flex flex-wrap items-center gap-3">
          {isAuto ? (
            <span className="set-status ok"><Zap size={14} /> Mode AUTO actif</span>
          ) : (
            <button type="button" className="btn btn-primary btn-sm" disabled={busy || configuredCount === 0} onClick={() => void activate("auto")}>
              <Zap />Activer le mode AUTO
            </button>
          )}
          {status.routing && (
            <label className="set-check">
              <input
                type="checkbox"
                checked={status.routing.hedging}
                disabled={busy}
                onChange={(e) => void saveRouting({ hedging: e.target.checked })}
              />
              Course au premier mot
            </label>
          )}
        </div>
        {status.routing && (
          <dl className="set-resolved">
            {LEVELS.map((l) => (
              <div key={l.id}>
                <dt>{l.label}</dt>
                <dd>{status.routing!.resolved[l.id]?.slice(0, 3).join("  →  ") || "aucun cerveau avec clé (cerveau local)"}</dd>
              </div>
            ))}
          </dl>
        )}
        <ChainEditor status={status} busy={busy} onSave={(chains) => void saveRouting({ chains })} />
      </Section>

    </>
  );
}
