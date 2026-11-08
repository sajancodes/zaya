"""Smart Home IoT Automation Action for Zaya.
Created and developed by Sajan Rai.

Controls smart home lights, switches, climate control, and appliances across
Home Assistant, MQTT, and local smart devices.
"""
from __future__ import annotations

from dataclasses import asdict
from typing import Any

from core.execution_policy import require_owner
from core.iot_bridge import get_iot_bridge
from core.tool_result import ToolResult


def smart_home(parameters: dict[str, Any], **_kwargs) -> ToolResult:
    """Execute smart home device control or discovery."""
    require_owner()
    action = str(parameters.get("action", "list")).lower().strip()
    bridge = get_iot_bridge()

    if action == "list":
        domain = parameters.get("domain")
        devices = bridge.list_devices(domain=domain)
        summary = f"Found {len(devices)} smart device(s)."
        return ToolResult(
            "success",
            summary,
            {"devices": [asdict(d) for d in devices]},
        )

    elif action in {"turn_on", "turn_off", "toggle", "set"}:
        entity_id = str(parameters.get("entity_id", "")).strip()
        if not entity_id:
            return ToolResult("failed", "Parameter 'entity_id' is required for device control.", {})

        attrs = parameters.get("attributes") or {}
        if "brightness" in parameters:
            attrs["brightness"] = parameters["brightness"]
        if "temperature" in parameters:
            attrs["temperature"] = parameters["temperature"]

        service_act = "set_state" if action == "set" else action
        res = bridge.control_device(entity_id, action=service_act, attributes=attrs)
        summary = f"Device '{entity_id}' is now {res['state'].upper()}."
        evidence = [{"source": "smart_home", "entity_id": entity_id, "state": res["state"]}]
        return ToolResult("success", summary, res, evidence=evidence, side_effect=True)

    elif action == "register":
        entity_id = str(parameters.get("entity_id", "")).strip()
        if not entity_id:
            return ToolResult("failed", "Parameter 'entity_id' is required to register a device.", {})

        name = parameters.get("name")
        domain = parameters.get("domain")
        initial_state = str(parameters.get("state", "off"))
        attributes = parameters.get("attributes") or {}

        dev = bridge.register_device(
            entity_id=entity_id,
            name=name,
            domain=domain,
            initial_state=initial_state,
            attributes=attributes,
        )
        return ToolResult(
            "success",
            f"Registered smart device '{dev.entity_id}' ({dev.name}).",
            asdict(dev),
            side_effect=True,
        )

    return ToolResult("failed", f"Unknown action '{action}'. Valid actions are 'list', 'turn_on', 'turn_off', 'toggle', 'set', 'register'.", {})


TOOL = {
    "name": "smart_home",
    "description": (
        "Control smart home lights, switches, climate, and appliances via Home Assistant, MQTT, "
        "and local smart devices. Supports listing devices, turning on/off, toggling, and setting attributes."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "enum": ["list", "turn_on", "turn_off", "toggle", "set", "register"],
                "description": "Smart home action to execute: 'list' (default), 'turn_on', 'turn_off', 'toggle', 'set', 'register'.",
            },
            "entity_id": {
                "type": "STRING",
                "description": "Device identifier (e.g., 'light.desk_lamp', 'switch.fan', 'climate.living_room').",
            },
            "domain": {
                "type": "STRING",
                "description": "Optional domain filter (e.g., 'light', 'switch', 'climate').",
            },
            "name": {
                "type": "STRING",
                "description": "Human-readable device name for registration.",
            },
            "brightness": {
                "type": "INTEGER",
                "description": "Brightness percentage (0-100) or value (0-255) for lights.",
            },
            "temperature": {
                "type": "NUMBER",
                "description": "Target temperature in Celsius for climate devices.",
            },
            "attributes": {
                "type": "OBJECT",
                "description": "Additional device attributes or state payload.",
            },
        },
        "required": ["action"],
    },
    "handler": smart_home,
}
