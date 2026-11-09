# `actions/` — built-in tool reference

`actions/` is the built-in, file-backed tool layer of Zaya. Every `actions/*.py`
file that exposes a module-level `TOOL` dict is auto-discovered at startup by
`core/action_loader.discover_actions()` (`core/action_loader.py:159-223`) and
plugged into the Gemini Live session exactly like a drop-in plugin. `main.py`
never hardcodes per-action declarations or dispatch branches; it only wires the
registry (`main.py:668-692`).

Two properties shape everything below:

- **Discovery is non-fatal.** Import errors, invalid `TOOL` dicts and name
  collisions are logged and the file is skipped; they never raise out of the
  scan (`core/action_loader.py:22-24, 126-223`).
- **The registry is the only entry point the model sees.** `ActionRegistry.run`
  calls `require_owner()` before dispatch (`core/action_loader.py:99-110`), and
  handlers receive `parameters` plus only the context kwargs they declare
  (`core/action_loader.py:113-123`).

Unless stated otherwise, every `path:line` reference in this document is the
current source of truth; tool rows cite the `TOOL` dict that declares them.

---

## 1. Tool inventory

### 1.1 Actions with a `TOOL` dict

| Tool | Declared at | Category | What it does | Key parameters | Safety / confirmation | Return |
|---|---|---|---|---|---|---|
| `avatar_expression` | `actions/avatar_expression.py:19` | Assistant | Picks one emotion for the taskbar face **and** the spoken voice; publishes `avatar.emotion` on the event bus | `emotion` (enum `EMOTIONS`) | None; marks `side_effect=True` | `ToolResult` |
| `browser_control` | `actions/browser_control.py:1160` | Browser | Opens sites natively (default) or drives a Playwright automation session for interactive work | `action` (21 names), `mode` (`native`/`automation`), `browser`, `url`, `query`, `selector`, `text`, `description`, `key`, `incognito`, … | No prompt/undo. Native results are explicitly `verified=False`; automation may use a separate signed-out profile | Mixed: `ToolResult` for native open / navigation / failures, plain strings for most interactive steps |
| `call_owner` | `actions/mobile_call.py:18` | Phone | Initiates a direct audio call or push alert to the owner's paired companion phone | `reason`, `message`, `urgent` | Owner-presence checked; obeys quiet hours and call throttling | `ToolResult` |
| `code_helper` | `actions/code_helper.py:589` | Code | Writes, edits, explains, runs or builds a single code file | `action` (`write`/`edit`/`explain`/`run`/`build`/`auto`), `description`, `language`, `output_path`, `file_path`, `code`, `args`, `timeout` | No confirmation; `run` executes code locally with owner privileges | `str` |
| `coding_job` | `actions/coding_job.py:20` | Code | Coordinates OpenCode CLI supervised coding tasks with briefs and reviews | `action` (`start`/`status`/`continue`/`stop`), `task`, `project`, `create_project` | Tool-free brief and review; runs local OpenCode CLI process tree | `ToolResult` |
| `computer_control` | `actions/computer_control.py:517` | Desktop UI | Raw pyautogui input: type, click, hotkeys, scroll, screenshot, screen text search | `action` (19 declared names), `text`, `x`, `y`, `keys`, `key`, `description`, `path`, … | None. `pyautogui.FAILSAFE = True` (`actions/computer_control.py:20`) so slamming the mouse into a corner aborts | `str` |
| `computer_settings` | `actions/computer_settings.py:912` | System | Volume, brightness, window management, browser hotkeys, typing, lock, dark mode, WiFi, restart/shutdown | `action` (vocabulary spelled in the declaration), `description` fallback, `value` | `restart`/`shutdown`/`toggle_wifi` go through the on-screen confirmation gate (`_IRREVERSIBLE`, `actions/computer_settings.py:672-683`, `818-829`); volume/brightness/dark mode push undo entries (`877-906`) | `str` (may be a `[CONFIRMATION_PENDING]` sentence) |
| `conversation_history` | `actions/conversation_history.py:26` | Memory | Returns up to the last five archived messages, or a five-result search | `query` (optional) | Owner-only; history is context, never replayed | `ToolResult` |
| `desktop_control` | `actions/desktop.py:486` | Desktop UI | Wallpaper (path/URL), organize, clean, list, stats, plus an AI `task` escape hatch | `action`, `path`, `url`, `mode`, `task` | No confirmation and **no undo** for `organize`/`clean`; `task` runs Gemini-generated code in a soft sandbox (`actions/desktop.py:38-102`) | `str` |
| `dev_agent` | `actions/dev_agent.py:611` | Code | Plans and writes multi-file projects, installs deps, opens VSCode, runs and fixes errors | `description`, `language`, `project_name`, `timeout` | No confirmation; runs the project and auto-installs missing PyPI packages (`actions/dev_agent.py:331-351`) | `str` |
| `file_controller` | `actions/file_controller.py:725` | Files | File/folder management with shortcut paths and disk info | `action` (14 names), `path`, `destination`, `new_name`, `content`, `name`, `extension`, `count` | Home-directory-only path guard (`_is_safe_path`, `actions/file_controller.py:93-106`); delete uses send2trash (`186-195`) and protected folders are refused (`279-284`); undo pushed for create/write/move/copy/rename/delete/organize | `str` |
| `file_processor` | `actions/file_processor.py:845` | Files | Processes an uploaded file by detected type (image, PDF, docx, CSV, code, audio, video, archive, pptx, JSON) | `file_path`, `action`, `instruction`, `format`, `width`/`height`/`scale`/`quality`, `start`/`end`, `timestamp`, CSV filters, `save`, `destination` | **No path restriction.** `code … run` executes the file (`actions/file_processor.py:465-477`); `ffmpeg` is invoked for media (`589-716`) | `str` |
| `flight_finder` | `actions/flight_finder.py:363` | Web | Builds a Google Flights URL, reads the page, asks Gemini to extract options, optionally saves a report | `origin`, `destination`, `date`, `return_date`, `passengers`, `cabin`, `save` | No confirmation; opens a browser window and can write a report to Desktop | `str` |
| `game_updater` | `actions/game_updater.py` | Games | Canonical Steam & Epic updater: accessibility tree inspection, library verification, background download status, scheduling | `action`, `platform`, `game_name`, `app_id`, `hour`, `minute`, `shutdown_when_done` | Deterministic UIA automation; drive space validation; CLI `--scheduled` support | `str` |
| `git_control` | `actions/git_control.py:14` | Shell/Git | Structured Git: status, diff, branches, stage, commit, push, verify remote SHA | `action` (17 names), `path`, `branch`, `remote`, `paths`, `message` | Refuses globs, symlinks and secret-looking files (`core/git_utils.py:42-61, 120-139`); push is followed by remote verification (`102-108`); policy also blocks force pushes (`core/execution_policy.py:64-65`) | `ToolResult` |
| `open_app` | `actions/open_app.py:277` | System | Launches an app by executable lookup, or URL-style `start` command, or Start-Menu typing | `app_name` | No confirmation. Windows paths use `shell=True` (`actions/open_app.py:84-89, 95-99`) and a pyautogui Start-Menu fallback (`103-116`) | `str` |
| `owner_presence` | `actions/owner_presence.py:15` | Context | Checks or explicitly sets owner presence state (away, present, auto) | `action` (`status`/`set`), `mode`, `hours` | Owner-only; updates local presence state | `ToolResult` |
| `personal_profile` | `actions/personal_profile.py:24` | Memory | Explicitly imports a local profile JSON or registers project path aliases | `action` (`status`/`import`/`register_project`), `path`, `name`, `aliases` | Import is explicit only; profile data stays local and git-ignored | `ToolResult` |
| `reminder` | `actions/reminder.py:341` | System | Sets a timed reminder through the OS scheduler (Task Scheduler / launchd / cron) | `date` (`YYYY-MM-DD`), `time` (`HH:MM`), `message` | No confirmation or undo; writes a helper script and a persistent scheduled entry | `str` |
| `runtime_logs` | `actions/runtime_logs.py:16` | Diagnostics | Returns recent in-memory log entries with severity filtering | `limit`, `level`, `component` | Read-only access to runtime logging ring buffer | `ToolResult` |
| `runtime_status` | `actions/runtime_status.py:22` | Diagnostics | Reads authoritative task-runtime state, or proxies WhatsApp status | `action` (`summary`/`active_tasks`/`recent_tasks`/`failures`/`waiting`/`whatsapp`) | Read-only | `ToolResult` |
| `send_message` | `actions/send_message.py:280` | Communications | Sends messages via non-WhatsApp desktop apps (Telegram, Signal, Discord, Instagram, Messenger) by GUI automation | `receiver`, `message_text`, `platform` | WhatsApp is refused and redirected to the `whatsapp` tool (`actions/send_message.py:251-253`). Blind keypress sequences; success is a text heuristic (`268-276`) | `str` |
| `session_activity` | `actions/session_activity.py:24` | Context | Maintains a short, owner-authorized activity summary for WhatsApp auto replies | `action` (`set`/`clear`/`status`), `kind`, `summary`, `minutes` (clamped 1–60) | Owner-only; activity is deliberately narrow, no secrets/history | `ToolResult` |
| `system_diagnostics` | `actions/system_diagnostics.py:10` | Diagnostics | Non-destructive capability checks for plugins/actions/audio/providers/runtime/browser/WhatsApp | `action` (`full` default) | Read-only | `ToolResult` (from `core/diagnostics.inspect`) |
| `terminal_exec` | `actions/terminal_exec.py:59` | Shell/Git | Real shell commands with cwd sessions, timeouts, output and exit evidence | `action` (`run`/`which`/`pwd`/`cd`/`session_status`/`cancel`), `command`, `cwd`, `session_id`, `shell`, `timeout` | `core.execution_policy.classify` gates every command; `confirm` shows the HUD banner (`actions/terminal_exec.py:30-53`). Owner "Full Access" can auto-execute (`core/confirm.py:96-101`) | `ToolResult` |
| `terminate_app` | `actions/process_terminate.py:18` | System | Closes or force-terminates running applications/processes safely | `target`, `force`, `kill_tree` | Require owner; protected processes refusal | `ToolResult` |
| `video_player` | `actions/video_player.py:327` | Media | Plays video on the assistant display window, or hands playback to a browser (`move_to_browser` reuses the last song) | `action` (`play`/`stop`/`mute`/`unmute`/`move_to_browser`), `target`, `browser`, `source` | No confirmation. Returns immediately with `status=opening` before the picture appears | `str` |
| `weather_report` | `actions/weather_report.py:55` | Web | Opens a Google search for the weather in the browser | `city` | No confirmation; browser open is unverified | `str` |
| `web_search` | `actions/web_search.py:385` | Web | Web search with modes: search, news, research, price, compare | `query`, `mode`, `items`, `aspect` | Read-only network; backends may fail and return a single error string (`actions/web_search.py:379-381`) | `str` |
| `whatsapp` | `actions/whatsapp.py:78` | Communications | WhatsApp monitoring, explicit sends, per-chat and global auto-reply modes, local read state | `action` (19 names), `name`, `chat`, `query`, `message`, `mode`, `request_id`, `seconds`, `alert_id`, `limit` | Owner-only. External messages are untrusted; auto replies use only shared session activity; `mark_read` changes local state only (`actions/whatsapp.py:69-72`) | `ToolResult` |
| `youtube_video` | `actions/youtube_video.py:445` | Media | Opens YouTube videos in the browser, summarizes transcripts, fetches info, lists trending | `action` (`play`/`summarize`/`get_info`/`trending`), `query`, `save`, `region`, `url` | No confirmation; browser open plus screen scraping (`actions/youtube_video.py:65-72, 225-283`) | `str` |

