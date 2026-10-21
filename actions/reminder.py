import json
import os
import math
import time
import platform
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from xml.sax.saxutils import escape

from core.execution_policy import require_owner
from core.reminders import get_reminders
from core.tool_result import ToolResult

_CNW: dict = (
    {"creationflags": subprocess.CREATE_NO_WINDOW}
    if platform.system() == "Windows" else {}
)

def _base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


def _get_os() -> str:
    _sys = platform.system()
    if _sys == "Darwin":
        return "mac"
    if _sys == "Linux":
        return "linux"
    return "windows"


def _scripts_dir() -> Path:
    d = Path.home() / ".jarvis" / "reminders"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _write_notify_script(task_name: str, reminder_id: str, database: Path) -> Path:
    script_path = _scripts_dir() / f"{task_name}.py"
    # Values are Python string literals, never executable owner message text.
    body = (
        "# Zaya reminder callback; keep this file if notification fails.\n"
        "import sys\nfrom pathlib import Path\n"
        f"sys.path.insert(0, {str(_base_dir())!r})\n"
        "from core.reminders import notify_scheduled\n"
        f"ok = notify_scheduled({reminder_id!r}, {str(database)!r}, {_get_os()!r})\n"
        "if ok:\n    Path(__file__).unlink(missing_ok=True)\n"
        "sys.exit(0 if ok else 1)\n"
    )
    script_path.write_text(body, encoding="utf-8")
    script_path.chmod(0o600)
    return script_path


def _schedule_windows(target_dt: datetime, task_name: str,
                      script_path: Path, message: str) -> str:
    python_exe = Path(sys.executable)
    pythonw = python_exe.parent / "pythonw.exe"
    if pythonw.exists():
        python_exe = pythonw

    xml_path = _scripts_dir() / f"{task_name}.xml"
    xml_content = (
        '<?xml version="1.0" encoding="UTF-16"?>\n'
        '<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">\n'
        '  <RegistrationInfo><Description>Zaya Reminder</Description></RegistrationInfo>\n'
        '  <Triggers><TimeTrigger>\n'
        f'    <StartBoundary>{target_dt.strftime("%Y-%m-%dT%H:%M:%S")}</StartBoundary>\n'
        '    <Enabled>true</Enabled>\n'
        '  </TimeTrigger></Triggers>\n'
        '  <Actions><Exec>\n'
        f'    <Command>{escape(str(python_exe))}</Command>\n'
        f'    <Arguments>{escape(chr(34) + str(script_path) + chr(34))}</Arguments>\n'
        '  </Exec></Actions>\n'
        '  <Settings>\n'
        '    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>\n'
        '    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>\n'
        '    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>\n'
        '    <StartWhenAvailable>true</StartWhenAvailable>\n'
        '    <ExecutionTimeLimit>PT5M</ExecutionTimeLimit>\n'
        '    <RestartOnFailure><Interval>PT1M</Interval><Count>3</Count></RestartOnFailure>\n'
        '    <Enabled>true</Enabled>\n'
        '  </Settings>\n'
        '  <Principals><Principal>\n'
        '    <LogonType>InteractiveToken</LogonType>\n'
        '    <RunLevel>LeastPrivilege</RunLevel>\n'
        '  </Principal></Principals>\n'
        '</Task>'
    )

    xml_path.write_text(xml_content, encoding="utf-16")

    result = subprocess.run(
        ["schtasks", "/Create", "/TN", task_name, "/XML", str(xml_path), "/F"],
        capture_output=True, text=True, timeout=20, **_CNW,
    )

    try:
        xml_path.unlink(missing_ok=True)
    except Exception:
        pass

    if result.returncode != 0:
        script_path.unlink(missing_ok=True)
        err = (result.stderr or result.stdout).strip()
        print(f"[Reminder] ❌ schtasks: {err}")
        return ""  

    return task_name


