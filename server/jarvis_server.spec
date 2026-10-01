# -*- mode: python ; coding: utf-8 -*-
import site, sys
from pathlib import Path

block_cipher = None

# Collecter les données nécessaires à faster-whisper et llama-cpp
added_datas = []

# Trouver les DLLs CUDA/cuBLAS pour llama-cpp-python
import glob, os
venv_site = Path(sys.executable).parent.parent / "Lib" / "site-packages"

# llama_cpp — inclure les DLLs natives (racine + lib/)
llama_cpp_path = venv_site / "llama_cpp"
if llama_cpp_path.exists():
    for dll in llama_cpp_path.glob("*.dll"):
        added_datas.append((str(dll), "llama_cpp"))
    llama_lib = llama_cpp_path / "lib"
    if llama_lib.exists():
        for f in llama_lib.iterdir():
            added_datas.append((str(f), "llama_cpp/lib"))

# DLLs CUDA (pip nvidia-*) : ggml-cuda.dll en dépend. En frozen,
# _add_cuda_dll_dirs ne les trouve pas (packages data-only) → les placer
# DANS llama_cpp/lib, à côté de ggml-cuda.dll, sinon LoadLibrary ouvre une
# boîte d'erreur invisible et le chargement du modèle reste bloqué.
for _nv_sub in ("cublas", "cuda_runtime"):
    _nv_bin = venv_site / "nvidia" / _nv_sub / "bin"
    if _nv_bin.exists():
        for dll in _nv_bin.glob("*.dll"):
            added_datas.append((str(dll), "llama_cpp/lib"))

# faster_whisper — assets
fw_path = venv_site / "faster_whisper"
if fw_path.exists():
    added_datas.append((str(fw_path / "assets"), "faster_whisper/assets"))

# openwakeword — modèles ONNX embarqués (hey_jarvis + mel/embedding)
oww_models = venv_site / "openwakeword" / "resources" / "models"
if oww_models.exists():
    for f in oww_models.glob("*.onnx"):
        added_datas.append((str(f), "openwakeword/resources/models"))

# Skills Fable — chargés depuis <exe>/skills en mode frozen, mais on les
# embarque aussi en interne au cas où
skills_dir = Path("skills")
if skills_dir.exists():
    for f in skills_dir.glob("*.md"):
        added_datas.append((str(f), "skills"))

# pkgutil.iter_modules (auto-découverte des outils, fournisseurs) ne voit rien
# en mode frozen : embarquer tous les sous-modules des paquets du serveur.
from PyInstaller.utils.hooks import collect_submodules
local_modules = collect_submodules("tools") + collect_submodules("core") + collect_submodules("utils")

a = Analysis(
    ["main.py"],
    pathex=[str(Path(".").resolve())],
    binaries=[],
    datas=added_datas,
    hiddenimports=[
        "uvicorn.logging",
        "uvicorn.loops",
        "uvicorn.loops.auto",
        "uvicorn.loops.asyncio",
        "uvicorn.loops.uvloop",
        "uvicorn.protocols",
        "uvicorn.protocols.http",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.http.h11_impl",
        "uvicorn.protocols.http.httptools_impl",
        "uvicorn.protocols.websockets",
        "uvicorn.protocols.websockets.auto",
        "uvicorn.protocols.websockets.websockets_impl",
        "uvicorn.protocols.websockets.wsproto_impl",
        "uvicorn.lifespan",
        "uvicorn.lifespan.off",
        "uvicorn.lifespan.on",
        "fastapi",
        "starlette",
        "websockets",
        "llama_cpp",
        "faster_whisper",
        "scipy.signal",
        "numpy",
        "pydantic",
        "pydantic_settings",
        "aiohttp",
        "aiofiles",
        "httpx",
        "edge_tts",
        "openwakeword",
        "openwakeword.model",
        "openwakeword.utils",
        "onnxruntime",
        "pyperclip",
        "PIL",
        "PIL.Image",
        "psutil",
        "ctypes",
        "ctypes.wintypes",
        "win32api",
        "win32con",
        "win32gui",
    ] + local_modules,
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "IPython", "jupyter"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="jarvis_server",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
)