### 1.2 Modules without a `TOOL` dict

These files are imported by the app directly, not through discovery; `discover_actions` silently skips them (`core/action_loader.py:194-195`).

| Module | Role |
|---|---|
| `actions/screen_processor.py` | Screen/webcam capture for the Live session (`_capture_screen` / `_capture_camera`); no separate vision session (`actions/screen_processor.py:1-8`) |
| `actions/system_monitor.py` | Background metric checks (CPU/RAM/temp/GPU thresholds with cooldowns); no subprocess calls (`actions/system_monitor.py:1-21`) |
| `actions/background_monitor.py` | User-configured topic watching via daily DuckDuckGo news checks; blocked categories for crypto/finance (`actions/background_monitor.py:1-22`) |
| `actions/proactive.py` | `ProactiveEngine`: decides *when* unprompted speech is allowed and builds context (`actions/proactive.py:1-23`) |
| `actions/ui_runtime_guard.py` | Late-bound UI safety shims for MainWindow logging (`actions/ui_runtime_guard.py:1-42`) |

---

## 2. Conventions every action follows

**Declaration contract.** `TOOL` must be a module-level `dict` with:

- `name` — string matching `^[a-zA-Z_][a-zA-Z0-9_]{0,63}$` (`core/action_loader.py:37, 133-136`).
- `description` — non-empty string the Live model reads for routing (`138-141`).
- `parameters` — a dict with `"type": "OBJECT"` following the Gemini function-declaration schema (`143-146`).
- `handler` — a callable (`148-151`).

