# Zaya — architecture reference

Developer-facing reference for how the pieces fit together at run time: process start, threads, the Gemini Live session, the
tool-call path, the voice path and the UI surface.

Line references are `path:line` into this repository. No API keys, tokens or session data are reproduced here. Sibling
documents: `docs/codebase/core.md`, `docs/codebase/actions.md`, `docs/codebase/plugins-tests-tooling.md`.

## 1. Purpose and top-level layout

Zaya is a Windows desktop voice assistant built on the Gemini Live API, plus a taskbar companion and a desktop operator.
`main.py` is the composition root and the Live-session owner; `ui.py` is the Qt surface; everything else is a library it
pulls in.

| Path | Role |
|---|---|
| `main.py` | Entry point, `ZayaLive` (Live session, audio loops, mic gates, tool dispatch, reconnect ladder) |
| `ui.py` | `ZayaUI` façade + `MainWindow`, HUD `HudCanvas`, overlays, cameras/video, drawers |
| `actions/*.py` | Built-in tools that self-describe with a module-level `TOOL` dict; discovered at startup |
| `plugins/*.py` | Drop-in tools with a module-level `PLUGIN` dict + `run()`; discovered at startup, toggleable |
| `core/` | Shared runtime: loaders, event bus, echo guard, VAD, memory/config, keys, task runtime, operator, confirm gate |
| `memory/` | `config_manager` (settings), `memory_manager` (long-term facts), `conversation_store` (local chat archive) |
| `services/` | Taskbar companion (`zayabar.py`), companion bubble, desktop `DisplayWindow`s, WhatsApp |
| `dashboard/` | Local FastAPI/uvicorn remote-control server (phone browser) |
| `config/api_keys.json` | Owner settings store (keys, voice, device names, UI colour, feature flags). Read only through `memory/config_manager` or `config/__init__.py` |
| `zayabar.json` | Companion-bar geometry, assets, poke reactions, emotion tones, audio ducking |

`config/__init__.py` is a small legacy reader (`get_config()` `:13`, `get_os()` `:20`, `is_windows()/is_mac()/is_linux()`
`:24-26`) returning the configured `os_system` or the detected platform; most of the app reads settings through
`memory/config_manager` instead.

## 2. Startup sequence

### 2.1 Pre-import patches (`main.py:1-34`)

Before any other import:

- **`CREATE_NO_WINDOW` for every subprocess** (`main.py:7-16`). On Windows, `subprocess.Popen` itself is replaced by a
  subclass that ORs `CREATE_NO_WINDOW` into `creationflags` and drops any inherited `startupinfo`, so no per-file flag is
  needed anywhere else. `ui.py:16-19` still carries its own `_WIN_HIDE` dict, now redundant on Windows but harmless.
- **UTF-8 console** (`main.py:26-34`). `sys.stdout`/`sys.stderr` are reconfigured with `encoding="utf-8", errors="replace"`.
  Every status line printed later carries an emoji, and on a legacy code page (`cp1254`, `cp932`, …) an emoji print inside
  the receive loop raised `UnicodeEncodeError` and took the session down at startup. Failures are swallowed so `pythonw` and
  redirected pipes still start.

### 2.2 Process start → single instance (`main.py:2778-2803`)

1. `QApplication.instance() or QApplication(sys.argv)`.
2. `SingleInstance()` → `acquire()` (`core/single_instance.py:22-39`). The instance name is
   `zaya-desktop-<sha256(home)[:20]>` (`:12-13`), so it is per-user, not per-machine. A `QLockFile` in the temp directory is
   tried with a zero timeout and `setStaleLockTime(0)` (`:14-17`) — a long-running assistant is never considered stale just
   because time passed. Any lock error other than `LockFailedError` raises `RuntimeError`.
3. If the lock is already held, the new process calls `activate_existing()` (`core/single_instance.py:41-49`), which opens a
   `QLocalSocket` to the running instance, writes `b'activate\n'` and returns `False`; `main()` returns immediately and the
   second process exits.
4. The lock owner starts a `QLocalServer` with `UserAccessOption`, removes any socket left by a crashed run (`:34`), and
   calls `on_activate` on each new connection (`:51-57`).
5. `ZayaUI("face.png")` is constructed, and `instance.on_activate = ui.activate_existing` (`main.py:2787`).
6. `stopping = threading.Event()`; `worker = threading.Thread(target=_run_desktop_agent, args=(ui, stopping), daemon=True)`;
   `ui.root.mainloop()` blocks the main thread.
7. On exit: `stopping.set()`, `ui._shutdown_audio()`, `worker.join(timeout=2)`, then `instance.close()` in the outer
   `finally` (`main.py:2792-2800`). The lock is deliberately held until UI shutdown has finished so a second launch cannot
   race it.

### 2.3 QApplication and the UI (immediately above, plus `ui.py:5823-5852`)

`ZayaUI.__init__` creates/uses the `QApplication`, sets the Fusion style (`ui.py:5826`), constructs
`MainWindow(face_path)` and immediately calls `configure_desktop_interface()` (`ui.py:5828`), which switches the window into
the "Settings & Controls" layout (see §7). It then optionally builds the taskbar companion `ZayaBar` when `zayabar.json` has
`enabled: true` (`ui.py:5836-5847`, default in the shipped file), wires the companion signals, and shows the main window
only if there is no bar, if `show_main_window_on_start` is set, or if no API key is stored yet (`ui.py:5848-5849`).

`_RootShim` (`ui.py:5814-5820`) exposes `mainloop()` → `QApplication.exec()`, plus a no-op `protocol()`.

### 2.4 Agent thread → `ZayaLive`

`_run_desktop_agent` (`main.py:2750-2775`) runs entirely on the worker thread:

1. `ui.wait_for_api_key(stopping)` (`ui.py:6042-6049`) polls `MainWindow._ready` every 100 ms until the setup overlay has
   been completed or `stopping` is set.
2. `ZayaLive(ui)` — construction happens here, on the agent thread, not the Qt thread.
3. `asyncio.run(agent.run())` (`main.py:2757`) creates the event loop the whole session lives on.
4. Failures are caught, redacted (`core/audit.redact`), logged to the activity log and appended to
   `logs/startup_failure.log`; `finally` closes the AudioDucker (`main.py:2774-2775`).

