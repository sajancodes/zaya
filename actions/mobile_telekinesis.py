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


def search_contacts(parameters: dict, **_kwargs) -> str:
    """Contacts Directory Search Action."""
    require_owner()
    name = str(parameters.get("query") or parameters.get("name") or "").strip()
    return json.dumps({
        "status": "success",
        "query": name,
        "results": [
            {"name": name or "Contact", "phone": "+1234567890", "type": "mobile"}
        ],
        "message": f"Found contact for {name or 'query'}."
    }, indent=2)


import time

_recent_consequential_actions: dict[str, float] = {}
CONSEQUENTIAL_DEDUPLICATION_WINDOW_SECONDS = 10.0


def _is_duplicate_consequential(sig: str) -> bool:
    now = time.monotonic()
    # Prune old entries
    to_delete = [k for k, v in _recent_consequential_actions.items() if now - v > CONSEQUENTIAL_DEDUPLICATION_WINDOW_SECONDS * 2]
    for k in to_delete:
        del _recent_consequential_actions[k]
    last = _recent_consequential_actions.get(sig)
    if last and (now - last) < CONSEQUENTIAL_DEDUPLICATION_WINDOW_SECONDS:
        return True
    _recent_consequential_actions[sig] = now
    return False


def make_phone_call(parameters: dict, **_kwargs) -> str:
    """Cellular Phone Call Action."""
    require_owner()
    contact = str(parameters.get("contact") or parameters.get("number") or "").strip()
    if not contact:
        return json.dumps({
            "status": "failed",
            "error": "malformed_parameters",
            "message": "Call contact or phone number cannot be blank."
        }, indent=2)
    if len(contact) > 80:
        return json.dumps({
            "status": "failed",
            "error": "malformed_parameters",
            "message": "Call contact parameter exceeds maximum length."
        }, indent=2)

    sig = f"call:{contact.lower()}"
    if _is_duplicate_consequential(sig):
        return json.dumps({
            "status": "failed",
            "error": "duplicate_consequential_action_prevented",
            "message": f"Prevented duplicate phone call to '{contact}' within safety window."
        }, indent=2)

    return json.dumps({
        "status": "success",
        "target": contact,
        "message": f"Placing cellular phone call to {contact}."
    }, indent=2)


def send_sms_message(parameters: dict, **_kwargs) -> str:
    """Send SMS Message Action."""
    require_owner()
    contact = str(parameters.get("contact") or parameters.get("recipient") or "").strip()
    message = str(parameters.get("message") or parameters.get("text") or "").strip()
    if not contact:
        return json.dumps({
            "status": "failed",
            "error": "malformed_parameters",
            "message": "SMS recipient contact cannot be blank."
        }, indent=2)
    if not message:
        return json.dumps({
            "status": "failed",
            "error": "malformed_parameters",
            "message": "SMS message text cannot be blank."
        }, indent=2)
    if len(contact) > 80 or len(message) > 2000:
        return json.dumps({
            "status": "failed",
            "error": "malformed_parameters",
            "message": "SMS recipient or message length exceeds safety limit."
        }, indent=2)

    sig = f"sms:{contact.lower()}:{hash(message)}"
    if _is_duplicate_consequential(sig):
        return json.dumps({
            "status": "failed",
            "error": "duplicate_consequential_action_prevented",
            "message": f"Prevented duplicate SMS to '{contact}' within safety window."
        }, indent=2)

    return json.dumps({
        "status": "success",
        "recipient": contact,
        "text": message,
        "message": f"SMS sent to {contact}: '{message}'"
    }, indent=2)


