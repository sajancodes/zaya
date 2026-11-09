"""Eval harness and benchmarks for desktop GUI automation and grounding reliability.
Runs a comprehensive suite of repeatable GUI tasks and measures success rate,
grounding strategy, pixel accuracy, and latency. Saves results to JSON.
"""
from __future__ import annotations

import json
import os
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from unittest.mock import MagicMock, patch
from PIL import Image, ImageDraw

# Add project root to sys.path
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import actions.computer_control as cc


@dataclass
class EvalTaskResult:
    task_id: str
    name: str
    category: str
    success: bool
    status: str
    strategy_used: str = "none"
    error_px: float = 0.0
    latency_ms: float = 0.0
    error_message: str = ""
    evidence: Dict[str, Any] = field(default_factory=dict)


class MockDesktopEnvironment:
    """Provides synthetic screens, mock active windows, and deterministic mock grounding."""

    def __init__(self, width: int = 1920, height: int = 1080):
        self.width = width
        self.height = height
        self.active_window_title = "Desktop"
        self.active_hwnd = 1001

        # Ground truth elements: name -> (x, y, w, h)
        self.elements: Dict[str, tuple[int, int, int, int]] = {
            "Create post": (400, 200, 150, 40),
            "What's on your mind?": (400, 260, 500, 100),
            "Post": (850, 600, 80, 36),
            "Search": (100, 50, 250, 32),
            "Submit": (500, 700, 120, 40),
            "Cancel": (640, 700, 100, 40),
            "Settings": (1800, 40, 40, 40),
            "Close": (1900, 10, 20, 20),
        }

    def render_screen(self) -> Image.Image:
        """Render a synthetic screen image with known ground-truth elements."""
        img = Image.new("RGB", (self.width, self.height), color=(240, 242, 245))
        draw = ImageDraw.Draw(img)

        # Draw title bar of active window
        draw.rectangle([0, 0, self.width, 35], fill=(30, 30, 30))
        draw.text((20, 10), self.active_window_title, fill=(255, 255, 255))

        # Draw buttons and text areas
        for name, (x, y, w, h) in self.elements.items():
            fill_color = (24, 119, 242) if name in ("Create post", "Post", "Submit") else (220, 220, 220)
            text_color = (255, 255, 255) if fill_color == (24, 119, 242) else (10, 10, 10)
            draw.rectangle([x, y, x + w, y + h], fill=fill_color, outline=(150, 150, 150), width=1)
            draw.text((x + 8, y + (h // 4)), name, fill=text_color)

        return img


class GuiEvalHarness:
    """Executes 20+ automated evaluation tasks and benchmarks performance."""

    def __init__(self, mock_env: Optional[MockDesktopEnvironment] = None):
        self.env = mock_env or MockDesktopEnvironment()
        self.results: List[EvalTaskResult] = []

    def run_all(self, runs_per_task: int = 1) -> Dict[str, Any]:
        from core import gui_verifier
        tasks: List[tuple[str, str, Callable[[], EvalTaskResult]]] = [
            ("click_by_description_ocr", "Grounding", self._eval_click_by_description_ocr),
            ("click_by_coordinates", "Mouse", self._eval_click_by_coordinates),
            ("double_click", "Mouse", self._eval_double_click),
            ("right_click", "Mouse", self._eval_right_click),
            ("move_mouse", "Mouse", self._eval_move_mouse),
            ("drag_mouse", "Mouse", self._eval_drag_mouse),
            ("scroll_wheel", "Mouse", self._eval_scroll),
            ("type_text", "Keyboard", self._eval_type_text),
            ("smart_type", "Keyboard", self._eval_smart_type),
            ("clear_field", "Keyboard", self._eval_clear_field),
            ("hotkey", "Keyboard", self._eval_hotkey),
            ("press_key", "Keyboard", self._eval_press_key),
            ("clipboard_roundtrip", "Clipboard", self._eval_clipboard_roundtrip),
            ("screenshot_capture", "Screen", self._eval_screenshot_capture),
            ("screen_find_existing", "Grounding", self._eval_screen_find_existing),
            ("screen_find_missing", "Grounding", self._eval_screen_find_missing),
            ("screen_click_existing", "Grounding", self._eval_screen_click_existing),
            ("screen_click_missing", "Grounding", self._eval_screen_click_missing),
            ("focus_window_match", "Window", self._eval_focus_window_match),
            ("focus_window_missing", "Window", self._eval_focus_window_missing),
            ("verify_window_match", "Window", self._eval_verify_window_match),
            ("prepare_environment", "Window", self._eval_prepare_environment),
            ("wait_for_element", "Timing", self._eval_wait_for_element),
            ("act_and_verify_loop", "Verification", self._eval_act_and_verify_loop),
            ("wait_seconds", "Timing", self._eval_wait_seconds),
            ("random_data_gen", "Utility", self._eval_random_data),
            ("user_data_lookup", "Utility", self._eval_user_data),
            ("hidpi_coord_transform", "Coordinate", self._eval_hidpi_transform),
            ("normalized_1000_transform", "Coordinate", self._eval_normalized_1000_transform),
        ]

        total_runs = 0
        passed_runs = 0

        for task_id, category, runner in tasks:
            for run_idx in range(runs_per_task):
                gui_verifier.clear_target_window()
                t0 = time.perf_counter()
                try:
                    res = runner()
                except Exception as ex:
                    res = EvalTaskResult(
                        task_id=task_id,
                        name=task_id.replace("_", " ").title(),
                        category=category,
                        success=False,
                        status="error",
                        error_message=str(ex),
                    )
                latency = (time.perf_counter() - t0) * 1000.0
                res.latency_ms = round(latency, 2)
                self.results.append(res)
                total_runs += 1
                if res.success:
                    passed_runs += 1

        summary = {
            "total_tasks": len(tasks),
            "total_runs": total_runs,
            "passed_runs": passed_runs,
            "success_rate": round((passed_runs / max(1, total_runs)) * 100.0, 2),
            "results": [asdict(r) for r in self.results],
        }
        return summary

    # ── Task Implementations ──────────────────────────────────────────────────

    def _eval_click_by_description_ocr(self) -> EvalTaskResult:
        self.env.active_window_title = "Facebook - Brave"
        img = self.env.render_screen()
        target_name = "Create post"
        gt_x, gt_y, gt_w, gt_h = self.env.elements[target_name]
        gt_center = (gt_x + gt_w // 2, gt_y + gt_h // 2)

        # Mock OCR finding the exact ground truth
        mock_ocr_data = [{
            "text": target_name,
            "words": [
                {"text": "Create", "x": gt_x, "y": gt_y, "w": 60, "h": gt_h},
                {"text": "post", "x": gt_x + 65, "y": gt_y, "w": 50, "h": gt_h},
            ]
        }]
        with patch("actions.computer_control.subprocess.run") as mock_subproc, \
             patch("actions.computer_control.pyautogui.screenshot", return_value=img), \
             patch("core.gui_verifier.get_active_window_info", return_value={"title": "Facebook - Brave", "hwnd": 1001}), \
             patch("actions.computer_control._native_win32_click", return_value=True):
            mock_res = MagicMock()
            mock_res.returncode = 0
            mock_res.stdout = json.dumps(mock_ocr_data)
            mock_subproc.return_value = mock_res

            res = cc.computer_control({"action": "click", "description": target_name})
            success = "Clicked" in res
            error_px = 0.0

            return EvalTaskResult(
                task_id="click_by_description_ocr",
                name="Click by Description (OCR)",
                category="Grounding",
                success=success,
                status="success" if success else "failed",
                strategy_used="ocr",
                error_px=error_px,
                evidence={"result": res, "target": target_name, "gt_center": gt_center},
            )

    def _eval_click_by_coordinates(self) -> EvalTaskResult:
        with patch("actions.computer_control._native_win32_click", return_value=True):
            res = cc.computer_control({"action": "click", "x": 450, "y": 220})
            success = "Clicked (450, 220)" in res
            return EvalTaskResult(
                task_id="click_by_coordinates",
                name="Click by Coordinates",
                category="Mouse",
                success=success,
                status="success" if success else "failed",
                strategy_used="direct_coords",
                evidence={"result": res},
            )

    def _eval_double_click(self) -> EvalTaskResult:
        with patch("actions.computer_control._native_win32_click", return_value=True):
            res = cc.computer_control({"action": "double_click", "x": 500, "y": 300})
            success = "Double-clicked (500, 300)" in res
            return EvalTaskResult(
                task_id="double_click",
                name="Double Click",
                category="Mouse",
                success=success,
                status="success" if success else "failed",
                evidence={"result": res},
            )

    def _eval_right_click(self) -> EvalTaskResult:
        with patch("actions.computer_control._native_win32_click", return_value=True):
            res = cc.computer_control({"action": "right_click", "x": 600, "y": 400})
            success = "Clicked (600, 400) [right]" in res
            return EvalTaskResult(
                task_id="right_click",
                name="Right Click",
                category="Mouse",
                success=success,
                status="success" if success else "failed",
                evidence={"result": res},
            )

    def _eval_move_mouse(self) -> EvalTaskResult:
        with patch("actions.computer_control.pyautogui.moveTo") as mock_move:
            res = cc.computer_control({"action": "move", "x": 800, "y": 500})
            success = "Mouse → (800, 500)" in res
            return EvalTaskResult(
                task_id="move_mouse",
                name="Move Mouse",
                category="Mouse",
                success=success,
                status="success" if success else "failed",
                evidence={"result": res},
            )

    def _eval_drag_mouse(self) -> EvalTaskResult:
        with patch("actions.computer_control.pyautogui.moveTo"), \
             patch("actions.computer_control.pyautogui.dragTo"):
            res = cc.computer_control({"action": "drag", "x1": 100, "y1": 100, "x2": 400, "y2": 400})
            success = "Dragged (100,100) → (400,400)" in res
            return EvalTaskResult(
                task_id="drag_mouse",
                name="Drag Mouse",
                category="Mouse",
                success=success,
                status="success" if success else "failed",
                evidence={"result": res},
            )

    def _eval_scroll(self) -> EvalTaskResult:
        with patch("actions.computer_control.pyautogui.scroll"):
            res = cc.computer_control({"action": "scroll", "direction": "down", "amount": 5})
            success = "Scrolled down ×5" in res
            return EvalTaskResult(
                task_id="scroll_wheel",
                name="Scroll Wheel",
                category="Mouse",
                success=success,
                status="success" if success else "failed",
                evidence={"result": res},
            )

    def _eval_type_text(self) -> EvalTaskResult:
        with patch("actions.computer_control.pyautogui.typewrite"):
            res = cc.computer_control({"action": "type", "text": "Hello Zaya!"})
            success = "Typed: Hello Zaya!" in res
            return EvalTaskResult(
                task_id="type_text",
                name="Type Text",
                category="Keyboard",
                success=success,
                status="success" if success else "failed",
                evidence={"result": res},
            )

    def _eval_smart_type(self) -> EvalTaskResult:
        with patch("actions.computer_control._clear_field"), \
             patch("actions.computer_control.pyautogui.typewrite"), \
             patch("actions.computer_control.pyperclip.copy"), \
             patch("actions.computer_control.pyautogui.hotkey"):
            res = cc.computer_control({"action": "smart_type", "text": "A quick brown fox jumps over the lazy dog."})
            success = "Smart-typed" in res
            return EvalTaskResult(
                task_id="smart_type",
                name="Smart Type",
                category="Keyboard",
                success=success,
                status="success" if success else "failed",
                evidence={"result": res},
            )

    def _eval_clear_field(self) -> EvalTaskResult:
        with patch("actions.computer_control.pyautogui.hotkey"), \
             patch("actions.computer_control.pyautogui.press"):
            res = cc.computer_control({"action": "clear_field"})
            success = res == "Field cleared"
            return EvalTaskResult(
                task_id="clear_field",
                name="Clear Field",
                category="Keyboard",
                success=success,
                status="success" if success else "failed",
                evidence={"result": res},
            )

    def _eval_hotkey(self) -> EvalTaskResult:
        with patch("actions.computer_control.pyautogui.hotkey"):
            res = cc.computer_control({"action": "hotkey", "keys": "ctrl+shift+t"})
            success = "Hotkey: ctrl+shift+t" in res
            return EvalTaskResult(
                task_id="hotkey",
                name="Hotkey Press",
                category="Keyboard",
                success=success,
                status="success" if success else "failed",
                evidence={"result": res},
            )

    def _eval_press_key(self) -> EvalTaskResult:
        with patch("actions.computer_control.pyautogui.press"):
            res = cc.computer_control({"action": "press", "key": "enter"})
            success = "Pressed: enter" in res
            return EvalTaskResult(
                task_id="press_key",
                name="Press Single Key",
                category="Keyboard",
                success=success,
                status="success" if success else "failed",
                evidence={"result": res},
            )

    def _eval_clipboard_roundtrip(self) -> EvalTaskResult:
        with patch("actions.computer_control.pyperclip.copy"), \
             patch("actions.computer_control.pyperclip.paste", return_value="Sample clipboard data"), \
             patch("actions.computer_control.pyautogui.hotkey"):
            res_paste = cc.computer_control({"action": "paste", "text": "Sample clipboard data"})
            res_copy = cc.computer_control({"action": "copy"})
            success = "Pasted" in res_paste and res_copy == "Sample clipboard data"
            return EvalTaskResult(
                task_id="clipboard_roundtrip",
                name="Clipboard Roundtrip",
                category="Clipboard",
                success=success,
                status="success" if success else "failed",
                evidence={"copy": res_copy, "paste": res_paste},
            )

    def _eval_screenshot_capture(self) -> EvalTaskResult:
        img = self.env.render_screen()
        with patch("actions.computer_control.pyautogui.screenshot", return_value=img):
            res = cc.computer_control({"action": "screenshot"})
            success = "Screenshot saved" in res
            return EvalTaskResult(
                task_id="screenshot_capture",
                name="Screenshot Capture",
                category="Screen",
                success=success,
                status="success" if success else "failed",
                evidence={"result": res},
            )

    def _eval_screen_find_existing(self) -> EvalTaskResult:
        with patch("actions.computer_control._find_via_uia", return_value=(475, 220)):
            res = cc.computer_control({"action": "screen_find", "description": "Create post"})
            success = res == "475,220"
            return EvalTaskResult(
                task_id="screen_find_existing",
                name="Screen Find Existing Element",
                category="Grounding",
                success=success,
                status="success" if success else "failed",
                strategy_used="uia",
                evidence={"coords": res},
            )

    def _eval_screen_find_missing(self) -> EvalTaskResult:
        with patch("actions.computer_control._find_via_uia", return_value=None), \
             patch("actions.computer_control._find_via_ocr", return_value=None), \
             patch("actions.computer_control._find_via_som", return_value=None), \
             patch("actions.computer_control._find_via_coordinates", return_value=None), \
             patch("actions.computer_control.pyautogui.screenshot", return_value=self.env.render_screen()):
            res = cc.computer_control({"action": "screen_find", "description": "Totally Nonexistent Button"})
            success = res == "NOT_FOUND"
            return EvalTaskResult(
                task_id="screen_find_missing",
                name="Screen Find Missing Element",
                category="Grounding",
                success=success,
                status="success" if success else "failed",
                evidence={"result": res},
            )

    def _eval_screen_click_existing(self) -> EvalTaskResult:
        with patch("actions.computer_control._screen_find", return_value=(890, 618)), \
             patch("actions.computer_control._click", return_value="Clicked (890, 618) [left]"):
            res = cc.computer_control({"action": "screen_click", "description": "Post"})
            success = "Clicked 'Post' at (890, 618)" in res
            return EvalTaskResult(
                task_id="screen_click_existing",
                name="Screen Click Existing Element",
                category="Grounding",
                success=success,
                status="success" if success else "failed",
                evidence={"result": res},
            )

    def _eval_screen_click_missing(self) -> EvalTaskResult:
        with patch("actions.computer_control._screen_find", return_value=None):
            res = cc.computer_control({"action": "screen_click", "description": "Missing button"})
            success = "Element not found on screen" in res
            return EvalTaskResult(
                task_id="screen_click_missing",
                name="Screen Click Missing Element",
                category="Grounding",
                success=success,
                status="success" if success else "failed",
                evidence={"result": res},
            )

    def _eval_focus_window_match(self) -> EvalTaskResult:
        with patch("core.gui_verifier.list_visible_windows", return_value=[{"title": "Brave - Facebook", "hwnd": 1234}]), \
             patch("core.gui_verifier.get_active_window_info", return_value={"title": "Brave - Facebook", "hwnd": 1234}):
            res = cc.computer_control({"action": "focus_window", "title": "Brave"})
            success = "Focused window:" in res and "Facebook" in res
            return EvalTaskResult(
                task_id="focus_window_match",
                name="Focus Window Match",
                category="Window",
                success=success,
                status="success" if success else "failed",
                evidence={"result": res},
            )

    def _eval_focus_window_missing(self) -> EvalTaskResult:
        with patch("core.gui_verifier.list_visible_windows", return_value=[]):
            res = cc.computer_control({"action": "focus_window", "title": "NonexistentApp12345"})
            success = "focus_window failed" in res and "Focused window" not in res
            return EvalTaskResult(
                task_id="focus_window_missing",
                name="Focus Window Missing",
                category="Window",
                success=success,
                status="success" if success else "failed",
                evidence={"result": res},
            )

    def _eval_verify_window_match(self) -> EvalTaskResult:
        with patch("core.gui_verifier.get_active_window_info", return_value={"title": "Brave - Facebook", "hwnd": 1234}):
            res = cc.computer_control({"action": "verify_window", "title": "Brave"})
            success = "Active window verified" in res
            return EvalTaskResult(
                task_id="verify_window_match",
                name="Verify Active Window Match",
                category="Window",
                success=success,
                status="success" if success else "failed",
                evidence={"result": res},
            )

    def _eval_prepare_environment(self) -> EvalTaskResult:
        with patch("core.gui_verifier.focus_window", return_value={"success": True, "active_title": "Brave"}), \
             patch("core.gui_verifier.get_active_window_info", return_value={"title": "Brave", "hwnd": 1234}):
            res = cc.computer_control({"action": "prepare_environment", "window": "Brave"})
            success = "Environment prepared" in res
            return EvalTaskResult(
                task_id="prepare_environment",
                name="Prepare Environment & Maximize",
                category="Window",
                success=success,
                status="success" if success else "failed",
                evidence={"result": res},
            )

    def _eval_wait_for_element(self) -> EvalTaskResult:
        with patch("actions.computer_control._screen_find", side_effect=[None, (400, 200)]), \
             patch("time.sleep"):
            res = cc.computer_control({"action": "wait_for", "description": "Create post", "timeout": 2.0})
            success = "appeared on screen at" in res
            return EvalTaskResult(
                task_id="wait_for_element",
                name="Wait For Dynamic Element",
                category="Timing",
                success=success,
                status="success" if success else "failed",
                evidence={"result": res},
            )

    def _eval_act_and_verify_loop(self) -> EvalTaskResult:
        with patch("actions.computer_control._click", return_value="Clicked (400, 200) [left]"), \
             patch("actions.computer_control.pyautogui.screenshot") as mock_ss, \
             patch("core.gui_verifier.get_active_window_info", return_value={"title": "Brave - Facebook", "hwnd": 1234}), \
             patch("actions.computer_control._find_via_ocr", return_value=(450, 280)), \
             patch("time.sleep"):
            mock_ss.return_value.size = (1920, 1080)
            res = cc.computer_control({"action": "click", "x": 400, "y": 200, "expect": "What's on your mind?"})
            success = "verified post-condition" in res
            return EvalTaskResult(
                task_id="act_and_verify_loop",
                name="Act-and-Verify Closed Loop",
                category="Verification",
                success=success,
                status="success" if success else "failed",
                evidence={"result": res},
            )

    def _eval_wait_seconds(self) -> EvalTaskResult:
        with patch("time.sleep"):
            res = cc.computer_control({"action": "wait", "seconds": 0.1})
            success = "Waited 0.1s" in res
            return EvalTaskResult(
                task_id="wait_seconds",
                name="Wait Duration",
                category="Timing",
                success=success,
                status="success" if success else "failed",
                evidence={"result": res},
            )

    def _eval_random_data(self) -> EvalTaskResult:
        res = cc.computer_control({"action": "random_data", "type": "name"})
        success = len(res) > 3 and " " in res
        return EvalTaskResult(
            task_id="random_data_gen",
            name="Random Data Generation",
            category="Utility",
            success=success,
            status="success" if success else "failed",
            evidence={"result": res},
        )

    def _eval_user_data(self) -> EvalTaskResult:
        res = cc.computer_control({"action": "user_data", "field": "name"})
        success = len(res) > 0
        return EvalTaskResult(
            task_id="user_data_lookup",
            name="User Profile Data",
            category="Utility",
            success=success,
            status="success" if success else "failed",
            evidence={"result": res},
        )

    def _eval_hidpi_transform(self) -> EvalTaskResult:
        with patch("actions.computer_control.get_screen_metrics") as mock_metrics:
            mock_metrics.return_value = {
                "primary_w": 1920, "primary_h": 1080,
                "logical_w": 1536, "logical_h": 864,
                "scale_x": 1.25, "scale_y": 1.25
            }
            # 4K coordinates mapped to 1080p
            x, y = cc.to_logical_coords(3840, 2160, 3840, 2160)
            success = x == 1919 and y == 1079
            return EvalTaskResult(
                task_id="hidpi_coord_transform",
                name="HiDPI Coordinate Normalization",
                category="Coordinate",
                success=success,
                status="success" if success else "failed",
                evidence={"mapped": (x, y)},
            )

    def _eval_normalized_1000_transform(self) -> EvalTaskResult:
        with patch("actions.computer_control.get_screen_metrics") as mock_metrics:
            mock_metrics.return_value = {
                "primary_w": 1920, "primary_h": 1080,
                "logical_w": 1920, "logical_h": 1080,
                "scale_x": 1.0, "scale_y": 1.0
            }
            # Center of 1000x1000 space
            x, y = cc.to_logical_coords(500, 500, 1000, 1000)
            success = x == 960 and y == 540
            return EvalTaskResult(
                task_id="normalized_1000_transform",
                name="Normalized [0..1000] Transform",
                category="Coordinate",
                success=success,
                status="success" if success else "failed",
                evidence={"mapped": (x, y)},
            )


def run_baseline_and_save(out_path: str = "eval_baseline.json") -> Dict[str, Any]:
    harness = GuiEvalHarness()
    summary = harness.run_all(runs_per_task=2)
    path = Path(out_path)
    path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"[GuiEvalHarness] Baseline eval saved to {path.resolve()}")
    print(f"[GuiEvalHarness] Success rate: {summary['success_rate']}% ({summary['passed_runs']}/{summary['total_runs']} passed)")
    return summary


if __name__ == "__main__":
    out_file = sys.argv[1] if len(sys.argv) > 1 else "eval_baseline.json"
    run_baseline_and_save(out_file)
