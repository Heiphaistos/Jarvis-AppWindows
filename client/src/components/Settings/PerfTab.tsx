import { useEffect, useState } from "react";
import { Gauge, Loader2, Zap, Scale, Leaf, ShieldCheck } from "lucide-react";
import { useJarvisStore } from "../../stores/jarvisStore";

const API = "http://127.0.0.1:8765/api/performance";

interface PerfProfile {
  name: string;
  label: string;
  description: string;
  n_gpu_layers: number;
  n_ctx: number;
  max_tokens: number;
}

const ICONS: Record<string, typeof Zap> = { max: Zap, balanced: Scale, eco: Leaf };

/** Onglet PERF — profils prédéfinis, rechargement des modèles en arrière-plan. */
export function PerfTab() {
  const [profiles, setProfiles] = useState<PerfProfile[]>([]);
  const [active, setActive] = useState("");
  const [reloading, setReloading] = useState(false);
  const [error, setError] = useState("");
  const perfActive = useJarvisStore((s) => s.perfActive);

  // Le serveur confirme (ou rétrograde via protocole matériel) → sync UI
  useEffect(() => {
    if (perfActive) {
      setActive(perfActive);
      setReloading(false);
    }
  }, [perfActive]);

  useEffect(() => {
    fetch(API)
      .then((r) => r.json())
      .then((d) => {
        setProfiles(d.profiles ?? []);
        setActive(d.active ?? "");
      })
      .catch(() => setError("Serveur injoignable"));
  }, []);

  const apply = async (name: string) => {
    if (name === active || reloading) return;
    setError("");
    setReloading(true);
    try {
      const res = await fetch(API, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ profile: name }),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(String(data.detail ?? "Erreur"));
      } else {
        setActive(data.active);
      }
    } catch {
      setError("Serveur injoignable");
    } finally {
      // Le rechargement continue côté serveur (~30-60 s) — notice à la fin
      setTimeout(() => setReloading(false), 4000);
    }
  };

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center gap-2 text-[9px] text-blue-400/50">
        <Gauge size={12} className="text-cyan-400" />
        Le changement recharge les modèles (~30-60 s). JARVIS reste accessible pendant l'opération.
      </div>
      <div className="flex items-start gap-2 p-2.5 rounded-lg text-[9px] text-blue-400/50"
        style={{ background: "rgba(0,255,136,0.05)", border: "1px solid rgba(0,255,136,0.15)" }}>
        <ShieldCheck size={13} className="text-green-400 shrink-0 mt-0.5" />
        <span>
          <span className="text-green-400 font-bold">Protocole matériel actif</span> — démarrage
          toujours en Économie, VRAM plafonnée à 80 % : en cas de dépassement soutenu, le profil
          est rétrogradé automatiquement pour protéger votre carte graphique.
        </span>
      </div>

      {error && <div className="text-[9px] text-red-400 px-1">{error}</div>}
      {reloading && (
        <div className="flex items-center gap-2 text-[10px] text-amber-400">
          <Loader2 size={11} className="animate-spin" /> Rechargement des modèles en cours…
        </div>
      )}

      <div className="flex flex-col gap-1.5">
        {profiles.map((p) => {
          const Icon = ICONS[p.name] ?? Gauge;
          const isActive = p.name === active;
          return (
            <button
              key={p.name}
              onClick={() => void apply(p.name)}
              disabled={reloading}
              className="flex items-start gap-3 p-3 rounded-xl text-left transition-all disabled:opacity-50"
              style={{
                background: isActive ? "rgb(var(--accent-rgb) / 0.1)" : "rgba(255,255,255,0.02)",
                border: `1px solid ${isActive ? "rgb(var(--accent-rgb) / 0.35)" : "rgba(255,255,255,0.06)"}`,
              }}
            >
              <Icon size={16} className={isActive ? "text-cyan-400 mt-0.5" : "text-blue-400/40 mt-0.5"} />
              <div className="flex-1">
                <div className="text-[12px] font-bold tracking-wider"
                  style={{ color: isActive ? "var(--accent)" : "#ffffff88" }}>
                  {p.label}
                  {isActive && <span className="ml-2 text-[8px] text-green-400">● ACTIF</span>}
                </div>
                <div className="text-[9px] text-blue-400/40 mt-0.5 leading-relaxed">{p.description}</div>
                <div className="text-[8px] text-blue-400/30 mt-1 font-mono">
                  GPU {p.n_gpu_layers === -1 ? "100%" : `${p.n_gpu_layers} couches`} · contexte {p.n_ctx} · réponses ≤{p.max_tokens} tokens
                </div>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}
