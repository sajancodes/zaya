"""Route the smallest useful tool surface for the current owner request.

The router is deliberately deterministic. It is a latency and safety budget,
not a second model: when it cannot tell which tools are relevant it falls back
to a small, documented core set instead of every schema Zaya owns.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Iterable, Sequence


_TOKEN = re.compile(r"[a-z0-9]+")


def _text(value: Any) -> str:
    return value if isinstance(value, str) else ""


def normalize_declaration(declaration: Any) -> dict[str, Any]:
    """Return a plain declaration from either Zaya's dict form or an object."""
    if isinstance(declaration, dict):
        name = _text(declaration.get("name"))
        description = _text(declaration.get("description"))
        parameters = declaration.get("parameters")
        if parameters is None:
            parameters = declaration.get("input_schema")
        if parameters is None:
            parameters = declaration.get("parameters_json_schema")
        if parameters is None:
            parameters = {"type": "object", "properties": {}}
        return {"name": name, "description": description, "parameters": parameters}
    name = _text(getattr(declaration, "name", ""))
    description = _text(getattr(declaration, "description", ""))
    parameters = getattr(declaration, "parameters", None)
    if parameters is None:
        parameters = {"type": "object", "properties": {}}
    return {"name": name, "description": description, "parameters": parameters}


def schema_size(declaration: Any) -> int:
    try:
        return len(json.dumps(normalize_declaration(declaration), ensure_ascii=False, default=str))
    except (TypeError, ValueError):
        return 0


def _tokens(value: str) -> set[str]:
    return {token for token in _TOKEN.findall(value.lower()) if len(token) > 1}


# Behavioural areas, not provider names. A phrase can select more than one.
_CATEGORY_WORDS: dict[str, set[str]] = {
    "app": {"app", "application", "launch", "open", "close", "quit", "spotify", "chrome",
            "brave", "discord", "steam", "vscode", "notepad", "calculator", "explorer"},
    "computer": {"click", "double", "right", "type", "press", "key", "hotkey", "keyboard",
                 "mouse", "cursor", "scroll", "drag", "window", "minimize", "maximize",
                 "focus", "foreground", "desktop", "screen", "snap", "tile", "center",
                 "bluetooth", "wireless", "airpods", "earbuds", "headset"},
    "browser": {"browser", "tab", "website", "url", "page", "navigate", "reload",
                "playwright", "dom", "download", "bookmark"},
    "files": {"file", "files", "folder", "directory", "path", "read", "write", "create",
              "delete", "remove", "move", "copy", "rename", "list", "find", "zip",
              "pdf", "document", "excel", "csv", "word", "storage", "disk", "clean"},
    "terminal": {"terminal", "shell", "powershell", "pwsh", "cmd", "command", "run",
                 "execute", "script", "process", "kill", "terminate"},
    "git": {"git", "github", "commit", "stage", "push", "pull", "branch", "repo",
            "repository", "checkout", "diff", "merge", "remote", "uncommitted", "untracked", "clean"},
    "message": {"whatsapp", "telegram", "message", "send", "reply", "contact", "chat",
                "sms", "email", "mail", "inbox", "unread"},
    "phone": {"phone", "android", "companion", "call", "dial", "flashlight", "notification",
              "mobile", "device"},
    "memory": {"remember", "recall", "memory", "forget", "preference", "profile"},
    "time": {"remind", "reminder", "calendar", "schedule", "meeting", "appointment",
             "alarm", "timer"},
    "media": {"music", "song", "play", "pause", "resume", "next", "previous", "volume",
              "mute", "video", "youtube", "movie", "audio", "speakers", "headphones", "headset", "microphone", "whisper", "ceiling", "safety", "hearing"},
    "vision": {"see", "look", "screenshot", "screen", "camera", "image", "photo", "ocr",
               "read", "visible", "display", "perception", "vision", "monitor", "resolution", "refresh", "hz", "scaling", "gpu"},
    "web": {"search", "web", "internet", "news", "weather", "google", "research",
            "flight", "wiki", "information"},
    "spatial": {"spatial", "3d", "object", "scene", "model", "glb", "workspace"},
    "coding": {"code", "coding", "project", "build", "fix", "bug", "test", "opencode",
               "compile", "dependency", "install", "setup", "developer", "port", "ports"},
    "system": {"system", "battery", "cpu", "ram", "memory", "disk", "process", "status",
               "diagnostic", "logs", "runtime", "performance", "network"},
    "network": {"network", "ping", "latency", "dns", "wifi", "ethernet", "ip", "bandwidth", "speedtest", "port", "ports", "listening", "ssid", "wlan", "bssid", "rssi"},
    "clipboard": {"clipboard", "paste", "copy", "copied", "snippet", "vault"},
    "mission": {"mission", "plan", "steps", "background", "supervise", "multi", "task"},
    "whatsapp": {"whatsapp", "auto", "reply", "monitor", "contact"},
    "home": {"lights", "light", "tuya", "smart", "home", "mqtt", "printer"},
    "focus": {"focus", "disturb", "dnd", "quiet", "pomodoro", "notification", "notifications"},
    "power": {"battery", "power", "charger", "charging", "cycles", "health", "mwh", "wear", "drain", "energy"},
    "env": {"env", "environment", "path", "variable", "variables", "toolchain", "sdk", "compiler"},
    "thermal": {"temp", "temperature", "thermals", "gpu", "celsius", "overheating", "overheat", "fan", "wattage", "vram"},
    "service": {"service", "services", "daemon", "daemons", "wsl", "docker", "spooler", "svchost"},
    "startup": {"startup", "boot", "autorun", "autostart", "login"},
    "software": {"software", "program", "programs", "installed", "uninstall", "package", "packages"},
    "event": {"event", "events", "crash", "crashes", "bsod", "reboot", "shutdown", "bugcheck", "wevtutil", "error", "errors"},
    "tasks": {"task", "tasks", "scheduler", "schtasks", "cron", "scheduled", "automate"},
    "driver": {"driver", "drivers", "device", "devices", "pnputil", "hardware", "pnp", "peripheral", "peripherals"},
    "usb": {"usb", "pendrive", "flashdrive", "thumbdrive", "dongle", "removable", "port", "hub"},
    "firewall": {"firewall", "advfirewall", "inbound", "outbound", "rules", "block", "allow", "netsh"},
    "boot": {"boot", "uptime", "reboot", "restart", "shutdown", "wake", "sleep", "standby"},
    "dns": {"dns", "nameserver", "lookup", "resolve", "resolver", "domain", "hostname"},
}

