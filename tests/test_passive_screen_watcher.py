import time
from core.passive_screen_watcher import PassiveScreenWatcher, ScreenContext


def test_screen_context_recent():
    ctx = ScreenContext(timestamp=time.time())
    assert ctx.is_recent(10.0) is True

    old_ctx = ScreenContext(timestamp=time.time() - 100.0)
    assert old_ctx.is_recent(30.0) is False


def test_crash_pattern_detection():
    watcher = PassiveScreenWatcher()

    # Python traceback
    sample = """
Traceback (most recent call last):
  File "main.py", line 42, in <module>
ZeroDivisionError: division by zero
    """
    snippet, err_type = watcher.inspect_text_for_crashes(sample)
    assert "ZeroDivisionError" in snippet
    assert err_type == "python_traceback"

    # Pytest failure
    sample_pytest = "FAILED tests/test_core.py::test_init - AssertionError: expected True"
    snippet2, err_type2 = watcher.inspect_text_for_crashes(sample_pytest)
    assert "FAILED tests/test_core.py::test_init" in snippet2
    assert err_type2 == "pytest_failure"


def test_screen_context_prompt_formatting():
    watcher = PassiveScreenWatcher()
    watcher._current_context = ScreenContext(
        app_name="code.exe",
        window_title="Zaya - main.py - Visual Studio Code",
        detected_error="SyntaxError: invalid syntax",
        error_type="python_exception",
        has_error=True,
        timestamp=time.time(),
    )
    prompt = watcher.get_screen_context_prompt()
    assert "[ACTIVE SCREEN CONTEXT]" in prompt
    assert "Visual Studio Code" in prompt
    assert "SyntaxError: invalid syntax" in prompt
