mod commands;
use commands::sidecar::{start_server, stop_server, SidecarState};
use std::sync::Mutex;
use tauri::Manager;

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .manage(SidecarState(Mutex::new(None)))
        .setup(|app| {
            // Auto-start the Python server silently on app launch
            let state = app.state::<SidecarState>();
            if let Err(e) = commands::sidecar::launch_server(&state) {
                eprintln!("[JARVIS] Serveur non démarré automatiquement: {e}");
            }
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![start_server, stop_server])
        .on_window_event(|window, event| {
            // Kill the Python server when the window is closed
            if let tauri::WindowEvent::Destroyed = event {
                let handle = window.app_handle();
                let state = handle.state::<SidecarState>();
                commands::sidecar::kill_server(&state);
            }
        })
        .run(tauri::generate_context!())
        .expect("error while running JARVIS");
}
