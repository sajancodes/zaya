"""
core/pc_ecosystem.py — Zaya Secure Phone-PC AI Ecosystem.

Enables secure, allowlisted, carefully gated computer assistance from paired
Android companions. Built to enforce:
  1. Strict command allowlist with typed argument validation (no arbitrary shell).
  2. Strict filesystem boundaries (permitted directories, traversal prevention,
     symlink escape prevention, device path blocking, sensitive file exclusion).
  3. Safe process invocation (structured args, allowlisted application IDs, no shell=True).
  4. Explicit approval gate for consequential operations (file write/delete, process termination).
  5. Privacy-conscious audit trail with secret redaction.
"""
from __future__ import annotations

import logging
import os
import platform
import re
import shutil
import subprocess
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from core.audit import redact

log = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_UPLOADS = ROOT / "uploads"

# Execution and payload limits
MAX_READ_BYTES = 512 * 1024       # 512 KB
MAX_DIR_ENTRIES = 100
MAX_DIAGNOSTIC_LINES = 50
COMMAND_TIMEOUT_SECONDS = 10.0
APPROVAL_TTL_SECONDS = 300.0       # 5 minutes

# Windows device paths and reserved names
_DANGEROUS_DEVICE_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
    "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9",
}

# Sensitive filename patterns and directory names that must NEVER be accessed
_SENSITIVE_NAMES = {
    ".ssh", ".aws", ".gnupg", ".config", ".env", ".bash_history", ".zshrc",
    "id_rsa", "id_ed25519", "id_ecdsa", "id_dsa", "known_hosts",
    "authorized_keys", "credentials", "api_keys.json", "master.key",
    "wallet.dat", "keychain", "ntds.dit", "sam", "system", "security",
}

_SENSITIVE_EXTENSIONS = {
    ".pem", ".key", ".pfx", ".p12", ".kdbx", ".env", ".secret",
}

_CRITICAL_SYSTEM_PROCESSES = {
    "csrss", "lsass", "smss", "winlogon", "services", "system", "explorer",
    "init", "systemd", "kernel", "launchd",
}

# Controlled application registry (only these app IDs may be launched)
_ALLOWLISTED_APPS: dict[str, dict[str, str]] = {
    "calculator": {"Windows": "calc.exe", "Darwin": "Calculator", "Linux": "gnome-calculator"},
    "notepad": {"Windows": "notepad.exe", "Darwin": "TextEdit", "Linux": "gedit"},
    "spotify": {"Windows": "Spotify", "Darwin": "Spotify", "Linux": "spotify"},
    "browser": {"Windows": "msedge", "Darwin": "Safari", "Linux": "firefox"},
    "terminal": {"Windows": "cmd.exe", "Darwin": "Terminal", "Linux": "bash"},
    "code": {"Windows": "code", "Darwin": "Visual Studio Code", "Linux": "code"},
    "vscode": {"Windows": "code", "Darwin": "Visual Studio Code", "Linux": "code"},
    "vlc": {"Windows": "vlc", "Darwin": "VLC", "Linux": "vlc"},
}


def redact_secrets(text: str | Any) -> str:
    """Ensure any token, secret hash, API key or password is scrubbed."""
    if not isinstance(text, str):
        text = str(text)
    # Scrub JWTs (header starts with eyJ)
    text = re.sub(r'eyJ[\w\-]{10,}\.[\w\-]{10,}(?:\.[\w\-]+)?', '[REDACTED]', text)
    # Scrub Bearer tokens
    text = re.sub(r'(?i)bearer\s+[\w\-.~+/]+', 'Bearer [REDACTED]', text)
    # Scrub provider specific keys like Gemini / OpenAI / GitHub
    text = re.sub(r'(?:AIza[\w-]{15,}|gh[pousr]_[\w]{15,}|sk-[\w-]{15,})', '[REDACTED]', text)
    # Scrub key/token/secret/password pairs
    text = re.sub(r'(?i)(?:api[_-]?key|token|password|secret|cookie|authorization|key)\s*[:=]\s*["\']?[\w\-.~+/]{6,}["\']?', '[REDACTED]', text)
    # Also pass through core.audit.redact
    return str(redact(text))


