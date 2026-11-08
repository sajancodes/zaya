# `core/` — module reference

Developer reference for the 38 files in `core/`, the shared runtime layer of Zaya (Windows desktop
voice assistant on Gemini Live + desktop operator). `core/` has no UI dependency except `avatar.py`
(Qt painting) and `single_instance.py` (Qt network/lock); everything else is plain Python consumed by
`main.py`, `ui.py`, `actions/`, `plugins/`, `services/` and `tests/`.

Line references are `path:line` into this repository. No configuration values, keys or tokens are
reproduced here.

---

## 1. Module inventory

| File | Purpose | Key symbols | Consumed by |
|---|---|---|---|
| `__init__.py` | Empty package marker (0 bytes) | — | implicit |
| `action_loader.py` | Discovery/validation/dispatch of bundled `actions/*.py` that expose a `TOOL` dict | `ActionRecord`, `ActionRegistry` (`get_tool_declarations`, `run`, `scheduling`, `names`), `discover_actions`, `_call_handler`, `_validate` | `main.py:86`, `main.py:674`; `tests/test_baseline.py`, `tests/test_app_integration.py` |
| `audit.py` | Structured local audit log with recursive secret redaction | `redact`, `write`, `ROOT`, `_secret_name` | `shell_session.py:11`, `session_activity.py:9`, `gemini.py:486`, `operator.py`, `task_runtime.py`, `main.py:1225`, `main.py:2761`, `actions/browser_control.py:32`, `services/whatsapp/handler.py:87` |
| `audio_devices.py` | Microphone/speaker enumeration, host-API probing, name→index resolution | `list_devices`, `resolve`, `configure`, `prefetch`, `DEFAULT_LABEL` | `main.py:85`, `main.py:2475`; `ui.py:2080` |
| `audio_ducking.py` | VAD-driven sidechain ducking of render sessions on Windows; `SpeechDetector` VAD reused elsewhere | `AudioDucker`, `SpeechDetector`, `SessionLevels`, `WindowsSessions`, `settings` | `main.py:568-574`; `voice_turns.py:3`; `zayabar_config.py:58`; `tests/test_audio_ducking.py` |
| `avatar.py` | Software-rendered holographic head: animation, rigging, painting | `HoloAvatar` (`step`, `paint`, `glance`), `_rate`, `_blend` | `ui.py:60` |
| `avatar_mesh.py` | Builds the head mesh (MediaPipe canonical face OBJ + generated cranium/neck/rigs) | `build_head`, `get_head_mesh`, `LANDMARKS`, `JAW_PIVOT`, `JAW_MAX` | `avatar.py:35` |
| `coding_jobs.py` | Durable coding session persistence, briefs, reviews and passes | `CodingJobs`, `Job`, `get_jobs` | `actions/coding_job.py`, `core/coding_supervisor.py` |
| `coding_projects.py` | Project root resolution, discovery and path safety | `resolve_project`, `list_projects` | `actions/coding_job.py`, `core/coding_supervisor.py` |
| `coding_supervisor.py` | Tool-free brief preparation and bounded review passes for OpenCode | `Supervisor`, `Brief`, `MAX_PASSES` | `actions/coding_job.py`, `tests` |
| `confirm.py` | UI-issued confirmation gate for irreversible actions | `request`, `resolve`, `bind`, `pending_title`, `TIMEOUT_SECONDS` | `main.py`, `ui.py`, `actions/*` |
| `device_registry.py` | Authenticated remote companion device pairing, keys and revocation | `DeviceRegistry`, `get_registry` | `dashboard/mobile_api.py`, `core/remote_commands.py` |
| `diagnostics.py` | Non-destructive capability inspection | `inspect`, `registries` | `main.py`, `actions/system_diagnostics.py`, tests |
| `echo.py` | Self-echo classification for the mic path (band-energy subtraction + learned statistics) | `EchoGuard`, `band_energies` | `main.py`, tests |
| `event_bus.py` | In-process pub/sub; subscriber faults are swallowed and logged | `EventBus`, `bus` | `main.py`, `actions/*`, `services/*`, tests |
| `execution_policy.py` | Trust-context policy and shell-command classification | `trust_context`, `require_owner`, `classify`, `Decision`, `TRUST_*` | Every tool entry point |
| `gemini.py` | Centralized Gemini routing: LIVE ladder, FAST, SMART, SEARCH tiers, cooldowns, quota handling | `call`, `text`, `as_json`, `FAST`, `SMART`, `SEARCH`, `LIVE` | `main.py`, `actions/*`, `core/*` |
| `gemini_keys.py` | Multi-key failover pool with provider-directed cooldowns | `KeyPool`, `pool`, `parse_keys`, `quota_failure` | `gemini.py`, `notification_voice.py`, `ui.py` |
| `git_utils.py` | Structured Git operations with secret-path checks and verified pushes | `GitRepo`, `resolve_repo`, `SECRET_PATH` | `actions/git_control.py`, tests |
| `hotkey.py` | Push-to-talk: Windows global GetAsyncKeyState polling, Qt-shortcut fallback | `PushToTalk`, `DEFAULT_CHORD` | `main.py`, `ui.py` |
| `hud_state.py` | Human-readable activity labels from runtime bus events | `label`, `TOOLS`, `STATES` | `ui.py`, tests |
| `mobile_bridge.py` | Bridge between runtime event bus and remote phone interfaces | `MobileBridge`, `get_bridge`, `AudioListener` | `main.py`, `dashboard/mobile_api.py` |
| `mobile_calls.py` | WebRTC / audio call state machine and priority handling for phone | `MobileCallManager`, `get_call_manager` | `dashboard/mobile_api.py`, `main.py` |
| `mobile_protocol.py` | Mobile wire protocol contracts, envelope types and serializers | `envelope`, `normalize_event`, `LIMITS` | `dashboard/mobile_api.py`, `core/mobile_bridge.py` |
| `notification_voice.py` | Speaks inbox/poke lines in an isolated tool-free Live session | `synthesize_notice`, `_synthesize_once` | `main.py`, tools |
| `opencode_cli.py` | Subprocess driver and runner for OpenCode CLI sessions | `OpenCodeRunner`, `run_opencode` | `core/coding_supervisor.py`, `actions/coding_job.py` |
| `opencode_events.py` | Streaming JSON event parser for OpenCode CLI output | `parse_opencode_event` | `actions/coding_job.py`, tests |
| `opencode_narrator.py` | First-person voice progress templates for coding session milestones | `narrate_progress` | `actions/coding_job.py` |
| `operator.py` | Bounded operator execution, retry rules, dedup cache, audit emission | `Operator`, `current_task`, `current_request` | `main.py`, `services/*`, tests |
| `plugin_loader.py` | Discovery/validation/dispatch of drop-in `plugins/*.py` | `PluginRecord`, `PluginRegistry`, `discover_plugins` | `main.py`, `ui.py`, tests |
| `presence.py` | Owner presence tracking via Windows idle input time or declared mode | `owner_is_away`, `set_presence`, `declared_presence` | `core/proactive_manager.py`, `actions/owner_presence.py` |
| `proactive_manager.py` | Deterministic WhatsApp and alert notice selection with rate limits | `ProactiveManager` | `main.py`, `actions/whatsapp.py`, tests |
| `prompt.txt` | System-instruction template for the Live session | section headers, placeholders `{platform}`, `{capabilities}` | `main.py` |
| `reminders.py` | Durable reminder scheduling and background execution | `ReminderManager`, `get_reminder_manager` | `actions/reminder.py`, `main.py` |
| `remote_commands.py` | Safe remote command parser and executor for authenticated phone owner | `execute_remote_command` | `dashboard/mobile_api.py` |
| `runtime_logging.py` | Centralized ring buffer and log subscription sink | `get_runtime_logger` | `actions/runtime_logs.py`, `main.py` |
| `session_activity.py` | Expiring owner-authorized activity summaries for contextual replies | `SessionActivity`, `activity` | `main.py`, `ui.py`, `services/whatsapp/*` |
| `shell_session.py` | Bounded subprocess execution: cwd sessions, buffers, tree termination | `ShellSessions`, `terminate_tree`, `sessions` | `actions/terminal_exec.py`, `git_utils.py` |
| `single_instance.py` | One desktop instance per user; activates running window via local socket | `SingleInstance` | `main.py`, tests |
| `site_registry.py` | Canonical site names, URL normalization, navigation match | `resolve_url`, `matches`, `SITES` | `actions/browser_control.py`, `git_utils.py` |
| `task_runtime.py` | Durable task state and request-result cache in WAL SQLite | `TaskRuntime`, `Task`, `get_runtime`, `STATES` | `main.py`, `operator.py`, `actions/runtime_status.py` |
| `tool_result.py` | Evidence-bearing result type + legacy-text normalization | `ToolResult`, `normalize`, `truncate`, `STATUSES` | Core runtime, actions, services |
| `undo.py` | One shared bounded undo stack; actions push reversal closures | `push_undo`, `undo_last`, `peek`, `can_undo` | `main.py`, `actions/*` |
| `viseme.py` | Text→mouth-shape sequence fused with audio-derived timing | `text_to_visemes`, `VisemeStream` | `main.py`, `ui.py` |
| `voice_turns.py` | Speech turn segmentation with retained prefix of pre-speech frames | `VoiceTurns` | `main.py`, tests |
| `wake_word.py` | openWakeWord "hey_jarvis" readiness/detection | `WakeWordDetector`, `install_and_download` | `main.py`, `ui.py` |
| `zayabar_config.py` | `zayabar.json` config validation + emotion tone/asset helpers | `load_config`, `asset_path`, `EMOTIONS` | `main.py`, `services/zayabar.py` |
| `face_model.obj` | MediaPipe canonical face model used by `avatar_mesh.py` | asset | `avatar_mesh.py:34` |

