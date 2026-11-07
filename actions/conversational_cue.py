"""Conversational Cue and Custom Trigger Action.

Allows Zaya and the owner to arm instant reactive triggers (e.g. 'when I say mark',
'when I hum', 'on my mark, play Parvati', 'when I say anything').
"""
from __future__ import annotations

from typing import Any, Dict
from core.cue_manager import cue_manager


def register_cue(parameters: Dict[str, Any], **_kwargs) -> str:
    """Action handler to arm a conversational cue/trigger."""
    trigger_type = str(parameters.get("trigger_type", "any_input")).lower().strip()
    tool_name = str(parameters.get("tool_name", "video_player")).strip()
    raw_params = parameters.get("parameters", {})
    trigger_phrase = str(parameters.get("trigger_phrase", "")).strip()
    ack_phrase = str(parameters.get("ack_phrase", "Standing by, sir. Ready on your mark.")).strip()
    single_shot = bool(parameters.get("single_shot", True))

    cue = cue_manager.arm_cue(
        trigger_type=trigger_type,
        tool_name=tool_name,
        parameters=raw_params,
        trigger_phrase=trigger_phrase,
        single_shot=single_shot,
        ack_phrase=ack_phrase,
    )
    return f"status=armed cue_id={cue.id} trigger_type={trigger_type} tool={tool_name}"


TOOL = {
    "name": "register_cue",
    "description": (
        "Arms an instant conversational cue or custom trigger. Use whenever the user asks Zaya "
        "to wait for a cue, signal, phrase, humming, or any spoken sound before performing an action "
        "(e.g. 'when I say anything play...', 'on my mark', 'when I hum...'). "
        "When the cue fires, Zaya executes the bound tool immediately with zero refusal."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "trigger_type": {
                "type": "STRING",
                "enum": ["any_input", "phrase", "sound"],
                "description": "'any_input' to fire on the user's next words/sound, 'phrase' for a specific phrase, 'sound' on audio detection.",
            },
            "trigger_phrase": {
                "type": "STRING",
                "description": "Specific trigger word or phrase if trigger_type is 'phrase'.",
            },
            "tool_name": {
                "type": "STRING",
                "description": "Tool to invoke when triggered (e.g. 'video_player', 'media_controller').",
            },
            "parameters": {
                "type": "OBJECT",
                "description": "Arguments for the tool (e.g. {'action': 'play', 'source': 'Parvati', 'target': 'display'}).",
            },
            "ack_phrase": {
                "type": "STRING",
                "description": "Optional short confirmation phrase, e.g. 'Standing by, sir. Ready on your mark.'",
            },
            "single_shot": {
                "type": "BOOLEAN",
                "description": "True to fire once and disarm (default: True).",
            },
        },
        "required": ["trigger_type", "tool_name", "parameters"],
    },
    "handler": register_cue,
}
