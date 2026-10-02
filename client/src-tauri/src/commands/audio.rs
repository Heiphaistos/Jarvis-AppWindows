use cpal::traits::{DeviceTrait, HostTrait, StreamTrait};
use cpal::{FromSample, SampleFormat, SizedSample};
use serde::Serialize;
use std::sync::Mutex;
use tauri::{AppHandle, Emitter, State};

// cpal::Stream n'est pas Send sur certaines plateformes — wrapper pour forcer
pub struct StreamWrapper(pub cpal::Stream);
// SAFETY: WASAPI (Windows) et ALSA/PulseAudio (Linux) tolèrent l'arrêt du flux
// depuis un autre thread ; le flux n'est jamais utilisé en parallèle (Mutex).
unsafe impl Send for StreamWrapper {}

pub struct AudioStateInner(pub Mutex<Option<StreamWrapper>>);

/// ~85 ms à 48 kHz : assez court pour une détection de fin de phrase réactive.
const CHUNK: usize = 4096;

#[derive(Serialize)]
pub struct MicInfo {
    name: String,
    is_default: bool,
}

/// Micros disponibles, pour le choix dans Paramètres › Voix.
#[tauri::command]
pub fn list_mics() -> Result<Vec<MicInfo>, String> {
    let host = cpal::default_host();
    let default_name = host.default_input_device().and_then(|d| d.name().ok());
    let devices = host
        .input_devices()
        .map_err(|e| format!("Liste des micros : {e}"))?;
    let mut out: Vec<MicInfo> = Vec::new();
    for device in devices {
        let Ok(name) = device.name() else { continue };
        if out.iter().any(|m| m.name == name) {
            continue;
        }
        let is_default = default_name.as_deref() == Some(name.as_str());
        out.push(MicInfo { name, is_default });
    }
    Ok(out)
}

fn find_device(host: &cpal::Host, wanted: Option<&str>) -> Result<cpal::Device, String> {
    if let Some(name) = wanted.filter(|n| !n.is_empty()) {
        if let Ok(mut devices) = host.input_devices() {
            if let Some(device) = devices.find(|d| d.name().map(|n| n == name).unwrap_or(false)) {
                return Ok(device);
            }
        }
        eprintln!("[CPAL] Micro « {name} » introuvable — micro par défaut utilisé");
    }
    host.default_input_device()
        .ok_or_else(|| "Aucun périphérique d'entrée audio détecté".to_string())
}

/// Construit le flux pour n'importe quel format d'échantillon : beaucoup de
/// micros (surtout sous Linux) fournissent de l'entier 16 bits, pas du float32.
fn build_stream<T>(
    device: &cpal::Device,
    config: &cpal::StreamConfig,
    app: AppHandle,
) -> Result<cpal::Stream, cpal::BuildStreamError>
where
    T: SizedSample,
    f32: FromSample<T>,
{
    let channels = config.channels.max(1) as usize;
    let sample_rate = config.sample_rate.0;
    let err_app = app.clone();
    let mut pending: Vec<f32> = Vec::with_capacity(CHUNK * 2);
    device.build_input_stream(
        config,
        move |data: &[T], _: &cpal::InputCallbackInfo| {
            // Multicanal → mono (moyenne des canaux)
            for frame in data.chunks(channels) {
                let sum: f32 = frame.iter().map(|s| f32::from_sample_(*s)).sum();
                pending.push(sum / frame.len() as f32);
            }
            while pending.len() >= CHUNK {
                let chunk: Vec<f32> = pending.drain(..CHUNK).collect();
                let _ = app.emit(
                    "jarvis_audio_chunk",
                    serde_json::json!({ "data": chunk, "sampleRate": sample_rate }),
                );
            }
        },
        move |err| {
            eprintln!("[CPAL] Erreur capture : {err}");
            let _ = err_app.emit("jarvis_audio_error", err.to_string());
        },
        None,
    )
}

#[tauri::command]
pub fn start_mic(
    app: AppHandle,
    state: State<'_, AudioStateInner>,
    device: Option<String>,
) -> Result<u32, String> {
    let host = cpal::default_host();
    let device = find_device(&host, device.as_deref())?;
    let supported = device
        .default_input_config()
        .map_err(|e| format!("Config audio : {e}"))?;

    let sample_format = supported.sample_format();
    let config: cpal::StreamConfig = supported.into();
    let sample_rate = config.sample_rate.0;

    let stream = match sample_format {
        SampleFormat::F32 => build_stream::<f32>(&device, &config, app),
        SampleFormat::I16 => build_stream::<i16>(&device, &config, app),
        SampleFormat::U16 => build_stream::<u16>(&device, &config, app),
        SampleFormat::I32 => build_stream::<i32>(&device, &config, app),
        SampleFormat::U32 => build_stream::<u32>(&device, &config, app),
        SampleFormat::I8 => build_stream::<i8>(&device, &config, app),
        SampleFormat::U8 => build_stream::<u8>(&device, &config, app),
        SampleFormat::F64 => build_stream::<f64>(&device, &config, app),
        other => return Err(format!("Format audio non pris en charge : {other}")),
    }
    .map_err(|e| format!("Ouverture du micro : {e}"))?;

    stream.play().map_err(|e| format!("Démarrage du micro : {e}"))?;

    // Remplace un éventuel flux précédent (son Drop l'arrête).
    let mut guard = state.0.lock().map_err(|_| "État audio verrouillé".to_string())?;
    *guard = Some(StreamWrapper(stream));

    Ok(sample_rate)
}

#[tauri::command]
pub fn stop_mic(state: State<'_, AudioStateInner>) {
    if let Ok(mut guard) = state.0.lock() {
        *guard = None; // Drop → arrêt du flux
    }
}