Optional keys: `behavior` (`BLOCKING`/`NON_BLOCKING`) is forwarded to the API,
and `scheduling` (`WHEN_IDLE`/`SILENT`/`INTERRUPT`) decides when a result may
re-enter the conversation (`core/action_loader.py:42-49, 155-156`). No action in
this directory currently declares either; the values and defaults are the
loader's (`42-49`). `behavior` is copied into the tool declaration
(`77-85`); `scheduling` is exposed via `ActionRegistry.scheduling()` (`90-93`).

**Handler invocation.** Handlers may declare any signature. The loader passes
`parameters=` plus only the context kwargs the function declares, or all of
them when it declares `**kwargs` (`core/action_loader.py:113-123`). The context
keys are `player`, `speak`, `response`, `session_memory` (`:39`).

**Return values.** Handlers may return:

- a plain `str` (legacy style — most actions do this), or
- a `core.tool_result.ToolResult` with `status` in
  `success`/`failed`/`partial`/`waiting_confirmation` (`core/tool_result.py:8-38`).

Anything else is normalized: `normalize()` maps dicts with a valid status to
`ToolResult`, treats `[CONFIRMATION_PENDING]` text as `waiting_confirmation`,
error-prefixed strings as `failed`, and everything else as `partial` with
`{"legacy": True, "verified": False}` metadata (`core/tool_result.py:41-53`).
Outputs are truncated head+tail at 16384 bytes with an explicit marker
(`core/tool_result.py:11-17`).