### 2.5 Tool and plugin discovery (`main.py:668-697`)

Still inside `ZayaLive.__init__`:

- Inline tools (`TOOL_DECLARATIONS`, `main.py:350-517`) are the ones whose handling is woven into live-session state:
  `system_status`, `screen_process`, `close_camera`, `manage_monitor`, `shutdown_zaya`, `save_memory`, `recall_memory`,
  `undo`.
- `discover_actions(actions_dir=BASE_DIR/"actions", reserved_names=_inline_names, …)` (`main.py:674-678`,
  `core/action_loader.py:159-223`) imports every `actions/*.py` that is not `_`-prefixed, validates its `TOOL` dict and
  rejects collisions with the inline names.
- `discover_plugins(..., core_tool_names=_inline_names | action_registry.names(), …)` (`main.py:682-690`,
  `core/plugin_loader.py:223-287`). Plugins must not shadow an inline tool or a discovered action. Console logging carries
  the full boot transcript; only load *failures* reach the activity log (`plugin_loader.py:282-286`).
- Registries are published to `core.diagnostics.registries` (`main.py:691-692`) and to the UI as callables:
  `ui.get_plugins`, `ui.get_plugin_settings` (`main.py:693-694`).

### 2.6 Interface wiring in `ZayaLive.__init__`

Owner/UI callbacks assigned before the loop exists (`main.py:585-628`):

| Attribute | Value | Purpose |
|---|---|---|
| `ui.on_shutdown` | `self.shutdown` | Close Zaya → cancel the run task (`main.py:585`, `:928`) |
| `ui.on_push_to_talk`, `ui.ptt_hold` | `set_push_to_talk`, `_on_ptt` | PTT toggle / held state |
| `ui.on_text_command` | `_on_text_command` | Typed command from the input row |
| `ui.on_remote_clicked` | `_make_remote_key` | Remote Control key + URL |
| `ui.on_interrupt` | `self.interrupt` | Stop mid-speech |
| `ui.on_voice_change` | `_on_voice_change` | Voice picker → rebuild without checkpoint |
| `ui.on_credentials_change` | lambda → `request_reconnect(keep_context=False, …)` | Keys changed |
| `ui.on_audio_device_change` | `_on_audio_device_change` | Rebuild, keep conversation |
| `ui.request_say` | `plugin_say` | Mid-task speech channel for plugins (`main.py:695`, `:811`) |
| `ui.on_companion_reaction`, `ui.on_companion_audio_activity` | `companion_reaction`, `companion_audio_activity` | Bar poke/audio → log + ducking (`:1437-1446`) |

Also constructed here: `AudioDucker(...).start()` (`main.py:568-574`), `SpeechDetector` for owner speech (`:575-578`),
`SystemMonitor`, `ProactiveEngine`, `VisemeStream`, `EchoGuard`, the conversation store (§8), and the wake-word preference
state (`:700-705`) including the PTT restore (`:710-714`).

## 3. Threading and concurrency model

| Thread | Created at | Owns |
|---|---|---|
| Qt main thread | `main.py:2793` (`ui.root.mainloop()`) | All widgets; every widget touch happens here, marshalled by `pyqtSignal` |
| Agent thread (daemon) | `main.py:2790` | `ZayaLive.__init__` and the asyncio loop created by `asyncio.run` (`main.py:2757`, `:2454-2497`) |
| PortAudio input callback | `main.py:1687-1699` | Reads mic blocks; never touches queues directly |
| PortAudio output (via executor) | `main.py:2122` | `stream.write` is off-loaded with `asyncio.to_thread` |
| asyncio default executor | implicit | Vision capture (`:1328`, `:1334`), `system_status` (`:1355`), action/plugin handlers (`:1394`, `:1407`), conversation DB writes (`:915`), playback writes (`:2122`) |
| `push-to-talk` | `core/hotkey.py:109-111` | Windows global chord polling; `_on_ptt` may run here (`main.py:992`) |
| `WakeWordThread` | `core/wake_word.py:147` | openWakeWord inference; `feed()` is called from the mic callback (`main.py:1617-1618`) |
| Audio-ducking worker | `core/audio_ducking.py` (`start()`), started `main.py:574` | COM session enumeration and levels; the mic callback only calls `ducker.microphone(pcm)` (`:1672`) |
| Confirm-gate threads | `core/confirm.py:130`, `:179` | Expiry timer, and one worker for the accepted callable |
| `cam-stream` | `ui.py:3406` | Live camera frames → `_cam_frame_sig` |
| `ZayaHistory` | `ui.py:3499` | Loads the saved conversation off-thread |
| `wake-state-warm` | `ui.py:4493` | Pre-imports openwakeword so the drawer does not stall |
| Text-command threads | `ui.py:5051`, `:5084`, `:5704`, `:5757` | Call `on_text_command` off the UI thread |
| Plugin test threads | `ui.py:2723`, `:5433` | Settings "test" buttons, wake-word install |
| `gemini-live-oneshot` | `core/gemini.py:455` | Throwaway Live session for one-shot calls, capped by a 3-slot semaphore (`gemini.py:190-191`) |
| Dashboard uvicorn task | `main.py:2488` → `dashboard/server.py:856-884` | FastAPI/uvicorn server, as an asyncio task on the agent loop |

Cross-thread rules in practice:

- **Qt is never touched from a non-Qt thread directly.** `ZayaUI` is a thin façade over `MainWindow`, and every method
  with a non-Qt caller emits a signal instead: `set_state`→`_state_sig`, `write_log`→`_log_sig`,
  `show_content`→`_content_sig`, `show_confirm`→`_confirm_sig` (`ui.py:5936-5939`), `show_camera_frame`→`_camera_sig`, video
  and quiz/review equivalents (`ui.py:2963-2986`, connected at `:3251-3277`). `set_audio_level` and `push_visemes` store
  values that a Qt timer picks up (`ui.py:5985-5992`, `:6018-6025`).
- **PortAudio callback → loop** is `loop.call_soon_threadsafe(deliver)` (`main.py:1679`), wrapped in `try/except
  RuntimeError` for the case where the session closed mid-callback (`:1680-1681`). `deliver()` re-checks the gates and that
  the queue is still the same object before enqueueing (`:1656-1676`) — a callback from a closed session cannot feed its
  replacement.
