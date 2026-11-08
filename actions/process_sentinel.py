"""Process Resource Sentinel & Unresponsive Window Detector.
Created and developed by Sajan Rai for Zaya.

Monitors real-time CPU and memory hogs, detects hung/frozen application windows
via Win32 APIs, identifies resource anomalies, and provides safe guarded process
termination preventing accidental termination of critical OS infrastructure.
"""
from __future__ import annotations

import ctypes
import json
import os
from typing import Any, Dict, List, Optional, Set
import psutil

from core.execution_policy import require_owner

# Critical system processes that must never be terminated by user-space actions
_CRITICAL_SYSTEM_PROCESSES: Set[str] = {
    "system", "system idle process", "smss.exe", "csrss.exe", "wininit.exe",
    "services.exe", "lsass.exe", "svchost.exe", "fontdrvhost.exe",
    "winlogon.exe", "dwm.exe", "registry", "memory compression", "explorer.exe",
}


def _get_top_cpu(limit: int = 5) -> List[Dict[str, Any]]:
    """Return top processes ranked by CPU usage."""
    # First pass primes the cpu_percent counters in psutil
    procs = []
    for p in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]):
        try:
            info = p.info
            if info["name"] and info["name"].lower() not in ("system idle process",):
                procs.append({
                    "pid": info["pid"],
                    "name": info["name"],
                    "cpu_percent": round(info["cpu_percent"] or 0.0, 1),
                    "memory_percent": round(info["memory_percent"] or 0.0, 1),
                })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    procs.sort(key=lambda x: x["cpu_percent"], reverse=True)
    return procs[:limit]


def _get_top_memory(limit: int = 5) -> List[Dict[str, Any]]:
    """Return top processes ranked by Resident Set Size (RSS) memory."""
    procs = []
    for p in psutil.process_iter(["pid", "name", "memory_info", "memory_percent"]):
        try:
            info = p.info
            mem_info = info.get("memory_info")
            if info["name"] and mem_info:
                rss_mb = round(mem_info.rss / (1024 * 1024), 1)
                procs.append({
                    "pid": info["pid"],
                    "name": info["name"],
                    "memory_mb": rss_mb,
                    "memory_percent": round(info.get("memory_percent") or 0.0, 1),
                })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    procs.sort(key=lambda x: x["memory_mb"], reverse=True)
    return procs[:limit]


def _detect_hung_windows() -> List[Dict[str, Any]]:
    """Scan visible top-level windows for hung/frozen GUI threads."""
    hung_windows: List[Dict[str, Any]] = []
    if os.name != "nt":
        return hung_windows

    try:
        user32 = ctypes.windll.user32
        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

        def enum_cb(hwnd, _lparam):
            if user32.IsWindowVisible(hwnd) and user32.IsHungAppWindow(hwnd):
                length = user32.GetWindowTextLengthW(hwnd)
                buf = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buf, length + 1)
                title = buf.value.strip()

                pid = ctypes.c_ulong()
                user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                proc_pid = pid.value
                proc_name = "Unknown"
                try:
                    p = psutil.Process(proc_pid)
                    proc_name = p.name()
                except Exception:
                    pass

                hung_windows.append({
                    "hwnd": int(hwnd),
                    "title": title or "Untitled Window",
                    "pid": proc_pid,
                    "process_name": proc_name,
                })
            return True

        user32.EnumWindows(WNDENUMPROC(enum_cb), 0)
    except Exception:
        pass

    return hung_windows


