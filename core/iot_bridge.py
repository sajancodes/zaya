"""Smart Home IoT Automation Bridge for Zaya.
Created and developed by Sajan Rai.

Provides unified device control across Home Assistant, MQTT, and local smart devices
(lights, switches, climate, media players, sensors) with simulated fallback support.
"""
from __future__ import annotations

import json
import logging
import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional
import urllib.request
import urllib.error

from core.runtime_paths import mutable_path

logger = logging.getLogger(__name__)

_DEVICES_PATH = mutable_path(Path(__file__).resolve().parent.parent / "memory" / "iot_devices.json")


@dataclass
class SmartDevice:
    entity_id: str
    name: str
    domain: str  # light, switch, climate, media_player, sensor
    state: str = "off"
    attributes: dict[str, Any] = field(default_factory=dict)
    updated_at: float = field(default_factory=time.time)


class IoTBridge:
    """Manages smart home entities and dispatches state controls."""

    def __init__(
        self,
        ha_url: Optional[str] = None,
        ha_token: Optional[str] = None,
        storage_path: Optional[Path] = None,
    ) -> None:
        self.ha_url = (ha_url or "").rstrip("/")
        self.ha_token = ha_token or ""
        self.storage_path = storage_path or _DEVICES_PATH
        self._lock = threading.RLock()
        self._devices: dict[str, SmartDevice] = {}
        self._load_devices()

    def _load_devices(self) -> None:
        with self._lock:
            if self.storage_path.exists():
                try:
                    data = json.loads(self.storage_path.read_text(encoding="utf-8"))
                    for entity_id, raw in data.items():
                        self._devices[entity_id] = SmartDevice(
                            entity_id=entity_id,
                            name=raw.get("name", entity_id),
                            domain=raw.get("domain", entity_id.split(".")[0]),
                            state=raw.get("state", "off"),
                            attributes=raw.get("attributes", {}),
                            updated_at=raw.get("updated_at", time.time()),
                        )
                except Exception as exc:
                    logger.warning("Failed to load IoT devices file: %s", exc)

    def _save_devices(self) -> None:
        with self._lock:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                eid: asdict(dev) for eid, dev in self._devices.items()
            }
            self.storage_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def register_device(
        self,
        entity_id: str,
        name: Optional[str] = None,
        domain: Optional[str] = None,
        initial_state: str = "off",
        attributes: Optional[dict[str, Any]] = None,
    ) -> SmartDevice:
        """Register or update a known smart home device."""
        clean_id = entity_id.strip().lower()
        dom = domain or clean_id.split(".")[0]
        dev_name = name or clean_id.replace("_", " ").title()

        with self._lock:
            dev = SmartDevice(
                entity_id=clean_id,
                name=dev_name,
                domain=dom,
                state=initial_state,
                attributes=attributes or {},
                updated_at=time.time(),
            )
            self._devices[clean_id] = dev
            self._save_devices()
            return dev

    def get_device(self, entity_id: str) -> Optional[SmartDevice]:
        with self._lock:
            return self._devices.get(entity_id.strip().lower())

    def list_devices(self, domain: Optional[str] = None) -> List[SmartDevice]:
        with self._lock:
            if domain:
                clean_dom = domain.strip().lower()
                return [d for d in self._devices.values() if d.domain == clean_dom]
            return list(self._devices.values())

    def control_device(
        self,
        entity_id: str,
        action: str,  # turn_on, turn_off, toggle, set_state
        attributes: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Dispatch control command to Home Assistant or simulated local state."""
        clean_id = entity_id.strip().lower()
        dev = self.get_device(clean_id)
        if not dev:
            # Auto-register device if unknown
            dev = self.register_device(clean_id)

        attrs = attributes or {}
        new_state = dev.state

        if action == "turn_on":
            new_state = "on"
        elif action == "turn_off":
            new_state = "off"
        elif action == "toggle":
            new_state = "off" if dev.state == "on" else "on"
        elif action == "set_state":
            if "state" in attrs:
                new_state = str(attrs.pop("state"))

        # If Home Assistant API is configured, forward REST call
        ha_success = False
        if self.ha_url and self.ha_token:
            ha_success = self._forward_ha_service(dev.domain, action, clean_id, attrs)

        # Update local device state representation
        with self._lock:
            dev.state = new_state
            dev.attributes.update(attrs)
            dev.updated_at = time.time()
            self._save_devices()

        return {
            "entity_id": clean_id,
            "action": action,
            "state": dev.state,
            "attributes": dev.attributes,
            "ha_dispatched": ha_success,
            "updated_at": dev.updated_at,
        }

    def _forward_ha_service(
        self,
        domain: str,
        service: str,
        entity_id: str,
        service_data: dict[str, Any],
    ) -> bool:
        """Call Home Assistant REST API service endpoint."""
        url = f"{self.ha_url}/api/services/{domain}/{service}"
        payload = {"entity_id": entity_id, **service_data}
        data_bytes = json.dumps(payload).encode("utf-8")

        req = urllib.request.Request(
            url,
            data=data_bytes,
            headers={
                "Authorization": f"Bearer {self.ha_token}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=3.0) as resp:
                return resp.status in (200, 201)
        except Exception as exc:
            logger.warning("Failed to reach Home Assistant at %s: %s", url, exc)
            return False


_bridge: Optional[IoTBridge] = None
_bridge_lock = threading.Lock()


def get_iot_bridge() -> IoTBridge:
    global _bridge
    with _bridge_lock:
        if _bridge is None:
            _bridge = IoTBridge()
        return _bridge