# Tool names that are useful as a low-confidence fallback. They are cheap and
# cover the most common "what can you do / what is happening" turns.
_FALLBACK = (
    "runtime_status",
    "session_activity",
    "conversation_history",
    "open_app",
    "computer_control",
    "web_search",
)

# Extra names that map to an area even when the tool name has no shared token.
_CATEGORY_TOOLS: dict[str, set[str]] = {
    "app": {"open_app", "computer_control", "exit_app", "window_manager", "startup_sentinel", "software_sentinel"},
    "computer": {"computer_control", "computer_settings", "ghost_keyboard", "window_manager", "audio_switcher", "bluetooth_sentinel", "driver_sentinel", "usb_sentinel"},
    "browser": {"browser_control", "web_customizer"},
    "files": {"file_controller", "file_processor", "doc_generator", "screen_peeler", "storage_sentinel", "usb_sentinel"},
    "terminal": {"terminal_exec", "process_terminate", "runtime_logs", "coding_job", "process_sentinel", "port_sentinel", "service_sentinel", "event_log_sentinel", "task_scheduler_sentinel", "firewall_sentinel"},
    "git": {"git_control", "repo_sentinel"},
    "message": {"whatsapp", "send_message", "telegram_remote", "mobile_device"},
    "phone": {"mobile_device", "mobile_call", "port_tunnel"},
    "memory": {"personal_profile", "conversation_history", "session_activity", "quick_notes", "clipboard_vault"},
    "notes": {"quick_notes", "clipboard_vault"},
    "clipboard": {"clipboard_vault"},
    "time": {"reminder", "calendar_scheduler", "focus_mode", "task_scheduler_sentinel"},
    "media": {"media_controller", "video_player", "audio_switcher", "ear_safety"},
    "vision": {"display_perception", "hand_controls", "screen_peeler", "display_sentinel"},
    "web": {"web_search", "deep_research", "weather_report", "market_analytics", "map_navigator", "dns_sentinel"},
    "finance": {"market_analytics"},
    "travel": {"map_navigator"},
    "spatial": {"spatial_workspace"},
    "coding": {"coding_job", "code_search", "port_sentinel", "repo_sentinel", "env_sentinel"},
    "system": {"system_diagnostics", "runtime_status", "runtime_logs", "network_diagnostics", "process_sentinel", "storage_sentinel", "bluetooth_sentinel", "focus_mode", "power_sentinel", "env_sentinel", "display_sentinel", "thermal_sentinel", "service_sentinel", "startup_sentinel", "wifi_sentinel", "software_sentinel", "ear_safety", "event_log_sentinel", "task_scheduler_sentinel", "driver_sentinel", "usb_sentinel", "firewall_sentinel", "boot_sentinel", "dns_sentinel"},
    "storage": {"storage_sentinel", "usb_sentinel"},
    "bluetooth": {"bluetooth_sentinel"},
    "focus": {"focus_mode"},
    "power": {"power_sentinel", "computer_settings", "boot_sentinel"},
    "env": {"env_sentinel"},
    "thermal": {"thermal_sentinel"},
    "service": {"service_sentinel"},
    "startup": {"startup_sentinel"},
    "wifi": {"wifi_sentinel"},
    "software": {"software_sentinel"},
    "event": {"event_log_sentinel"},
    "tasks": {"task_scheduler_sentinel"},
    "driver": {"driver_sentinel"},
    "usb": {"usb_sentinel"},
    "firewall": {"firewall_sentinel"},
    "boot": {"boot_sentinel"},
    "dns": {"dns_sentinel"},
    "network": {"network_diagnostics", "system_diagnostics", "port_tunnel", "port_sentinel", "wifi_sentinel", "firewall_sentinel", "dns_sentinel"},
    "mission": {"mission_control"},
    "whatsapp": {"whatsapp"},
    "home": {"home_assistant", "printer_control"},
}


