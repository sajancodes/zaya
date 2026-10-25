"""Comprehensive tests for Zaya Unified Global Hand Input System.
Covers:
- Canonical gesture classification (TWO_FINGER, THUMBS_UP, FIST, OPEN_PALM, INDEX_ONLY, PINCH)
- Precedence ordering and stability
- DesktopController coordinate mapping, velocity-adaptive smoothing, and dead zone filtering
- Debounced left-click, two-finger text selection drag, fist scroll, thumbs-up enter
- Lost tracking safety (guaranteed mouse-up and scroll cessation)
- Selection context store and 3-tier text extraction (UIA -> Clipboard -> OCR)
- Non-destructive clipboard backup & restore
- Target app detection and Zaya PID injection safety
- Holographic Air Keyboard HUD non-activating flags & contextual hand switching
"""
from __future__ import annotations

import os
import time
from dataclasses import replace
from unittest.mock import MagicMock, patch

import pytest

from core.gesture.gesture_engine import GestureEngine
from core.gesture.hand_model import HandState, Point
from core.gesture.desktop_controller import DesktopController, get_foreground_info
from core.selection.context import SelectionContext, SelectionManager, get_selection_manager
from core.selection.selected_text import get_selected_text
from actions.read_selected_text import read_selected_text


def make_hand(
    t: float,
    finger_states=(False, True, False, False, False),
    pinch_dist: float = 0.5,
    thumb_y: float = 0.5,
    mcp_y: float = 0.6,
    wrist_y: float = 0.8,
    tip_x: float = 0.5,
    tip_y: float = 0.5,
    palm_z: float = 0.0,
) -> HandState:
    points = [Point(tip_x, tip_y, palm_z) for _ in range(21)]
    # Landmark 0: wrist
    points[0] = Point(tip_x, wrist_y, palm_z)
    # Landmark 2: thumb MCP
    points[2] = Point(tip_x - 0.05, mcp_y, palm_z)
    # Landmark 4: thumb tip
    points[4] = Point(tip_x - 0.05, thumb_y, palm_z)
    # Landmark 8: index tip
    points[8] = Point(tip_x, tip_y, palm_z)

    return HandState(
        hand_id="Right",
        handedness="Right",
        landmarks=tuple(points),
        world_landmarks=(),
        palm_center=Point(tip_x, tip_y + 0.1, palm_z),
        palm_normal=Point(0, 0, -1),
        finger_states=finger_states,
        velocity=Point(0, 0, 0),
        confidence=0.95,
        timestamp=t,
        relative_depth=0.0,
        pinch_distance=pinch_dist,
    )


# ============================================================================
# 1. GESTURE ENGINE CLASSIFICATION & PRECEDENCE
# ============================================================================

def test_two_finger_gesture_classification():
    """Index + Middle extended, Ring + Pinky folded -> TWO_FINGER."""
    engine = GestureEngine(stability=0.05)
    # finger_states: thumb=False, index=True, middle=True, ring=False, pinky=False
    h1 = make_hand(1.0, finger_states=(False, True, True, False, False))
    assert engine.update((h1,), 1.0) == []
    h2 = make_hand(1.08, finger_states=(False, True, True, False, False))
    events = engine.update((h2,), 1.08)
    assert len(events) >= 1
    assert events[0].type == "TWO_FINGER"
    assert events[0].metadata["phase"] == "enter"


def test_thumbs_up_gesture_classification():
    """Thumb extended with tip above MCP (y_tip < y_mcp in screen coords) -> THUMBS_UP."""
    engine = GestureEngine(stability=0.05)
    # Thumb tip at y=0.3, MCP at y=0.6 -> thumb points up!
    h1 = make_hand(
        1.0,
        finger_states=(True, False, False, False, False),
        thumb_y=0.3,
        mcp_y=0.6,
    )
    assert engine.update((h1,), 1.0) == []
    h2 = make_hand(
        1.08,
        finger_states=(True, False, False, False, False),
        thumb_y=0.3,
        mcp_y=0.6,
    )
    events = engine.update((h2,), 1.08)
    assert len(events) >= 1
    assert events[0].type == "THUMBS_UP"


