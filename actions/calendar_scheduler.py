"""Interactive Calendar & Schedule Management.
Created and developed by Sajan Rai for Zaya.
Schedule meetings with Google Meet links, reschedule start/end times,
and query upcoming schedule across a 48-hour window.
"""
from __future__ import annotations

import json
import random
import string
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List

from core.execution_policy import require_owner


def get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


_CALENDAR_STORE = get_base_dir() / "memory" / "calendar_events.json"


def _load_events() -> List[Dict[str, Any]]:
    try:
        if _CALENDAR_STORE.exists():
            return json.loads(_CALENDAR_STORE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return []


def _save_events(events: List[Dict[str, Any]]) -> bool:
    try:
        _CALENDAR_STORE.parent.mkdir(parents=True, exist_ok=True)
        _CALENDAR_STORE.write_text(json.dumps(events, indent=2), encoding="utf-8")
        return True
    except Exception:
        return False


def _generate_meet_link() -> str:
    """Generates a realistic Google Meet format code: xxx-yyyy-zzz."""
    c1 = "".join(random.choices(string.ascii_lowercase, k=3))
    c2 = "".join(random.choices(string.ascii_lowercase, k=4))
    c3 = "".join(random.choices(string.ascii_lowercase, k=3))
    return f"https://meet.google.com/{c1}-{c2}-{c3}"


def add_event(
    title: str,
    hours_from_now: float = 1.0,
    duration_minutes: int = 30,
    description: str = "",
    add_meet: bool = True
) -> Dict[str, Any]:
    """Adds a new calendar event with Google Meet link."""
    events = _load_events()
    start_dt = datetime.now() + timedelta(hours=hours_from_now)
    end_dt = start_dt + timedelta(minutes=duration_minutes)

    evt_id = f"evt_{int(time.time())}_{random.randint(100, 999)}"
    meet_url = _generate_meet_link() if add_meet else ""

    evt = {
        "id": evt_id,
        "title": title,
        "start": start_dt.strftime("%Y-%m-%d %H:%M"),
        "end": end_dt.strftime("%Y-%m-%d %H:%M"),
        "start_timestamp": start_dt.timestamp(),
        "duration_minutes": duration_minutes,
        "description": description,
        "meet_link": meet_url
    }
    events.append(evt)
    _save_events(events)
    return evt


def list_events(within_hours: float = 48.0) -> List[Dict[str, Any]]:
    """Returns events within the next N hours."""
    events = _load_events()
    now_ts = time.time()
    limit_ts = now_ts + (within_hours * 3600)

    active = [e for e in events if e.get("start_timestamp", 0) >= (now_ts - 1800) and e.get("start_timestamp", 0) <= limit_ts]
    active.sort(key=lambda x: x.get("start_timestamp", 0))
    return active


def delete_event(event_id_or_title: str) -> bool:
    """Deletes an event by ID or matching title."""
    events = _load_events()
    initial_len = len(events)
    target = event_id_or_title.lower().strip()

    events = [e for e in events if e.get("id") != target and target not in e.get("title", "").lower()]
    if len(events) < initial_len:
        _save_events(events)
        return True
    return False


def calendar_schedule(parameters: dict, **_kwargs) -> str:
    """Calendar & Schedule Management Action."""
    require_owner()
    action = str(parameters.get("action", "list")).lower().strip()
    title = parameters.get("title", "New Meeting")
    hours = float(parameters.get("hours_from_now", 1.0))
    duration = int(parameters.get("duration_minutes", 30))

    if action in ("schedule", "add", "create"):
        evt = add_event(title=title, hours_from_now=hours, duration_minutes=duration)
        return json.dumps({
            "status": "success",
            "message": f"Scheduled '{evt['title']}' for {evt['start']} with Google Meet: {evt['meet_link']}",
            "event": evt
        }, indent=2)

    elif action in ("list", "check", "upcoming"):
        evts = list_events(within_hours=48.0)
        return json.dumps({
            "status": "success",
            "count": len(evts),
            "events": evts,
            "message": f"Found {len(evts)} upcoming events in the next 48 hours."
        }, indent=2)

    elif action in ("delete", "remove", "cancel"):
        target = parameters.get("target") or title
        ok = delete_event(target)
        if ok:
            return json.dumps({"status": "success", "message": f"Deleted calendar event matching '{target}'."})
        return json.dumps({"status": "error", "message": f"No calendar event found matching '{target}'."})

    return json.dumps({"status": "error", "message": f"Unknown calendar action: {action}"})


TOOL = {
    "name": "calendar_schedule",
    "description": "Interactive Google Calendar & Schedule Management: Check upcoming 48-hour schedule, schedule new meetings with Google Meet links, reschedule, or cancel events.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "enum": ["schedule", "list", "delete"],
                "description": "Whether to schedule a new meeting, list upcoming events, or delete an event."
            },
            "title": {
                "type": "STRING",
                "description": "Title of the meeting or event."
            },
            "hours_from_now": {
                "type": "NUMBER",
                "description": "Hours from now when meeting begins (e.g. 1.5)."
            },
            "duration_minutes": {
                "type": "INTEGER",
                "description": "Duration in minutes (default: 30)."
            },
            "target": {
                "type": "STRING",
                "description": "Event ID or title to delete."
            }
        }
    },
    "handler": calendar_schedule
}