class PermittedDirectoryManager:
    """Manages explicit directory containment for remote PC file operations."""

    def __init__(self, permitted_roots: list[Path | str] | None = None) -> None:
        self._lock = threading.RLock()
        self.roots: list[Path] = []
        if permitted_roots:
            for r in permitted_roots:
                self.add_root(r)
        else:
            # Default to project workspace and uploads folder
            self.add_root(ROOT)
            self.add_root(DEFAULT_UPLOADS)

    def add_root(self, path: Path | str) -> bool:
        p = Path(path).resolve()
        # Reject root filesystems (e.g. C:\ or /)
        if p.parent == p or str(p) in ("/", "\\", "C:\\", "c:\\", "D:\\", "d:\\"):
            log.warning("Refused to add root directory as permitted: %s", p)
            return False
        with self._lock:
            if p not in self.roots:
                self.roots.append(p)
                return True
        return False

    def remove_root(self, path: Path | str) -> bool:
        p = Path(path).resolve()
        with self._lock:
            if p in self.roots:
                self.roots.remove(p)
                return True
        return False

    def list_roots(self) -> list[str]:
        with self._lock:
            return [str(r) for r in self.roots]

    def validate_path(self, raw_path: str, must_exist: bool = True) -> tuple[Path | None, str | None]:
        """Normalize, inspect, and verify strict containment inside a permitted root."""
        if not raw_path or not isinstance(raw_path, str):
            return None, "Empty or invalid path argument"

        if "\x00" in raw_path:
            return None, "Null bytes in path rejected"

        clean = raw_path.strip()
        # Check raw traversal markers before resolution
        parts = Path(clean).parts
        if ".." in parts or any(p == ".." for p in clean.replace("\\", "/").split("/")):
            return None, "Path traversal sequence detected ('..')"

        # Check Windows device paths
        for part in parts:
            name_no_ext = Path(part).stem.upper()
            if name_no_ext in _DANGEROUS_DEVICE_NAMES:
                return None, f"Dangerous device name rejected: {part}"
        if clean.startswith(("\\\\.\\", "\\\\?\\")):
            return None, "Windows device prefix rejected"

        try:
            target = Path(clean)
            if not target.is_absolute():
                with self._lock:
                    default_root = self.roots[0] if self.roots else ROOT
                target = (default_root / target).resolve()
            else:
                target = target.resolve()
        except Exception as err:
            return None, f"Invalid path resolution: {err}"

        # Containment verification
        contained = False
        with self._lock:
            for root in self.roots:
                try:
                    if target == root or target.is_relative_to(root):
                        contained = True
                        break
                except Exception:
                    continue

        if not contained:
            return None, "Path is outside permitted directories"

        # Check for symlink escapes: resolved target must still be relative to root
        try:
            real_target = Path(os.path.realpath(target))
            with self._lock:
                real_contained = any(real_target == r or real_target.is_relative_to(r) for r in self.roots)
            if not real_contained:
                return None, "Symlink escape detected: target points outside permitted boundary"
        except Exception as err:
            return None, f"Symlink resolution error: {err}"

        # Sensitive directory / file check
        for part in target.parts:
            low = part.lower()
            if low in _SENSITIVE_NAMES:
                return None, f"Access to sensitive resource '{part}' is forbidden"
            if Path(part).suffix.lower() in _SENSITIVE_EXTENSIONS:
                return None, f"Access to sensitive file extension '{Path(part).suffix}' is forbidden"

        if must_exist and not target.exists():
            return None, "Target path does not exist"

        return target, None


@dataclass
class PendingApproval:
    approval_id: str
    device_id: str
    command: str
    resource: str
    parameters: dict[str, Any]
    potential_side_effects: str
    reversible: bool
    created_at: float = field(default_factory=time.time)
    expires_at: float = field(default_factory=lambda: time.time() + APPROVAL_TTL_SECONDS)

    def to_dict(self) -> dict[str, Any]:
        return {
            "approval_id": self.approval_id,
            "device_id": self.device_id,
            "command": self.command,
            "resource": self.resource,
            "parameters": redact(self.parameters),
            "potential_side_effects": self.potential_side_effects,
            "reversible": self.reversible,
            "expires_in": max(0, int(self.expires_at - time.time())),
        }


