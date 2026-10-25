"""Unified Android Companion & Mobile Awareness Engine for Zaya.
Created and developed by Sajan Rai for Zaya.

Provides comprehensive phone control and remote awareness for paired Android devices:
- Hardware Telekinesis (flashlight, volume, Wi-Fi/Bluetooth/Hotspot panels, battery status)
- App Launching & Deep Links (YouTube, Spotify, Maps, Settings, custom packages)
- Media Playback Controls (play, pause, toggle, next, previous)
- Cellular Call Management (initiate call, answer, reject, caller announcement)
- Contacts Directory Lookup
- SMS Messaging (compose, dispatch)
- Real-time Notification Listening, Summarization, and Autonomous RemoteInput Inline Replies
- Unified Mobile Awareness (cross-device briefing combining phone, notifications, SMS, WhatsApp)
- Real Multimodal Phone Screen Vision (captures frame via MediaProjection consent and routes to LLM vision provider)
"""
from __future__ import annotations

import base64
import json
import logging
import threading
import time
from typing import Any, Dict, List, Optional

from core.event_bus import bus
from core.execution_policy import require_owner
from core.llm.router import LLMRouter
from core.llm.types import ImagePart, LLMMessage
from core.mobile_bridge import get_bridge
from core.tool_result import ToolResult

logger = logging.getLogger("actions.mobile_device")

# Thread-safe rolling cache of mobile events received over bridge/bus
_EVENTS_LOCK = threading.Lock()
_RECENT_NOTIFICATIONS: List[Dict[str, Any]] = []
_RECENT_CALLS: List[Dict[str, Any]] = []
_LATEST_HARDWARE: Dict[str, Any] = {}


def _on_phone_notification(data: dict) -> None:
    with _EVENTS_LOCK:
        _RECENT_NOTIFICATIONS.insert(0, {
            "app": data.get("app") or data.get("package") or "unknown",
            "sender": data.get("sender") or "",
            "text": data.get("text") or "",
            "package": data.get("package") or "",
            "timestamp": data.get("timestamp") or time.time(),
        })
        if len(_RECENT_NOTIFICATIONS) > 100:
            _RECENT_NOTIFICATIONS.pop()


def _on_phone_call(data: dict) -> None:
    with _EVENTS_LOCK:
        _RECENT_CALLS.insert(0, {
            "event": data.get("type") or "call.incoming",
            "caller_name": data.get("caller_name") or "",
            "caller_number": data.get("caller_number") or "",
            "call_id": data.get("call_id") or "",
            "timestamp": data.get("timestamp") or time.time(),
        })
        if len(_RECENT_CALLS) > 50:
            _RECENT_CALLS.pop()


def _on_phone_hardware(data: dict) -> None:
    with _EVENTS_LOCK:
        if "battery" in data:
            _LATEST_HARDWARE["battery"] = data["battery"]
        if "target" in data and "state" in data:
            _LATEST_HARDWARE[data["target"]] = data["state"]


# Subscribe to bus topics
try:
    bus.subscribe("phone_notification", _on_phone_notification)
    bus.subscribe("phone_call", _on_phone_call)
    bus.subscribe("phone_hardware", _on_phone_hardware)
except Exception as _sub_err:
    logger.debug("Failed to bind event bus subscriptions: %s", _sub_err)


def _dispatch(bridge, parameters: dict, action: str, arguments: dict) -> dict:
    result = bridge.dispatch_phone_action(action, arguments,
        device_id=str(parameters.get('device_id') or '').strip())
    if result.get('status') != 'success' and not result.get('error'):
        result['error'] = result.get('spoken_message') or 'No phone action success was confirmed.'
    return result


# ── Action Handlers ──────────────────────────────────────────────────────────

