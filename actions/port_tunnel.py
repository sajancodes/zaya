"""Localhost Port Tunneling Action for Zaya.
Created and developed by Sajan Rai for Zaya.

Expose local development ports to the public internet securely using quick, ephemeral tunnels.
Supports Cloudflare Tunnels (cloudflared), Bore, and LocalTunnel.
"""
from __future__ import annotations

import re
import atexit
import shutil
import subprocess
import threading
import time
from typing import Any, Dict, Optional

from core.execution_policy import require_owner
from core.tool_result import ToolResult

_active_tunnels: Dict[int, Dict[str, Any]] = {}


_tunnel_lock = threading.RLock()


def _terminate(proc):
    try:
        if proc.poll() is None:
            proc.terminate()
        proc.wait(timeout=3)
    except (OSError, subprocess.TimeoutExpired):
        try:
            proc.kill()
            proc.wait(timeout=3)
        except (OSError, subprocess.TimeoutExpired):
            pass


def start_tunnel_process(port: int, provider: str = 'cloudflared') -> Dict[str, Any]:
    if not 1 <= port <= 65535:
        return {'status': 'error', 'message': 'Port must be between 1 and 65535.'}
    with _tunnel_lock:
        existing = _active_tunnels.get(port)
        if existing and existing['proc'].poll() is None:
            return {'status': 'success', 'port': port, 'tunnel_url': existing['url'],
                    'provider': existing['provider'], 'message': f'Tunnel is running at {existing["url"]}.'}
        _active_tunnels.pop(port, None)
        selected = None
        cmd = None
        for name in ('cloudflared', 'bore', 'localtunnel'):
            if provider not in {'auto', name}:
                continue
            binary = shutil.which('npx' if name == 'localtunnel' else name)
            if not binary:
                continue
            selected = name
            cmd = ([binary, 'tunnel', '--url', f'http://localhost:{port}'] if name == 'cloudflared'
                   else [binary, 'local', str(port), '--to', 'bore.pub'] if name == 'bore'
                   else [binary, '-y', 'localtunnel', '--port', str(port)])
            break
        if cmd is None:
            return {'status': 'error', 'message': f'No installed utility for requested provider {provider}.'}
        try:
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)
        except OSError as error:
            return {'status': 'error', 'message': f'Tunnel process could not start: {error}'}
        ready = threading.Event()
        found = []

        def read_output(pipe):
            try:
                for line in pipe:
                    match = re.search(r'https://[a-zA-Z0-9-]+\.(?:trycloudflare\.com|loca\.lt)', line)
                    if match:
                        found.append(match.group(0))
                        ready.set()
                    elif selected == 'bore':
                        match = re.search(r'bore\.pub:\d+', line)
                        if match:
                            found.append('http://' + match.group(0))
                            ready.set()
            finally:
                pipe.close()
        for pipe in (proc.stdout, proc.stderr):
            threading.Thread(target=read_output, args=(pipe,), daemon=True).start()
        ready.wait(6)
        if not found or proc.poll() is not None:
            _terminate(proc)
            return {'status': 'error', 'port': port,
                    'message': 'Tunnel startup failed or no public URL was reported. No active tunnel was retained.'}
        url = found[0]
        _active_tunnels[port] = {'proc': proc, 'url': url, 'provider': selected, 'created_at': time.time()}
        return {'status': 'success', 'port': port, 'tunnel_url': url, 'provider': selected,
                'message': f'Tunnel process is running and reported {url}; public reachability was not independently tested.'}


def stop_tunnel_process(port: int) -> Dict[str, Any]:
    with _tunnel_lock:
        tunnel = _active_tunnels.pop(port, None)
        if tunnel is None:
            return {'status': 'error', 'message': f'No active tunnel on port {port}.'}
        _terminate(tunnel['proc'])
        if tunnel['proc'].poll() is None:
            _active_tunnels[port] = tunnel
            return {'status': 'error', 'message': 'Tunnel termination could not be confirmed.'}
        return {'status': 'success', 'message': f'Tunnel on port {port} stopped.'}


def stop_all_tunnels():
    for port in list(_active_tunnels):
        stop_tunnel_process(port)


atexit.register(stop_all_tunnels)


def deploy_wormhole(parameters: dict, **_kwargs) -> ToolResult:
    """Localhost Wormhole Port Tunneling Action."""
    require_owner()
    action = str(parameters.get("action") or "start").lower().strip()
    port = int(parameters.get("port") or 3000)
    provider = str(parameters.get("provider") or "auto").lower()

    if action == "start":
        res = start_tunnel_process(port, provider)
        if res.get("status") == "success":
            return ToolResult("success", res.get("message") or f"Port {port} tunnel started.", data=res)
        return ToolResult("failed", res.get("message") or "Failed to start port tunnel.", data=res)

    elif action == "stop":
        res = stop_tunnel_process(port)
        if res.get("status") == "success":
            return ToolResult("success", res.get("message") or f"Port {port} tunnel stopped.", data=res)
        return ToolResult("failed", res.get("message") or "Failed to stop port tunnel.", data=res)

    elif action in {"status", "list"}:
        tunnels = {
            p: {"url": v.get("url"), "provider": v.get("provider")}
            for p, v in list(_active_tunnels.items()) if v["proc"].poll() is None
        }
        msg = f"Active tunnels: {len(tunnels)}" if tunnels else "No active port tunnels."
        return ToolResult("success", msg, data={"active_tunnels": tunnels, "count": len(tunnels)})

    return ToolResult("failed", f"Unknown tunnel action: '{action}'.")


TOOL = {
    "name": "deploy_wormhole",
    "description": "Secure Port Tunneling: Expose local development ports (e.g. 3000, 8000) to the public internet securely using quick, ephemeral tunnels (cloudflared, bore, localtunnel).",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "enum": ["start", "stop", "status", "list"],
                "description": "Whether to start, stop, or check active port tunnels."
            },
            "port": {
                "type": "INTEGER",
                "description": "The local port number to expose (e.g. 3000, 5173, 8000)."
            },
            "provider": {
                "type": "STRING",
                "enum": ["auto", "cloudflared", "bore", "localtunnel"],
                "description": "Tunneling provider to use (default: auto)."
            }
        }
    },
    "handler": deploy_wormhole
}