- **Loop → Qt** for owner-facing status is signal-only, except `ui.set_state` during construction.
- `request_reconnect` (`main.py:838-850`) and `shutdown()` (`:928-938`) are loop-safe: they use `loop.call_soon_threadsafe`,
  and no-op when the loop/event does not exist yet.

## 4. Live session lifecycle

### 4.1 Connect with a bound (`main.py:103-119`)

`LIVE_CONNECT_TIMEOUT = 20.0` (`:103`). `_connect_live` wraps `client.aio.live.connect(model, config).__aenter__()` in
`asyncio.wait_for`, so a stalled provider cannot strand startup. A new `genai.Client` is built per attempt to avoid stale
HTTP session state (`:2525-2528`), with `api_version` `v1alpha` while proactive audio is still enabled and `v1beta` after it
has been dropped.

### 4.2 Config build — `_build_config` (`main.py:1048-1166`)

Executed on every connect attempt, so memory and prompt edits apply on the next reconnect:

- `config/api_keys.json` is read for `user_name` (`:1052-1058`); memory comes from `load_memory()` +
  `format_memory_for_prompt()` (`:1060-1061`) and the template from `core/prompt.txt` with a hard-coded fallback
  (`:317-325`).
- Prompt parts, in order (`:1111-1121`): `[CURRENT DATE & TIME]` (`:1066-1070`), `[IDENTITY]` with the assistant name and
  address form (`:1084-1089`), `[VOICE AND FACE DELIVERY]` built from `zayabar.json` `emotion_tones` (`:1112-1114`), the
  memory block, the rendered `core/prompt.txt`, and `[SAVED CHAT SAFETY]` telling the model that prior chat is local-only
  and that recall means calling `conversation_history` for at most five messages (`:1118-1121`).
- Template tokens `{assistant_name}`, `{platform}`, `{capabilities}`, `{limits}` are filled by a plain string replace
  (`_render_prompt`, `:300-310`). `capabilities` is derived from the union of inline, action and plugin declarations
  (`_describe_tools`, `:246-266`); `limits` from how the build is actually put together (`_describe_limits`, `:269-297`).
- Fixed fields: `response_modalities=["AUDIO"]`, both transcriptions, `system_instruction`, the full tool list (`:1128`),
  `session_resumption` with the in-memory handle (`:1131-1133`), sliding-window context compression (`:1136-1138`) and the
  speech voice from `get_voice()` (`:1139-1145`). Proactive audio is added while `_enhanced_live` is true **and** the user
  setting is on (`:1147-1155`).
- `_tuning_config()` while `_tuned_live` is true (`:1157-1158`, `:1168-1219`): server turn detection (only when
  `get_turn_tuning()["enabled"]` is set), `media_resolution`, and `thinking_config` unless the current model is
  `gemini-3.8-live`. If a working local VAD is available, `realtime_input_config` is then **replaced** with
  `automatic_activity_detection(disabled=True)` (`:1160-1164`) so turn boundaries are local (`VoiceTurns`, §6.2).

### 4.3 Model ladder and key pool

- `_gemini.LIVE_MODELS` (`core/gemini.py:162-166`): `gemini-3.8-live`, `gemini-3.1-flash-live-preview`,
  `gemini-2.5-flash-native-audio-preview-12-2025`.
- `_gemini.live_model()` (`gemini.py:260-269`) returns the first rung not currently cooling; if all are cooling it returns
  the top rung anyway rather than refusing to connect. With voice `"Nika"` (the default, `memory/config_manager.py:87`) the
  candidate list is restricted to the first rung (`gemini.py:265`).
- `_gemini.note_live_failure()` (`gemini.py:272-289`) cools a rung only for quota (`core/gemini_keys.quota_failure`) and
  gone/unavailable errors, and the run loop steps down (`main.py:2667-2677`).
- Keys come from `core.gemini_keys.pool` via `gemini_keys.select('live')` (`main.py:313-314`). `KeysCooling` on a selected
  key is handled as a first-class case: the UI is told, and the loop waits `retry_after` (interruptible by
  `_reconnect_event`) before retrying (`:2611-2620`). A mid-session quota failure marks the key limited and reconnects
  (`:2653-2660`).

### 4.4 Resumption

- `_resume_handle` lives in memory only and starts as `None` (`main.py:642`) — a fresh process never loads a provider
  checkpoint.
- Scope is `sha256(RESUME_PROTOCOL, model, voice, api_key)` (`memory/conversation_store.py:12-20`); if the scope differs
  from the previous session, the handle is dropped before connecting (`main.py:2512-2518`).
- The receive loop keeps a handle only while the server marks it `resumable`, and persists it for diagnostics with
  `save_handle`; an unsafe in-flight checkpoint clears it (`main.py:1841-1858`).
- A handle the server rejects is dropped once with an explicit log line so the same dead handle is not replayed forever
  (`main.py:2630-2647`).

### 4.5 Rebuild triggers and backoff

Voluntary rebuilds travel through `_ReconnectSignal` (`main.py:519-554`), raised by `_watch_reconnect` when
`_reconnect_event` is set (`:869-881`):

| Trigger | `keep_context` | Citation |
|---|---|---|
| Voice change | `False` (voice is baked into the session) | `main.py:852-860` |
| Credentials change | `False` | `main.py:627` |
| Audio device change | `True` (streams can only be reopened by rebuilding) | `main.py:862-867` |

The signal may arrive wrapped in an `ExceptionGroup` from the TaskGroup; helpers unwrap it and default to
`keep_context=True` (`main.py:534-554`). Voluntary rebuilds skip backoff (`:2627`).

Server-side failures walk a fixed order (`main.py:2603-2734`): invalid-key → prompt for re-configuration and wait for
`_ready`; resumption-handle rejection → drop and retry immediately; quota → mark the key, or step the model ladder;
preview-API rejects → drop `_tuned_live`, then drop `_enhanced_live`; network/timeouts → exponential backoff `3 → 6 → … → 60
s`, with the message that a VPN may be required. Any other error resets the default 3 s delay (`:2746-2748`).

