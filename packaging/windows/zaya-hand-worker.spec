# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for Zaya isolated hand worker runtime.
Created and developed by Sajan Rai for Zaya.

Produces ZayaHandWorker.exe wrapping core.gesture.worker for bounded stdin/stdout hand inference.
"""
import os
import sys
import runpy
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_submodules, collect_dynamic_libs

block_cipher = None

SPEC_ROOT = Path(SPECPATH).resolve()
REPO_ROOT = SPEC_ROOT.parents[1] if SPEC_ROOT.parent.name == 'packaging' else SPEC_ROOT

# Entry point script
entry_script = REPO_ROOT / 'packaging' / 'hand_worker_entry.py'

hidden_imports = [
    'mediapipe',
    'mediapipe.tasks',
    'mediapipe.tasks.python',
    'mediapipe.tasks.python.vision',
    'cv2',
    'numpy',
    'core.gesture.hand_tracker',
    'core.gesture.hand_model',
    'core.gesture.smoothing',
]

datas = []
try:
    datas += collect_data_files('mediapipe')
except Exception:
    pass

binaries = []
try:
    binaries += collect_dynamic_libs('mediapipe')
except Exception:
    pass

a = Analysis(
    [str(entry_script)],
    pathex=[str(REPO_ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={'matplotlib': {'backends': ['Agg']}},
    runtime_hooks=[],
    excludes=['tkinter', 'scipy', 'PyQt6', 'fastapi', 'uvicorn'],
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
    name='ZayaHandWorker',
    version=runpy.run_path(str(REPO_ROOT / 'tools' / 'windows_version_info.py'))['build_version_info'](REPO_ROOT, 'ZayaHandWorker.exe') if sys.platform == 'win32' else None,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