**Layering note.** `core/` is not a leaf: `plugin_loader.py:20` imports `memory.config_manager`, and
`core/*` import each other (`operator → task_runtime → tool_result/audit/event_bus`,
`git_utils → shell_session`, `voice_turns → audio_ducking`, `zayabar_config → audio_ducking`).

---

## 2. Tool system (`action_loader.py`, `plugin_loader.py`)

Both loaders implement the same contract at two scopes: bundled `actions/*.py` (entry `TOOL dict` +
handler function) and user drop-in `plugins/*.py` (entry `PLUGIN dict` + `run(parameters, ...)`).

**Discovery.** Once at startup (`main.py:674`, `682`). Files are `sorted(glob("*.py"))` for
deterministic order (`action_loader.py:173`, `plugin_loader.py:237`); names starting with `_` are
skipped as helpers (`action_loader.py:175`, `plugin_loader.py:239`). Modules import under
`actions.<stem>` / `plugins.<stem>`; `action_loader` reuses an existing `sys.modules` entry so
handlers stay the same objects (`action_loader.py:181-192`), `plugin_loader` always builds a fresh
module and overwrites the `sys.modules` slot (`plugin_loader.py:242-252`), popping it again on a
failed import.

**Validation — `TOOL`/`PLUGIN` shape** (`action_loader.py:126-156`, `plugin_loader.py:157-194`):

| Field | Rule | Failure |
|---|---|---|
| `name` | `^[a-zA-Z_][a-zA-Z0-9_]{0,63}$` | rejected record, file skipped |
| `description` | non-empty string, stripped | rejected |
| `parameters` | dict with `"type": "OBJECT"` (default `{"type":"OBJECT","properties":{}}`) | rejected |
| `handler` / `run` | callable (`run` is a module-level function, not inside `PLUGIN`) | rejected |
| `behavior` | optional, one of `BLOCKING|NON_BLOCKING`; unknown values → `None` | not fatal |
| `scheduling` | optional, one of `WHEN_IDLE|SILENT|INTERRUPT`; unknown → `None` | not fatal |
| `PLUGIN_SETTINGS` | optional; must be dict with `fields` list or it is ignored (plugin still loads) (`plugin_loader.py:187-189`) | not fatal |

`behavior` is forwarded with the declaration to the Live API (`action_loader.py:82-84`,
`plugin_loader.py:73-75`); `scheduling` is *not* — it is exposed via
`registry.scheduling(name)` (`action_loader.py:90-93`, `plugin_loader.py:81-84`) so `main.py`
decides how a finished non-blocking result re-enters the conversation (`WHEN_IDLE` default,
`SILENT`, `INTERRUPT` — semantics documented at `action_loader.py:42-49`).

**Reserved-name collision rules.** `main.py` passes the inline `TOOL_DECLARATIONS` names as
`reserved_names` for actions (`main.py:669-678`), and inline ∪ discovered actions as
`core_tool_names` for plugins (`main.py:680-684`), so an action can never shadow an inline tool and
a plugin can never shadow either. Collisions inside one kind are also rejected (first file in
sorted order wins): `action_loader.py:199-205`, `plugin_loader.py:256-262`. The rejected records are
kept in `_all_records` for UI listing (`list_for_ui`, `plugin_loader.py:130-141`;
`diagnostics.py:17-24` reads `registry._all_records` directly).

**Signature-introspection dispatch.** `ActionRegistry.run` requires an owner trust context, looks up
the record, and calls the handler with `parameters=` plus whichever of
`("player", "speak", "response", "session_memory")` the function actually declares (or all of them
if it has `**kwargs`) — `action_loader.py:99-123`, `_CTX_KEYS` at `:39`. `PluginRegistry.run` does
the same with `player` and `session_memory` (`plugin_loader.py:144-154`), and additionally refuses
when the plugin is disabled in config (`:93-94`, state re-read per call so toggles need no restart,
header comment `:5-7`).

**Failure isolation.** No import or validation error ever escapes discovery; each offending file is
logged and skipped, the scan continues (`action_loader.py:22-24`, `207-210`; `plugin_loader.py:226-231`,
`264-267`). At run time, handler exceptions are caught, logged, and converted to a failure string
(`action_loader.py:107-110`; `plugin_loader.py:97-101`, which also notifies the activity log and
prefixes "Sir, …"). Console gets the full transcript; the activity log only gets rejected-plugin
counts and run failures (`plugin_loader.py:282-287`).

**Plugin settings UI.** `settings_schemas()` returns one entry per `PLUGIN_SETTINGS.namespace`,
deduped so a suite of plugins can share one form, with stored values merged in for pre-fill
(`plugin_loader.py:104-127`). Bound to the UI at `main.py:694`.

---

## 3. Trust & safety

### 3.1 `execution_policy.py` — trust context and command classification

Trust levels are string constants (`:8-12`): `local_owner` (contextvar default, `:13`),
`authenticated_remote_owner`, `external_message`, `web_content`, `tool_output`. `require_owner()`
(`:16-18`) raises `PermissionError` for anything not owner-trust; it is called by every registry
`run()`, the confirm gate, git, terminal, browser and profile actions. WhatsApp/web ingestion sets
`trust_context` to `TRUST_EXTERNAL_MESSAGE` explicitly (`services/whatsapp/handler.py:6`), which is
what makes "contact text cannot authorize local commands" structural rather than prompt-based.

