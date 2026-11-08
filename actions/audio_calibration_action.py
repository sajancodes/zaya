"""Voice Acoustic Calibration Action for Zaya.
Created and developed by Sajan Rai.

Inspects ambient room noise floor, speech SNR, turn-around latencies,
and dynamically tunes speech silence cutoff thresholds.
"""
from __future__ import annotations

import base64
from dataclasses import asdict
from typing import Any

from core.execution_policy import require_owner
from core.tool_result import ToolResult
from core.voice_calibration import get_voice_calibration_engine


def voice_calibration(parameters: dict[str, Any], **_kwargs) -> ToolResult:
    """Inspect or tune voice acoustic calibration parameters."""
    require_owner()
    action = str(parameters.get("action", "status")).lower().strip()
    engine = get_voice_calibration_engine()

    if action == "status":
        prof = engine.get_profile()
        summary = (
            f"Acoustic calibration: Noise floor {prof.noise_floor_db} dBFS, "
            f"Speech SNR {prof.speech_snr_db} dB, Cadence: {prof.speech_cadence.upper()} "
            f"(Silence cutoff: {prof.recommended_silence_sec}s, Avg turnaround: {prof.avg_turnaround_ms}ms)."
        )
        evidence = [{"source": "voice_calibration", "snr": prof.speech_snr_db, "silence_cutoff": prof.recommended_silence_sec}]
        return ToolResult("success", summary, asdict(prof), evidence=evidence)

    elif action == "feed_ambient":
        audio_b64 = str(parameters.get("audio_b64", "")).strip()
        if not audio_b64:
            return ToolResult("failed", "Parameter 'audio_b64' is required to feed ambient sample.", {})
        try:
            pcm = base64.b64decode(audio_b64)
        except Exception as exc:
            return ToolResult("failed", f"Failed to decode base64 audio: {exc}", {})

        prof = engine.feed_ambient_sample(pcm)
        summary = f"Calibrated noise floor: {prof.noise_floor_db} dBFS."
        return ToolResult("success", summary, asdict(prof))

    elif action == "record_turn":
        latency_ms = float(parameters.get("turnaround_ms", 300.0))
        pause_sec = float(parameters.get("pause_sec", 0.35))
        audio_b64 = str(parameters.get("audio_b64", "")).strip()
        pcm = base64.b64decode(audio_b64) if audio_b64 else b"\x00" * 3200

        prof = engine.record_turn_metrics(
            speech_pcm_bytes=pcm,
            turnaround_latency_ms=latency_ms,
            inter_phrase_pause_sec=pause_sec,
        )
        summary = f"Turn recorded: cadence={prof.speech_cadence}, recommended_silence={prof.recommended_silence_sec}s."
        return ToolResult("success", summary, asdict(prof))

    return ToolResult("failed", f"Unknown action '{action}'. Valid actions are 'status', 'feed_ambient', 'record_turn'.", {})


TOOL = {
    "name": "voice_calibration",
    "description": (
        "Inspect ambient room noise floor in dBFS, speech SNR, turn-around latency, "
        "and dynamically tuned silence cutoff thresholds for speech detection."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "enum": ["status", "feed_ambient", "record_turn"],
                "description": "Action to perform: 'status' (default), 'feed_ambient', 'record_turn'.",
            },
            "audio_b64": {
                "type": "STRING",
                "description": "Base64 encoded 16-bit mono PCM audio chunk.",
            },
            "turnaround_ms": {
                "type": "NUMBER",
                "description": "Measured voice turn-around latency in milliseconds.",
            },
            "pause_sec": {
                "type": "NUMBER",
                "description": "Average inter-phrase pause duration in seconds.",
            },
        },
        "required": [],
    },
    "handler": voice_calibration,
}