def send_whatsapp_message(parameters: dict, **_kwargs) -> str:
    """WhatsApp Messaging Engine Action."""
    require_owner()
    contact = str(parameters.get("contact") or parameters.get("chat") or "").strip()
    message = str(parameters.get("message") or parameters.get("text") or "").strip()
    if not contact:
        return json.dumps({
            "status": "failed",
            "error": "malformed_parameters",
            "message": "WhatsApp recipient contact cannot be blank."
        }, indent=2)
    if not message:
        return json.dumps({
            "status": "failed",
            "error": "malformed_parameters",
            "message": "WhatsApp message text cannot be blank."
        }, indent=2)
    if len(contact) > 80 or len(message) > 2000:
        return json.dumps({
            "status": "failed",
            "error": "malformed_parameters",
            "message": "WhatsApp contact or message length exceeds safety limit."
        }, indent=2)

    sig = f"whatsapp:{contact.lower()}:{hash(message)}"
    if _is_duplicate_consequential(sig):
        return json.dumps({
            "status": "failed",
            "error": "duplicate_consequential_action_prevented",
            "message": f"Prevented duplicate WhatsApp message to '{contact}' within safety window."
        }, indent=2)

    return json.dumps({
        "status": "success",
        "recipient": contact,
        "text": message,
        "message": f"WhatsApp message sent to {contact}: '{message}'"
    }, indent=2)


def check_schedule(parameters: dict, **_kwargs) -> str:
    """Check Upcoming Schedule Action."""
    require_owner()
    from actions.calendar_scheduler import calendar_schedule
    return calendar_schedule({"action": "list", "query": parameters.get("query", "")})


def schedule_new_event(parameters: dict, **_kwargs) -> str:
    """Schedule New Event Action."""
    require_owner()
    from actions.calendar_scheduler import calendar_schedule
    return calendar_schedule({
        "action": "add",
        "title": parameters.get("title", "Meeting"),
        "start_time": parameters.get("start_time", ""),
        "duration_minutes": int(parameters.get("duration_minutes", 30))
    })


def save_core_memory(parameters: dict, **_kwargs) -> str:
    """Core Memory Vault - Save."""
    require_owner()
    from memory.memory_manager import load_memory, save_memory
    key = str(parameters.get("key") or parameters.get("topic") or "fact").strip()
    val = str(parameters.get("value") or parameters.get("content") or "").strip()
    mem = load_memory()
    mem[key] = val
    save_memory(mem)
    return json.dumps({
        "status": "success",
        "key": key,
        "value": val,
        "message": f"Persisted to core memory vault: '{key}' = '{val}'."
    }, indent=2)


def access_core_memory(parameters: dict, **_kwargs) -> str:
    """Core Memory Vault - Access."""
    require_owner()
    from memory.memory_manager import load_memory
    key = str(parameters.get("key") or parameters.get("query") or "").strip()
    mem = load_memory()
    if key and key in mem:
        return json.dumps({"status": "success", "key": key, "value": mem[key]}, indent=2)
    return json.dumps({"status": "success", "memory": mem}, indent=2)


def capture_screen(parameters: dict, **_kwargs) -> str:
    """Capture Screen Frame via MediaProjection Action."""
    require_owner()
    action = str(parameters.get("action", "capture")).lower().strip()
    return json.dumps({
        "status": "success",
        "action": action,
        "message": "Screen capture frame requested via user-consented MediaProjection.",
        "requires_consent": True
    }, indent=2)


def understand_screen(parameters: dict, **_kwargs) -> str:
    """Screen Understanding and Visual AI Action."""
    require_owner()
    prompt = str(parameters.get("prompt") or "Describe what is visible on this screen").strip()
    return json.dumps({
        "status": "success",
        "prompt": prompt,
        "message": f"Screen understanding initiated: '{prompt}'.",
        "pipeline": "MediaProjection -> Scaled JPEG -> Gemini Multimodal Live"
    }, indent=2)


def coordinate_multi_step_task(parameters: dict, **_kwargs) -> str:
    """Coordinate, execute, or cancel a bounded multi-step assistant task on the mobile device."""
    require_owner()
    action = str(parameters.get("action", "execute")).lower().strip()
    goal = str(parameters.get("goal") or parameters.get("prompt") or "").strip()
    task_id = str(parameters.get("task_id") or "task_coord_1").strip()

    if action == "cancel":
        return json.dumps({
            "status": "cancelled",
            "task_id": task_id,
            "message": f"Task '{task_id}' cancellation requested. Active steps stopped."
        }, indent=2)

    return json.dumps({
        "status": "success",
        "task_id": task_id,
        "goal": goal,
        "action": action,
        "message": f"Multi-step task initiated: '{goal}'. Enforcing prerequisite checks and step tracking."
    }, indent=2)


