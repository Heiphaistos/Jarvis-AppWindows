use cpal::traits::{DeviceTrait, HostTrait, StreamTrait};
use std::sync::Mutex;
use tauri::{AppHandle, Emitter, State};

// cpal::Stream n'est pas Send sur certaines plateformes — wrapper pour forcer
pub struct StreamWrapper(pub cpal::Stream);
// SAFETY: WASAPI (Windows) est thread-safe pour play/drop
unsafe impl Send for StreamWrapper {}

pub struct AudioStateInner(pub Mutex<Option<StreamWrapper>>);

#[tauri::command]
pub fn start_mic(app: AppHandle, state: State<'_, AudioStateInner>) -> Result<u32, String> {
    let host = cpal::default_host();
    let device = host
        .default_input_device()
        .ok_or_else(|| "Aucun périphérique d'entrée audio détecté".to_string())?;

    let supported = device
        .default_input_config()
        .map_err(|e| format!("Config audio : {e}"))?;

    let sample_rate = supported.sample_rate().0;
    let config = cpal::StreamConfig {
        channels: 1,
        sample_rate: supported.sample_rate(),
        buffer_size: cpal::BufferSize::Default,
    };

    let app2 = app.clone();
    let mut pending: Vec<f32> = Vec::with_capacity(8192);
    const CHUNK: usize = 4096;

    let stream = device
        .build_input_stream(
            &config,
            move |data: &[f32], _: &cpal::InputCallbackInfo| {
                pending.extend_from_slice(data);
                while pending.len() >= CHUNK {
                    let chunk: Vec<f32> = pending.drain(..CHUNK).collect();
                    let _ = app2.emit(
                        "jarvis_audio_chunk",
                        serde_json::json!({ "data": chunk, "sampleRate": sample_rate }),
                    );
                }
            },
            |err| eprintln!("[CPAL] Erreur capture : {err}"),
            None,
        )
        .map_err(|e| format!("Build stream : {e}"))?;

    stream.play().map_err(|e| format!("Play stream : {e}"))?;

    let mut guard = state.0.lock().unwrap();
    *guard = Some(StreamWrapper(stream));

    Ok(sample_rate)
}

#[tauri::command]
pub fn stop_mic(state: State<'_, AudioStateInner>) {
    let mut guard = state.0.lock().unwrap();
    *guard = None; // Drop → arrêt WASAPI
}