def _find_anomalies(cpu_threshold: float = 70.0, mem_mb_threshold: float = 2048.0) -> List[Dict[str, Any]]:
    """Identify processes consuming unusually excessive resources."""
    anomalies = []
    for p in psutil.process_iter(["pid", "name", "cpu_percent", "memory_info", "num_threads"]):
        try:
            info = p.info
            name = (info.get("name") or "").lower()
            if name in ("system idle process",):
                continue

            cpu = info.get("cpu_percent") or 0.0
            mem_info = info.get("memory_info")
            rss_mb = round(mem_info.rss / (1024 * 1024), 1) if mem_info else 0.0
            threads = info.get("num_threads") or 0

            reasons = []
            if cpu >= cpu_threshold:
                reasons.append(f"High CPU: {round(cpu, 1)}% >= {cpu_threshold}%")
            if rss_mb >= mem_mb_threshold:
                reasons.append(f"High RAM: {rss_mb} MB >= {mem_mb_threshold} MB")

            if reasons:
                anomalies.append({
                    "pid": info["pid"],
                    "name": info["name"],
                    "cpu_percent": round(cpu, 1),
                    "memory_mb": rss_mb,
                    "threads": threads,
                    "reasons": reasons,
                })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    return anomalies


def _terminate_process_safe(pid: Optional[int] = None, name: Optional[str] = None, force: bool = False) -> Dict[str, Any]:
    """Safely terminate a process, blocking critical system targets and Zaya itself."""
    current_pid = os.getpid()

    target_procs: List[psutil.Process] = []
    if pid is not None:
        if pid == current_pid:
            return {"status": "error", "message": "Cannot terminate current Zaya process."}
        try:
            target_procs.append(psutil.Process(pid))
        except psutil.NoSuchProcess:
            return {"status": "error", "message": f"Process with PID {pid} not found."}
    elif name:
        clean_name = name.lower().strip()
        for p in psutil.process_iter(["pid", "name"]):
            try:
                if p.info["name"] and p.info["name"].lower() == clean_name:
                    if p.info["pid"] != current_pid:
                        target_procs.append(p)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        if not target_procs:
            return {"status": "error", "message": f"No active process matching '{name}' found."}
    else:
        return {"status": "error", "message": "Must provide 'pid' or 'name' to terminate."}

    terminated = []
    blocked = []
    for p in target_procs:
        p_name = p.name().lower()
        if p_name in _CRITICAL_SYSTEM_PROCESSES or p.pid <= 4:
            blocked.append(f"{p.name()} (PID {p.pid} is a protected system process)")
            continue

        try:
            if force:
                p.kill()
            else:
                p.terminate()
            terminated.append(f"{p.name()} (PID {p.pid})")
        except Exception as e:
            blocked.append(f"{p.name()} (PID {p.pid}: {e})")

    if not terminated and blocked:
        return {
            "status": "error",
            "message": "Operation blocked: " + "; ".join(blocked)
        }

    return {
        "status": "success",
        "terminated": terminated,
        "blocked": blocked,
        "summary": f"Terminated {len(terminated)} process(es)." + (f" Blocked {len(blocked)} protected process(es)." if blocked else ""),
    }