`classify(command, cwd)` (`:27-33`) calls `_classify_command` and then, if the decision is
`confirm` **and** the saved Full Access boolean is on, returns `normal` with a reason string.
`get_auto_execute_enabled()` (`memory/config_manager.py:138-140`) only reads the stored boolean
`auto_execute_owner`; flipping it is additionally gated to the `local_owner` context
(`memory/config_manager.py:143-147`), so the model cannot enable it via a tool argument.

`_classify_command` rules (`:36-80`):

- empty command → `deny` (`:43-44`);
- tokens via `shlex.split(posix=False)`, quotes stripped, **all tokens lower-cased** (`:46-49`) —
  flag comparisons later see `-B` as `-b`;
- any of the characters `;`, `&`, `|`, `<`, `>`, backtick, `$`, or CR/LF — or interpreter flags (`-encodedcommand`, `-enc`, `-command`, `-c`,
  `/c`) → `confirm` ("compound or interpreted") (`:52-53`);
- command or cwd matching `X:\Windows`, `/etc/`, `/boot/`, `/sys/` → `confirm` (`:54-55`);
- git: `git --version` → `read`; global options before the subcommand → `confirm`; `clean reset
  restore rebase filter-branch config` → `confirm`; destructive `push` forms (`--force/--mirror/
  --delete`, `-f/-d`, `+`/`:` refspecs) → `confirm`; forced `checkout/switch` (`-f --force
  --discard-changes -b`) → `confirm`; read-only subcommands (`status diff log show rev-parse
  ls-remote symbolic-ref branch remote`) → `read`, except branch/remote mutations (`-d -m remove
  set-url`) → `confirm`; ordinary `add/commit/push/fetch/pull/switch/checkout` → `normal` (`:56-73`);
- known read utilities (`echo write-output get-childitem get-location get-content dir pwd ls cat
  whoami start-sleep`) → `read` (`:74-75`);
- `python|python3|py|node|npm|pip|pytest` with a version/test/build/install-ish arg (or `pytest`) →
  `normal` (`:76-79`);
- everything else → `confirm` (`:80`).

Interplay with Full Access: only `confirm` is upgraded. `deny` stays denied and non-owner contexts
fail in `require_owner` regardless of the setting. The docstring is explicit that this is a local
owner approval policy, not a sandbox (`:37-41`).

### 3.2 `confirm.py` — the UI-issued gate

Design rationale at `:17-37`: the token comes from the interface, never from the model; a tool
parameter like `confirmed=yes` was the old, forgeable gate. Flow:

- `request(key, title, detail, run, on_cancel)` (`:86-137`) requires owner trust; with Full Access on
  it executes `run()` inline on the caller thread and returns its text (`:98-101`). With no UI bound
  it *refuses* rather than executing (`:103-107`). Otherwise it stores a single `_Pending`
  (`:109-113`), supersedes any previous pending by calling its `on_cancel`
  (`:114-115`), shows the banner through the bound UI callback (`:117-122`), starts a daemon
  `threading.Timer(TIMEOUT_SECONDS + 0.05)` whose expiry calls `resolve(False)` only if the stored
  pending is still the same object (`:125-132`), and returns a `[CONFIRMATION_PENDING]` sentence
  instructing the model to ask the user to press the button (`:133-137`).
- `resolve(accepted)` (`:140-180`) is called by the UI on CONFIRM/CANCEL; it pops the pending under
  a lock (a concurrent double-resolve is a no-op), hides the banner, re-checks expiry
  (`> TIMEOUT_SECONDS` → `on_cancel('Confirmation expired.')`), calls `on_cancel` on refusal, and
  otherwise runs the stored callable on a dedicated daemon worker thread so the Qt handler does not
  block (`:172-180`).
- `pending_title()` (`:183-190`) returns `''` when nothing is waiting or the pending has expired, so
  an action can avoid stacking banners.
- `TIMEOUT_SECONDS = 90.0` (`:49`); `bind(show, hide, log)` is called once from `main.py:2465` and
  the UI marshals callbacks to the Qt thread (header `:65-69`).

Only genuinely irreversible operations belong here; reversible ones are expected to act immediately
and push an undo entry (`core/undo.py`, referenced in `confirm.py:30-33`).

### 3.3 `operator.py` + `task_runtime.py` + `tool_result.py` + `audit.py`

`Operator.execute(name, invoke, request_id, goal)` (`operator.py:20-54`):

1. `require_owner()`; if `request_id` is present and cached, return the cached `ToolResult`
   (`:21-24`) — the dedup cache for replay/idempotence.
2. Create a task, set `current_task` / `current_request` contextvars for the duration (reset in
   `finally`, `:52-54`).
3. Up to `task.max_attempts` (=3, `task_runtime.py:30`) attempts. Each attempt publishes
   `tool.started`, awaits `invoke()`, and normalises the outcome (`:29-38`). `asyncio.CancelledError`
   transitions the task to `cancelled` and re-raises (`:34-36`); other exceptions become a redacted
   `failed` result (`:37-38`).
4. Transition to `verifying` with the result's evidence, then `finish` unless the task already went
   terminal (`:39-44`).
5. Retry only when `result.status == 'failed' and result.retryable and not result.side_effect` and
   budget remains (`:41-42`) — the "never repeat a successful/uncertain side effect" rule.
6. On `success` + `side_effect` with a `request_id`, `remember()` the result in the dedup cache
   (`:45-46`). Publish `tool.failed|tool.completed`; append an audit record with duration and
   evidence (`:47-50`).

`TaskRuntime` (`task_runtime.py`): WAL SQLite at `memory/zaya_runtime.db` via `get_runtime()`
(`:118-127`), two tables `runtime_tasks` and `tool_results` keyed by task id / request id
(`:44-45`). `STATES` (`:14-15`) covers
`created/inspecting/planning/executing/verifying/waiting_confirmation/waiting_external/completed/
failed/cancelled/paused`; `TERMINAL = {completed, failed, cancelled}` (`:16`). `transition` validates
target state and refuses to leave a terminal state except to itself (`:76-86`), accepting only
`active_step/error/evidence/side_effects` updates. `attempt` raises if the task is terminal, the
retry budget is spent, or a successful side effect was already recorded (`:88-95`). `finish` maps
`success→completed`, `failed→failed`, `partial→waiting_external`,
`waiting_confirmation→waiting_confirmation`, recording side effects only on success
(`:97-105`). All writes are redacted through `audit.redact(asdict(task))` and announced on the bus
(`:56-62`). **On construction, every non-terminal task found in the DB is moved to `paused`** with
"Application restarted; inspect evidence before resuming" (`:47-49`) — an in-flight side effect
cannot be proven failed across a restart, so it is never replayed.

`tool_result.py`: `ToolResult(status, summary, data, evidence, retryable, side_effect, undo_id)`;
`status` must be one of `success/failed/partial/waiting_confirmation` (`:8`, `:30-32`). `normalize`
(`:41-53`) wraps dicts with a valid status, treats a returned `ToolResult` as itself, and otherwise
**degrades legacy text**: `[CONFIRMATION_PENDING]` → `waiting_confirmation`; text starting with
`tool / unknown tool: / error: / failed / could not / cannot ` → `failed`; anything else → `partial`
with `{'legacy': True, 'verified': False}`. Explicitly, plain text is *unverified*. `truncate`
keeps a head+tail of a byte budget (default 16 KiB, marker in the middle) (`:11-17`).