### 4.6 Session tasks and shutdown

Inside `async with (_connect_live(...), asyncio.TaskGroup())` (`main.py:2530-2533`), after resetting all transient flags
(`:2540-2551`), the TaskGroup gets (`:2577-2588`): `_watch_reconnect`, `_send_realtime`, `_listen_audio`, `_receive_audio`,
`_watch_voice_reply`, `_play_audio`, `_run_system_monitor`, `_run_background_monitor`, `_run_proactive_mode`,
`_run_sleep_watch`, and `_relay_phone_audio` when a dashboard exists. The morning briefing is additionally created once per
process when enabled and awake (`:2593-2595`, §6.6).

Shutdown paths:

- **Close Zaya / `aboutToQuit`** → `ZayaLive.shutdown()` cancels `_run_task` via the loop (`main.py:928-938`);
  `asyncio.CancelledError` is re-raised out of the retry loop (`:2597-2598`), so `asyncio.run` tears down and the agent
  thread ends.
- **`shutdown_zaya` tool** → saves the session summary, asks the model for a one-line goodbye, waits 1.5 s, then
  `os._exit(0)` (`main.py:1371-1386`). This deliberately skips `finally` blocks.
- **Per-iteration cleanup**: `finally` clears `self.session` and the loop sleeps the backoff (`:2735-2748`). Local turns are
  already archived; no bulk session summary is sent on every reconnect (`:2737-2738`).

### 4.7 Persists vs. fresh on launch

| Persists across restarts | Fresh every launch |
|---|---|
| Local chat rows in `memory/conversation.db` (never preloaded) | Provider session/checkpoint (`main.py:642`) |
| `operator_scope` / `operator_goal` state rows (`main.py:648-650`) | `_session_log` (`main.py:663`) |
| Long-term facts in `memory/long_term.json` + previous session summary | `_briefing_sent` starts as `bool(previous)` (`main.py:659`) |
| Task runtime DB `memory/zaya_runtime.db`; non-terminal tasks are marked `paused` on load (`core/task_runtime.py:46-49`) | In-memory resumption handle |
| Diagnostic handle + scope for 2 h (`conversation_store.py:13`, `:62-73`) | Vision/echo/VoiceTurns transient state (`main.py:2540-2551`) |
| `logs/runtime/voice_status.json`, startup failure log | — |

## 5. Tool-call pipeline

1. **Receive** — `response.tool_call` in `_receive_messages` (`main.py:1971-1984`). Function calls are de-duplicated by
   `fc.id` against `seen_calls`, and a batch TaskGroup child is created: `workers.create_task(self._run_tool_batch(calls,
   canceled, scope, goal))`. `canceled` ids come from `tool_call_cancellation` earlier in the stream (`:1826-1828`).
2. **Batch** — `_run_tool_batch` (`main.py:1800-1813`) executes calls sequentially, skips canceled ids, filters them again
   after execution (a cancellation arriving *during* execution must not be answered), then
   `session.send_tool_response(function_responses=...)` and finally `_flush_pending_vision()`.
3. **Operator** — `_execute_tool` (`main.py:1235-1264`) builds `request_id =
   f"{operator_scope}:{fc.name}:{sha256(json.dumps(args, sort_keys=True))}"` and runs the invocation through
   `Operator(get_runtime()).execute(...)` (`core/operator.py:20-54`). A cached result is returned when that request id was
   previously recorded. Retry is bounded by `Task.max_attempts = 3` (`core/task_runtime.py:30`) and gated on the result
   being `failed`, `retryable`, side-effect-free and unfinished (`operator.py:41`); successes that carry a side effect are
   remembered for dedup (`operator.py:45-46`). Each attempt publishes `tool.started` and a terminal
   `tool.completed`/`tool.failed` on the bus and writes an audit row (`operator.py:31`, `:47-50`).
4. **Implementation** — `_execute_tool_impl` (`main.py:1266-1435`):
   - `video_player` play/move routes to a browser target when the goal names one (`:1270-1274`); UI state goes to `THINKING`
     (`:1277`).
   - Inline branches: `save_memory` (returns immediately with `silent: True`, `:1280-1292`); `recall_memory` (file search,
     no thread hop, `:1298-1303`); `undo` (`:1305-1312`); `screen_process` (4 s cooldown + busy guard, capture on the
     executor, stores `_pending_vision`, returns a "[VISION_ACTIVE] …do not answer yet" string, `:1314-1348`);
     `close_camera` (`:1350-1352`); `system_status` (`:1354-1356`); `manage_monitor` (`:1358-1369`); `shutdown_zaya`
     (`:1371-1386`).
   - Action registry: `asyncio.to_thread(self._action_registry.run, name, args, ctx)` with `ctx = {"player": ui, "speak":
     self.speak, "response": None, "session_memory": None}` (`:1388-1394`); `web_search` results are mirrored to the content
     panel (`:1396-1403`). Plugin registry otherwise: `asyncio.to_thread(self._plugin_registry.run, name, args, player=ui,
     session_memory=None)` (`:1405-1408`), else `"Unknown tool: {name}"`.
   - Handlers receive only the context kwargs they declare (`core/action_loader.py:113-123`,
     `core/plugin_loader.py:144-154`) and both registries re-check owner trust with `require_owner()`
     (`action_loader.py:100`, `plugin_loader.py:88`). Crashes become a string result plus `speak_error`
     (`main.py:1412-1415`).
5. **Normalize** — results are coerced to `ToolResult` (`core/tool_result.py:41-53`). Real `ToolResult`/dict results keep
   their status, evidence, `retryable`, `side_effect`, `undo_id`; plain text becomes `{'legacy': True, 'verified': False}`
   and is classified by content, with head/tail truncation at 16 KiB (`tool_result.py:11-17`).
6. **Respond** — the `FunctionResponse` is rebuilt with the normalized dict (`main.py:1256-1264`). A `scheduling` hint, when
   the action or plugin declared one, is attached to the response so the API knows when the result may re-enter the
   conversation (`main.py:1428-1435`, `core/action_loader.py:42-49`).
