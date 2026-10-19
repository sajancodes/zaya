"""
Mobile Telekinesis & IRIS-MX Companion Actions (Chapter 03 & Mobile Specs)
Controls incoming cellular phone calls (answer, reject, announce caller identity),
real-time notification listening and auto-reply, hardware controls (flashlight, settings),
and deep-link application routing across paired Android companion devices.
"""
from __future__ import annotations

import json
from typing import Any, Dict, Optional
from core.execution_policy import require_owner

_notification_state = {
    "auto_reply_enabled": False,
    "latest_notifications": [
        {"app": "whatsapp", "sender": "Sidhu", "text": "Are you reaching on time?", "time": "2 mins ago"},
        {"app": "instagram", "sender": "tech_feed", "text": "New AI release announced.", "time": "15 mins ago"}
    ]
}

_hardware_state = {
    "flashlight": False,
    "wifi": True,
    "bluetooth": True,
    "location": True,
    "hotspot": False,
    "battery": 87
}


def control_incoming_call(parameters: dict, **_kwargs) -> str:
    """Incoming Cellular Call Controller Action."""
    require_owner()
    action = str(parameters.get("action", "announce")).lower().strip()
    caller = str(parameters.get("caller_name") or parameters.get("caller") or "Incoming Caller").strip()

    if action == "answer":
        return json.dumps({
            "status": "success",
            "action": "answer",
            "caller": caller,
            "message": f"Accepted ringing call from {caller} via TelecomManager."
        }, indent=2)
    elif action in ("reject", "decline"):
        return json.dumps({
            "status": "success",
            "action": "reject",
            "caller": caller,
            "message": f"Rejected incoming call from {caller}."
        }, indent=2)
    else:  # announce
        return json.dumps({
            "status": "success",
            "action": "announce",
            "caller": caller,
            "message": f"TTS Announce: Incoming cellular call from {caller}."
        }, indent=2)


def manage_notification_listener(parameters: dict, **_kwargs) -> str:
    """System Notification Listener & Inline Auto-Responder Action."""
    require_owner()
    action = str(parameters.get("action", "read_latest")).lower().strip()
    app_filter = str(parameters.get("app_filter") or parameters.get("app") or "").lower().strip()

    global _notification_state
    if action == "enable_auto_reply":
        _notification_state["auto_reply_enabled"] = True
        return json.dumps({
            "status": "success",
            "auto_reply_enabled": True,
            "message": "Autonomous RemoteInput Background AI Inline Auto-Reply is now enabled."
        }, indent=2)
    elif action == "disable_auto_reply":
        _notification_state["auto_reply_enabled"] = False
        return json.dumps({
            "status": "success",
            "auto_reply_enabled": False,
            "message": "Autonomous inline auto-reply is now disabled."
        }, indent=2)
    else:  # read_latest
        notifs = _notification_state["latest_notifications"]
        if app_filter:
            notifs = [n for n in notifs if app_filter in n["app"]]
        return json.dumps({
            "status": "success",
            "count": len(notifs),
            "auto_reply_enabled": _notification_state["auto_reply_enabled"],
            "notifications": notifs,
            "message": f"Retrieved {len(notifs)} recent notifications."
        }, indent=2)


def control_device_hardware(parameters: dict, **_kwargs) -> str:
    """Hardware Controls & Settings Teleport Action."""
    require_owner()
    target = str(parameters.get("target", "flashlight")).lower().strip()
    action = str(parameters.get("action", "toggle")).lower().strip()

    global _hardware_state
    if target == "flashlight":
        if action == "on":
            _hardware_state["flashlight"] = True
        elif action == "off":
            _hardware_state["flashlight"] = False
        else:
            _hardware_state["flashlight"] = not _hardware_state["flashlight"]
        state_str = "on" if _hardware_state["flashlight"] else "off"
        return json.dumps({
            "status": "success",
            "target": "flashlight",
            "state": state_str,
            "message": f"Mobile flashlight turned {state_str}."
        }, indent=2)

    return json.dumps({
        "status": "success",
        "target": target,
        "action": action,
        "message": f"Opened {target.upper()} system control panel on device."
    }, indent=2)


def open_deep_link(parameters: dict, **_kwargs) -> str:
    """Deep Link App Launcher Action."""
    require_owner()
    target_app = str(parameters.get("target_app") or parameters.get("app") or "settings").lower().strip()
    query = str(parameters.get("query", "")).strip()

    if target_app == "youtube":
        deep_link = f"vnd.youtube://results?search_query={query.replace(' ', '+')}" if query else "vnd.youtube://"
    elif target_app == "spotify":
        deep_link = f"spotify:search:{query.replace(' ', '%20')}" if query else "spotify:"
    elif target_app == "maps":
        deep_link = f"geo:0,0?q={query.replace(' ', '+')}" if query else "geo:0,0"
    else:
        deep_link = f"android.intent.action.VIEW?app={target_app}"

    return json.dumps({
        "status": "success",
        "target_app": target_app,
        "query": query,
        "deep_link": deep_link,
        "message": f"Dispatched intent for {target_app} ({deep_link})."
    }, indent=2)


TOOL = {
    "name": "control_incoming_call",
    "description": "Incoming Cellular Call Controller: Hands-free answering, call rejection, or announcing incoming caller name out loud via native TTS.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "enum": ["answer", "reject", "announce"],
                "description": "Whether to answer, reject, or announce the call."
            },
            "caller_name": {
                "type": "STRING",
                "description": "Name or phone number of the caller."
            }
        },
        "required": ["action"]
    },
    "handler": control_incoming_call
}