**Permission and trust.** `ActionRegistry.run` calls `require_owner()` first,
so external contexts (WhatsApp/web content) can never reach a file-backed tool
through the registry (`core/action_loader.py:99-104`,
`core/execution_policy.py:16-18`). Actions that are also callable directly
(e.g. `browser_control` used by `flight_finder` and `git_control`) repeat the
check inside their own handler (`actions/browser_control.py:1017-1018`,
`actions/git_control.py:7`).

**Safety model — confirm vs undo.** The codebase splits by reversibility: undo
entries for anything reversible (`core/undo.py:1-34`, max depth 10, `:46`), and
the HUD confirmation gate only for genuinely irreversible actions
(`core/confirm.py:30-36`, 90-second expiry `:49`). Confirmation is issued by
the interface, never by a model parameter (`core/confirm.py:17-28`).

**Discovery and collisions.** Files are scanned in sorted order
(`core/action_loader.py:173`). A name reserved by an inline core tool is
rejected, and a duplicate of an earlier-sorted action is rejected
(`199-205`). Plugins are loaded afterwards with action names in
`core_tool_names`, so a plugin can never shadow an action
(`main.py:680-684`, `core/plugin_loader.py:256-258`).

**Errors.** A handler exception is caught by the registry, logged with a
traceback and returned to the model as `Tool '<name>' failed: <e>`
(`core/action_loader.py:105-110`). Actions that want friendlier errors catch
their own exceptions and return a human sentence.

**Auditing.** Long outputs and evidence strings are passed through
`core.audit.redact`, which masks secret-shaped keys, token patterns and
environment secret values (`core/audit.py:11-25`); the shell session does this
for commands and output (`core/shell_session.py:29-30, 129`).

---

## 3. Deep dives

### 3.1 `browser_control` — native vs automation

The tool has two modes and they are deliberately different products
(`actions/browser_control.py:1160-1230`):

- **`mode=native` (default)** is used for ordinary open/search/new-tab. It
  launches the installed browser with its regular signed-in profile
  (`actions/browser_control.py:1050-1090`): named Windows browsers via their
  executable (`406-419`), the default browser via `os.startfile` on Windows /
  `open` on macOS / `xdg-open` elsewhere (`427-438`). The result is a
  `ToolResult` marked `partial` with `verified: False` and
  `profile: regular browser profile` (`1085-1090`), because the native launch
  cannot be inspected. The declaration instructs the model not to open an
  automation session merely to verify an ordinary open (`1162`).
- **`mode=automation`** selects the Playwright session for interactive work:
  click, type, scroll, fill_form, smart_click, smart_type, get_text/press,
  screenshot, tab and history actions (`1092-1149`).

Automation internals:

- `_BrowserSession` (`448-925`) launches a persistent context against the
  browser's **real** profile when possible; if that fails (browser already
  open, profile locked, newer Chrome blocks automation profiles) it falls back
  to direct computer_control without a separate sandbox profile, where
  sign-ins persist across sessions but are *not* the owner's regular ones.
- `_get_page` recovers from closed-page errors twice before any click/type can
  fire (`671-687`).
- `go_to` retries only explicit navigation, never a click or form; it then
  verifies the destination with `core.site_registry.matches` and records
  `browser_state` (`689-724`).
- `_browser_failure` redacts the error and marks mutating actions as
  `side_effect` (`31-38`).
- Interactive actions resume the last natively-opened URL first
  (`1103-1109`), and automation calls that exceed the 60-second future become
  `"Timed out after 60s."` failures (`1064-1065`, `1143-1144`).
- `_SessionRegistry` (`927-1009`) owns sessions, the active browser and the
  one-shot `pop_native_url` handoff (`944-950`).

### 3.2 `terminal_exec` / `git_control` / `shell_session`