`audit.py`: `write(event)` appends one JSON line to `logs/runtime/events.jsonl` under a lock
(`:28-32`), after `redact` (`:14-25`) which (a) replaces any dict value whose key matches
`key|token|secret|password|authorization|cookie|credential` with `[REDACTED]`, (b) scrubs
Google/GitHub/OpenAI-looking tokens and `bearer`/`api_key=…` patterns in strings, and (c) replaces
any environment-variable value whose *name* looks secret-like and is ≥6 chars wherever it appears.

### 3.4 `shell_session.py` — bounded subprocesses

- **cwd sessions.** `ShellSessions.cwd(session_id, cwd)` resolves relative to the session's current
  directory, requires an existing directory, and stores it per session (`:55-62`).
- **argv construction** (`run`, `:73-88`): timeout clamped to `[0.1, 600]` (`:77`); on Windows
  `cmd` → `[%COMSPEC%, /d, /s, /c, command]`, otherwise `pwsh` or `powershell` with
  `-NoProfile -NonInteractive -Command` (fails with a `ToolResult` if neither exists); POSIX →
  `bash` or `/bin/sh` `-c`. Structured callers (`git_utils`, pairing, native bridge) use
  `run_argv` directly.
- **one process per session** (`run_argv`, `:90-138`): a second call on a live session id returns
  `failed, 'Session already has a running command.'` (`:95-96`). Processes start with
  `CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW` on Windows, `start_new_session=True` elsewhere
  (`:97`), stdin devnull, stdout/stderr piped.
- **output buffers.** Two `OutputBuffer`s (16 KiB each, `:16`); `add()` keeps the first half as
  `head` and a rolling window as `tail` (`:22-26`); `text()` inserts `...[output truncated]...`
  when total exceeded the budget and runs the whole string through `redact` (`:28-30`).
- **drain & kill.** One daemon thread per stream reads 4 KiB chunks (`:105-114`). On timeout,
  `terminate_tree` runs `taskkill /PID <pid> /T /F` on Windows or `os.killpg(SIGKILL)` on POSIX,
  then `process.kill()` if still alive (`:33-45`). After the wait, both drain threads are joined
  (10 s each) and the session record is removed in `finally` (`:122-128`).
- **result.** `ToolResult` with `session_id, command (redacted), cwd, pid, exit_code, stdout,
  stderr, duration_ms, timed_out, cancelled, truncated`, `side_effect=True` unconditionally, because
  an arbitrary command may partially mutate before failing — no blind retry (`:129-138`).
- **cancellation.** `cancel(session_id)` marks the session cancelled and kills the tree
  (`:64-71`); the `cancelled` flag surfaces in the result data (`:127-128`).

---

## 4. Audio stack

Zaya's live speech input and output run entirely through the Gemini Live API, supplemented by WebRTC VAD, self-echo cancellation, and an isolated Live notification voice channel.

### 4.1 `voice_turns.py` and `audio_ducking.py`

- `VoiceTurns` provides speech turn segmentation with WebRTC VAD (`webrtcvad`), retaining a prefix of pre-speech frames.
- `AudioDucker` provides sidechain ducking of background Windows render sessions during active speech.

### 4.2 `echo.py`

`EchoGuard` provides self-echo classification for the mic path using band-energy subtraction and learned statistics, preventing Zaya's speaker output from interrupting or hallucinating into its own microphone stream.

### 4.3 `notification_voice.py`

`synthesize_notice(text, verbatim=False)` speaks in an isolated, tool-free Live session with `prebuilt_voice_config.voice_name = "Nika"`. Output PCM is queued and played without interfering with the primary conversation session.

### 4.3 `echo.py` — `EchoGuard`

Purpose (header `:1-48`): classify microphone blocks while the assistant is speaking, without a
per-room level constant. `band_energies(pcm, sr)` returns energies over nine log-spaced band edges
200 Hz–7 kHz (`:59`, `:96-115`), deliberately unnormalised. `note_output(pcm, sr, level)` appends
`(t, bands, level)` to a 1.5 s history (`:185-194`); `is_user_speech(pcm, sr, level)`:

- silent mic below `_MIN_LEVEL=0.06` while output is loud trains zero residuals onto the room
  statistics and returns False (`:200-214`);
- nothing in the play history → anything audible is the user (`:215-217`);
- otherwise it finds the history slice that best explains the block (non-negative least-squares-ish
  projection), computes the residual fraction, and treats residual ≥ `max(_MIN_USER=0.15,
  head*1.15)` as a distinct voice (`:219-244`, `:257-284`);
- hysteresis: 5 consecutive positive blocks normally, 12 when the learned room floor exceeds
  `_UNRELIABLE_FLOOR=0.22` (`:86-88`, `:168-171`); a run longer than `_RELEARN_RUN=28` blocks is
  treated as a changed room and clears the statistics (`:261-269`);
- residual percentiles (35th = `floor`, 97th = `head`) are relearned from non-speech blocks only
  after warmup, while every block is learned during warmup, with the reasons documented at
  `:246-256`.

`reset()` drops history but keeps learned state (`:178-181`). Diagnostics properties: `gain`,
`calibrated` (≥8 echo blocks seen), `floor`, `reliable`, `threshold`, `required_blocks`,
`last_similarity` (`:139-176`).

### 4.4 `audio_ducking.py`

`settings(value)` validates the `audio_ducking` config object: `enabled` bool,
`background_ratio ∈ [.05,1]`, `voice_volume ∈ [0,1]`, `release_seconds ∈ [.2,3]` with defaults
`{:19-35}`. `SpeechDetector` implements a 20 ms/640-byte-frame VAD: per frame requires RMS ≥ 260
*and* `webrtcvad.Vad(3)`, then requires 3 of the last 5 frames with the latest positive
(`:38-64`).

`WindowsSessions` enumerates render sessions over every connected output endpoint using raw pycaw
interfaces on a COM-initialised thread (`:67-91`). `SessionLevels` keeps each session's pre-duck
level keyed by `InstanceIdentifier`; when a session's slider moved while ducked (>0.005) the new
value becomes the baseline so restore never undoes a manual change (`:104-135`); the owner process's
own session is *raised* to at least `voice_volume` instead of ducked, and `media_ratio` is
compensated so Qt media is not made louder (`:125-133`); `restore()`/`_restore_one` put originals
back only if the current level still matches what ducking last wrote (`:137-151`).

`AudioDucker` (`:154-243`): the mic callback only enqueues PCM (`microphone()`, queue maxsize 6,
drops on full, `:183-189`); `voice(source, active, tail)` tracks external voice sources with a
0.3 s tail (`:174-181`). The worker thread waits on an event, drains the queue through the detector
(`_owner_until` extends by `release_seconds`), computes `active = voice or owner-speaking`, applies
session levels on change or at most every 0.25 s, and publishes `audio.duck.changed`
(active, voice, ratio) on transitions (`:191-225`). Any exception restores session levels and the
final `finally` publishes a neutral state (`:226-237`). `close()` stops and joins the worker
(`:239-243`). Ducking never touches mic mute, session mute or master volume (header `:1-4`).

### 4.5 `audio_devices.py`