7. **Vision flush** — `_flush_pending_vision` sends the frame captured by `screen_process` as `send_client_content`
   immediately after the tool response, labelled `[IMAGE SOURCE: WEBCAM]`/`[IMAGE SOURCE: SCREEN CAPTURE]`
   (`main.py:1751-1792`), so the model has both the result and the image before generating anything.

Vision lifecycle flags are reset on every session rebuild (`main.py:2541-2545`); the camera view is closed 2 s after the
turn that answers the vision question (`:1962-1969`).

## 6. Voice pipeline

### 6.1 Microphone gates — `_microphone_input` (`main.py:1607-1681`)

Every block passes, in this order:

1. **Wake word sleep** — when wake mode is on and Zaya is asleep, the block is dropped and fed to `WakeWordDetector.feed`
   instead (`:1614-1619`).
2. **Mute / phone / push-to-talk** — `ui.muted`, `_phone_active`, or PTT enabled without the chord held (`:1620-1623`). The
   phone relay sets `_phone_active` so the PC mic is silenced while the phone streams (`:2406-2408`).
3. **Companion poke audio** — while the bar is speaking a reaction, mic input is dropped, plus a 0.5 s tail (`:1624-1627`,
   `:1440-1446`).
4. **While speaking** — `EchoGuard.is_user_speech` decides. Blocks that are `_barge_audio`-retained until `required_blocks`
   consecutive positives arrive, then the retained prefix plus the current block is delivered and `barge_in` is set
   (`:1633-1644`). Retention exists so the server hears the first syllables of the interruption.
5. **Echo tail after speaking** — `_tail_active()` covers `_out_latency + 0.25 s` (`:924-926`, `:940-963`). A genuine reply
   through the tail opens the guard immediately (`:1647-1651`).
6. **Delivery** — `loop.call_soon_threadsafe(deliver)`; the queue is bounded at 16 and drops the oldest item instead of
   accumulating stale speech (`:1668-1670`). Each packet also feeds the ducker and the owner VAD, which is what marks owner
   activity for notifications (`:1672-1675`).

### 6.2 Out queue and turn markers — `_send_realtime` (`main.py:1545-1605`)

- Queue items are `{"data": bytes, "mime_type": str}`; `audio/pcm` is rewritten to `audio/pcm;rate=16000` and sent through
  the modern `audio=` field (Gemini 3.x rejects the old `media_chunks` field with a 1007, `:1578-1585`).
- When a local VAD is available, `VoiceTurns` (`core/voice_turns.py:6-36`) decides boundaries: it keeps a 6-block prefix of
  pre-speech frames, emits `activity_start` only when it goes active, and `activity_end` after 0.9 s of silence
  (`main.py:1587-1605`).
- On idle timeout after streaming, a *generated* quiet pad (ten 100 ms silent blobs, ≈1 s, no captured audio) is sent before
  the stream is closed, because a bare stream end can discard the pending server VAD turn (`:1556-1576`). Without a local
  VAD the close is `audio_stream_end=True`.
- Health marks (`stream_start`, `quiet_padding`, `stream_end`, `idle_input`, `sent`, `blocked` with the gate name) are
  recorded by `_voice_mark` (`:1538-1543`).

### 6.3 Receive loop — `_receive_messages` (`main.py:1815-1991`)

- **Interruption** — `server_content.interrupted` drains queued audio via `interrupt()`, clears the interrupted flag, the
  output buffer and the echo tail (`:1831-1839`).
- **Resumption** — see §4.4; only `resumable` handles are kept.
- **Audio** — `response.data` is sliced into 2400-byte (50 ms) chunks as it is enqueued, so `interrupt()` can stop sound
  within ~50 ms (`:1860-1873`).
- **Output transcript** — cleaned (`_clean_transcript`, `:345-348`), de-duplicated against the whole buffer
  (`_is_repeat_chunk`, `:334-343`), published as `avatar.caption` on the event bus and fed to the viseme stream
  (`:1878-1895`).
- **Input transcript** — the growing user turn is written to the conversation store through `record` (updating the row
  created by the first chunk), sets the operator scope/goal via `_begin_owner_goal`, and refreshes `_last_user_speech`
  (`:1897-1905`).
- **Turn completion** — clears owner-pending flags, sets `_turn_done_event`, skips the rest if the turn ended interrupted,
  logs `You:`/`<name>:` lines, appends the model turn to the store, broadcasts to the dashboard, and handles the deferred
  camera close (`:1911-1969`).
- **Errors** — an exception prints, re-raises, and fails the TaskGroup (hence the session), leaving any pending output
  buffer appended to the store in `finally` (`:1985-1991`).

### 6.4 Playback loop — `_play_audio` (`main.py:1993-2132`)

- Output device resolved with a fallback to the system default when the saved device will not open (`:1996-2022`).
- `stream.latency` is read once and drives the echo tail size (`:2028-2035`).
- Chunks are batched up to 9600 bytes (~200 ms) per write; the executor write is the only place audio reaches the device
  (`:2064-2069`, `:2122`).
- The speaking gate is owned by actual playback: `set_speaking(True)` per batch, released after 0.35 s without audio, on
  `_turn_done_event`, or by an interrupt (`:2050-2059`).
- Visemes: `_pcm_visemes` slices the batch into 20 ms `(level, openness, width)` frames (`main.py:186-243`), the batch is
  scheduled against `_play_cursor` (wall-clock time the audio becomes audible, re-anchored only when physically impossible,
  `:2075-2104`) and pushed to the HUD (`ui.py:480-533`). Each batch is also recorded with `EchoGuard.note_output` (`:2111`,
  `:2117`).

### 6.5 Sleep, wake, PTT and stalled-reply recovery

- `WAKE_SLEEP_TIMEOUT = 120 s` (`main.py:95`); `_run_sleep_watch` polls every 5 s and sleeps after the silence window unless
  speaking (`:763-774`).
- Wake sources: detector thread (`:742-744`), UI buttons (`:778-802`), holding the PTT chord (`:995-1000`), remote dashboard
  commands (`:2440-2441`). Typed commands are refused while asleep (`:902-904`).
- `_watch_voice_reply` (`:1481-1485`) detects a request that produced no speech for 20 s and calls `_recover_stalled_voice`
  (`:1487-1494`), which only clears pending flags, marks `reply_timeout` and keeps the session — never replaying a task.

