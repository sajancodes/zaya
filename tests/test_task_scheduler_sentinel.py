"""Tests for Windows Scheduled Tasks Sentinel."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch
import pytest

from actions.task_scheduler_sentinel import (
    task_scheduler_sentinel,
    _query_all_tasks,
    get_user_tasks,
    get_running_scheduled_tasks,
    search_tasks,
    get_task_details,
    get_scheduler_summary,
    TOOL,
)
from core.execution_policy import set_trust, TRUST_LOCAL_OWNER, TRUST_UNKNOWN
from core.fast_reflex import FastReflexRouter

_MOCK_SCHTASKS_CSV = """
"\\MyBackupJob","11/9/2026 2:00:00 AM","Ready"
"\\MySyncService","N/A","Running"
"\\Microsoft\\Windows\\Defrag\\ScheduledDefrag","N/A","Ready"
"\\Microsoft\\Windows\\Update\\Orchestrator","N/A","Disabled"
"\\Lenovo\\Vantage\\PeriodicTask","11/10/2026 5:00:00 AM","Ready"
"""

_MOCK_VERBOSE_TASK = """
Folder: \\
HostName:      PARROT
TaskName:      \\MyBackupJob
Next Run Time: 11/9/2026 2:00:00 AM
Status:        Ready
Logon Mode:    Interactive/Background
Last Run Time: 11/8/2026 2:00:00 AM
Last Result:   0
Author:        Sajan
Task To Run:   C:\\scripts\\backup.bat
"""


@pytest.fixture(autouse=True)
def _owner_trust():
    set_trust(TRUST_LOCAL_OWNER)
    yield
    set_trust(TRUST_LOCAL_OWNER)


def test_owner_security_gate():
    set_trust(TRUST_UNKNOWN)
    with pytest.raises(PermissionError):
        task_scheduler_sentinel({"action": "summary"})


def test_tool_declaration():
    assert TOOL["name"] == "task_scheduler_sentinel"
    assert "parameters" in TOOL
    assert callable(TOOL["handler"])


@patch("subprocess.run")
def test_query_all_tasks_parsing(mock_run):
    mock_run.return_value = MagicMock(returncode=0, stdout=_MOCK_SCHTASKS_CSV)
    tasks = _query_all_tasks()
    assert len(tasks) == 5

    backup = tasks[0]
    assert backup["task_name"] == "\\MyBackupJob"
    assert backup["folder"] == "Root"
    assert backup["status"] == "Ready"
    assert backup["is_microsoft"] is False

    ms = tasks[2]
    assert ms["task_name"] == "\\Microsoft\\Windows\\Defrag\\ScheduledDefrag"
    assert ms["folder"] == "Microsoft"
    assert ms["is_microsoft"] is True


@patch("subprocess.run")
def test_query_all_tasks_error(mock_run):
    mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="Error")
    tasks = _query_all_tasks()
    assert tasks == []


@patch("actions.task_scheduler_sentinel._query_all_tasks")
def test_get_user_tasks(mock_query):
    mock_query.return_value = [
        {"task_name": "\\UserTask", "is_microsoft": False, "status": "Ready"},
        {"task_name": "\\Microsoft\\Windows\\SysTask", "is_microsoft": True, "status": "Ready"},
    ]
    user_only = get_user_tasks(include_microsoft=False)
    assert len(user_only) == 1
    assert user_only[0]["task_name"] == "\\UserTask"

    all_t = get_user_tasks(include_microsoft=True)
    assert len(all_t) == 2


@patch("actions.task_scheduler_sentinel._query_all_tasks")
def test_get_running_scheduled_tasks(mock_query):
    mock_query.return_value = [
        {"task_name": "\\Task1", "status": "Ready"},
        {"task_name": "\\Task2", "status": "Running"},
        {"task_name": "\\Task3", "status": "Disabled"},
    ]
    running = get_running_scheduled_tasks()
    assert len(running) == 1
    assert running[0]["task_name"] == "\\Task2"


@patch("actions.task_scheduler_sentinel._query_all_tasks")
def test_search_tasks(mock_query):
    mock_query.return_value = [
        {"task_name": "\\LenovoSync"},
        {"task_name": "\\BackupScript"},
        {"task_name": "\\WindowsUpdate"},
    ]
    matches = search_tasks("backup")
    assert len(matches) == 1
    assert matches[0]["task_name"] == "\\BackupScript"

    assert search_tasks("") == []


@patch("subprocess.run")
def test_get_task_details(mock_run):
    mock_run.return_value = MagicMock(returncode=0, stdout=_MOCK_VERBOSE_TASK)
    details = get_task_details("\\MyBackupJob")
    assert details["task_name"] == "\\MyBackupJob"
    assert details["status"] == "Ready"
    assert details["author"] == "Sajan"
    assert details["last_result"] == "0"


@patch("actions.task_scheduler_sentinel._query_all_tasks")
def test_get_scheduler_summary(mock_query):
    mock_query.return_value = [
        {"task_name": "\\UserJob1", "folder": "Root", "next_run_time": "Tomorrow", "status": "Ready", "is_microsoft": False},
        {"task_name": "\\UserJob2", "folder": "Root", "next_run_time": "N/A", "status": "Running", "is_microsoft": False},
        {"task_name": "\\Microsoft\\Task", "folder": "Microsoft", "next_run_time": "N/A", "status": "Ready", "is_microsoft": True},
    ]
    summary = get_scheduler_summary()
    assert summary["total_tasks_registered"] == 3
    assert summary["user_and_app_tasks_count"] == 2
    assert summary["running_tasks_count"] == 1
    assert len(summary["upcoming_tasks"]) == 1


def test_task_scheduler_sentinel_actions():
    res_raw = task_scheduler_sentinel({"action": "summary"})
    res = json.loads(res_raw)
    assert res["status"] == "success"
    assert "data" in res

    err_raw = task_scheduler_sentinel({"action": "unknown_action"})
    err = json.loads(err_raw)
    assert err["status"] == "error"


def test_fast_reflex_scheduled_tasks():
    router = FastReflexRouter()
    intent, score = router.match("check scheduled tasks")
    assert intent == "SCHEDULED_TASKS_QUERY"
    assert score >= 0.88

    res = router.execute_intent("SCHEDULED_TASKS_QUERY")
    assert res.matched is True
    assert "Task Scheduler has" in res.ack
