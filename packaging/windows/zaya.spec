# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for Zaya desktop application (onedir production build).
Created and developed by Sajan Rai for Zaya.
"""
import os
import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

SPEC_ROOT = Path(SPECPATH).resolve()
REPO_ROOT = SPEC_ROOT.parents[1] if (SPEC_ROOT.name == 'windows' and SPEC_ROOT.parent.name == 'packaging') else SPEC_ROOT

# Discover all action and plugin modules to prevent silent omissions
action_modules = []
actions_dir = REPO_ROOT / 'actions'
if actions_dir.is_dir():
    for f in actions_dir.glob('*.py'):
        if f.name != '__init__.py' and not f.name.startswith('.'):
            action_modules.append(f'actions.{f.stem}')

plugin_modules = []
plugins_dir = REPO_ROOT / 'plugins'
if plugins_dir.is_dir():
    for f in plugins_dir.glob('*.py'):
        if f.name != '__init__.py' and not f.name.startswith('.'):
            plugin_modules.append(f'plugins.{f.stem}')

hidden_imports = [
    'PyQt6',
    'PyQt6.QtCore',
    'PyQt6.QtGui',
    'PyQt6.QtWidgets',
    'PyQt6.QtNetwork',
    'numpy',
    'sounddevice',
    'webrtcvad',
    'google.genai',
    'google.genai.types',
    'fastapi',
    'uvicorn',
    'uvicorn.logging',
    'uvicorn.loops',
    'uvicorn.protocols',
    'uvicorn.lifespan',
    'cryptography',
    'requests',
    'bs4',
    'pyautogui',
    'pyperclip',
    'PIL',
    'PIL.Image',
    'cv2',
    'mss',
    'psutil',
    'send2trash',
    'reportlab',
    'qrcode',
    'comtypes',
    'win10toast',
    'wmi',
    'pywinauto',
    'core.version',
    'core.runtime_paths',
    'core.update',
    'core.update.desktop_updater',
    'core.update.update_ui',
    'services.spatial_server',
] + action_modules + plugin_modules

datas = [
    (str(REPO_ROOT / 'actions'), 'actions'),
    (str(REPO_ROOT / 'plugins'), 'plugins'),
    # Never bundle the owner's provider keys, pairing credentials or settings.
    (str(REPO_ROOT / 'config' / 'jarvis.ico'), 'config'),
    (str(REPO_ROOT / 'core' / 'prompt.txt'), 'core'),
]

renderer_dist = REPO_ROOT / 'spatial_renderer' / 'dist'
if renderer_dist.is_dir():
    datas.append((str(renderer_dist), 'spatial_renderer/dist'))

assets_dir = REPO_ROOT / 'assets'
if assets_dir.is_dir():
    datas.append((str(assets_dir), 'assets'))

version_json = REPO_ROOT / 'version.json'
if version_json.is_file():
    datas.append((str(version_json), '.'))

icon_path = str(REPO_ROOT / 'config' / 'jarvis.ico')
if not os.path.isfile(icon_path):
    icon_path = None

a = Analysis(
    [str(REPO_ROOT / 'main.py')],
    pathex=[str(REPO_ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'scipy', 'pandas', 'IPython', 'pytest', 'unittest'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Zaya',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon_path,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='Zaya',
)
