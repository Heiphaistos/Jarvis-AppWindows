use std::hash::BuildHasher;
use std::io::{Read, Write};
use std::net::TcpStream;
use std::path::{Path, PathBuf};
use std::process::{Child, Command};
use std::sync::Mutex;
use std::time::{Duration, Instant, SystemTime};
use tauri::State;

#[cfg(windows)]
use std::os::windows::process::CommandExt;

const ADDR: &str = "127.0.0.1:8765";

/// Serveur lancé par JARVIS (+ jeton qui l'autorise à demander son arrêt propre)
/// et dossier des ressources du bundle.
pub struct SidecarState(pub Mutex<Option<(Child, String)>>, pub Mutex<Option<PathBuf>>);

#[cfg(windows)]
const SERVER_BIN: &str = "jarvis_server.exe";
#[cfg(not(windows))]
const SERVER_BIN: &str = "jarvis_server";

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
#[cfg(windows)]
fn kill_orphan_servers() {
    let mut cmd = Command::new("taskkill");
    cmd.args(["/F", "/T", "/IM", SERVER_BIN]);
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
        #[cfg(windows)]
        kill_orphan_servers();
        if !wait_until(Duration::from_secs(6), || !is_server_running()) {
            // Port tenu par autre chose qu'un jarvis_server.exe (serveur de dev python main.py) : on le réutilise.
            return Ok(());
        }
    }

    let resource_dir = state.1.lock().map_err(|e| e.to_string())?.clone();
    let server_exe = server_exe(resource_dir.as_deref())?;

    let token = new_token();
    let mut cmd = Command::new(&server_exe);
    cmd.env("JARVIS_SHUTDOWN_TOKEN", &token);

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