def control_device_hardware(parameters: dict, **_kwargs) -> ToolResult:
    """Controls phone hardware: flashlight, media volume, and settings panels."""
    require_owner()
    target = str(parameters.get("target") or "flashlight").lower().strip()
    action = str(parameters.get("action") or "toggle").lower().strip()
    percent = parameters.get("percent")

    bridge = get_bridge()
    if not bridge.phone_connected():
        return ToolResult("failed", "No companion phone connected. No phone hardware was changed.")

    if target == "flashlight":
        enabled = action == "on" or (action == "toggle" and not _LATEST_HARDWARE.get("flashlight", False))
        res = _dispatch(bridge, parameters,"set_flashlight", {"enabled": enabled})
        if res.get("status") == "success":
            with _EVENTS_LOCK:
                _LATEST_HARDWARE["flashlight"] = enabled
            return ToolResult("success", f"Mobile flashlight turned {'on' if enabled else 'off'}.", data=res)
        return ToolResult("failed", res.get("error") or "Failed to set flashlight.", data=res)

    elif target == "volume":
        val = int(percent) if percent is not None else 50
        res = _dispatch(bridge, parameters,"set_volume", {"percent": max(0, min(100, val))})
        if res.get("status") == "success":
            return ToolResult("success", f"Phone media volume adjusted to {val}%.", data=res)
        return ToolResult("failed", res.get("error") or "Failed to adjust phone volume.", data=res)

    elif target in {"wifi", "bluetooth", "hotspot", "location", "settings"}:
        res = _dispatch(bridge, parameters,"open_settings", {"setting": target})
        if res.get("status") == "success":
            return ToolResult("success", f"Opened {target.upper()} settings panel on phone.", data=res)
        return ToolResult("failed", res.get("error") or f"Failed to open {target} settings.", data=res)

    return ToolResult("failed", f"Unsupported hardware target: '{target}'.")


def open_phone_app(parameters: dict, **_kwargs) -> ToolResult:
    """Launches an application or deep link on the connected Android companion."""
    require_owner()
    target_app = str(parameters.get("target_app") or parameters.get("app") or "").strip()
    query = str(parameters.get("query") or "").strip()

    if not target_app:
        return ToolResult("failed", "Must specify target_app to launch (e.g. 'youtube', 'spotify', 'maps', 'settings').")

    bridge = get_bridge()
    if not bridge.phone_connected():
        return ToolResult("failed", "No companion phone connected. Open Zaya Companion to launch apps.")

    res = _dispatch(bridge, parameters,"launch_app", {"name": target_app, "query": query})
    if res.get("status") == "success":
        msg = f"Launched '{target_app}' on phone" + (f" with query '{query}'." if query else ".")
        return ToolResult("success", msg, data=res)
    return ToolResult("failed", res.get("error") or f"Could not launch '{target_app}'.", data=res)


def control_phone_media(parameters: dict, **_kwargs) -> ToolResult:
    """Controls media playback on the connected phone."""
    require_owner()
    action = str(parameters.get("action") or "toggle").lower().strip()

    bridge = get_bridge()
    if not bridge.phone_connected():
        return ToolResult("failed", "No companion phone connected.")

    if action == "status":
        res = _dispatch(bridge, parameters,"get_media_status", {})
    else:
        res = _dispatch(bridge, parameters,"control_media", {"action": action})

    if res.get("status") == "success":
        return ToolResult("success", f"Phone media command '{action}' executed.", data=res)
    return ToolResult("failed", res.get("error") or f"Media command '{action}' failed.", data=res)


def search_phone_contacts(parameters: dict, **_kwargs) -> ToolResult:
    """Searches phone contacts directory for names and phone numbers."""
    require_owner()
    query = str(parameters.get("query") or "").strip()
    if not query:
        return ToolResult("failed", "Search query cannot be empty.")

    bridge = get_bridge()
    if not bridge.phone_connected():
        return ToolResult("failed", "No companion phone connected.")

    res = _dispatch(bridge, parameters,"lookup_contact", {"query": query})
    if res.get("status") == "success":
        contacts = res.get("contacts") or res.get("result") or []
        count = len(contacts) if isinstance(contacts, list) else 1
        return ToolResult("success", f"Found {count} matching contact(s) for '{query}'.", data=res)
    return ToolResult("failed", res.get("error") or f"Contact search failed for '{query}'.", data=res)


