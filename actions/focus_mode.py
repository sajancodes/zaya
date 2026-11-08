"""Focus Mode, Do Not Disturb (DND) & Notification Center Sentinel.
Created and developed by Sajan Rai for Zaya.

Manages deep work focus sessions, suppresses desktop notifications via Windows
Quiet Hours / Do Not Disturb (DND), controls per-app notification permissions,
and tracks personal productivity streaks in local SQLite memory.
"""
from __future__ import annotations

import datetime
import json
import os
from pathlib import Path
import sqlite3
import time
from typing import Any, Dict, List, Optional

from core.execution_policy import require_owner

_DB_PATH = Path("memory") / "focus_sessions.db"
_ACTIVE_SESSION_FILE = Path("memory") / "active_focus.json"

_QUIET_HOURS_REG_PATH = r"Software\Microsoft\Windows\CurrentVersion\Notifications\QuietHours"
_NOTIFICATIONS_SETTINGS_REG_PATH = r"Software\Microsoft\Windows\CurrentVersion\Notifications\Settings"


def _get_db() -> sqlite3.Connection:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_DB_PATH), timeout=5.0)
    conn.row_factory = sqlite3.Row
    with conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS focus_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                start_time TEXT NOT NULL,
                end_time TEXT,
                target_minutes INTEGER NOT NULL,
                actual_minutes REAL,
                goal TEXT,
                status TEXT NOT NULL,
                created_at REAL NOT NULL
            )
            """
        )
    return conn


def _get_windows_quiet_hours_state() -> Dict[str, Any]:
    """Inspect Windows Quiet Hours / Do Not Disturb service state via winreg."""
    if os.name != "nt":
        return {"available": False, "state_code": 0, "state_name": "Non-Windows OS"}

    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, _QUIET_HOURS_REG_PATH, 0, winreg.KEY_READ)
        try:
            val, _ = winreg.QueryValueEx(key, "QuietHoursServiceState")
            names = {0: "Off (All notifications allowed)", 1: "Priority Only", 2: "Alarms Only / Do Not Disturb"}
            return {
                "available": True,
                "state_code": int(val),
                "state_name": names.get(int(val), f"Custom State ({val})"),
                "dnd_active": int(val) in (1, 2),
            }
        finally:
            winreg.CloseKey(key)
    except Exception as e:
        return {"available": False, "state_code": 0, "state_name": f"Unavailable: {e}", "dnd_active": False}


def _set_windows_quiet_hours_state(state_code: int) -> bool:
    """Set Windows Quiet Hours / Do Not Disturb state (0=off, 1=priority, 2=alarms only)."""
    if os.name != "nt":
        return False

    try:
        import winreg
        key = winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, _QUIET_HOURS_REG_PATH, 0, winreg.KEY_SET_VALUE)
        try:
            winreg.SetValueEx(key, "QuietHoursServiceState", 0, winreg.REG_DWORD, int(state_code))
            return True
        finally:
            winreg.CloseKey(key)
    except Exception:
        return False


def _get_active_session() -> Optional[Dict[str, Any]]:
    if not _ACTIVE_SESSION_FILE.exists():
        return None
    try:
        with open(_ACTIVE_SESSION_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if not isinstance(data, dict):
                return None
            return data
    except Exception:
        return None


def _save_active_session(session_data: Optional[Dict[str, Any]]) -> None:
    _ACTIVE_SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
    if session_data is None:
        if _ACTIVE_SESSION_FILE.exists():
            try:
                _ACTIVE_SESSION_FILE.unlink()
            except Exception:
                pass
        return
    with open(_ACTIVE_SESSION_FILE, "w", encoding="utf-8") as f:
        json.dump(session_data, f, indent=2)


def _list_app_notification_rules() -> List[Dict[str, Any]]:
    """List per-app notification rules registered with Windows."""
    if os.name != "nt":
        return []

    results = []
    try:
        import winreg
        parent_key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, _NOTIFICATIONS_SETTINGS_REG_PATH, 0, winreg.KEY_READ)
        i = 0
        while True:
            try:
                app_id = winreg.EnumKey(parent_key, i)
                i += 1
            except OSError:
                break

            # Read app subkey settings
            try:
                app_key = winreg.OpenKey(parent_key, app_id, 0, winreg.KEY_READ)
                try:
                    enabled = True
                    try:
                        val, _ = winreg.QueryValueEx(app_key, "Enabled")
                        enabled = bool(val)
                    except OSError:
                        pass
                    results.append({"app_id": app_id, "enabled": enabled})
                finally:
                    winreg.CloseKey(app_key)
            except Exception:
                continue
        winreg.CloseKey(parent_key)
    except Exception:
        pass
    return sorted(results, key=lambda x: x["app_id"].lower())


def _toggle_app_notification(app_id: str, enabled: bool) -> bool:
    """Enable or disable notifications for a specific registered Windows app."""
    if os.name != "nt":
        return False

    try:
        import winreg
        sub_path = f"{_NOTIFICATIONS_SETTINGS_REG_PATH}\\{app_id}"
        app_key = winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, sub_path, 0, winreg.KEY_SET_VALUE)
        try:
            winreg.SetValueEx(app_key, "Enabled", 0, winreg.REG_DWORD, 1 if enabled else 0)
            return True
        finally:
            winreg.CloseKey(app_key)
    except Exception:
        return False


def focus_mode(parameters: dict, **_kwargs) -> str:
    """Dispatches Focus Mode, Do Not Disturb and notification actions."""
    require_owner()
    action = str(parameters.get("action") or "status").lower().strip()

    # 1. Status Query
    if action in ("status", "check"):
        quiet = _get_windows_quiet_hours_state()
        active = _get_active_session()

        if active:
            start_ts = active.get("start_ts", time.time())
            target_mins = active.get("target_minutes", 25)
            elapsed_mins = round((time.time() - start_ts) / 60.0, 1)
            remaining_mins = max(0.0, round(target_mins - elapsed_mins, 1))
            goal = active.get("goal") or "Deep work"
            is_overtime = elapsed_mins >= target_mins

            summary = (
                f"Focus Mode ACTIVE: '{goal}'. Elapsed: {elapsed_mins}m / {target_mins}m "
                f"({remaining_mins}m remaining" + (", goal reached!" if is_overtime else "") + "). "
                f"Windows DND: {'ON' if quiet.get('dnd_active') else 'OFF'}."
            )
            return json.dumps({
                "status": "success",
                "active": True,
                "summary": summary,
                "session": {
                    "goal": goal,
                    "target_minutes": target_mins,
                    "elapsed_minutes": elapsed_mins,
                    "remaining_minutes": remaining_mins,
                    "is_overtime": is_overtime,
                    "start_time": active.get("start_time"),
                },
                "quiet_hours": quiet,
            }, indent=2)
        else:
            summary = (
                f"Focus Mode is currently INACTIVE. "
                f"Windows Quiet Hours: {quiet.get('state_name', 'Unknown')}."
            )
            return json.dumps({
                "status": "success",
                "active": False,
                "summary": summary,
                "quiet_hours": quiet,
            }, indent=2)

    # 2. Start Focus Session
    if action in ("start", "on", "activate", "begin"):
        active = _get_active_session()
        target_minutes = int(parameters.get("duration_minutes") or parameters.get("duration") or 25)
        goal = str(parameters.get("goal") or parameters.get("topic") or "Deep focus work").strip()
        set_dnd = parameters.get("set_dnd", True)

        now = datetime.datetime.now()
        start_time_str = now.strftime("%Y-%m-%d %H:%M:%S")
        start_ts = time.time()

        prev_quiet = _get_windows_quiet_hours_state()
        if set_dnd:
            _set_windows_quiet_hours_state(2)  # Alarms Only / DND

        # Record in DB
        with _get_db() as conn:
            cur = conn.execute(
                """
                INSERT INTO focus_sessions (start_time, target_minutes, goal, status, created_at)
                VALUES (?, ?, ?, 'in_progress', ?)
                """,
                (start_time_str, target_minutes, goal, start_ts),
            )
            session_id = cur.lastrowid

        new_session = {
            "session_id": session_id,
            "start_time": start_time_str,
            "start_ts": start_ts,
            "target_minutes": target_minutes,
            "goal": goal,
            "prev_dnd_state": prev_quiet.get("state_code", 0),
        }
        _save_active_session(new_session)

        target_time = (now + datetime.timedelta(minutes=target_minutes)).strftime("%I:%M %p")
        summary = (
            f"Focus Mode activated for {target_minutes} minutes (until {target_time}) on '{goal}'. "
            f"Do Not Disturb engaged to prevent distractions. Let's do great work, sir."
        )
        return json.dumps({"status": "success", "summary": summary, "session": new_session}, indent=2)

    # 3. Stop / Complete Focus Session
    if action in ("stop", "off", "cancel", "end", "finish"):
        active = _get_active_session()
        if not active:
            return json.dumps({
                "status": "success",
                "summary": "No active focus session found to stop.",
                "active": False,
            }, indent=2)

        start_ts = active.get("start_ts", time.time())
        target_mins = active.get("target_minutes", 25)
        actual_mins = round((time.time() - start_ts) / 60.0, 1)
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        session_id = active.get("session_id")
        goal = active.get("goal") or "Deep work"
        prev_dnd = active.get("prev_dnd_state", 0)

        # Restore previous DND state
        _set_windows_quiet_hours_state(prev_dnd)

        # Update DB
        with _get_db() as conn:
            if session_id:
                conn.execute(
                    """
                    UPDATE focus_sessions
                    SET end_time = ?, actual_minutes = ?, status = 'completed'
                    WHERE id = ?
                    """,
                    (now_str, actual_mins, session_id),
                )

        _save_active_session(None)

        summary = (
            f"Focus session completed! You focused for {actual_mins} minutes on '{goal}' "
            f"(target: {target_mins}m). Do Not Disturb restored. Excellent effort, sir."
        )
        return json.dumps({
            "status": "success",
            "summary": summary,
            "focused_minutes": actual_mins,
            "goal": goal,
        }, indent=2)

    # 4. Extend Focus Session
    if action in ("extend", "add_time"):
        active = _get_active_session()
        if not active:
            return json.dumps({
                "status": "error",
                "message": "Cannot extend: no focus session is currently active.",
            }, indent=2)

        add_mins = int(parameters.get("minutes") or 15)
        active["target_minutes"] = active.get("target_minutes", 25) + add_mins
        _save_active_session(active)

        with _get_db() as conn:
            if active.get("session_id"):
                conn.execute(
                    "UPDATE focus_sessions SET target_minutes = ? WHERE id = ?",
                    (active["target_minutes"], active["session_id"]),
                )

        summary = f"Focus session extended by {add_mins} minutes. New target: {active['target_minutes']} minutes."
        return json.dumps({"status": "success", "summary": summary, "session": active}, indent=2)

    # 5. History / Productive Time Query
    if action in ("history", "stats", "summary"):
        with _get_db() as conn:
            rows = conn.execute(
                """
                SELECT id, start_time, end_time, target_minutes, actual_minutes, goal, status
                FROM focus_sessions
                ORDER BY id DESC LIMIT 10
                """
            ).fetchall()

            today_str = datetime.datetime.now().strftime("%Y-%m-%d")
            today_rows = conn.execute(
                """
                SELECT SUM(actual_minutes) as total_mins, COUNT(id) as total_sessions
                FROM focus_sessions
                WHERE start_time LIKE ? AND status = 'completed'
                """,
                (f"{today_str}%",),
            ).fetchone()

        total_today_mins = round(today_rows["total_mins"] or 0.0, 1)
        total_sessions = today_rows["total_sessions"] or 0

        past_sessions = [dict(r) for r in rows]
        summary = (
            f"Focus Analytics: {total_sessions} session(s) completed today totaling "
            f"{total_today_mins} focused minutes ({round(total_today_mins / 60.0, 1)} hrs)."
        )
        return json.dumps({
            "status": "success",
            "summary": summary,
            "today_minutes": total_today_mins,
            "today_sessions": total_sessions,
            "recent_sessions": past_sessions,
        }, indent=2)

    # 6. Direct DND Toggle / Set
    if action in ("dnd_toggle", "dnd", "quiet_hours"):
        enable = parameters.get("enabled")
        if enable is None:
            curr = _get_windows_quiet_hours_state()
            new_code = 0 if curr.get("dnd_active") else 2
        else:
            new_code = 2 if enable else 0

        success = _set_windows_quiet_hours_state(new_code)
        state_str = "ENABLED (Alarms Only)" if new_code == 2 else "DISABLED (Normal)"
        summary = f"Windows Do Not Disturb / Quiet Hours is now {state_str}."
        return json.dumps({
            "status": "success" if success else "partial",
            "summary": summary,
            "state_code": new_code,
        }, indent=2)

    # 7. App Notification Permissions
    if action in ("apps", "list_apps"):
        apps = _list_app_notification_rules()
        summary = f"Found {len(apps)} registered application(s) in Windows notification settings."
        return json.dumps({"status": "success", "summary": summary, "apps": apps}, indent=2)

    if action in ("app_toggle", "set_app"):
        app_id = str(parameters.get("app_id") or "").strip()
        if not app_id:
            return json.dumps({"status": "error", "message": "Missing required parameter 'app_id'."}, indent=2)
        enabled = bool(parameters.get("enabled", True))
        ok = _toggle_app_notification(app_id, enabled)
        summary = f"Notifications for '{app_id}' {'enabled' if enabled else 'disabled'}."
        return json.dumps({"status": "success" if ok else "error", "summary": summary, "app_id": app_id, "enabled": enabled}, indent=2)

    return json.dumps({
        "status": "error",
        "message": f"Unknown action '{action}'. Choose from: status, start, stop, extend, history, dnd_toggle, apps, app_toggle."
    }, indent=2)


TOOL = {
    "name": "focus_mode",
    "description": "Control Windows Focus Mode / Do Not Disturb (DND), timed deep work sessions, suppression of interruptions, and app notification permissions.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "enum": ["status", "start", "stop", "extend", "history", "dnd_toggle", "apps", "app_toggle"],
                "description": "Focus mode operation to execute (default: 'status').",
            },
            "duration_minutes": {
                "type": "INTEGER",
                "description": "Duration for focus session in minutes (default: 25).",
            },
            "goal": {
                "type": "STRING",
                "description": "The specific objective or task to focus on.",
            },
            "minutes": {
                "type": "INTEGER",
                "description": "Minutes to add when extending current session (default: 15).",
            },
            "enabled": {
                "type": "BOOLEAN",
                "description": "True to enable DND or app notification; False to disable.",
            },
            "app_id": {
                "type": "STRING",
                "description": "App identifier when configuring per-app notification rules.",
            },
        },
    },
    "handler": focus_mode,
}
