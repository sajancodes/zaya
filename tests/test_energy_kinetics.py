"""Tests for Predictive Energy Kinetics & Battery Optimization Sentinel (Cycle 77).
Created and developed by Sajan Rai for Zaya.
"""
from __future__ import annotations

import json
import time
from unittest.mock import patch
import pytest

from core.energy_kinetics import EnergyKineticsSentinel, BatterySnapshot, PowerTelemetry
from actions.energy_kinetics_action import handle_energy_kinetics
from core.execution_policy import with_trust, TRUST_LOCAL_OWNER


class TestEnergyKinetics:
    def test_drain_rate_calculation(self):
        sentinel = EnergyKineticsSentinel()
        t0 = time.time()

        # Simulate 10% battery loss over 30 minutes (0.5 hours) -> 20%/hr
        with patch("time.time", side_effect=[t0, t0 + 1800.0]):
            sentinel.record_snapshot(percent=80.0, power_plugged=False)
            sentinel.record_snapshot(percent=70.0, power_plugged=False)

            drain = sentinel.calculate_drain_rate()
            assert 19.5 <= drain <= 20.5

    def test_plugged_ac_has_zero_drain(self):
        sentinel = EnergyKineticsSentinel()
        sentinel.record_snapshot(percent=90.0, power_plugged=True)
        sentinel.record_snapshot(percent=95.0, power_plugged=True)

        assert sentinel.calculate_drain_rate() == 0.0

    def test_telemetry_recommendation_logic(self):
        sentinel = EnergyKineticsSentinel()

        # Plugged in -> Performance
        with patch.object(sentinel, "query_live_battery", return_value=(85.0, True, None)), \
             patch("actions.computer_settings.get_power_mode", return_value="balanced"):
            t_plugged = sentinel.evaluate_telemetry()
            assert t_plugged.recommended_profile == "performance"

        # Low battery unplugged (< 20%) -> Battery Saver
        with patch.object(sentinel, "query_live_battery", return_value=(14.0, False, 1800)), \
             patch("actions.computer_settings.get_power_mode", return_value="balanced"):
            t_low = sentinel.evaluate_telemetry()
            assert t_low.recommended_profile == "battery_saver"

    def test_proactive_event_dispatch_on_low_battery(self):
        sentinel = EnergyKineticsSentinel()
        sentinel.alert_cooldown_sec = 0.0

        with patch.object(sentinel, "query_live_battery", return_value=(10.0, False, 1200)), \
             patch("core.event_bus.bus.publish") as mock_pub, \
             patch("actions.computer_settings.get_power_mode", return_value="balanced"):
            sentinel.evaluate_telemetry()
            assert mock_pub.called
            assert mock_pub.call_args[0][0] == "power.low_battery"


class TestEnergyKineticsAction:
    def test_action_status_and_forecast(self):
        with with_trust(TRUST_LOCAL_OWNER):
            res = handle_energy_kinetics(action="status")
            data = json.loads(res)
            assert data["status"] == "success"
            assert "telemetry" in data
            assert "percent" in data["telemetry"]

            forecast_res = handle_energy_kinetics(action="forecast")
            forecast_data = json.loads(forecast_res)
            assert forecast_data["status"] == "success"
            assert "message" in forecast_data
