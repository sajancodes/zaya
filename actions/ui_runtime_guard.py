"""Late-bound UI safety shims.

The desktop UI predates the thin ZayaUI facade.  Most runtime code logs through
ZayaUI.write_log(), while a couple of MainWindow media callbacks still call
self.write_log().  That method never existed on MainWindow, so a recoverable
QMediaPlayer error could raise AttributeError inside the error handler itself and
leave media state half-open.  Action discovery imports this helper after ui.py is
loaded; adding the forwarding method to the class is enough for already-created
MainWindow instances because normal Python attribute lookup is dynamic.
"""
from __future__ import annotations


def _install_mainwindow_log_forwarder() -> None:
    try:
        from ui import MainWindow
    except Exception:
        return

    if hasattr(MainWindow, "write_log"):
        return

    def write_log(self, text: str) -> None:
        try:
            log = getattr(self, "_log", None)
            if log is not None and hasattr(log, "append_log"):
                log.append_log(str(text))
                return
        except Exception:
            pass
        # Logging must never turn a recoverable multimedia error into a second
        # exception.  Console fallback is intentionally best-effort.
        try:
            print(str(text))
        except Exception:
            pass

    MainWindow.write_log = write_log


_install_mainwindow_log_forwarder()
