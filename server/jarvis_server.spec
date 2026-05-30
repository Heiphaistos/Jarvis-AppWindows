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

# faster_whisper — assets
fw_path = venv_site / "faster_whisper"
if fw_path.exists():
    added_datas.append((str(fw_path / "assets"), "faster_whisper/assets"))

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
        "pyperclip",
        "PIL",
        "PIL.Image",
        "psutil",
        "ctypes",
        "ctypes.wintypes",
        "win32api",
        "win32con",
        "win32gui",
    ],
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