def test_fist_gesture_classification():
    """All fingers folded and thumb not pointing up -> FIST."""
    engine = GestureEngine(stability=0.05)
    # Thumb tip at y=0.7, MCP at y=0.6 (thumb down/folded)
    h1 = make_hand(
        1.0,
        finger_states=(False, False, False, False, False),
        thumb_y=0.7,
        mcp_y=0.6,
    )
    assert engine.update((h1,), 1.0) == []
    h2 = make_hand(
        1.08,
        finger_states=(False, False, False, False, False),
        thumb_y=0.7,
        mcp_y=0.6,
    )
    events = engine.update((h2,), 1.08)
    assert len(events) >= 1
    assert events[0].type == "FIST"


def test_open_palm_gesture_classification():
    """All 4 main fingers extended -> OPEN_PALM."""
    engine = GestureEngine(stability=0.05)
    h1 = make_hand(1.0, finger_states=(False, True, True, True, True))
    assert engine.update((h1,), 1.0) == []
    h2 = make_hand(1.08, finger_states=(False, True, True, True, True))
    events = engine.update((h2,), 1.08)
    assert len(events) >= 1
    assert events[0].type == "OPEN_PALM"


def test_pinch_precedence_over_open_hand():
    """If pinch_distance < 0.25, PINCH takes precedence."""
    engine = GestureEngine(stability=0.05)
    h1 = make_hand(1.0, finger_states=(True, True, True, True, True), pinch_dist=0.15)
    assert engine.update((h1,), 1.0) == []
    h2 = make_hand(1.08, finger_states=(True, True, True, True, True), pinch_dist=0.15)
    events = engine.update((h2,), 1.08)
    assert len(events) >= 1
    assert events[0].type == "PINCH"


# ============================================================================
# 2. DESKTOP CONTROLLER MAPPING, SMOOTHING & SAFETY
# ============================================================================

def test_desktop_controller_mapping_and_clamping():
    dc = DesktopController(screen_size=(1920, 1080))
    # Active box is (0.12, 0.12, 0.88, 0.88)
    # Center (0.5, 0.5) should map to middle of screen
    x, y = dc.map_coords(0.5, 0.5)
    assert 950 <= x <= 970
    assert 530 <= y <= 550

    # Bounds outside active box clamp to screen edges
    x_min, y_min = dc.map_coords(0.0, 0.0)
    assert x_min == 0 and y_min == 0
    x_max, y_max = dc.map_coords(1.0, 1.0)
    assert x_max == 1919 and y_max == 1079


def test_desktop_controller_smoothing_and_dead_zone():
    dc = DesktopController(screen_size=(1920, 1080))
    dc.curr_x, dc.curr_y = 500.0, 500.0

    # Small displacement (< 2.0 px dead zone) is ignored
    sx, sy = dc.smooth_pointer(501, 501)
    assert sx == 500 and sy == 500

    # Larger displacement moves smoothly towards target
    sx, sy = dc.smooth_pointer(700, 700)
    assert 500 < sx < 700
    assert 500 < sy < 700


def test_desktop_controller_debounced_click():
    dc = DesktopController(screen_size=(1920, 1080))
    clicks = []
    dc._mouse_click = lambda: clicks.append(1)
    dc._set_cursor_pos = lambda x, y: None

    hand = make_hand(1.0, tip_x=0.5, tip_y=0.5)

    # First INDEX_ONLY triggers single click
    dc.handle_frame(hand, "INDEX_ONLY", 1.0)
    assert len(clicks) == 1

    # Immediate subsequent INDEX_ONLY within debounce cooldown does NOT click again
    dc.handle_frame(hand, "INDEX_ONLY", 1.1)
    assert len(clicks) == 1

    # Transitioning to OPEN_PALM re-arms click
    dc.handle_frame(hand, "OPEN_PALM", 1.2)
    assert dc.click_armed is True

    # After cooldown and re-arm, new INDEX_ONLY clicks again
    dc.handle_frame(hand, "INDEX_ONLY", 1.5)
    assert len(clicks) == 2