def make_phone_call(parameters: dict, **_kwargs) -> ToolResult:
    """Initiates a cellular phone call to a contact or phone number."""
    require_owner()
    contact = str(parameters.get("contact") or parameters.get("number") or "").strip()
    if not contact:
        return ToolResult("failed", "Must specify contact name or phone number.")

    bridge = get_bridge()
    if not bridge.phone_connected():
        return ToolResult("failed", "No companion phone connected.")

    app = str(parameters.get('app') or 'phone').strip().lower()
    if app not in {'phone', 'whatsapp'}:
        return ToolResult('failed', 'Choose phone or whatsapp for the call.')
    res = _dispatch(bridge, parameters,"initiate_call", {"query": contact, "app": app})
    if res.get("status") == "success":
        return ToolResult("success", res.get("spoken_message") or f"Opened the dialer for {contact}.", data=res)
    return ToolResult("failed", res.get("error") or f"Failed to place call to {contact}.", data=res)


def browse_phone_media(parameters: dict, **_kwargs) -> ToolResult:
    """Search or open shared phone media, subject to Android permissions."""
    require_owner()
    kind = str(parameters.get('kind') or 'photos').strip().lower()
    if kind not in {'photos', 'videos', 'audio'}:
        return ToolResult('failed', 'Choose photos, videos or audio.')
    res = _dispatch(get_bridge(), parameters, 'browse_media', {
        'kind': kind, 'query': str(parameters.get('query') or '')[:120],
        'uri': str(parameters.get('uri') or '')[:500], 'limit': 10})
    return ToolResult('success' if res.get('status') == 'success' else 'failed',
                      res.get('spoken_message') or res.get('error') or 'Phone media lookup failed.', data=res)


def control_incoming_call(parameters: dict, **_kwargs) -> ToolResult:
    """Controls incoming cellular calls: answer, reject, or announce caller out loud."""
    require_owner()
    action = str(parameters.get("action") or "announce").lower().strip()
    caller = str(parameters.get("caller_name") or parameters.get("caller") or "Incoming Caller").strip()

    bridge = get_bridge()
    if not bridge.phone_connected():
        return ToolResult("failed", "No companion phone connected; no cellular call was changed.")

    if action == "answer":
        res = _dispatch(bridge, parameters,"answer_call", {})
    elif action in {"reject", "decline"}:
        res = _dispatch(bridge, parameters,"reject_call", {})
    else:  # announce
        res = _dispatch(bridge, parameters,"set_caller_announcement", {"enabled": True, "caller": caller})

    if res.get("status") == "success":
        return ToolResult("success", f"Call action '{action}' completed for {caller}.", data=res)
    return ToolResult("failed", res.get("error") or f"Call action '{action}' failed.", data=res)


def send_sms_message(parameters: dict, **_kwargs) -> ToolResult:
    """Sends a text SMS message through the connected Android phone."""
    require_owner()
    contact = str(parameters.get("contact") or parameters.get("recipient") or "").strip()
    message = str(parameters.get("message") or parameters.get("text") or "").strip()

    if not contact or not message:
        return ToolResult("failed", "Both contact/recipient and message body are required.")

    bridge = get_bridge()
    if not bridge.phone_connected():
        return ToolResult("failed", "No companion phone connected to send SMS.")

    res = _dispatch(bridge, parameters,"compose_sms", {"recipient": contact, "message": message})
    if res.get("status") == "success":
        return ToolResult("success", res.get("spoken_message") or "SMS composer opened; sending is not confirmed.", data=res)
    return ToolResult("failed", res.get("error") or f"Failed to send SMS to {contact}.", data=res)


