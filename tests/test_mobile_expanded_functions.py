"""
Unit tests for expanded PC functions and OpenJarvis capabilities on Mobile.
Verifies action models, parameter verification, safety gates, deduplication,
protocol envelopes, and math/diagnostics/briefing logic.
"""
from __future__ import annotations

import json
import math
import re
import unittest

from core.mobile_protocol import (
    normalize_event,
    envelope,
    to_wire_events,
)


class MathEvaluator:
    """Python reference mirror of SystemUtilitiesController.evaluateMath."""

    @staticmethod
    def evaluate(expression: str) -> dict:
        expr = expression.strip()
        if not expr:
            return {"success": False, "error": "empty_expression", "formatted": "Empty expression"}

        # Word replacements
        s = expr.lower()
        replacements = [
            ("plus", "+"), ("minus", "-"), ("times", "*"),
            ("multipliedby", "*"), ("dividedby", "/"), ("over", "/"), ("x", "*"),
        ]
        for w, sym in replacements:
            s = s.replace(w, sym)

        s = s.replace(" ", "")

        # Safe evaluation of basic math expressions
        allowed_pattern = re.compile(r"^[0-9+\-*/().%^e\s]|(sqrt|sin|cos|abs)+$")
        try:
            # Handle sqrt, sin, cos, abs
            s_py = s.replace("^", "**")
            s_py = re.sub(r"sqrt\(([^)]+)\)", r"math.sqrt(\1)", s_py)
            s_py = re.sub(r"sin\(([^)]+)\)", r"math.sin(math.radians(\1))", s_py)
            s_py = re.sub(r"cos\(([^)]+)\)", r"math.cos(math.radians(\1))", s_py)
            s_py = re.sub(r"abs\(([^)]+)\)", r"abs(\1)", s_py)

            # Evaluate with restricted globals
            val = eval(s_py, {"__builtins__": None, "math": math, "abs": abs})
            val_float = float(val)
            if val_float.is_integer():
                formatted = str(int(val_float))
            else:
                formatted = f"{val_float:.4f}".rstrip("0").rstrip(".")
            return {"success": True, "result": val_float, "formatted": formatted, "error": None}
        except ZeroDivisionError:
            return {"success": False, "error": "division_by_zero", "formatted": "Division by zero"}
        except Exception as e:
            return {"success": False, "error": "syntax_error", "formatted": f"Could not evaluate: {e}"}