def test_desktop_controller_two_finger_selection():
    dc = DesktopController(screen_size=(1920, 1080))
    downs, ups, cursor_moves = [], [], []
    dc._mouse_down = lambda: downs.append(1)
    dc._mouse_up = lambda: ups.append(1)
    dc._set_cursor_pos = lambda x, y: cursor_moves.append((x, y))

    get_selection_manager().clear()

    # Enter TWO_FINGER selection
    h1 = make_hand(1.0, tip_x=0.4, tip_y=0.4)
    dc.handle_frame(h1, "TWO_FINGER", 1.0)
    assert dc.is_selecting is True
    assert len(downs) == 1
    assert len(ups) == 0

    # Update TWO_FINGER drag
    h2 = make_hand(1.05, tip_x=0.6, tip_y=0.6)
    dc.handle_frame(h2, "TWO_FINGER", 1.05)
    assert dc.is_selecting is True
    assert len(downs) == 1
    assert len(ups) == 0

    # Exit TWO_FINGER to OPEN_PALM
    h3 = make_hand(1.1, tip_x=0.6, tip_y=0.6)
    dc.handle_frame(h3, "OPEN_PALM", 1.1)
    assert dc.is_selecting is False
    assert len(ups) == 1

    # Selection context must have been saved in SelectionManager
    ctx = get_selection_manager().get_selection()
    assert ctx is not None
    assert ctx.width > 0 and ctx.height > 0


def test_desktop_controller_lost_tracking_safety():
    """Lost tracking during selection or scroll MUST immediately release mouse and halt scroll."""
    dc = DesktopController(screen_size=(1920, 1080))
    ups = []
    dc._mouse_down = lambda: None
    dc._mouse_up = lambda: ups.append(1)
    dc._set_cursor_pos = lambda x, y: None

    # Start selection
    h1 = make_hand(1.0, tip_x=0.3, tip_y=0.3)
    dc.handle_frame(h1, "TWO_FINGER", 1.0)
    assert dc.is_selecting is True

    # Tracking lost (hand is None)
    dc.handle_frame(None, "NONE", 1.1)
    assert dc.is_selecting is False
    assert len(ups) == 1  # Mouse button released!


def test_desktop_controller_fist_scroll_and_halt():
    dc = DesktopController(screen_size=(1920, 1080))
    wheels = []
    dc._mouse_wheel = lambda delta: wheels.append(delta)
    dc._set_cursor_pos = lambda x, y: None

    # Enter FIST -> baseline locked
    h1 = make_hand(1.0, tip_y=0.4)
    dc.handle_frame(h1, "FIST", 1.0)
    assert dc.is_scrolling is True
    assert len(wheels) == 0

    # Move fist downwards -> scrolls down (negative delta)
    h2 = make_hand(1.06, tip_y=0.55)
    dc.handle_frame(h2, "FIST", 1.06)
    assert len(wheels) == 1
    assert wheels[0] < 0

    # Hand opens to OPEN_PALM -> scrolling halts immediately
    h3 = make_hand(1.1, tip_y=0.55)
    dc.handle_frame(h3, "OPEN_PALM", 1.1)
    assert dc.is_scrolling is False
    assert dc.scroll_baseline_y is None


# ============================================================================
# 3. SELECTION CONTEXT & THREE-TIER TEXT RETRIEVAL
# ============================================================================

def test_selection_context_ttl_expiration():
    ctx = SelectionContext(
        start=(100, 100),
        end=(300, 200),
        rect=(100, 100, 300, 200),
        timestamp=time.time() - 400.0,
    )
    assert ctx.is_valid(ttl_seconds=300.0) is False

    fresh_ctx = SelectionContext(
        start=(100, 100),
        end=(300, 200),
        rect=(100, 100, 300, 200),
        timestamp=time.time(),
    )
    assert fresh_ctx.is_valid(ttl_seconds=300.0) is True


def test_get_selected_text_fallback_chain(monkeypatch):
    """Verifies UIA -> Clipboard -> OCR fallback order."""
    get_selection_manager().clear()

    # 1. Tier 1: UIA returns text directly
    monkeypatch.setattr("core.selection.selected_text._extract_via_uia", lambda: "UIA Text")
    assert get_selected_text() == "UIA Text"

    # 2. Tier 2: UIA empty, Clipboard returns text
    get_selection_manager().clear()
    monkeypatch.setattr("core.selection.selected_text._extract_via_uia", lambda: "")
    monkeypatch.setattr("core.selection.selected_text._extract_via_clipboard", lambda: "Clipboard Text")
    assert get_selected_text() == "Clipboard Text"

    # 3. Tier 3: UIA & Clipboard empty, OCR returns text from context rect
    get_selection_manager().clear()
    monkeypatch.setattr("core.selection.selected_text._extract_via_clipboard", lambda: "")
    monkeypatch.setattr("core.selection.selected_text._extract_via_ocr", lambda ctx: "OCR Text")
    ctx = SelectionContext(start=(10, 10), end=(200, 100), rect=(10, 10, 200, 100))
    get_selection_manager().set_selection(ctx)
    assert get_selected_text(ctx) == "OCR Text"