### 6.6 Background speakers inside the session

`_send_startup_briefing` (`main.py:2136-2268`) is two-phase: an instant greeting, with the news fetch already running on the
executor and the previous session summary popped once (`pop_last_session`, `:2174`), then a news phase gated on
`_turn_done_event` with an extra buffer so phase 2 cannot talk over phase 1 (`:2202-2268`). `_run_system_monitor`
(`:2302-2320`), `_run_background_monitor` (`:2324-2353`) and `_run_proactive_mode` (`:2357-2394`) each check "session
exists, awake, not speaking, owner not pending" before injecting text through `send_client_content`.
`_operator_notifications` (`:1496-1536`) relays inbox/notification lines: each item is synthesized to audio by
`core.notification_voice.synthesize_notice`, enqueued in 2400-byte slices with `_notification_active` set, and only marked
delivered when that succeeded.

## 7. UI surface

### 7.1 `MainWindow` — structure (`ui.py:2962-3298`)

- Signals for every cross-thread entry point (`ui.py:2963-2986`).
- Built layout: header (`_build_header`, `:4054`), left metric panel (`:4144`), centre `QSplitter` (`:3208-3224`) holding a
  `QStackedWidget` (`:3202-3206`) of `HudCanvas` / camera page / video page, plus the content panel (`:4584`) and quiz panel
  (`:4807`), right panel (`:4215`), footer (`:5038-5067`), and the two floating drawers (quick `:4284`, controls `:4425`).
- HUD: `HudCanvas` (`ui.py:406-943`) runs a 16 ms timer (`:468-470`), renders the software avatar (`core/avatar.py`) with a
  fallback glowing core, and consumes `set_audio_level` (`:533-547`) and `push_visemes` (`:480-532`).
- Timers: clock (`:3240-3243`), metrics (`:3246-3249`, backing `_SysMetrics`, `:252-404`), camera frames, video sound sync
  (`:3185-3187`).
- Shortcuts: F4 mute, F11 fullscreen, Esc interrupt (`:3293-3298`).

### 7.2 Desktop mode — `configure_desktop_interface` (`ui.py:3300-3360`)

Called unconditionally from `ZayaUI.__init__`. The legacy central widget (containing header, HUD, panels) is taken off the
window and hidden (`:3304-3307`); the window becomes "Zaya — Settings & Controls". It then:

- re-uses the two drawers as the main settings UI (`:3317-3322`), adds mute / stop-speaking / conversation-history /
  last-conversation-history / close buttons (`:3324-3340`);
- moves the video page into `DisplayWindow` "Zaya — Media Display" (`:3347`), the camera page into "Zaya — Camera" (`:3349`)
  and the content+quiz panels into "Zaya — Display" (`:3351-3355`) (`services/desktop_windows.py:6-29`: a `QDialog` that
  re-parents its widget and emits `closed`).

The visible character in this mode is the taskbar companion, not the HUD.

### 7.3 Overlays

All floating panels are children of the central widget, positioned by hand (`_centre_overlay`, `ui.py:5588-5598`), and
inherit `_HudOverlay` (`:1965-1984`) which repaints the region it covered on hide.

| Overlay | Line | Notes |
|---|---|---|
| `_CameraPreview` | `ui.py:1345` | Small screen-capture preview |
| `FileDropZone` + `_DropCanvas` | `ui.py:1153`, `:1238` | Drag/drop upload target; `current_file` feeds `file_processor` |
| `SetupOverlay` | `ui.py:1412` | API-key/OS setup; emits `done(key, os_name)` |
| `CustomizeOverlay` | `ui.py:1635` | Name, user name, voice, UI accent (`HueWheel`, `:1541`) |
| `PluginManagerOverlay` | `ui.py:1854` | Enable/disable plugins from `ui.get_plugins()` |
| `ConfirmBanner` | `ui.py:1987` | Irreversible-action gate; `answered` → `core.confirm.resolve` (`:5639-5648`) |
| `AudioDeviceOverlay` | `ui.py:2067` | Mic/speaker picker; emits `picked` → `on_audio_device_change` |
| `MemoryOverlay` | `ui.py:2196` | Browse/forget long-term facts |
| `ClipboardPanel` | `ui.py:2392` | Appears on clipboard change, offers canned commands |
| `PluginSettingsOverlay` | `ui.py:2478` | Renders `PLUGIN_SETTINGS` sections; test buttons run off-thread (`:2697-2723`) |
| `RemoteKeyOverlay` | `ui.py:2734` | QR + one-time key for the phone dashboard; refreshes its key (`:2928`) |

### 7.4 Content, history, camera, media

- `show_content(title, text)` (`ui.py:6051-6053`) → `_content_sig` → `_show_content` (`:4674-4692`), which also asks the HUD
  to glance at the panel; used by the briefing, web search and any action that calls `player.show_content`.
- Conversation history: the live `LogWidget` inside a `DisplayWindow` (`:3328-3331`); the saved archive is loaded on demand
  in a thread and rendered by `_show_saved_history` (`:3487-3505`).
- Camera: `start_camera_stream`/`stop_camera_stream` (`ui.py:3403-3449`) run `_cam_loop` on a `cam-stream` thread and emit
  frames through `_cam_frame_sig`; the HUD's camera page or the desktop camera window displays them (`:3379-3401`).
- Media: `_on_video_open` (`ui.py:3451-3485`) uses a `QGraphicsVideoItem` (not `QVideoWidget`) so overlays stay above it,
  plus a second `QMediaPlayer` for split audio streams (YouTube) kept in step by a 1 s timer (`:3180-3187`,
  `_sync_video_sound` `:3565`). Opening a video mutes the mic by default (`_sync_mic_for_video`, `:3561`) and closing it
  gives the microphone back (`:3530-3544`).

### 7.5 Companion bar integration (`ui.py:5835-5873`)

`ZayaBar` (`services/zayabar.py:17`) is a frameless translucent `Tool` window that seats itself on the taskbar (position
timer, `:57-60`). Wiring:

- `_applied_state_sig` → `bar.state_changed` → `ZayaBar.set_state` (`ui.py:5842`, `services/zayabar.py:46`);
- `bar.reaction_requested` → `_bar_reaction` → `ZayaLive.companion_reaction`, which writes the line into the activity log
  (`main.py:1437-1438`);
