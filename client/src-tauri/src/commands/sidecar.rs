use std::hash::BuildHasher;
use std::io::{Read, Write};
use std::net::TcpStream;
use std::process::{Child, Command};
use std::sync::Mutex;
use std::time::{Duration, Instant, SystemTime};
use tauri::State;

#[cfg(windows)]
use std::os::windows::process::CommandExt;

const ADDR: &str = "127.0.0.1:8765";

/// Serveur lancé par JARVIS + jeton qui l'autorise à demander son arrêt propre.
pub struct SidecarState(pub Mutex<Option<(Child, String)>>);

/// True if something is already listening on 127.0.0.1:8765
fn is_server_running() -> bool {
    TcpStream::connect_timeout(&ADDR.parse().unwrap(), Duration::from_millis(300)).is_ok()
}

fn wait_until(timeout: Duration, mut done: impl FnMut() -> bool) -> bool {
    let start = Instant::now();
    while start.elapsed() < timeout {
        if done() {
            return true;
        }
        std::thread::sleep(Duration::from_millis(100));
    }
    done()
}

/// Serveur Python compilé (PyInstaller), livré à côté de JARVIS.exe : ressource
/// du bundle (installeur, remplacée à chaque mise à jour) ou fichier du zip portable.
fn server_exe() -> Result<std::path::PathBuf, String> {
    let exe = std::env::current_exe().map_err(|e| e.to_string())?;
    let dir = exe.parent().ok_or("Impossible de trouver le dossier de JARVIS.exe")?;
    let server_path = dir.join("jarvis_server.exe");
    if !server_path.exists() {
        return Err(format!("{} introuvable", server_path.display()));
    }
    Ok(server_path)
}

/// Chemin du dossier models/ à côté de JARVIS.exe
fn models_dir() -> Option<std::path::PathBuf> {
    let exe = std::env::current_exe().ok()?;
    Some(exe.parent()?.join("models"))
}

/// Jeton aléatoire (RandomState est semé par l'OS) : seul JARVIS peut arrêter son serveur.
fn new_token() -> String {
    let seed = SystemTime::now().duration_since(SystemTime::UNIX_EPOCH).map(|d| d.as_nanos()).unwrap_or(0);
    let r = || std::collections::hash_map::RandomState::new().hash_one((seed, std::process::id()));
    format!("{:016x}{:016x}", r(), r())
}

/// Job Object Windows « tuer à la fermeture » : le serveur PyInstaller (chargeur + processus
/// Python enfant) y est rattaché. Quand JARVIS.exe se termine, même sur un plantage,
/// Windows ferme le dernier handle du job et tue tout l'arbre : plus de serveur orphelin.
#[cfg(windows)]
mod job {
    use std::sync::OnceLock;
    use windows_sys::Win32::System::JobObjects::*;

    static JOB: OnceLock<usize> = OnceLock::new();

    fn handle() -> usize {
        *JOB.get_or_init(|| unsafe {
            let h = CreateJobObjectW(std::ptr::null(), std::ptr::null());
            if h.is_null() {
                return 0;
            }
            let mut info: JOBOBJECT_EXTENDED_LIMIT_INFORMATION = std::mem::zeroed();
            info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;
            SetInformationJobObject(
                h,
                JobObjectExtendedLimitInformation,
                &info as *const _ as *const core::ffi::c_void,
                std::mem::size_of::<JOBOBJECT_EXTENDED_LIMIT_INFORMATION>() as u32,
            );
            h as usize
        })
    }

    pub fn assign(child: &std::process::Child) {
        use std::os::windows::io::AsRawHandle;
        let h = handle();
        if h == 0 || unsafe { AssignProcessToJobObject(h as _, child.as_raw_handle() as _) } == 0 {
            eprintln!("[JARVIS] Job Object indisponible : arrêt du serveur par kill seulement");
        }
    }

    /// Tue tout ce qui reste dans le job (chargeur PyInstaller et son processus Python).
    pub fn terminate() {
        if let Some(&h) = JOB.get() {
            if h != 0 {
                unsafe { TerminateJobObject(h as _, 0) };
            }
        }
    }
}

/// Une seule instance de JARVIS : toute instance de jarvis_server.exe trouvée au
/// démarrage est donc l'orphelin d'une session précédente (ancienne version, plantage).
fn kill_orphan_servers() {
    let mut cmd = Command::new("taskkill");
    cmd.args(["/F", "/T", "/IM", "jarvis_server.exe"]);
    #[cfg(windows)]
    cmd.creation_flags(0x08000000); // CREATE_NO_WINDOW
    let _ = cmd.output();
}

/// Start the Python server silently. Idempotent: does nothing if already running.
pub fn launch_server(state: &SidecarState) -> Result<(), String> {
    let mut guard = state.0.lock().map_err(|e| e.to_string())?;
    if guard.is_some() {
        return Ok(());
    }

    if is_server_running() {
        kill_orphan_servers();
        if !wait_until(Duration::from_secs(6), || !is_server_running()) {
            // Port tenu par autre chose qu'un jarvis_server.exe (serveur de dev python main.py) : on le réutilise.
            return Ok(());
        }
    }

    let server_exe = server_exe()?;
    let token = new_token();
    let mut cmd = Command::new(&server_exe);
    cmd.env("JARVIS_SHUTDOWN_TOKEN", &token);

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
    // Le chargeur PyInstaller décompresse ~1,4 Go avant de créer son processus Python :
    // rattaché ici, cet enfant hérite du job.
    #[cfg(windows)]
    job::assign(&child);

    *guard = Some((child, token));
    Ok(())
}

/// POST /api/shutdown avec le jeton : le serveur se ferme proprement (LLM déchargé, bases fermées).
fn request_shutdown(token: &str) -> bool {
    let Ok(mut s) = TcpStream::connect_timeout(&ADDR.parse().unwrap(), Duration::from_millis(500)) else {
        return false;
    };
    let _ = s.set_read_timeout(Some(Duration::from_secs(2)));
    let _ = s.set_write_timeout(Some(Duration::from_secs(1)));
    let req = format!(
        "POST /api/shutdown HTTP/1.1\r\nHost: {ADDR}\r\nX-Jarvis-Token: {token}\r\nContent-Length: 0\r\nConnection: close\r\n\r\n"
    );
    let mut head = [0u8; 12];
    s.write_all(req.as_bytes()).is_ok()
        && s.read(&mut head).map(|n| head[..n].starts_with(b"HTTP/1.1 200")).unwrap_or(false)
}

/// Arrête le serveur lancé par JARVIS : arrêt propre via l'API, puis tout l'arbre est tué en secours.
pub fn kill_server(state: &SidecarState) {
    let Ok(mut guard) = state.0.lock() else { return };
    let Some((mut child, token)) = guard.take() else { return };
    if request_shutdown(&token) {
        wait_until(Duration::from_secs(5), || matches!(child.try_wait(), Ok(Some(_))));
    }
    #[cfg(windows)]
    job::terminate();
    let _ = child.kill();
    let _ = child.wait();
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
