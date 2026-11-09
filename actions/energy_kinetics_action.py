"""Energy Kinetics Action — Predictive Battery & Power Optimization.
Created and developed by Sajan Rai for Zaya.
"""
from __future__ import annotations

import json
from typing import Any, Dict

from core.energy_kinetics import get_energy_kinetics_sentinel


def handle_energy_kinetics(
    action: str = "status",
    apply_recommendation: bool = False,
) -> str:
    """Query battery drain kinetics, runtime forecast, or apply recommended profile."""
    sentinel = get_energy_kinetics_sentinel()

    if action == "status":
        telemetry = sentinel.evaluate_telemetry()
        res = {"status": "success", "telemetry": telemetry.to_dict()}

        if apply_recommendation and telemetry.recommended_profile:
            from actions.computer_settings import set_power_mode
            switch_msg = set_power_mode(telemetry.recommended_profile)
            res["applied_profile"] = telemetry.recommended_profile
            res["switch_result"] = switch_msg

        return json.dumps(res)

    elif action == "forecast":
        telemetry = sentinel.evaluate_telemetry()
        drain = telemetry.drain_rate_pct_per_hr
        hrs = telemetry.estimated_runtime_hours
        msg = f"Battery: {telemetry.percent}%. Drain: {drain:.1f}%/hr. "
        if hrs:
            msg += f"Est. Runtime: {hrs:.1f} hours remaining."
        else:
            msg += "On AC power (charging)."

        return json.dumps({
            "status": "success",
            "message": msg,
            "estimated_runtime_hours": hrs,
            "drain_rate_pct_per_hr": drain,
        })

    return f"Unknown energy kinetics action: '{action}'."


TOOL = {
    "name": "energy_kinetics",
    "description": (
        "Monitor battery drain velocity (%/hr), estimate runtime under current load, "
        "and proactively optimize power schemes between performance, balanced, and battery saver."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "enum": ["status", "forecast"],
                "description": "Energy kinetics action.",
            },
            "apply_recommendation": {
                "type": "BOOLEAN",
                "description": "Whether to automatically switch to the recommended power profile.",
            },
        },
        "required": ["action"],
    },
    "handler": handle_energy_kinetics,
}