- `bar.reaction_audio_active` → `_bar_audio_activity` → `ZayaLive.companion_audio_activity`, which ducks other sessions
  under the poke voice and holds a 0.5 s tail (`main.py:1440-1446`);
- `_win._log_sig` → `bar.observe_log` so the bar sees the same log stream;
- `aboutToQuit` → `bar.shutdown` (`ui.py:5846`);
- `MainWindow._runtime_event` (`ui.py:5505-5518`) is subscribed to every bus event (`:3256`) and turns `tool.*`/task events
  into a human activity label via `core.hud_state`.

`zayabar.json` supplies geometry, assets, poke reactions, emotion tones and the `audio_ducking` block;
`core/zayabar_config.py` validates it and `main.py:1112-1114` injects the emotion tones into the session prompt.

## 8. Conversation persistence touch points

- **Store** — `ConversationStore` (`main.py:644-656`; `memory/conversation_store.py:23-124`), SQLite at
  `memory/conversation.db` (`conversation_store.py:12`), tables `state` + `messages`. Failure to open it is not fatal: the
  UI is told and `_conversation` becomes `None` (`main.py:653-656`).
- **Startup** — `has_history()` decides whether the UI says "Previous conversation saved in History" and whether the
  briefing is suppressed (`main.py:646-659`). The saved chat is never preloaded; `restore_content()` in the store exists but
  is only exercised by tests (`conversation_store.py:114-124`, `tests/test_conversation.py:53`, `:75`).
- **Writes** — all through `_conversation_write` (`main.py:911-917`), which offloads to `asyncio.to_thread` and swallows
  `OSError`/`sqlite3.Error` with a UI line: `record` for the streaming user turn (`:1903`), `append` for the model turn
  (`:1951`), the `finally` flush of a partial model turn (`:1990-1991`), typed commands (`:920`), and `save_handle` /
  `clear_handle` for resumption state (`:1853`, `:1858`, `:2626`, `:2645`).
- **Operator scope / goal** — `_begin_owner_goal` rotates `_operator_scope` (uuid4) per owner turn, stores
  `redact(text)[:300]` as the goal, and persists both to the store (`main.py:1221-1233`). They are read back at startup so
  the identity of the current command survives a restart (`:648-650`).
- **Recall** — only on explicit request, through the `conversation_history` action, which is capped at five messages and a 4
  KiB text budget and returns `ToolResult` with an explicit "historical context only" summary
  (`actions/conversation_history.py:7-23`). The system prompt says the same thing (`main.py:1118-1121`).
- **Long-term memory** — `save_memory` writes facts through `update_memory` (`main.py:1280-1292`); `recall_memory` searches
  them (`:1298-1303`); `_save_session_summary` (`:2272-2298`) summarizes the session (last 40 turns, in the remembered
  language) and appends it to `long_term.json`; the next briefing pops it once (`pop_last_session`, `:2174`).
- **Execution evidence** — task states and tool results live in `memory/zaya_runtime.db` (`core/task_runtime.py:122-127`);
  any task that was not terminal when the process ended is marked `paused` at load so an in-flight side effect is never
  replayed (`:46-49`).

## 9. Key files and line references

| File | What to look at |
|---|---|
| `main.py:7-34` | Global `Popen` `CREATE_NO_WINDOW` patch; UTF-8 stream fix |
| `main.py:108-119` | `_connect_live`, 20 s connect bound |
| `main.py:350-517` | Inline `TOOL_DECLARATIONS` |
| `main.py:519-554` | `_ReconnectSignal` + group unwrapping |
| `main.py:557-720` | `ZayaLive.__init__`: services, UI wiring, discovery, wake/PTT state |
| `main.py:1048-1219` | `_build_config` / `_tuning_config` |
| `main.py:1235-1435` | Tool pipeline: `_execute_tool` → `_execute_tool_impl` |
| `main.py:1545-1605` | `_send_realtime`: pacing, quiet padding, turn markers |
| `main.py:1607-1681` | `_microphone_input`: all mic gates |
| `main.py:1751-1991` | Vision flush; receive loop and tool-batch scheduling |
| `main.py:1993-2132` | Playback loop, viseme schedule, echo recording |
| `main.py:2454-2748` | `run()`: per-iteration config, model/key/mode fallbacks, backoff |
| `main.py:2750-2803` | Agent thread, `main()`, lock lifetime |
| `ui.py:406-943` | `HudCanvas` (avatar, waveform, viseme schedule) |
| `ui.py:2962-3360` | `MainWindow.__init__`; `configure_desktop_interface` |
| `ui.py:5588-5704` | Overlay placement, confirm banner, clipboard, plugin overlays |
| `ui.py:5823-6136` | `ZayaUI` façade, companion bar, thread-safe emit points |
| `core/action_loader.py:42-123` | Action behaviour/scheduling, `ActionRegistry` dispatch |
| `core/plugin_loader.py:51-154` | `PluginRegistry` declarations/run/settings/UI list |
| `core/operator.py:20-54` | Bounded execution, dedup, audit, bus events |
| `core/tool_result.py:11-53` | `ToolResult`, truncation, legacy normalization |
| `core/echo.py:118-290`, `core/voice_turns.py:6-36` | Echo classification; turn boundaries with prefix retention |
| `core/single_instance.py:22-66`, `core/event_bus.py:10-35` | Startup lock/socket; pub/sub bus |
| `memory/conversation_store.py:19-124` | Scope hashing, state, messages, recall |
| `zayabar.json`, `config/__init__.py` | Companion geometry/assets/tones; legacy OS reader |

## 10. Observations and risks

Each item is grounded in the code as written; none of these are hypotheses about intent.

1. **`interrupt()` is reachable from the Qt thread but mutates loop-owned state.** `ui.on_interrupt` is
   `ZayaLive.interrupt` (`main.py:625`), called directly by the Esc shortcut and the stop button (`ui.py:5708-5710`,
   `:3325-3327`). It drains `audio_in_queue` with `get_nowait()` and clears `_turn_done_event` (`main.py:1013-1029`) —
   asyncio primitives touched from outside their loop. The mic path documents the opposite rule and routes through
   `call_soon_threadsafe` (`main.py:1609-1612`); the interrupt path does not.
