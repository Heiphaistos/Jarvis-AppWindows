mod commands;
use commands::audio::AudioStateInner;
use commands::sidecar::{start_server, stop_server, SidecarState};
use std::sync::Mutex;
use tauri::Manager;

/// Une seule instance de JARVIS (un seul serveur sur le port 8765) : la seconde
/// remet la fenêtre existante au premier plan et s'arrête.
#[cfg(windows)]
fn already_running() -> bool {
    use windows_sys::Win32::Foundation::{GetLastError, ERROR_ALREADY_EXISTS};
    use windows_sys::Win32::System::Threading::CreateMutexW;
    use windows_sys::Win32::UI::WindowsAndMessaging::{FindWindowW, SetForegroundWindow, ShowWindow, SW_RESTORE};
    let wide = |s: &str| s.encode_utf16().chain(Some(0)).collect::<Vec<u16>>();
    let name = wide("Local\\JARVIS-assistant-instance");
    // Handle volontairement conservé jusqu'à la fin du processus.
    unsafe {
        CreateMutexW(std::ptr::null(), 0, name.as_ptr());
        if GetLastError() != ERROR_ALREADY_EXISTS {
            return false;
        }
        let hwnd = FindWindowW(std::ptr::null(), wide("J.A.R.V.I.S.").as_ptr());
        if !hwnd.is_null() {
            ShowWindow(hwnd, SW_RESTORE);
            SetForegroundWindow(hwnd);
        }
    }
    true
}

fn shutdown(handle: &tauri::AppHandle) {
    commands::sidecar::kill_server(&handle.state::<SidecarState>());
    // Arrêter capture audio si active
    if let Ok(mut guard) = handle.state::<AudioStateInner>().0.lock() {
        *guard = None;
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    #[cfg(windows)]
    if already_running() {
        return;
    }
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
                shutdown(window.app_handle());
            }
        })
        .build(tauri::generate_context!())
        .expect("error while building JARVIS")
        // Toute sortie de l'appli (croix, Alt+F4, fin de session) passe ici ; un plantage est couvert par le Job Object.
        .run(|handle, event| {
            if let tauri::RunEvent::Exit = event {
                shutdown(handle);
            }
        });
}
