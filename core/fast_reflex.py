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

        # Precompute normalized intent vectors
        for intent_name, intent_data in REFLEX_INTENTS.items():
            for p in intent_data["phrases"]:
                v = self._vectorize(p, dim)
                norm = np.linalg.norm(v)
                if norm > 0:
                    self._intent_vectors.append((intent_name, v / norm))

    def _vectorize(self, text: str, dim: int) -> np.ndarray:
        vec = np.zeros(dim, dtype=np.float32)
        for gram in _tokenize_3grams(text):
            idx = self._vocab_idx.get(gram)
            if idx is not None:
                vec[idx] += 1.0
        return vec

    def match(self, text: str) -> Tuple[Optional[str], float]:
        """Matches input text against reflex intents. Returns (intent_name, score)."""
        clean = text.lower().strip()
        clean = re.sub(r"^(zaya|hey zaya|please|hey)\s+", "", clean).strip()
        clean = re.sub(r"[?!.,]", "", clean).strip()

        if not clean:
            return None, 0.0

        # Exact match check first (sub-millisecond)
        for intent_name, intent_data in REFLEX_INTENTS.items():
            for p in intent_data["phrases"]:
                if clean == p:
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
        for intent_name, ref_vec in self._intent_vectors:
            score = float(np.dot(query_vec, ref_vec))
            if score > best_score:
                best_score = score
                best_intent = intent_name

        if best_score >= 0.88:
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

        return FastReflexResult(matched=True, intent=intent_name, ack=intent_data.get("ack", "Done, sir."))

    def handle(self, text: str) -> Optional[FastReflexResult]:
        """Convenience method: matches and executes if confidence is sufficient."""
        intent_name, score = self.match(text)
        if intent_name and score >= 0.88:
            return self.execute_intent(intent_name)
        return None


# Global singleton instance
fast_reflex = FastReflexRouter()
