import React, { useEffect, useState } from "react";
import ReactDOM from "react-dom/client";
import "./index.css";
import App from "./App";
import { Gate } from "./components/Shell/Gate";
import { bootstrapSession, type SessionState } from "./lib/session";

/** Application : direct. Navigateur : ouvrir la session avant de se connecter au serveur. */
function Root() {
  const [session, setSession] = useState<SessionState | null>(null);
  useEffect(() => {
    void bootstrapSession().then(setSession);
  }, []);
  if (!session) return null;
  if (!session.authenticated) {
    return <Gate session={session} onAuthenticated={() => void bootstrapSession().then(setSession)} />;
  }
  return <App />;
}

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <Root />
  </React.StrictMode>,
);