def test_non_destructive_clipboard_restoration(monkeypatch):
    """Clipboard extraction must preserve the user's pre-existing clipboard contents."""
    from core.selection.selected_text import _extract_via_clipboard
    import sys

    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr("core.selection.selected_text._snapshot_windows_clipboard", lambda: [])
    monkeypatch.setattr("core.selection.selected_text._restore_windows_clipboard", lambda s: False)

    fake_clipboard = {"text": "UserOriginalData"}

    def fake_paste():
        return fake_clipboard["text"]

    def fake_copy(val):
        fake_clipboard["text"] = val

    import pyperclip
    monkeypatch.setattr(pyperclip, "paste", fake_paste)
    monkeypatch.setattr(pyperclip, "copy", fake_copy)

    # When Ctrl+C is simulated, target app writes "NewlyCopiedData"
    def fake_hotkey(hotkey):
        if hotkey == "ctrl+c":
            fake_clipboard["text"] = "NewlyCopiedData"
        return True

    monkeypatch.setattr("actions.ghost_keyboard.send_hotkey", fake_hotkey)

    result = _extract_via_clipboard()
    assert result == "NewlyCopiedData"
    # User's original clipboard MUST be restored!
    assert fake_clipboard["text"] == "UserOriginalData"


def test_read_selected_text_action(monkeypatch):
    spoken = []
    ctx = SelectionContext(
        start=(50, 50),
        end=(250, 150),
        rect=(50, 50, 250, 150),
        target_app="VS Code",
        cached_text="def hello_world(): return 42",
    )
    get_selection_manager().set_selection(ctx)

    monkeypatch.setattr("actions.read_selected_text.require_owner", lambda: None)
    result = read_selected_text({}, speak=lambda txt: spoken.append(txt))

    assert result.status == "success"
    assert "def hello_world()" in result.data["text"]
    assert spoken == ["def hello_world(): return 42"]


# ============================================================================
# 4. TARGET APP DETECTION & ZAYA PID SAFETY
# ============================================================================

def test_target_app_detection_and_zaya_block():
    fake_info = {
        "app": "Zaya",
        "title": "Zaya Main Window",
        "pid": os.getpid(),
        "is_zaya": True,
    }
    with patch("core.gesture.controller.get_foreground_info", return_value=fake_info):
        from core.gesture.controller import HandController
        from core.gesture.virtual_keyboard import VirtualKey
        from core.gesture.gesture_state import InteractionMode

        controller = HandController()
        controller.mode = InteractionMode.KEYBOARD
        controller.keyboard_visible = True
        test_key = VirtualKey("A", "A", "A", (0, 0, 0.1, 0.2), 0)
        assert controller._inject(test_key) is False


# ============================================================================
# 5. CONTEXTUAL HAND SWITCHING (KEYBOARD VS DESKTOP)
# ============================================================================

def test_contextual_hand_switching():
    from core.gesture.controller import HandController
    from core.gesture.gesture_state import InteractionMode

    hc = HandController()
    hc.mode = InteractionMode.NAVIGATION
    hc.keyboard_visible = True

    # Screen: 1920 x 1080.
    # Top HUD Keyboard is located at: y in [0, 250], x in [~144, ~1776]
    # Mapped from normalized tip: tip_y=0.15 maps into top 15% (inside HUD)
    h_top = make_hand(1.0, tip_x=0.5, tip_y=0.15)
    # tip_y=0.7 maps into lower screen (outside HUD)
    h_bottom = make_hand(1.0, tip_x=0.5, tip_y=0.7)

    with patch("core.ghost_overlay.update_passive_overlay") as mock_overlay:
        # Hand in top area -> inside HUD
        hc.on_hands((h_top,))
        assert mock_overlay.called
        last_packet = mock_overlay.call_args[0][0]
        assert last_packet.get("visible") is True
        assert last_packet.get("mode") == "virtual_keyboard"
        # cursor_rel is populated when over keyboard
        assert last_packet.get("cursor_rel") is not None

        # Hand in bottom area -> outside HUD
        hc.on_hands((h_bottom,))
        assert hc.desktop.curr_y > 250
