import pytest
import platform
from actions.computer_settings import (
    get_power_mode,
    list_power_schemes,
    set_power_mode,
    computer_settings,
    _detect_action,
)
from core.undo import undo_last
from core.execution_policy import with_trust, TRUST_LOCAL_OWNER, TRUST_EXTERNAL_MESSAGE


def test_detect_action_power_aliases():
    assert _detect_action("switch to performance mode")["action"] in ("performance_mode", "high_performance")
    assert _detect_action("high performance")["action"] in ("performance_mode", "high_performance")
    assert _detect_action("ultimate performance")["action"] in ("performance_mode", "ultimate_performance")
    assert _detect_action("balanced mode")["action"] == "balanced_mode"
    assert _detect_action("turn on battery saver")["action"] in ("battery_saver", "power_saver")
    assert _detect_action("power saver")["action"] in ("battery_saver", "power_saver")
    assert _detect_action("power scheme")["action"] == "power_mode"


def test_get_power_mode():
    mode = get_power_mode()
    assert isinstance(mode, str)
    assert len(mode) > 0


@pytest.mark.skipif(platform.system() != "Windows", reason="Windows specific powercfg")
def test_power_mode_switching_and_undo():
    initial_mode = get_power_mode()
    try:
        with with_trust(TRUST_LOCAL_OWNER):
            # Test query
            res_query = computer_settings({"action": "power_mode"})
            assert "Current power scheme:" in res_query

            # Test switch to performance
            res_perf = computer_settings({"action": "performance_mode"})
            assert "Switched power mode" in res_perf

            # Test undo
            undo_res = undo_last()
            assert "Undone: power mode" in undo_res

            # Test switch to balanced
            res_bal = computer_settings({"action": "balanced_mode"})
            assert "Switched power mode" in res_bal
    finally:
        # Restore initial mode
        if "balanced" in initial_mode.lower():
            set_power_mode("balanced")
        elif "ultimate" in initial_mode.lower() or "perf" in initial_mode.lower():
            set_power_mode("performance")
        elif "saver" in initial_mode.lower():
            set_power_mode("battery_saver")


def test_owner_trust_gate():
    with with_trust(TRUST_EXTERNAL_MESSAGE):
        with pytest.raises(PermissionError, match="Untrusted or external source"):
            computer_settings({"action": "power_mode"})

    with with_trust(TRUST_LOCAL_OWNER):
        res = computer_settings({"action": "power_mode"})
        assert "Current power scheme:" in res
