import { useJarvisStore, THEMES, accentOf } from "../../stores/jarvisStore";
import type { ThemeName, HoloStyle, HoloDensity, HoloSpeed, SkinName, LayoutName } from "../../stores/jarvisStore";
import {
  Globe2, Disc3, Sparkles, Dna, Grid3x3, Tornado, Pipette, Snowflake, Turtle, Rabbit,
} from "lucide-react";

const SKIN_OPTIONS: { id: SkinName; label: string; description: string; bg: string; panel: string; radius: number }[] = [
  { id: "holo", label: "Holographique", description: "Le style du site : verre, néons, coins HUD", bg: "radial-gradient(circle at 50% 0%, #0a2140, #020a16)", panel: "rgba(0,212,255,0.14)", radius: 6 },
  { id: "minimal", label: "Épuré", description: "Sombre mat, typographie système, aucun effet", bg: "#0b0d12", panel: "rgba(255,255,255,0.06)", radius: 6 },
  { id: "aurora", label: "Aurora", description: "Dégradés mouvants et verre épais", bg: "linear-gradient(135deg, #2a1a6e, #07051a 55%, #0b3c5a)", panel: "rgba(255,255,255,0.12)", radius: 9 },
  { id: "tactical", label: "Tactique", description: "Console militaire, angles vifs, monospace", bg: "repeating-linear-gradient(0deg, #030806 0 7px, #0a1a12 7px 8px)", panel: "rgba(0,255,136,0.1)", radius: 1 },
];

// Gabarit miniature de chaque disposition : colonnes CSS + cases (h = hologramme)
const LAYOUT_PREVIEWS: { id: LayoutName; label: string; description: string; cols: string; cells: ("p" | "h" | "c")[] }[] = [
  { id: "hud", label: "HUD", description: "Télémétrie, hologramme, conversation", cols: "1fr 1.4fr 1.6fr", cells: ["p", "h", "c"] },
  { id: "immersive", label: "Immersif", description: "Hologramme plein cadre", cols: "1fr", cells: ["h"] },
  { id: "split", label: "Duo", description: "Hologramme + grande conversation", cols: "1fr 2fr", cells: ["h", "c"] },
  { id: "compact", label: "Compact", description: "Conversation seule, sans 3D", cols: "1fr", cells: ["c"] },
];

const HOLO_OPTIONS: { id: HoloStyle; label: string; icon: typeof Globe2 }[] = [
  { id: "sphere", label: "Sphère orbitale", icon: Globe2 },
  { id: "reactor", label: "Réacteur Arc", icon: Disc3 },
  { id: "galaxy", label: "Nébuleuse", icon: Sparkles },
  { id: "dna", label: "Hélice ADN", icon: Dna },
  { id: "matrix", label: "Matrice", icon: Grid3x3 },
  { id: "vortex", label: "Vortex", icon: Tornado },
];

const DENSITY_OPTIONS: { id: HoloDensity; label: string }[] = [
  { id: "low", label: "Légère" },
  { id: "normal", label: "Normale" },
  { id: "high", label: "Dense" },
];

const SPEED_OPTIONS: { id: HoloSpeed; label: string; icon: typeof Turtle }[] = [
  { id: "slow", label: "Lente", icon: Turtle },
  { id: "normal", label: "Normale", icon: Snowflake },
  { id: "fast", label: "Rapide", icon: Rabbit },
];

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-2.5">
      <div className="rail-title">{title}</div>
      {children}
    </div>
  );
}

function Chip({ active, onClick, children, title }: { active: boolean; onClick: () => void; children: React.ReactNode; title?: string }) {
  return (
    <button
      onClick={onClick}
      title={title}
      aria-pressed={active}
      className="opt-card flex! items-center gap-2.5 text-[11.5px]"
      style={{ color: active ? "var(--accent)" : "var(--ink-soft)" }}
    >
      {children}
    </button>
  );
}

