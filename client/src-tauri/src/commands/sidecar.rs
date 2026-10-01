use std::net::TcpStream;
use std::path::{Path, PathBuf};
use std::process::{Child, Command};
use std::sync::Mutex;
use tauri::State;

#[cfg(windows)]
use std::os::windows::process::CommandExt;

/// Processus serveur lancé par l'application + dossier des ressources du bundle.
pub struct SidecarState(pub Mutex<Option<Child>>, pub Mutex<Option<PathBuf>>);

#[cfg(windows)]
const SERVER_BIN: &str = "jarvis_server.exe";
#[cfg(not(windows))]
const SERVER_BIN: &str = "jarvis_server";

/// True if something is already listening on 127.0.0.1:8765
fn is_server_running() -> bool {
    TcpStream::connect("127.0.0.1:8765").is_ok()
}

fn exe_dir() -> Option<PathBuf> {
    Some(std::env::current_exe().ok()?.parent()?.to_path_buf())
}

/// Serveur Python compilé (PyInstaller) : ressource du bundle (installeur,
/// .deb, AppImage — remplacée à chaque mise à jour) ou fichier du zip portable,
/// à côté de l'exécutable.
fn server_exe(resource_dir: Option<&Path>) -> Result<PathBuf, String> {
    let candidates: Vec<PathBuf> = resource_dir
        .into_iter()
        .map(Path::to_path_buf)
        .chain(exe_dir())
        .map(|d| d.join(SERVER_BIN))
        .collect();
    candidates
        .iter()
        .find(|p| p.is_file())
        .cloned()
        .ok_or_else(|| match candidates.first() {
            Some(p) => format!("{SERVER_BIN} introuvable ({})", p.display()),
            None => format!("{SERVER_BIN} introuvable"),
        })
}

/// Dossier models/ : à côté de JARVIS.exe sous Windows (portable, installeur
/// utilisateur) ; sous Linux l'application est en lecture seule (/usr, AppImage)
/// → ~/.local/share/JARVIS/models.
fn models_dir() -> Option<PathBuf> {
    #[cfg(windows)]
    {
        Some(exe_dir()?.join("models"))
    }
    #[cfg(not(windows))]
    {
        let base = std::env::var_os("XDG_DATA_HOME")
            .map(PathBuf::from)
            .or_else(|| std::env::var_os("HOME").map(|h| PathBuf::from(h).join(".local/share")))?;
        Some(base.join("JARVIS").join("models"))
    }
}

/// Start the Python server silently. Idempotent: does nothing if already running.
pub fn launch_server(state: &SidecarState) -> Result<(), String> {
    if is_server_running() {
        return Ok(());
    }

    let mut guard = state.0.lock().map_err(|e| e.to_string())?;
    if guard.is_some() {
        return Ok(());
    }

    let resource_dir = state.1.lock().map_err(|e| e.to_string())?.clone();
    let server_exe = server_exe(resource_dir.as_deref())?;

    let mut cmd = Command::new(&server_exe);

    // Indique au serveur où trouver les modèles
    if let Some(models) = models_dir() {
        let _ = std::fs::create_dir_all(&models);
        cmd.env("JARVIS_MODELS_DIR", models.to_string_lossy().as_ref());
    }

    // Répertoire de travail = dossier de JARVIS.exe (Windows) ; sous Linux le
    // serveur range ses données dans ~/.local/share/JARVIS.
    #[cfg(windows)]
    if let Some(dir) = exe_dir() {
        cmd.current_dir(dir);
    }

    #[cfg(windows)]
    cmd.creation_flags(0x08000000); // CREATE_NO_WINDOW

    let child = cmd
        .spawn()
        .map_err(|e| format!("Impossible de démarrer {SERVER_BIN}: {e}"))?;

    *guard = Some(child);
    Ok(())
}

/// Kill the managed server process if we own it.
pub fn kill_server(state: &SidecarState) {
    if let Ok(mut guard) = state.0.lock() {
        if let Some(mut child) = guard.take() {
            let _ = child.kill();
            let _ = child.wait();
        }
    }
}

#[tauri::command]
pub fn start_server(state: State<'_, SidecarState>) -> Result<(), String> {
    launch_server(&state)
}

#[tauri::command]
pub fn stop_server(state: State<'_, SidecarState>) -> Result<(), String> {
    kill_server(&state);
    Ok(())
}