def _schedule_mac(target_dt: datetime, task_name: str,
                  script_path: Path) -> str:
    agents_dir = Path.home() / "Library" / "LaunchAgents"
    agents_dir.mkdir(parents=True, exist_ok=True)

    label     = f"com.jarvis.reminder.{task_name}"
    plist_path = agents_dir / f"{label}.plist"

    plist_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>             <string>{label}</string>
  <key>ProgramArguments</key>
  <array>
    <string>{sys.executable}</string>
    <string>{script_path}</string>
  </array>
  <key>StartCalendarInterval</key>
  <dict>
    <key>Year</key>   <integer>{target_dt.year}</integer>
    <key>Month</key>  <integer>{target_dt.month}</integer>
    <key>Day</key>    <integer>{target_dt.day}</integer>
    <key>Hour</key>   <integer>{target_dt.hour}</integer>
    <key>Minute</key> <integer>{target_dt.minute}</integer>
  </dict>
  <key>RunAtLoad</key>         <false/>
  <key>StandardOutPath</key>   <string>/dev/null</string>
  <key>StandardErrorPath</key> <string>/dev/null</string>
</dict>
</plist>
"""
    plist_path.write_text(plist_content, encoding="utf-8")
    plist_path.chmod(0o644)

    result = subprocess.run(
        ["launchctl", "load", str(plist_path)],
        capture_output=True, text=True,
    )

    if result.returncode != 0:
        plist_path.unlink(missing_ok=True)
        script_path.unlink(missing_ok=True)
        print(f"[Reminder] ❌ launchctl: {result.stderr.strip()}")
        return ""

    return label


def _schedule_linux(target_dt: datetime, task_name: str,
                    script_path: Path) -> str:

    if shutil.which("systemd-run"):
        on_calendar = target_dt.strftime("%Y-%m-%d %H:%M:%S")
        result = subprocess.run(
            [
                "systemd-run",
                "--user",
                f"--on-calendar={on_calendar}",
                f"--unit={task_name}",
                "--",
                sys.executable, str(script_path),
            ],
            capture_output=True, text=True,
        )
        if result.returncode == 0:
            return task_name
        print(f"[Reminder] ⚠️ systemd-run failed: {result.stderr.strip()}, trying 'at'")

    if shutil.which("at"):
        at_time = target_dt.strftime("%H:%M %Y-%m-%d")
        import shlex
        cmd_str = shlex.join([sys.executable, str(script_path)]) + "\n"
        result  = subprocess.run(
            ["at", at_time],
            input=cmd_str, capture_output=True, text=True,
        )
        if result.returncode == 0:
            return task_name
        print(f"[Reminder] ❌ at: {result.stderr.strip()}")
        return ""

    print("[Reminder] ❌ Neither systemd-run nor at found on this Linux system.")
    return ""

def reminder(parameters: dict, **_kwargs) -> ToolResult:
    require_owner()
    store = get_reminders()
    action = str(parameters.get("action") or "create").strip().lower()
    try:
        if action in {"status", "list"}:
            rid = str(parameters.get("id") or "").strip()
            rows = [store.get(rid)] if rid else store.list()
            return ToolResult("success", f"{len(rows)} saved reminders; check delivery timestamps and errors.",
                              {"reminders": rows, "now_local": datetime.now().astimezone().isoformat()},
                              [{"source": "local reminder ledger"}])
        if action == "cancel":
            item = store.cancel(str(parameters.get("id") or ""))
            return ToolResult("success", "Reminder cancelled, sir.", {"reminder": item},
                              [{"cancelled": True}], side_effect=True)
        if action != "create":
            raise ValueError("Use create, status, list or cancel.")
        message = str(parameters.get("message") or "").strip()
        if not message or len(message) > 1000:
            raise ValueError("Give me a reminder message between 1 and 1000 characters.")
        now = time.time()
        if parameters.get("delay_seconds") is not None:
            delay = float(parameters["delay_seconds"])
            if not math.isfinite(delay) or not 0 < delay <= 366 * 86400:
                raise ValueError("The reminder delay must be positive and at most one year.")
            due_at = now + delay
        else:
            date_str = str(parameters.get("date") or datetime.fromtimestamp(now).strftime("%Y-%m-%d"))
            time_str = str(parameters.get("time") or "").strip()
            if not time_str:
                raise ValueError("Tell me when to remind you: a delay, or a date and time.")
            fmt = "%Y-%m-%d %H:%M:%S" if time_str.count(":") == 2 else "%Y-%m-%d %H:%M"
            due_at = datetime.strptime(f"{date_str} {time_str}", fmt).timestamp()
        if not math.isfinite(due_at) or due_at <= now:
            raise ValueError("That reminder time has already passed. Give me a future time.")
        delivery = str(parameters.get('delivery') or 'voice').strip().lower()
        item = store.create(message, due_at, delivery=delivery)
        task_name = "ZayaReminder_" + item["id"][:16]
        script_path = None
        try:
            script_path = _write_notify_script(task_name, item["id"], store.path)
            target = datetime.fromtimestamp(due_at)
            os_name = _get_os()
            if os_name == "windows":
                job_id = _schedule_windows(target, task_name, script_path, message)
            elif os_name == "mac":
                job_id = _schedule_mac(target, task_name, script_path)
            else:
                job_id = _schedule_linux(target, task_name, script_path)
            if not job_id:
                raise RuntimeError("The system scheduler did not accept background delivery.")
            store.update(item["id"], scheduler_id=job_id)
        except Exception as error:
            store.update(item["id"], error=str(error)[:1000])
            if script_path is not None:
                script_path.unlink(missing_ok=True)
            return ToolResult("partial", ("Scheduled phone call saved; Zaya must be running at the due time because background startup could not be registered." if delivery == 'call' else "I've saved it for spoken delivery while Zaya is running, sir. Background desktop delivery could not be registered."),
                              {"reminder": store.get(item["id"])}, [{"saved": True, "background_registered": False}], side_effect=True)
        label = 'Phone call' if delivery == 'call' else 'Reminder'
        return ToolResult("success", f"{label} scheduled for {item['due_local']}." +
                          (' The paired phone and laptop must be online; a pending call retries when available.' if delivery == 'call' else ''),
                          {"reminder": store.get(item["id"])},
                          [{"saved": True, "background_registered": True, "scheduler_id": job_id}], side_effect=True)
    except (ValueError, TypeError, OSError, OverflowError) as error:
        return ToolResult("failed", str(error))


TOOL = {
    "name": "reminder",
    "description": (
        "Create a durable timed reminder with spoken delivery in Zaya and a desktop fallback. "
        "For 'call me at/in' use delivery=call to schedule an actual ringing phone call, never an ordinary spoken reminder. "
        "For 'in N minutes' use delay_seconds=N*60, calculated from the live clock when called. "
        "Use action=status whenever the owner asks about a reminder or says you forgot it: "
        "inspect due time, voice_queued_at, desktop_notified_at and error before answering. "
        "Do not claim the owner heard a reminder merely because it was saved or queued."),
    "parameters": {"type": "OBJECT", "properties": {
        "action": {"type": "STRING", "enum": ["create", "status", "list", "cancel"]},
        "delivery": {"type": "STRING", "enum": ["voice", "call"], "description": "call for a scheduled ringing phone call; voice for an ordinary reminder."},
        "id": {"type": "STRING", "description": "Exact saved reminder ID for status or cancellation."},
        "delay_seconds": {"type": "NUMBER", "description": "Relative delay in seconds, evaluated from the clock at this call."},
        "date": {"type": "STRING", "description": "Local date YYYY-MM-DD; today if omitted."},
        "time": {"type": "STRING", "description": "Local 24-hour time HH:MM or HH:MM:SS for an absolute reminder."},
        "message": {"type": "STRING", "description": "The exact reminder message to deliver."},
    }},
    "handler": reminder,
}