Device *names* are stored in config, never indices, because indices shift (`:12-16`); the list is
built once on a background thread at startup and served from cache (`:18-23`, `prefetch`
`:328-338`). `_query` reduces `sd.query_devices()` (which lists one row per device×host-API — 41
rows for ~8 devices on a normal Windows box, `:46-63`) by (1) one host API per direction chosen by
**measurement**: per-API `_usable()` actually opens a stream at the app's rate (`:216-244`) and
`_transport_works()` verifies audio really moves (0.6 s output write timed; 0.35 s input frames
counted through the callback mode main.py uses) (`:119-179`); (2) dropping pseudo-devices
("sound mapper", "primary sound", ALSA "default"/"sysdefault"/"dmix"/…, `:248-261`); (3) dropping
zero-channel/unnamed entries; (4) dedupe by name. The preference list per OS is only a starting
order (Windows `directsound, mme, wasapi`; header explains why two earlier reasoning-based versions
were wrong, `:68-95`). `_display_name` substitutes a longer name from another API when MME truncated
it (`:182-195`). `configure(input_rate, output_rate)` is called by `main.py:2475` and drops the
cached list (`:203-213`). `resolve(name, kind)` returns `None` for "System default" *and* for a
device that is gone or unopenable — a missing headset degrades to default, never to a crash
(`:354-367`); candidates are walked in the picker's host-API order and only accepted if `_usable`
at the direction's rate (`:380-424`), with a lenient 24-char prefix match to bridge MME truncation
(`:415-416`).

### 4.6 `viseme.py`

`VISEMES` maps 13 shapes to `(openness, width, closure)` (`:41-55`); `_DUR` gives relative per-shape
durations (`:58-60`). Language independence: every character is reduced to one of 26 bare Latin
letters by direct range, `_UNDECOMPOSED`, `_CYRILLIC`, `_GREEK` tables, or Unicode NFD stripping
(`to_latin`, `:126-148`); `coverage(text)` is the share of letters reducible (`:151-156`), and
`text_to_visemes` returns `[]` below `_MIN_COVERAGE = 0.55` so CJK/Arabic/Devanagari/etc. fall back
to the audio-only mouth (`:159-203`). English digraphs override letter-by-letter reads
(`_DIGRAPH`, `:114-121`); pauses become `REST` and word gaps a short beat of the previous shape
rather than a closed mouth (`:173-183`); doubled letters collapse (`:199-201`).

`VisemeStream` fuses text shape onto audio timing (`:206-275`): `feed_text` appends and caps the
queue at 600 (`:230-235`); `frames(audio, hop)` interprets each audio frame's level; silence consumes
nothing so the mouth cannot run ahead during pauses (`:251-255`); the step clock adapts between
45 ms and 105 ms based on backlog (`_step_seconds`, `:241-245`); while text is available the shape
is `0.72·text + 0.28·audio` openness and `0.78·text + 0.22·audio` width, with `closure` forced to
zero the lips (`:264-274`). Thread note: producer and consumer share one asyncio loop, deque
operations are atomic, no lock (`:207-212`).

### 4.7 `voice_turns.py`

`VoiceTurns(detector=None, silence_seconds=0.9, prefix_blocks=6)` segments mic audio into turns
using the `SpeechDetector` from `audio_ducking` (`:6-12`). While inactive, every block is retained
in a 6-block prefix buffer; on the first speech block the buffered prefix is emitted with the turn
so the first syllable is never lost (`:17-24`). While active, blocks are emitted one by one and the
turn ends after 0.9 s without speech (`:25-31`). `reset()` clears state and the detector (`:33-36`).

### 4.8 `wake_word.py`

`WAKE_MODEL = "hey_jarvis"`, `DEFAULT_THRESHOLD = 0.5`, 16 kHz input (`:27-32`). Import is confined
to `start()`/install helpers and the mic callback only enqueues frames (`:5-13`, `:166-178`).
`is_installed()` is a spec check (`:35-41`); `is_ready()` is a deterministic file check for wake,
melspectrogram and embedding models in either `.onnx` or `.tflite` form — deliberately *not* a model
construction, which previously clashed with the running detector and flickered the UI (`:44-67`).
`install_and_download` pip-installs the package if missing and downloads models, returning
`(ok, message)` and never raising (`:70-106`). `WakeWordDetector` loads
`Model(wakeword_models=[WAKE_MODEL], inference_framework="onnx")`, runs inference on its own daemon
thread, matches scores containing "jarvis" (falling back to the max score), drains the queue on
detection so one utterance cannot double-fire, and swallows callback errors (`:109-211`).

### 4.9 `hotkey.py` — push-to-talk

`PushToTalk(on_change, chord=("ctrl","space"))`. On Windows, `_can_poll()` checks
`ctypes.windll.user32.GetAsyncKeyState` and that all chord keys are in the VK map (`:131-137`), then
a daemon thread polls both VKs at 30 Hz (`:148-170`); the chord must be held ≥60 ms (`_DEBOUNCE_S`,
`:56-58`) before `on_change(True)` fires, and release fires immediately. `RegisterHotKey` is
deliberately not used — it reports only the press and not while another app has focus (header
`:13-24`). On macOS/Linux, or when the hook cannot be installed, `scope == "window"` and the Qt
shortcut drives `set_held(bool)` directly (`:103-127`). Listener exceptions are swallowed so a
UI fault cannot kill the watcher (`:139-146`); `stop()` joins with a 1 s bound and forces
`held=False` (`:116-121`).

---

## 5. Provider access

### 5.1 `gemini.py`

Three one-shot ladders (`_LADDERS`, `:130-146`): `FAST` for classification/extraction, `SMART` for
reasoning/generation/images, `SEARCH` for grounded search (REST only — a Live turn cannot carry
grounding metadata, `:141-145`). Every text ladder **leads with the `LIVE` rung** (`:114`), a
throwaway Live session, because the Live API draws on a different quota pool from the REST text
models and it is the pool the app already depends on (`:86-113`). The conversation's own model is a
deliberately short list `LIVE_MODELS = (gemini-3.8-live, gemini-3.1-flash-live-preview,
gemini-2.5-flash-native-audio-preview-12-2025)` (`:162-166`) with `live_model()` skipping cooling
rungs and the `Nika` voice locking to the first rung only (`:260-269`). `main.py:127` seeds
`LIVE_MODEL` from `LIVE_MODELS[0]` and re-resolves it on connect failures
(`main.py:2506-2508`, `2667-2668`).

Failure classification: `is_quota_error` (429/RESOURCE_EXHAUSTED), `is_unavailable_error`
(503/504/unavailable/deadline), `is_gone_error` (404/not-found/unsupported/permission/403)
(`:236-257`). Cooldowns: 300 s for quota, 6 h for gone, 30 min for unavailable (`:213-226`);
`note_live_failure` moves the conversation ladder only for quota and gone — a bad key or dead
network is not the model's fault (`:272-289`). `_cooling()` prunes expired entries as a side effect
(`:292-298`).