`terminal_exec` is the only action that feeds arbitrary command text from the
model into a real shell (`actions/terminal_exec.py:59-64`). Non-`run` operations
are cheap:
`cancel` and `which` and the `pwd`/`cd`/`session_status` family read or mutate
session state (`13-21`). For `run`:

1. `core.execution_policy.classify` returns `deny`/`confirm`/`read`/`normal`
   (`execution_policy.py:27-33, 36-80`).
2. `deny` → failed result; `confirm` → the action parks the command behind
   `core.confirm.request` and returns a `[CONFIRMATION_PENDING]` sentence
   (`actions/terminal_exec.py:30-53`); confirmation has 90 s to be pressed
   (`core/confirm.py:49, 125-137`).
3. Otherwise the command runs immediately; `side_effect` is false only for
   `read` (`actions/terminal_exec.py:54-56`).

The classifier is conservative, not a sandbox: compound/interpreted commands
(`;`, `|`, `<`, `>`, backticks, `$`, `-c`, `-Command`, …) and protected system
locations always require the human gate; unknown programs fall through to
`confirm` (`core/execution_policy.py:50-80`). The owner's saved Full Access
setting downgrades `confirm` to normal (`execution_policy.py:30-33`), and the
same setting bypasses `confirm.request` (`core/confirm.py:96-101`).

`core/shell_session.py` is the execution engine shared by
`terminal_exec` and `git_control`:

- Named cwd sessions resolved against the previous cwd, rejecting missing
  directories (`shell_session.py:55-62`).
- Timeout clamped to `max(0.1, min(timeout, 600))` seconds (`:77`).
- Windows runs `powershell -NoProfile -NonInteractive -Command` or `cmd /c`;
  POSIX runs `bash -c`/`sh -c` (`78-88`).
- Output is captured head+tail into two 16 KiB buffers with redaction
  (`15-30`).
- `terminate_tree` kills the whole process tree (`taskkill /T /F` on Windows,
  process group otherwise) on timeout or explicit cancel (`33-45, 64-71`).
- Results carry pid, exit code, stdout/stderr, duration, `timed_out`,
  `cancelled`, truncation flags and `side_effect=True` (`90-138`).

`git_control` wraps `core.git_utils.GitRepo.operate` (`actions/git_control.py:6-11`,
`core/git_utils.py:78-145`). Notable behaviour:

- Read-only operations never mark side effects (`git_utils.py:81-87`).
- `stage`/`unstage` require explicit paths; globs, paths outside the repo and
  `-`-prefixed values are rejected; symlinks are refused and files matching
  `SECRET_PATH` or containing `SECRET_CONTENT` are refused unread
  (`git_utils.py:9-10, 42-61`).
- `push` verifies the checked-out branch, runs `push -u`, then calls
  `verify_push`, which compares local HEAD to `git ls-remote` and returns
  `partial` when verification is impossible (`git_utils.py:63-76, 99-108`).
- `commit` re-checks the staged index for secrets and whitespace errors before
  committing, and appends the commit SHA to evidence (`120-139`).
- `open_remote` calls `browser_control` in native mode directly
  (`git_utils.py:140-144`), bypassing the registry — which is why the handler
  keeps its own `require_owner`.

### 3.3 `file_controller` / `file_processor`

`file_controller` is the guarded file API. Every operation resolves shortcut
paths (`desktop`, `downloads`, … and `desktop/sub/path` forms) and then checks
`_is_safe_path`, which only allows the user's home directory
(`actions/file_controller.py:93-106, 151-177`). Deletion never unlinks:
it requires `send2trash`, returns a failure explaining permanent deletion is
disabled when the library is missing, and pushes a restore undo
(`186-195, 286-291`). Deleting a protected directory itself is refused
(`279-284`). Undo coverage: create file/folder (`244, 263`), write (`444`),
move (`320`), copy (`363`), rename (`388`), delete (`289`) and desktop
organize (`608`). `organize_desktop` journals every move and registers a single
undo that puts files back and removes only the folders it created while they
are empty (`541-621`).

`file_processor` is the opposite: the handler trusts `file_path` from the model
and only checks existence (`actions/file_processor.py:784-793`). It detects the
type by extension probing (`50-73`) and dispatches to per-type handlers
(`815-829`). Notably:

- `code … run` executes the file with `subprocess.run(["python", str(path)])`
  for `.py` only, 30 s timeout (`465-477`).
- Media actions shell out to `ffmpeg` after a version probe (`589-716`).
- AI-backed actions use a Gemini wrapper sharing key lookup (`37-47`).
- `save` defaults to true and results are written next to the source via
  `_output_path`.

So the same machine has a home-only, undo-covered file manager and an
unrestricted, execution-capable file processor; the difference is deliberate
tool intent, not enforced architecture.