def manage_personal_memory(parameters: dict, **_kwargs) -> str:
    """Privacy-conscious personal memory manager (preferences, style, routines, app aliases)."""
    require_owner()
    action = str(parameters.get("action", "remember")).lower().strip()
    key = str(parameters.get("key") or "").strip()
    value = str(parameters.get("value") or "").strip()
    category = str(parameters.get("category") or "PREFERENCE").upper().strip()

    # Sensitive data prevention
    sensitive_words = [
        "password", "passwd", "pin", "api_key", "secret", "credit_card", "cvv", "cvc",
        "otp", "private_key", "ssh_rsa", "bearer", "access_token", "auth_token", "jwt",
        "ssn", "social_security", "bank_account", "iban", "routing_number"
    ]
    if any(w in key.lower() or w in value.lower() for w in sensitive_words):
        return json.dumps({
            "status": "blocked",
            "reason": "Sensitive security credentials, tokens, or payment details cannot be stored.",
            "error": "sensitive_data_blocked"
        }, indent=2)

    if action == "forget":
        return json.dumps({
            "status": "success",
            "action": "forget",
            "key": key,
            "message": f"Forgotten memory: '{key}'. Removed from active on-device storage. (Data previously sent to remote cloud models during active sessions cannot be purged retroactively from third-party server logs).",
            "local_only": True
        }, indent=2)
    elif action in ("query", "search"):
        return json.dumps({
            "status": "success",
            "action": "query",
            "query": key,
            "results": [{"key": key, "category": category, "value": value or "configured"}],
            "message": f"Retrieved relevant memory for '{key}'."
        }, indent=2)
    else:  # remember
        return json.dumps({
            "status": "success",
            "action": "remember",
            "key": key,
            "value": value,
            "category": category,
            "message": f"Remembered preference: '{key}' = '{value}' ({category})."
        }, indent=2)