/** Onglet APPARENCE — esthétique, disposition, palette, hologramme. */
export function ThemeTab() {
  const s = useJarvisStore();
  const accent = accentOf(s.theme, s.customAccent);

  return (
    <div className="flex flex-col gap-6">
      <Section title="Esthétique">
        <div className="opt-grid">
          {SKIN_OPTIONS.map((o) => (
            <button key={o.id} className="opt-card" aria-pressed={s.skin === o.id} onClick={() => s.setSkin(o.id)}>
              <div className="opt-preview" style={{ background: o.bg, gridTemplateColumns: "1fr 2fr" }}>
                <i style={{ background: o.panel, borderRadius: o.radius, border: `1px solid ${accent}55` }} />
                <i style={{ background: o.panel, borderRadius: o.radius, border: `1px solid ${accent}55` }} />
              </div>
              <strong>{o.label}</strong>
              <small>{o.description}</small>
            </button>
          ))}
        </div>
      </Section>

      <Section title="Disposition">
        <div className="opt-grid">
          {LAYOUT_PREVIEWS.map((o) => (
            <button key={o.id} className="opt-card" aria-pressed={s.layout === o.id} onClick={() => s.setLayout(o.id)}>
              <div className="opt-preview" style={{ background: "rgba(0,0,0,0.35)", gridTemplateColumns: o.cols }}>
                {o.cells.map((c, i) => (
                  <i
                    key={i}
                    style={
                      c === "h"
                        ? { background: `radial-gradient(circle, ${accent}bb 0 14%, ${accent}22 15% 40%, transparent 42%)` }
                        : { background: c === "c" ? `${accent}26` : `${accent}14`, border: `1px solid ${accent}44` }
                    }
                  />
                ))}
              </div>
              <strong>{o.label}</strong>
              <small>{o.description}</small>
            </button>
          ))}
        </div>
      </Section>

      <Section title="Palette">
        <div className="grid grid-cols-3 gap-2">
          {(Object.keys(THEMES) as ThemeName[])
            .filter((n) => n !== "custom")
            .map((name) => {
              const t = THEMES[name];
              return (
                <Chip key={name} active={s.theme === name} onClick={() => s.setTheme(name)}>
                  <span
                    className="w-4 h-4 rounded-full shrink-0"
                    style={{ background: `radial-gradient(circle at 35% 35%, ${t.accent}, ${t.accentSoft})`, boxShadow: `0 0 10px ${t.accent}88` }}
                  />
                  {t.label}
                </Chip>
              );
            })}
          <label
            className="opt-card flex! items-center gap-2.5 text-[11.5px] cursor-pointer"
            aria-pressed={s.theme === "custom"}
            style={{ color: s.theme === "custom" ? "var(--accent)" : "var(--ink-soft)" }}
          >
            <Pipette size={14} />
            <span className="flex-1">Libre</span>
            <input
              type="color"
              value={s.customAccent}
              onChange={(e) => {
                s.setCustomAccent(e.target.value);
                s.setTheme("custom");
              }}
              className="w-7 h-5 rounded cursor-pointer bg-transparent border-0"
            />
          </label>
        </div>
      </Section>

      <Section title="Hologramme">
        <div className="grid grid-cols-3 gap-2">
          {HOLO_OPTIONS.map(({ id, label, icon: Icon }) => (
            <Chip key={id} active={s.holoStyle === id} onClick={() => s.setHoloStyle(id)}>
              <Icon size={15} />
              {label}
            </Chip>
          ))}
        </div>
      </Section>

      <div className="grid grid-cols-2 gap-4">
        <Section title="Densité">
          <div className="flex gap-1.5">
            {DENSITY_OPTIONS.map(({ id, label }) => (
              <Chip key={id} active={s.holoDensity === id} onClick={() => s.setHoloDensity(id)}>
                <span className="mx-auto">{label}</span>
              </Chip>
            ))}
          </div>
        </Section>
        <Section title="Vitesse">
          <div className="flex gap-1.5">
            {SPEED_OPTIONS.map(({ id, label, icon: Icon }) => (
              <Chip key={id} active={s.holoSpeed === id} onClick={() => s.setHoloSpeed(id)} title={label}>
                <Icon size={14} className="mx-auto" />
              </Chip>
            ))}
          </div>
        </Section>
      </div>
    </div>
  );
}