### 3.4 `computer_control` / `computer_settings`

`computer_control` is the low-level pyautogui action set
(`actions/computer_control.py:517-588`): typing, mouse, hotkeys, scroll,
screenshots and OCR-free screen text search via `screen_find`/`screen_click`.
Failsafe is enabled, so a corner slam aborts the move (`:20`).

`computer_settings` is the higher-level, intent-aware facade
(`actions/computer_settings.py:912-961`). Its structure:

- `ACTION_MAP` maps ~60 action names to functions (`595-655`), including an
  alias superset (`play_pause`, `reload`, `fullscreen`, …).
- The tool declaration now spells out the entire vocabulary explicitly so the
  model does not need a second translation call; the in-file comments record
  that this replaced an inner Gemini round trip (`918-945`).
- A local resolver handles fallback `description` text: aliases, numeric volume
  phrases, `difflib` fuzzy matches and substring matching (`689-782`).
- `_IRREVERSIBLE` is exactly `{restart, shutdown, toggle_wifi}`
  (`672-683`); those actions park behind `confirm.request` and the handler
  returns early — it does not perform them (`818-829`). `_DANGEROUS_ACTIONS`
  remains as an alias for the old set (`685-686`).
- Reversible settings capture the previous value and push undo: `volume_set`
  (`831-839`), volume up/down/mute (`883-899`), brightness up/down (`885-902`),
  dark mode toggle (`903-906`). Platform functions themselves use
  `osascript`/WMI/PowerShell (`546-593` for WiFi/restart/shutdown, `189-242`
  for brightness).

### 3.5 `desktop_control` / `open_app` / `send_message` / `youtube_video` / `video_player`

**`desktop_control`** manages the Desktop folder: wallpaper (path and
downloaded URL), `organize` (by_type/by_date), `clean` (archive all loose
files into `Desktop Archive <date>`), `list`, `stats`, and a free-form `task`
(`actions/desktop.py:415-482`). `organize`/`clean` move files with no undo
registry (`309-349, 377-395`). `task` generates Python through Gemini under a
strict prompt (allowed modules only, no deletion, no subprocess, `104-154`)
and executes it with `exec` inside an injected-module sandbox
(`38-102, 462-477`).

**`open_app`** tries, in order: `shutil.which` on the given name then
`subprocess.Popen(app_name, shell=True)` (`actions/open_app.py:80-93`); a
`start <app_name>` shell command when the name contains `:` (URL/shell target,
`95-99`); a pyautogui Start-Menu search that types the name and presses Enter
(`103-116`). It returns success text without independent verification.

**`send_message`** resolves the target platform from a keyword list
(`actions/send_message.py:218-233`) and drives desktop apps: Telegram and
Signal/Discord via `_desktop_send` (open app, Ctrl+F search contact, paste
message, Enter — `127-150, 158-166`), Instagram and Messenger via fixed
tab/arrow keypress sequences in the browser (`169-216`). WhatsApp is refused
with a pointer to the `whatsapp` tool (`251-253`), although the old
`_send_whatsapp` helper still exists and delegates to Hermes
(`152-155`). Success reporting is a string heuristic that now excludes
`"not sent"` (`268-276`).

**`youtube_video`** is browser-side playback plus transcript/info/trending
(`actions/youtube_video.py:445-475`). `_open_url` uses platform launchers with
`cmd /c start` on Windows (`65-72`); `play` resolves or scrapes a video URL and
opens the browser (`284-309`); `summarize` uses `youtube-transcript-api` and
optionally saves to a file opened in Notepad (`136-223`); trending is scraped
from YouTube pages (`258-283`).

**`video_player`** is the display-window player and is explicitly *not*
`youtube_video` — its declaration says the latter "opens videos in the web
browser and summarises transcripts, it never plays anything on the assistant's
display" (`actions/video_player.py:327-350`). `move_to_browser` reuses the last
source and closes the display (`330-333, 351-372`). It returns as soon as
playback is requested (`status=opening`), so the model is instructed not to
wait or re-call (`344-349`).

---

## 4. Duplication and legacy map

**Two desktop organizers.** `desktop.py:309-349` (`organize`) and
`desktop.py:377-395` (`clean`) move files with no undo. `file_controller.py`
implements `organize_desktop` again (`541-621`) with a journal and a single
undo entry. Both are reachable from the model (`desktop_control` action
`organize`, `file_controller` action `organize_desktop`), with different safety
guarantees.

**Plugin/action collision — `game_updater`.** `plugins/game_updater.py:2462`
declares `"name": "game_updater"`, which collides with the action at
`actions/game_updater.py:1063`. Because `main.py` passes action names into the
plugin loader (`main.py:681-684`), the plugin is rejected at load time
(`core/plugin_loader.py:256-258`) and the bundled action shadows it. The plugin
file remains in the tree.

