# Desktop runtime audit dispositions

These dispositions follow the numbered consolidated review. They describe the
current implementation, rather than treating every reported concern as proven.

| Finding | Disposition and evidence |
| --- | --- |
| 28 | Fixed. Failed or cancelled screen/camera capture releases the vision latch and preview. Failed image delivery also releases it. Successful camera capture retains the latch until its answer completes. |
| 29, 81 | Fixed. Optional mobile accessor, frame queue, payload and send errors remain inside the camera relay boundary. Audio stays connected; camera availability is retried and diagnostics are limited to once per minute. Cancellation still propagates. |
| 31 | Not a defect. Clipboard text is a value supplied to a constant format template. Braces inside the value are never parsed as another template. |
| 41 | Task-result cache validation is handled by the core audit. |
| 42 | Fixed. Configuration reads use `Path.read_text`, which closes the file. |
| 43, 45 | Already safe for the actual queue. Playback uses an unbounded `asyncio.Queue`; these synchronous insertions cannot raise `QueueFull`, and there is no suspension between obtaining and using the queue. |
| 44 | Existing lifecycle guard. Sender and session are owned by the same nested context: TaskGroup children are cancelled before the live session closes. Real send failures propagate into reconnect handling. A missing-session guard would hide the error rather than repair a demonstrated race. |
| 46 | Fixed. Summary generation isolates new turns and restores the last 80 pending turns on failure or cancellation. Locally archived conversations were already independent of this optional summary. No previous conversation is loaded or replayed at startup. |
| 47 | Fixed. Recursive TaskGroup cooldown lookup respects the longest provider delay instead of treating nested key cooldowns as generic errors. |
| 48 | Fixed. A failed JPEG encoder result is ignored, and camera handles are released on every exit, including failed fallback opens. The reported exception would have been a `None` attribute error, not an unbound local. |
| 67 | Fixed. The initial assistant name is Zaya before configuration is built. |
| 68 | Not a defect. `get_turn_tuning()` always supplies its `enabled` key with the configured default of false; the call-site `.get` fallback is unreachable for this provider. |
| 69 | Fixed. UI credential and identity updates use the same locked, atomic configuration writer as other settings. Only requested fields are changed, preserving concurrent preferences and refusing to overwrite corrupt JSON. |
| 70 | Already guarded. Each widget access during retheming is protected against a deleted Qt object. |
| 71, 74 | Hardened. Configuration readiness is represented by a thread-safe event and exposed through `is_ready()`. Runtime waiting no longer reads the private Qt `_ready` flag. |
| 73 | Fixed display latency. Long output and queued notices now drain in adaptive chunks per timer tick. The original timer yielded to Qt and did not block the UI, but could leave later output hidden behind minutes of typing. |
| 75 | Intentional continuation. Desktop mode first reveals its detached results window, then populates the shared content/review widget. Returning early would show an empty window. |

Verification: `python -m unittest tests.test_runtime_audit_fixes tests.test_gemini_keys`
passes 16 tests. The regression module includes offline Qt checks and does not
access physical microphones, cameras, provider APIs, credentials, or owner history.
