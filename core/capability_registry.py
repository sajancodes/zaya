"""Runtime Self-Knowledge and Centralized Capability Registry for Zaya.
Created and developed by Sajan Rai for Zaya.

Provides an authoritative, dynamically probed inventory of what Zaya genuinely can
and cannot execute at runtime across OS features, hardware devices, active AI models,
tool readiness, missing dependencies, and security boundaries.
"""
from __future__ import annotations

import logging
import os
import platform
import shutil
import sys
import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class HardwareInventory:
    displays: int = 1
    has_microphone: bool = False
    has_speaker: bool = False
    has_camera: bool = False
    microphone_names: List[str] = field(default_factory=list)
    speaker_names: List[str] = field(default_factory=list)
    camera_count: int = 0


@dataclass
class DependencyStatus:
    name: str
    available: bool
    version: Optional[str] = None
    purpose: str = ""
    install_hint: str = ""


@dataclass
class CapabilitySnapshot:
    """Complete, factual snapshot of Zaya's current operational abilities."""
    timestamp: float = field(default_factory=time.time)
    os_name: str = ""
    os_version: str = ""
    platform_system: str = ""
    is_admin: bool = False
    hardware: Dict[str, Any] = field(default_factory=dict)
    dependencies: Dict[str, bool] = field(default_factory=dict)
    missing_dependencies: List[str] = field(default_factory=list)
    active_tools_count: int = 0
    active_tool_names: List[str] = field(default_factory=list)
    active_providers: List[str] = field(default_factory=list)
    local_ollama_available: bool = False
    trust_level: str = "unknown"
    readiness_summary: str = ""


