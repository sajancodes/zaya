"""Developer Port & Service Inspector Engine.
Created and developed by Sajan Rai for Zaya.

Inspects active TCP/UDP ports, identifies processes holding specific ports,
benchmarks common development ports (3000, 5173, 8000, etc.), and safely frees
occupied ports to resolve EADDRINUSE conflicts without risking critical OS processes.
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional, Set
import psutil

from core.execution_policy import require_owner

COMMON_DEV_PORTS = [3000, 3001, 4000, 5000, 5173, 8000, 8080, 8888, 9000, 5432, 3306, 27017, 6379]

# System services that must never be terminated by port freeing
_PROTECTED_PROCESS_NAMES: Set[str] = {
    "system", "system idle process", "smss.exe", "csrss.exe", "wininit.exe",
    "services.exe", "lsass.exe", "svchost.exe", "fontdrvhost.exe",
    "winlogon.exe", "dwm.exe", "explorer.exe",
}


def _get_process_details(pid: Optional[int]) -> Dict[str, Any]:
    """Retrieve process name, memory, and path safely."""
    if not pid or pid <= 4:
        return {"name": "System" if pid == 4 else "Unknown", "path": "", "memory_mb": 0.0}
    try:
        p = psutil.Process(pid)
        mem_mb = round(p.memory_info().rss / (1024 * 1024), 1)
        try:
            exe_path = p.exe()
        except (psutil.AccessDenied, psutil.NoSuchProcess):
            exe_path = ""
        return {"name": p.name(), "path": exe_path, "memory_mb": mem_mb}
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return {"name": "Unknown", "path": "", "memory_mb": 0.0}


def _inspect_port(port: int, kind: str = "tcp") -> Dict[str, Any]:
    """Find any connection or listener binding to target port."""
    matches = []
    try:
        conns = psutil.net_connections(kind=kind)
        for c in conns:
            if c.laddr and c.laddr.port == port:
                proc = _get_process_details(c.pid)
                matches.append({
                    "port": port,
                    "protocol": kind.upper(),
                    "status": c.status,
                    "local_address": f"{c.laddr.ip}:{c.laddr.port}",
                    "pid": c.pid,
                    "process_name": proc["name"],
                    "path": proc["path"],
                    "memory_mb": proc["memory_mb"],
                })
    except Exception as e:
        return {"occupied": False, "port": port, "error": str(e), "matches": []}

    occupied = len(matches) > 0
    return {
        "port": port,
        "occupied": occupied,
        "count": len(matches),
        "matches": matches,
    }


def _list_listening_ports(limit: int = 25) -> List[Dict[str, Any]]:
    """List all currently listening TCP ports."""
    results = []
    seen_ports = set()
    try:
        conns = psutil.net_connections(kind="tcp")
        for c in conns:
            if c.status == psutil.CONN_LISTEN and c.laddr:
                port = c.laddr.port
                if port not in seen_ports:
                    seen_ports.add(port)
                    proc = _get_process_details(c.pid)
                    results.append({
                        "port": port,
                        "local_address": f"{c.laddr.ip}:{c.laddr.port}",
                        "pid": c.pid,
                        "process_name": proc["name"],
                        "memory_mb": proc["memory_mb"],
                    })
    except Exception:
        pass

    results.sort(key=lambda x: x["port"])
    return results[:limit]


def _scan_dev_ports() -> Dict[str, Any]:
    """Scan popular development ports and categorize as occupied or free."""
    occupied = []
    free = []

    try:
        conns = psutil.net_connections(kind="tcp")
        active_ports = {c.laddr.port: c.pid for c in conns if c.laddr and c.status == psutil.CONN_LISTEN}

        for port in COMMON_DEV_PORTS:
            if port in active_ports:
                pid = active_ports[port]
                proc = _get_process_details(pid)
                occupied.append({
                    "port": port,
                    "pid": pid,
                    "process_name": proc["name"],
                })
            else:
                free.append(port)
    except Exception:
        pass

    return {
        "occupied": occupied,
        "free": free,
        "total_scanned": len(COMMON_DEV_PORTS),
    }


def _free_port(port: int, force: bool = False) -> Dict[str, Any]:
    """Safely terminate the process binding to a specific port."""
    current_pid = os.getpid()
    inspection = _inspect_port(port)

    if not inspection.get("occupied") or not inspection.get("matches"):
        return {"status": "success", "summary": f"Port {port} is already free and unoccupied."}

    terminated = []
    blocked = []

    for match in inspection["matches"]:
        pid = match.get("pid")
        if not pid:
            continue
        if pid == current_pid:
            blocked.append(f"PID {pid} (Zaya assistant process)")
            continue
        if pid <= 4:
            blocked.append(f"PID {pid} (Critical OS System process)")
            continue

        try:
            p = psutil.Process(pid)
            name = p.name().lower()
            if name in _PROTECTED_PROCESS_NAMES:
                blocked.append(f"{p.name()} (PID {pid} is a protected system service)")
                continue

            if force:
                p.kill()
            else:
                p.terminate()
            terminated.append(f"{p.name()} (PID {pid})")
        except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
            blocked.append(f"PID {pid}: {e}")

    if not terminated and blocked:
        return {
            "status": "error",
            "message": f"Cannot free port {port}: " + "; ".join(blocked),
        }

    summary = f"Port {port} freed. Terminated: " + ", ".join(terminated)
    if blocked:
        summary += f" (Blocked: {', '.join(blocked)})"

    return {
        "status": "success",
        "summary": summary,
        "terminated": terminated,
        "blocked": blocked,
    }


def port_sentinel(parameters: dict, **_kwargs) -> str:
    """Dispatches port inspection, dev port scanning, and port freeing."""
    require_owner()
    action = str(parameters.get("action") or "inspect").lower().strip()
    port = parameters.get("port")
    if port is not None:
        port = int(port)

    # 1. Inspect Single Port
    if action in ("inspect", "check", "query"):
        if port is None:
            return json.dumps({"status": "error", "message": "Must provide 'port' number to inspect."}, indent=2)
        res = _inspect_port(port)
        if res.get("occupied"):
            m = res["matches"][0]
            summary = f"Port {port} is OCCUPIED by '{m['process_name']}' (PID {m['pid']}, status {m['status']}, {m['memory_mb']} MB RAM)."
        else:
            summary = f"Port {port} is FREE and available for binding."
        return json.dumps({"status": "success", "summary": summary, "data": res}, indent=2)

    # 2. List All Listening Ports
    if action in ("list", "listening"):
        limit = max(1, min(int(parameters.get("limit") or 25), 100))
        ports = _list_listening_ports(limit)
        summary = f"Found {len(ports)} active listening TCP port(s)."
        return json.dumps({"status": "success", "summary": summary, "data": ports}, indent=2)

    # 3. Scan Common Dev Ports
    if action in ("dev_ports", "scan_dev", "common"):
        dev = _scan_dev_ports()
        occ_str = ", ".join(f"{p['port']} ({p['process_name']})" for p in dev["occupied"]) if dev["occupied"] else "None"
        summary = f"Dev Ports: {len(dev['occupied'])} occupied ({occ_str}), {len(dev['free'])} free."
        return json.dumps({"status": "success", "summary": summary, "data": dev}, indent=2)

    # 4. Free Port
    if action in ("free", "kill", "release", "free_port"):
        if port is None:
            return json.dumps({"status": "error", "message": "Must provide 'port' number to free."}, indent=2)
        force = bool(parameters.get("force"))
        res = _free_port(port, force=force)
        return json.dumps(res, indent=2)

    return json.dumps({
        "status": "error",
        "message": f"Unknown action '{action}'. Choose from: inspect, list, dev_ports, free_port."
    }, indent=2)


TOOL = {
    "name": "port_sentinel",
    "description": "Inspect active network ports, identify processes binding to specific ports, scan popular development ports (3000, 5173, 8000), and safely free occupied ports with protected system guardrails.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "enum": ["inspect", "list", "dev_ports", "free_port"],
                "description": "Port management action (default: 'inspect').",
            },
            "port": {
                "type": "INTEGER",
                "description": "Port number to inspect or free (e.g. 3000, 8000, 5173).",
            },
            "limit": {
                "type": "INTEGER",
                "description": "Maximum number of listening ports to list (default: 25).",
            },
            "force": {
                "type": "BOOLEAN",
                "description": "Whether to force-kill process on the port.",
            },
        },
    },
    "handler": port_sentinel,
}
