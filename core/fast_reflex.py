"""Fast semantic reflex router for zero-latency local execution.

Executes high-frequency utility commands (media control, screenshots, time/date)
in < 2ms using lightweight pure-NumPy n-gram vector similarity and regex trees.
No heavy models or external API calls required.
"""
from __future__ import annotations

import datetime
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
import numpy as np


@dataclass
class FastReflexResult:
    matched: bool
    intent: str = ""
    ack: str = ""
    tool_name: str = ""
    arguments: dict = field(default_factory=dict)
    data: Any = None


# Intent definitions with canonical trigger phrases
REFLEX_INTENTS: Dict[str, Dict[str, Any]] = {
    "MEDIA_PAUSE": {
        "phrases": ["pause", "pause music", "pause video", "stop music", "pause playback", "hold on pause"],
        "media_key": "pause",
        "ack": "Paused, sir.",
    },
    "MEDIA_PLAY": {
        "phrases": ["play", "resume", "resume music", "continue playing", "unpause", "resume playback"],
        "media_key": "play",
        "ack": "Resuming playback, sir.",
    },
    "MEDIA_NEXT": {
        "phrases": ["next", "next track", "next song", "skip", "skip song", "skip track"],
        "media_key": "next",
        "ack": "Next track, sir.",
    },
    "MEDIA_PREV": {
        "phrases": ["previous", "previous track", "previous song", "last track", "last song", "go back a track"],
        "media_key": "previous",
        "ack": "Previous track, sir.",
    },
    "MEDIA_MUTE": {
        "phrases": ["mute", "mute volume", "mute sound", "mute pc", "silence audio", "unmute"],
        "media_key": "mute",
        "ack": "Mute toggled, sir.",
    },
    "VOLUME_UP": {
        "phrases": ["volume up", "turn it up", "louder", "raise volume", "increase volume"],
        "media_key": "volume_up",
        "ack": "Volume up, sir.",
    },
    "VOLUME_DOWN": {
        "phrases": ["volume down", "turn it down", "quieter", "lower volume", "decrease volume"],
        "media_key": "volume_down",
        "ack": "Volume down, sir.",
    },
    "SCREENSHOT": {
        "phrases": ["screenshot", "take screenshot", "take a screenshot", "capture screen", "screen grab"],
        "tool": "computer_control",
        "args": {"action": "screenshot"},
        "ack": "Screenshot captured, sir.",
    },
    "TIME_QUERY": {
        "phrases": ["what time is it", "current time", "what's the time", "tell me the time", "what time"],
        "dynamic": "time",
    },
    "DATE_QUERY": {
        "phrases": ["what date is it", "what's today's date", "today's date", "what is today's date", "what day is today"],
        "dynamic": "date",
    },
    "BATTERY_QUERY": {
        "phrases": [
            "battery", "what is my battery", "what's my battery", "battery status",
            "check battery", "battery level", "how much battery", "battery percentage"
        ],
        "dynamic": "battery",
    },
    "SYSTEM_HEALTH_QUERY": {
        "phrases": [
            "cpu usage", "check cpu usage", "ram usage", "check ram usage",
            "system health", "system status", "hardware status", "check cpu", "check ram",
            "check system health"
        ],
        "dynamic": "system_health",
    },
    "NETWORK_PING_QUERY": {
        "phrases": [
            "ping", "check ping", "test ping", "ping test", "network ping", "what is my ping"
        ],
        "dynamic": "network_ping",
    },
    "NETWORK_STATUS_QUERY": {
        "phrases": [
            "check internet", "internet status", "network status", "is internet working",
            "is wifi working", "check network", "internet connection"
        ],
        "dynamic": "network_status",
    },
    "CLIPBOARD_READ_QUERY": {
        "phrases": [
            "what's on my clipboard", "what is on my clipboard", "read clipboard",
            "check clipboard", "read my clipboard", "what did i copy"
        ],
        "dynamic": "clipboard_read",
    },
    "TOP_CPU_QUERY": {
        "phrases": [
            "what's using the most cpu", "what is using the most cpu", "top cpu",
            "top cpu process", "what's slowing down my pc", "top cpu processes"
        ],
        "dynamic": "top_cpu",
    },
    "NOT_RESPONDING_QUERY": {
        "phrases": [
            "any frozen apps", "any hung apps", "any apps not responding",
            "not responding apps", "frozen windows", "hung windows"
        ],
        "dynamic": "not_responding",
    },
    "DISK_SPACE_QUERY": {
        "phrases": [
            "how much disk space", "free disk space", "check disk space",
            "disk space", "storage status", "how much storage left", "hard drive space"
        ],
        "dynamic": "disk_space",
    },
    "DEV_PORTS_QUERY": {
        "phrases": [
            "check dev ports", "are dev ports free", "check open ports",
            "list listening ports", "listening ports", "check port status"
        ],
        "dynamic": "dev_ports",
    },
    "ACTIVE_AUDIO_DEVICE_QUERY": {
        "phrases": [
            "what audio device am i using", "what is my audio output",
            "current audio device", "list audio devices", "audio output device"
        ],
        "dynamic": "audio_device",
    },
    "APP_AUDIO_QUERY": {
        "phrases": [
            "what apps are playing audio", "what apps are making sound",
            "active audio apps", "app volume sessions"
        ],
        "dynamic": "app_audio",
    },
    "REPO_STATUS_QUERY": {
        "phrases": [
            "git status", "repo status", "check git status",
            "check repo status", "is repo clean", "any uncommitted changes"
        ],
        "dynamic": "repo_status",
    },
    "BLUETOOTH_STATUS_QUERY": {
        "phrases": [
            "is bluetooth on", "check bluetooth", "bluetooth status",
            "bluetooth devices", "any bluetooth connected"
        ],
        "dynamic": "bluetooth_status",
    },
    "FOCUS_MODE_QUERY": {
        "phrases": [
            "focus mode status", "how much focus time left", "is focus mode on",
            "check focus session", "focus status"
        ],
        "dynamic": "focus_status",
    },
    "BATTERY_HEALTH_QUERY": {
        "phrases": [
            "battery health", "battery wear", "battery degradation",
            "check battery health", "battery cycle count", "how healthy is my battery"
        ],
        "dynamic": "battery_health",
    },
    "PATH_AUDIT_QUERY": {
        "phrases": [
            "check path", "audit path", "verify path",
            "path status", "check path entries", "how is my path"
        ],
        "dynamic": "path_audit",
    },
    "DEV_TOOLS_AUDIT_QUERY": {
        "phrases": [
            "which dev tools are installed", "check dev tools", "installed cli tools",
            "what compilers are installed", "list dev tools", "installed developer tools"
        ],
        "dynamic": "dev_tools_audit",
    },
    "SCREEN_RESOLUTION_QUERY": {
        "phrases": [
            "screen resolution", "what is my screen resolution", "display resolution",
            "check screen resolution", "refresh rate", "what is my refresh rate",
            "display refresh rate", "check display hz"
        ],
        "dynamic": "display_resolution",
    },
    "HARDWARE_TEMPERATURE_QUERY": {
        "phrases": [
            "cpu temperature", "gpu temperature", "what is my gpu temperature",
            "check temperature", "is my pc overheating", "hardware temperature",
            "thermal status", "pc temperature", "how hot is my pc"
        ],
        "dynamic": "hardware_thermal",
    },
    "WINDOWS_SERVICES_QUERY": {
        "phrases": [
            "windows services", "check windows services", "running services",
            "list services", "service status", "how many services are running",
            "background services"
        ],
        "dynamic": "windows_services",
    },
    "STARTUP_PROGRAMS_QUERY": {
        "phrases": [
            "startup programs", "check startup programs", "what runs on startup",
            "startup apps", "list startup programs", "boot programs",
            "auto run programs"
        ],
        "dynamic": "startup_programs",
    },
    "WIFI_STATUS_QUERY": {
        "phrases": [
            "wifi status", "wifi signal", "what wifi am i on",
            "check wifi", "wifi connection", "wifi speed", "is wifi connected"
        ],
        "dynamic": "wifi_status",
    },
    "INSTALLED_SOFTWARE_QUERY": {
        "phrases": [
            "installed software", "check installed apps", "how many apps are installed",
            "list installed programs", "installed programs", "what apps are installed"
        ],
        "dynamic": "installed_software",
    },
    "WHISPER_MODE_CMD": {
        "phrases": [
            "whisper mode", "night mode", "turn on whisper mode",
            "quiet audio mode", "activate whisper mode"
        ],
        "tool": "ear_safety",
        "args": {"action": "whisper"},
        "ack": "Whisper Mode activated. Master volume set to 15% with DND engaged, sir.",
    },
    "NORMAL_AUDIO_MODE_CMD": {
        "phrases": [
            "normal audio mode", "daytime audio mode", "restore audio mode",
            "turn off whisper mode"
        ],
        "tool": "ear_safety",
        "args": {"action": "normal"},
        "ack": "Normal audio mode restored at 50% volume, sir.",
    },
    "EAR_SAFETY_STATUS_QUERY": {
        "phrases": [
            "ear safety status", "check volume limit", "volume ceiling",
            "what is my volume limit", "ear safety"
        ],
        "dynamic": "ear_safety_status",
    },
    "EVENT_LOG_QUERY": {
        "phrases": [
            "system errors", "check system errors", "event log errors",
            "system crash logs", "any crashes", "check event log", "windows event logs"
        ],
        "dynamic": "event_log_errors",
    },
    "SCHEDULED_TASKS_QUERY": {
        "phrases": [
            "scheduled tasks", "check scheduled tasks", "what tasks are scheduled",
            "task scheduler", "list scheduled tasks", "check task scheduler"
        ],
        "dynamic": "scheduled_tasks",
    },
    "HARDWARE_DEVICES_QUERY": {
        "phrases": [
            "hardware devices", "check hardware devices", "device drivers",
            "check drivers", "any device problems", "hardware health", "device manager"
        ],
        "dynamic": "hardware_devices",
    },
    "USB_DEVICES_QUERY": {
        "phrases": [
            "usb devices", "check usb devices", "what usb devices are plugged in",
            "check usb", "usb ports", "removable drives", "usb flash drive"
        ],
        "dynamic": "usb_devices",
    },
    "FIREWALL_STATUS_QUERY": {
        "phrases": [
            "firewall status", "check firewall", "windows firewall",
            "is firewall enabled", "check firewall status"
        ],
        "dynamic": "firewall_status",
    },
    "SYSTEM_UPTIME_QUERY": {
        "phrases": [
            "system uptime", "how long has my pc been on", "when did my pc boot",
            "uptime", "last reboot", "pc uptime", "how long has the computer been running"
        ],
        "dynamic": "system_uptime",
    },
    "DNS_HEALTH_QUERY": {
        "phrases": [
            "dns status", "check dns", "what is my dns", "dns servers",
            "dns latency", "dns speed", "test dns", "check dns speed"
        ],
        "dynamic": "dns_health",
    },
    "MEMORY_ANALYSIS_QUERY": {
        "phrases": [
            "memory breakdown", "top memory apps", "memory pressure",
            "what is using my ram", "memory leak check", "ram breakdown",
            "memory footprint", "app memory usage"
        ],
        "dynamic": "memory_analysis",
    },
    "LOCAL_IP_QUERY": {
        "phrases": [
            "what is my local ip", "my ip address", "local ip", "check local ip",
            "what is my ip", "router ip", "default gateway", "my mac address"
        ],
        "dynamic": "local_ip",
    },
    "MIC_STATUS_QUERY": {
        "phrases": [
            "is my mic muted", "check microphone", "mic status", "microphone status",
            "microphone volume", "is microphone muted", "check mic", "mic volume"
        ],
        "dynamic": "mic_status",
    },
    "MIC_MUTE": {
        "phrases": [
            "mute my mic", "mute microphone", "mute mic", "mute the mic"
        ],
        "dynamic": "mic_mute",
    },
    "MIC_UNMUTE": {
        "phrases": [
            "unmute my mic", "unmute microphone", "unmute mic", "unmute the mic"
        ],
        "dynamic": "mic_unmute",
    },
    "PROTOCOL_HANDLER_QUERY": {
        "phrases": [
            "check protocol handlers", "what protocols are registered", "protocol handlers",
            "check registered protocols", "url protocols", "deep link handlers"
        ],
        "dynamic": "protocol_handlers",
    },
    "NIGHT_LIGHT_STATUS": {
        "phrases": [
            "is night light on", "check night light", "night light status",
            "is blue light filter on", "check blue light filter"
        ],
        "dynamic": "night_light_status",
    },
    "NIGHT_LIGHT_ON": {
        "phrases": [
            "turn on night light", "enable night light", "activate night light",
            "turn on blue light filter", "enable blue light filter"
        ],
        "dynamic": "night_light_on",
    },
    "NIGHT_LIGHT_OFF": {
        "phrases": [
            "turn off night light", "disable night light", "deactivate night light",
            "turn off blue light filter", "disable blue light filter"
        ],
        "dynamic": "night_light_off",
    },
    "NIGHT_LIGHT_TOGGLE": {
        "phrases": [
            "toggle night light", "switch night light", "toggle blue light filter"
        ],
        "dynamic": "night_light_toggle",
    },
    "RECYCLE_BIN_QUERY": {
        "phrases": [
            "how much trash is in recycle bin", "check recycle bin", "recycle bin status",
            "recycle bin size", "is recycle bin empty", "check trash", "check the trash"
        ],
        "dynamic": "recycle_bin_status",
    },
    "RECYCLE_BIN_EMPTY": {
        "phrases": [
            "empty recycle bin", "clear recycle bin", "empty the recycle bin",
            "empty trash", "clear trash"
        ],
        "dynamic": "recycle_bin_empty",
    },
    "DEFAULT_APP_QUERY": {
        "phrases": [
            "what opens pdf", "default app for pdf", "what app opens mp4",
            "default browser app", "check file associations", "default apps", "what opens zip"
        ],
        "dynamic": "default_apps",
    },
    "TIMEZONE_QUERY": {
        "phrases": [
            "what is my timezone", "check timezone", "what's my timezone",
            "system timezone", "current timezone", "utc offset", "what timezone am i in"
        ],
        "dynamic": "timezone_status",
    },
    "CLIPBOARD_HISTORY_QUERY": {
        "phrases": [
            "is clipboard history enabled", "check clipboard history", "clipboard history status",
            "is clipboard history on", "clipboard history"
        ],
        "dynamic": "clipboard_history_status",
    },
    "CLIPBOARD_HISTORY_ON": {
        "phrases": [
            "enable clipboard history", "turn on clipboard history", "activate clipboard history"
        ],
        "dynamic": "clipboard_history_on",
    },
    "CLIPBOARD_HISTORY_OFF": {
        "phrases": [
            "disable clipboard history", "turn off clipboard history", "deactivate clipboard history"
        ],
        "dynamic": "clipboard_history_off",
    },
    "POWER_PLAN_QUERY": {
        "phrases": [
            "what power plan am i on", "check power plan", "power plan status",
            "current power scheme", "what is my power mode"
        ],
        "dynamic": "power_plan_status",
    },
    "HOSTS_FILE_QUERY": {
        "phrases": [
            "check hosts file", "what's in my hosts file", "what is in my hosts file",
            "hosts file entries", "local domain overrides", "hosts file status"
        ],
        "dynamic": "hosts_file_status",
    },
    "FOCUS_MODE_START": {
        "phrases": [
            "start focus mode", "turn on focus mode", "activate focus mode",
            "enter focus mode", "begin focus mode"
        ],
        "tool": "focus_mode",
        "args": {"action": "start", "duration_minutes": 25, "goal": "Deep work"},
        "ack": "Focus mode activated for 25 minutes. Do Not Disturb is active, sir.",
    },
    "FOCUS_MODE_STOP": {
        "phrases": [
            "end focus mode", "stop focus mode", "turn off focus mode",
            "finish focus session", "exit focus mode"
        ],
        "tool": "focus_mode",
        "args": {"action": "stop"},
        "ack": "Focus session completed, sir.",
    },
    "DND_TOGGLE": {
        "phrases": [
            "toggle do not disturb", "toggle dnd", "turn on do not disturb",
            "quiet hours", "enable do not disturb"
        ],
        "tool": "focus_mode",
        "args": {"action": "dnd_toggle"},
        "ack": "Do Not Disturb toggled, sir.",
    },
    "WINDOW_SNAP_LEFT": {
        "phrases": [
            "snap left", "snap window left", "window left", "snap active window left"
        ],
        "tool": "window_manager",
        "args": {"action": "snap", "position": "left"},
        "ack": "Window snapped to the left, sir.",
    },
    "WINDOW_SNAP_RIGHT": {
        "phrases": [
            "snap right", "snap window right", "window right", "snap active window right"
        ],
        "tool": "window_manager",
        "args": {"action": "snap", "position": "right"},
        "ack": "Window snapped to the right, sir.",
    },
    "WINDOW_CENTER": {
        "phrases": [
            "center window", "center active window", "center the window"
        ],
        "tool": "window_manager",
        "args": {"action": "center"},
        "ack": "Window centered, sir.",
    },
    "WINDOW_MAXIMIZE": {
        "phrases": [
            "maximize window", "maximize active window", "maximize the window"
        ],
        "tool": "window_manager",
        "args": {"action": "maximize"},
        "ack": "Window maximized, sir.",
    },
    "POWER_PERFORMANCE": {
        "phrases": [
            "performance mode", "switch to performance mode", "enable performance mode",
            "turn on performance mode", "high performance mode", "activate performance mode"
        ],
        "tool": "computer_settings",
        "args": {"action": "performance_mode"},
        "ack": "Performance mode activated, sir.",
    },
    "POWER_BALANCED": {
        "phrases": [
            "balanced mode", "switch to balanced mode", "enable balanced mode",
            "turn on balanced mode", "balanced power mode"
        ],
        "tool": "computer_settings",
        "args": {"action": "balanced_mode"},
        "ack": "Balanced mode enabled, sir.",
    },
    "POWER_BATTERY": {
        "phrases": [
            "battery saver", "switch to battery saver", "enable battery saver",
            "turn on battery saver", "power saver mode"
        ],
        "tool": "computer_settings",
        "args": {"action": "battery_saver"},
        "ack": "Battery saver activated, sir.",
    },
    "SYSTEM_LOCK": {
        "phrases": [
            "lock screen", "lock my pc", "lock computer", "lock the screen", "lock workstation"
        ],
        "tool": "computer_settings",
        "args": {"action": "lock_screen"},
        "ack": "Workstation locked, sir.",
    },
    "SHOW_DESKTOP": {
        "phrases": [
            "show desktop", "minimize all windows", "minimize everything", "go to desktop"
        ],
        "tool": "computer_settings",
        "args": {"action": "show_desktop"},
        "ack": "Showing desktop, sir.",
    },
    "SLEEP_DISPLAY": {
        "phrases": [
            "sleep display", "turn off screen", "turn off display", "turn off monitor"
        ],
        "tool": "computer_settings",
        "args": {"action": "sleep_display"},
        "ack": "Display turned off, sir.",
    },
    "MONITOR_MODE_START": {
        "phrases": [
            "monitor mode active", "activate monitor mode", "turn on monitor mode",
            "start monitor mode", "enable monitor mode", "monitor my screen",
            "monitor mode on", "monitor screen"
        ],
        "tool": "robotics_screen_monitor",
        "args": {"action": "start", "task": "Continuous screen surveillance and spatial monitoring"},
        "ack": "Monitor mode active, sir. Continuously observing your display.",
    },
    "MONITOR_MODE_STOP": {
        "phrases": [
            "monitor mode inactive", "deactivate monitor mode", "turn off monitor mode",
            "stop monitor mode", "disable monitor mode", "monitor mode off"
        ],
        "tool": "robotics_screen_monitor",
        "args": {"action": "stop"},
        "ack": "Monitor mode deactivated, sir.",
    },
    "DARK_MODE": {
        "phrases": [
            "toggle dark mode", "switch dark mode", "toggle theme", "toggle dark theme"
        ],
        "tool": "computer_settings",
        "args": {"action": "dark_mode"},
        "ack": "Theme toggled, sir.",
    },
    "OPEN_CALCULATOR": {
        "phrases": [
            "open calculator", "launch calculator", "start calculator"
        ],
        "tool": "open_app",
        "args": {"app": "calculator"},
        "ack": "Opening calculator, sir.",
    },
    "OPEN_NOTEPAD": {
        "phrases": [
            "open notepad", "launch notepad", "start notepad"
        ],
        "tool": "open_app",
        "args": {"app": "notepad"},
        "ack": "Opening Notepad, sir.",
    },
    "OPEN_TERMINAL": {
        "phrases": [
            "open terminal", "launch terminal", "open command prompt", "launch cmd"
        ],
        "tool": "open_app",
        "args": {"app": "terminal"},
        "ack": "Opening terminal, sir.",
    },
    "OPEN_EXPLORER": {
        "phrases": [
            "open file explorer", "open explorer", "open files", "launch file explorer"
        ],
        "tool": "open_app",
        "args": {"app": "file explorer"},
        "ack": "Opening File Explorer, sir.",
    },
    "OPEN_TASK_MANAGER": {
        "phrases": [
            "open task manager", "launch task manager", "start task manager"
        ],
        "tool": "open_app",
        "args": {"app": "task manager"},
        "ack": "Opening Task Manager, sir.",
    },
}


