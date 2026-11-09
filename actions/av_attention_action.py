"""Multi-Modal Audio/Visual Fusion Attention Gate Action (Cycle 80).
Created and developed by Sajan Rai for Zaya.
"""
from __future__ import annotations

import json
from typing import Any, Dict, Optional

from core.av_attention_fusion import get_av_attention_gate


def handle_av_attention(
    action: str = "status",
    urgency: str = "normal",
    face_detected: Optional[bool] = None,
    gaze_at_screen: Optional[bool] = None,
    voice_detected: Optional[bool] = None,
    head_yaw_deg: float = 0.0,
    head_pitch_deg: float = 0.0,
) -> str:
    """Inspect or update owner attention and multimodal cognitive engagement state."""
    gate = get_av_attention_gate()

    if action == "status":
        state = gate.evaluate_attention()
        history = gate.get_recent_history(limit=5)
        return json.dumps({
            "status": "success",
            "current_state": state.to_dict(),
            "history_count": len(history),
            "recent_history": history,
        })

    elif action == "evaluate":
        state = gate.evaluate_attention()
        return json.dumps({
            "status": "success",
            "evaluated_state": state.to_dict(),
        })

    elif action == "should_speak":
        allowed = gate.should_speak(urgency=urgency)
        return json.dumps({
            "status": "success",
            "urgency": urgency,
            "should_speak": allowed,
        })

    elif action == "record_cue":
        updated_cues = []
        if face_detected is not None or gaze_at_screen is not None:
            v_cue = gate.update_visual(
                face_detected=bool(face_detected),
                gaze_at_screen=bool(gaze_at_screen),
                head_yaw_deg=head_yaw_deg,
                head_pitch_deg=head_pitch_deg,
            )
            updated_cues.append("visual")

        if voice_detected is not None:
            a_cue = gate.update_acoustic(
                voice_detected=bool(voice_detected),
                is_speech_directed=True,
            )
            updated_cues.append("acoustic")

        state = gate.evaluate_attention()
        return json.dumps({
            "status": "success",
            "updated_cues": updated_cues,
            "resulting_state": state.to_dict(),
        })

    return f"Unknown av_attention action: '{action}'."


TOOL = {
    "name": "av_attention_gate",
    "description": (
        "Inspect and control the Multi-Modal Audio/Visual Fusion Attention Gate. "
        "Fuses face gaze, speech activity, and keyboard/mouse interaction to decide "
        "whether to speak aloud, show subtle visual cards, or withhold interruptions."
    ),
    "handler": handle_av_attention,
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "enum": ["status", "evaluate", "should_speak", "record_cue"],
                "description": "Action to perform on the attention gate.",
            },
            "urgency": {
                "type": "STRING",
                "enum": ["normal", "low", "urgent", "alarm"],
                "description": "Urgency category when querying should_speak.",
            },
            "face_detected": {
                "type": "BOOLEAN",
                "description": "Whether the owner's face is detected by the visual sensor.",
            },
            "gaze_at_screen": {
                "type": "BOOLEAN",
                "description": "Whether the owner is looking directly at the primary monitor.",
            },
            "voice_detected": {
                "type": "BOOLEAN",
                "description": "Whether vocal acoustics are currently active.",
            },
            "head_yaw_deg": {
                "type": "NUMBER",
                "description": "Head yaw angle in degrees (-90 to +90).",
            },
            "head_pitch_deg": {
                "type": "NUMBER",
                "description": "Head pitch angle in degrees (-90 to +90).",
            },
        },
        "required": ["action"],
    },
}
