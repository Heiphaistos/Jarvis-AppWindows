use std::process::{Child, Command};
use std::sync::Mutex;
use tauri::State;

pub struct SidecarState(pub Mutex<Option<Child>>);

#[tauri::command]
pub fn start_server(state: State<'_, SidecarState>) -> Result<(), String> {
    let mut guard = state.0.lock().map_err(|e| e.to_string())?;
    if guard.is_some() {
        return Ok(());
    }
    let child = Command::new("jarvis-server")
        .spawn()
        .map_err(|e| format!("Impossible de démarrer le serveur: {}", e))?;
    *guard = Some(child);
    Ok(())
}

#[tauri::command]
pub fn stop_server(state: State<'_, SidecarState>) -> Result<(), String> {
    let mut guard = state.0.lock().map_err(|e| e.to_string())?;
    if let Some(mut child) = guard.take() {
        child.kill().map_err(|e| e.to_string())?;
    }
    Ok(())
}