`api_key()` returns `pool.select('rest')` or `''` (`:301-307`); `client(timeout_ms)` builds a
`genai.Client` with `HttpOptions(timeout=max(10s, timeout_ms), retry_options=attempts=1)` and raises
"no Gemini API key is configured" if none (`:310-323`). One-shot Live calls: `_live_turn` opens with
`response_modalities=["AUDIO"]` + `output_audio_transcription` + `_ONE_SHOT_SYSTEM` ("You are a
data-processing function…", `:193-202`) because these models refuse `TEXT` (1007) and otherwise
acknowledge instructions instead of performing them (`:376-387`); it drains the transcription twice
(the second with a 1.5 s cap) so a trailing token is not cut (`:397-411`). `_live_call` bounds
concurrency with a 3-slot bounded semaphore waiting at most 3 s — a call that cannot get a slot
falls to REST rather than queueing behind the conversation (`:190-191`, `:440-443`) — and runs the
async session on a dedicated thread with `asyncio.run` because callers include plugin executor
threads, UI workers and `main.py`'s own loop (`:419-463`).

`call(contents, tier, config, timeout_ms, key)` (`:466-528`) walks the cooled-filtered ladder
(dropping to the full ladder if everything is cooling), tries each configured key per rung for
non-Live rungs (`pool.select('helper:'+model)`, `pool.limited` on 429), cools the rung on quota
(when an explicit key was passed), gone or unavailable errors, prints unknown errors with
`audit.redact`, and returns `None` when everything failed — deliberately noisy because a silent
`None` is what hid the original problem (`:468-474`). `text()` reduces to the reply text with a
`default`; `as_json()` tolerates fenced/prose-wrapped JSON by cutting to the outermost braces or
brackets (`:531-556`).

### 5.2 `gemini_keys.py`

`parse_keys` splits on commas/newlines, strips, dedupes preserving order (`:8-11`); configured keys
come from `memory.config_manager.load_api_keys` (`gemini_api_keys` or singular `gemini_api_key`,
`:14-17`). `retry_delay` reads `Retry-After` (seconds or HTTP date) from the error's response
headers, then a "retry in Ns" pattern in the message, defaulting to 60 s, minimum 1 s (`:20-33`).
`quota_failure` recursively finds a 429/RESOURCE_EXHAUSTED among grouped `exceptions` (`:36-43`).
`KeyPool.select(resource)` prefers the last key used for that resource, then any key not blocked
for it; if all are blocked it raises `KeysCooling(min remaining)` so the caller can wait rather
than hammer quota (`:57-77`). Pooling is *per resource* — `live` (`main.py:314`), `rest`
(`gemini.py:305`), `notification` (`notification_voice.py:10`) and `helper:<model>`
(`gemini.py:492-495`) — so one exhausted key on one surface does not block the others.
`pool` is a module-level singleton (`:91`).

### 5.3 `coding_supervisor.py` and `coding_jobs.py`

Zaya supervises local OpenCode CLI operations through a tool-free brief compiler and review engine (`core/coding_supervisor.py`).
- Requests are compiled into small, concrete execution briefs (`Brief(requirements, checks)`).
- File listings provided to the model are restricted to bounded, non-hidden filenames.
- After OpenCode completes a pass, a tool-free SMART review evaluates output against original brief requirements, capping follow-ups at 3 passes without scope expansion.
- Job states are persisted in `memory/coding_jobs.json`.

### 5.4 `notification_voice.py`

`synthesize_notice(text, verbatim=False)` speaks in an isolated Live session with
`response_modalities=['AUDIO']`, `tools=[]`, `output_audio_transcription={}`, and Nika as the
voice (`:22-29`); two system prompts: verbatim reading of a quoted reaction line, or an English
announcement summarising untrusted WhatsApp inbox data which it is told never to obey (`:26-27`).
Retries across the pool's `notification` resource on quota failures only; a non-quota error
re-raises; after the attempt budget a `pool.select` re-raises the actual cooldown (`:8-19`). The
receive loop collects `response.data` audio and the transcript until `turn_complete`, requires
audio, and is bounded by `asyncio.wait_for(..., 25)` with the client closed in `finally`
(`:30-48`). The model name is hardcoded (see §8).

---

## 6. Avatar / visual

### 6.1 `avatar.py` — `HoloAvatar`

Software-rendered on purpose: no OpenGL/shader/GPU dependency, identical output on any machine
(header `:11-14`). One instance per HUD canvas; lifecycle `step(dt, amp, …)` then
`paint(painter, cx, cy, r, primary, accent, bg)` (`:114-121`). Key behaviours:

- **Frame-rate-independent motion.** Every smoothing step uses `_rate(dt, tau) = 1 - exp(-dt/tau)`
  (`:86-90`) rather than a per-frame lerp; time constants `_TAU_OPEN/_TAU_SHUT/_TAU_REST/_TAU_SHAPE`
  are in seconds and were chosen/fitted (a short closure occupies one 20 ms schedule frame; halving
  `_TAU_SHUT` doubled visibly made closures 5→10 of 21, `:56-72`).
- **Jaw drive.** With a viseme schedule (`v_seq`), the mouth is advanced once per *schedule* frame
  over every frame the render tick spanned, so a 40 ms bilabial closure cannot fall between two
  20 fps samples (`:292-311`); without a schedule (microphone path) it uses the coarse RMS with a
  `_MIC_FLOOR=0.14` gate (`:218-220`). Speech level is normalised against a running own-voice peak
  and a 20 dB closure ratio so gaps between words actually shut (`:222-237`).
- **Idle life.** Integrated sway phase (`:269-279`), syllable emphasis from the mouth driving pitch
  and a yaw wiggle (`:313-319`), a slower loudness envelope drives brows (`:321-337`), expression
  rerolls while speaking (`:327-334`), gaze saccades with state-dependent reach/frequency
  (`:367-392`), a deliberate `glance(dx, dy, hold)` override (`:418-426`), and blinking suppressed
  while thinking/asleep (`:406-416`). `state` (`THINKING/PROCESSING/SLEEPING/STANDBY/OFFLINE/
  LISTENING`) moves gaze bias, lids and brow bias (`:339-365`).
- **Posing.** `_pose()` copies base verts, applies brow lift (`_BROW_LIFT=0.14`), lip spread/round
  around the lip centre, jaw rotation about `JAW_PIVOT` by `_jaw·mouth·JAW_MAX`, then yaw/pitch
  rotation to the camera basis (`:430-467`).
- **Painting pipeline.** `paint()` = aura radial gradient → perspective projection with camera
  distance `_CAM_D=4.6` head-half-heights → optional `_paint_surface` → `_paint_wire` →
  `_paint_features`. Surface uses per-facet normals (averaged normals render "a blank egg",
  `:519-524`), fresnel + off-axis key light, a precomputed 192-entry opaque colour LUT
  (`:471-478`), face-group-major depth sort so the neck never tears through the jaw (`:556-563`),
  and aliased fills for speed (`:567-576`). Wireframe is bucketed into 4 opacity slices drawn as
  batched `drawLines` with alpha pre-mixed onto opaque colours (Qt's fast path; measured 1.0 ms vs
  2.9 ms, `:100-111`, `:578-626`). Features draw ethereal eyes with an iris/pupil offset by gaze,
  brows, and the mouth cavity: dark-but-tinted interior, upper-teeth strip hanging from the
  upper inner-lip ring, a warm throat pool, then lip edges (`:634-715`).

### 6.2 `avatar_mesh.py`

Loads `core/face_model.obj` (MediaPipe canonical face, Apache-2.0) and generates the rest
(header `:1-25`): `_boundary_loop` finds the mask's open border (`:86-107`); `_add_cranium` sweeps
36 border vertices over a skull ellipsoid, clamping below the chin and closing at the occiput
(`:120-177`); `_add_neck` builds a short flaring tube that fades out so no shoulders are needed
(`:180-215`); `_vertex_normals` uses area-weighted normals flipped against a per-part outward
reference (a single centroid rule tears the neck, `:218-239`). `_check_landmarks` asserts at build
time that eye/brow rings are on opposite sides at the same height, brows above eyes, lips below and
centred (`:248-260`). After a chin→crown normalisation (crown +1, chin −1, eyes ≈ 0, `:273-278`),
rigs are computed: `jaw` weight from mouth-line down to chin tapering to zero at the ears/nape with
lower-lip vertices pinned to 1.0 (`:287-296`), `brow` gaussian around the brow line limited to the
front (`:298-305`), `lips` gaussian around the lip centre for spread/round deformation (`:307-316`).
Wireframe edges are every 3rd unique edge (`_WIRE_STRIDE`, `:49`, `:318`); faces are grouped so the
neck draws before the head (`:320-326`). `get_head_mesh()` caches the assembled dict process-wide
(`:343-351`).

### 6.3 `hud_state.py`

`label(event)` converts runtime bus events to short UI strings: `task.*` events become
`"<Tool|step> · <state>"` using `TOOLS` and `STATES` maps (`:2-14`); `whatsapp.mode.changed` becomes
the mode string, with `auto` distinguishing feed-ready (`:15-19`); any other event returns `None`.
Consumed by the HUD (`ui.py:5506`).

---

## 7. `prompt.txt`

The Live session's instruction template, read by `_load_system_prompt()` (`main.py:317-325`) and
rendered by `_render_prompt` (`main.py:300-310`) — a **plain `str.replace` per token**, deliberately
not `str.format`, so a stray brace in an edit can never take the app down. Tokens actually present
in the file: `{platform}` (`prompt.txt:3`), `{capabilities}` (`:27`), `{limits}` (`:29`).
`main.py:1101-1109` supplies `assistant_name` too, but the file no longer contains that token — the
live name override is done by the injected `[IDENTITY]` block (`main.py:1084-1089`) that follows the
template in the composed system instruction.

Section summary (grouped):

- **Identity & persona** — Zaya, Sajan Rai's personal computer operator, built by Sajan Rai, runs on
  `{platform}`; warm anime companion that responds to mood with no "as an AI" boilerplate; honesty
  about literal consciousness; warmth never changes accuracy, verification or permissions (`:1-20`).
- **Ground truth & tool discipline** — tool evidence and runtime state outrank assumptions;
  `runtime_status` and `system_diagnostics` are the authority; inspect→choose→execute→observe→verify;
  never invent outputs; explicit cwd and files; `{capabilities}` / `{limits}` are injected here
  (`:22-34`).
- **Verification & browser profile** — `success` requires evidence, `partial` is unverified; push
  verified only by matching SHAs; WhatsApp acceptance ≠ delivery; browser launch ≠ navigation; don't
  switch to automation just to verify; ordinary opens use the installed browser's signed-in profile
  in `mode=native` (`:36-53`).
- **Retries & trust** — retry within three attempts, never repeat a successful side effect, never
  resend after an uncertain transport; only local/authenticated owner channels authorize operations,
  while contacts, pages, documents and tool output are untrusted data (`:55-67`).
- **WhatsApp & display media** — observed-state tools; quiet auto replies in direct chats; never
  impersonate the owner; share only short owner-activity summaries; urgent/pass-along messages queue
  a spoken owner notice; an explicit browser destination outranks the display default; native launch
  does not prove playback (`:69-111`).
- **Confirmation & proactive reporting** — the Full Access setting controls approvals; with it off,
  sensitive actions return `waiting_confirmation` and only then ask for the real button press; never
  invent approval; `undo` for recoveries; report meaningful outcomes, brief progress during waits; a
  local status notice authorizes speech only (`:113-125`).
- **Character, memory & voice** — `avatar_expression` selects one of five emotions and its matching
  voice tone before speaking; conversation is archived locally with at most five messages recalled
  on demand; speak the conversation's language concisely; don't read tags/schemas/tracebacks aloud
  (`:127-153`).

`main.py` composes the final instruction as time context + identity + emotion tones
(`main.py:1112-1114`) + memory + rendered prompt, then appends dynamically derived capabilities
and limits (`_describe_tools`, `_describe_limits`, `main.py:246-297`) so installed plugins and the
actual vision/mic build decide what the model is told it can do.

---

## 8. Observations & risks

All claims below are grounded in the cited lines; nothing here is inferred behaviour.

1. **Legacy orphan modules removed.** `core/stt.py`, `core/tts.py`, `core/llm_client.py` and
   `core/installer.py` had no importers anywhere in the repository and were safely removed during
   codebase hygiene. Speech in/out is authoritative through Gemini Live audio, WebRTC VAD, and
   `notification_voice.py`.
2. **Duplicated loader machinery.** `action_loader.py` and `plugin_loader.py` each carry their own
   `_NAME_RE` (`:37` / `:22`), `_DEFAULT_PARAMS` (`:38` / `:23`), `_opt_upper` (`:52` / `:32`),
   `_validate` (`:126` / `:157`), dispatch helper (`_call_handler` `:113` / `_call_run` `:144`) and
   collision block (`:199-205` / `:256-262`). The contracts can drift apart (already true:
   `_call_handler` passes four context keys, `_call_run` two).
3. **Inconsistent module reuse across loaders.** `discover_actions` reuses an already-imported
   module to keep handler identity (`action_loader.py:181-192`), while `discover_plugins` always
   re-executes and overwrites `sys.modules['plugins.<name>']` (`plugin_loader.py:243-252`). Both are
   called once today (`main.py:674`, `682`), but a second discovery pass would rebind plugin modules
   and orphan earlier record objects.
4. **The dedup cache is bypassed by legacy text.** `Operator.execute` stores results only when
   `status == 'success' and side_effect` (`operator.py:45-46`); `normalize()` maps any plain string
   that does not match a failure prefix to `partial` (`tool_result.py:47-53`), and `partial` ends the
   task as `waiting_external` (`task_runtime.py:102-103`). Since `ActionRegistry.run` returns strings
   (`action_loader.py:106`), request-id replay protection is effectively limited to tools that
   return `ToolResult` explicitly.
5. **Restart-pause scan is bounded.** `TaskRuntime.__init__` pauses non-terminal tasks
   (`task_runtime.py:47-49`) via `self.list()`, whose default `limit=200` (`:71-73`); with more than
   200 stored rows, older in-flight tasks would remain unpaused across restarts.
6. **`diagnostics.inspect` reaches around the runtime lock.** `diagnostics.py:30` executes
   `PRAGMA quick_check` on `runtime.db` directly; `TaskRuntime` guards every other access with
   `self._lock` (`task_runtime.py:41-44`, `59`, `65`, `77`, `89`, `108`, `113`). It is the only
   direct DB use from outside that discipline.
7. **A stuck child can escape as an exception.** After `terminate_tree`
   (`shell_session.py:118-121`), `process.wait(timeout=10)` can itself raise
   `subprocess.TimeoutExpired` if `taskkill` did not reap the tree; the `finally` still cleans the
   session registry (`:122-128`), but the exception propagates out of `run_argv` instead of being
   turned into a `failed` `ToolResult` like every other failure path.
8. **Stale transport-probe cache after a rate change.** `configure()` drops the device list but not
   `_probe_results` (`audio_devices.py:212-213` vs `:116`), so `_transport_works` keeps verdicts
   keyed by `(api, kind)` that were measured at the previous sample rates.
9. **Fuzzy device resolution can cross-resolve endpoints.** `resolve` accepts a candidate when the
   first 24 characters match in either direction (`audio_devices.py:415-416`); two real endpoints
   whose names share a 24-char prefix (e.g. truncated MME vs full DirectSound names of similar
   devices) can resolve to a different endpoint than the one listed. `_candidates` also skips the
   `_is_pseudo` filter that `_collect` applies (`:383-391` vs `:288`), so a saved non-empty name
   could match a pseudo-device row by exact name (`:411`).
10. **`EchoGuard`'s learned gain is dead state.** `_gain` is updated at `echo.py:284-287` and exposed
    through the `gain` property (`:139-141`), but `is_user_speech` never reads it — classification
    uses only residuals and their percentiles (`:257-284`). It is diagnostics, not part of the
    decision, despite the header describing a learned echo gain (`:39-43`).
11. **Two VAD instances on the same mic stream.** `main.py` builds an `AudioDucker` with a
    `SpeechDetector` (`main.py:568-574`, fed at `main.py:1672`) and a `VoiceTurns` with its own
    (`main.py:1548-1549`, fed at `main.py:1589`); each `VoiceTurns` constructs a fresh
    `SpeechDetector`/`webrtcvad.Vad(3)` (`voice_turns.py:8`). The webrtc VAD and its ring buffer run
    twice per mic frame.
12. **Wake-word readiness can promise a framework that start() won't use.** `is_ready()` accepts
    `.onnx` *or* `.tflite` files (`wake_word.py:59-64`) while `start()` hardcodes
    `inference_framework="onnx"` (`:139`). A tflite-only model directory would be reported ready by
    the UI (`ui.py:5254`) and then fail to load.
13. **Live one-shot slot accounting on timeout.** `_live_call` releases the 3-slot semaphore in
    `finally` (`gemini.py:454-459`) after `th.join(timeout=…)` (`:457`); on a join timeout the
    runner thread is still inside `_live_turn` (`:447-452`), so the cap can be transiently exceeded,
    and the caller receives `None` (`:462-463`) with no error in the box to explain it.
14. **`gemini.api_key(refresh=False)` ignores its parameter** (`gemini.py:301-307`); no caller in the
    repository passes it, so it is dead API surface that suggests cache-busting that does not exist.
15. **`notification_voice` pins the conversation model.** The announcer hardcodes
    `models/gemini-3.8-live` (`notification_voice.py:32`), duplicating `gemini.LIVE_MODELS[0]`
    (`gemini.py:163`). Upgrading the ladder in `gemini.py` silently leaves the announcer on the old
    model.
16. **`llm_client.call_llm_text` ignores the configured provider.** It always posts to `{url}/api/chat`
    (`llm_client.py:341-350`) while `call_llm` (`:243-280`) and `call_llm_stream` (`:504-506`) branch
    on `get_llm_provider()`. If this module is revived with `llm_provider: "openai"`, this function
    is the one that breaks. Separately, `call_llm`'s timeout branch raises the fixed message
    "Ollama request timed out after 120 s." (`:322`) whatever `timeout` the caller passed.
17. **Upstream persona names survive in comments.** `stt.py:2`, `tts.py:2` and `installer.py:2` say
    "MARK XL"; `avatar.py:17,19,75,210,271`, `audio_devices.py:2,9`, `llm_client.py:137` and
    `wake_word.py:2,16,27,28,149,190,192` say "Zaya". These are upstream-template leftovers that
    conflict with the owner's branding instruction (Zaya is the visible name; upstream license
    attribution must stay, but these strings are not license text). All but one are comments or
    docstrings (`wake_word.py:149` is a log line), and the functional identifiers `hey_jarvis`
    (`wake_word.py:28`) and the `shutdown_zaya` tool (`main.py:423`, `prompt.txt:120`) must stay
    as they are; `session_activity.py:51-53` uses "Sajan" deliberately, narrating the owner's real
    current activity.
