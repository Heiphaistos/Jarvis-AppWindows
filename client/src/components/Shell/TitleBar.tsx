import { useEffect, useRef } from "react";
import { getCurrentWindow } from "@tauri-apps/api/window";
import { isTauri } from "../../lib/platform";
import { WebMenu } from "./WebMenu";
import { LayoutDashboard, Maximize2, Columns2, MessageSquare, ArrowLeftRight } from "lucide-react";
import { useJarvisStore } from "../../stores/jarvisStore";
import type { LayoutName } from "../../stores/jarvisStore";
import { SettingsPanel } from "../Settings/SettingsPanel";
import pkg from "../../../package.json";

export const LAYOUT_OPTIONS: { id: LayoutName; label: string; icon: typeof LayoutDashboard; hint: string }[] = [
  { id: "hud", label: "HUD", icon: LayoutDashboard, hint: "Télémétrie, hologramme et conversation côte à côte" },
  { id: "immersive", label: "Immersif", icon: Maximize2, hint: "Hologramme plein cadre, conversation flottante" },
  { id: "split", label: "Duo", icon: Columns2, hint: "Panneau hologramme + grande conversation" },
  { id: "compact", label: "Compact", icon: MessageSquare, hint: "Conversation seule, sans 3D (le plus léger)" },
];

export function BrandMark() {
  return (
    <svg className="brand-mark" viewBox="0 0 40 40" fill="none" stroke="currentColor" aria-hidden>
      <circle cx="20" cy="20" r="18" strokeOpacity="0.35" />
      <circle className="spin" cx="20" cy="20" r="14" strokeWidth="2" strokeDasharray="6 5" />
      <circle className="spin-rev" cx="20" cy="20" r="9" strokeWidth="1.5" strokeDasharray="20 8" />
      <circle cx="20" cy="20" r="4" fill="currentColor" stroke="none" />
    </svg>
  );
}

function Clock() {
  const ref = useRef<HTMLSpanElement>(null);
  useEffect(() => {
    const tick = () => {
      if (ref.current) ref.current.textContent = new Date().toLocaleTimeString("fr-FR");
    };
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, []);
  return <span ref={ref} className="tb-clock" data-tauri-drag-region />;
}

function WindowControls() {
  const win = () => getCurrentWindow();
  return (
    <div className="flex">
      <button className="win-btn" onClick={() => void win().minimize()} title="Réduire" aria-label="Réduire">
        <svg width="11" height="11" viewBox="0 0 11 11"><rect y="5" width="11" height="1" fill="currentColor" /></svg>
      </button>
      <button className="win-btn" onClick={() => void win().toggleMaximize()} title="Agrandir" aria-label="Agrandir">
        <svg width="10" height="10" viewBox="0 0 10 10" fill="none" stroke="currentColor"><rect x="0.5" y="0.5" width="9" height="9" rx="1" /></svg>
      </button>
      <button className="win-btn close" onClick={() => void win().close()} title="Fermer" aria-label="Fermer">
        <svg width="11" height="11" viewBox="0 0 11 11" stroke="currentColor" strokeWidth="1.1"><path d="M1 1l9 9M10 1l-9 9" /></svg>
      </button>
    </div>
  );
}

/** Barre de titre : grille 1fr | auto | 1fr — rien ne peut se chevaucher. */
export function TitleBar() {
  const isConnected = useJarvisStore((s) => s.isConnected);
  const layout = useJarvisStore((s) => s.layout);
  const setLayout = useJarvisStore((s) => s.setLayout);
  const layoutSide = useJarvisStore((s) => s.layoutSide);
  const setLayoutSide = useJarvisStore((s) => s.setLayoutSide);
  const canMirror = layout === "hud" || layout === "split";

  return (
    <header className="titlebar" data-tauri-drag-region>
      <div className="tb-left" data-tauri-drag-region>
        <div className="brand" data-tauri-drag-region>
          <BrandMark />
          <span className="brand-name" data-tauri-drag-region>J.A.R.V.I.S.</span>
        </div>
        <span className="chip hidden min-[900px]:inline-flex" data-tauri-drag-region>
          <span className="dot live" style={{ "--c": isConnected ? "var(--green)" : "var(--red)" } as React.CSSProperties} />
          {isConnected ? "CORE EN LIGNE" : "CORE HORS LIGNE"}
        </span>
      </div>

      <nav className="segmented" aria-label="Disposition">
        {LAYOUT_OPTIONS.map(({ id, label, icon: Icon, hint }) => (
          <button key={id} aria-pressed={layout === id} onClick={() => setLayout(id)} title={hint}>
            <Icon />
            <span className="seg-label">{label}</span>
          </button>
        ))}
      </nav>

      <div className="tb-right" data-tauri-drag-region>
        <Clock />
        <span className="chip hidden min-[1000px]:inline-flex" data-tauri-drag-region>v{pkg.version}</span>
        {canMirror && (
          <button
            className="icon-btn"
            onClick={() => setLayoutSide(layoutSide === "left" ? "right" : "left")}
            title="Inverser gauche / droite"
            aria-label="Inverser gauche / droite"
          >
            <ArrowLeftRight />
          </button>
        )}
        <SettingsPanel />
        <span className="tb-sep" />
        {isTauri ? <WindowControls /> : <WebMenu />}
      </div>
    </header>
  );
}
