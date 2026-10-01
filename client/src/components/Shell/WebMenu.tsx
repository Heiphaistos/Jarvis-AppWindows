import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { Power, LogOut, Globe } from "lucide-react";
import { api } from "../../lib/platform";
import { logout, serverMode, stopAgent } from "../../lib/session";

/** Remplace les boutons de fenêtre quand JARVIS tourne dans un navigateur. */
export function WebMenu() {
  const mode = serverMode();
  const [open, setOpen] = useState(false);
  const [autostart, setAutostart] = useState<boolean | null>(null);
  const [stopped, setStopped] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open || mode !== "agent") return;
    api("/agent/autostart")
      .then((r) => r.json())
      .then((d: { enabled: boolean }) => setAutostart(d.enabled))
      .catch(() => setAutostart(null));
  }, [open, mode]);

  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent) => {
      const t = e.target as Node;
      if (!ref.current?.contains(t) && !menuRef.current?.contains(t)) setOpen(false);
    };
    window.addEventListener("mousedown", close);
    return () => window.removeEventListener("mousedown", close);
  }, [open]);

  const toggleAutostart = async () => {
    const next = !autostart;
    const r = await api("/agent/autostart", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ enabled: next }),
    }).catch(() => null);
    if (r?.ok) setAutostart(next);
  };

  const stop = async () => {
    if (!window.confirm("Arrêter JARVIS ? Les routines et rappels ne seront plus annoncés.")) return;
    await stopAgent();
    setStopped(true);
  };

  if (stopped) {
    return <span className="chip" style={{ color: "var(--amber)" }}>JARVIS ARRÊTÉ — fermez l'onglet</span>;
  }

  return (
    <div ref={ref} style={{ position: "relative" }}>
      <button
        className="icon-btn"
        onClick={() => setOpen((v) => !v)}
        title={mode === "hosted" ? "Version web" : "Panneau web"}
        aria-label="Menu du panneau web"
        aria-expanded={open}
      >
        <Globe />
      </button>
      {open && createPortal(
        <div ref={menuRef} className="web-menu panel" role="menu">
          <div className="readout" style={{ marginBottom: 8 }}>
            {mode === "hosted" ? "Version web hébergée" : "Panneau web local"}
          </div>
          {mode === "agent" && (
            <>
              <label className="web-menu-row">
                <input
                  type="checkbox"
                  checked={!!autostart}
                  disabled={autostart === null}
                  onChange={() => void toggleAutostart()}
                />
                Démarrer avec la session
              </label>
              <button className="web-menu-row danger" onClick={() => void stop()} role="menuitem">
                <Power size={14} /> Arrêter JARVIS
              </button>
            </>
          )}
          {mode === "hosted" && (
            <button className="web-menu-row" onClick={() => void logout()} role="menuitem">
              <LogOut size={14} /> Se déconnecter
            </button>
          )}
        </div>,
        document.body,
      )}
    </div>
  );
}