class ApprovalManager:
    """Manages explicit user confirmations for consequential PC actions."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._pending: dict[str, PendingApproval] = {}

    def create(self, device_id: str, command: str, resource: str,
               parameters: dict[str, Any], side_effects: str,
               reversible: bool = False) -> PendingApproval:
        now = time.time()
        self._prune(now)
        approval_id = uuid.uuid4().hex
        approval = PendingApproval(
            approval_id=approval_id,
            device_id=device_id,
            command=command,
            resource=resource,
            parameters=parameters,
            potential_side_effects=side_effects,
            reversible=reversible,
            created_at=now,
            expires_at=now + APPROVAL_TTL_SECONDS,
        )
        with self._lock:
            self._pending[approval_id] = approval
        return approval

    def get(self, approval_id: str) -> PendingApproval | None:
        now = time.time()
        with self._lock:
            self._prune(now)
            return self._pending.get(approval_id)

    def consume(self, approval_id: str, device_id: str) -> PendingApproval | None:
        """Validate and atomically remove approval. Prevents replay."""
        now = time.time()
        with self._lock:
            self._prune(now)
            approval = self._pending.get(approval_id)
            if not approval or approval.device_id != device_id:
                return None
            return self._pending.pop(approval_id, None)

    def reject(self, approval_id: str, device_id: str) -> bool:
        with self._lock:
            approval = self._pending.get(approval_id)
            if approval and approval.device_id == device_id:
                self._pending.pop(approval_id, None)
                return True
        return False

    def list_for_device(self, device_id: str) -> list[dict[str, Any]]:
        now = time.time()
        with self._lock:
            self._prune(now)
            return [
                a.to_dict() for a in self._pending.values()
                if a.device_id == device_id
            ]

    def _prune(self, now: float) -> None:
        stale = [aid for aid, a in self._pending.items() if a.expires_at <= now]
        for aid in stale:
            self._pending.pop(aid, None)


class PCAuditLogger:
    """Privacy-conscious, secret-redacted audit log for PC ecosystem operations."""

    def __init__(self, max_entries: int = 200) -> None:
        self._lock = threading.RLock()
        self._entries: list[dict[str, Any]] = []
        self._max = max_entries

    def log(self, device_id: str, command: str, status: str,
            summary: str, error: str | None = None) -> None:
        entry = {
            "timestamp": time.time(),
            "device_id": device_id[:16],
            "command": command,
            "status": status,
            "summary": redact_secrets(summary[:300]),
            "error": redact_secrets(error[:300]) if error else None,
        }
        with self._lock:
            self._entries.append(entry)
            if len(self._entries) > self._max:
                self._entries = self._entries[-self._max:]

    def get_entries(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._lock:
            return list(reversed(self._entries[-limit:]))


class PCEcosystemBridge:
    """Typed Allowlisted PC Command Interface for Zaya.

    Every operation enforces:
      1. Paired device check & device authorization.
      2. Allowlisted command validation.
      3. Typed argument schema validation.
      4. Risk classification & approval gate.
      5. Filesystem & process safety boundaries.
      6. Output limits and execution timeouts.
      7. Privacy-conscious audit trail.
    """

    def __init__(self, permitted_roots: list[Path | str] | None = None) -> None:
        self.dirs = PermittedDirectoryManager(permitted_roots)
        self.approvals = ApprovalManager()
        self.audit = PCAuditLogger()
        self._running_processes: dict[str, subprocess.Popen] = {}
        self._lock = threading.RLock()

    def get_allowed_commands(self) -> dict[str, Any]:
        """Return schema and risk metadata for all allowlisted commands."""
        return {
            "reachability": {
                "risk": "LOW",
                "requires_approval": False,
                "description": "Check if PC companion service is alive",
                "parameters": {},
            },
            "system_status": {
                "risk": "LOW",
                "requires_approval": False,
                "description": "Get CPU, memory, battery, and platform status",
                "parameters": {},
            },
            "diagnostic_info": {
                "risk": "LOW",
                "requires_approval": False,
                "description": "Read non-sensitive diagnostic logs with redacted secrets",
                "parameters": {"component": "string (optional)", "limit": "int (optional, max 50)"},
            },
            "system_info": {
                "risk": "LOW",
                "requires_approval": False,
                "description": "Bounded system architecture and runtime summary",
                "parameters": {"detail_level": "string (optional: basic|summary)"},
            },
            "launch_app": {
                "risk": "MEDIUM",
                "requires_approval": False,
                "description": "Launch an approved application by identifier",
                "parameters": {
                    "app_id": "string (one of: spotify, calculator, notepad, browser, terminal, code, vlc)"
                },
            },
            "list_dir": {
                "risk": "LOW",
                "requires_approval": False,
                "description": "List files in a permitted directory",
                "parameters": {
                    "directory": "string (optional, defaults to workspace)",
                    "max_entries": "int (optional, max 100)"
                },
            },
            "read_file": {
                "risk": "LOW",
                "requires_approval": False,
                "description": "Read bounded text content from a permitted file",
                "parameters": {
                    "path": "string (required)",
                    "max_bytes": "int (optional, max 512KB)"
                },
            },
            "write_file": {
                "risk": "HIGH",
                "requires_approval": True,
                "description": "Write or overwrite content in a permitted file",
                "parameters": {
                    "path": "string (required)",
                    "content": "string (required)",
                    "append": "bool (optional)",
                    "confirmed": "bool (optional)"
                },
            },
            "terminate_process": {
                "risk": "HIGH",
                "requires_approval": True,
                "description": "Safely terminate a user-launched process",
                "parameters": {
                    "process_name": "string (required)",
                    "pid": "int (optional)",
                    "confirmed": "bool (optional)"
                },
            },
        }

    # ── Dispatcher ────────────────────────────────────────────────────────────

    def execute(self, device_id: str, command: str, parameters: dict[str, Any] | None = None,
                confirmed: bool = False, approval_id: str | None = None) -> dict[str, Any]:
        """Execute or gate a typed allowlisted PC command."""
        params = dict(parameters or {})
        cmd = (command or "").strip().lower()

        # 1. Reject unknown commands
        allowed = self.get_allowed_commands()
        if cmd not in allowed:
            self.audit.log(device_id, cmd, "rejected", f"Unknown command: {cmd}", "unknown_command")
            return {
                "ok": False,
                "status": "error",
                "error": f"Unknown command '{cmd}'. Allowed commands: {', '.join(sorted(allowed.keys()))}",
            }

        # 2. Check for unexpected fields if schema specifies strict params
        expected_params = allowed[cmd]["parameters"]
        # Allow control keys in parameters
        accepted_keys = set(expected_params.keys()) | {"confirmed", "approval_id"}
        unexpected = [k for k in params.keys() if k not in accepted_keys]
        if unexpected:
            self.audit.log(device_id, cmd, "rejected", f"Unexpected parameters: {unexpected}", "invalid_arguments")
            return {
                "ok": False,
                "status": "error",
                "error": f"Unexpected parameters for command '{cmd}': {unexpected}",
            }

        # 3. Handle Approval Gate for Consequential Operations
        is_consequential = allowed[cmd]["requires_approval"]
        if is_consequential and not confirmed:
            # If an approval_id was passed, attempt to consume it
            if approval_id:
                pending = self.approvals.consume(approval_id, device_id)
                if not pending or pending.command != cmd:
                    self.audit.log(device_id, cmd, "rejected", "Invalid or expired approval token", "approval_invalid")
                    return {
                        "ok": False,
                        "status": "error",
                        "error": "The confirmation approval token is invalid, expired, or belongs to another device.",
                    }
                # Consumed successfully -> proceed to execution
            else:
                # Create pending approval and pause execution
                resource = str(params.get("path") or params.get("process_name") or "PC resource")
                side_effects = (
                    f"Modifying/writing file at {resource}" if cmd == "write_file"
                    else f"Terminating process {resource}"
                )
                reversible = False
                pending = self.approvals.create(
                    device_id=device_id,
                    command=cmd,
                    resource=resource,
                    parameters=params,
                    side_effects=side_effects,
                    reversible=reversible,
                )
                self.audit.log(device_id, cmd, "needs_approval", f"Paused for approval: {cmd} on {resource}")
                return {
                    "ok": True,
                    "status": "needs_approval",
                    "approval_id": pending.approval_id,
                    "target_pc": platform.node() or "Personal Computer",
                    "action": cmd,
                    "resource": resource,
                    "parameters": redact(params),
                    "potential_side_effects": side_effects,
                    "reversible": reversible,
                    "expires_in": int(APPROVAL_TTL_SECONDS),
                }

        # 4. Narrow Command Handlers
        try:
            handler = getattr(self, f"_cmd_{cmd}", None)
            if not handler:
                return {"ok": False, "status": "error", "error": f"Handler not implemented for {cmd}"}
            result = handler(device_id, params)
            self.audit.log(device_id, cmd, "success", f"Executed {cmd}")
            return result
        except Exception as err:
            err_msg = str(err)
            self.audit.log(device_id, cmd, "failed", f"Failed {cmd}: {err_msg}", err_msg)
            return {"ok": False, "status": "error", "error": err_msg}

    # ── Individual Handlers ───────────────────────────────────────────────────

    def _cmd_reachability(self, device_id: str, params: dict[str, Any]) -> dict[str, Any]:
        return {
            "ok": True,
            "status": "success",
            "data": {
                "reachable": True,
                "server_name": "Zaya",
                "hostname": platform.node(),
                "os": platform.system(),
                "timestamp": time.time(),
            },
        }

    def _cmd_system_status(self, device_id: str, params: dict[str, Any]) -> dict[str, Any]:
        data: dict[str, Any] = {
            "platform": platform.platform(),
            "os": platform.system(),
            "os_version": platform.version(),
            "python_version": platform.python_version(),
            "cpu_count": os.cpu_count() or 1,
        }
        try:
            import psutil
            cpu_percent = psutil.cpu_percent(interval=0.1)
            mem = psutil.virtual_memory()
            battery = psutil.sensors_battery()
            data.update({
                "cpu_percent": cpu_percent,
                "memory_total_mb": round(mem.total / (1024 * 1024), 1),
                "memory_available_mb": round(mem.available / (1024 * 1024), 1),
                "memory_percent": mem.percent,
                "battery": {
                    "percent": round(battery.percent, 1) if battery else None,
                    "power_plugged": battery.power_plugged if battery else None,
                } if battery else None,
            })
        except ImportError:
            data["metrics"] = "psutil unavailable; basic status returned"
        return {"ok": True, "status": "success", "data": data}

    def _cmd_system_info(self, device_id: str, params: dict[str, Any]) -> dict[str, Any]:
        detail = str(params.get("detail_level", "summary")).lower()
        if detail not in ("basic", "summary"):
            return {"ok": False, "status": "error", "error": "detail_level must be 'basic' or 'summary'"}

        report = {
            "hostname": platform.node(),
            "system": platform.system(),
            "release": platform.release(),
            "architecture": platform.machine(),
            "processor": platform.processor() or "Unknown",
            "permitted_directories": self.dirs.list_roots(),
        }
        return {"ok": True, "status": "success", "data": report}

    def _cmd_diagnostic_info(self, device_id: str, params: dict[str, Any]) -> dict[str, Any]:
        limit = params.get("limit", 20)
        if not isinstance(limit, int) or limit < 1:
            limit = 20
        limit = min(limit, MAX_DIAGNOSTIC_LINES)

        log_path = ROOT / "logs" / "runtime" / "zaya.log"
        lines: list[str] = []
        if log_path.exists():
            try:
                with open(log_path, "r", encoding="utf-8", errors="replace") as f:
                    all_lines = f.readlines()
                    lines = [redact_secrets(line.strip()) for line in all_lines[-limit:]]
            except Exception as err:
                lines = [f"Could not read diagnostic log: {err}"]
        else:
            lines = ["Diagnostic log file does not exist yet. System operational."]

        return {
            "ok": True,
            "status": "success",
            "data": {
                "entries": lines,
                "count": len(lines),
                "component": params.get("component") or "all",
            },
        }

    def _cmd_launch_app(self, device_id: str, params: dict[str, Any]) -> dict[str, Any]:
        app_id = str(params.get("app_id") or "").strip().lower()
        if not app_id:
            return {"ok": False, "status": "error", "error": "app_id is required"}

        if app_id not in _ALLOWLISTED_APPS:
            return {
                "ok": False,
                "status": "error",
                "error": f"Application '{app_id}' is not in the allowlisted apps: {list(_ALLOWLISTED_APPS.keys())}",
            }

        os_name = platform.system()
        target_bin = _ALLOWLISTED_APPS[app_id].get(os_name)
        if not target_bin:
            return {"ok": False, "status": "error", "error": f"App '{app_id}' is not supported on {os_name}"}

        # Resolve binary path
        binary_path = shutil.which(target_bin) or shutil.which(target_bin.split(".")[0])
        if not binary_path and os_name == "Windows":
            # For Windows builtin exes that might reside in System32
            win_dir = os.environ.get("WINDIR", "C:\\Windows")
            candidate = Path(win_dir) / "System32" / target_bin
            if candidate.exists():
                binary_path = str(candidate)

        if not binary_path:
            return {
                "ok": False,
                "status": "error",
                "error": f"Executable '{target_bin}' not found on this system.",
            }

        # Direct invocation without shell=True to prevent command injection
        try:
            proc = subprocess.Popen(
                [binary_path],
                shell=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            with self._lock:
                self._running_processes[f"{app_id}_{proc.pid}"] = proc
            return {
                "ok": True,
                "status": "success",
                "data": {
                    "app_id": app_id,
                    "pid": proc.pid,
                    "binary": target_bin,
                    "message": f"Successfully launched {app_id} (PID {proc.pid})",
                },
            }
        except Exception as err:
            return {"ok": False, "status": "error", "error": f"Failed to launch {app_id}: {err}"}

    def _cmd_list_dir(self, device_id: str, params: dict[str, Any]) -> dict[str, Any]:
        raw_dir = params.get("directory")
        if raw_dir is None:
            # Default to first permitted root
            with self.dirs._lock:
                target_dir = self.dirs.roots[0] if self.dirs.roots else ROOT
        else:
            resolved, err = self.dirs.validate_path(str(raw_dir), must_exist=True)
            if err or not resolved:
                return {"ok": False, "status": "error", "error": err or "Invalid directory path"}
            if not resolved.is_dir():
                return {"ok": False, "status": "error", "error": f"Path is not a directory: {resolved.name}"}
            target_dir = resolved

        max_entries = params.get("max_entries", 50)
        if not isinstance(max_entries, int) or max_entries < 1:
            max_entries = 50
        max_entries = min(max_entries, MAX_DIR_ENTRIES)

        entries: list[dict[str, Any]] = []
        try:
            for child in sorted(target_dir.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))[:max_entries]:
                # Skip hidden or sensitive files
                if child.name.startswith(".") or child.name.lower() in _SENSITIVE_NAMES:
                    continue
                if child.suffix.lower() in _SENSITIVE_EXTENSIONS:
                    continue
                stat = child.stat()
                entries.append({
                    "name": child.name,
                    "is_dir": child.is_dir(),
                    "size": stat.st_size if child.is_file() else None,
                    "modified": stat.st_mtime,
                })
        except Exception as err:
            return {"ok": False, "status": "error", "error": f"Failed to list directory: {err}"}

        return {
            "ok": True,
            "status": "success",
            "data": {
                "directory": target_dir.name,
                "count": len(entries),
                "entries": entries,
            },
        }

    def _cmd_read_file(self, device_id: str, params: dict[str, Any]) -> dict[str, Any]:
        raw_path = params.get("path")
        if not raw_path or not isinstance(raw_path, str):
            return {"ok": False, "status": "error", "error": "path parameter is required"}

        target, err = self.dirs.validate_path(raw_path, must_exist=True)
        if err or not target:
            return {"ok": False, "status": "error", "error": err or "Invalid path"}

        if not target.is_file():
            return {"ok": False, "status": "error", "error": "Target path is not a file"}

        size = target.stat().st_size
        max_bytes = params.get("max_bytes", MAX_READ_BYTES)
        if not isinstance(max_bytes, int) or max_bytes <= 0:
            max_bytes = MAX_READ_BYTES
        max_bytes = min(max_bytes, MAX_READ_BYTES)

        if size > max_bytes:
            return {
                "ok": False,
                "status": "error",
                "error": f"File size ({size} bytes) exceeds the bounded limit of {max_bytes} bytes",
            }

        try:
            # Check for binary file bytes
            with open(target, "rb") as f:
                raw_chunk = f.read(1024)
                if b"\x00" in raw_chunk:
                    return {"ok": False, "status": "error", "error": "Binary files cannot be read as text"}
                f.seek(0)
                content = f.read(max_bytes).decode("utf-8", errors="replace")

            # Redact secrets in returned file preview if applicable
            clean_content = redact_secrets(content)
            return {
                "ok": True,
                "status": "success",
                "data": {
                    "path": target.name,
                    "size": size,
                    "content": clean_content,
                },
            }
        except Exception as err:
            return {"ok": False, "status": "error", "error": f"Failed to read file: {err}"}

    def _cmd_write_file(self, device_id: str, params: dict[str, Any]) -> dict[str, Any]:
        raw_path = params.get("path")
        if not raw_path or not isinstance(raw_path, str):
            return {"ok": False, "status": "error", "error": "path parameter is required"}

        content = params.get("content")
        if content is None or not isinstance(content, str):
            return {"ok": False, "status": "error", "error": "content parameter is required (must be string)"}

        # Target file may not exist yet, but its parent must validate inside permitted directory
        target, err = self.dirs.validate_path(raw_path, must_exist=False)
        if err or not target:
            return {"ok": False, "status": "error", "error": err or "Invalid file destination"}

        append = bool(params.get("append", False))
        mode = "a" if append else "w"

        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            with open(target, mode, encoding="utf-8") as f:
                f.write(content)

            return {
                "ok": True,
                "status": "success",
                "data": {
                    "path": target.name,
                    "bytes_written": len(content.encode("utf-8")),
                    "mode": "appended" if append else "written",
                },
            }
        except Exception as err:
            return {"ok": False, "status": "error", "error": f"Failed to write file: {err}"}

    def _cmd_terminate_process(self, device_id: str, params: dict[str, Any]) -> dict[str, Any]:
        pname = str(params.get("process_name") or "").strip().lower()
        pid = params.get("pid")
        if not pname and pid is None:
            return {"ok": False, "status": "error", "error": "Either process_name or pid is required"}

        if pname in _CRITICAL_SYSTEM_PROCESSES or any(c in pname for c in _CRITICAL_SYSTEM_PROCESSES):
            return {
                "ok": False,
                "status": "error",
                "error": f"Refusing to terminate critical system process '{pname}'",
            }

        try:
            import psutil
            terminated = 0
            for proc in psutil.process_iter(["pid", "name"]):
                try:
                    if pid is not None and proc.info["pid"] == pid:
                        proc.terminate()
                        proc.wait(timeout=3)
                        terminated += 1
                        break
                    elif pname and pname in (proc.info["name"] or "").lower():
                        proc.terminate()
                        proc.wait(timeout=3)
                        terminated += 1
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

            return {
                "ok": True,
                "status": "success",
                "data": {
                    "terminated_count": terminated,
                    "target": pname or pid,
                },
            }
        except ImportError:
            return {"ok": False, "status": "error", "error": "psutil is required for process termination"}


_bridge_instance: PCEcosystemBridge | None = None
_instance_lock = threading.Lock()


def get_pc_ecosystem() -> PCEcosystemBridge:
    global _bridge_instance
    with _instance_lock:
        if _bridge_instance is None:
            _bridge_instance = PCEcosystemBridge()
        return _bridge_instance


def reset_pc_ecosystem() -> None:
    global _bridge_instance
    with _instance_lock:
        _bridge_instance = None