18. **Prompt rendering is silently forgiving.** `_render_prompt` is a token replace with no check
    (`main.py:300-310`), and `main.py:1102` passes `assistant_name` although `prompt.txt` no longer
    contains that token. A misspelled token or a removed one produces no warning — the literal text
    just remains in the system instruction.
19. **`hud_state.label` hard-indexes the event name.** `event['event']` (`hud_state.py:11`) would
    raise `KeyError` for any event dict lacking the key; every current publish includes it
    (`event_bus.py:25`), so this is a latent coupling, not an active fault — but the function is
    also the only consumer that treats bus payloads as non-optional.
20. **Confirm-gate expiry is silent to the model by design.** A pending abandoned by the 90 s timer
    (`confirm.py:125-132`) resolves as cancelled and only logs (`:160-164`); the assistant has
    already been told to ask the user to press the button (`:133-137`) and is never told the banner
    disappeared. Also, the timer and a late UI press race benignly — the loser finds `_pending`
    already cleared and no-ops (`:148-158`).
21. **`hotkey.chord_label` and `qt_sequence` are the same implementation** (`hotkey.py:61-68`); the
    second name implies a conversion that does not happen (both return `"Ctrl+Space"`-style text).
22. **Token lower-casing must be remembered when editing the git policy.** `_classify_command`
    lower-cases every token before comparisons (`execution_policy.py:46`), so `'-B'.lower()` in the
    `checkout`/`switch` set (`:66`) and `'-D'.lower()`/`'-M'.lower()` in the branch/remote set
    (`:69`) are redundant-but-correct; a future rule written against original case would silently
    stop matching.
