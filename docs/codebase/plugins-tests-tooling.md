# Plugins, tests and tooling

**Created and developed by Sajan Rai.** See [creator credits](../../CREDITS.md).

Developer reference for the plugin system, the regression suite, and the build/tooling
surface of Zaya. Snapshot: branch `main`, HEAD `d62f5ad` (2026-10-16). Every
reference below points at that revision; this survey was read-only.

Companion notes live in this directory alongside this file.

---

## 1. Plugin API contract

The contract is defined entirely by `core/plugin_loader.py`; `plugins/_template.py`
is the author-facing copy of it.

### 1.1 Discovery and validation

- `discover_plugins(plugins_dir, core_tool_names, logger, notify)` scans
  `plugins/*.py` in sorted filename order for deterministic boot output
  (`core/plugin_loader.py:223`, `:237`).
- Files whose name starts with `_` are skipped by design (`:239`): the package
  marker `plugins/__init__.py` (empty), the template `plugins/_template.py`, and
  shared helpers such as `plugins/_telegram_ops.py`.
- Each candidate is imported as `plugins.<stem>`, registered in `sys.modules`,
  and popped again if import fails so a later retry is not poisoned (`:242-252`).
- Import errors never abort the scan. `_load_error` (`:197-220`) turns them into
  actionable text:
  - a missing `plugins._x` helper is named explicitly ("download '_telegram_ops.py'
    into the same folder as telegram_remote.py and restart");
  - a missing third-party package becomes `pip install <name>`;
  - anything else becomes `Failed to load: <exc>`.
- `_validate` (`:157-194`) checks, in order: `PLUGIN` is a dict; `PLUGIN['name']`
  matches `^[a-zA-Z_][a-zA-Z0-9_]{0,63}$` (`_NAME_RE`, `:22`); `description` is a
  non-empty string; `parameters` is a dict with `"type": "OBJECT"` (default
  `{"type": "OBJECT", "properties": {}}`, `:23`); `run` is callable.
  A malformed `PLUGIN_SETTINGS` is *ignored*, not fatal (`:187-189`).
- Name collisions reject the plugin, not the scan: against core tool names
  (`:256-258`) or against an earlier plugin in the same folder (`:259-262`).
  Core names include inline tools **and** every discovered `actions/*.py` tool
  (`main.py:669-684`), which is why `plugins/game_updater.py` is rejected today
  (see §3.3).
- Result: `PluginRegistry._plugins` holds only valid records; `_all_records`
  keeps valid + invalid for the UI listing (`:54-55`). Boot logs one line per
  file plus a summary (`:269-281`); only rejections are forwarded to the
  activity log via `notify` (`:285-286`).

### 1.2 The `PLUGIN` dict

| Key | Required | Notes |
| --- | --- | --- |
| `name` | yes | Tool name the model calls; identifier regex above. |
| `description` | yes | Model-facing trigger text; write it for a small model (explicit "use for" phrases and "do NOT use X" warnings are the house style). |
| `parameters` | yes | `{"type": "OBJECT", "properties": {...}, "required": [...]}`; `required` may be omitted for zero-arg tools. |
| `behavior` | no | `BLOCKING` or `NON_BLOCKING`; upper-cased from `_BEHAVIORS` (`:28`). No shipped plugin sets it. |
| `scheduling` | no | `WHEN_IDLE`, `SILENT` or `INTERRUPT` (`:29`). No shipped plugin sets it. |
| `brief` | no | Short description for a small-model tool budget, intended to be consumed via `providers/schema.py`; dormant in this checkout (see §9.12). |

Parameter descriptions are also prompt text: `telegram_remote` builds its action
enum and description from a capability table (`plugins/telegram_remote.py:694-695`),
and lifestyle plugins pass the user's verbatim utterance through as `query`/`request`
(e.g. `plugins/calorie_counter.py:39-44`, `plugins/excel_writer.py:37-43`).

### 1.3 `run()` and the calling convention

```python
def run(parameters: dict, player=None, session_memory=None) -> str:
```

- `_call_run` (`core/plugin_loader.py:144-154`) inspects the signature and passes
  `player` / `session_memory` only when declared (or when the plugin uses
  `**kwargs`), so a minimal `def run(parameters):` still works.
- Return value is spoken back through the model; return a short natural-language
  string. `None` is normalized to `"Done."` (`:96`).
- The convention is "never raise" — catch errors and return a spoken failure
  string (`plugins/_template.py:32-33`). The loader catches anyway as a second
  safety net.
- `player` is the UI object. Plugins log with `player.write_log(...)`, and use
  `player.request_say` for mid-task speech; `main.py:695` wires that to the same
  client-content injection the built-in actions get (`plugins/game_updater.py:2432-2449`).
- `session_memory` is reserved and currently always `None` from `main.py`
  (`main.py:1407`).

### 1.4 Execution, enable/disable and error surfaces

- `PluginRegistry.get_tool_declarations()` (`:64-76`) adds tools to the live
  session schema, skipping disabled plugins and including `behavior` only when set.
- `PluginRegistry.run(name, ...)` (`:87-101`):
  1. `require_owner()` from `core.execution_policy` (`:88-89`) — the same owner
     gate as every other tool, so a lower-trust channel can never reach a plugin;
  2. returns `"Plugin '<name>' is not available."` for unknown or invalid names;
  3. returns `"The '<name>' plugin is currently disabled."` when switched off;
  4. catches crashes, logs `Plugin '<name>' crashed during run(): ...` to the
     console, notifies the activity log, prints the traceback, and returns
     `"Sir, the '<name>' plugin failed: <e>"`.
- `scheduling` from the record is merged into the `FunctionResponse` in
  `main.py:1428-1430`, so a future `NON_BLOCKING` plugin can re-enter the
  conversation at the right moment.

Enable state is an opt-out model: `get_plugin_enabled` returns `True` unless
`plugins_enabled[<name>]` is `False` (`memory/config_manager.py:344-346`);
`save_plugin_enabled` persists the switch (`:389-402`).

### 1.5 Per-plugin settings and UI surfaces

- A plugin may declare `PLUGIN_SETTINGS = {"namespace": ..., "title": ...,
  "fields": [...], "action": {...}}`. `settings_schemas()` (`:104-127`) dedupes by
  namespace (a suite of plugins can share one form), merges stored values for
  pre-fill, and exposes an optional test/connect button.
- Values live in `plugin_config[<namespace>]` inside `config/api_keys.json`
  (ignored by Git): `get_plugin_config` (`memory/config_manager.py:355-359`),
  `get_plugin_setting` (`:362-364`), `save_plugin_config` (`:367-386`, merge-only
  read-modify-write).
- Wiring in `main.py:691-694`: `ui.get_plugins = registry.list_for_ui` and
  `ui.get_plugin_settings = registry.settings_schemas`.
- UI hosts: `PluginManagerOverlay` (`ui.py:1854`) lists valid and invalid plugins
  with their rejection reason; `PluginSettingsOverlay` (`ui.py:2478`) renders the
  declared fields, including `type: password` fields — treat those values as
  secrets and never print them.
- Only two files declare settings today: `plugins/telegram_remote.py:613-668`
  (bot token, pairing code, allow-lists, opt-in screen/camera toggles) and
  `plugins/game_updater.py:111` (never rendered — the plugin is rejected).

---

## 2. Plugin inventory

Twelve `.py` files ship in `plugins/`: the empty package marker, two files skipped
by discovery (a template and a shared helper), and nine plugin candidates. Eight
are live; one is rejected by name collision.

| File | Tool name | Entry points | What it does | Settings | Tests |
| --- | --- | --- | --- | --- | --- |
| `_template.py` | — (skipped) | `PLUGIN` :8, `run` :25 | Copy-me template and contract documentation. | — | — |
| `_telegram_ops.py` | — (helper) | `EXTRA_OPS` :67, `produce()` :665 | Shared Telegram extras (screenshots, hardware readout, STT/TTS) behind the bridge. | — | — |
| `telegram_remote.py` | `telegram_remote` | `PLUGIN` :670, `run` :1851 | Remote-control bridge: phone drives the computer over Telegram, machine pushes screenshots/status back. | :613 | — |
| `chat_takeover.py` | `chat_takeover` | `PLUGIN` :45, `run` :658 | Watches a visible non-WhatsApp chat and replies in the user's style until told to stop. | — | refusal path only |
| `game_updater.py` | `game_updater` (rejected) | `PLUGIN` :2461, `run` :2452 | Steam/Epic install, update, list, download status, daily schedule. | :111 (unreachable) | — |
| `water_reminder.py` | `water_reminder` | `PLUGIN` :24, `run` :181 | Periodic spoken hydration reminders plus intake tracking against a daily goal; state in `memory/water_state.json` (:22). | — | — |
| `pomodoro.py` | `pomodoro` | `PLUGIN` :27, `run` :240 | Focus/break timer with spoken transitions and today's focus totals; state in `memory/pomodoro_state.json` (:25). | — | — |
| `calorie_counter.py` | `calorie_counter` | `PLUGIN` :25, `run` :162 | Takes its own webcam photo of food and reports calories/macros. | — | — |
| `excel_writer.py` | `excel_writer` | `PLUGIN` :22, `run` :187 | Builds a real `.xlsx` (headers, rows, total, chart) on the Desktop from a spoken description. | — | — |
| `document_review.py` | `document_review` | `PLUGIN` :54, `run` :211 | Lays a contract/policy out on screen: what it commits to, points worth knowing before signing. | — | — |
| `quiz.py` | `quiz` | `PLUGIN` :58, `run` :276 | Puts a model-written quiz on the HUD; results return later as a `[QUIZ_DONE]` message. | — | — |

Notes:

- The two giants are `telegram_remote.py` (~2,100 lines) and `game_updater.py`
  (~2,515); every other plugin is roughly 180-740 lines.
- No plugin declares `behavior` or `scheduling`, so every plugin runs blocking
  with default scheduling behavior.
- Stateful plugins write JSON under `memory/`; both state files are currently
  missing from `.gitignore` (see §8).

---

## 3. Plugin highlights

### 3.1 `telegram_remote.py` — the security-boundary plugin

- Deliberately kept "the size of the thing it is: a security boundary"
  (`plugins/telegram_remote.py:174-177`). The capability table (`:221-229`) is the
  merge point for the model schema, the Telegram command menu and `/help`, so all
  three cannot drift.
- Constants block (`:183-218`) is the policy document: message age/skew limits,
  rate limiting, pairing window and tries, reply/turn windows, voice note and file
  caps, autostart timings.
- `PLUGIN_SETTINGS` (`:613-668`) defaults the dangerous switches *off*: screen
  (`allow_screenshot`, `:630-632`), camera (`allow_camera`, `:640-642`), autostart
  (`start_on_launch`, `:657-659`), voice replies and away alerts. Folders are the
  permission model for file transfer (`:643-652`). A `TEST CONNECTION` action
  button is attached at `:667`.
- The helper import is guarded (`:178-181`): if `_telegram_ops.py` is missing the
  bridge still loads and the extra ops "simply never appear in the schema, the menu
  or /help" — with an explicit hint at `:1196` and `:2002`.
- Outbound work is queued so `write_log` never blocks on the network (`:709-742`);
  `run()` dispatch is at `:1851`; the opt-in autostart thread is `_autostart`
  (`:2059-2099`).
- Fragility: `_telegram_ops.py` imports a `providers` package at `:490`
  (`from providers import registry`) and `:610` (`from providers import audio`) for
  STT/TTS. No `providers/` directory exists in this checkout and nothing references
  it in source control, so Telegram voice-note transcription and TTS raise
  `ModuleNotFoundError` at call time (caught by callers). The `brief` comment at
  `plugins/telegram_remote.py:684-688` also points at a `providers/schema.py`
  that does not exist.

### 3.2 `chat_takeover.py` — vision-driven chat fallback

- Scope is enforced at the top of `run()` (`plugins/chat_takeover.py:658-663`):
  only `instagram`, `discord`, `telegram`, `signal`, `slack` are accepted; WhatsApp
  and unspecified platforms return a failed `ToolResult` telling the model to use
  the WhatsApp tools instead.
- The description (`:45-63`) states the model-visible rules: platform is required,
  the tool watches the screen itself, call it exactly once per request, never use
  `screen_process` for an ongoing takeover.
- This is the only plugin with direct test coverage: it asserts the refusal for
  `whatsapp` and for an unspecified platform without ever grabbing the screen
  (`tests/test_whatsapp_identity_notifications.py:62-67`).

### 3.3 `plugins/game_updater.py` — a rejected duplicate

- The plugin and the core action both declare `"name": "game_updater"`
  (`plugins/game_updater.py:2462`, `actions/game_updater.py:1064`). Discovery
  prefers the action (core names win, `core/plugin_loader.py:256-258`), so the
  plugin is rejected at startup and its settings never render.
- This is intentional and documented: "One existing plugin is intentionally
  rejected because `game_updater.py` duplicates the core `game_updater` tool;
  diagnostics expose that exact reason" (`docs/VALIDATION.md:53-55`).
- Consequence: the 2,514-line plugin is unreachable through the tool schema
  while its `--scheduled` CLI path still runs when invoked by hand
  (`:2424-2427`); the scheduled task it installs points back at this file
  (`:2188`, `:2211`, `:2236`), so the duplication is not inert — it can drift from
  the core action that actually serves model calls.

---

## 4. Test suite map

Fifty test modules plus `tests/__init__.py`, containing 207 `def test_` methods.
Last recorded full pass: 207 tests in 73.9 s (`docs/VALIDATION.md:402-404`).

Run locally with the interpreter that launches Zaya (`readme.md:426-431`):

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -v
.venv\Scripts\python.exe -m ruff check --isolated --select E9,F63,F7,F82 core actions services memory main.py ui.py tests tools
```

| Group | Modules | What it pins |
| --- | --- | --- |
| Voice and audio | `test_voice`, `test_voice_turns`, `test_voice_priority`, `test_audio_ducking`, `test_live_listening`, `test_live_tool_workers` | Turn-taking, local speech boundaries, ducking, interruption, tool workers during playback. |
| Live session and credentials | `test_startup_recovery`, `test_gemini_keys` | Fresh startup vs saved checkpoints, bounded connect, key rotation/dedup/cooldowns. |
| Conversation and history | `test_conversation`, `test_history_display` | Durable turns, restore-on-demand, History views without live replay. |
| Browser | `test_browser`, `test_browser_integration`, `test_browser_media`, `test_browser_native`, `test_browser_recovery` | Real Chromium against local HTTP, native vs automation routing, closed-context recovery without replay. |
| WhatsApp and Hermes | `test_whatsapp_auto_mode`, `test_whatsapp_followups`, `test_whatsapp_handler`, `test_whatsapp_identity_notifications`, `test_whatsapp_queries`, `test_whatsapp_recovery`, `test_whatsapp_relays`, `test_whatsapp_store`, `test_hermes_bridge`, `test_hermes_sender`, `test_native_bridge`, `test_pairing`, `test_proactive`, `test_session_activity` | Identity merge, unread/dedup, auto-mode scope, owner relays, persistence, pairing, transport fixtures. |
| Policy, confirmation, runtime | `test_policy`, `test_confirmation`, `test_auto_execution`, `test_operator`, `test_runtime`, `test_tool_result` | Owner-only execution, confirmation gate, runtime operation IDs, normalized tool results. |
| Desktop, UI, companion | `test_app_integration`, `test_desktop_media`, `test_companion_bubble`, `test_zayabar`, `test_poke_voices`, `test_hud_state`, `test_identity`, `test_emotional_delivery`, `test_diagnostics`, `test_baseline`, `test_profile`, `test_project_syntax` | Qt smoke in subprocess, identity/task state, HUD/camera, poke audio fixtures, profile/memory roundtrips, repo-wide syntax. |
| Git, terminal, single instance | `test_git`, `test_terminal`, `test_single_instance` | Real temp git repos and SHA checks, terminal output/cancel, second-launch activation. |

Conventions worth keeping:

- `unittest` + `unittest.mock`; temporary directories for every file-touching test.
- Qt tests run a child process with `QT_QPA_PLATFORM=offscreen`; they never touch
  the owner's desktop.
- Browser tests launch real Chromium against local HTTP pages, never the personal
  profile (see `docs/VALIDATION.md:77-80`).
- WhatsApp tests use mocked/controlled transport; no real messages are sent.
- `tests/test_project_syntax.py:10` AST-parses every project Python source
  including `plugins` and `tools`, so plugin syntax at least parses under test.
- `tests/test_poke_voices.py:11` imports `tools.generate_poke_voices.generate` and
  asserts single-synthesis plus 24 kHz mono PCM output (`:16-27`).

---

## 5. Coverage gaps

- **Plugins** are almost untested. The only direct exercise is the `chat_takeover`
  refusal path (`tests/test_whatsapp_identity_notifications.py:62-67`). There is no
  coverage for `telegram_remote.py`, `_telegram_ops.py`, `game_updater.py`,
  `water_reminder.py`, `pomodoro.py`, `calorie_counter.py`, `excel_writer.py`,
  `document_review.py` or `quiz.py`.
- **`core/plugin_loader.py` itself has no dedicated tests.** The registry is only
  constructed as an empty stub for app integration
  (`tests/test_app_integration.py:45,51`); discovery, validation, collision
  rejection and `_call_run` signature adaptation are unpinned.
- **`dashboard/server.py` is never exercised.** Tests patch `DashboardServer` to
  raise an offline fixture error (`tests/test_conversation.py:221`,
  `tests/test_gemini_keys.py:140`, `tests/test_single_instance.py:195`), so the
  authenticated phone surface has no runtime regression coverage.
- **`ui.py` internals** are covered only end-to-end via the offscreen subprocess
  smoke (e.g. `test_app_integration`, `test_zayabar`, `test_companion_bubble`);
  overlay classes such as Plugin Manager and Plugin Settings have no unit tests.
- **Actions**: `actions/dev_agent.py` and `actions/file_processor.py` are not
  referenced by any test module.
- **Memory**: `memory/memory_manager.py` is only round-tripped for basic
  update/search (`tests/test_baseline.py:21-23`, `tests/test_profile.py:12-17`);
  `core/proactive_manager.py` is exercised through the WhatsApp notification tests.
- **CI lint scope** excludes `plugins/` and `dashboard/` from the ruff command;
  the only automated check plugin files get is the source parse in
  `test_project_syntax.py`.

---

## 6. Tooling and CI

### 6.1 `setup.py`

- Enforces a Python floor of 3.11 and warns above 3.13 (`setup.py:23-24`,
  `:32-55`).
- Installs `requirements.txt` (OS-specific extras filtered by pip markers), then
  Playwright `chromium` + `firefox` — browser install failure is non-fatal
  (`:74-90`).
- Checks `core/face_model.obj` for truncation and prints per-OS post-install
  notes for Windows pywin32, Linux native tools and macOS `osascript`
  (`:58-66`, `:94-120`).

### 6.2 `tools/`

- `tools/zaya_setup.py` — private setup CLI: `--install-hermes-hook`
  (`services.whatsapp.bridge.install_hook`, preserving pairing), `--profile`
  (local profile bootstrap), `--project` (project alias registration)
  (`:6-24`).
- `tools/generate_poke_voices.py` — pre-renders each configured Nika reaction once
  so playback never calls AI; writes 24 kHz mono 16-bit WAVs atomically via a
  `.tmp` replace (`:9-27`).

### 6.3 Dependencies

`requirements.txt` is grouped by concern and installs plugin extras up front
("dropping a .py into plugins/ should make it work on the next launch"); each
extra is imported inside a `try/except` at the point of use, so an uninstalled
extra disables exactly one feature (plugin extras include `openpyxl` for
`excel_writer` and `pygetwindow` for `game_updater`/`chat_takeover`). Heavy
extras (`pandas`, `pydub`, `mediapipe`) and the wake word package are opt-in and
documented as such.

### 6.4 CI (`.github/workflows/tests.yml`)

- `windows-latest`, Python 3.13, pip cache (`:13-20`).
- Installs `requirements.txt` plus `ruff`, then `playwright install chromium`
  (`:22-24`).
- Lint gate: `python -m ruff check --isolated --select E9,F63,F7,F82 core
  actions services memory main.py ui.py tests tools` (`:26`) — error-class checks
  only, and `plugins/` is not in scope.
- Test gate: `python -m unittest discover -s tests -v` (`:28`).
- Triggers: pushes to `zaya-updates` **and** `main`, pull requests to `main`
  (`:2-6`). The legacy branch in the workflow matches the still-unretired
  `zaya-updates` policy text in `docs/ZAYA_IMPLEMENTATION_PLAN.md:37-66`; the
  current delivery branch is `main` (`docs/implementation.md:7-8`).

---

## 7. Documentation inventory

| File | Role |
| --- | --- |
| `readme.md` | User-facing setup, optional integrations, configuration table (`:386-396`), architecture list (`:402-416`), test commands (`:422-437`) and troubleshooting table (`:439-449`). |
| `AGENTS.md` | Owner workflow: commit identity, branch policy, privacy rules, auto-reply behavior. |
| `CREDITS.md` | Attribution; visible assistant identity is Zaya, created by Sajan Rai. |
| `LICENSE` | Upstream license attribution preserved alongside Zaya branding. |
| `docs/implementation.md` | Index into the plan and validation docs; confirms `main` is the delivery branch. |
| `docs/VALIDATION.md` | Append-only evidence log (latest entries Oct 15; 207 tests). Historical entries intentionally supersede each other — read the top blocks first. |
| `docs/ZAYABAR.md` | Taskbar companion configuration (`zayabar.json`, artwork, poke clips). |
| `docs/ZAYA_IMPLEMENTATION_PLAN.md` | Original implementation contract. |

Staleness to fix when convenient: the plan's §1.1 still mandates "Work only on
`zaya-updates`" (`docs/ZAYA_IMPLEMENTATION_PLAN.md:37-66`) while the repo, CI and
`docs/implementation.md` have moved to `main`; `plugins/_template.py:13-14` still
tells authors to "see game_updater's description in main.py", but `main.py` is no
longer where that description lives (`actions/game_updater.py:1064`).

---

## 8. Repository hygiene

Tracked but questionable:

- `plugins/Hostinger VPS.zip` is tracked (67,017 bytes; five files under
  `Hostinger VPS/`: `cloud.py`, `cloud_agent.py`, `README.txt`, `reminder.py`,
  `lazyimport.py`). It breaks the "one plugin = one .py file" distribution model,
  cannot be discovered by the loader, and contains code that will silently rot.
- `assets/` is 7.31 MB across 11 files, including
  `assets/Don't Scream_ Roblox Horror Live.png` (the largest single asset) and
  `assets/standby.gif`.
- Other large tracked files: `ui.py` (~260 KB), `main.py` (~138 KB),
  `plugins/game_updater.py` (~113 KB), `dashboard/static/crypto-js.min.js` (~61 KB).

Ignored / untracked:

- Ignored correctly: `config/api_keys.json` (`.gitignore:9`), `memory/*.db`
  (`:25`), `memory/long_term.json` (`:24`), `memory/projects.json` (`:64`),
  `memory/zayabar_state.json` (`:65`), `memory/backups/` (`:68`),
  `memory/profile*.json` (`:70`), `config/hermes*.json` (`:72`), and
  `plugins/*.exe` (`:76`) — the latter currently masks a local 57 MB
  `windowsdesktop-runtime` installer in `plugins/`.
- Untracked at snapshot: `_outline.txt` (working notes), `docs/codebase/` (this
  doc set) and `memory/water_state.json` (63 bytes, plugin state).
- Gap: `memory/water_state.json` is **not** matched by any `.gitignore` rule, and
  neither is `memory/pomodoro_state.json` once created. A broad `git add memory/`
  would commit personal routine data that the rest of the project deliberately
  keeps local. Consider `memory/*_state.json` (or explicit entries) alongside the
  existing `memory/zayabar_state.json` rule.

---

## 9. Observations and risks

1. **`plugins/game_updater.py` is dead weight with a live blast radius.** The
   plugin is rejected by the name collision (`core/plugin_loader.py:256-258`),
   yet its scheduled-task installer writes `--scheduled` tasks pointing at
   `plugins/game_updater.py` (`plugins/game_updater.py:2188`, `:2236`). Two copies
   of the same capability (~2,515-line plugin, ~1,100-line action) will drift.
   Decide which side is canonical and delete the other.
2. **Missing `providers` package breaks documented Telegram features.**
   `plugins/_telegram_ops.py:490` and `:610` import `providers` for STT/TTS; no
   such package exists in this checkout. Voice-note transcription and voice
   replies degrade at call time, and `plugins/telegram_remote.py:684-688` points
   at a `providers/schema.py` comment that is also stale.
3. **Plugins ship with almost no tests and are outside CI lint.** The nine plugin
   candidates (roughly 6,800 lines) get no unit coverage; only `chat_takeover`'s
   refusal path is asserted, and the ruff gate skips `plugins/`. A regression in
   the Telegram bridge, reminders or quiz would only show at runtime.
4. **The plugin loader's own contract is unpinned.** Validation rules, collision
   rejection and `_call_run` kwargs adaptation (`core/plugin_loader.py:144-154`,
   `:157-194`) have no dedicated tests; a change could silently change how every
   plugin loads. A small `tests/test_plugin_loader.py` using temp plugin files
   would close this cheaply.
5. **Plugin Manager/Settings overlays have no unit tests.** `ui.py:1854` and
   `ui.py:2478` render user-editable security toggles (screenshot, camera,
   autostart) but are only covered indirectly. A malformed `PLUGIN_SETTINGS` is
   tolerated by design (`core/plugin_loader.py:187-189`), so UI regressions are
   the likeliest failure mode.
6. **Dashboard server is untested by construction.** Every suite that boots the
   app patches `DashboardServer` to raise (`tests/test_conversation.py:221`,
   `tests/test_gemini_keys.py:140`, `tests/test_single_instance.py:195`). It is an
   authenticated phone surface, which is exactly the kind of code that deserves a
   test before it deserves trust.
7. **Plugin state files escape the privacy pattern.** `memory/water_state.json`
   (and `pomodoro_state.json` when used) are not gitignored while sibling state
   files are (`memory/zayabar_state.json`, `.gitignore:65`). One careless
   `git add memory/` would commit routine data; fix the ignore list.
8. **`plugins/Hostinger VPS.zip` should not be tracked.** It is an unzipped-style
   bundle inside `plugins/`, invisible to discovery, and duplicates code that
   cannot be updated. Move it out of the repo or document it as an archive.
9. **Branch/workflow documentation is inconsistent.** The plan mandates
   `zaya-updates` (`docs/ZAYA_IMPLEMENTATION_PLAN.md:37-66`), CI still triggers on
   it (`.github/workflows/tests.yml:4`), but `docs/implementation.md:7-8` and the
   commit history say `main`. Retire or annotate the legacy branch text so the
   next contributor is not bounced to the wrong branch.
10. **`docs/VALIDATION.md` is append-only and easy to misread.** The file records
    68 tests in the Oct 14 entry (`:24-30`) and 207 in the latest entry (`:402`).
    Keep new entries on top and treat older entries as historical evidence, not
    current counts.
11. **`plugins/_template.py` is a good contract but incomplete onboarding.** It
    documents `PLUGIN` and `run()` well, but never mentions `PLUGIN_SETTINGS`,
    `behavior`/`scheduling`, or the `plugins._helper` distribution rule that
    `_load_error` handles (`core/plugin_loader.py:197-220`). Authors discover
    those by reading `telegram_remote.py` instead — worth folding into the
    template.
12. **`brief` is a one-plugin optimization with a dead reference.** Only
    `telegram_remote` uses it (`plugins/telegram_remote.py:686-688`) and its
    comment points at missing code. Either implement the `providers/schema.py`
    budget path or drop the key until it exists.