@dataclass(frozen=True)
class RouteResult:
    declarations: tuple[Any, ...]
    candidate_count: int
    schema_chars: int
    confidence: float
    fallback: bool = False


class ToolRouter:
    """Select a bounded, high-signal subset of declarations."""

    def __init__(self, fallback_names: Sequence[str] = _FALLBACK):
        self.fallback_names = tuple(fallback_names)

    @staticmethod
    def _categories(query: str) -> set[str]:
        words = _tokens(query)
        found: set[str] = set()
        for category, vocabulary in _CATEGORY_WORDS.items():
            if words & vocabulary:
                found.add(category)
        # Common compounds that tokenisation would split.
        low = query.lower()
        if any(pair in low for pair in ("multi step", "multi-step", "background task")):
            found.add("mission")
        if any(pair in low for pair in ("screen shot", "screenshot")):
            found.add("vision")
        return found

    def route(
        self,
        query: str,
        declarations: Iterable[Any],
        *,
        max_tools: int = 12,
        max_schema_chars: int = 14000,
        allow_fallback: bool = True,
    ) -> RouteResult:
        items = [d for d in declarations if normalize_declaration(d)["name"]]
        max_tools = max(1, int(max_tools or 1))
        max_schema_chars = max(256, int(max_schema_chars or 256))
        if not items:
            return RouteResult((), 0, 0, 0.0)

        query_words = _tokens(query)
        categories = self._categories(query)
        scored: list[tuple[float, int, Any]] = []
        for position, declaration in enumerate(items):
            normalized = normalize_declaration(declaration)
            name = normalized["name"].lower()
            name_words = _tokens(name.replace("_", " "))
            description_words = _tokens(normalized["description"])
            score = 0.0
            score += 4.0 * len(query_words & name_words)
            score += 1.0 * len(query_words & description_words)
            for category in categories:
                if name in _CATEGORY_TOOLS.get(category, set()):
                    score += 8.0
                if name_words & _CATEGORY_WORDS.get(category, set()):
                    score += 3.0
                if description_words & _CATEGORY_WORDS.get(category, set()):
                    score += 1.0
            # Prefer a short, single-purpose tool over a giant unrelated
            # automation surface when both happen to share a word.
            score -= min(1.0, len(description_words) / 500.0)
            scored.append((score, -position, declaration))

        scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
        positive = [item for item in scored if item[0] > 0]
        fallback = False
        if positive:
            chosen = positive
            best = positive[0][0]
            confidence = min(1.0, best / 18.0)
        else:
            fallback = True
            confidence = 0.0
            chosen = [item for item in scored if normalize_declaration(item[2])["name"] in self.fallback_names]
            if not chosen and allow_fallback:
                chosen = scored[:max_tools]

        if fallback and not allow_fallback:
            return RouteResult((), len(items), 0, confidence, fallback=True)

        selected: list[Any] = []
        used = 0
        seen: set[str] = set()
        for _, _, declaration in chosen:
            name = normalize_declaration(declaration)["name"]
            if name in seen:
                continue
            size = schema_size(declaration)
            if len(selected) >= max_tools:
                break
            if selected and used + size > max_schema_chars:
                continue
            if not selected and size > max_schema_chars:
                # A single oversized schema still has to be representable;
                # never silently drop the only relevant tool.
                selected.append(declaration)
                used += size
                seen.add(name)
                break
            selected.append(declaration)
            used += size
            seen.add(name)
            if used >= max_schema_chars:
                break

        return RouteResult(tuple(selected), len(items), used, confidence, fallback=fallback)