def manage_phone_notifications(parameters: dict, **_kwargs) -> ToolResult:
    """Reads, groups, summarizes, or replies to Android notifications."""
    require_owner()
    action = str(parameters.get("action") or "read_latest").lower().strip()
    app_filter = str(parameters.get("app_filter") or parameters.get("package") or "").lower().strip()
    reply_text = str(parameters.get("reply_text") or "").strip()
    key = str(parameters.get("key") or "").strip()

    bridge = get_bridge()
    if bridge.phone_connected():
        if action == "reply" and reply_text:
            res = _dispatch(bridge, parameters,"reply_notification", {"notification_key": key, "text": reply_text})
            if res.get("status") == "success":
                return ToolResult("success", f"Sent inline reply: \"{reply_text}\"", data=res)
            return ToolResult("failed", res.get("error") or "Failed to send inline notification reply.", data=res)

        elif action == "summarize":
            res = _dispatch(bridge, parameters,"summarize_notifications", {"package_filter": app_filter})
            if res.get("status") == "success":
                return ToolResult("success", res.get("summary") or "Notification summary retrieved.", data=res)

        elif action == "read_latest":
            res = _dispatch(bridge, parameters,"read_latest_notification", {"package_filter": app_filter})
            if res.get("status") == "success":
                item = res.get("notification") or res.get("result") or {}
                desc = f"Latest from {item.get('sender', 'Unknown')} ({item.get('app', 'app')}): \"{item.get('text', '')}\""
                return ToolResult("success", desc, data=res)

        else:  # read_all / read_notifications
            res = _dispatch(bridge, parameters,"read_notifications", {"package_filter": app_filter, "limit": 20})
            if res.get("status") == "success":
                items = res.get("notifications") or res.get("result") or []
                return ToolResult("success", f"Retrieved {len(items)} notification(s).", data=res)

    # Fallback to local cached events
    with _EVENTS_LOCK:
        notifs = list(_RECENT_NOTIFICATIONS)
        if app_filter:
            notifs = [n for n in notifs if app_filter in n["app"].lower() or app_filter in n["package"].lower()]

    if not notifs:
        return ToolResult("success", "No active notifications found.", data={"notifications": []})

    if action == "read_latest":
        latest = notifs[0]
        desc = f"Latest notification from {latest['sender'] or 'Unknown'} ({latest['app']}): \"{latest['text']}\""
        return ToolResult("success", desc, data={"notification": latest})

    return ToolResult("success", f"Retrieved {len(notifs)} notification(s).", data={"notifications": notifs[:15]})


def get_phone_awareness_summary(parameters: dict, **_kwargs) -> ToolResult:
    """Unified cross-device awareness: brings together notifications, calls, WhatsApp, and tasks."""
    require_owner()

    with _EVENTS_LOCK:
        recent_notifs = list(_RECENT_NOTIFICATIONS[:10])
        recent_calls = list(_RECENT_CALLS[:5])
        hardware = dict(_LATEST_HARDWARE)

    # Check WhatsApp unread/recent if available
    whatsapp_summary = "status unavailable"
    try:
        from services.whatsapp.service import get_service
        wa = get_service().query("unread", limit=5)
        if wa and wa.status == 'success' and isinstance(wa.data, dict):
            records = wa.data.get('records')
            if isinstance(records, list):
                whatsapp_summary = f"{len(records)} unread WhatsApp chat(s) in the current local view (up to 5 shown)"
    except Exception:
        pass

    # Connected status
    bridge = get_bridge()
    connected = bridge.phone_connected()

    lines = [
        f"**Companion Phone Status**: {'Connected' if connected else 'Offline'}",
        f"- Last reported battery: {str(hardware['battery']) + '%' if 'battery' in hardware else 'Unknown'}",
        f"- Last reported flashlight: {('On' if hardware['flashlight'] else 'Off') if 'flashlight' in hardware else 'Unknown'}",
        f"- Recent Calls: {len(recent_calls)} logged",
        f"- Recent Notifications: {len(recent_notifs)} recorded",
        f"- WhatsApp: {whatsapp_summary}",
    ]

    if recent_calls:
        latest_call = recent_calls[0]
        lines.append(f"  * Last call: {latest_call.get('event')} from {latest_call.get('caller_name') or latest_call.get('caller_number', 'unknown')}")

    if recent_notifs:
        latest_n = recent_notifs[0]
        lines.append(f"  * Last alert: [{latest_n.get('app')}] {latest_n.get('sender')}: {latest_n.get('text')}")

    briefing = "\n".join(lines)
    return ToolResult("success", briefing, data={
        "connected": connected,
        "hardware": hardware,
        "recent_calls": recent_calls,
        "recent_notifications": recent_notifs,
    })


def capture_phone_screen(parameters: dict, **_kwargs) -> ToolResult:
    """Captures the active phone screen frame safely via user-consented MediaProjection."""
    require_owner()
    prompt = str(parameters.get("prompt") or "").strip()

    bridge = get_bridge()
    if not bridge.phone_connected():
        return ToolResult("failed", "No companion phone connected. MediaProjection requires active connection.")

    res = bridge.dispatch_screen_capture(prompt=prompt, timeout_sec=120.0, device_id=str(parameters.get('device_id') or ''))
    if res.get("status") == "success" or "jpeg" in res:
        width = res.get("width", 1080)
        height = res.get("height", 2400)
        return ToolResult("success", f"Screen frame captured successfully ({width}x{height}).",
                          data={"width": width, "height": height, "has_jpeg": bool(res.get("jpeg"))})
    return ToolResult("failed", res.get("error") or "Screen capture failed or was denied on device.", data=res)