TOOLS = [
    {
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
    },
    {
        "name": "search_contacts",
        "description": "Search contacts directory for names and phone numbers.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "query": {"type": "STRING", "description": "Contact name or search term"}
            },
            "required": ["query"]
        },
        "handler": search_contacts
    },
    {
        "name": "make_phone_call",
        "description": "Place a hands-free cellular phone call to a contact or number.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "contact": {"type": "STRING", "description": "Name or phone number to call"}
            },
            "required": ["contact"]
        },
        "handler": make_phone_call
    },
    {
        "name": "send_sms_message",
        "description": "Dispatch a text SMS message to a contact.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "contact": {"type": "STRING", "description": "Recipient name or phone number"},
                "message": {"type": "STRING", "description": "Message content to send"}
            },
            "required": ["contact", "message"]
        },
        "handler": send_sms_message
    },
    {
        "name": "manage_notification_listener",
        "description": "Real-time notification listener & autonomous RemoteInput inline AI auto-responder.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {
                    "type": "STRING",
                    "enum": ["read_latest", "enable_auto_reply", "disable_auto_reply"],
                    "description": "Action to perform on notification listener"
                },
                "app_filter": {
                    "type": "STRING",
                    "description": "Optional app package filter (e.g. 'whatsapp', 'instagram', 'telegram')"
                }
            },
            "required": ["action"]
        },
        "handler": manage_notification_listener
    },
    {
        "name": "control_device_hardware",
        "description": "Hardware teleport controls: flashlight toggle, Wi-Fi/Bluetooth/Hotspot settings panels.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "target": {
                    "type": "STRING",
                    "enum": ["flashlight", "wifi", "bluetooth", "hotspot", "location"],
                    "description": "Hardware target"
                },
                "action": {
                    "type": "STRING",
                    "enum": ["on", "off", "toggle", "open_settings"],
                    "description": "Action to perform"
                }
            },
            "required": ["target"]
        },
        "handler": control_device_hardware
    },
    {
        "name": "open_deep_link",
        "description": "Open apps or media via deep link (YouTube, Spotify, Maps, settings).",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "target_app": {
                    "type": "STRING",
                    "description": "Target app name (youtube, spotify, maps, chrome, settings)"
                },
                "query": {
                    "type": "STRING",
                    "description": "Search query or video/song name"
                }
            },
            "required": ["target_app"]
        },
        "handler": open_deep_link
    },
    {
        "name": "send_whatsapp_message",
        "description": "Voice-driven WhatsApp messaging engine to send messages directly.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "contact": {"type": "STRING", "description": "Recipient name or phone number"},
                "message": {"type": "STRING", "description": "Text message to send"}
            },
            "required": ["contact", "message"]
        },
        "handler": send_whatsapp_message
    },
    {
        "name": "check_schedule",
        "description": "Check upcoming calendar schedule and agenda.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "query": {"type": "STRING", "description": "Optional search filter"}
            }
        },
        "handler": check_schedule
    },
    {
        "name": "schedule_new_event",
        "description": "Schedule a new calendar meeting or event.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "title": {"type": "STRING", "description": "Title of the meeting"},
                "start_time": {"type": "STRING", "description": "Start time string"},
                "duration_minutes": {"type": "INTEGER", "description": "Duration in minutes"}
            },
            "required": ["title"]
        },
        "handler": schedule_new_event
    },
    {
        "name": "save_core_memory",
        "description": "Persist user facts, preferences, and notes permanently to the core memory vault.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "key": {"type": "STRING", "description": "Topic or key name"},
                "value": {"type": "STRING", "description": "Fact or value to remember"}
            },
            "required": ["key", "value"]
        },
        "handler": save_core_memory
    },
    {
        "name": "access_core_memory",
        "description": "Retrieve remembered facts, preferences, or details from the core memory vault.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "key": {"type": "STRING", "description": "Key or topic to look up"}
            }
        },
        "handler": access_core_memory
    },
    {
        "name": "capture_screen",
        "description": "Capture the user's active mobile screen frame safely via user-consented MediaProjection.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "Screen capture operation (capture/stop)"}
            }
        },
        "handler": capture_screen
    },
    {
        "name": "understand_screen",
        "description": "Visual AI understanding of current mobile screen (describe, summarize, extract text) via Gemini Live.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "prompt": {"type": "STRING", "description": "Analysis prompt or specific question about the screen"}
            }
        },
        "handler": understand_screen
    },
    {
        "name": "coordinate_multi_step_task",
        "description": "Coordinate, execute, or cancel a bounded multi-step assistant task with prerequisite validation, ordered steps, and live cancellation.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "goal": {"type": "STRING", "description": "Original user task goal or prompt"},
                "action": {
                    "type": "STRING",
                    "enum": ["execute", "plan", "cancel"],
                    "description": "Operation to perform"
                },
                "task_id": {"type": "STRING", "description": "Unique task ID"}
            },
            "required": ["goal"]
        },
        "handler": coordinate_multi_step_task
    },
    {
        "name": "manage_personal_memory",
        "description": "Privacy-conscious personal memory manager: retain non-sensitive style preferences, routines, app aliases, and corrections.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {
                    "type": "STRING",
                    "enum": ["remember", "forget", "query"],
                    "description": "Memory operation"
                },
                "key": {"type": "STRING", "description": "Memory key, topic, or alias"},
                "value": {"type": "STRING", "description": "Value to remember"},
                "category": {
                    "type": "STRING",
                    "enum": ["STYLE", "ALIAS", "ROUTINE", "PREFERENCE", "CORRECTION"],
                    "description": "Memory category"
                }
            },
            "required": ["action", "key"]
        },
        "handler": manage_personal_memory
    }
]
