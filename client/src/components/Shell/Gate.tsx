import { useState, type FormEvent } from "react";
import { BrandMark } from "./TitleBar";
import { login, type SessionState } from "../../lib/session";

/** Écran affiché avant l'interface quand le navigateur n'a pas (encore) de session. */
export function Gate({ session, onAuthenticated }: { session: SessionState; onAuthenticated: () => void }) {
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    const err = await login(password);
    setBusy(false);
    if (err) {
      setError(err);
      setPassword("");
    } else {
      onAuthenticated();
    }
  };

  let body;
  if (session.offline) {
    body = (
      <p>
        Le serveur JARVIS ne répond pas. Relancez <b>JARVIS Web</b> sur ce PC, puis
        rechargez la page.
      </p>
    );
  } else if (session.mode === "hosted") {
    body = session.passwordConfigured === false ? (
      <p>Aucun mot de passe n'est configuré sur le serveur (variable <code>JARVIS_PASSWORD</code>).</p>
    ) : (
      <form onSubmit={(e) => void submit(e)} className="gate-form">
        <label htmlFor="jarvis-pass">Mot de passe</label>
        <input
          id="jarvis-pass"
          type="password"
          autoComplete="current-password"
          autoFocus
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
        <button type="submit" disabled={busy || !password}>
          {busy ? "Vérification…" : "Entrer"}
        </button>
        {error && <p role="alert" className="gate-error">{error}</p>}
      </form>
    );
  } else {
    body = (
      <p>
        Ce panneau s'ouvre avec la clé fournie au lancement. Relancez <b>JARVIS Web</b> :
        l'onglet s'ouvrira de lui-même, déjà connecté.
      </p>
    );
  }

  return (
    <div className="gate">
      <div className="gate-card panel">
        <div className="brand" style={{ justifyContent: "center", marginBottom: 14 }}>
          <BrandMark />
          <span className="brand-name">J.A.R.V.I.S.</span>
        </div>
        {body}
      </div>
    </div>
  );
}
