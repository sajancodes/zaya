"""
Zaya — Environment setup and dependency installer.
Created and developed by Sajan Rai — https://github.com/sajancodes

Configures the runtime environment for Zaya desktop assistant, optical hand tracking,
and spatial intelligence. Installs OS-filtered Python dependencies, fetches Playwright
browser automation binaries, validates core assets, and provides opt-in setup for
modular local speech, isolated hand tracking, and web distribution services.
"""
from __future__ import annotations

import argparse
import os
import platform
import subprocess
import sys
import urllib.request
from pathlib import Path
from typing import List

OS = platform.system()  # "Windows" | "Darwin" | "Linux"
HERE = Path(__file__).resolve().parent

MIN_PY = (3, 11)  # Minimum Python version required for Zaya
MAX_PY = (3, 13)  # Highest tested version (Python 3.13 regression environment)

HAND_MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/hand_landmarker/"
    "hand_landmarker/float16/latest/hand_landmarker.task"
)


def _run(label: str, args: List[str], cwd: Path | None = None) -> bool:
    """Run a subprocess command with clear user-facing feedback."""
    print(f"\n▶ {label}")
    try:
        subprocess.run(args, check=True, cwd=str(cwd or HERE))
        return True
    except subprocess.CalledProcessError as e:
        print(f"⚠️  Command returned non-zero exit code {e.returncode}: {' '.join(args)}")
        return False
    except FileNotFoundError as e:
        print(f"⚠️  Executable not found ({e}): {args[0]}")
        return False


def _check_python() -> None:
    """Validate Python interpreter version and provide actionable error guidance."""
    v = sys.version_info[:2]
    if v > MAX_PY:
        print(
            f"\n⚠️  Python {v[0]}.{v[1]} is newer than the tested target "
            f"({MAX_PY[0]}.{MAX_PY[1]}). Continuing — if a dependency wheel is missing, "
            f"install Python {MAX_PY[0]}.{MAX_PY[1]} and run setup again."
        )
        return
    if v < MIN_PY:
        print(
            f"\n❌ Python {v[0]}.{v[1]} detected — Zaya requires at least "
            f"Python {MIN_PY[0]}.{MIN_PY[1]}."
        )
        print("   Please install a supported version and run setup:")
        print(f"     py -{MAX_PY[0]}.{MAX_PY[1]} setup.py        (Windows)")
        print(f"     python{MAX_PY[0]}.{MAX_PY[1]} setup.py      (macOS / Linux)")
        sys.exit(1)


def _ensure_directories() -> None:
    """Create essential local runtime directories if they do not yet exist."""
    dirs = [
        HERE / "logs" / "runtime",
        HERE / "memory",
        HERE / "config",
        HERE / "models",
    ]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)


def _check_assets() -> None:
    """Validate presence and integrity of bundled assets and configuration."""
    print("\n🔍 Validating core model and character assets…")

    # 1. 3D Face Avatar Model
    face = HERE / "core" / "face_model.obj"
    if not face.exists() or face.stat().st_size < 4096:
        print(
            "  ⚠️  core/face_model.obj is missing or truncated — avatar will fall "
            "back to glowing core."
        )
    else:
        print("  ✓ core/face_model.obj present.")

    # 2. Companion Taskbar Configuration
    zayabar = HERE / "zayabar.json"
    if not zayabar.exists():
        print("  ⚠️  zayabar.json configuration missing in root directory.")
    else:
        print("  ✓ zayabar.json character configuration verified.")

    # 3. MediaPipe Hand Model
    hand_model = HERE / "models" / "hand_landmarker.task"
    if hand_model.exists():
        size_mb = hand_model.stat().st_size / (1024 * 1024)
        print(f"  ✓ models/hand_landmarker.task present ({size_mb:.1f} MB).")
    else:
        print(
            "  ℹ️  models/hand_landmarker.task not yet downloaded (required for "
            "optical hand control; use --with-hands to install)."
        )