_NEGATION_RE = re.compile(
    r"\b(don't|dont|do\s+not|never|not|no|stop|cancel|avoid|prevent|disallow|won't|wont|will\s+not|shouldn't|should\s+not|cannot|can't|cant|refrain\s+from|i\s+(?:don't|dont|do\s+not)\s+want)\b",
    re.IGNORECASE,
)

_QUESTION_HYPOTHETICAL_RE = re.compile(
    r"^(what\s+happens\s+if|what\s+would\s+happen|what\s+if|how\s+do\s+i|how\s+can\s+i|how\s+to|why\s+would|why\s+should|explain\s+how|explain\s+why|explain\s+what|explain\b|tell\s+me\s+about|tell\s+me\s+how|tell\s+me\s+what|is\s+it\s+(?:possible|safe)\s+to|can\s+you\s+explain|what\s+are\s+the\s+consequences)\b",
    re.IGNORECASE,
)

_FILLER_WORDS = {
    "the", "a", "an", "my", "your", "please", "zaya", "hey", "can", "you",
    "to", "for", "me", "now", "just", "it", "this", "that", "up", "on", "in"
}


def _tokenize_3grams(text: str) -> set[str]:
    clean = re.sub(r"[^\w\s]", "", text.lower().strip())
    words = clean.split()
    chars = f" {' '.join(words)} "
    return {chars[i : i + 3] for i in range(len(chars) - 2)}


