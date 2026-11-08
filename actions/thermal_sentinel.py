"""Hardware Thermal, GPU Sensor & CPU Frequency Sentinel.
Created and developed by Sajan Rai for Zaya.

Inspects hardware thermals, dedicated GPU sensors (NVIDIA temperature, VRAM usage,
power draw, utilization), and CPU clock frequency scaling across hardware cores.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from typing import Any, Dict, List, Optional

import psutil

from core.execution_policy import require_owner


def _query_nvidia_smi() -> Dict[str, Any]:
    """Query dedicated NVIDIA GPU sensors via nvidia-smi CLI."""
    nvsmi = shutil.which("nvidia-smi")
    if not nvsmi:
        return {
            "available": False,
            "message": "nvidia-smi not found (integrated GPU or non-NVIDIA hardware).",
        }

    cmd = [
        nvsmi,
        "--query-gpu=name,temperature.gpu,utilization.gpu,utilization.memory,memory.total,memory.free,memory.used,power.draw",
        "--format=csv,noheader,nounits",
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=2.5)
        if proc.returncode != 0 or not proc.stdout.strip():
            return {"available": False, "message": "nvidia-smi query returned no data."}

        # Parse CSV line: e.g. "NVIDIA GeForce RTX 4050 Laptop GPU, 39, 0, 0, 6141, 3949, 1972, 11.85"
        parts = [p.strip() for p in proc.stdout.splitlines()[0].split(",")]
        if len(parts) >= 8:
            name = parts[0]
            temp_c = int(parts[1]) if parts[1].isdigit() else 0
            gpu_util = int(parts[2]) if parts[2].isdigit() else 0
            mem_util = int(parts[3]) if parts[3].isdigit() else 0
            mem_total = int(parts[4]) if parts[4].isdigit() else 0
            mem_free = int(parts[5]) if parts[5].isdigit() else 0
            mem_used = int(parts[6]) if parts[6].isdigit() else 0
            try:
                power_w = round(float(parts[7]), 2)
            except ValueError:
                power_w = 0.0

            # Thermal rating
            if temp_c < 50:
                condition = "Cool"
            elif temp_c < 70:
                condition = "Normal"
            elif temp_c < 82:
                condition = "Warm"
            else:
                condition = "Hot / Thermal Throttling"

            return {
                "available": True,
                "name": name,
                "temperature_c": temp_c,
                "condition": condition,
                "gpu_utilization_percent": gpu_util,
                "memory_utilization_percent": mem_util,
                "vram_total_mb": mem_total,
                "vram_used_mb": mem_used,
                "vram_free_mb": mem_free,
                "power_draw_w": power_w,
            }
    except Exception as e:
        return {"available": False, "message": f"Error querying nvidia-smi: {e}"}

    return {"available": False, "message": "Failed to parse GPU metrics."}


def _query_cpu_telemetry() -> Dict[str, Any]:
    """Inspect CPU clock speeds, scaling frequencies, and logical core loads."""
    freq = psutil.cpu_freq()
    curr_mhz = round(freq.current) if freq else 0
    max_mhz = round(freq.max) if freq and freq.max else 0
    min_mhz = round(freq.min) if freq and freq.min else 0

    per_cpu = psutil.cpu_percent(interval=0.1, percpu=True)
    avg_load = round(sum(per_cpu) / len(per_cpu), 1) if per_cpu else 0.0

    return {
        "current_frequency_mhz": curr_mhz,
        "max_frequency_mhz": max_mhz,
        "min_frequency_mhz": min_mhz,
        "physical_cores": psutil.cpu_count(logical=False) or 1,
        "logical_cores": psutil.cpu_count(logical=True) or 1,
        "average_load_percent": avg_load,
        "per_core_load_percent": per_cpu,
    }


def thermal_sentinel(parameters: dict, **_kwargs) -> str:
    """Dispatches Thermal, GPU Sensor and CPU Frequency actions."""
    require_owner()
    action = str(parameters.get("action") or "summary").lower().strip()

    # 1. Hardware Sensor Summary
    if action in ("summary", "status", "temperature", "thermals"):
        gpu = _query_nvidia_smi()
        cpu = _query_cpu_telemetry()

        if gpu.get("available"):
            gpu_str = (
                f"GPU: {gpu['name']} running {gpu['condition']} at {gpu['temperature_c']}°C "
                f"(Power: {gpu['power_draw_w']}W, VRAM: {gpu['vram_used_mb']:,}MB / {gpu['vram_total_mb']:,}MB, Util: {gpu['gpu_utilization_percent']}%)."
            )
        else:
            gpu_str = "GPU: Integrated / Non-NVIDIA display."

        cpu_ghz = round(cpu["current_frequency_mhz"] / 1000.0, 2)
        cpu_str = f"CPU: {cpu_ghz} GHz across {cpu['logical_cores']} threads ({cpu['average_load_percent']}% load)."

        summary = f"Hardware Thermals: {gpu_str} {cpu_str}"
        return json.dumps({
            "status": "success",
            "summary": summary,
            "gpu": gpu,
            "cpu": cpu,
        }, indent=2)

    # 2. Dedicated GPU Deep Telemetry
    if action in ("gpu", "nvidia", "vram"):
        gpu = _query_nvidia_smi()
        if not gpu.get("available"):
            summary = gpu.get("message", "Dedicated GPU is unavailable.")
        else:
            summary = (
                f"NVIDIA GPU: {gpu['name']} is at {gpu['temperature_c']}°C ({gpu['condition']}). "
                f"VRAM: {gpu['vram_used_mb']:,}MB used of {gpu['vram_total_mb']:,}MB. Power: {gpu['power_draw_w']}W."
            )
        return json.dumps({"status": "success", "summary": summary, "data": gpu}, indent=2)

    # 3. CPU Core Scaling & Frequencies
    if action in ("cpu", "cores", "frequency"):
        cpu = _query_cpu_telemetry()
        cpu_ghz = round(cpu["current_frequency_mhz"] / 1000.0, 2)
        summary = (
            f"CPU Topology: {cpu['physical_cores']} physical cores, {cpu['logical_cores']} logical threads. "
            f"Current clock: {cpu_ghz} GHz (Avg load: {cpu['average_load_percent']}%)."
        )
        return json.dumps({"status": "success", "summary": summary, "data": cpu}, indent=2)

    return json.dumps({
        "status": "error",
        "message": f"Unknown action '{action}'. Choose from: summary, gpu, cpu."
    }, indent=2)


TOOL = {
    "name": "thermal_sentinel",
    "description": "Inspect hardware thermal sensors, dedicated NVIDIA GPU temperature, VRAM usage, power wattage, and CPU clock frequencies across processor cores.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "enum": ["summary", "gpu", "cpu"],
                "description": "Hardware sensor operation to execute (default: 'summary').",
            },
        },
    },
    "handler": thermal_sentinel,
}
