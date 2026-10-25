"""Zaya Canonical Hand Controller.
Created and developed by Sajan Rai for Zaya.

Unifies webcam hand tracking into a single global Windows input layer:
- Desktop mouse movement, left-clicks, two-finger selection, fist scrolling
- Holographic Top Air Keyboard HUD with target application focus tracking
- 3D Spatial workspace mode preservation
"""
from __future__ import annotations

import os
import sys
import threading
import time
from typing import Optional, Tuple

from .gesture_state import InteractionMode
from .gesture_engine import GestureEngine
from .virtual_keyboard import VirtualKeyboard
from .hand_tracker import HandTracker
from .desktop_controller import DesktopController, get_foreground_info


class HandController:
    def __init__(self):
        self.lock = threading.RLock()
        self.mode = InteractionMode.DISABLED
        self.engine = GestureEngine()
        self.keyboard = VirtualKeyboard(self._inject)
        self.desktop = DesktopController()
        self.tracker = HandTracker(self.on_hands)
        self.modifiers = set()
        from .spatial_controller import SpatialController
        self.spatial = SpatialController()
        self.last_start = None
        self.latest_hands = ()
        self.current_gesture = "NONE"
        self.latest_packet = {}
        self.keyboard_visible = False

    def _inject(self, key):
        if self.mode != InteractionMode.KEYBOARD and not self.keyboard_visible:
            return False

        # Ensure we never inject into Zaya itself or when foreground is invalid
        info = get_foreground_info()
        if info.get("is_zaya") or (os.name == "nt" and info.get("pid") in (0, os.getpid())):
            return False

        from actions.ghost_keyboard import inject_text, send_hotkey

        if key.modifier:
            mod_name = key.output.lower()
            if mod_name in self.modifiers:
                self.modifiers.remove(mod_name)
            else:
                self.modifiers.add(mod_name)
            return "latched"

        output = key.output.lower()
        if self.modifiers:
            hotkey_str = "+".join(sorted(self.modifiers)) + "+" + output
            result = send_hotkey(hotkey_str)
            self.modifiers.clear()
            return result

        # Special hotkeys
        if output in ("backspace", "enter", "space", "tab", "esc", "left", "right", "up", "down"):
            return send_hotkey(output)

        # Single characters
        return inject_text(key.output.lower(), 0) if len(output) == 1 else send_hotkey(output)

    def toggle_keyboard(self, visible: Optional[bool] = None) -> bool:
        with self.lock:
            if visible is None:
                self.keyboard_visible = not self.keyboard_visible
            else:
                self.keyboard_visible = bool(visible)
            from core.ghost_overlay import update_passive_overlay
            update_passive_overlay({"visible": self.keyboard_visible, "mode": "virtual_keyboard"})
            return self.keyboard_visible

    def on_hands(self, hands):
        from core.ghost_overlay import update_passive_overlay

        with self.lock:
            self.latest_hands = tuple(hands)
            if not hands:
                self.desktop.on_tracking_lost()
                self.modifiers.clear()
                self.keyboard.reset()
                self.current_gesture = "NONE"
                self.latest_packet = {
                    "mode": self.mode.value,
                    "visible": self.keyboard_visible and self.mode in (InteractionMode.KEYBOARD, InteractionMode.NAVIGATION),
                }
                update_passive_overlay(self.latest_packet)
                return

            now = hands[0].timestamp if hands else time.monotonic()
            events = self.engine.update(hands, now)
            hand = hands[0]
            state = self.engine.states.get(hand.hand_id)
            candidate_pose = state[0] if state else "NONE"
            stable = bool(state and state[2])
            desktop_pose = candidate_pose if stable else "NONE"
            self.current_gesture = candidate_pose if stable else f"({candidate_pose})"

            self.desktop.update_target_info()
            mon_left, mon_top, mon_right, mon_bottom = self.desktop.monitor_rect
            mon_w = max(800, mon_right - mon_left)
            mon_h = max(600, mon_bottom - mon_top)
            hud_w = min(1180, int(mon_w * 0.85))
            hud_h = min(240, int(mon_h * 0.28))
            hud_x1 = mon_left + (mon_w - hud_w) // 2
            hud_x2 = hud_x1 + hud_w
            hud_y1 = mon_top + 8
            hud_y2 = hud_y1 + hud_h

            tip = hand.landmarks[8]
            target_px_x, target_px_y = self.desktop.map_coords(tip.x, tip.y)
            smooth_x, smooth_y = self.desktop.smooth_pointer(target_px_x, target_px_y)

            keyboard_active = (self.mode == InteractionMode.KEYBOARD) or (
                self.keyboard_visible and self.mode == InteractionMode.NAVIGATION
            )
            inside_keyboard = keyboard_active and (hud_x1 <= smooth_x <= hud_x2) and (hud_y1 <= smooth_y <= hud_y2)

            if inside_keyboard:
                if self.desktop.is_selecting or self.desktop.is_dragging:
                    self.desktop.on_tracking_lost()

                header_h = 32
                keys_x = 10
                keys_w = hud_w - 20
                keys_y = header_h + 4
                keys_h = hud_h - keys_y - 8
                local_x = smooth_x - hud_x1
                local_y = smooth_y - hud_y1
                norm_kx = max(0.0, min(1.0, (local_x - keys_x) / max(1.0, keys_w)))
                norm_ky = max(0.0, min(1.0, (local_y - keys_y) / max(1.0, keys_h)))

                sent = self.keyboard.update(hand, rel_pos=(norm_kx, norm_ky))

                poke_occurred = any(e.type == "POKE" and e.metadata.get("phase") == "enter" for e in events)
                index_enter = any(e.type == "INDEX_ONLY" and e.metadata.get("phase") == "enter" for e in events)
                if not sent and (poke_occurred or index_enter) and self.keyboard.key:
                    sent = self.keyboard.strike()

                if desktop_pose == "THUMBS_UP" and stable:
                    if self.desktop.enter_armed and (now - self.desktop.last_enter_time > self.desktop.enter_cooldown):
                        from actions.ghost_keyboard import send_hotkey

                        send_hotkey("enter")
                        self.desktop.enter_armed = False
                        self.desktop.last_enter_time = now
                        sent = "Enter"
                elif desktop_pose == "OPEN_PALM" and stable:
                    self.desktop.enter_armed = True

                packet = {
                    "mode": "virtual_keyboard",
                    "visible": True,
                    "state": self.keyboard.state,
                    "key": self.keyboard.key.id if self.keyboard.key else "",
                    "sent": sent or "",
                    "error": self.keyboard.error,
                    "modifiers": sorted(self.modifiers),
                    "hovered": self.keyboard.key.id if self.keyboard.key else "",
                    "cursor_rel": (norm_kx, norm_ky),
                    "target": self.desktop.target_info,
                    "selected_part": getattr(self.spatial, "selected_part", ""),
                }
                self.latest_packet = packet
                update_passive_overlay(packet)

            else:
                if self.keyboard.state != "idle":
                    self.keyboard.reset()

                if keyboard_active:
                    packet = {
                        "mode": "virtual_keyboard",
                        "visible": True,
                        "state": "idle",
                        "key": "",
                        "sent": "",
                        "error": "",
                        "modifiers": sorted(self.modifiers),
                        "hovered": "",
                        "cursor_rel": None,
                        "target": self.desktop.target_info,
                        "selected_part": getattr(self.spatial, "selected_part", ""),
                    }
                    self.latest_packet = packet
                    update_passive_overlay(packet)
                else:
                    self.latest_packet = {
                        "mode": self.mode.value,
                        "visible": False,
                        "selected_part": getattr(self.spatial, "selected_part", ""),
                    }

                if self.mode in (InteractionMode.NAVIGATION, InteractionMode.KEYBOARD):
                    self.desktop.handle_frame(hand, desktop_pose, now, stable=stable, events=events)

                if self.mode in (InteractionMode.SPATIAL, InteractionMode.SELECTION):
                    # Spatial mode isolation: global desktop input is NOT dispatched in SPATIAL
                    self.spatial.update(hands, events, self.engine, self.mode == InteractionMode.SELECTION)

    def stop(self):
        with self.lock:
            self.mode = InteractionMode.DISABLED
            self.modifiers.clear()
            self.keyboard.reset()
            self.desktop.on_tracking_lost()
            self.engine.states.clear()
            self.engine.pokes.clear()
            self.engine.previous.clear()
            self.engine.rotations.clear()
            self.engine.two = None
            self.latest_hands = ()
            self.current_gesture = "NONE"
            self.latest_packet = {}
        self.tracker.stop()
        from core.ghost_overlay import update_passive_overlay
        update_passive_overlay({"visible": False, "mode": "virtual_keyboard"})

    def set_mode(self, mode, sensitivity=None):
        requested = InteractionMode(mode)
        if requested not in (InteractionMode.NAVIGATION, InteractionMode.KEYBOARD, InteractionMode.SPATIAL, InteractionMode.SELECTION):
            raise ValueError("Choose a supported interaction mode.")
        with self.lock:
            old_mode = self.mode
            if old_mode == requested:
                return
            self.desktop.on_tracking_lost()
            if old_mode == InteractionMode.KEYBOARD:
                self.modifiers.clear()
                self.keyboard.reset()
                self.keyboard_visible = False
                from core.ghost_overlay import update_passive_overlay
                update_passive_overlay({"visible": False, "mode": "virtual_keyboard"})
            if requested == InteractionMode.KEYBOARD:
                self.keyboard_visible = True
                if sensitivity is not None:
                    from .calibration import Calibration
                    self.keyboard.config = Calibration(press=0.2 / sensitivity, release=0.07 / sensitivity, min_velocity=0.8 / sensitivity)
                from core.ghost_overlay import update_passive_overlay
                update_passive_overlay({"visible": True, "mode": "virtual_keyboard"})
            self.mode = requested
            if self.last_start:
                ls = list(self.last_start)
                ls[1] = requested.value
                self.last_start = tuple(ls)

    def start(self, model_path, mode, device=0, fps=24, mirror=True, confidence=0.65, sensitivity=1.0, timeout=12.0):
        requested = InteractionMode(mode)
        if requested not in (InteractionMode.NAVIGATION, InteractionMode.KEYBOARD, InteractionMode.SPATIAL, InteractionMode.SELECTION):
            raise ValueError("Choose a supported interaction mode.")
        with self.lock:
            if self.tracker.state == "ACTIVE" and self.last_start and self.last_start[2] == int(device):
                self.set_mode(requested, sensitivity)
                return
            self.stop()
            self.mode = requested
            from .calibration import Calibration
            self.keyboard.config = Calibration(press=0.2 / sensitivity, release=0.07 / sensitivity, min_velocity=0.8 / sensitivity)
            try:
                self.tracker.start(model_path, device, fps, mirror, confidence)
                self.last_start = (model_path, mode, device, fps, mirror, confidence, sensitivity)
            except Exception:
                self.mode = InteractionMode.DISABLED
                raise
        if timeout:
            self.tracker.wait_active(timeout)

    def pause(self):
        self.stop()
        self.tracker.state = "PAUSED"

    def resume(self):
        if self.tracker.state != "PAUSED" or not self.last_start:
            raise ValueError("No paused hand session to resume.")
        from .settings import load
        settings = load()
        self.start(self.last_start[0], self.last_start[1], settings.device, settings.fps, settings.mirror, settings.confidence, settings.sensitivity)

    def status(self):
        with self.lock:
            return {
                "mode": self.mode.value,
                "camera": self.tracker.state,
                "error": self.tracker.error,
                "keyboard": self.keyboard.state,
                "keyboard_visible": self.keyboard_visible,
                "injection_error": self.keyboard.error,
                "gesture": self.current_gesture,
                "hands_count": len(self.latest_hands),
                "hovered": self.keyboard.key.id if self.keyboard.key else "",
                "modifiers": sorted(self.modifiers),
                "selected_part": getattr(self.spatial, "selected_part", ""),
                "target": self.desktop.target_info,
            }


hands = HandController()