def understand_phone_screen(parameters: dict, **_kwargs) -> ToolResult:
    """Genuine Multimodal Screen Understanding Engine.

    Requests a frame from the companion phone via MediaProjection consent,
    receives the real JPEG frame, routes it to the LLM vision router,
    and returns genuine AI multimodal perception of the active screen.
    Never fabricates results.
    """
    require_owner()
    prompt = str(parameters.get("prompt") or "Describe what is visible on this mobile screen in detail").strip()

    bridge = get_bridge()
    if not bridge.phone_connected():
        return ToolResult("failed", "No companion phone connected. Cannot capture or understand phone screen.")

    # Step 1: Dispatch screen capture request to phone
    res = bridge.dispatch_screen_capture(prompt=prompt, timeout_sec=120.0, device_id=str(parameters.get('device_id') or ''))
    if res.get("status") == "failed" and "jpeg" not in res:
        return ToolResult("failed", res.get("error") or "Screen capture timed out or consent was not granted on device.")

    jpeg_data = res.get("jpeg")
    if not jpeg_data:
        return ToolResult("failed", "No image data returned from mobile device screen capture.")

    # Step 2: Decode JPEG frame
    try:
        if isinstance(jpeg_data, str):
            jpeg_bytes = base64.b64decode(jpeg_data)
        elif isinstance(jpeg_data, bytes):
            jpeg_bytes = jpeg_data
        else:
            return ToolResult("failed", "Corrupt image format in screen frame response.")
    except Exception as decode_err:
        return ToolResult("failed", f"Failed to decode screen frame: {decode_err}")

    # Step 3: Genuine multimodal model analysis via LLMRouter
    try:
        router = LLMRouter()
        messages = [
            LLMMessage(
                role="user",
                content=[
                    prompt,
                    ImagePart(data=jpeg_bytes, mime_type="image/jpeg"),
                ],
            )
        ]
        llm_resp = router.route(messages=messages, task="vision")
        visual_analysis = llm_resp.content

        return ToolResult(
            "success",
            visual_analysis,
            data={
                "provider": llm_resp.provider,
                "model": llm_resp.model,
                "width": res.get("width"),
                "height": res.get("height"),
                "prompt": prompt,
            },
        )
    except Exception as vision_err:
        logger.error("Screen vision analysis failed: %s", vision_err, exc_info=True)
        return ToolResult("failed", f"Screen frame captured, but visual AI analysis failed: {vision_err}")


# ── Canonical Tool Schemas ───────────────────────────────────────────────────