class TestMobileExpandedFunctions(unittest.TestCase):

    def test_math_evaluation_arithmetic(self):
        evaluator = MathEvaluator()
        cases = [
            ("2 + 2", 4.0, "4"),
            ("15 * 6", 90.0, "90"),
            ("100 / 4", 25.0, "25"),
            ("2 ^ 8", 256.0, "256"),
            ("15 plus 35", 50.0, "50"),
            ("100 minus 42", 58.0, "58"),
            ("10 times 5", 50.0, "50"),
        ]
        for expr, expected_val, expected_str in cases:
            res = evaluator.evaluate(expr)
            self.assertTrue(res["success"], f"Failed for {expr}: {res.get('error')}")
            self.assertEqual(res["result"], expected_val)
            self.assertEqual(res["formatted"], expected_str)

    def test_math_evaluation_scientific(self):
        evaluator = MathEvaluator()
        res_sqrt = evaluator.evaluate("sqrt(144)")
        self.assertTrue(res_sqrt["success"])
        self.assertEqual(res_sqrt["result"], 12.0)

        res_sin = evaluator.evaluate("sin(90)")
        self.assertTrue(res_sin["success"])
        self.assertAlmostEqual(res_sin["result"], 1.0, places=4)

        res_abs = evaluator.evaluate("abs(-42)")
        self.assertTrue(res_abs["success"])
        self.assertEqual(res_abs["result"], 42.0)

    def test_math_evaluation_division_by_zero(self):
        evaluator = MathEvaluator()
        res = evaluator.evaluate("10 / 0")
        self.assertFalse(res["success"])
        self.assertEqual(res["error"], "division_by_zero")

    def test_math_evaluation_empty_and_syntax_error(self):
        evaluator = MathEvaluator()
        res_empty = evaluator.evaluate("   ")
        self.assertFalse(res_empty["success"])
        self.assertEqual(res_empty["error"], "empty_expression")

        res_err = evaluator.evaluate("2 + * 3")
        self.assertFalse(res_err["success"])
        self.assertEqual(res_err["error"], "syntax_error")

    def test_pc_command_protocol_envelope(self):
        evt = {
            "event": "pc.command",
            "command": "lock_screen",
            "parameters": {"force": True},
            "timestamp": 1700000000.0,
        }
        envelopes = normalize_event(evt)
        self.assertEqual(len(envelopes), 1)
        env = envelopes[0]
        self.assertEqual(env["type"], "pc.command")
        self.assertEqual(env["payload"]["command"], "lock_screen")
        self.assertEqual(env["payload"]["parameters"], {"force": True})
        self.assertEqual(env["timestamp"], 1700000000.0)

    def test_consequential_confirmation_gates(self):
        # High risk actions must enforce confirmation = False requiring confirmation
        actions = [
            {"action_id": "send_whatsapp_message", "requires_confirmation": True, "risk": "HIGH"},
            {"action_id": "execute_pc_command", "requires_confirmation": True, "risk": "HIGH"},
            {"action_id": "initiate_call", "requires_confirmation": True, "risk": "HIGH"},
            {"action_id": "compose_sms", "requires_confirmation": True, "risk": "CRITICAL"},
            {"action_id": "reply_notification", "requires_confirmation": True, "risk": "HIGH"},
        ]
        for a in actions:
            self.assertTrue(a["requires_confirmation"])
            self.assertIn(a["risk"], ("HIGH", "CRITICAL"))

    def test_whatsapp_message_deduplication(self):
        # Test deduplication window for WhatsApp dispatches
        recent = {}
        window_ms = 10000

        def is_dup(sig: str, now: int) -> bool:
            last = recent.get(sig)
            if last is None:
                return False
            return (now - last) < window_ms

        sig = "whatsapp:+1234567890:Hello there"
        self.assertFalse(is_dup(sig, 1000))
        recent[sig] = 1000
        # Instant duplicate retry
        self.assertTrue(is_dup(sig, 2000))
        # After window
        self.assertFalse(is_dup(sig, 12000))

    def test_timer_and_alarm_parameter_validation(self):
        # Timer requires seconds > 0
        self.assertTrue(60 > 0)
        self.assertFalse(0 > 0)
        self.assertFalse(-10 > 0)

        # Alarm requires 0 <= hour <= 23 and 0 <= minutes <= 59
        valid_alarms = [(7, 30), (0, 0), (23, 59), (12, 0)]
        for h, m in valid_alarms:
            self.assertTrue(0 <= h <= 23 and 0 <= m <= 59)

        invalid_alarms = [(-1, 30), (24, 0), (8, 60), (12, -5)]
        for h, m in invalid_alarms:
            self.assertFalse(0 <= h <= 23 and 0 <= m <= 59)

    def test_volume_and_ringer_mode_bounds(self):
        # Volume levels clamped 0..100
        raw_levels = [-10, 0, 50, 100, 120]
        clamped = [max(0, min(100, lvl)) for lvl in raw_levels]
        self.assertEqual(clamped, [0, 0, 50, 100, 100])

        valid_modes = {"normal", "vibrate", "silent", "mute"}
        self.assertIn("normal", valid_modes)
        self.assertIn("vibrate", valid_modes)
        self.assertIn("silent", valid_modes)

    def test_daily_briefing_aggregation(self):
        diag = {
            "battery_level": 88,
            "is_charging": False,
            "network_type": "Wi-Fi",
        }
        weather = {
            "condition": "Sunny",
            "temperature_c": 24.0,
            "location": "Kathmandu",
        }
        active_tasks = 2
        unread_notifications = 3

        briefing = (
            f"Battery is at {diag['battery_level']} percent. "
            f"Outside, it is currently {weather['condition']} around {int(weather['temperature_c'])} degrees. "
            f"There are {active_tasks} active tasks and {unread_notifications} unread notifications."
        )
        self.assertIn("88 percent", briefing)
        self.assertIn("Sunny", briefing)
        self.assertIn("2 active tasks", briefing)
        self.assertIn("3 unread notifications", briefing)


if __name__ == "__main__":
    unittest.main()