**`code_helper` vs `dev_agent`.** `code_helper` is single-file
write/edit/explain/run/build (`actions/code_helper.py:589-632`); `dev_agent`
builds multi-file projects, installs dependencies and runs them
(`actions/dev_agent.py:611-638`). The overlapping surface is
"write code" requests whose scale decides the tool.

**WhatsApp send path.** `send_message` no longer sends WhatsApp
(`actions/send_message.py:251-253`); the `whatsapp` tool owns that
(`actions/whatsapp.py:38-39`). The dead helper `_send_whatsapp` remains
(`send_message.py:152-155`).

**Browser hotkeys duplicated.** `computer_settings` implements browser tab /
zoom / find / history actions with pyautogui keyboard shortcuts
(`computer_settings.py:595-646`), which overlaps `computer_control`'s
`hotkey`/`press` and `browser_control`'s native tab actions.

**Two playback paths.** `youtube_video` (browser) and `video_player` (display
window) can both satisfy "play this video". The declarations actively steer:
`video_player` forbids `youtube_video` for display playback
(`video_player.py:347-349`), and `youtube_video` describes itself as the
browser/transcript tool.

**Weather via browser.** `weather_report` opens a Google search rather than
using a weather API (`weather_report.py:21-31`); `web_search` could retrieve
the same data without a browser window. Both remain available.

**`flight_finder` mixes browser modes.** It calls `browser_control` twice
directly: a native `go_to`, then `get_text`, which forces an *automation*
session for the same site (`flight_finder.py:139-143`). The two calls can end
up in different browser profiles/instances.

**Legacy identifiers.** Ghosts of the pre-Zaya name survive: the sandbox code
is compiled as `"<zaya_desktop>"` (`desktop.py:97`), automation profiles live
in the user's real browser window directly, and
`computer_settings` keeps `_DANGEROUS_ACTIONS` as a compatibility alias
(`computer_settings.py:685-686`).

---

## 5. Observations and risks

1. **`desktop_control.task` is a soft sandbox, not a security boundary.**
   Generated code runs via `exec` in a namespace with curated builtins
   (`actions/desktop.py:38-102`), but `ctypes` (full module) and a read-only
   `winreg` shim are injected on Windows (`66-78`). `ctypes` can load arbitrary
   DLLs, and `pyautogui` is also injected whenever installed (`63-64`), so the
   "allowed modules only" prompt is advisory. The engine that produces the code
   is the same live model; a task error returns generated code in logs
   (`99-101`).

2. **`open_app` executes model-supplied strings through the shell.**
   `subprocess.Popen(app_name, shell=True)` (`actions/open_app.py:84-89`) and
   `subprocess.Popen(f"start {app_name}", shell=True)` when the name contains
   `:` (`95-99`). The parameter is free-form text; there is no quoting or
   validation. This runs with owner privileges.

3. **`file_processor` has no path restriction and one action executes code.**
   The handler checks only existence/isfile (`actions/file_processor.py:784-793`)
   and `code … run` shells out to `python` on the given path
   (`465-477`). Any file the process can read is in scope, and `.py` uploads
   can execute. This contrasts with `file_controller`'s home-only guard
   (`file_controller.py:93-106`).

4. **`dev_agent` executes a model-chosen command and installs packages.**
   `_run_project` does `run_command.split()` and executes the argv
   (`actions/dev_agent.py:298-311`) after swapping `python` for `sys.executable`;
   `_try_auto_install` runs `pip install <name>` derived from stderr
   (`331-351`). No confirmation gate covers either.

5. **`send_message` is blind keyboard automation with string-based success.**
   Instagram and Messenger paths press fixed keys regardless of actual UI state
   (`send_message.py:169-216`); `_desktop_send` types and presses Enter without
   verification (`137-150`). Success is inferred from the returned sentence
   (`268-276`), so a misfired sequence can still read as success unless the
   text says "not sent".

6. **`game_updater` disables the pyautogui failsafe and guesses coordinates.**
   `pyautogui.FAILSAFE = False` (`game_updater.py:353`), avatar detection falls
   back to a hard-coded relative click (`224`), and the install dialog clicks
   fixed fractions of the window (`378-382`). It can also shut the machine
   down: `_system_shutdown` runs `shutdown /s /t 10` (`633-639`) from a watcher
   loop (`642-665`).

7. **`game_updater` scheduling writes privileged, persistent entries.**
   Windows scheduling first attempts `schtasks /RL HIGHEST /RU SYSTEM`
   (`game_updater.py:816-819`); macOS writes a LaunchAgent plist (`826-858`);
   Linux rewrites the user's crontab (`861-877`). None of these are undoable
   from the assistant.