class CapabilityRegistry:
    """Centralized runtime registry auditing capabilities, hardware, and libraries."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._cached_snapshot: Optional[CapabilitySnapshot] = None
        self._cache_timestamp: float = 0.0
        self._cache_ttl_sec: float = 30.0

    # ── Discovery Probes ────────────────────────────────────────────────────

    def probe_os_environment(self) -> dict:
        """Inspect the host operating system and privilege tier."""
        is_admin = False
        if os.name == "nt":
            try:
                import ctypes
                is_admin = bool(ctypes.windll.shell32.IsUserAnAdmin())
            except Exception:
                pass
        else:
            is_admin = (os.geteuid() == 0) if hasattr(os, "geteuid") else False

        return {
            "os_name": os.name,
            "platform_system": platform.system(),
            "os_version": platform.version(),
            "platform_release": platform.release(),
            "architecture": platform.machine(),
            "python_version": sys.version.split()[0],
            "is_admin": is_admin,
            "has_powershell": bool(shutil.which("powershell")),
            "has_bash": bool(shutil.which("bash")),
        }

    def probe_hardware(self) -> HardwareInventory:
        """Safely probe audio, display, and camera devices without locking them."""
        inv = HardwareInventory()

        # 1. Displays via mss if available
        try:
            import mss
            mss_cls = getattr(mss, 'MSS', getattr(mss, 'mss', None))
            with mss_cls() as sct:
                inv.displays = max(1, len(sct.monitors) - 1)
        except Exception:
            inv.displays = 1

        # 2. Audio devices via sounddevice if available
        try:
            import sounddevice as sd
            devices = sd.query_devices()
            mics = [d["name"] for d in devices if d.get("max_input_channels", 0) > 0]
            speakers = [d["name"] for d in devices if d.get("max_output_channels", 0) > 0]
            inv.has_microphone = len(mics) > 0
            inv.has_speaker = len(speakers) > 0
            inv.microphone_names = mics[:4]
            inv.speaker_names = speakers[:4]
        except Exception:
            # Fallback assumption for standard desktop
            inv.has_microphone = True
            inv.has_speaker = True

        # 3. Camera probe via opencv if available
        try:
            import cv2
            cap = cv2.VideoCapture(0)
            if cap.isOpened():
                inv.has_camera = True
                inv.camera_count = 1
                cap.release()
        except Exception:
            inv.has_camera = False

        return inv

    def probe_dependencies(self) -> List[DependencyStatus]:
        """Verify presence of key optional modules and runtime dependencies."""
        probes = [
            ("mss", "Screen capture without external binaries", "pip install mss"),
            ("sounddevice", "Real-time full-duplex microphone and speaker I/O", "pip install sounddevice"),
            ("numpy", "Numerical audio arrays and viseme processing", "pip install numpy"),
            ("cv2", "Computer vision, webcam processing, and hand gestures", "pip install opencv-python"),
            ("pyautogui", "Simulated mouse and keyboard automation", "pip install pyautogui"),
            ("pyperclip", "System clipboard text extraction and setting", "pip install pyperclip"),
            ("playwright", "Automated browser session control", "pip install playwright"),
            ("fastapi", "Local companion server and dashboard endpoints", "pip install fastapi"),
        ]

        results = []
        for mod_name, purpose, hint in probes:
            try:
                mod = __import__(mod_name)
                ver = getattr(mod, "__version__", "available")
                results.append(DependencyStatus(name=mod_name, available=True, version=ver, purpose=purpose, install_hint=hint))
            except ImportError:
                results.append(DependencyStatus(name=mod_name, available=False, version=None, purpose=purpose, install_hint=hint))
        return results

    def probe_ai_providers(self) -> Tuple[List[str], bool]:
        """Inspect available AI keys and local inference servers."""
        active = []
        if os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"):
            active.append("gemini")
        if os.environ.get("OPENAI_API_KEY"):
            active.append("openai")
        if os.environ.get("GROQ_API_KEY"):
            active.append("groq")
        if os.environ.get("ANTHROPIC_API_KEY"):
            active.append("anthropic")

        # Probe local Ollama on port 11434 (timeout 0.3s)
        ollama_active = False
        try:
            import urllib.request
            req = urllib.request.Request("http://127.0.0.1:11434/api/tags", headers={"User-Agent": "Zaya"})
            with urllib.request.urlopen(req, timeout=0.3) as response:
                if response.status == 200:
                    ollama_active = True
                    active.append("ollama")
        except Exception:
            pass

        return active, ollama_active

    def probe_active_tools(self) -> List[str]:
        """List all discovered tool names in Zaya."""
        try:
            from core.action_loader import get_loaded_tools
            tools = get_loaded_tools()
            if isinstance(tools, dict):
                return sorted(tools.keys())
            elif isinstance(tools, list):
                return sorted([t.get("name", "") for t in tools if isinstance(t, dict)])
        except Exception:
            pass
        return []

    # ── Public Evaluation & Capability Snapshot ─────────────────────────────

    def snapshot(self, force_refresh: bool = False) -> CapabilitySnapshot:
        """Generate a complete, cached capability snapshot."""
        with self._lock:
            now = time.time()
            if not force_refresh and self._cached_snapshot and (now - self._cache_timestamp < self._cache_ttl_sec):
                return self._cached_snapshot

            os_info = self.probe_os_environment()
            hw = self.probe_hardware()
            deps = self.probe_dependencies()
            providers, ollama = self.probe_ai_providers()
            tool_names = self.probe_active_tools()

            # Determine trust
            trust = "unknown"
            try:
                from core.execution_policy import get_trust
                trust = get_trust()
            except Exception:
                pass

            dep_map = {d.name: d.available for d in deps}
            missing = [d.name for d in deps if not d.available]

            readiness = (
                f"Zaya running on {os_info['platform_system']} ({os_info['architecture']}). "
                f"Tools loaded: {len(tool_names)}. Active AI providers: {', '.join(providers) or 'None'}. "
                f"Displays: {hw.displays}. Mic: {'Yes' if hw.has_microphone else 'No'}. "
                f"Missing optional packages: {', '.join(missing) if missing else 'None'}."
            )

            snap = CapabilitySnapshot(
                timestamp=now,
                os_name=os_info["os_name"],
                os_version=os_info["os_version"],
                platform_system=os_info["platform_system"],
                is_admin=os_info["is_admin"],
                hardware=asdict(hw),
                dependencies=dep_map,
                missing_dependencies=missing,
                active_tools_count=len(tool_names),
                active_tool_names=tool_names,
                active_providers=providers,
                local_ollama_available=ollama,
                trust_level=trust,
                readiness_summary=readiness,
            )

            self._cached_snapshot = snap
            self._cache_timestamp = now
            return snap

    def can_execute(self, capability: str) -> Tuple[bool, str]:
        """Check whether a specific action or capability can genuinely execute."""
        cap = capability.lower().strip()
        snap = self.snapshot()

        if cap in {"camera", "webcam", "video_capture"}:
            if not snap.dependencies.get("cv2", False):
                return False, "OpenCV (cv2) is not installed. Run: pip install opencv-python"
            if not snap.hardware.get("has_camera", False):
                return False, "No physical webcam or video capture device detected."
            return True, "Camera device is available and OpenCV is loaded."

        elif cap in {"gui_automation", "mouse_click", "keyboard_input"}:
            if not snap.dependencies.get("pyautogui", False):
                return False, "pyautogui is not installed. Run: pip install pyautogui"
            return True, "GUI automation is available."

        elif cap in {"screen_capture", "screen_peeler"}:
            if not snap.dependencies.get("mss", False):
                return False, "mss screen capture is not installed. Run: pip install mss"
            return True, "Screen capture is available."

        elif cap in {"browser_automation", "playwright"}:
            if not snap.dependencies.get("playwright", False):
                return False, "playwright is not installed. Run: pip install playwright"
            return True, "Browser automation is available."

        elif cap in {"local_llm", "ollama"}:
            if not snap.local_ollama_available:
                return False, "Local Ollama server is not reachable on http://127.0.0.1:11434."
            return True, "Local Ollama is active and responding."

        elif cap in {"cloud_ai", "gemini"}:
            if "gemini" not in snap.active_providers:
                return False, "GEMINI_API_KEY environment variable is not set."
            return True, "Gemini API key is configured."

        # Default check against active tools
        if cap in snap.active_tool_names:
            return True, f"Tool '{cap}' is loaded and active."

        return False, f"Capability or tool '{capability}' is not recognized or loaded."

    def explain_limitation(self, capability: str) -> str:
        """Produce an honest, factual explanation of a missing capability."""
        ok, reason = self.can_execute(capability)
        if ok:
            return f"'{capability}' is operational: {reason}"
        return f"Cannot execute '{capability}': {reason}"


# ── Global Singleton ─────────────────────────────────────────────────────────

_registry: Optional[CapabilityRegistry] = None
_registry_lock = threading.Lock()


def get_capability_registry() -> CapabilityRegistry:
    global _registry
    with _registry_lock:
        if _registry is None:
            _registry = CapabilityRegistry()
        return _registry