def _install_core_requirements() -> bool:
    """Install core Python dependencies from requirements.txt."""
    req_file = HERE / "requirements.txt"
    if not req_file.exists():
        print("❌ requirements.txt not found in project root.")
        return False

    return _run(
        "Installing core dependencies (OS-specific packages auto-filtered)…",
        [sys.executable, "-m", "pip", "install", "-r", "requirements.txt"],
    )


def _install_playwright() -> None:
    """Install Playwright browser binaries (Chromium + Firefox) for web automation."""
    try:
        _run(
            "Installing Playwright browser binaries (chromium + firefox)…",
            [sys.executable, "-m", "playwright", "install", "chromium", "firefox"],
        )
    except Exception as e:
        print(f"\n⚠️  Playwright browsers were not installed ({e}).")
        print("    Everything except browser automation works. Retry later with:")
        print(f"    {sys.executable} -m playwright install chromium firefox")


def _setup_local_speech() -> bool:
    """Install optional dependencies for modular on-device speech (Whisper + Piper)."""
    speech_req = HERE / "requirements-local-speech.txt"
    if not speech_req.exists():
        print("⚠️  requirements-local-speech.txt not found.")
        return False

    print("\n📦 Setting up Modular Local Speech Pipeline (faster-whisper + piper-tts)…")
    return _run(
        "Installing local speech packages…",
        [sys.executable, "-m", "pip", "install", "-r", "requirements-local-speech.txt"],
    )


def _setup_hand_tracking() -> bool:
    """Configure isolated environment and download MediaPipe hand landmark weights."""
    print("\n🖐️ Setting up Optical Hand Tracking & Air Keyboard Pipeline…")
    hands_venv = HERE / ".venv-hands"
    hands_python = (
        hands_venv / "Scripts" / "python.exe"
        if OS == "Windows"
        else hands_venv / "bin" / "python"
    )

    # 1. Create isolated virtual environment if missing
    if not hands_python.exists():
        print("  Creating isolated .venv-hands environment…")
        if not _run("Creating .venv-hands…", [sys.executable, "-m", "venv", ".venv-hands"]):
            return False

    # 2. Install requirements-hands.txt inside .venv-hands
    hands_req = HERE / "requirements-hands.txt"
    if hands_req.exists():
        print("  Installing MediaPipe and OpenCV in .venv-hands…")
        _run(
            "Installing hand dependencies…",
            [str(hands_python), "-m", "pip", "install", "-r", "requirements-hands.txt"],
        )

    # 3. Ensure official Google MediaPipe Hand Landmarker task file exists
    model_dir = HERE / "models"
    model_dir.mkdir(parents=True, exist_ok=True)
    model_path = model_dir / "hand_landmarker.task"

    if not model_path.exists() or model_path.stat().st_size < 100000:
        print(f"  Downloading official Hand Landmarker model to {model_path}…")
        try:
            urllib.request.urlretrieve(HAND_MODEL_URL, str(model_path))
            print(f"  ✓ Model downloaded successfully ({model_path.stat().st_size / (1024*1024):.1f} MB).")
        except Exception as e:
            print(f"  ⚠️  Could not download hand model ({e}). You can download manually from:")
            print(f"      {HAND_MODEL_URL}")
            return False
    else:
        print("  ✓ models/hand_landmarker.task already present.")

    return True


def _setup_web_distribution() -> bool:
    """Install optional FastAPI and web backend requirements for telemetry and site."""
    web_req = HERE / "web" / "requirements.txt"
    if not web_req.exists():
        print("⚠️  web/requirements.txt not found.")
        return False

    print("\n🌐 Setting up Web Distribution & Telemetry Server Dependencies…")
    return _run(
        "Installing web requirements…",
        [sys.executable, "-m", "pip", "install", "-r", str(web_req)],
    )


