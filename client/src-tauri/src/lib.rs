mod commands;
use commands::audio::AudioStateInner;
use commands::sidecar::{start_server, stop_server, SidecarState};
use std::sync::Mutex;
use tauri::Manager;

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .manage(SidecarState(Mutex::new(None)))
        .manage(AudioStateInner(Mutex::new(None)))
        .setup(|app| {
            let state = app.state::<SidecarState>();
            if let Err(e) = commands::sidecar::launch_server(&state) {
                eprintln!("[JARVIS] Serveur non démarré automatiquement: {e}");
            }
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            start_server,
            stop_server,
            commands::audio::start_mic,
            commands::audio::stop_mic,
        ])
        .on_window_event(|window, event| {
            if let tauri::WindowEvent::Destroyed = event {
                let handle = window.app_handle();
                let state = handle.state::<SidecarState>();
                commands::sidecar::kill_server(&state);
                // Arrêter capture audio si active
                let audio = handle.state::<AudioStateInner>();
                let mut guard = audio.0.lock().unwrap();
                *guard = None;
            }
        })
        .run(tauri::generate_context!())
        .expect("error while running JARVIS");
}
