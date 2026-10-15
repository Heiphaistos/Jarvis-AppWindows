import { useEffect } from "react";
import { RefreshCw } from "lucide-react";
import { Row, Section, Toggle } from "../Settings/controls";
import { checkForUpdate, installUpdate, updaterAvailable, useUpdateStore } from "../../lib/updater";

/** Vérification silencieuse au démarrage (si le réglage est actif). */
export function useStartupUpdateCheck() {
  useEffect(() => {
    if (useUpdateStore.getState().auto) void checkForUpdate(true);
  }, []);
}

/** Fenêtre de confirmation, progression et erreurs. */
export function UpdateDialog() {
  const { phase, version, notes, percent, error, dismiss } = useUpdateStore();
  if (phase === "idle" || phase === "checking") return null;
  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center" style={{ background: "rgba(0,0,0,0.6)" }} role="dialog" aria-modal="true" aria-label="Mise à jour">
      <div className="panel flex flex-col gap-3 p-5" style={{ width: 440, maxWidth: "90vw" }}>
        {phase === "available" && (
          <>
            <h3 className="set-title">Nouvelle version disponible</h3>
            <p className="set-hint">JARVIS {version} est disponible. L'application redémarrera après l'installation.</p>
            {notes && <pre className="set-hint" style={{ whiteSpace: "pre-wrap", maxHeight: 200, overflow: "auto" }}>{notes}</pre>}
            <div className="flex gap-2 justify-end">
              <button type="button" className="btn btn-ghost btn-sm" onClick={dismiss}>Plus tard</button>
              <button type="button" className="btn btn-primary btn-sm" onClick={() => void installUpdate()}>Mettre à jour maintenant</button>
            </div>
          </>
        )}
        {phase === "installing" && (
          <>
            <h3 className="set-title">Installation de la mise à jour</h3>
            <p className="set-hint">{percent === null ? "Téléchargement en cours…" : `Téléchargement : ${percent} %`}</p>
            <progress value={percent ?? undefined} max={100} style={{ width: "100%" }} />
          </>
        )}
        {phase === "uptodate" && (
          <>
            <h3 className="set-title">Mise à jour</h3>
            <p className="set-hint">JARVIS est à jour.</p>
            <div className="flex justify-end"><button type="button" className="btn btn-ghost btn-sm" onClick={dismiss}>Fermer</button></div>
          </>
        )}
        {phase === "error" && (
          <>
            <h3 className="set-title">Mise à jour impossible</h3>
            <p className="set-hint">{error}</p>
            <div className="flex justify-end"><button type="button" className="btn btn-ghost btn-sm" onClick={dismiss}>Fermer</button></div>
          </>
        )}
      </div>
    </div>
  );
}

/** Bloc des réglages : interrupteur + bouton « Rechercher une mise à jour ». */
export function UpdateSection() {
  const auto = useUpdateStore((s) => s.auto);
  const setAuto = useUpdateStore((s) => s.setAuto);
  const phase = useUpdateStore((s) => s.phase);
  return (
    <Section
      title="Mises à jour"
      hint={updaterAvailable ? "Les mises à jour sont vérifiées par signature avant installation." : "Disponible uniquement dans l'application installée."}
    >
      <Row label="Vérifier les mises à jour automatiquement" hint="Au démarrage de JARVIS.">
        <Toggle label="Vérifier les mises à jour automatiquement" checked={auto} onChange={setAuto} />
      </Row>
      <Row label="Version à jour ?">
        <button type="button" className="btn btn-ghost btn-sm" disabled={!updaterAvailable || phase === "checking"} onClick={() => void checkForUpdate(false)}>
          <RefreshCw />{phase === "checking" ? "Recherche…" : "Rechercher une mise à jour"}
        </button>
      </Row>
    </Section>
  );
}
