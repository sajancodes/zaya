"""Tests for Zaya Runtime Self-Knowledge and Capability Registry.
Created and developed by Sajan Rai for Zaya.
"""
from __future__ import annotations

import os
from unittest.mock import patch

from core.capability_registry import CapabilityRegistry, get_capability_registry
from actions.capability_action import capability_action


class TestCapabilityRegistry:
    def test_probe_os_environment(self):
        reg = CapabilityRegistry()
        os_info = reg.probe_os_environment()
        assert "os_name" in os_info
        assert "platform_system" in os_info
        assert "python_version" in os_info
        assert isinstance(os_info["is_admin"], bool)

    def test_probe_hardware_safe(self):
        reg = CapabilityRegistry()
        hw = reg.probe_hardware()
        assert hw.displays >= 1
        assert isinstance(hw.has_microphone, bool)
        assert isinstance(hw.has_speaker, bool)

    def test_probe_dependencies(self):
        reg = CapabilityRegistry()
        deps = reg.probe_dependencies()
        assert len(deps) >= 5
        dep_names = {d.name for d in deps}
        assert "numpy" in dep_names
        assert "mss" in dep_names

    def test_snapshot_caching(self):
        reg = CapabilityRegistry()
        s1 = reg.snapshot()
        s2 = reg.snapshot()
        assert s1.timestamp == s2.timestamp  # cached

        s3 = reg.snapshot(force_refresh=True)
        assert s3.timestamp >= s1.timestamp

    def test_can_execute_honest_explanations(self):
        reg = CapabilityRegistry()

        # Simulated missing cv2
        with patch.object(reg, "probe_dependencies") as mock_deps:
            from core.capability_registry import DependencyStatus
            mock_deps.return_value = [DependencyStatus("cv2", available=False, install_hint="pip install opencv-python")]
            can_run, reason = reg.can_execute("camera")
            assert can_run is False
            assert "opencv-python" in reason
            assert "Cannot execute 'camera'" in reg.explain_limitation("camera")

    def test_can_execute_screen_capture(self):
        reg = CapabilityRegistry()
        can_run, reason = reg.can_execute("screen_capture")
        assert can_run is True
        assert "available" in reason


class TestCapabilityAction:
    def test_action_status(self):
        res = capability_action({"action": "status"})
        assert res.status == "success"
        assert "Zaya running on" in res.summary
        assert "hardware" in res.data

    def test_action_check_capability(self):
        res = capability_action({"action": "check", "capability": "screen_capture"})
        assert res.status == "success"
        assert res.data["can_execute"] is True

    def test_action_check_missing_capability(self):
        res = capability_action({"action": "check", "capability": "non_existent_laser_cannon"})
        assert res.status == "partial"
        assert res.data["can_execute"] is False