def _check_os_postinstall() -> None:
    """Run OS-specific verification checks and display platform notices."""
    if OS == "Windows":
        try:
            import win32com.client  # noqa: F401
            print("\n✓ Windows pywin32 COM integration registered.")
        except ImportError:
            postinstall = Path(sys.executable).parent / "Scripts" / "pywin32_postinstall.py"
            print(
                "\n⚠️  pywin32 did not register correctly — desktop shortcut "
                "creation will use a slower fallback. To fix it, run:\n"
                f'    "{sys.executable}" -m pip install --force-reinstall pywin32\n'
                f'    "{sys.executable}" "{postinstall}" -install'
            )

        # Check CoreAudio ducking availability
        try:
            import pycaw  # noqa: F401
            print("✓ Windows CoreAudio session ducking module (pycaw) available.")
        except ImportError:
            print("ℹ️  pycaw not detected; audio ducking will be disabled.")

    elif OS == "Linux":
        print(
            "\nℹ️  Linux note — voice-controlled system actions shell out to native tools:\n"
            "    • volume      → pulseaudio-utils   (pactl)\n"
            "    • brightness  → brightnessctl\n"
            "    • reminders   → systemd (systemd-run) or 'at'\n"
            "    • open URLs   → xdg-utils          (xdg-open)"
        )
    elif OS == "Darwin":
        print(
            "\nℹ️  macOS note — volume, brightness and reminders use built-in "
            "'osascript' / LaunchAgents.\n"
            "    For Safari browser automation: python -m playwright install webkit"
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Zaya Setup — Created and developed by Sajan Rai (sajancodes)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python setup.py                     Standard installation (core + Playwright browsers)
  python setup.py --with-local-speech Include offline speech (faster-whisper + Piper)
  python setup.py --with-hands        Include optical hand tracking & .venv-hands
  python setup.py --all               Full install (core, speech, hands, and web)
  python setup.py --check-only        Validate environment without installing packages
        """,
    )
    parser.add_argument(
        "--skip-browsers",
        action="store_true",
        help="Skip downloading Playwright browser binaries (saves ~300MB download).",
    )
    parser.add_argument(
        "--with-local-speech",
        action="store_true",
        help="Install optional local offline speech packages (faster-whisper, piper-tts).",
    )
    parser.add_argument(
        "--with-hands",
        action="store_true",
        help="Configure isolated .venv-hands environment and fetch MediaPipe hand model.",
    )
    parser.add_argument(
        "--with-web",
        action="store_true",
        help="Install optional web backend server dependencies (web/requirements.txt).",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Install core and all optional components (local speech, hands, web).",
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Check Python version, directories, and assets without installing.",
    )

    args = parser.parse_args()

    print(f"==================================================")
    print(f"  ZAYA SYSTEM SETUP — Created by Sajan Rai        ")
    print(f"  Detected OS: {OS or 'Unknown'} | Python: {sys.version.split()[0]}")
    print(f"==================================================")

    _check_python()
    _ensure_directories()
    _check_assets()

    if args.check_only:
        print("\n✅ Environment check complete.")
        return

    # 1. Core Python Dependencies
    _install_core_requirements()

    # 2. Playwright Browser Binaries
    if not args.skip_browsers:
        _install_playwright()
    else:
        print("\nℹ️  Skipping Playwright browser installation (--skip-browsers).")

    # 3. Optional Local Speech Engine
    if args.with_local_speech or args.all:
        _setup_local_speech()

    # 4. Optional Optical Hand Tracking & Air Keyboard
    if args.with_hands or args.all:
        _setup_hand_tracking()

    # 5. Optional Web Distribution & Telemetry
    if args.with_web or args.all:
        _setup_web_distribution()

    # 6. OS Platform Integration Checks
    _check_os_postinstall()

    # 7. Next Steps Guidance
    print("\n==================================================")
    print("✅ Zaya setup finished successfully!")
    print("==================================================")
    print("Next steps:")
    print("  1. Launch Zaya:")
    print(f"       {Path(sys.executable).name} main.py")
    print("  2. First-Run Setup:")
    print("       Enter your Google Gemini API key when prompted.")
    print("       Your key is encrypted locally using Windows DPAPI.")
    print("  3. Optional Controls:")
    print("       • Right-click Zaya on your taskbar for Settings & Controls.")
    print("       • Enable optical hands or 3D workspace in Settings > Hand controls.")
    print("       • Pair native Android companion from Settings > Remote Control.")
    print("\nCreated and developed by Sajan Rai — https://github.com/sajancodes")


if __name__ == "__main__":
    main()