8. **Linux brightness fallbacks build `shell=True` command strings.**
   `computer_settings.py:199-204` and `228-233` interpolate a Python one-liner
   into an `xrandr` command under `shell=True`. The embedded values are
   computed locally, but this bypasses the argv-style execution used
   everywhere else in the module.

9. **Native browser opens are unverifiable by design, and automation may use a
   different profile.** Native results are `partial` with `verified: False`
   (`browser_control.py:1085-1090`); automation falls back to
   an error directing to computer_control when the real profile is locked
   (`654-668`). The declaration warns the model not to claim shared sign-ins
   (`1162`), but a user asking "did it open?" cannot be answered from evidence.

10. **`flight_finder` switches browser modes mid-flow.** `go_to` runs natively,
    then `get_text` opens an automation session for the same URL
    (`flight_finder.py:139-143`). The text read may come from the separate
    automation window/profile, not the window the user sees.

11. **The Full Access setting bypasses both gates.** `classify` downgrades
    `confirm` to normal (`core/execution_policy.py:30-33`) and
    `confirm.request` executes immediately (`core/confirm.py:96-101`). With it
    enabled, `terminal_exec`, `computer_settings`'s shutdown/restart/WiFi and
    every other confirm-gated action run without a human press. This is a
    documented owner choice, not a bug, but it is the single switch that
    matters most for these risks.

12. **Category-level false positives in the command policy.** Any command
    containing `-c`/`/c`/`-command` tokens or shell composition goes to
    `confirm` (`core/execution_policy.py:52-53`), including benign things like
    `python -c "print(1)"` or `pytest -c`. Conversely, unknown binaries fall to
    `confirm` (`80`), so the policy is conservative in the safe direction — but
    it is not a sandbox, as its own docstring says (`39-41`).

13. **Duplicate organize semantics.** `desktop_control`'s `organize` has no
    undo (`desktop.py:309-349`) while `file_controller`'s has one
    (`file_controller.py:541-621`). Two tools for one user intent with
    different reversibility invites accidental data movement the user cannot
    take back.

14. **`tool_result` legacy detection is heuristic.** A plain-string return that
    happens to start with `failed`/`error:` is `failed`; everything else is
    `partial` and explicitly marked unverified (`tool_result.py:41-53`). Most
    actions still return strings, so most results reach the model through this
    heuristic rather than structured statuses.

15. **`weather_report` declares less than it reads.** The handler reads
    `parameters.get("time")` (`weather_report.py:11`) but the `TOOL` dict only
    exposes `city` (`58-68`), so the parameter is unreachable by declaration
    and effectively dead. The same file returns a browser-open message without
    independent verification (`21-34`).

16. **Startup ordering decides name collisions.** Actions are scanned in sorted
    filename order and the first valid declaration wins; later duplicates are
    rejected (`core/action_loader.py:173, 202-205`). A future rename or
    file-added collision will be resolved alphabetically rather than
    intentionally.

17. **`send_message` description contains a duplicated sentence fragment.**
    `"platform. Write 'message_text' ..."` repeats after the WhatsApp sentence
    (`send_message.py:282-289`); cosmetic, but it is the text the model routes
    on.

18. **Interview the capture-only modules as trusted code.** `screen_processor`,
    `system_monitor`, `background_monitor` and `proactive` run outside the
    action registry and therefore outside `require_owner()` dispatch
    (`core/action_loader.py:194-195`); their safety relies on the app calling
    them in owner context (e.g. `screen_processor.py:1-8`).

## Coding requests through OpenCode

`coding_job` is Zaya's owner-only entry point for new coding requests. Zaya
expands the owner's request into a concrete brief, sends it with
`opencode run --format json` in a hidden process, reads the response stream,
and reviews the result. Missing original requirements trigger focused follow-up
prompts in the same session, with at most three passes per owner request.
It stores bounded local job state. `status` reads the actual
response; `continue` sends a new owner prompt to the saved session; `stop` pauses
work and keeps the files. A fresh app startup never replays a saved coding task.
The live dispatcher redirects legacy `dev_agent` / `code_helper` calls through
this entry point; their existing implementations remain available to direct
integrations. Existing projects need an explicit directory; new projects use
`create_project=true` to prepare their folder without placeholder files.

Progress notices use short first-person templates and the existing isolated
voice channel. OpenCode's responses never enter the voice session as commands.
The runner uses installed OpenCode settings, with no injected permission config
and no auto-approval flag. A refusal is reported as a response; a coding request
does not bypass the existing confirmation behavior of Zaya's other tools.