def process_sentinel(parameters: dict, **_kwargs) -> str:
    """Dispatches process monitoring, anomaly detection, and safe termination."""
    require_owner()
    action = str(parameters.get("action") or "summary").lower().strip()
    limit = max(1, min(int(parameters.get("limit") or 5), 20))

    # 1. Top CPU
    if action in ("top_cpu", "cpu"):
        top = _get_top_cpu(limit)
        summary = "Top CPU consumers: " + ", ".join(f"{p['name']} ({p['cpu_percent']}%)" for p in top)
        return json.dumps({"status": "success", "summary": summary, "data": top}, indent=2)

    # 2. Top Memory
    if action in ("top_memory", "memory", "ram"):
        top = _get_top_memory(limit)
        summary = "Top Memory consumers: " + ", ".join(f"{p['name']} ({p['memory_mb']} MB)" for p in top)
        return json.dumps({"status": "success", "summary": summary, "data": top}, indent=2)

    # 3. Not Responding / Hung Windows
    if action in ("not_responding", "hung", "frozen"):
        hung = _detect_hung_windows()
        if hung:
            summary = f"Detected {len(hung)} unresponsive/hung window(s): " + ", ".join(f"'{w['title']}' ({w['process_name']})" for w in hung)
        else:
            summary = "No frozen or unresponsive application windows detected. All GUI threads responding normally."
        return json.dumps({"status": "success", "summary": summary, "data": hung}, indent=2)

    # 4. Resource Anomalies
    if action in ("anomalies", "rogue", "bottleneck"):
        cpu_t = float(parameters.get("cpu_threshold") or 70.0)
        mem_t = float(parameters.get("memory_mb_threshold") or 2048.0)
        anomalies = _find_anomalies(cpu_t, mem_t)
        if anomalies:
            summary = f"Detected {len(anomalies)} resource anomaly/hogs: " + ", ".join(f"{a['name']} ({', '.join(a['reasons'])})" for a in anomalies)
        else:
            summary = f"No resource anomalies detected (thresholds: CPU > {cpu_t}%, RAM > {mem_t} MB)."
        return json.dumps({"status": "success", "summary": summary, "data": anomalies}, indent=2)

    # 5. Safe Terminate
    if action in ("kill", "terminate", "kill_safe"):
        pid = parameters.get("pid")
        if pid is not None:
            pid = int(pid)
        name = parameters.get("name") or parameters.get("process_name")
        force = bool(parameters.get("force"))
        res = _terminate_process_safe(pid=pid, name=name, force=force)
        return json.dumps(res, indent=2)

    # 6. Overall System Summary
    if action == "summary":
        top_cpu = _get_top_cpu(3)
        top_mem = _get_top_memory(3)
        hung = _detect_hung_windows()
        anomalies = _find_anomalies(75.0, 3072.0)

        hung_str = f"{len(hung)} hung window(s)" if hung else "0 hung windows"
        anom_str = f"{len(anomalies)} anomaly/hogs" if anomalies else "0 anomalies"
        top_cpu_str = f"{top_cpu[0]['name']} ({top_cpu[0]['cpu_percent']}%)" if top_cpu else "None"
        top_mem_str = f"{top_mem[0]['name']} ({top_mem[0]['memory_mb']} MB)" if top_mem else "None"
        summary = (
            f"Process Sentinel: {hung_str}, {anom_str}. "
            f"Top CPU: {top_cpu_str}. Top RAM: {top_mem_str}."
        )
        return json.dumps({
            "status": "success",
            "summary": summary,
            "data": {
                "top_cpu": top_cpu,
                "top_memory": top_mem,
                "hung_windows": hung,
                "anomalies": anomalies,
            }
        }, indent=2)

    return json.dumps({
        "status": "error",
        "message": f"Unknown action '{action}'. Choose from: summary, top_cpu, top_memory, not_responding, anomalies, kill_safe."
    }, indent=2)


TOOL = {
    "name": "process_sentinel",
    "description": "Inspect CPU/memory hogging processes, detect hung or frozen application windows, identify resource anomalies, and safely terminate rogue processes with system protection guards.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "enum": ["summary", "top_cpu", "top_memory", "not_responding", "anomalies", "kill_safe"],
                "description": "Operation to perform (default: 'summary').",
            },
            "limit": {
                "type": "INTEGER",
                "description": "Number of top processes to return (default: 5).",
            },
            "pid": {
                "type": "INTEGER",
                "description": "Process ID to terminate safely.",
            },
            "name": {
                "type": "STRING",
                "description": "Process name to terminate safely.",
            },
            "cpu_threshold": {
                "type": "NUMBER",
                "description": "CPU percentage threshold for anomaly detection (default: 70.0).",
            },
            "memory_mb_threshold": {
                "type": "NUMBER",
                "description": "Memory MB threshold for anomaly detection (default: 2048.0).",
            },
            "force": {
                "type": "BOOLEAN",
                "description": "Whether to force kill (SIGKILL) instead of graceful termination.",
            },
        },
    },
    "handler": process_sentinel,
}
