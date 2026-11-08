"""Voiceprint Biometric Guard Action for Zaya.
Created and developed by Sajan Rai.

Guards voice-command authorization by verifying acoustic features (pitch, spectral centroid,
zero crossing rate) against the enrolled owner voiceprint.
"""
from __future__ import annotations

import base64
from typing import Any

from core.execution_policy import require_owner
from core.tool_result import ToolResult
from core.voice_biometrics import get_voiceprint_manager


def voiceprint_guard(parameters: dict[str, Any], **_kwargs) -> ToolResult:
    """Manage or verify speaker voiceprint biometric profiles."""
    require_owner()
    action = str(parameters.get("action", "status")).lower().strip()
    mgr = get_voiceprint_manager()

    if action == "status":
        info = mgr.status()
        summary = (
            f"Voiceprint guard status: {'Enrolled (' + str(info['samples_count']) + ' samples)' if info['enrolled'] else 'Not enrolled (permissive mode)'}."
        )
        return ToolResult("success", summary, info)

    elif action == "enroll":
        audio_b64 = str(parameters.get("audio_b64", "")).strip()
        if not audio_b64:
            return ToolResult("failed", "Parameter 'audio_b64' (base64 encoded 16-bit PCM) is required for enrollment.", {})

        try:
            pcm_bytes = base64.b64decode(audio_b64)
        except Exception as exc:
            return ToolResult("failed", f"Failed to decode base64 audio: {exc}", {})

        sample_rate = int(parameters.get("sample_rate", 16000))
        success, msg = mgr.enroll(pcm_bytes, sample_rate=sample_rate)
        if success:
            return ToolResult("success", msg, mgr.status(), side_effect=True)
        return ToolResult("failed", msg, {})

    elif action == "verify":
        audio_b64 = str(parameters.get("audio_b64", "")).strip()
        if not audio_b64:
            return ToolResult("failed", "Parameter 'audio_b64' is required for verification.", {})

        try:
            pcm_bytes = base64.b64decode(audio_b64)
        except Exception as exc:
            return ToolResult("failed", f"Failed to decode base64 audio: {exc}", {})

        sample_rate = int(parameters.get("sample_rate", 16000))
        threshold = float(parameters.get("threshold", 0.55))

        res = mgr.verify(pcm_bytes, sample_rate=sample_rate, threshold=threshold)
        summary = (
            f"Voiceprint verification: {'MATCH' if res.match else 'MISMATCH'} "
            f"(confidence: {res.confidence * 100:.1f}%, distance: {res.distance})."
        )
        evidence = [{"source": "voiceprint_biometrics", "match": res.match, "distance": res.distance}]
        return ToolResult("success" if res.match else "failed", summary, res.__dict__, evidence=evidence)

    elif action == "reset":
        mgr.reset()
        return ToolResult("success", "Owner voiceprint profile has been reset.", mgr.status(), side_effect=True)

    return ToolResult("failed", f"Unknown action '{action}'. Valid actions are 'status', 'enroll', 'verify', 'reset'.", {})


TOOL = {
    "name": "voiceprint_guard",
    "description": (
        "Inspect, enroll, verify, or reset speaker voiceprint biometric profiles. "
        "Extracts acoustic pitch, spectral centroid, and zero-crossing rate to verify owner identity."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "enum": ["status", "enroll", "verify", "reset"],
                "description": "Action to perform: 'status' (default), 'enroll', 'verify', or 'reset'.",
            },
            "audio_b64": {
                "type": "STRING",
                "description": "Base64-encoded raw 16-bit mono PCM audio bytes.",
            },
            "sample_rate": {
                "type": "INTEGER",
                "description": "Audio sample rate in Hz (default: 16000).",
            },
            "threshold": {
                "type": "NUMBER",
                "description": "Distance threshold for speaker match (default: 0.55).",
            },
        },
        "required": [],
    },
    "handler": voiceprint_guard,
}