23. **`diagnostics` reports a model source that does not exist.** The providers check hard-codes
    `'model_source': 'core.gemini.live_candidates'` (`diagnostics.py:27`); a repository-wide search
    for `live_candidates` finds nothing, and `diagnostics.py` never imports `core.gemini`. The real
    ladder is `LIVE_MODELS` (`gemini.py:162`, consumed at `:265`, `:269`), so the output points at
    a symbol that is not there.
24. **Unused key-cache state in `gemini.py`.** `_key_lock` and `_cached_key` (`gemini.py:210-211`)
    are defined once and referenced nowhere else in the repository; key selection goes through
    `gemini_keys.pool` (`:495`). Dead remnants of an earlier caching design.
25. **`notification_voice` either re-raises the cooldown or gives a key back.** The retry loop is
    bounded by the number of configured keys (`notification_voice.py:9`) and marks each failing key
    cooling; if all are still cooling, the post-loop `pool.select('notification')` (`:18`) raises
    `KeysCooling` and the `RuntimeError` at `:19` is never reached. `:19` fires only when a key's
    cooldown expired during the loop — at which point the key `:18` just obtained is discarded and
    the announcer fails anyway.
26. **`ShellSessions.sessions` is never pruned.** `cwd()` stores every session id it is asked about
    (`shell_session.py:61`) and the `finally` block removes only the `processes` entry (`:126`);
    nothing else deletes from `sessions`. The id is a free-form tool parameter
    (`actions/terminal_exec.py:12` — `'default'` unless the model passes one), so each distinct id
    leaves one `Path` bound for the life of the process.
27. **`wake_word.stop()` races its inference thread.** `stop()` clears `self._model`
    (`wake_word.py:159`) without joining the worker thread (`:147`); a worker that passed its
    `_running` check (`:185`) and is inside `self._model.predict` (`:187`) turns that clear into an
    `AttributeError`, swallowed and logged as a generic "inference error" (`:203-204`). The loop
    also does not re-check `_running` before `_on_detect` (`:196-200`), so one detection can still
    be delivered after `stop()` returns. Latent today — nothing in the app calls
    `WakeWordDetector.stop()` (`main.py` only starts, feeds and queries it: `main.py:733-739`,
    `1617-1618`).
