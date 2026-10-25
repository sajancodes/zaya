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
import os
import tempfile
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List

from core.execution_policy import require_owner


def get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


_EVENT_LOCK = threading.RLock()

_CALENDAR_STORE = get_base_dir() / "memory" / "calendar_events.json"


def _load_events() -> List[Dict[str, Any]]:
    try:
        if _CALENDAR_STORE.exists():
            data = json.loads(_CALENDAR_STORE.read_text(encoding="utf-8"))
            # A hand-edited or half-written store must not take the action
            # down: _load_events() returned whatever was in the file, and a
            # JSON object instead of a list made events.append() raise.
            if isinstance(data, list):
                return [e for e in data if isinstance(e, dict)]
    except Exception:
        pass
    return []


def _save_events(events: List[Dict[str, Any]]) -> bool:
    temporary = None
    try:
        _CALENDAR_STORE.parent.mkdir(parents=True, exist_ok=True)
        if _CALENDAR_STORE.exists():
            existing = json.loads(_CALENDAR_STORE.read_text(encoding="utf-8"))
            if not isinstance(existing, list):
                return False
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=_CALENDAR_STORE.parent,
                                         prefix='.calendar-', suffix='.tmp', delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(events, stream, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, _CALENDAR_STORE)
        return True
    except (OSError, ValueError):
        return False
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _generate_meet_link() -> str:
    """No meeting service is authenticated here; never invent a meeting URL."""
    return ''


def add_event(*args, **kwargs):
    with _EVENT_LOCK:
        return _add_event(*args, **kwargs)


def _add_event(
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
    evt["sync_status"] = "local_only"
    events.append(evt)
    if not _save_events(events):
        raise OSError("Calendar event was not saved; existing records were preserved.")
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
    target = str(event_id_or_title or '').strip().casefold()
    if not target:
        raise ValueError('Specify an exact event ID or title to delete.')
    with _EVENT_LOCK:
        events = _load_events()
        matched = [e for e in events if str(e.get('id', '')).casefold() == target]
        if not matched:
            matched = [e for e in events if str(e.get('title', '')).strip().casefold() == target]
        if len(matched) > 1:
            raise ValueError('Several events have that title. Use the exact event ID.')
        if not matched:
            return False
        if not _save_events([e for e in events if e is not matched[0]]):
            raise OSError('Calendar deletion was not saved; existing records were preserved.')
        return True


def calendar_schedule(parameters: dict, **kwargs) -> str:
    try:
        return _calendar_schedule(parameters, **kwargs)
    except (OSError, ValueError, OverflowError) as error:
        return json.dumps({'status': 'error', 'message': str(error)})


def _calendar_schedule(parameters: dict, **_kwargs) -> str:
    """Calendar & Schedule Management Action."""
    require_owner()
    action = str(parameters.get("action", "list")).lower().strip()
    title = parameters.get("title", "New Meeting")

    # The model supplies these as free-form JSON, so a non-numeric value
    # used to raise ValueError straight out of the handler.
    try:
        hours = float(parameters.get("hours_from_now", 1.0))
    except (TypeError, ValueError):
        return json.dumps({
            "status": "error",
            "message": "hours_from_now must be a number (e.g. 1.5 for ninety minutes from now)."
        })
    try:
        duration = int(parameters.get("duration_minutes", 30))
    except (TypeError, ValueError):
        return json.dumps({
            "status": "error",
            "message": "duration_minutes must be a whole number of minutes."
        })
    if duration <= 0:
        return json.dumps({"status": "error", "message": "duration_minutes must be greater than zero."})

    if action in ("schedule", "add", "create"):
        evt = add_event(title=title, hours_from_now=hours, duration_minutes=duration)
        return json.dumps({
            "status": "success",
            "message": f"Saved local event '{evt['title']}' for {evt['start']}. Google Calendar and Meet are not connected.",
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
    "description": "Local calendar: save events, list the next 48 hours, or delete one exact event ID/title. Google Calendar and Meet are not connected; no external meeting link is created.",
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