2. **The default voice disables the Live model ladder.** `get_voice()` defaults to `"Nika"` (`memory/config_manager.py:87`)
   and `live_model()` then restricts candidates to `LIVE_MODELS[:1]` (`core/gemini.py:265`), returning it even while it is
   cooling (`:269`). On the shipped default, a quota error at the top rung means every reconnect retries the same model.
3. **Turn tuning is silently overridden when a local VAD is present.** `_tuning_config()` builds server-side turn detection
   (`main.py:1196-1197`), but `_build_config` then reassigns `cfg['realtime_input_config']` with
   `automatic_activity_detection(disabled=True)` (`main.py:1160-1164`); the later assignment wins, so the user's
   `turn_tuning` settings never reach the provider. `webrtcvad` is declared in `requirements.txt:15` and present in the
   project venv, so this is the ordinary path.
4. **Remote dashboard commands skip `_begin_owner_goal`.** `_on_text_command` rotates the operator scope, sets the goal and
   refreshes owner activity (`main.py:905-909`, `:1221-1233`), while `_process_dashboard_commands` calls `_send_owner_text`
   directly (`main.py:2442`). The scope therefore stays from the previous owner turn, and since the Operator dedup key is
   `scope:name:args-hash` with cached successes returned without re-execution (`main.py:1245-1252`,
   `core/operator.py:22-24`, `:45-46`), an identical side-effecting call from the phone within the same scope can be
   answered from cache instead of performed.
5. **The HUD is constructed, animated and fed while hidden.** `ZayaUI` always enters desktop mode (`ui.py:5828`), which
   hides the legacy surface that contains the HUD (`ui.py:3304-3307`), yet `HudCanvas` starts a 16 ms timer at construction
   (`ui.py:468-470`) and the playback loop keeps pushing viseme schedules and levels into it (`main.py:2107`, `:1676`).
   Per-frame work and audio-derived scheduling are spent on a widget that is not on screen in the default configuration.
6. **Connect-timeout cleanup depends on the SDK.** In `_connect_live`, the `__aexit__` guard is entered only after
   `asyncio.wait_for` returns (`main.py:112-119`); a timeout raises before the `try`, so any half-opened transport is left
   to the SDK's own cancellation handling.
7. **`shutdown_zaya` uses `os._exit(0)`.** After saving the summary and asking for a goodbye (`main.py:1371-1386`), the
   process exits immediately: TaskGroup `finally` blocks, the AudioDucker close, the dashboard shutdown and the
   conversation-store connection are all skipped. Close Zaya instead cancels the run task and unwinds normally
   (`main.py:928-938`, `ui.py:3338-3340`).
8. **A failure while the camera is open leaves the capture thread running.** Session rebuild resets `_vision_cam_active` /
   `_vision_close_pending` (`main.py:2541-2545`) but never calls `ui.stop_camera_stream()`; the close is normally driven by
   the vision turn completing (`main.py:1962-1969`) or by `close_camera`. A reconnect in between leaves the `cam-stream`
   thread (`ui.py:3403-3407`) capturing until the user closes it or the app exits.
9. **Unbounded in-memory accumulation.** `audio_in_queue` is created without `maxsize` (`main.py:2536`), `_session_log`
   grows for the lifetime of the session (`main.py:663`, trimmed only when a summary is written), and `seen_calls` /
   `canceled` are per-session sets (`main.py:1819`). Only `out_queue` is bounded, at 16 (`main.py:2537`).
10. **One shared executor for audio writes, capture, tool handlers and DB writes.** `stream.write` (`main.py:2122`), vision
    capture (`:1328`, `:1334`), action/plugin handlers (`:1394`, `:1407`) and conversation writes (`:915`) all use the
    loop's default `ThreadPoolExecutor`, so a slow handler occupies a worker the playback path may want; `main.py:2603-2608`
    already records "executor after shutdown" errors as a known failure mode.
11. **Legacy string results defeat retry and dedup.** Actions that return prose are normalized to `partial` with `{'legacy':
    True, 'verified': False}` (`core/tool_result.py:46-53`), so the Operator's retry condition (`operator.py:41`) and dedup
    condition (`:45`) both miss. Handler crashes are converted to strings *inside* the registries
    (`core/action_loader.py:107-110`, `core/plugin_loader.py:97-101`), so a crashing action is never a retryable failure.
    Tools that want retry or dedup must return a `ToolResult`.
12. **A single malformed server message ends the session.** `_receive_messages` prints, re-raises and lets the TaskGroup
    fail (`main.py:1985-1988`), so any unexpected shape in the stream costs a full reconnect rather than one skipped
    message.
13. **`ZayaUI.glance` can never work.** It calls `self._avatar` (`ui.py:5994-6000`), which `ZayaUI.__init__` never
    assigns (`ui.py:5824-5852`); the `AttributeError` is swallowed by the broad `except`. The working path is on the HUD
    itself (`self.hud.glance`, `ui.py:472-478`, used at `:4681`).
14. **`ConversationStore.restore_content()` is production dead code.** It is defined at `conversation_store.py:114-124` and
    referenced only from tests (`tests/test_conversation.py:53`, `:75`). Recall in production goes exclusively through the
    capped `conversation_history` action, which matches the owner rule that history is never preloaded — but the method is a
    standing invitation to wire a resume path that the rule forbids.
15. **`_asst_name` has a placeholder value that only `_build_config` replaces.** It is initialised as `"JARVI    S"`
    (`main.py:560`) and set to `"Zaya"` in both `_build_config` branches (`:1054`, `:1057`). Any code path that logs the
    assistant name before the first config build (or after a build failure) prints the placeholder.
16. **Diagnostics write continuously without rotation.** `_listen_audio` writes `logs/runtime/voice_status.json` every 2 s
    while a session is live (`main.py:1729-1746`), overwriting a single file; `_run_desktop_agent` appends to
    `logs/startup_failure.log` (`:2767-2771`). The snapshot contains flags, queue sizes and voice marks only — the key list
    is visible at `main.py:1731-1740`, and no transcript text is written there.
