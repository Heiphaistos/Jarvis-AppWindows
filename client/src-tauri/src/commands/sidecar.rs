use std::net::TcpStream;
use std::process::{Child, Command};
use std::sync::Mutex;
use tauri::State;

#[cfg(windows)]
use std::os::windows::process::CommandExt;

pub struct SidecarState(pub Mutex<Option<Child>>);

/// Serveur Python compilé (PyInstaller) — embarqué dans le binaire à la compilation
static SERVER_EXE: &[u8] = include_bytes!("../../resources/jarvis_server.exe");

/// True if something is already listening on 127.0.0.1:8765
fn is_server_running() -> bool {
    TcpStream::connect("127.0.0.1:8765").is_ok()
}

/// Extrait jarvis_server.exe à côté de JARVIS.exe si absent ou différent.
/// Retourne le chemin de l'exe extrait.
fn extract_server_exe() -> Result<std::path::PathBuf, String> {
    let exe = std::env::current_exe().map_err(|e| e.to_string())?;
    let dir = exe.parent().ok_or("Impossible de trouver le dossier de JARVIS.exe")?;
    let server_path = dir.join("jarvis_server.exe");

    if !server_path.exists() {
        std::fs::write(&server_path, SERVER_EXE)
            .map_err(|e| format!("Extraction jarvis_server.exe échouée: {e}"))?;
    }
    Ok(server_path)
}

/// Chemin du dossier models/ à côté de JARVIS.exe
fn models_dir() -> Option<std::path::PathBuf> {
    let exe = std::env::current_exe().ok()?;
    Some(exe.parent()?.join("models"))
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

    let server_exe = extract_server_exe()?;

    let mut cmd = Command::new(&server_exe);

    // Indique au serveur où trouver les modèles
    if let Some(models) = models_dir() {
        cmd.env("JARVIS_MODELS_DIR", models.to_string_lossy().as_ref());
    }

    // Répertoire de travail = dossier de JARVIS.exe
    if let Ok(exe) = std::env::current_exe() {
        if let Some(dir) = exe.parent() {
            cmd.current_dir(dir);
        }
    }

    #[cfg(windows)]
    cmd.creation_flags(0x08000000); // CREATE_NO_WINDOW

    let child = cmd
        .spawn()
        .map_err(|e| format!("Impossible de démarrer jarvis_server: {e}"))?;

    *guard = Some(child);
    Ok(())
}

/// Kill the managed server process if we own it.
pub fn kill_server(state: &SidecarState) {
    if let Ok(mut guard) = state.0.lock() {
        if let Some(mut child) = guard.take() {
            let _ = child.kill();
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