TOOLS: list[dict] = [
    {
        "name": "control_device_hardware",
        "description": "Hardware control for paired Android companion: toggle flashlight, adjust media volume, or open Wi-Fi/Bluetooth/Hotspot/Location settings panels.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "target": {
                    "type": "STRING",
                    "enum": ["flashlight", "volume", "wifi", "bluetooth", "hotspot", "location", "settings"],
                    "description": "Target hardware feature or settings panel."
                },
                "action": {
                    "type": "STRING",
                    "enum": ["on", "off", "toggle", "open_settings", "set_volume"],
                    "description": "Action to perform on target."
                },
                "percent": {
                    "type": "INTEGER",
                    "description": "Target percentage (0-100) if adjusting volume."
                }
            },
            "required": ["target"]
        },
        "handler": control_device_hardware
    },
    {
        "name": "open_phone_app",
        "description": "Launch an application or deep link on the connected Android phone (e.g. YouTube, Spotify, Maps, Settings, Chrome).",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "target_app": {
                    "type": "STRING",
                    "description": "Target app name or package (e.g. 'youtube', 'spotify', 'maps', 'chrome', 'settings')."
                },
                "query": {
                    "type": "STRING",
                    "description": "Optional search term, song, video, or destination to navigate to."
                }
            },
            "required": ["target_app"]
        },
        "handler": open_phone_app
    },
    {
        "name": "control_phone_media",
        "description": "Control media playback on connected Android companion (play, pause, toggle, next track, previous track, status).",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {
                    "type": "STRING",
                    "enum": ["play", "pause", "toggle", "next", "previous", "status"],
                    "description": "Media command."
                }
            },
            "required": ["action"]
        },
        "handler": control_phone_media
    },
    {
        "name": "search_phone_contacts",
        "description": "Search the Android device's contacts directory by name or phone number.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "query": {
                    "type": "STRING",
                    "description": "Contact name or phone number query."
                }
            },
            "required": ["query"]
        },
        "handler": search_phone_contacts
    },
    {
        "name": "make_phone_call",
        "description": "Start a cellular or WhatsApp call on the paired Android phone. Resolve saved contact names, including didi, with search_phone_contacts first. Android asks for confirmation. Report the actual result; an opened calling screen does not prove a connected call.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "app": {"type": "STRING", "enum": ["phone", "whatsapp"], "description": "Calling app. Default phone; use whatsapp when requested."},
                "contact": {
                    "type": "STRING",
                    "description": "Name or phone number to call."
                }
            },
            "required": ["contact"]
        },
        "handler": make_phone_call
    },
    {
        "name": "browse_phone_media",
        "description": "Find photos, videos or audio in the paired phone's shared media library by filename. Returns bounded metadata and phone content URIs. Supply a returned URI to open it on the phone. Does not upload or describe media contents. Android permission is required.",
        "parameters": {"type": "OBJECT", "properties": {
            "kind": {"type": "STRING", "enum": ["photos", "videos", "audio"]},
            "query": {"type": "STRING"}, "uri": {"type": "STRING"}}, "required": ["kind"]},
        "handler": browse_phone_media
    },
    {
        "name": "control_incoming_call",
        "description": "Manage incoming cellular calls on the phone: answer hands-free, decline/reject, or announce caller identity out loud.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {
                    "type": "STRING",
                    "enum": ["answer", "reject", "announce"],
                    "description": "Action to perform."
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
        "name": "send_sms_message",
        "description": "Compose and send a text SMS message through the Android companion phone.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "contact": {
                    "type": "STRING",
                    "description": "Recipient name or phone number."
                },
                "message": {
                    "type": "STRING",
                    "description": "SMS message text to send."
                }
            },
            "required": ["contact", "message"]
        },
        "handler": send_sms_message
    },
    {
        "name": "manage_phone_notifications",
        "description": "Listen to, summarize, or dispatch inline RemoteInput replies to Android notifications.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {
                    "type": "STRING",
                    "enum": ["read_latest", "read_all", "summarize", "reply"],
                    "description": "Notification operation."
                },
                "app_filter": {
                    "type": "STRING",
                    "description": "Optional app or package name filter (e.g. 'whatsapp', 'instagram', 'messages')."
                },
                "reply_text": {
                    "type": "STRING",
                    "description": "Reply text if action is 'reply'."
                },
                "key": {
                    "type": "STRING",
                    "description": "Notification key if replying to a specific notification."
                }
            },
            "required": ["action"]
        },
        "handler": manage_phone_notifications
    },
    {
        "name": "get_phone_awareness_summary",
        "description": "Unified awareness briefing across phone status, missed/recent calls, SMS, notifications, and WhatsApp unreads.",
        "parameters": {
            "type": "OBJECT",
            "properties": {}
        },
        "handler": get_phone_awareness_summary
    },
    {
        "name": "capture_phone_screen",
        "description": "Capture the user's active mobile screen frame via Android MediaProjection consent.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "prompt": {
                    "type": "STRING",
                    "description": "Optional context prompt for capture."
                }
            }
        },
        "handler": capture_phone_screen
    },
    {
        "name": "understand_phone_screen",
        "description": "Real Multimodal Phone Screen Vision: captures the live Android screen, passes the frame to Gemini/multimodal AI, and returns genuine visual analysis.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "prompt": {
                    "type": "STRING",
                    "description": "Specific question or analysis prompt about what is visible on the phone screen."
                }
            },
            "required": ["prompt"]
        },
        "handler": understand_phone_screen
    }
]

# Device choice is explicit when several paired phones are online.
for _mobile_tool in TOOLS:
    _mobile_tool['parameters'].setdefault('properties', {})['device_id'] = {
        'type': 'STRING', 'description': 'Exact paired device ID if several phones are connected.'}
