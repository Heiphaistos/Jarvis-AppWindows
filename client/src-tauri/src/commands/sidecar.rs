use std::net::TcpStream;
use std::process::{Child, Command};
use std::sync::Mutex;
use tauri::State;

#[cfg(windows)]
use std::os::windows::process::CommandExt;

pub struct SidecarState(pub Mutex<Option<Child>>);

/// True if something is already listening on 127.0.0.1:8765
fn is_server_running() -> bool {
    TcpStream::connect("127.0.0.1:8765").is_ok()
}

/// Walk up from the exe to find the project's `server/` directory.
/// Works for both dev (target/debug) and release (target/release) builds.
fn find_server_dir() -> Option<std::path::PathBuf> {
    let exe = std::env::current_exe().ok()?;
    // target/(debug|release)/JARVIS.exe → up 4 levels → project root → server/
    let from_exe = exe
        .parent()? // target/debug or target/release
        .parent()? // target
        .parent()? // src-tauri
        .parent()? // client
        .parent()? // project root
        .join("server");
    if from_exe.join("main.py").exists() {
        return Some(from_exe);
    }
    // Installed (NSIS currentUser): server/ next to exe
    let next_to_exe = exe.parent()?.join("server");
    if next_to_exe.join("main.py").exists() {
        return Some(next_to_exe);
    }
    None
}

/// Start the Python server silently. Idempotent: does nothing if already running.
pub fn launch_server(state: &SidecarState) -> Result<(), String> {
    // Don't spawn a second server if port is already open
    if is_server_running() {
        return Ok(());
    }

    let mut guard = state.0.lock().map_err(|e| e.to_string())?;
    if guard.is_some() {
        return Ok(());
    }

    let dir = find_server_dir()
        .ok_or_else(|| "Dossier server/ introuvable — lancez depuis le répertoire du projet".to_string())?;

    let python = dir.join(".venv").join("Scripts").join("python.exe");
    if !python.exists() {
        return Err(format!(
            "Python venv introuvable: {} — exécutez: python -m venv server\\.venv",
            python.display()
        ));
    }

    let mut cmd = Command::new(&python);
    cmd.arg("main.py").current_dir(&dir);

    #[cfg(windows)]
    cmd.creation_flags(0x08000000); // CREATE_NO_WINDOW — silencieux, pas de terminal

    let child = cmd
        .spawn()
        .map_err(|e| format!("Impossible de démarrer le serveur Python: {e}"))?;

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
