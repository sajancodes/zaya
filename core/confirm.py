"""
core/confirm.py — a confirmation the model cannot forge.

THE PROBLEM WITH THE OLD GATE
    computer_settings guarded shutdown and restart like this:

        confirmed = str(params.get("confirmed", "")).lower()
        if confirmed not in ("yes", "true", "1", "confirm"):
            return "Please confirm by calling again with confirmed=yes."

    `confirmed` is a tool parameter, which means the *model* writes it. Nothing
    stops it from sending confirmed=yes on the first call, and nothing checks
    that a human was ever involved. It is a convention, not a gate — and its
    coverage was two actions, so deleting files and switching off the WiFi the
    assistant is talking over went through with no gate at all.

THE DESIGN HERE (WHEN FULL ACCESS IS OFF)
    The confirmation token is issued by the *interface*, never by the model:

      1. An action calls `request(...)` with a callable that does the real work.
      2. This module hands the UI a banner with CONFIRM / CANCEL and returns
         IMMEDIATELY with a sentence for the model to say out loud.
      3. If — and only if — the user presses CONFIRM, the UI calls `resolve()`,
         which runs the stored callable off the Qt thread.

    Nothing blocks. The model keeps talking while the banner is up, so this
    costs no latency at all; in fact it is cheaper than the old gate, which
    burned two tool round trips (reject, then re-call) on every shutdown.

WHAT BELONGS HERE AND WHAT DOES NOT
    Only genuinely irreversible things. Anything that can be reversed should be
    done at once and pushed onto core/undo.py instead — undo is faster than a
    question, and an assistant that asks before every action is one nobody uses.

    The owner's saved Full Access setting opts out of the confirmation step for
    owner requests. External execution contexts are rejected in both modes.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Callable, Optional

# A pending confirmation is abandoned after this long. Chosen to outlast a
# normal "hang on, let me look at the screen" pause without leaving a live
# shutdown button sitting on the HUD for the rest of the day.
TIMEOUT_SECONDS = 90.0


@dataclass
class _Pending:
    key:     str
    title:   str
    detail:  str
    run:     Callable[[], str]
    at:      float
    on_cancel: Optional[Callable[[str], None]] = None


_pending: Optional[_Pending] = None
_lock = threading.RLock()

# Set once at startup by main.py. Signature: (title, detail) -> None for show,
# and () -> None for hide. Both are marshalled onto the Qt thread by the UI.
_show_cb: Optional[Callable[[str, str], None]] = None
_hide_cb: Optional[Callable[[], None]] = None
_log_cb:  Optional[Callable[[str], None]] = None


def bind(show, hide, log=None) -> None:
    """Wire this module to the HUD. Called once from main.py at startup."""
    global _show_cb, _hide_cb, _log_cb
    _show_cb, _hide_cb, _log_cb = show, hide, log


def _log(msg: str) -> None:
    if _log_cb:
        try:
            _log_cb(msg)
        except Exception:
            pass


def request(key: str, title: str, detail: str, run: Callable[[], str],
            on_cancel: Optional[Callable[[str], None]] = None) -> str:
    """Park an irreversible action behind the on-screen gate.

    Returns the sentence the tool should hand back to the model — phrased as an
    instruction so the assistant asks the user out loud in their own language,
    rather than reading an English string verbatim."""
    global _pending

    from core.execution_policy import require_owner
    from memory.config_manager import get_auto_execute_enabled
    require_owner()
    if get_auto_execute_enabled():
        result = run() or 'Done.'
        _log(f'SYS: Automatically executed owner request — {title}. {result}')
        return result

    if _show_cb is None:
        # No interface bound (headless, or a very early call). Refuse rather
        # than silently performing something irreversible.
        return (f"I cannot confirm '{title}' right now because the interface is "
                f"not available, so I have not done it.")

    with _lock:
        old = _pending
        _pending = _Pending(key=key, title=title, detail=detail,
                            run=run, at=time.monotonic(), on_cancel=on_cancel)
        current = _pending
    if old and old.on_cancel:
        old.on_cancel('Superseded by another confirmation.')

    try:
        _show_cb(title, detail)
    except Exception as e:
        with _lock:
            if _pending is current:
                _pending = None
        return f"Could not ask for confirmation: {e}. Nothing was done."

    _log(f"SYS: Awaiting confirmation — {title}")
    # Anything behind this gate is irreversible, so a phone in another room has
    # to know about it. Which phone treatment it gets depends on where the
    # request came from: asked from the phone, the owner is not at the desktop
    # and cannot see the banner, so the laptop may ring. Asked at the desktop,
    # he is standing in front of it and a written note is the polite answer.
    try:
        from core.event_bus import bus
        from core.execution_policy import get_trust, TRUST_AUTHENTICATED_REMOTE_OWNER
        bus.publish('confirm.requested', title=title, detail=detail, key=f'confirm:{key}',
                    remote=get_trust() == TRUST_AUTHENTICATED_REMOTE_OWNER)
    except Exception:
        pass

    def expire():
        resolve(False, expected=current)
    timer = threading.Timer(TIMEOUT_SECONDS + 0.05, expire)
    timer.daemon = True
    timer.start()
    return (
        f"[CONFIRMATION_PENDING] I have put a confirmation on screen for: {title}. "
        f"Say ONE short sentence in the user's own language telling them you need "
        f"them to confirm it on the HUD before you do it. Do not claim it is done."
    )


def resolve(accepted: bool, *, expected=None) -> None:
    """Called by the UI when the user presses CONFIRM or CANCEL.

    Runs the stored callable on a worker thread — this is invoked from the Qt
    thread, and shutting the machine down from inside a button handler would
    freeze the interface on its way out."""
    global _pending

    with _lock:
        if expected is not None and _pending is not expected:
            return
        p, _pending = _pending, None
        # Do not hide a newer confirmation installed during this resolution.
        if p is not None and _hide_cb:
            try:
                _hide_cb()
            except Exception:
                pass

    if p is None:
        return

    if time.monotonic() - p.at > TIMEOUT_SECONDS:
        _log(f"SYS: Confirmation expired — {p.title}")
        if p.on_cancel:
            p.on_cancel('Confirmation expired.')
        return

    if not accepted:
        _log(f"SYS: Cancelled — {p.title}")
        if p.on_cancel:
            p.on_cancel('Owner cancelled the action.')
        return

    def _worker():
        try:
            result = p.run() or "Done."
            _log(f"SYS: Confirmed — {p.title}. {result}")
        except Exception as e:
            _log(f"ERR: {p.title} failed — {e}")

    threading.Thread(target=_worker, daemon=True,
                     name=f"confirm-{p.key}").start()


def pending_title() -> str:
    """'' when nothing is waiting. Lets an action avoid stacking two banners."""
    with _lock:
        if _pending is None:
            return ""
        if time.monotonic() - _pending.at > TIMEOUT_SECONDS:
            return ""
        return _pending.title
