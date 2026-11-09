"""Tests for OpenCode visible terminal mode, live streaming, and dynamic task modification.
Created and developed by Sajan Rai for Zaya.
"""
from __future__ import annotations

import os
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

os.environ.setdefault("TRUST_LOCAL_OWNER", "1")

from core.coding_jobs import CodingJob, CodingJobs, _stream_write
from tools.opencode_live_terminal import get_stream_path, stream_log
from actions.coding_job import coding_job


@pytest.fixture
def temp_store(tmp_path):
    store_file = tmp_path / "coding_jobs.json"
    return str(store_file)


class TestVisibleTerminalData:
    def test_job_has_visible_and_modifications(self):
        job = CodingJob(id="job123", project="/dummy", goal="build app", visible=True)
        assert job.visible is True
        assert job.pending_modifications == []

        public_dict = job.public()
        assert public_dict["visible"] is True
        assert "pending_modifications" in public_dict


class TestLiveStreamWriter:
    def test_stream_write_appends_to_log(self, tmp_path):
        job_id = "test_stream_job"
        log_path = get_stream_path(job_id)
        if log_path.exists():
            log_path.unlink()

        try:
            _stream_write(job_id, "Line 1: Started pass")
            _stream_write(job_id, "Line 2: Executing tool")

            assert log_path.exists()
            content = log_path.read_text(encoding="utf-8")
            assert "Line 1: Started pass" in content
            assert "Line 2: Executing tool" in content
        finally:
            if log_path.exists():
                log_path.unlink()

    def test_stream_log_once_reads_existing(self, capsys):
        job_id = "test_once_job"
        log_path = get_stream_path(job_id)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text("Tool: shell npm test\n[OUTPUT] tests passed\n", encoding="utf-8")

        try:
            stream_log(job_id, once=True)
            captured = capsys.readouterr().out
            assert "ZAYA OPENCODE LIVE TERMINAL" in captured
            assert "Tool: shell npm test" in captured
            assert "[OUTPUT] tests passed" in captured
        finally:
            if log_path.exists():
                log_path.unlink()


class TestDynamicModification:
    def test_modify_empty_task_raises(self, temp_store):
        jobs = CodingJobs(store_path=temp_store)
        with pytest.raises(ValueError, match="Tell me what you want to modify"):
            jobs.modify("")

    def test_modify_without_sessions_raises(self, temp_store):
        jobs = CodingJobs(store_path=temp_store)
        with pytest.raises(ValueError, match="no coding session to modify"):
            jobs.modify("Add unit tests")

    def test_modify_appends_to_goal_and_pending(self, temp_store, tmp_path):
        proj_dir = tmp_path / "my_project"
        proj_dir.mkdir()
        (proj_dir / "app.py").write_text("print('hello')")

        jobs = CodingJobs(store_path=temp_store)

        with patch("core.coding_jobs.prepare_workspace", return_value=proj_dir), \
             patch("core.coding_jobs.resolve_project", return_value=proj_dir), \
             patch.object(jobs, "_begin"):
            job = jobs.start(str(proj_dir), "Build feature A", visible=True)
            assert job.visible is True

            job.phase = "working"
            jobs.modify("Also support dark mode")

            assert "Owner modification: Also support dark mode" in job.goal
            assert "Also support dark mode" in job.pending_modifications

    def test_modify_resumes_paused_or_completed_session(self, temp_store, tmp_path):
        proj_dir = tmp_path / "test_proj"
        proj_dir.mkdir()
        (proj_dir / "index.js").write_text("console.log(1)")

        jobs = CodingJobs(store_path=temp_store)

        with patch("core.coding_jobs.prepare_workspace", return_value=proj_dir), \
             patch("core.coding_jobs.resolve_project", return_value=proj_dir), \
             patch.object(jobs, "_begin") as mock_begin:
            job = jobs.start(str(proj_dir), "Initial task")
            job.phase = "completed"
            job.session_id = "sess_123"

            jobs.modify("Now add tests")
            assert mock_begin.called
            assert "Now add tests" in job.goal


class TestCodingJobActionModify:
    def test_action_modify_requires_owner(self):
        from core.execution_policy import set_trust, TRUST_UNKNOWN
        set_trust(TRUST_UNKNOWN)
        try:
            res = coding_job({"action": "modify", "task": "Do something"})
            assert res.status == "failed"
            assert "Only the owner" in res.summary
        finally:
            from core.execution_policy import TRUST_LOCAL_OWNER
            set_trust(TRUST_LOCAL_OWNER)

    def test_action_modify_with_owner(self, temp_store, tmp_path):
        proj_dir = tmp_path / "action_proj"
        proj_dir.mkdir()
        (proj_dir / "main.py").write_text("# code")

        with patch("actions.coding_job.get_jobs") as mock_get_jobs, \
             patch("core.coding_jobs.prepare_workspace", return_value=proj_dir):
            mock_jobs = CodingJobs(store_path=temp_store)
            mock_get_jobs.return_value = mock_jobs

            with patch.object(mock_jobs, "_begin"):
                mock_jobs.start(str(proj_dir), "Setup server")

                result = coding_job({"action": "modify", "task": "Use FastAPI instead of Flask"})
                assert result.status == "started"
                assert "Modification accepted" in result.summary
                assert "Use FastAPI instead of Flask" in mock_jobs.latest().goal