class FastReflexRouter:
    def __init__(self):
        # Build vocabulary from all phrases
        vocab = set()
        self._intent_vectors: List[Tuple[str, np.ndarray]] = []
        for intent_name, intent_data in REFLEX_INTENTS.items():
            for p in intent_data["phrases"]:
                vocab.update(_tokenize_3grams(p))

        self._vocab_list = sorted(vocab)
        self._vocab_idx = {gram: i for i, gram in enumerate(self._vocab_list)}
        dim = len(self._vocab_list)

        # Precompute normalized intent vectors with phrases
        for intent_name, intent_data in REFLEX_INTENTS.items():
            for p in intent_data["phrases"]:
                v = self._vectorize(p, dim)
                norm = np.linalg.norm(v)
                if norm > 0:
                    self._intent_vectors.append((intent_name, v / norm, p))

    def _vectorize(self, text: str, dim: int) -> np.ndarray:
        vec = np.zeros(dim, dtype=np.float32)
        for gram in _tokenize_3grams(text):
            idx = self._vocab_idx.get(gram)
            if idx is not None:
                vec[idx] += 1.0
        return vec

    def match(self, text: str) -> Tuple[Optional[str], float]:
        """Matches input text against reflex intents. Returns (intent_name, score)."""
        raw_clean = text.lower().strip()
        raw_clean = re.sub(r"^(zaya|hey zaya|please|hey)\s+", "", raw_clean).strip()

        # Questions, explanations, or hypotheticals must route to full reasoning engine
        if _QUESTION_HYPOTHETICAL_RE.search(raw_clean):
            return None, 0.0

        is_question = text.strip().endswith("?") or "?" in text
        user_negations = set(m.lower().strip() for m in _NEGATION_RE.findall(raw_clean))

        clean = re.sub(r"[?!.,]", "", raw_clean).strip()
        if not clean:
            return None, 0.0

        # Exact match check first (sub-millisecond)
        for intent_name, intent_data in REFLEX_INTENTS.items():
            for p in intent_data["phrases"]:
                if clean == p:
                    phrase_negations = set(m.lower().strip() for m in _NEGATION_RE.findall(p))
                    if user_negations - phrase_negations:
                        # Extra unhandled negation
                        continue
                    if is_question and not intent_name.endswith("_QUERY"):
                        continue
                    return intent_name, 1.0

        # Don't evaluate long conversational queries as micro-reflexes
        if len(clean.split()) > 6:
            return None, 0.0

        # Vector cosine similarity
        query_vec = self._vectorize(clean, len(self._vocab_list))
        norm = np.linalg.norm(query_vec)
        if norm == 0:
            return None, 0.0
        query_vec /= norm

        best_intent = None
        best_score = 0.0
        best_phrase = ""
        for intent_name, ref_vec, p in self._intent_vectors:
            score = float(np.dot(query_vec, ref_vec))
            if score > best_score:
                best_score = score
                best_intent = intent_name
                best_phrase = p

        if best_score >= 0.88 and best_intent:
            # Action intents must never match questions
            if is_question and not best_intent.endswith("_QUERY"):
                return None, best_score

            # Verify negation consistency: user cannot have extra negations not present in matched phrase
            phrase_negations = set(m.lower().strip() for m in _NEGATION_RE.findall(best_phrase))
            if user_negations - phrase_negations:
                return None, 0.0

            # Substantive token coverage check: substantive words cannot silently vanish
            q_words = set(re.findall(r"\b\w+\b", clean))
            p_words = set(re.findall(r"\b\w+\b", best_phrase))
            extra_words = [w for w in (q_words - p_words) if w not in _FILLER_WORDS]
            if extra_words:
                # If any extra word is a negation, question marker, or if there are 2+ extra substantive words
                if any(_NEGATION_RE.search(w) for w in extra_words) or len(extra_words) >= 2:
                    return None, 0.0

            return best_intent, best_score
        return None, best_score

    def execute_intent(self, intent_name: str) -> FastReflexResult:
        """Executes a matched reflex intent locally and immediately."""
        intent_data = REFLEX_INTENTS.get(intent_name)
        if not intent_data:
            return FastReflexResult(matched=False)

        # Dynamic query intents
        if intent_data.get("dynamic") == "time":
            now_str = datetime.datetime.now().strftime("%I:%M %p").lstrip("0")
            return FastReflexResult(
                matched=True,
                intent=intent_name,
                ack=f"It is {now_str}, sir.",
                data={"time": now_str},
            )

        if intent_data.get("dynamic") == "date":
            today_str = datetime.datetime.now().strftime("%A, %B %d, %Y")
            return FastReflexResult(
                matched=True,
                intent=intent_name,
                ack=f"Today is {today_str}, sir.",
                data={"date": today_str},
            )

        if intent_data.get("dynamic") == "battery":
            try:
                import psutil
                batt = psutil.sensors_battery()
                if batt is not None:
                    pct = int(batt.percent)
                    if batt.power_plugged:
                        ack = f"Battery is at {pct}% and charging, sir." if pct < 100 else "Battery is fully charged at 100%, sir."
                    else:
                        ack = f"Battery is at {pct}%, sir."
                    return FastReflexResult(
                        matched=True,
                        intent=intent_name,
                        ack=ack,
                        data={"percent": pct, "plugged": bool(batt.power_plugged)},
                    )
            except Exception:
                pass
            return FastReflexResult(matched=True, intent=intent_name, ack="Battery sensor is unavailable, sir.")

        if intent_data.get("dynamic") == "system_health":
            try:
                from services.system_monitor import get_system_status
                st = get_system_status()
                cpu = st.get("cpu_percent", 0)
                ram_pct = st.get("ram_percent", 0)
                ram_used = st.get("ram_used_gb", 0)
                ram_tot = st.get("ram_total_gb", 0)
                ack = f"CPU is at {cpu}%, RAM is at {ram_pct}% ({ram_used} GB of {ram_tot} GB used), sir."
                return FastReflexResult(matched=True, intent=intent_name, ack=ack, data=st)
            except Exception:
                pass
            return FastReflexResult(matched=True, intent=intent_name, ack="System metrics are currently unavailable, sir.")

        if intent_data.get("dynamic") == "network_ping":
            try:
                from actions.network_diagnostics import _run_icmp_ping
                res = _run_icmp_ping("1.1.1.1", count=1, timeout_ms=600)
                if res.get("reachable"):
                    ack = f"Ping is {res['avg_ms']} milliseconds, sir."
                else:
                    ack = "Ping target is currently unreachable, sir."
                return FastReflexResult(matched=True, intent=intent_name, ack=ack, data=res)
            except Exception:
                pass
            return FastReflexResult(matched=True, intent=intent_name, ack="Unable to test ping right now, sir.")

        if intent_data.get("dynamic") == "network_status":
            try:
                from actions.network_diagnostics import _check_tcp_latency, _get_local_ip
                online = _check_tcp_latency("1.1.1.1", 53, timeout=0.8) is not None
                local_ip = _get_local_ip()
                if online:
                    ack = f"Internet is connected, local IP is {local_ip}, sir."
                else:
                    ack = "Internet connection appears to be offline, sir."
                return FastReflexResult(matched=True, intent=intent_name, ack=ack, data={"online": online, "local_ip": local_ip})
            except Exception:
                pass
            return FastReflexResult(matched=True, intent=intent_name, ack="Network status is currently unavailable, sir.")

        if intent_data.get("dynamic") == "clipboard_read":
            try:
                from actions.clipboard_vault import _read_system_clipboard
                text = _read_system_clipboard().strip()
                if not text:
                    ack = "The clipboard is currently empty, sir."
                elif len(text) > 70:
                    ack = f"Clipboard has {len(text)} characters: {text[:65]}..., sir."
                else:
                    ack = f"Clipboard content is: {text}, sir."
                return FastReflexResult(matched=True, intent=intent_name, ack=ack, data={"content": text, "char_count": len(text)})
            except Exception:
                pass
            return FastReflexResult(matched=True, intent=intent_name, ack="Unable to read the clipboard right now, sir.")

        if intent_data.get("dynamic") == "top_cpu":
            try:
                from actions.process_sentinel import _get_top_cpu
                top = _get_top_cpu(1)
                if top:
                    ack = f"Top CPU process is {top[0]['name']} at {top[0]['cpu_percent']}%, sir."
                else:
                    ack = "No high CPU processes detected, sir."
                return FastReflexResult(matched=True, intent=intent_name, ack=ack, data=top)
            except Exception:
                pass
            return FastReflexResult(matched=True, intent=intent_name, ack="Unable to inspect CPU processes right now, sir.")

        if intent_data.get("dynamic") == "not_responding":
            try:
                from actions.process_sentinel import _detect_hung_windows
                hung = _detect_hung_windows()
                if hung:
                    ack = f"Detected {len(hung)} frozen window(s): {hung[0]['title']} ({hung[0]['process_name']}), sir."
                else:
                    ack = "No frozen or unresponsive applications detected, sir."
                return FastReflexResult(matched=True, intent=intent_name, ack=ack, data=hung)
            except Exception:
                pass
            return FastReflexResult(matched=True, intent=intent_name, ack="Unable to scan for unresponsive applications, sir.")

        if intent_data.get("dynamic") == "disk_space":
            try:
                from actions.storage_sentinel import _get_drive_telemetry
                drives = _get_drive_telemetry()
                if drives:
                    primary = drives[0]
                    ack = f"Drive {primary['mountpoint']} has {primary['free_gb']} GB free out of {primary['total_gb']} GB, sir."
                else:
                    ack = "Storage information is currently unavailable, sir."
                return FastReflexResult(matched=True, intent=intent_name, ack=ack, data=drives)
            except Exception:
                pass
            return FastReflexResult(matched=True, intent=intent_name, ack="Unable to inspect disk storage right now, sir.")

        if intent_data.get("dynamic") == "dev_ports":
            try:
                from actions.port_sentinel import _scan_dev_ports
                dev = _scan_dev_ports()
                occ = len(dev.get("occupied", []))
                free = len(dev.get("free", []))
                if occ > 0:
                    first = dev["occupied"][0]
                    ack = f"{occ} dev port(s) active, including {first['port']} ({first['process_name']}). {free} ports free, sir."
                else:
                    ack = f"All {free} common dev ports are completely free, sir."
                return FastReflexResult(matched=True, intent=intent_name, ack=ack, data=dev)
            except Exception:
                pass
            return FastReflexResult(matched=True, intent=intent_name, ack="Unable to inspect dev ports right now, sir.")

        if intent_data.get("dynamic") == "audio_device":
            try:
                from actions.audio_switcher import _get_default_speakers
                spk = _get_default_speakers()
                ack = f"Audio is outputting through '{spk['device']}' at {spk['volume_percent']}%, sir."
                return FastReflexResult(matched=True, intent=intent_name, ack=ack, data=spk)
            except Exception:
                pass
            return FastReflexResult(matched=True, intent=intent_name, ack="Unable to inspect audio devices right now, sir.")

        if intent_data.get("dynamic") == "app_audio":
            try:
                from actions.audio_switcher import _list_app_sessions
                sessions = _list_app_sessions()
                if sessions:
                    apps_str = ", ".join(s["process"] for s in sessions)
                    ack = f"Found {len(sessions)} active audio app(s): {apps_str}, sir."
                else:
                    ack = "No apps are currently producing audio, sir."
                return FastReflexResult(matched=True, intent=intent_name, ack=ack, data=sessions)
            except Exception:
                pass
            return FastReflexResult(matched=True, intent=intent_name, ack="Unable to inspect application audio sessions, sir.")

        if intent_data.get("dynamic") == "repo_status":
            try:
                from actions.repo_sentinel import _inspect_repo_status
                st = _inspect_repo_status()
                if st.get("is_git_repo"):
                    if st["clean"]:
                        sync = f", ahead by {st['ahead']}" if st['ahead'] > 0 else ", in sync"
                        ack = f"Repository '{st['repo_name']}' is clean on branch '{st['branch']}'{sync}, sir."
                    else:
                        dirty_total = st['unstaged_count'] + st['staged_count'] + st['untracked_count']
                        ack = f"Repository '{st['repo_name']}' has {dirty_total} uncommitted file(s) on branch '{st['branch']}', sir."
                else:
                    ack = "Active directory is not a Git repository, sir."
                return FastReflexResult(matched=True, intent=intent_name, ack=ack, data=st)
            except Exception:
                pass
            return FastReflexResult(matched=True, intent=intent_name, ack="Unable to inspect repository status right now, sir.")

        if intent_data.get("dynamic") == "bluetooth_status":
            try:
                from actions.bluetooth_sentinel import _get_bluetooth_telemetry
                data = _get_bluetooth_telemetry()
                if data["adapter_present"]:
                    ack = f"Bluetooth is on via {data['adapter_name']}. {data['paired_count']} paired device(s), {data['connected_count']} connected, sir."
                else:
                    ack = "Bluetooth is currently off or adapter is disconnected, sir."
                return FastReflexResult(matched=True, intent=intent_name, ack=ack, data=data)
            except Exception:
                pass
            return FastReflexResult(matched=True, intent=intent_name, ack="Unable to inspect Bluetooth status right now, sir.")

        if intent_data.get("dynamic") == "focus_status":
            try:
                from actions.focus_mode import _get_active_session, _get_windows_quiet_hours_state
                act = _get_active_session()
                if act:
                    elapsed = round((time.time() - act.get("start_ts", time.time())) / 60.0, 1)
                    rem = max(0.0, round(act.get("target_minutes", 25) - elapsed, 1))
                    ack = f"Focus mode is active on '{act.get('goal', 'Deep work')}'. {rem}m remaining of {act.get('target_minutes', 25)}m, sir."
                else:
                    quiet = _get_windows_quiet_hours_state()
                    dnd_str = "DND is on" if quiet.get("dnd_active") else "DND is off"
                    ack = f"No active focus session ({dnd_str}), sir."
                return FastReflexResult(matched=True, intent=intent_name, ack=ack, data=act)
            except Exception:
                pass
            return FastReflexResult(matched=True, intent=intent_name, ack="Unable to inspect focus status right now, sir.")

        if intent_data.get("dynamic") == "battery_health":
            try:
                from actions.power_sentinel import _generate_battery_health_report
                rep = _generate_battery_health_report()
                if rep.get("has_battery"):
                    cond = rep.get("condition", "Good")
                    pct = rep.get("health_percent", 100.0)
                    cycles = rep.get("cycle_count", "N/A")
                    ack = f"Battery health is {cond} at {pct}% with {cycles} cycles completed, sir."
                else:
                    ack = "Running on direct AC power with no battery hardware detected, sir."
                return FastReflexResult(matched=True, intent=intent_name, ack=ack, data=rep)
            except Exception:
                pass
            return FastReflexResult(matched=True, intent=intent_name, ack="Unable to inspect battery health right now, sir.")

        if intent_data.get("dynamic") == "path_audit":
            try:
                from actions.env_sentinel import _audit_path
                res = _audit_path()
                ack = f"PATH has {res['total_entries']} entries ({res['missing_count']} missing, {res['duplicate_count']} duplicates). Status: {res['health']}, sir."
                return FastReflexResult(matched=True, intent=intent_name, ack=ack, data=res)
            except Exception:
                pass
            return FastReflexResult(matched=True, intent=intent_name, ack="Unable to audit system PATH right now, sir.")

        if intent_data.get("dynamic") == "dev_tools_audit":
            try:
                from actions.env_sentinel import _audit_developer_tools
                res = _audit_developer_tools()
                top = ", ".join(t["name"] for t in res["installed"][:6])
                ack = f"Found {res['installed_count']} active developer tools on PATH: {top}, sir."
                return FastReflexResult(matched=True, intent=intent_name, ack=ack, data=res)
            except Exception:
                pass
            return FastReflexResult(matched=True, intent=intent_name, ack="Unable to audit developer tools right now, sir.")

        if intent_data.get("dynamic") == "display_resolution":
            try:
                from actions.display_sentinel import _get_display_metrics
                m = _get_display_metrics()
                ack = f"Display is {m['physical_width']}x{m['physical_height']} at {m['refresh_rate_hz']}Hz ({m['dpi_scale_percent']}% scaling, {m['primary_gpu']}), sir."
                return FastReflexResult(matched=True, intent=intent_name, ack=ack, data=m)
            except Exception:
                pass
            return FastReflexResult(matched=True, intent=intent_name, ack="Unable to inspect display resolution right now, sir.")

        if intent_data.get("dynamic") == "hardware_thermal":
            try:
                from actions.thermal_sentinel import _query_nvidia_smi, _query_cpu_telemetry
                gpu = _query_nvidia_smi()
                cpu = _query_cpu_telemetry()
                cpu_ghz = round(cpu["current_frequency_mhz"] / 1000.0, 2)
                if gpu.get("available"):
                    ack = f"GPU is {gpu['condition']} at {gpu['temperature_c']}°C ({gpu['power_draw_w']}W). CPU is at {cpu_ghz} GHz, sir."
                else:
                    ack = f"CPU is at {cpu_ghz} GHz across {cpu['logical_cores']} threads ({cpu['average_load_percent']}% load), sir."
                return FastReflexResult(matched=True, intent=intent_name, ack=ack, data={"gpu": gpu, "cpu": cpu})
            except Exception:
                pass
            return FastReflexResult(matched=True, intent=intent_name, ack="Unable to inspect hardware thermals right now, sir.")

        if intent_data.get("dynamic") == "windows_services":
            try:
                from actions.service_sentinel import _get_services_summary
                data = _get_services_summary()
                ack = f"Windows has {data['running_count']} running services out of {data['total']} registered, sir."
                return FastReflexResult(matched=True, intent=intent_name, ack=ack, data=data)
            except Exception:
                pass
            return FastReflexResult(matched=True, intent=intent_name, ack="Unable to inspect Windows services right now, sir.")

        if intent_data.get("dynamic") == "startup_programs":
            try:
                from actions.startup_sentinel import _get_all_startup_entries
                data = _get_all_startup_entries()
                ack = f"Found {data['total_count']} auto-run startup programs ({data['dead_count']} orphaned targets), sir."
                return FastReflexResult(matched=True, intent=intent_name, ack=ack, data=data)
            except Exception:
                pass
            return FastReflexResult(matched=True, intent=intent_name, ack="Unable to inspect startup programs right now, sir.")

        if intent_data.get("dynamic") == "wifi_status":
            try:
                from actions.wifi_sentinel import _get_wifi_interface_telemetry
                data = _get_wifi_interface_telemetry()
                if data.get("connected"):
                    ack = f"Connected to '{data['ssid']}' on {data['band']} with {data['signal_percent']}% signal ({data['rx_rate_mbps']} Mbps), sir."
                else:
                    ack = "Wi-Fi is currently disconnected or inactive, sir."
                return FastReflexResult(matched=True, intent=intent_name, ack=ack, data=data)
            except Exception:
                pass
            return FastReflexResult(matched=True, intent=intent_name, ack="Unable to inspect Wi-Fi status right now, sir.")

        if intent_data.get("dynamic") == "installed_software":
            try:
                from actions.software_sentinel import _audit_installed_software
                apps = _audit_installed_software()
                ack = f"Found {len(apps)} installed desktop applications registered on Windows, sir."
                return FastReflexResult(matched=True, intent=intent_name, ack=ack, data=apps[:10])
            except Exception:
                pass
            return FastReflexResult(matched=True, intent=intent_name, ack="Unable to inspect installed software right now, sir.")

        if intent_data.get("dynamic") == "ear_safety_status":
            try:
                from actions.ear_safety import _load_safety_config, _get_master_volume
                cfg = _load_safety_config()
                vol = _get_master_volume()
                ack = f"Ear safety ceiling is set to {cfg['max_volume_percent']}% (Current volume: {vol}%), sir."
                return FastReflexResult(matched=True, intent=intent_name, ack=ack, data=cfg)
            except Exception:
                pass
            return FastReflexResult(matched=True, intent=intent_name, ack="Unable to inspect ear safety status right now, sir.")

        if intent_data.get("dynamic") == "event_log_errors":
            try:
                from actions.event_log_sentinel import get_event_log_summary
                data = get_event_log_summary()
                latest_crash = data.get("latest_app_crash")
                crash_note = f" Latest crash: {latest_crash['app_name']}." if latest_crash else ""
                ack = f"Event Log Status: {data['health_status']}. Found {data['recent_system_errors_count']} system errors and {data['recent_app_crashes_count']} app crashes.{crash_note}"
                return FastReflexResult(matched=True, intent=intent_name, ack=ack, data=data)
            except Exception:
                pass
            return FastReflexResult(matched=True, intent=intent_name, ack="Unable to inspect Windows event logs right now, sir.")

        if intent_data.get("dynamic") == "scheduled_tasks":
            try:
                from actions.task_scheduler_sentinel import get_scheduler_summary
                data = get_scheduler_summary()
                running_part = f" ({data['running_tasks_count']} running)" if data['running_tasks_count'] else ""
                ack = f"Task Scheduler has {data['user_and_app_tasks_count']} application tasks registered{running_part} out of {data['total_tasks_registered']} total, sir."
                return FastReflexResult(matched=True, intent=intent_name, ack=ack, data=data)
            except Exception:
                pass
            return FastReflexResult(matched=True, intent=intent_name, ack="Unable to inspect scheduled tasks right now, sir.")

        if intent_data.get("dynamic") == "hardware_devices":
            try:
                from actions.driver_sentinel import get_hardware_health_summary
                data = get_hardware_health_summary()
                prob_part = f" Warning: {data['problem_device_count']} problem devices detected." if data['problem_device_count'] else " All devices OK."
                ack = f"Hardware Health: {data['hardware_health']}. GPU: {data['primary_gpu']}.{prob_part}"
                return FastReflexResult(matched=True, intent=intent_name, ack=ack, data=data)
            except Exception:
                pass
            return FastReflexResult(matched=True, intent=intent_name, ack="Unable to inspect hardware devices right now, sir.")

        if intent_data.get("dynamic") == "usb_devices":
            try:
                from actions.usb_sentinel import get_usb_summary
                data = get_usb_summary()
                drives_note = f" and {data['removable_drives_count']} removable storage drive(s)" if data['removable_drives_count'] else ""
                ack = f"Detected {data['connected_usb_devices_count']} connected USB devices{drives_note}, sir."
                return FastReflexResult(matched=True, intent=intent_name, ack=ack, data=data)
            except Exception:
                pass
            return FastReflexResult(matched=True, intent=intent_name, ack="Unable to inspect USB devices right now, sir.")

        if intent_data.get("dynamic") == "firewall_status":
            try:
                from actions.firewall_sentinel import get_firewall_summary
                data = get_firewall_summary()
                ack = f"Windows Firewall: {data['security_posture']}, sir."
                return FastReflexResult(matched=True, intent=intent_name, ack=ack, data=data)
            except Exception:
                pass
            return FastReflexResult(matched=True, intent=intent_name, ack="Unable to inspect Windows Firewall status right now, sir.")

        if intent_data.get("dynamic") == "system_uptime":
            try:
                from actions.boot_sentinel import get_system_uptime
                data = get_system_uptime()
                ack = f"System has been running for {data['uptime_formatted']}, sir."
                return FastReflexResult(matched=True, intent=intent_name, ack=ack, data=data)
            except Exception:
                pass
            return FastReflexResult(matched=True, intent=intent_name, ack="Unable to inspect system uptime right now, sir.")

        if intent_data.get("dynamic") == "dns_health":
            try:
                from actions.dns_sentinel import get_dns_health_summary
                data = get_dns_health_summary()
                ack = f"DNS Health: {data['health_rating']}. Primary DNS: {data['primary_dns_server']} ({data['average_latency_ms']} ms avg latency), sir."
                return FastReflexResult(matched=True, intent=intent_name, ack=ack, data=data)
            except Exception:
                pass
            return FastReflexResult(matched=True, intent=intent_name, ack="Unable to inspect DNS health right now, sir.")

        if intent_data.get("dynamic") == "memory_analysis":
            try:
                from actions.memory_sentinel import assess_memory_pressure
                data = assess_memory_pressure()
                stats = data["stats"]
                dom = data.get("dominant_application")
                top_str = f" Leading consumer: {dom['application']} ({dom['memory_mb']:,} MB)." if dom else ""
                ack = f"RAM Status: {data['pressure_level']}. Using {stats['ram_used_gb']} GB of {stats['ram_total_gb']} GB ({stats['ram_percent']}%).{top_str}"
                return FastReflexResult(matched=True, intent=intent_name, ack=ack, data=data)
            except Exception:
                pass
            return FastReflexResult(matched=True, intent=intent_name, ack="Unable to inspect memory usage right now, sir.")

        if intent_data.get("dynamic") == "local_ip":
            try:
                from actions.adapter_sentinel import get_network_ip_summary
                data = get_network_ip_summary()
                gw_str = f" (Router: {data['default_gateway']})" if data['default_gateway'] != "Unknown" else ""
                ack = f"Your local IP is {data['primary_ip']} on {data['primary_adapter_name']}{gw_str}, sir."
                return FastReflexResult(matched=True, intent=intent_name, ack=ack, data=data)
            except Exception:
                pass
            return FastReflexResult(matched=True, intent=intent_name, ack="Unable to inspect network adapter IP right now, sir.")

        if intent_data.get("dynamic") == "mic_status":
            try:
                from actions.mic_sentinel import get_microphone_status
                data = get_microphone_status()
                mute_str = "MUTED" if data["muted"] else "UNMUTED"
                ack = f"Microphone is {mute_str} ({data['device']} at {data['volume_percent']}% volume), sir."
                return FastReflexResult(matched=True, intent=intent_name, ack=ack, data=data)
            except Exception:
                pass
            return FastReflexResult(matched=True, intent=intent_name, ack="Unable to inspect microphone status right now, sir.")

        if intent_data.get("dynamic") == "mic_mute":
            try:
                from actions.mic_sentinel import set_microphone_mute
                data = set_microphone_mute(True)
                ack = "Microphone muted, sir."
                return FastReflexResult(matched=True, intent=intent_name, ack=ack, data=data)
            except Exception:
                pass
            return FastReflexResult(matched=True, intent=intent_name, ack="Unable to mute microphone right now, sir.")

        if intent_data.get("dynamic") == "mic_unmute":
            try:
                from actions.mic_sentinel import set_microphone_mute
                data = set_microphone_mute(False)
                ack = "Microphone unmuted, sir."
                return FastReflexResult(matched=True, intent=intent_name, ack=ack, data=data)
            except Exception:
                pass
            return FastReflexResult(matched=True, intent=intent_name, ack="Unable to unmute microphone right now, sir.")

        if intent_data.get("dynamic") == "protocol_handlers":
            try:
                from actions.protocol_sentinel import get_protocol_summary
                data = get_protocol_summary()
                apps_preview = ", ".join(data["popular_apps_sample"][:5]) if data["popular_apps_sample"] else "Standard handlers"
                ack = f"Found {data['total_protocols_registered']} registered URL protocols ({apps_preview}), sir."
                return FastReflexResult(matched=True, intent=intent_name, ack=ack, data=data)
            except Exception:
                pass
            return FastReflexResult(matched=True, intent=intent_name, ack="Unable to inspect protocol handlers right now, sir.")

        if intent_data.get("dynamic") == "night_light_status":
            try:
                from actions.night_light_sentinel import get_night_light_status
                data = get_night_light_status()
                sched = data["schedule"]
                sched_txt = f" (scheduled {sched['start_time']} - {sched['end_time']})" if sched["has_schedule"] else ""
                ack = f"Windows Night Light is currently {data['state_label']}{sched_txt}, sir."
                return FastReflexResult(matched=True, intent=intent_name, ack=ack, data=data)
            except Exception:
                pass
            return FastReflexResult(matched=True, intent=intent_name, ack="Unable to check Night Light status right now, sir.")

        if intent_data.get("dynamic") == "night_light_on":
            try:
                from actions.night_light_sentinel import set_night_light
                data = set_night_light(True)
                ack = "Windows Night Light enabled, sir."
                return FastReflexResult(matched=True, intent=intent_name, ack=ack, data=data)
            except Exception:
                pass
            return FastReflexResult(matched=True, intent=intent_name, ack="Unable to enable Night Light right now, sir.")

        if intent_data.get("dynamic") == "night_light_off":
            try:
                from actions.night_light_sentinel import set_night_light
                data = set_night_light(False)
                ack = "Windows Night Light disabled, sir."
                return FastReflexResult(matched=True, intent=intent_name, ack=ack, data=data)
            except Exception:
                pass
            return FastReflexResult(matched=True, intent=intent_name, ack="Unable to disable Night Light right now, sir.")

        if intent_data.get("dynamic") == "night_light_toggle":
            try:
                from actions.night_light_sentinel import toggle_night_light
                data = toggle_night_light()
                new_state = "enabled" if data.get("enabled") else "disabled"
                ack = f"Windows Night Light {new_state}, sir."
                return FastReflexResult(matched=True, intent=intent_name, ack=ack, data=data)
            except Exception:
                pass
            return FastReflexResult(matched=True, intent=intent_name, ack="Unable to toggle Night Light right now, sir.")

        if intent_data.get("dynamic") == "recycle_bin_status":
            try:
                from actions.recycle_bin_sentinel import get_recycle_bin_stats
                data = get_recycle_bin_stats()
                if data["is_empty"]:
                    ack = "Recycle Bin is completely empty, sir."
                else:
                    ack = f"Recycle Bin contains {data['items_count']:,} item(s) using {data['size_mb']} MB of disk space, sir."
                return FastReflexResult(matched=True, intent=intent_name, ack=ack, data=data)
            except Exception:
                pass
            return FastReflexResult(matched=True, intent=intent_name, ack="Unable to inspect Recycle Bin right now, sir.")

        if intent_data.get("dynamic") == "recycle_bin_empty":
            try:
                from actions.recycle_bin_sentinel import empty_recycle_bin
                data = empty_recycle_bin(confirm=True)
                if data.get("status") == "success":
                    ack = f"Recycle Bin emptied, freed {data.get('freed_mb', 0)} MB across {data.get('freed_items', 0)} item(s), sir."
                elif data.get("status") == "partial_success":
                    ack = f"Recycle Bin partially emptied: removed {data.get('freed_items', 0)} item(s) ({data.get('freed_mb', 0)} MB), but {data.get('remaining_items', 0)} item(s) remain locked, sir."
                elif data.get("status") == "unverified":
                    ack = "Recycle Bin empty command executed, but remaining items could not be verified, sir."
                elif data.get("status") == "cancelled":
                    ack = "Recycle Bin emptying was cancelled, sir."
                else:
                    ack = data.get("message") or "Unable to empty Recycle Bin right now, sir."
                return FastReflexResult(matched=True, intent=intent_name, ack=ack, data=data)
            except Exception:
                pass
            return FastReflexResult(matched=True, intent=intent_name, ack="Unable to empty Recycle Bin right now, sir.")

        if intent_data.get("dynamic") == "default_apps":
            try:
                from actions.file_assoc_sentinel import get_common_associations_audit
                data = get_common_associations_audit()
                hl = data["highlights"]
                ack = f"Default Apps: Web: {hl['browser_default']}, PDF: {hl['pdf_reader']}, Archives: {hl['archive_manager']}, Editor: {hl['text_editor']}, sir."
                return FastReflexResult(matched=True, intent=intent_name, ack=ack, data=data)
            except Exception:
                pass
            return FastReflexResult(matched=True, intent=intent_name, ack="Unable to inspect default applications right now, sir.")

        if intent_data.get("dynamic") == "timezone_status":
            try:
                from actions.clock_sentinel import get_system_timezone_info
                data = get_system_timezone_info()
                ack = f"System timezone is {data['timezone_name']} ({data['utc_offset']}), sir."
                return FastReflexResult(matched=True, intent=intent_name, ack=ack, data=data)
            except Exception:
                pass
            return FastReflexResult(matched=True, intent=intent_name, ack="Unable to inspect system timezone right now, sir.")

        if intent_data.get("dynamic") == "clipboard_history_status":
            try:
                from actions.clipboard_ring_sentinel import get_clipboard_history_status
                data = get_clipboard_history_status()
                ack = f"Windows Clipboard History is currently {data['state_label']} ({data['hotkey']}), sir."
                return FastReflexResult(matched=True, intent=intent_name, ack=ack, data=data)
            except Exception:
                pass
            return FastReflexResult(matched=True, intent=intent_name, ack="Unable to check Clipboard History status right now, sir.")

        if intent_data.get("dynamic") == "clipboard_history_on":
            try:
                from actions.clipboard_ring_sentinel import set_clipboard_history
                data = set_clipboard_history(True)
                ack = "Windows Clipboard History enabled (Win + V), sir."
                return FastReflexResult(matched=True, intent=intent_name, ack=ack, data=data)
            except Exception:
                pass
            return FastReflexResult(matched=True, intent=intent_name, ack="Unable to enable Clipboard History right now, sir.")

        if intent_data.get("dynamic") == "clipboard_history_off":
            try:
                from actions.clipboard_ring_sentinel import set_clipboard_history
                data = set_clipboard_history(False)
                ack = "Windows Clipboard History disabled, sir."
                return FastReflexResult(matched=True, intent=intent_name, ack=ack, data=data)
            except Exception:
                pass
            return FastReflexResult(matched=True, intent=intent_name, ack="Unable to disable Clipboard History right now, sir.")

        if intent_data.get("dynamic") == "power_plan_status":
            try:
                from actions.power_plan_sentinel import get_active_power_scheme
                data = get_active_power_scheme()
                ack = f"Active Windows power plan is {data['name']}, sir."
                return FastReflexResult(matched=True, intent=intent_name, ack=ack, data=data)
            except Exception:
                pass
            return FastReflexResult(matched=True, intent=intent_name, ack="Unable to inspect power scheme right now, sir.")

        if intent_data.get("dynamic") == "hosts_file_status":
            try:
                from actions.hosts_sentinel import get_hosts_summary
                data = get_hosts_summary()
                dev_str = f" ({data['local_dev_mappings']} local dev mapping(s))" if data['local_dev_mappings'] else ""
                ack = f"Hosts file contains {data['total_mappings']} active mapping(s){dev_str}, sir."
                return FastReflexResult(matched=True, intent=intent_name, ack=ack, data=data)
            except Exception:
                pass
            return FastReflexResult(matched=True, intent=intent_name, ack="Unable to inspect hosts file right now, sir.")

        # Media key dispatch
        media_key = intent_data.get("media_key")
        if media_key:
            try:
                from actions.media_controller import dispatch_media_key
                dispatch_media_key(media_key)
            except Exception as e:
                print(f"[FastReflex] Media key error: {e}")
            return FastReflexResult(
                matched=True,
                intent=intent_name,
                ack=intent_data.get("ack", "Done, sir."),
                tool_name="media_controller",
                arguments={"action": media_key},
            )

        # Tool dispatch
        tool = intent_data.get("tool")
        if tool == "computer_control":
            args = intent_data.get("args", {})
            try:
                from actions.computer_control import computer_control
                res = computer_control(args)
            except Exception as e:
                res = str(e)
            return FastReflexResult(
                matched=True,
                intent=intent_name,
                ack=intent_data.get("ack", "Done, sir."),
                tool_name=tool,
                arguments=args,
                data=res,
            )

        if tool == "computer_settings":
            args = intent_data.get("args", {})
            try:
                from actions.computer_settings import computer_settings
                res = computer_settings(args)
            except Exception as e:
                res = str(e)
            return FastReflexResult(
                matched=True,
                intent=intent_name,
                ack=intent_data.get("ack", "Done, sir."),
                tool_name=tool,
                arguments=args,
                data=res,
            )

        if tool == "open_app":
            args = intent_data.get("args", {})
            try:
                from actions.open_app import open_app
                res = open_app(args)
            except Exception as e:
                res = str(e)
            return FastReflexResult(
                matched=True,
                intent=intent_name,
                ack=intent_data.get("ack", "Done, sir."),
                tool_name=tool,
                arguments=args,
                data=res,
            )

        if tool == "window_manager":
            args = intent_data.get("args", {})
            try:
                from actions.window_manager import window_manager
                res = window_manager(args)
            except Exception as e:
                res = str(e)
            return FastReflexResult(
                matched=True,
                intent=intent_name,
                ack=intent_data.get("ack", "Done, sir."),
                tool_name=tool,
                arguments=args,
                data=res,
            )

        if tool == "focus_mode":
            args = intent_data.get("args", {})
            try:
                from actions.focus_mode import focus_mode
                res = focus_mode(args)
            except Exception as e:
                res = str(e)
            return FastReflexResult(
                matched=True,
                intent=intent_name,
                ack=intent_data.get("ack", "Done, sir."),
                tool_name=tool,
                arguments=args,
                data=res,
            )

        if tool == "ear_safety":
            args = intent_data.get("args", {})
            try:
                from actions.ear_safety import ear_safety
                res = ear_safety(args)
            except Exception as e:
                res = str(e)
            return FastReflexResult(
                matched=True,
                intent=intent_name,
                ack=intent_data.get("ack", "Done, sir."),
                tool_name=tool,
                arguments=args,
                data=res,
            )

        if tool == "robotics_screen_monitor":
            args = intent_data.get("args", {})
            try:
                from actions.robotics_monitor_action import handle_robotics_screen_monitor
                res = handle_robotics_screen_monitor(**args)
            except Exception as e:
                res = str(e)
            return FastReflexResult(
                matched=True,
                intent=intent_name,
                ack=intent_data.get("ack", "Monitor mode active, sir."),
                tool_name=tool,
                arguments=args,
                data=res,
            )

        return FastReflexResult(matched=True, intent=intent_name, ack=intent_data.get("ack", "Done, sir."))

    def handle(self, text: str) -> Optional[FastReflexResult]:
        """Convenience method: matches and executes if confidence is sufficient."""
        intent_name, score = self.match(text)
        if intent_name and score >= 0.88:
            return self.execute_intent(intent_name)
        return None


# Global singleton instance
fast_reflex = FastReflexRouter()
